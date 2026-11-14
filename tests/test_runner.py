# pyright: reportPrivateUsage=false
# White-box tests: they check this module's internal helpers (leading-underscore names) directly.
"""The Run lifecycle: gating on the agent version, the daily stop, speech muting, the after-stop
action and the error paths - with a fake link, bot, scanner and script runner (no game at all)."""

from __future__ import annotations



from unclefarmer import paths, settings, stats
from unclefarmer.engine import runner as R
from unclefarmer.engine import script as script_mod
from unclefarmer.engine.bot import Respawned
from unclefarmer.link import AgentError
from pathlib import Path
import datetime as dt
import types

import pytest
from conftest import as_bot, as_kind, returning, stand_in, Clock
from unclefarmer.engine.bot import Bot
from typing import Any, NoReturn
from collections.abc import Callable
from unclefarmer.engine.botparts.parts import Parts
from unclefarmer.stats import Record
from threading import Event
from unclefarmer.engine.runner import Run


# ---------------------------------------------------------------- fakes
class FakeLink:
    def __init__(self, pid: int | None=None) -> None:
        self.pid = pid
        self.sent: list[str] = []
        self.closed = False
        self.reply: dict[str, str] = {}
        self.snap: dict[str, Any] = {}
        self.asked: list[str] = []

    def send(self, line: str) -> str:
        self.sent.append(line)
        return self.reply.get(line, "ok")

    def json(self, line: str) -> Any:
        self.asked = self.asked + [line]
        return self.snap if line in ("mem", "mem state") else {}

    def close(self) -> None:
        self.closed = True


class LoginLink(FakeLink):
    """A saved-login exchange whose status advances without waiting for real time."""

    def __init__(self, states: list[dict[str, Any]]) -> None:
        super().__init__()
        self.states = list(states)

    def json(self, line: str) -> Any:
        self.asked.append(line)
        if line.startswith("autologin "):
            return {"ok": True}
        if line == "autologinstatus":
            return self.states.pop(0)
        return self.snap


class NeverStops:
    """The login poll's stop token for a deterministic unit test."""

    def wait(self, timeout: float) -> bool:
        return False


def saved_login_profile(character: str) -> dict[str, Any]:
    """The only profile field automatic login needs before it reaches the game."""
    return {"login_email": "hero@example.com"}


class FakeBot:
    def __init__(self, link: FakeLink, profile: dict[str, Any], log: Callable[..., Any], stop_event: Event, clock: Clock | None=None) -> None:
        self.a = link
        self.p = profile
        self.log = log
        self.stop_event = stop_event
        self.farmed = False
        self.finish_calls = 0
        self.defend_calls = 0
        self.ran = False
        self.agent_state = False        # the runner sets these from the agent's version and the profile
        self.guarding = False

    def finish(self) -> None:
        self.finish_calls += 1

    def defend(self) -> None:
        self.defend_calls += 1

    def refresh_sheet(self, force: bool=False) -> dict[str, Any] | None:
        pass

    def bag_rows(self) -> list[dict[str, Any]]:
        return []

    def me(self) -> dict[str, Any]:
        return {"sheet": {"level": 1}}

    def map_id(self) -> int:
        return 1


class FakeTally:
    def __init__(self, character: str, title: str, clock: Clock | None=None, tool: None=None) -> None:
        self.character, self.title, self.tool = character, title, tool
        self.updates: list[bool] = []
        self.finished_with = None
        self.saved = False
        self.drop_left: int | None = None

    def update(self, bot: Parts, force: bool=False) -> None:
        self.updates.append(force)

    def finish(self, bot: Parts | None=None) -> None:
        self.finished_with = bot

    def save(self) -> None:
        self.saved = True

    def result(self) -> Record:
        return {"kills": 3}

    def results(self) -> list[Record]:
        return [self.result()]


class FakeRunner:
    # what the real Runner holds after reading the script: its lines and subs (no farm command here)
    main: list[script_mod.Node] = []
    subs: dict[str, list[script_mod.Node]] = {}

    def __init__(self, bot: FakeBot, text: str) -> None:
        self.bot, self.text = bot, text

    def run(self) -> None:
        self.bot.ran = True


class FarmingRunner(FakeRunner):
    main = [script_mod.Node("farm", 1)]

    def run(self) -> None:
        super().run()
        self.bot.farmed = True


class BoomRunner(FakeRunner):
    def __init__(self, bot: FakeBot, text: str) -> None:
        pass

    def run(self) -> None:
        raise script_mod.ScriptError(3, "bad command")


def make(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, text: str = "wait 1", walk: bool = False,
         app: dict[str, Any] | None = None, plan: tuple[dt.datetime | None, str | None] = (None, None), agent: int = 27,
         snap: dict[str, Any] | None = None, keys: str = "ready", reply: dict[str, str] | None = None,
         scan_raises: BaseException | None = None, link_raises: BaseException | None = None,
         runner: type[FakeRunner] | None = None) -> tuple[Run, list[FakeLink], list[tuple[str, bool]], list[str]]:
    monkeypatch.setattr(paths, "LOGS", str(tmp_path))
    application: dict[str, Any] = {"game_folder": "", "after_stop": "nothing"}
    application.update(app or {})
    monkeypatch.setattr(settings, "load_app", stand_in(settings.load_app, lambda: application))
    monkeypatch.setattr(settings, "has_profile", stand_in(settings.has_profile, lambda character: True))
    monkeypatch.setattr(settings, "load_profile", stand_in(settings.load_profile, lambda character: {"vitals_key": "v", "points_key": "p", "mp_use": False}))
    monkeypatch.setattr(R, "Bot", FakeBot)
    monkeypatch.setattr(R, "Runner", runner or FakeRunner)
    monkeypatch.setattr(stats, "Tally", FakeTally)
    monkeypatch.setattr(stats, "report", stand_in(stats.report, lambda r, title: "report"))
    monkeypatch.setattr(stats, "short", stand_in(stats.short, lambda r, drop=None: "short"))

    from unclefarmer import daily as daily_mod
    from unclefarmer import phrases as phrases_mod
    from unclefarmer import scan as scan_mod
    from unclefarmer.engine import keyslots
    monkeypatch.setattr(daily_mod, "plan", stand_in(daily_mod.plan, lambda app: plan))
    monkeypatch.setattr(phrases_mod, "arrange", stand_in(phrases_mod.arrange, returning({})))
    monkeypatch.setattr(keyslots, "arrange", stand_in(keyslots.arrange, returning(None)))
    if scan_raises is not None:
        exc = scan_raises

        def boom(*a: object, **k: object) -> NoReturn:
            raise exc
        monkeypatch.setattr(scan_mod, "scan_and_save", boom)
    else:
        monkeypatch.setattr(scan_mod, "scan_and_save", stand_in(scan_mod.scan_and_save, lambda link, character, game_folder="": ({}, {"class": "warrior"})))

    base = {"version": "mwagent %d" % agent, "keys": keys, "arm": "ok", "speech": "on",
            "speech off": "off", "guardmods on": "on", "closegame": "ok"}
    base.update(reply or {})
    snap_map = {"ok": True, "self": {"name": "Hero", "id": 7, "x": 5, "y": 6}, "map": {"id": 5121}}
    if snap is not None:
        snap_map = snap
    links: list[FakeLink] = []

    def make_link(pid: int | None = None, **kw: object) -> FakeLink:
        if link_raises is not None:
            raise link_raises
        link = FakeLink(pid)
        link.reply, link.snap = base, snap_map
        links.append(link)
        return link

    monkeypatch.setattr(R, "AgentLink", make_link)
    logs: list[tuple[str, bool]] = []
    done: list[str] = []
    run = R.Run(text, "TestRun", 999,
                lambda line, speak, r: logs.append((line, speak)),
                lambda reason, r: done.append(reason), walk=walk)
    return run, links, logs, done


# ---------------------------------------------------------------- the Run object itself
def test_run_init_defaults() -> None:
    run = R.Run("wait 1", "Title", 42, lambda line, speak, run: None, lambda reason, run: None)
    assert run.text == "wait 1" and run.title == "Title" and run.pid == 42
    assert run.stop_event.is_set() is False
    assert run.character is None and run.tally is None and run.bot is None
    assert run.speech_choice is None and run.ended_by_itself is False
    assert run.after_stop == "nothing" and run.walk is False
    assert run.daemon is True and run.name == "unclefarmer-run-42"
    assert isinstance(run.started, float)


def test_start_keeps_the_games_list_server_when_the_agent_lookup_fails(monkeypatch: pytest.MonkeyPatch,
                                                                        tmp_path: Path) -> None:
    monkeypatch.setattr(R, "AGENT_SERVER", 42)      # exercise the server path without newer fake-only features
    run, _, _, done = make(monkeypatch, tmp_path, agent=42)
    run.profile = settings.character_profile("Hero", 7, "S1")
    def no_server(link: object) -> str:
        return ""
    monkeypatch.setattr(R, "server_name", no_server)
    run.run()
    assert done == ["finished"]
    assert run.profile == settings.character_profile("Hero", 7, "S1")


def test_farmed_only_for_a_farming_run() -> None:
    run = R.Run("", "", 1, lambda line, speak, run: None, lambda reason, run: None)
    run.bot = as_kind(Bot, types.SimpleNamespace(farmed=True))
    assert run.farmed() is True
    run.kind = "errand"
    assert run.farmed() is False
    run.kind = ""
    run.bot = None
    assert run.farmed() is False


def test_a_tools_menu_run_keeps_its_results_apart_from_farming() -> None:
    run = R.Run("gem_maker check\n", "Gem Maker check", 1, lambda line, speak, run: None, lambda reason, run: None)
    assert run._tool() is None                  # a plan or script farms
    run.kind = "errand"
    assert run._tool() == "gem_maker"
    run.text = "chores\n"
    assert run._tool() == "chores"
    run.text = "go 1041\n"                      # the walking assistant: no job of the Tools menu
    assert run._tool() is None


def test_stop_sets_the_stop_event() -> None:
    run = R.Run("", "", 1, lambda line, speak, run: None, lambda reason, run: None)
    assert not run.stop_event.is_set()
    run.stop()
    assert run.stop_event.is_set()


def test_saved_login_waits_for_a_confirmed_world(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = settings.character_profile("Hero", 7, "S1")
    run = R.Run("", "", 1, lambda line, speak, run: None, lambda reason, run: None)
    run.profile, run.stop_event = profile, NeverStops()  # type: ignore[assignment]
    monkeypatch.setattr(settings, "load_profile", saved_login_profile)
    link = LoginLink([{"ok": True, "running": True, "status": "loading character"},
                      {"ok": True, "running": False, "status": "ready"}])
    link.reply["arm"] = "armed"

    run._login_saved_character(as_kind(R.AgentLink, link), R.AGENT_LOGIN)

    assert link.sent == ["arm"]
    assert link.asked == ["autologin hero@example.com 7", "autologinstatus", "autologinstatus"]


def test_saved_login_refuses_to_start_without_a_confirmed_world(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = settings.character_profile("Hero", 7, "S1")
    run = R.Run("", "", 1, lambda line, speak, run: None, lambda reason, run: None)
    run.profile, run.stop_event = profile, NeverStops()  # type: ignore[assignment]
    monkeypatch.setattr(settings, "load_profile", saved_login_profile)
    link = LoginLink([{"ok": True, "running": False, "status": "timed out loading character"}])
    link.reply["arm"] = "armed"

    with pytest.raises(R.Stopped, match="timed out loading character"):
        run._login_saved_character(as_kind(R.AgentLink, link), R.AGENT_LOGIN)


# ---------------------------------------------------------------- logging
def test_log_writes_to_the_daily_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run, _, logs, _ = make(monkeypatch, tmp_path)
    run.character = "Hero"
    run.log("hello", speak=True)
    (line, speak) = logs[0]
    assert speak is True and "hello" in line
    files = list(tmp_path.glob("*.log"))
    assert len(files) == 1
    assert "Hero: hello" in files[0].read_text(encoding="utf-8")


def test_write_log_swallows_an_oserror(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(paths, "LOGS", str(tmp_path / "missing"))
    R._write_log("nothing")            # must not raise


def bot_of(run: R.Run) -> FakeBot:
    """The (pretend) Bot a finished run made (only an early refusal leaves it None)."""
    assert run.bot is not None
    return as_kind(FakeBot, run.bot)


def test_write_crash_appends_the_traceback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(paths, "LOGS", str(tmp_path))
    R._write_crash("Title", "Hero")
    text = (tmp_path / "errors.log").read_text(encoding="utf-8")
    assert "Title" in text and "Hero" in text


# ---------------------------------------------------------------- run: happy path
def test_run_completes_and_reports(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run, links, logs, done = make(monkeypatch, tmp_path)
    run.run()
    assert done == ["finished"]
    assert run.ended_by_itself is True
    assert bot_of(run).ran is True and bot_of(run).finish_calls == 1
    assert run.tally is not None and as_kind(FakeTally, run.tally).saved is True
    assert links[0].closed is True
    assert "keysup" in links[0].sent
    assert any("starting TestRun as Hero" in line for line, _ in logs)


def test_run_walk_ends_on_arrival(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run, links, _logs, done = make(monkeypatch, tmp_path, walk=True)
    run.run()
    assert done == ["arrived"]
    assert run.tally is None
    assert bot_of(run).finish_calls == 0
    assert links[0].closed is True


# ---------------------------------------------------------------- run: gating
def test_run_refuses_an_old_agent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run, links, _logs, done = make(monkeypatch, tmp_path, agent=4)
    run.run()
    assert "older" in done[0] and run.ended_by_itself is False
    assert links and links[0].closed is True


def test_run_reads_the_lean_state_when_the_agent_has_it(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run, links, _, _ = make(monkeypatch, tmp_path, agent=37)
    run.run()
    assert links[0].asked[0] == "mem state"
    assert bot_of(run).agent_state is True


def test_run_reads_the_full_snapshot_from_an_older_agent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run, links, _, _ = make(monkeypatch, tmp_path, agent=36)
    run.run()
    assert links[0].asked[0] == "mem"
    assert bot_of(run).agent_state is False


def test_run_asks_you_to_log_in(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run, _, _, done = make(monkeypatch, tmp_path, snap={"ok": False})
    run.run()
    assert "log in" in done[0]


def test_run_blocked_by_the_daily_stop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run, links, _, done = make(monkeypatch, tmp_path, plan=(None, "05:00"))
    run.run()
    assert "farming is over" in done[0]
    assert links == []


def test_run_refuses_when_the_keys_are_unusable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run, _, _, done = make(monkeypatch, tmp_path, keys="not ready")
    run.run()
    assert "keys can't be used" in done[0]


def test_run_survives_a_guard_that_will_not_turn_on(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run, _, logs, done = make(monkeypatch, tmp_path, agent=26, reply={"guardmods on": "nope"})
    run.run()
    assert done == ["finished"]
    assert any("Ctrl/Shift/Alt" in line for line, _ in logs)
    assert bot_of(run).guarding is False


def test_run_blanks_keys_an_old_agent_cannot_read(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run, _, _, done = make(monkeypatch, tmp_path, agent=5)
    run.run()
    assert done == ["finished"]
    assert bot_of(run).p["points_key"] == "" and bot_of(run).p["vitals_key"] == ""


# ---------------------------------------------------------------- run: speech
def test_run_mutes_and_unmutes_the_game_speech(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run, links, logs, _done = make(monkeypatch, tmp_path, app={"game_speech": "running"})
    run.run()
    sent = links[0].sent
    assert "speech off" in sent and "speech on" in sent
    assert any("speech is off" in line for line, _ in logs)


def test_run_leaves_always_muted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run, links, _, _ = make(monkeypatch, tmp_path, app={"game_speech": "always"})
    run.run()
    sent = links[0].sent
    assert "speech off" in sent and "speech on" not in sent


# ---------------------------------------------------------------- run: after-stop
def test_run_closes_the_game_after_farming(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run, links, _, _ = make(monkeypatch, tmp_path, runner=FarmingRunner, app={"after_stop": "close_game"})
    run.run()
    assert run.farmed() is True
    assert "closegame" in links[0].sent
    assert run.after_stop == "close_game"


def test_run_does_not_close_the_game_after_a_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run, links, _, _ = make(monkeypatch, tmp_path, app={"after_stop": "close_game"})
    run.run()
    assert "closegame" not in links[0].sent


# ---------------------------------------------------------------- run: error paths
def test_run_reports_a_script_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run, _, _, done = make(monkeypatch, tmp_path, runner=BoomRunner)
    run.run()
    assert "line 3" in done[0]


def test_run_reports_a_missing_game(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run, links, _, done = make(monkeypatch, tmp_path, link_raises=AgentError("no_game"))
    run.run()
    assert done[0] == "the game isn't running with the agent"
    assert links == []


def test_run_reports_a_lost_connection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run, _, _, done = make(monkeypatch, tmp_path, link_raises=AgentError("closed"))
    run.run()
    assert done[0] == "lost the connection to the game"


def test_run_reports_our_own_value_error_not_a_lost_connection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, allow_ignored_failures: None) -> None:
    # A ValueError is a bug in the bot's own numbers, not a dead agent: reporting it as "lost the
    # connection to the game" hid a whole class of crashes (random_cell's inverted randrange).
    class ValueBoom(FakeRunner):
        def run(self) -> None:
            raise ValueError("empty range for randrange()")

    run, _, _, done = make(monkeypatch, tmp_path, runner=ValueBoom)
    run.run()
    assert done[0].startswith("unexpected error: ValueError")
    assert "empty range for randrange()" in done[0]
    assert (tmp_path / "errors.log").exists()          # the traceback is kept for a bug report


def test_run_logs_a_failed_scan_and_continues(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, allow_ignored_failures: None) -> None:
    run, _, logs, done = make(monkeypatch, tmp_path, scan_raises=RuntimeError("boom"))
    run.run()
    assert done == ["finished"]
    assert any("couldn't scan" in line for line, _ in logs)


# ---------------------------------------------------------------- guard
class GuardBot:
    def __init__(self) -> None:
        self.events: list[str] = []

    def defend(self) -> None:
        self.events.append("defend")

    def finish(self) -> None:
        self.events.append("finish")


def a_run() -> Run:
    return R.Run("", "", 1, lambda line, speak, run: None, lambda reason, run: None)


def test_guard_defends_and_finishes() -> None:
    run, bot = a_run(), GuardBot()
    run.guard(as_bot(bot))
    assert bot.events == ["defend", "finish"]


def test_guard_can_leave_the_character_where_they_are() -> None:
    run, bot = a_run(), GuardBot()
    run.guard(as_bot(bot), finish=False)
    assert bot.events == ["defend"]


def test_guard_retries_after_a_respawn() -> None:
    run, bot = a_run(), GuardBot()
    calls = {"n": 0}

    def defend():
        calls["n"] += 1
        bot.events.append("defend")
        if calls["n"] == 1:
            raise Respawned

    bot.defend = defend
    run.guard(as_bot(bot))
    assert bot.events == ["defend", "defend", "finish"]


def test_guard_keeps_guarding_when_finishing_fails(allow_ignored_failures: None) -> None:
    run, bot = a_run(), GuardBot()

    def finish():
        bot.events.append("finish")
        raise RuntimeError("stuck")

    bot.finish = finish
    run.guard(as_bot(bot))
    assert bot.events == ["defend", "finish", "defend"]


def test_guard_gives_up_at_once_when_stopped(allow_ignored_failures: None) -> None:
    run, bot = a_run(), GuardBot()

    def finish():
        bot.events.append("finish")
        raise RuntimeError("stuck")

    bot.finish = finish
    run.stop()
    run.guard(as_bot(bot))
    assert bot.events == ["defend", "finish"]


def test_guard_swallows_a_second_defend_failure(allow_ignored_failures: None) -> None:
    run, bot = a_run(), GuardBot()
    calls = {"n": 0}

    def defend():
        calls["n"] += 1
        bot.events.append("defend")
        if calls["n"] == 2:
            raise RuntimeError("still stuck")

    def finish():
        bot.events.append("finish")
        raise RuntimeError("stuck")

    bot.defend, bot.finish = defend, finish
    run.guard(as_bot(bot))                     # must not raise
    assert bot.events == ["defend", "finish", "defend"]
