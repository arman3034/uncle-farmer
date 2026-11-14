"""Runs a script on its own thread, with its own connection to the game.

The agent releases every key a connection held when that connection closes, so even a crash here
can't leave the character walking.

Several runs can go at once, one per game client (each has its own pid, connection and Bot). They
share the day's log file; applog serialises the writes.
"""

from __future__ import annotations

import datetime as dt
import threading
import time
from collections.abc import Callable
from typing import Any

from .. import applog, daily, gameinstall, phrases, scan, settings, stats, trust
from ..clock import CLOCK, Clock, clock_for
from ..errors import carry_on
from ..i18n import _
from ..link import AgentError, AgentLink, server_name
from . import chores, keyslots, triggers, xpcard
from .bot import Bot, Respawned, Stopped
from .botparts.base import GameBroken
from .botparts.parts import Sighting, Where
from .script import Runner, ScriptError

AGENT_VERSION = 5   # the agent's StateServer.VERSION this app needs (4: dialog, target; 5: typing quantities)
AGENT_SPEECH = 14   # from here the agent can silence the game and reads the own-HP key's answer
AGENT_POINTS = 24   # from here the agent reads the accumulation-points key's answer (rage, marks, combos; 22-23 dropped its request)
AGENT_TEAM = 27     # from here the agent sets quick phrases and reads teammates' positions ("/6")
AGENT_GUARD = 26    # from here the agent can ignore the player's own Shift/Ctrl/Alt while a run drives the game
AGENT_STATE = 37    # from here `mem state` gives the lean map+self+entities snapshot, without bag/slots/modes/ui
AGENT_KEYS = 38     # from here `keysup` releases only the keys this connection holds, not the whole game's
AGENT_ASK = 39      # from here `ask vitals` / `ask petvitals` get HP and MP from the server without the R key
AGENT_ACT = 40      # from here `use <uid>` uses a bag item and `select <id>` picks the target, no arrow or target keys
AGENT_SHEET = 43    # from here `ask sheet` reads the character sheet without the key or its window
AGENT_SLOTS = 46    # from here `slot <n>` presses an attack key through the game's own key method, no keyboard
                    # (45 had it too, but never let the key go: the game then refused every walk)
AGENT_SERVER = 58   # from here `server` identifies the live S1/S2 route without a game packet
AGENT_LOGIN = 67    # from here automatic login includes the companion game connection

def _write_log(line: str) -> None:
    """Every run line to today's log; a broken log must never stop a run (applog says so once)."""
    applog.write(line)


def _write_crash(title: str, character: str | None) -> None:
    """The whole traceback of an unexpected error to logs/errors.log: one line in the window says
    what happened, this says where, so a crash on someone else's PC can be fixed from their logs."""
    applog.crash(title, character or "")


class Run(threading.Thread):
    # set by the window once the run starts (main.py): where it is, what it is, who it follows
    locate: Callable[[str], Where | None] | None
    last_seen: Callable[[str], Sighting | None] | None
    tell: Callable[[str], None] | None
    kind: str
    follows: str | None

    def __init__(self, text: str, title: str, pid: int, on_log: Callable[[str, bool, "Run"], None],
                 on_done: Callable[[str, "Run"], None], walk: bool = False, clock: Clock = CLOCK) -> None:
        """on_log(line, speak, run) and on_done(reason, run) are called from this thread.
        walk: the walking assistant - it isn't farming, so the farming day's end doesn't block it,
        it earns no results, and it ends where it arrived, still riding (no end-of-run trip)."""
        super().__init__(daemon=True, name="unclefarmer-run-%d" % pid)
        self.text, self.title, self.pid = text, title, pid
        self.on_log, self.on_done = on_log, on_done
        self.stop_event = threading.Event()
        self.character: str | None = None   # known once connected; names the run in the log
        self.profile: str | None = None     # the character's own settings key, not merely its display name
        self.tally: stats.Tally | None = None   # what this run earns, readable while it runs
        self.bot: Bot | None = None         # the Bot once running (private message commands reach it here)
        self.link: AgentLink | None = None  # this run's connection to the game, while it runs
        self.muted = False        # this run turned the game's own speech off (the end turns it on again)
        self.speech_choice: str | None = None  # "on"/"off" when the player muted or unmuted this game by hand
        self.ended_by_itself = False  # the run ended on its own (plan done, a stop rule, the daily stop...),
                                      # not by the player's Stop or a lost game: the after-stop action applies
        self.after_stop = "nothing"   # what the app setting said to do then: nothing | close_game | shutdown
        self.before_farming_done = False  # the Character settings' before-farming triggers ran (once a run)
        self.after_farming_done = False   # the Character settings' after-farming triggers ran (once a run)
        self.schedule: tuple[str, str] | None = None   # (schedule id, occurrence) when a schedule started it
        self.clock = clock
        self.started = self.clock.time()
        self.walk = walk

    def farmed(self) -> bool:
        """The after-stop action (close the game, shut the PC down) is for the end of farming: a
        plan or script that farmed. A tool (Gem Maker, Enhancer), the walking assistant, `come` or
        `follow`, or a script that never farmed, ends and leaves the game and the PC alone."""
        return getattr(self, "kind", "") != "errand" and bool(getattr(self.bot, "farmed", False))

    def stop(self) -> None:
        self.stop_event.set()

    def guard(self, bot: Bot, finish: bool = True) -> None:
        """The run stopped on its own (stuck, an error, a stop rule): never leave the character
        standing there. Fight back and drink until nothing attacks, then end somewhere safe as a
        finished run does (finish=False: stay where we are, e.g. beside the player who called us).
        Pressing Stop (or losing the game) ends this at once."""
        for _round in range(2):
            try:
                bot.defend()
                if finish:
                    bot.finish()
                return
            except Respawned:
                continue            # died while guarding and came back: guard again from there
            except Exception as e:    # stuck again, the game gone, or the same bug once more
                carry_on(e, "finishing safely")
                if self.stop_event.is_set():
                    return
                self.log(_("couldn't finish safely: {err}", err=e))
                try:
                    bot.defend()    # finishing failed (stuck again?): at least stay on guard
                except Exception as e2:
                    carry_on(e2, "staying on guard")
                    self.log(_("couldn't stay on guard either: {err}", err=e2))
                return

    def log(self, message: str, speak: bool=False) -> None:
        line = "%s  %s" % (time.strftime("%H:%M:%S"), message)
        _write_log("%s  %s: %s" % (line[:8], self.character, message) if self.character else line)
        self.on_log(line, speak, self)

    def run(self) -> None:
        """Connect, set up, run the plan or script, and whatever ends it, end it well: one step per
        method below. self.link and self.muted hold what the end has to undo even when the start
        failed half way (self.bot is None until the Bot exists)."""
        reason = _("finished")
        app = settings.load_app()
        try:
            bot = self._start(app)
            reason = self._play(bot) or reason
        except GameBroken as e:
            # The game is frozen: guarding or walking on would only look stuck, and closing the game
            # or the PC as if farming had ended hides what happened. The player restarts the game.
            reason = str(e)
        except Stopped as e:
            reason = self._stopped(e)
        except ScriptError as e:
            reason = str(e)
        except AgentError as e:
            reason = _("lost the connection to the game") if str(e) != "no_game" else _("the game isn't running with the agent")
        except OSError as e:
            reason = _("lost the connection to the game: {err}", err=e)
        except Exception as e:   # never let the thread die silently
            reason = self._crashed(e)
        finally:
            self._after_farming()
            self._end(app, reason)

    # ---------------------------------------------------------------- starting
    def _start(self, app: dict[str, Any]) -> Bot:
        """The game connected and checked, the character scanned, the keys armed: the Bot, set up."""
        day_end, blocked = daily.plan(app) if not self.walk else (None, None)
        character: str
        if blocked:
            raise Stopped(_("the day's farming is over - the drop time resets at {reset}; start again "
                            "after that", reset=blocked))
        link = self.link = AgentLink(pid=self.pid)
        version = link.send("version")
        agent = int(version.split()[1]) if version.startswith("mwagent ") else 0
        if agent < AGENT_VERSION:
            raise Stopped(_("the game is running an older Uncle Farmer agent - restart Mist World so it loads "
                            "the new one"))
        snap = link.json("mem state" if agent >= AGENT_STATE else "mem")
        if not snap.get("ok") and self.profile:
            self._login_saved_character(link, agent)
            snap = link.json("mem state" if agent >= AGENT_STATE else "mem")
        if not snap.get("ok"):
            raise Stopped(snap.get("error") or _("log in to a character first"))
        character = self.character = snap["self"]["name"]
        server = server_name(link) if agent >= AGENT_SERVER else ""
        observed = settings.character_profile(character, snap["self"].get("id"), server)
        # The Games list may already know this client's server.  Keep that confirmed identity if
        # one server lookup briefly fails while starting the run.
        if not (self.profile and settings.same_character(self.profile, observed)
                and settings.profile_server(self.profile)):
            self.profile = observed
        applog.thread("run %d %s" % (self.pid, character))
        profile, found = self._profile(link, self.profile)
        guard = self._arm(link, agent, profile, app)
        self.log(_("starting {what} as {name}", what=self.title, name=character), speak=True)
        bot = self._make_bot(link, profile, agent, guard, day_end, app)
        self._set_up(bot, snap, profile, found, agent, app)
        return bot

    def _login_saved_character(self, link: AgentLink, agent: int) -> None:
        """Use this plan's saved account, then wait for the requested character to be selected."""
        if agent < AGENT_LOGIN:
            raise Stopped(_("the game is running an older Uncle Farmer agent - restart Mist World so it loads "
                            "the new one"))
        character = self.profile or ""
        email = settings.load_profile(character).get("login_email")
        entity_id = settings.profile_id(character)
        if not isinstance(email, str) or not email or not entity_id:
            raise Stopped(_("the plan's character has no saved account. Log in to it once first."))
        if link.send("arm") != "armed":
            raise Stopped(_("the game refused the login request"))
        reply = link.json("autologin %s %s" % (email, entity_id))
        if not reply.get("ok"):
            raise Stopped(str(reply.get("error") or _("automatic login could not start")))
        self.log(_("starting automatic login"), speak=True)
        while not self.stop_event.wait(0.25):
            state = link.json("autologinstatus")
            if state.get("running"):
                continue
            if state.get("status") == "ready":
                self.log(_("automatic login finished"))
                return
            raise Stopped(str(state.get("status") or _("automatic login stopped")))
        raise Stopped(_("stopped by you"))

    def _profile(self, link: AgentLink, character: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """Every run starts with a fresh scan: skills, keys, potions, beasts, pets -> the profile (a
        character without a profile gets one here). (profile, what the scan found)."""
        try:
            return scan.scan_and_save(link, character, self.game_folder())
        except Exception as e:      # a failed scan must never stop a run; the saved profile still works
            carry_on(e, "scanning the character")
            self.log(_("couldn't scan {name}: {err}", name=settings.profile_display(character), err=e))
            if not settings.has_profile(character):
                self.log(_("{name} has no profile yet - using the default keys. Open Character, Settings to check them.",
                           name=settings.profile_display(character)), speak=True)
            return settings.load_profile(character), {}

    def _arm(self, link: AgentLink, agent: int, profile: dict[str, Any], app: dict[str, Any]) -> str | None:
        """Keys armed, the player's modifiers kept out, the game's own speech off as set. Returns
        the answer to `guardmods on` (None for an agent that can't)."""
        link.send("arm")
        keys = link.send("keys")
        if not keys.startswith("ready"):
            raise Stopped(_("the game's keys can't be used: {why}", why=keys))
        guard: str | None = None
        if agent >= AGENT_GUARD:
            # The player holding Ctrl in another window (NVDA) made the bot's potion key a
            # Ctrl+key hotkey binding: the beast went onto the blue potions' key. The agent
            # now ignores the player's Shift/Ctrl/Alt in this game until this run's link closes.
            guard = link.send("guardmods on")
            if guard != "on":
                self.log(_("couldn't stop your Ctrl/Shift/Alt reaching this game: {why}", why=guard))
        if agent < AGENT_POINTS:
            profile["points_key"] = ""     # an older agent can't read the T key's answer
        if agent < AGENT_SPEECH:
            profile["vitals_key"] = ""     # an older agent can't read the own-HP key's answer
        elif app.get("game_speech", "running") in ("running", "always") and link.send("speech") == "on":
            self.muted = link.send("speech off") == "off"
            if self.muted:
                self.log(_("the game's own speech is off while the bot runs"))
        return guard

    def _make_bot(self, link: AgentLink, profile: dict[str, Any], agent: int, guard: str | None,
                  day_end: dt.datetime | None, app: dict[str, Any]) -> Bot:
        bot = Bot(link, profile, self.log, self.stop_event, clock=self.clock)
        bot.agent_version = agent
        bot.agent_state = agent >= AGENT_STATE
        bot.agent_keys = agent >= AGENT_KEYS
        bot.agent_ask = agent >= AGENT_ASK
        bot.agent_act = agent >= AGENT_ACT
        bot.agent_sheet = agent >= AGENT_SHEET
        bot.agent_slots = agent >= AGENT_SLOTS and bot.p.get("skills_by_slot", True)
        bot.guarding = guard == "on"     # let go while paused: the player may play by hand then
        if day_end:
            bot.daily_stop_at = day_end.timestamp()
            bot.daily_reset = daily.reset_clock()
            self.log(_("farming stops at {time} at the latest (the drop time resets at {reset})",
                       time=day_end.strftime("%H:%M"), reset=bot.daily_reset))
        bot.character = self.character   # names the game in logs/dialogs.log when several run
        bot.profile_key = self.profile   # the daily chores are kept per character, not per name
        name = self.profile or self.character or ""

        def save_profile(data: dict[str, Any]) -> None:
            settings.save_profile(name, data)

        bot.save_profile = save_profile
        bot.trusted = trust.from_settings(app)
        bot.locate = getattr(self, "locate", None)   # where another of our characters is (follow, come)
        bot.last_seen = getattr(self, "last_seen", None)   # where our games last saw a trusted player
        bot.tell = getattr(self, "tell", None)       # answers the player who asked for this run
        self.bot = bot
        return bot

    def _set_up(self, bot: Bot, snap: dict[str, Any], profile: dict[str, Any], found: dict[str, Any], agent: int,
                app: dict[str, Any]) -> None:
        """The results, where the run started, max MP, the quick phrases and the keys it needs."""
        if not self.walk:
            if getattr(bot, "agent_sheet", False):
                # the results count contribution and experience from the first sheet they see: a
                # fresh one now, or the first reading comes after the first kills and leaves them out
                bot.ask_sheet(force=True)
            bot.tally = self.tally = stats.Tally(self.character or "", self.title, clock=clock_for(bot),
                                                 tool=self._tool())
            if getattr(bot, "daily_stop_at", 0.0):
                bot.tally.deadline(bot.daily_stop_at)     # Time remaining counts down to it at the latest
            bot.tally.update(bot, force=True)
        here: dict[str, Any] = snap.get("self") or {}
        where: dict[str, Any] = snap.get("map", {})
        if where.get("id"):
            bot.start_place = (snap["map"]["id"], int(here.get("x", 0)), int(here.get("y", 0)))
        sheet: dict[str, Any] = here.get("sheet") or {}
        if profile.get("mp_use", True) and not sheet.get("maxmp"):
            # Max MP is only on the character sheet, and only farming reads it on its own:
            # without it a walk, `come` or `follow` never drank a blue potion.
            bot.refresh_sheet(force=True)
        # what each quick phrase does, and the useful codes ("/6" finds teammates) on EMPTY slots
        phrases.arrange(bot, self.game_folder(), here.get("id"), found.get("class"),
                        agent >= AGENT_TEAM)
        if not self.walk:
            keyslots.arrange(bot)        # skills and items the bot needs, onto EMPTY keys only

    def game_folder(self) -> str:
        """This game's own folder (the copy it runs from), else the settings' one."""
        return gameinstall.folder_of(self.pid, settings.load_app().get("game_folder", ""))

    def _tool(self) -> str | None:
        """The job (stats.TOOLS) this run is when it is one from the Tools menu, else None: its
        results are kept apart from farming."""
        if getattr(self, "kind", "") != "errand":
            return None
        words = self.text.split()
        return words[0] if words and words[0] in stats.TOOLS else None

    # ---------------------------------------------------------------- running and stopping
    def _play(self, bot: Bot) -> str | None:
        """The plan or script itself, then the end of a finished run. A reason when not "finished"."""
        script = Runner(bot, self.text)          # read first: a script that doesn't parse does nothing
        if getattr(self, "kind", "") != "errand" and not self.walk:
            if triggers.farms(script.main, script.subs):
                self._before_farming()
            cfg = chores.config(bot.p)
            if cfg.get("before_farming") and chores.due(self.profile or self.character, cfg):
                bot.log(_("the day's chores first"))
                with stats.doing(bot, "chores"):
                    chores.run(bot, cfg)
        script.run()
        if self.walk:
            return _("arrived")          # stay there, on the beast
        for _try in range(3):
            try:
                bot.finish()      # a finished run ends off the beast, on a map where no monsters spawn
                break
            except Respawned:     # died or pulled back on the way: go on from there
                continue
        self.ended_by_itself = True
        return None

    def _stopped(self, e: Stopped) -> str:
        """The run stopped itself (stuck, a stop rule, the drop time...): a frozen game says so;
        otherwise guard, and end somewhere safe unless asked to stay."""
        reason = str(e)
        bot = self.bot
        if bot is not None and not self.stop_event.is_set() and not self.walk:
            try:
                bot.check_game(force=True)   # a frozen game looks like a stuck walk, or any other failure
                broken = False
            except GameBroken as why:
                reason, broken = str(why), True
            except Exception:      # the game gone: guard finds that out itself
                broken = False
            if not broken:
                self.guard(bot, finish=not getattr(e, "stay", False))
                # called away by a player (come, follow, home): not the end of farming, so no
                # closing the game or the PC
                self.ended_by_itself = (not self.stop_event.is_set() and not getattr(e, "stay", False)
                                        and not getattr(e, "asked", False))
        return reason

    def _before_farming(self) -> None:
        """The Character settings' before-farming triggers (engine/triggers.py), each one ticked,
        one after the other, before the plan or script's first line - once a run. A job that
        fails is said and farming still starts; Stop, a frozen or lost game end the run here."""
        bot = self.bot
        if self.before_farming_done or bot is None:
            return
        self.before_farming_done = True
        triggers.run_stage(bot, "before", self.log, self.stop_event.is_set)

    def _after_farming(self) -> None:
        """The Character settings' after-farming triggers (engine/triggers.py: Sell shards now,
        Clean the bag now, Update shard prices, Gathering, Store items now), each one ticked, one
        after the other, the same as from the Tools menu. Only after a farming run that ended by
        itself - the plan done, a stop rule, the daily stop - as the after-stop action is: never
        after Stop, a lost or frozen game, `come`/`follow`, a tool or the walking assistant. Before
        the results close (each job's earnings are its own, apart from farming) and before the game
        is closed or the PC shut down. Once a run. A job that fails is logged and the next one still
        runs; Stop ends them all."""
        bot = self.bot
        if self.after_farming_done or bot is None or self.walk or not self.ended_by_itself or not self.farmed():
            return
        self.after_farming_done = True
        triggers.run_stage(bot, "after", self.log, self.stop_event.is_set)

    def _crashed(self, e: Exception) -> str:
        carry_on(e, "the run")
        reason = _("unexpected error: {err}", err=repr(e))
        _write_crash(self.title, self.character)
        if self.bot is not None and not self.stop_event.is_set() and not self.walk:
            self.log(reason, speak=True)
            self.guard(self.bot)      # a bug is no reason to stand still while monsters hit us
        return reason

    # ---------------------------------------------------------------- the end
    def _end(self, app: dict[str, Any], reason: str) -> None:
        """However it ended: the results finished, the game let go, said, saved and reported."""
        bot = self.bot
        if self.tally:
            self._last_readings(bot)
            try:
                self.tally.finish(bot)
            except Exception as e:
                carry_on(e, "finishing the results on the way out")
                try:
                    self.tally.finish()
                except Exception as e:
                    carry_on(e, "finishing the results without the bot")
                    self.log(_("couldn't finish the results: {err}", err=e))
        if self.link:
            self._pause_card(bot)
            self._let_go(app, bot, self.link)
        self.log(_("stopped: {why}", why=reason), speak=True)
        tell = getattr(self, "tell", None)
        if tell and not self.stop_event.is_set() and reason != _("arrived"):
            try:
                tell(_("Stopped: {why}", why=reason))      # e.g. lost sight of them
            except Exception as e:
                carry_on(e, "telling the player the run stopped")
        if self.tally:
            self.tally.save()
            r, *jobs = self.tally.results()
            for line in stats.report(r, _("Results of {what}", what=self.title)).splitlines():
                self.log(line)
            for job in jobs:              # chores or the Gem Maker on the way: apart from farming
                for line in stats.report(job, _("Results of {what}", what=job["run"])).splitlines():
                    self.log(line)
            if app.get("results_speak", "end") == "end":
                self.log(stats.short(r, self.tally.drop_left), speak=True)
        self.on_done(reason, self)

    def _pause_card(self, bot: Bot | None) -> None:
        """A farming run over: its running experience card paused (xp_card_pause), so the minutes
        aren't spent standing in town. Not after Stop: the player is there, and every wait would
        end at once. Best effort - the game may already be gone."""
        if bot is None or self.walk or self.stop_event.is_set() or not getattr(bot, "farmed", False):
            return
        try:
            xpcard.away(bot, _("farming is over"))
        except Exception as e:
            carry_on(e, "pausing the experience card at the end")

    def _last_readings(self, bot: Bot | None) -> None:
        """Before the results close: the kills the game reported since the bot last looked, and a
        fresh character sheet. The sheet is read without waiting while farming (agent 43), so the
        last reading can be a few seconds old; the long-run simulator caught each run's results
        coming out a kill and its contribution short. Only the keyless sheet: the key would open
        a window at the end. Best effort - the game may already be gone."""
        if bot is None or not self.link:
            return
        try:
            if hasattr(bot, "count_kills"):
                bot.count_kills()
            if getattr(bot, "agent_sheet", False) and hasattr(bot, "ask_sheet"):
                bot.ask_sheet(force=True)
        except Exception as e:      # a lost game, a stop: the results keep what they had
            carry_on(e, "the last readings for the results")

    def _let_go(self, app: dict[str, Any], bot: Bot | None, link: AgentLink) -> None:
        """The keys let go, the game's speech back, and the after-stop action, then the link closed."""
        try:
            if bot is not None and hasattr(bot, "let_go"):
                bot.let_go()      # only this run's keys; a `keysup` could drop another controller's
            else:
                link.send("keysup")
            if self.muted and app.get("game_speech") != "always" and self.speech_choice != "off":
                link.send("speech on")
            self.after_stop = app.get("after_stop", "nothing")
            if self.ended_by_itself and self.farmed() and self.after_stop in ("close_game", "shutdown"):
                # the game closes as its own close button does; a shutdown waits for every bot
                self.log(_("farming is over - closing the game"), speak=True)
                link.send("arm")
                link.send("closegame")
        except (AgentError, OSError) as e:
            self.log(_("couldn't finish at the game's end: {err}", err=e))
        link.close()
