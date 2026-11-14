"""What to run (the Plans and scripts list) and running it: start, stop, pause, errands, follow."""

from __future__ import annotations

import time

import wx

from ... import settings
from ...engine import plan as plans
from ...engine.runner import Run
from ...engine.script import check as check_script, login_target
from ...i18n import _
from ..common import error, save_file
from ..plan import plan_text
from .base import FrameParts, Item, foreground_pid, saved_item
from collections.abc import Callable

LOGIN_OPEN_RETRY = 90.0


def run_text_and_profile(item: Item, profile: str | None) -> tuple[str | None, str | None, str | None]:
    """Read one item and resolve its optional ``login`` directive before a run is made.

    The returned error is already suitable for a dialog or a remote reply.
    """
    try:
        if item[0] == "plan":
            text = plans.to_script(plans.load(item[1]))
        else:
            with open(plans.script_path(item[1]), encoding="utf-8") as f:
                text = f.read()
    except (OSError, ValueError) as e:
        return None, None, _("Couldn't open it: {err}", err=e)
    problem = check_script(text)
    if problem:
        return None, None, problem
    target = login_target(text) if item[0] == "script" else None
    if target:
        matches = [known for known, _email in settings.automatic_login_profiles()
                   if target.casefold() in (known.casefold(), settings.profile_display(known).casefold())]
        if len(matches) != 1:
            return None, None, _("The script's login character is not a known saved character: {name}", name=target)
        target = matches[0]
    if profile and target and not settings.same_character(profile, target):
        return None, None, _("The scheduled character and the script's login character are different.")
    return text, profile or target, None


class RunsMixin(FrameParts):
    # ------------------------------------------------------------ what to run
    def item_label(self, item: Item) -> str:
        kind, name = item
        return name if kind == "plan" else _("{name} (script)", name=name)

    def fill_runs(self, select: Item | None = None) -> None:
        self.items = [("plan", n) for n in plans.names()] + [("script", n) for n in plans.script_names()]
        labels = [self.item_label(it) for it in self.items]
        self.what.Set(labels or [_("No plans yet")])
        self.plan_list.Set(labels)
        want = select or (saved_item(self.s.get("last_run", "")) if self.s.get("last_run") else None)
        i = self.items.index(want) if want in self.items else 0
        self.what.SetSelection(i)
        if self.items:
            self.plan_list.SetSelection(self.items.index(select) if select in self.items else
                                        max(0, min(self.plan_list.GetSelection(), len(self.items) - 1)))
        self.show_summary()

    def selected_item(self) -> Item | None:
        """The plan chosen to run on the Bot tab."""
        i = self.what.GetSelection()
        return self.items[i] if 0 <= i < len(self.items) else None

    def listed_item(self) -> Item | None:
        """The plan or script selected on the Plans tab."""
        i = self.plan_list.GetSelection()
        return self.items[i] if 0 <= i < len(self.items) else None

    def active_item(self) -> Item | None:
        """The plan command's target: the Plans list there, otherwise the Bot tab's choice."""
        return self.listed_item() if self.nb.GetSelection() == 1 else self.selected_item()

    def show_summary(self) -> None:
        item = self.listed_item()
        if not item:
            self.summary.ChangeValue(_("No plans yet. Press New plan to make one."))
            return
        try:
            if item[0] == "plan":
                text = plan_text(plans.load(item[1]))
            else:
                with open(plans.script_path(item[1]), encoding="utf-8") as f:
                    text = f.read()
        except (OSError, ValueError) as e:
            text = _("Couldn't open it: {err}", err=e)
        self.summary.ChangeValue(text)

    def on_plan_key(self, evt: wx.KeyEvent) -> None:
        if wx.Window.FindFocus() is not self.plan_list:
            evt.Skip()
            return
        k = evt.GetKeyCode()
        if k in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.edit_selected()
        elif k == wx.WXK_DELETE:
            self.delete_selected()
        else:
            evt.Skip()

    def item_text(self, item: Item) -> str:
        kind, name = item
        if kind == "plan":
            return plans.to_script(plans.load(name))
        with open(plans.script_path(name), encoding="utf-8") as f:
            return f.read()

    # ------------------------------------------------------------ running
    def update_buttons(self) -> None:
        """The buttons follow the selected game: another game can be started while one runs."""
        pid = self.selected_pid()
        on = pid in self.runs
        self.start_btn.Enable(pid is not None and not on and bool(self.items))
        self.stop_btn.Enable(on)
        self.sync_pause()
        self.what.Enable(not on and bool(self.items))
        if pid is not None and on:
            item = ("plan" if self.runs[pid].kind == "plan" else "script", self.runs[pid].title)
            if item in self.items:
                self.what.SetSelection(self.items.index(item))
    def is_paused(self, pid: int | None) -> bool:
        run = self.runs.get(pid) if pid is not None else None
        return bool(run and run.bot is not None and run.bot.paused.is_set())

    def sync_pause(self) -> None:
        """The Pause button follows the selected game's run: Pause while it runs, Go on while paused
        (a private message can pause and resume it too)."""
        pid = self.selected_pid()
        run = self.runs.get(pid) if pid is not None else None
        label = _("Go &on") if self.is_paused(pid) else _("&Pause")
        if self.pause_btn.GetLabel() != label:
            self.pause_btn.SetLabel(label)
        self.pause_btn.Enable(bool(run and run.bot is not None))

    def toggle_pause(self, pid: int | None = None) -> None:
        """Pause the run where it is - keys let go, the run not ended - or let a paused one go on.
        While paused the game is the player's: their own Shift, Ctrl and Alt work in it again."""
        pid = self.selected_pid() if pid is None else pid
        run = self.runs.get(pid) if pid is not None else None
        if not run or run.bot is None:
            self.say(_("The bot isn't running."))
            return
        if run.bot.paused.is_set():
            run.bot.paused.clear()
            self.say(_("Going on"), run)
        else:
            run.bot.paused.set()
            self.say(_("Paused"), run)
        self.sync_pause()
        self.label_games()

    def toggle(self) -> None:
        """The Pause key: the game window in front if it is one of ours, else the selected game."""
        pid = foreground_pid()
        if pid not in {g[0] for g in self.games}:
            pid = self.selected_pid()
        if pid in self.runs:
            self.stop(pid)
        else:
            self.start(pid)

    def automatic_login_window(self, profile: str) -> tuple[int | None, str]:
        """Find a window for *profile*, opening exactly one if no usable client exists.

        The eventual sign-in remains in :class:`Run`, after the game's agent is reachable.  This
        boundary only owns choosing or opening a client, which lets schedules and scripts follow
        the identical guarded sequence.
        """
        self.refresh_games()
        pending = getattr(self, "pending_logins", None)
        if pending is None:
            pending = self.pending_logins = {}
        pid = next((g[0] for g in self.games if settings.is_profile_of(g[1], profile)), None)
        if pid is not None:
            pending.pop(profile, None)
            return pid, ""
        signed_out = [g[0] for g in self.games if not g[1] and g[0] not in self.runs]
        if len(signed_out) == 1:
            pending.pop(profile, None)
            return signed_out[0], ""
        label = settings.profile_display(profile)
        if len(signed_out) > 1:
            return None, _("{name} has more than one signed-out game; close the extras or log in first", name=label)
        opened = pending.get(profile)
        if opened is not None and time.monotonic() - opened < LOGIN_OPEN_RETRY:
            return None, _("opening a game for {name}", name=label)
        problem = self.open_client_for_login()
        if problem:
            pending.pop(profile, None)
            return None, problem
        pending[profile] = time.monotonic()
        return None, _("opening a game for {name}", name=label)

    def _game_to_start(self, profile: str | None) -> tuple[int | None, str]:
        """The selected game, else the character's own (opening one to log in): (pid, why we wait)."""
        pid = self.selected_pid()
        if pid is None:
            self.refresh_games()
            pid = self.selected_pid()
        if pid is None and profile:
            return self.automatic_login_window(profile)
        return pid, ""

    def _item_for_game(self, pid: int, item: Item | None) -> Item | None:
        """Started from inside a game window: what that character ran last, if anything."""
        if pid == self.selected_pid():
            return item
        name = next((g[1] for g in self.games if g[0] == pid), None)
        last = settings.last_run_of(self.s, name)
        return saved_item(last) if last and saved_item(last) in self.items else item

    def start(self, pid: int | None = None, item: Item | None = None, remote: bool = False,
              profile: str | None = None) -> str | None:
        """Start a bot. remote: asked by private message - no message boxes; returns what to answer."""
        def fail(text: str) -> str | None:
            if remote:
                return text
            error(self, text)
            return None
        given = item
        wanted = profile                 # the scheduled character, before a script's login can name one
        item = item or self.selected_item()
        text: str | None = None
        if item:
            # read first: a script's `login` line names the character whose game it needs
            text, profile, problem = run_text_and_profile(item, wanted)
            if problem or text is None:
                return fail(problem or _("Couldn't open it."))
        if pid is None:
            pid, waiting = self._game_to_start(profile)
            if pid is None and waiting:
                self.say(waiting)
                return waiting if remote else None
        if pid is None:
            self.say(_("No game with the agent is running."))
            return None
        if pid in self.runs:
            return _("Already running.")
        chosen = item if given else self._item_for_game(pid, item)
        if chosen != item:
            item, text = chosen, None    # that item's own steps, never the selected one's
        if not item:
            self.say(_("Make a plan first, in the Plans tab."))
            return _("There's no plan to run.")
        if text is None:
            text, profile, problem = run_text_and_profile(item, wanted)
            if problem or text is None:
                return fail(problem or _("Couldn't open it."))
        self.s["last_run"] = "%s:%s" % item
        name = next((g[1] for g in self.games if g[0] == pid), None)
        if name:
            self.s.setdefault("last_runs", {})[settings.stable_key(name)] = "%s:%s" % item
        save_file(self, settings.save_app, self.s)      # a failed save must not stop the start
        run = Run(text, item[1], pid, self.on_log, self.on_done, clock=self.clock)
        run.locate = self.locate
        run.last_seen = self.last_seen
        run.kind = item[0]
        run.character = settings.profile_name(name) or None   # for the log until the run reads it from the game itself
        run.profile = profile or name
        self.runs[pid] = run
        self.last_line[pid] = _("Starting")
        self.label_games()
        self.update_buttons()
        run.start()
        self.poll()
        return _("Starting {what}.", what=item[1])

    def run_errand(self, text: str, title: str, walk: bool = False) -> None:
        """A one-off job for the selected game, run like a script: a tool from the Tools menu, or
        the walking assistant (walk)."""
        pid = self.selected_pid()
        if pid is None:
            self.say(_("No game with the agent is running."))
            return
        if pid in self.runs:
            self.say(_("Stop the bot first."))
            return
        run = Run(text, title, pid, self.on_log, self.on_done, walk=walk, clock=self.clock)
        run.locate = self.locate
        run.last_seen = self.last_seen
        run.kind = "errand"
        run.profile = self.selected_character()
        run.character = settings.profile_name(run.profile) or None
        self.runs[pid] = run
        self.last_line[pid] = _("Starting")
        self.label_games()
        self.update_buttons()
        run.start()

    def errand_for(self, pid: int, text: str, title: str, tell: Callable[[str], None] | None = None,
                   follows: str | None = None) -> str | None:
        """A job asked for by private message, run like the walking assistant (stays where it ends);
        tell(text) answers the player when it ends by itself."""
        if pid in self.runs:
            return _("Busy - send stop first.")
        run = Run(text, title, pid, self.on_log, self.on_done, walk=True, clock=self.clock)
        run.locate = self.locate
        run.last_seen = self.last_seen
        run.tell = tell
        run.kind = "errand"
        run.follows = follows
        run.profile = self.character(pid)
        run.character = settings.profile_name(run.profile) or None
        self.runs[pid] = run
        self.last_line[pid] = _("Starting")
        self.label_games()
        self.update_buttons()
        run.start()
        return None

    def follow_for(self, pid: int, leader: str, tell: Callable[[str], None] | None = None) -> str | None:
        """'follow' from a trusted player: this game's character follows them. A run already going
        is stopped first, and following starts once it has ended. Returns what to answer."""
        run = self.runs.get(pid)
        if run and getattr(run, "follows", None) == leader.lower():
            return _("Already following you.")
        if run:
            run.stop()
            self._when_stopped(pid, lambda: self._start_follow(pid, leader, tell))
            return _("Stopping {what}, then following you.", what=run.title)
        return self._start_follow(pid, leader, tell)

    def _when_stopped(self, pid: int, then: Callable[[], object], tries: int = 0) -> None:
        if self.destroyed:
            return
        if pid in self.runs and tries < 240:          # a run can take a while to end safely
            wx.CallLater(500, self._when_stopped, pid, then, tries + 1)
        elif pid not in self.runs:
            then()
        else:
            self.say(_("The bot didn't stop in time, so it isn't following you."))

    def _start_follow(self, pid: int, leader: str, tell: Callable[[str], None] | None = None) -> str:
        # an errand that stays where it ends: no daily stop, no results, no end place
        busy = self.errand_for(pid, 'follow "%s"' % leader, _("following {name}", name=leader), tell,
                               follows=leader.lower())
        return busy or _("Following you.")

    def unfollow(self, pid: int) -> str | None:
        run = self.runs.get(pid)
        if not run or not getattr(run, "follows", None):
            return _("I'm not following anyone.")
        run.stop()
        return _("Stopped following.")

    def stop(self, pid: int | None = None) -> None:
        which = self.selected_pid() if pid is None else pid
        run = self.runs.get(which) if which is not None else None
        if run:
            self.say(_("Stopping"), run)
            run.stop()

    def stop_all(self) -> None:
        if not self.runs:
            self.say(_("No bot is running."))
            return
        self.say(_("Stopping every bot"))
        for run in list(self.runs.values()):
            run.stop()

    def tagged(self) -> bool:
        """With more than one game, every log line says which character it is about."""
        return len(self.games) > 1 or len(self.runs) > 1
