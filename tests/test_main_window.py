# pyright: reportPrivateUsage=false
# White-box tests: they check this module's internal helpers (leading-underscore names) directly.
"""The main window's own logic, part by part (gui/mainparts), without opening a window.

Win is a stand-in window: the widgets are small fakes, and every method it doesn't define itself is
the real one from MainFrame, bound to it - so the parts call each other exactly as in the window.
"""

from __future__ import annotations

import threading
import types
from types import SimpleNamespace
from collections.abc import Callable
from typing import Any, ClassVar, cast

import pytest

wx = pytest.importorskip("wx")

from unclefarmer import chat, messages, settings, speech, stats, tones  # noqa: E402
from unclefarmer.gui import main  # noqa: E402
from unclefarmer.gui.mainparts import games as games_part, results as results_part, runs as runs_part, talk as talk_part  # noqa: E402
from unclefarmer.gui.mainparts.base import LOG_LIMIT, SNAP_FRESH  # noqa: E402

from conftest import returning, stand_in, Clock  # noqa: E402


class Widget:
    """The few widget calls the parts make: a value, a label, a selection, enabled or not."""

    def __init__(self, selection: int=0) -> None:
        self.value, self.label, self.selection, self.enabled = "", "", selection, True
        self.items: dict[tuple[int, int], str] = {}

    def ChangeValue(self, v: str) -> None:
        self.value = v

    def AppendText(self, t: str) -> None:
        self.value += t

    def GetValue(self) -> str:
        return self.value

    def SetInsertionPointEnd(self) -> None:
        pass

    def GetSelection(self) -> int:
        return self.selection

    def SetSelection(self, i: int) -> None:
        self.selection = i

    def GetLabel(self) -> str:
        return self.label

    def SetLabel(self, t: str) -> None:
        self.label = t

    def Enable(self, on: bool=True) -> None:
        self.enabled = on

    def GetNextItem(self, item: int, geometry: int=0, state: int=0) -> int:
        return self.selection if item < 0 else -1      # one selected row, as the Games list has

    def GetItemText(self, i: int, col: int) -> str:
        return self.items.get((i, col), "")

    def SetItem(self, i: int, col: int, text: str) -> None:
        self.items[(i, col)] = text

    def DeleteAllItems(self) -> None:
        self.items.clear()

    def InsertItem(self, i: int, text: str) -> None:
        self.items[(i, 0)] = text

    def SetItemState(self, i: int, _state: int, _mask: int) -> None:
        self.selection = i

    def Focus(self, _i: int) -> None:
        pass

    def EnsureVisible(self, _i: int) -> None:
        pass


class Win:
    """A stand-in main window. Whatever it doesn't define is MainFrame's own method, bound here."""

    def __init__(self, games: list[tuple[int, str, str]] | tuple[()]=(), runs: dict[int, FakeRun] | None=None, s: dict[str, Any] | dict[str, int] | dict[str, str] | None=None) -> None:
        self.clock = Clock()
        self.s = dict(s or {})
        self.games = list(games)
        self.unavailable_agents: dict[int, tuple[int, str]] = {}
        self.runs = dict(runs or {})
        self.messengers: dict[int, Any] = {}       # a game's messenger, or the test's stand-in for one
        self.chats: dict[int, Any] = {}
        self.chat_windows: dict[int, Any] = {}
        self.items: list[Any] = []
        self.log_lines: list[tuple[str, bool]] = []
        self.last_line: dict[int, str] = {}
        self.silenced: set[int] = set()
        self.voice_fixed: dict[int, bool] = {}
        self.destroyed = False
        self.snap: tuple[int, dict[str, Any], float] | None = None
        self.game_list, self.log_filter, self.log_box = Widget(0), Widget(0), Widget()
        self.fields = {"activity": Widget()}
        self.start_btn, self.stop_btn, self.pause_btn, self.what = Widget(), Widget(), Widget(), Widget()
        self.plan_list, self.nb = Widget(), Widget()
        self.said: list[str] = []
        self.started: list[tuple[int | None, Any, bool]] = []     # (pid, what to run, asked remotely)
        self.stopped: list[int | None] = []
        self.shutdowns = 0

    def __getattr__(self, name: str) -> Any:
        attr = getattr(main.MainFrame, name)
        return attr.__get__(self) if callable(attr) and hasattr(attr, "__get__") else attr

    # what would touch the screen or the computer
    def say(self, text: str, run: FakeRun | None=None) -> None:
        self.said.append(text)

    def start(self, pid: int | None=None, item: str | None=None, remote: bool=False) -> str:
        self.started.append((pid, item, remote))
        return "started"

    def stop(self, pid: int | None=None) -> None:
        self.stopped.append(pid)

    def poll(self) -> None:
        pass

    def shut_down(self) -> None:
        self.shutdowns += 1


def test_restock_now_tool_dispatches_the_shared_script_job() -> None:
    from unclefarmer.gui.mainparts import editing

    calls: list[tuple[str, str]] = []
    def run_errand(text: str, title: str) -> None:
        calls.append((text, title))

    frame: Any = SimpleNamespace(run_errand=run_errand)
    editing.EditingMixin.restock_now(frame)
    assert calls == [("restock\n", "Restocking supplies")]


class FakeRun:
    def __init__(self, pid: int, title: str="wolves", character: str="Ali", bot: Any = None, tally: Any = None) -> None:
        self.pid, self.title, self.character, self.bot, self.tally = pid, title, character, bot, tally
        self.kind, self.started, self.stops = "plan", 0.0, 0
        self.ended_by_itself, self.after_stop, self._farmed, self.alive = False, "", False, True

    def stop(self) -> None:
        self.stops += 1

    def is_alive(self):
        return self.alive

    def farmed(self) -> bool:
        return self._farmed


def bot(kills: int=0, deaths: int=0, paused: bool=False) -> types.SimpleNamespace:
    b = SimpleNamespace(kills=kills, deaths=deaths, paused=threading.Event())
    if paused:
        b.paused.set()
    return b


def test_a_live_server_label_promotes_the_id_only_game_row_and_never_downgrades() -> None:
    fallback = settings.character_profile("Killua", 2905)
    on_s1 = settings.character_profile("Killua", 2905, "S1")
    w = Win(games=[(1, fallback, "central plains")], runs={1: FakeRun(1)})
    snap = {"self": {"id": 2905, "name": "Killua", "hp": 1, "maxhp": 1},
            "map": {"name": "central plains"}, "_server": "S1"}
    w.render(1, snap, {})
    assert w.games[0][1] == on_s1

    snap["_server"] = ""
    w.render(1, snap, {})
    assert w.games[0][1] == on_s1


@pytest.fixture
def spoken(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    out: list[str] = []
    monkeypatch.setattr(speech, "speak", stand_in(speech.speak, lambda text, interrupt=False: out.append(text) or True))
    return out


# ================================================================ games
def test_a_game_row_says_who_where_and_what_runs() -> None:
    w = Win(games=[(1, "Ali", "turkey cave"), (2, "", "")],
            runs={1: FakeRun(1, bot=bot())})
    assert w.game_row(w.games[0]) == ("Ali", "turkey cave", "Running wolves")
    assert w.game_row(w.games[1]) == ("Not logged in", "", "Stopped")
    w.runs[1].bot.paused.set()
    assert w.game_row(w.games[0])[2] == "Paused wolves"
    w.label_games()
    assert w.game_list.items[(0, 2)] == "Paused wolves"


def test_the_selected_game_is_the_list_s_selection() -> None:
    w = Win(games=[(1, "Ali", "a"), (2, "Sara", "b")])
    w.game_list.selection = 1
    assert (w.selected_pid(), w.selected_character()) == (2, "Sara")
    w.game_list.selection = -1                   # nothing selected
    assert w.selected_pid() is None and w.selected_character() is None


def test_plan_commands_follow_the_visible_plan_control() -> None:
    w = Win()
    w.items = [("plan", "wolves"), ("script", "daily")]
    w.what, w.plan_list, w.nb = Widget(0), Widget(1), Widget(1)
    assert w.active_item() == ("script", "daily")
    w.nb.selection = 0
    assert w.active_item() == ("plan", "wolves")


def test_menu_actions_follow_the_selected_game_and_plan_state() -> None:
    none = main.action_menu_states(available=False, running=False, any_running=True, has_items=True,
                                   has_messengers=False, selected=None)
    assert not none["run_start"] and none["run_stop_all"] and none["run_results"]
    assert none["messages_private"] and none["character_import"] and not none["tools_gather"]

    stopped = main.action_menu_states(available=True, running=False, any_running=False, has_items=True,
                                      has_messengers=True, selected=("plan", "wolves"))
    assert stopped["run_start"] and stopped["run_walk"] and stopped["character_scan"]
    assert stopped["tools_gem"] and stopped["plans_duplicate"] and stopped["plans_export"]

    running = main.action_menu_states(available=True, running=True, any_running=True, has_items=True,
                                      has_messengers=True, selected=("script", "daily"))
    assert running["run_stop"] and running["run_pause"] and running["run_stop_all"]
    assert not running["run_start"] and not running["run_walk"] and not running["character_scan"]
    assert not running["tools_dungeon"] and not running["plans_duplicate"] and not running["plans_export"]


def test_a_reading_is_reused_only_for_its_game_and_while_fresh() -> None:
    w = Win()
    w.snap = (1, {"ok": True}, w.clock.time())
    assert w.cached(1) == {"ok": True}
    assert w.cached(2) is None
    w.clock.advance(SNAP_FRESH + 1)
    assert w.cached(1) is None


def test_the_run_text_says_how_long_and_how_it_went() -> None:
    w = Win()
    assert w.run_text(None) == "Not running"
    run = FakeRun(1, bot=bot(kills=12, deaths=1))
    w.clock.now = run.started + 3700
    assert w.run_text(run) == "1 h 1 min, 12 kills, 1 deaths"


# ================================================================ runs
def test_the_pause_key_acts_on_the_game_in_front_if_it_is_ours(monkeypatch: pytest.MonkeyPatch) -> None:
    w = Win(games=[(1, "Ali", ""), (2, "Sara", "")], runs={2: FakeRun(2)})
    monkeypatch.setattr(runs_part, "foreground_pid", stand_in(runs_part.foreground_pid, lambda: 2))
    w.toggle()
    assert w.stopped == [2] and w.started == []          # Sara's runs: Pause stops it
    monkeypatch.setattr(runs_part, "foreground_pid", stand_in(runs_part.foreground_pid, lambda: 999))     # not one of ours
    w.game_list.selection = 0
    w.toggle()
    assert w.started == [(1, None, False)]               # the selected game starts


def test_pause_and_go_on() -> None:
    run = FakeRun(1, bot=bot())
    w = Win(games=[(1, "Ali", "")], runs={1: run})
    w.toggle_pause(1)
    assert run.bot.paused.is_set() and w.said[-1] == "Paused"
    assert w.pause_btn.label == "Go &on"
    w.toggle_pause(1)
    assert not run.bot.paused.is_set() and w.said[-1] == "Going on"
    w.toggle_pause(5)
    assert w.said[-1] == "The bot isn't running."


def test_stop_every_bot() -> None:
    w = Win()
    w.stop_all()
    assert w.said == ["No bot is running."]
    runs = {1: FakeRun(1), 2: FakeRun(2)}
    w.runs = runs
    w.stop_all()
    assert [r.stops for r in runs.values()] == [1, 1]


def test_log_lines_say_whose_they_are_once_there_are_two_games() -> None:
    w = Win(games=[(1, "Ali", "")])
    assert not w.tagged()
    w.games.append((2, "Sara", ""))
    assert w.tagged()


# ================================================================ log
def test_a_log_line_is_kept_shown_and_spoken_when_it_matters(spoken: list[Any]) -> None:
    run = FakeRun(1, character="Ali")
    w = Win(games=[(1, "Ali", ""), (2, "Sara", "")], runs={1: run})
    w._append("12:00:00  wolf down", False, run)
    w._append("12:00:01  stuck near 4,5", True, run)
    assert w.log_lines == [("12:00:00  Ali: wolf down", False), ("12:00:01  Ali: stuck near 4,5", True)]
    assert w.last_line[1] == "stuck near 4,5"
    assert w.fields["activity"].value == "stuck near 4,5"     # the selected game's activity field
    assert spoken == ["Ali: stuck near 4,5"]


def test_the_log_keeps_its_last_lines_only() -> None:
    w = Win()
    for i in range(LOG_LIMIT + 1):
        w._append("line %d" % i, False)
    assert len(w.log_lines) < LOG_LIMIT and w.log_lines[-1][0] == "line %d" % LOG_LIMIT


def test_a_finished_run_leaves_and_a_farming_end_can_shut_the_computer_down() -> None:
    done = FakeRun(1)
    done.ended_by_itself, done._farmed, done.after_stop = True, True, "shutdown"
    other = FakeRun(2)
    w = Win(games=[(1, "Ali", ""), (2, "Sara", "")], runs={1: done, 2: other})
    w._done(done)
    assert 1 not in w.runs and w.shutdowns == 0
    assert w.said == ["The computer shuts down once the other bots have finished."]
    w._done(other)
    assert w.runs == {} and w.shutdowns == 1


def test_a_run_that_didn_t_farm_never_shuts_the_computer_down() -> None:
    run = FakeRun(1)
    run.ended_by_itself, run.after_stop = True, "shutdown"         # a tool or a walk: no farming
    w = Win(runs={1: run})
    w._done(run)
    assert w.shutdowns == 0


# ================================================================ private messages and chat
def test_our_characters_are_found_through_their_own_game() -> None:
    class Link:
        def json(self, line: str) -> Any:
            return {"ok": True, "map": {"id": 5302}, "self": {"x": 10.0, "y": 20.0}}

    w = Win(games=[(1, "Ali", ""), (2, "Sara", "")])
    w.messengers = {1: SimpleNamespace(link=Link()), 2: SimpleNamespace(link=None)}
    assert w.locate(" ali ") == (5302, 10.0, 20.0)
    assert w.locate("Sara") is None                       # her game has no link yet
    assert w.locate("Nobody") is None


def test_a_character_with_its_own_key_is_still_found_and_started_by_its_name() -> None:
    class Link:
        def json(self, line: str) -> Any:
            return {"ok": True, "map": {"id": 5302}, "self": {"x": 10.0, "y": 20.0}}

    key = settings.character_profile("Ali", 2905, "S1")
    w = Win(games=[(1, key, "")], s={"last_runs": {"Ali": "plan:wolves"}})     # saved before keys
    w.messengers = {1: SimpleNamespace(link=Link())}
    assert w.locate("ali") == (5302, 10.0, 20.0)
    w.items = [("plan", "wolves")]
    assert w.start_bot(1, "") == "started" and w.started[-1][1] == ("plan", "wolves")


def test_the_latest_sighting_of_a_player_counts_while_it_is_recent() -> None:
    w = Win()
    now = w.clock.time()
    w.messengers = {1: SimpleNamespace(sightings={"kim": (1041, 1, 2, now - 100)}),
                    2: SimpleNamespace(sightings={"kim": (5302, 3, 4, now - 10)})}
    assert w.last_seen("Kim") == (5302, 3, 4, 10)
    w.clock.advance(talk_part.TalkMixin.SEEN_FOR)
    assert w.last_seen("Kim") is None


def test_start_from_a_private_message_finds_the_plan() -> None:
    w = Win(games=[(1, "Ali", "")], s={"last_runs": {"Ali": "plan:wolves"}})
    w.items = [("plan", "wolves"), ("plan", "turkey cave"), ("script", "daily")]
    assert w.start_bot(1, "TURKEY") == "started" and w.started[-1] == (1, ("plan", "turkey cave"), True)
    assert w.start_bot(1, "") == "started" and w.started[-1][1] == ("plan", "wolves")    # the last one
    assert w.start_bot(1, "bears") == "No plan called bears."
    w.s = {}
    assert w.start_bot(1, "") == "Which plan? Send: start <plan name>"


def test_a_private_message_plays_its_tone_and_a_channel_line_is_read_when_wanted(monkeypatch: pytest.MonkeyPatch, spoken: list[Any]) -> None:
    played: list[str] = []
    monkeypatch.setattr(tones, "play", stand_in(tones.play, lambda name: played.append(name)))
    monkeypatch.setattr(talk_part, "foreground_pid", stand_in(talk_part.foreground_pid, lambda: None))
    w = Win(games=[(1, "Ali", "")], s={"pm_trusted": ["Boss"], "chat_read": "open", "chat_speak": ["4"]})
    w.chat_line(1, {"channel": chat.PRIVATE, "name": "Boss", "text": "hi"})
    w.chat_line(1, {"channel": chat.PRIVATE, "name": "Kim", "text": "hi"})
    assert played == ["chime", "ding"] and spoken == []

    team = {"channel": "4", "name": "Sara", "text": "need heals", "when": 0}
    w.chat_line(1, team)
    assert spoken == []                                    # read only while the Chat window is open
    shown: list[dict[str, Any]] = []
    w.chat_windows[1] = SimpleNamespace(add=shown.append)
    w.chat_line(1, team)
    w.chat_line(1, dict(team, channel="0"))                # Global isn't one to read
    w.chat_line(1, dict(team, name="ali"))                 # our own line
    assert spoken == ["Team, Sara: need heals"] and len(shown) == 3


def test_nothing_is_read_or_played_while_that_game_is_in_front(monkeypatch: pytest.MonkeyPatch, spoken: list[Any]) -> None:
    played: list[str] = []
    monkeypatch.setattr(tones, "play", stand_in(tones.play, lambda name: played.append(name)))
    monkeypatch.setattr(talk_part, "foreground_pid", stand_in(talk_part.foreground_pid, lambda: 1))
    w = Win(games=[(1, "Ali", "")], s={"chat_read": "always", "chat_speak": ["4"]})
    w.chat_line(1, {"channel": chat.PRIVATE, "name": "Kim", "text": "hi"})
    w.chat_line(1, {"channel": "4", "name": "Sara", "text": "hi", "when": 0})
    assert played == [] and spoken == []


def test_each_game_gets_one_messenger_and_one_chat_feed(monkeypatch: pytest.MonkeyPatch) -> None:
    class Fake:
        made: ClassVar[list[int]] = []

        def __init__(self, pid: int, *a: object, **k: object) -> None:
            self.pid, self.stopped, self.unsupported = pid, False, False
            Fake.made.append(pid)

        def start(self) -> None:
            pass

        def stop(self) -> None:
            self.stopped = True

        def is_alive(self):
            return not self.stopped

    monkeypatch.setattr(messages, "Messenger", Fake)
    monkeypatch.setattr(chat, "Feed", Fake)
    w = Win(games=[(1, "Ali", ""), (2, "Sara", "")])
    w.keep_messengers()
    w.keep_chats()
    assert sorted(w.messengers) == [1, 2] and sorted(w.chats) == [1, 2]
    gone = w.messengers[2]
    w.games = [(1, "Ali", "")]                             # Sara's game closed
    w.keep_messengers()
    w.keep_messengers()
    assert sorted(w.messengers) == [1] and gone.stopped
    assert Fake.made.count(1) == 2                         # one messenger and one feed, never again


# ================================================================ results and the game's voice
def test_shift_pause_speaks_the_running_results_else_the_last_run(monkeypatch: pytest.MonkeyPatch, spoken: list[Any]) -> None:
    monkeypatch.setattr(results_part, "foreground_pid", stand_in(results_part.foreground_pid, lambda: None))
    monkeypatch.setattr(stats, "short", stand_in(stats.short, lambda r, drop=None: "%d kills, drop %s" % (r["kills"], drop)))
    monkeypatch.setattr(stats, "runs", stand_in(stats.runs, lambda character: [{"kills": 7}] if character == "Sara" else []))
    tally = SimpleNamespace(result=lambda: {"kills": 40}, drop_left=3600)
    w = Win(games=[(1, "Ali", ""), (2, "Sara", ""), (3, "New", "")], runs={1: FakeRun(1, tally=tally)})
    w.speak_results()
    w.game_list.selection = 1
    w.snap = (2, {"ok": True, "self": {"sheet": {"drop_seconds": 1200, "age": 0}}}, w.clock.time())   # Sara's game, open
    w.speak_results()
    w.game_list.selection = 2
    w.speak_results()
    assert spoken == ["Ali: 40 kills, drop 3600", "Sara, last run: 7 kills, drop 1200", "No results yet."]


def test_results_are_spoken_every_so_often_while_farming(monkeypatch: pytest.MonkeyPatch, spoken: list[Any]) -> None:
    monkeypatch.setattr(stats, "short", stand_in(stats.short, lambda r, drop=None: "ok"))
    tally = SimpleNamespace(result=returning(dict[str, Any]()), spoken=0.0, drop_left=None)
    w = Win(runs={1: FakeRun(1, tally=tally)}, s={"results_every": 30})
    w.clock.now = 29 * 60
    w.progress()
    assert spoken == []
    w.clock.now = 30 * 60
    w.progress()
    w.progress()
    assert spoken == ["Ali: ok"]
    w.s["results_every"] = 0
    w.clock.now = 120 * 60
    w.progress()
    assert spoken == ["Ali: ok"]


def test_every_game_is_muted_once_when_its_speech_is_always_off(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[Callable[[], object]] = []

    def thread(target: Callable[[], object], daemon: bool | None = None) -> SimpleNamespace:
        return SimpleNamespace(start=lambda: started.append(target))
    monkeypatch.setattr(results_part.threading, "Thread", thread)
    w = Win(games=[(1, "Ali", ""), (2, "Sara", "")], s={"game_speech": "always"})
    w.keep_silent()
    w.keep_silent()
    assert w.silenced == {1, 2} and len(started) == 1     # once per game
    w2 = Win(games=[(1, "Ali", "")], s={"game_speech": "running"})
    w2.keep_silent()
    assert w2.silenced == set()


def test_the_voice_fix_is_sent_only_when_it_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[Callable[[], object]] = []
    sent: list[tuple[int, str]] = []

    def thread(target: Callable[[], object], daemon: bool | None = None, name: str | None = None) -> SimpleNamespace:
        return SimpleNamespace(start=lambda: started.append(target))

    class Link:
        def __init__(self, pid: int, timeout: float) -> None:
            self.pid = pid

        def __enter__(self) -> "Link":
            return self

        def __exit__(self, *exc: object) -> None:
            pass

        def send(self, line: str) -> str:
            sent.append((self.pid, line))
            return line.split()[-1]
    monkeypatch.setattr(results_part.threading, "Thread", thread)
    monkeypatch.setattr(results_part, "AgentLink", Link)
    w = Win(games=[(1, "Ali", ""), (2, "Sara", "")], s={})
    w.keep_voice_fix()
    assert started == [] and sent == []                  # on by default, as every game starts: nothing to say
    w.s["fix_voice"] = False
    w.keep_voice_fix()
    w.keep_voice_fix()
    assert len(started) == 1                             # once per change
    started[0]()
    assert sent == [(1, "voicefix off"), (2, "voicefix off")]
    w.games.append((3, "Zoya", ""))
    w.keep_voice_fix()
    started[1]()
    assert sent[-1] == (3, "voicefix off")               # a game opened later is told too
    w.s["fix_voice"] = True
    w.keep_voice_fix()
    started[2]()
    assert sent[-3:] == [(1, "voicefix on"), (2, "voicefix on"), (3, "voicefix on")]


def test_an_empty_game_folder_setting_is_filled_in_from_the_installed_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    from unclefarmer import gameinstall
    from unclefarmer.gui.mainparts import editing

    saved: list[dict[str, Any]] = []
    monkeypatch.setattr(gameinstall, "status", stand_in(gameinstall.status, lambda folder: "installed" if folder == "D:/Game" else "nogame"))
    monkeypatch.setattr(gameinstall, "find_installed", stand_in(gameinstall.find_installed, lambda remembered="": "D:/Game"))
    def save(parent: object, writer: Callable[..., object], data: dict[str, Any]) -> bool:
        saved.append(dict(data))
        return True
    monkeypatch.setattr(editing, "save_file", save)
    frame: Any = types.SimpleNamespace(s={"game_folder": ""})
    assert editing.EditingMixin.remember_game_folder(frame) == "D:/Game"
    assert frame.s["game_folder"] == "D:/Game" and saved == [{"game_folder": "D:/Game"}]
    assert editing.EditingMixin.remember_game_folder(frame) == "D:/Game" and len(saved) == 1   # once


def test_automatic_login_opens_only_one_client_then_uses_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """A schedule tick cannot make a new window every time the game is still loading."""
    opened: list[None] = []
    frame = cast(Any, types.SimpleNamespace(games=[], runs={}, pending_logins={}))
    frame.refresh_games = lambda: None
    frame.open_client_for_login = lambda: opened.append(None) or None
    monkeypatch.setattr(runs_part.time, "monotonic", lambda: 10.0)

    first = runs_part.RunsMixin.automatic_login_window(frame, "Hero\x1fS1\x1f1")
    second = runs_part.RunsMixin.automatic_login_window(frame, "Hero\x1fS1\x1f1")
    frame.games = [(44, None, None)]
    ready = runs_part.RunsMixin.automatic_login_window(frame, "Hero\x1fS1\x1f1")

    assert first == (None, "opening a game for Hero - S1")
    assert second == first and opened == [None]
    assert ready == (44, "") and frame.pending_logins == {}


def test_a_stale_agent_record_does_not_make_the_game_refresh_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """An old port file with a reused PID must not prevent the main window from appearing."""
    reads: list[None] = []
    def no_games() -> list[tuple[int, str | None, str | None]]:
        reads.append(None)
        return []

    monkeypatch.setattr(games_part, "games", no_games)
    def agent_rows() -> list[tuple[int, int, str]]:
        return [(9000, 42, "old")]

    monkeypatch.setattr(games_part, "agents", agent_rows)
    window = Win()

    window.refresh_games()
    window.poll()

    assert reads == [None]
    assert window.unavailable_agents == {42: (9000, "old")}


def test_a_start_from_inside_a_game_runs_the_last_plans_own_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    """The last-run swap must read that plan's text, never run the selected plan under its name."""
    made: list[tuple[str, str]] = []

    class Run:
        def __init__(self, text: str, title: str, pid: int, *a: object, **k: object) -> None:
            made.append((text, title))
            self.title = title

        def start(self) -> None:
            pass

    def read(item: Any, profile: str | None) -> tuple[str, str | None, None]:
        return "steps of %s" % item[1], profile, None

    monkeypatch.setattr(runs_part, "Run", Run)
    monkeypatch.setattr(runs_part, "run_text_and_profile", read)
    def saved(*args: object) -> bool:
        return True
    monkeypatch.setattr(runs_part, "save_file", saved)
    frame: Any = SimpleNamespace(
        s={"last_runs": {"Ali": "plan:wolves"}}, games=[(1, "Ali", ""), (2, "Sara", "")], runs={}, last_line={},
        items=[("plan", "turkey"), ("plan", "wolves")], clock=Clock(), said=[],
        selected_item=lambda: None, selected_pid=lambda: 2, label_games=lambda: None, update_buttons=lambda: None,
        poll=lambda: None, on_log=None, on_done=None, locate=None, last_seen=None)
    frame.say = frame.said.append
    frame._item_for_game = types.MethodType(runs_part.RunsMixin._item_for_game, frame)

    assert runs_part.RunsMixin.start(frame, 1) == "Starting wolves."    # nothing selected: the last run
    frame.selected_item = lambda: ("plan", "turkey")
    frame.runs = {}
    assert runs_part.RunsMixin.start(frame, 1) == "Starting wolves."    # another one selected
    assert made == [("steps of wolves", "wolves"), ("steps of wolves", "wolves")]


def test_a_game_that_was_slow_once_comes_back_to_the_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """A live game that missed one refresh is pinged again later, not hidden until it restarts."""
    listed: list[list[tuple[int, str | None, str | None]]] = [[], [(42, "Ali", "Town")]]
    pinged: list[int] = []
    monkeypatch.setattr(games_part, "games", lambda: listed.pop(0))
    monkeypatch.setattr(games_part, "agents", lambda: [(9000, 42, "live")])
    def answers(pid: int) -> bool:
        pinged.append(pid)
        return True
    monkeypatch.setattr(games_part, "_answers", answers)
    window: Any = Win()
    window.refresh_games()
    assert window.games == [] and window.unavailable_agents == {42: (9000, "live")}

    window.poll = types.MethodType(games_part.GamesMixin.poll, window)
    window.SetStatusText = lambda text: None  # pyright: ignore[reportUnknownLambdaType]
    window.snap_busy = True                               # no game reading in this test
    window.poll()                                         # too soon: no ping, no rebuild
    assert pinged == []
    window.clock.advance(games_part.UNAVAILABLE_RETRY)
    window.poll()
    assert pinged == [42] and window.games == [(42, "Ali", "Town")] and window.unavailable_agents == {}
