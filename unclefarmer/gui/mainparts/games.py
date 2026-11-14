"""The Games list, reading the selected game, the live status fields and the character scans."""

from __future__ import annotations

import threading

import wx

from ... import applog, jsonio, nearby, scan, settings
from ...engine.runner import Run
from ...errors import carry_on
from ...i18n import _
from ...link import AgentError, AgentLink, agents, games, server_name
from ..common import error, first_selected, select_row
from .base import SNAP_FRESH, FrameParts, Game, duration_text, out_of, profile_of, saved_item
from typing import Any

UNAVAILABLE_RETRY = 15.0   # seconds between quiet checks of an agent that didn't answer the last refresh


def _answers(pid: int) -> bool:
    """Whether this game's agent answers now: one short ping, no list rebuild."""
    try:
        with AgentLink(pid=pid, timeout=1) as a:
            return a.send("ping") == "pong"
    except (AgentError, OSError, ValueError):
        return False


class GamesMixin(FrameParts):
    # ------------------------------------------------------------ game and status
    def selected_index(self) -> int | None:
        i = first_selected(self.game_list)
        return i if 0 <= i < len(self.games) else None

    def selected_pid(self) -> int | None:
        i = self.selected_index()
        return self.games[i][0] if i is not None else None

    def selected_character(self) -> str | None:
        i = self.selected_index()
        return self.games[i][1] if i is not None else None

    def selected_profile(self) -> str | None:
        """The selected game profile, but only while a character is actually logged in."""
        return self.selected_character() if profile_of(self.snapshot()) else None

    def game_row(self, game: Game) -> tuple[str, str, str]:
        pid, name, where = game
        run = self.runs.get(pid)
        if not run:
            state = _("Stopped")
        elif self.is_paused(pid):
            state = _("Paused {what}", what=run.title)
        else:
            state = _("Running {what}", what=run.title)
        return (settings.profile_display(name) if name else _("Not logged in"), where or "", state)

    def label_games(self) -> None:
        """Rewrite the rows in place (running or not) without moving the selection."""
        for i, game in enumerate(self.games):
            for col, text in enumerate(self.game_row(game)):
                if self.game_list.GetItemText(i, col) != text:
                    self.game_list.SetItem(i, col, text)

    def refresh_games(self) -> None:
        if self.destroyed:
            return
        old = self.selected_pid()
        self.games = games()
        advertised = {pid: (port, secret) for port, pid, secret in agents()}
        confirmed = {pid for pid, _name, _where in self.games}
        # A crashed game can leave its port record behind and Windows can later reuse its PID.
        # Do not make poll() refresh recursively for that record. A restarted agent has a new
        # port or secret, so poll() will immediately notice it again; a live game that was only
        # slow to answer is pinged again every UNAVAILABLE_RETRY seconds (poll), so it comes back.
        self.unavailable_agents = {pid: record for pid, record in advertised.items() if pid not in confirmed}
        self.unavailable_checked = self.clock.time()
        # a game whose bot is still running stays in the list even if it didn't answer just now
        listed = {g[0] for g in self.games}
        for pid, run in self.runs.items():
            if pid not in listed:
                self.games.append((pid, run.profile or run.character, None))
        self.filling = True
        self.game_list.DeleteAllItems()
        for i, game in enumerate(self.games):
            for col, text in enumerate(self.game_row(game)):
                if col == 0:
                    self.game_list.InsertItem(i, text)
                else:
                    self.game_list.SetItem(i, col, text)
        if not self.games:
            self.game_list.InsertItem(0, _("No game found"))
        pids = [g[0] for g in self.games]
        sel = pids.index(old) if old in pids else 0
        select_row(self.game_list, sel)
        self.filling = False
        if self.selected_pid() != old:
            self.pick_last_run()
        self.update_buttons()
        self.poll()

    def game_changed(self) -> None:
        self.pick_last_run()
        self.update_buttons()
        self.poll()

    def pick_last_run(self) -> None:
        """Each character remembers what it ran last; choosing its game selects that again."""
        if self.selected_pid() in self.runs:
            return
        last = settings.last_run_of(self.s, self.selected_character())
        if last:
            want = saved_item(last)
            if want in self.items:
                self.what.SetSelection(self.items.index(want))

    def snapshot(self, pid: int | None = None, max_age: float = SNAP_FRESH) -> dict[str, Any] | None:
        """A game's state (the selected game's unless pid is given), or None. Used by the poll, by
        the editors' "from the game" buttons and by the Chat window; a reading newer than max_age
        is reused, so opening a window right after a poll doesn't wait on the agent again."""
        if pid is None:
            pid = self.selected_pid()
            if pid is None:
                self.refresh_games()
                pid = self.selected_pid()
                if pid is None:
                    return None
        s = self.cached(pid, max_age)
        return s if s is not None else self._snapshot_for(pid)

    def cached(self, pid: int | None, max_age: float = SNAP_FRESH) -> dict[str, Any] | None:
        if self.snap and self.snap[0] == pid and self.clock.time() - self.snap[2] <= max_age:
            return self.snap[1]
        return None

    @staticmethod
    def _snapshot_for(pid: int) -> dict[str, Any] | None:
        try:
            with AgentLink(pid=pid, timeout=3) as a:
                s = a.json("mem")
                if jsonio.is_object(s) and s.get("ok"):
                    s["_server"] = server_name(a)
                    account: object = {}
                    try:
                        account = jsonio.loads(a.send("loginaccount"))
                    except ValueError:
                        pass
                    if jsonio.is_object(account) and account.get("ok") and isinstance(account.get("email"), str):
                        s["_account"] = account["email"]
                    return s
                return None
        except (AgentError, OSError, ValueError):
            return None

    def request_snapshot(self, pid: int | None) -> None:
        """Read the game on a worker thread: the window stays responsive if the agent is slow or
        the game is hung, which a three-second read on the window's thread was not."""
        if self.destroyed or pid is None or self.snap_busy:
            return
        if self.snap and self.snap[0] == pid and self.clock.time() - self.snap[2] <= 2.0:
            return              # like a fresh reading, a fresh failure: don't hammer the agent
        self.snap_busy = True
        game = pid

        def work() -> None:
            try:
                s = self._snapshot_for(game)
                wx.CallAfter(self._got_snapshot, game, s)
            except Exception as e:        # a dead worker must not stop the status for good
                carry_on(e, "reading the game status")
                self.snap_busy = False
        threading.Thread(target=work, daemon=True).start()

    def _got_snapshot(self, pid: int, s: dict[str, Any] | None) -> None:
        self.snap_busy = False
        if self.destroyed:
            return
        self.snap = (pid, s, self.clock.time())
        if pid == self.selected_pid():
            self.poll()

    def show_status(self, **values: str) -> None:
        for key, ctrl in self.fields.items():
            text = values.get(key, "")
            if ctrl.GetValue() != text:
                ctrl.ChangeValue(text)

    def poll(self) -> None:
        if self.destroyed:
            return
        # a client opened or closed since the list was made: remake it (port files only, cheap)
        live = {pid for port, pid, secret in agents()
                if self.unavailable_agents.get(pid) != (port, secret)} | set(self.runs)
        if live != {g[0] for g in self.games}:
            self.refresh_games()
            return
        if self.unavailable_agents and self.clock.time() - self.unavailable_checked >= UNAVAILABLE_RETRY:
            self.unavailable_checked = self.clock.time()
            if any(_answers(pid) for pid in self.unavailable_agents):
                self.refresh_games()
                return
        running = len(self.runs)
        self.sync_pause()
        self.label_games()
        self.SetStatusText(_("{games} games, {bots} bots running", games=len(self.games), bots=running)
                           if len(self.games) != 1 else
                           (_("1 game, bot running") if running else _("1 game, bot stopped")))
        if not self.games:
            self.show_status(activity=_("No game found. Start Mist World. (First time? File, Settings, Install.)"))
            return
        self.progress()
        self.keep_silent()
        self.keep_voice_fix()
        restorer = getattr(self, "sound_restorer", None)
        if restorer is not None:
            restorer.sync([game[0] for game in self.games])
        self.keep_messengers()
        self.keep_chats()
        pid = self.selected_pid()
        run = self.runs.get(pid) if pid is not None else None
        values = {"run": self.run_text(run)}
        if pid is not None and run:
            values["activity"] = self.last_line.get(pid, _("Starting"))
        self.request_snapshot(pid)              # a worker fills the cache; never blocks here
        s = self.cached(pid, 10.0)
        tried = self.snap is not None and self.snap[0] == pid and self.clock.time() - self.snap[2] <= 10.0
        if s is None and not tried:
            values.setdefault("activity", _("Reading the game"))
            self.show_status(**values)
            return
        self.render(pid, s, values)

    def render(self, pid: int | None, s: dict[str, Any] | None, values: dict[str, str]) -> None:
        """The status fields from one game reading. A reading can be partial (at the log-in screen,
        or an agent still starting): no key is trusted without asking."""
        run = self.runs.get(pid) if pid is not None else None
        i = self.selected_index()
        if i is None or pid is None:
            self.show_status(**values)
            return
        me = s.get("self") if s is not None else None
        if s is None or not jsonio.is_object(me) or not me.get("name") or not jsonio.is_object(s.get("map")) \
                or not s["map"].get("name"):
            values.setdefault("activity", _("The game is running but no character is logged in."))
            self.show_status(**values)
            return
        game = self.games[i]
        profile = profile_of(s)
        same = bool(game[1] and profile and settings.same_character(game[1], profile))
        if same and game[1] and settings.profile_server(game[1]) and not settings.profile_server(profile or ""):
            profile = game[1]       # a brief failed lookup must not make an announced identity ambiguous again
        if not same or game[1] != profile or game[2] != s["map"]["name"]:     # logged in, changed map, switched character
            self.games[i] = (game[0], profile, s["map"]["name"])
            self.label_games()
        elif game[1]:
            profile = game[1]       # retain the server label gathered with this game's first reading
        account = s.get("_account")
        if profile and isinstance(account, str):
            try:
                settings.remember_character_account(profile, account)
            except (OSError, ValueError) as e:
                applog.write("couldn't remember the saved account for %s: %r" % (profile, e), "WARNING")
        if not run:
            self.auto_scan_async(profile or me["name"], pid)     # never while the bot runs: it has the keyboard
            values["activity"] = _("Ready")
        sheet: dict[str, Any] = me.get("sheet") or {}
        vit: dict[str, Any] = me.get("vitals") or {}
        mp = vit.get("mp") if vit.get("mp", -1) >= 0 else sheet.get("mp")
        values.update(
            where=_("{map}, {x}, {y}", map=s["map"]["name"], x=int(me.get("x", 0)), y=int(me.get("y", 0))),
            hp=out_of(me.get("hp"), me.get("maxhp")),
            mp=out_of(mp, sheet.get("maxmp")),
            pet=nearby.pet_text(s),
            players=nearby.players_text(s),
            bag=(_("{pct}% full ({load} of {max})", pct=int(100.0 * sheet["load"] / sheet["maxload"]),
                   load=sheet["load"], max=sheet["maxload"]) if sheet.get("maxload", 0) > 0 and sheet.get("load", -1) >= 0
                 else _("Not read yet")),
            drop=(_("{left} left", left=duration_text(sheet["drop_seconds"])) if sheet.get("drop_seconds", -1) >= 0
                  else _("Not read yet")))
        self.show_status(**values)

    def run_text(self, run: Run | None) -> str:
        if not run:
            return _("Not running")
        bits = [duration_text(self.clock.time() - run.started)]
        bot = run.bot
        if bot is not None:
            bits.append(_("{n} kills", n=bot.kills))
            if bot.deaths:
                bits.append(_("{n} deaths", n=bot.deaths))
        return ", ".join(bits)

    def auto_scan(self, name: str, pid: int | None = None) -> None:
        """Scan a logged-in character into its profile when it has never been scanned or the scan
        is old: the player never has to type skills, potions, beasts or pets in. Blocking: the
        poll calls auto_scan_async instead."""
        when: dict[str, float] = getattr(self, "scanned", {})
        self.scanned = when
        if self.clock.time() - when.get(name, 0) < scan.RESCAN_AFTER:
            return
        when[name] = self.clock.time()
        pid = self.selected_pid() if pid is None else pid
        try:
            with AgentLink(pid=pid, timeout=5) as a:
                scan.scan_and_save(a, name, self.s.get("game_folder", ""))
        except Exception as e:       # scanning is a convenience; never break the window over it
            carry_on(e, "scanning a character")
            applog.write("auto-scan of %s failed: %r" % (name, e), "WARNING")
            when[name] = self.clock.time() - scan.RESCAN_AFTER + 60     # try again in a minute

    def auto_scan_async(self, name: str, pid: int) -> None:
        """The poll's scan, on a worker thread: the status keeps updating while it reads the game."""
        when: dict[str, float] = getattr(self, "scanned", {})
        if not name or name in self.scanning or self.clock.time() - when.get(name, 0) < scan.RESCAN_AFTER:
            return
        self.scanning.add(name)

        def work() -> None:
            try:
                self.auto_scan(name, pid)
            finally:
                self.scanning.discard(name)
        threading.Thread(target=work, daemon=True).start()

    def scan_now(self) -> None:
        name = self.selected_profile()
        if not name:
            error(self, _("Log in to a character in the game first."))
            return
        if self.selected_pid() in self.runs:
            error(self, _("Stop the bot first. It uses the keyboard while it runs."))
            return
        self.scanned = getattr(self, "scanned", {})
        self.scanned.pop(name, None)
        with wx.BusyCursor():
            self.auto_scan(name)
        self.say(_("{name} scanned.", name=settings.profile_display(name)))
