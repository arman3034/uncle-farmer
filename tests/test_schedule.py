"""Scheduled runs: when a plan or script runs (once, every day, chosen days), that each occurrence
runs once, what happens to times missed while the app was closed, a busy or missing game, editing,
turning off, deleting, the file surviving a restart - and the main window's side: starting through
the Start button's own path, refusing a busy game, and writing down how a scheduled run ended.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest

from unclefarmer import schedule
from unclefarmer.schedule import FAILED, STARTED, WAIT, Schedule, Scheduler

T0 = dt.datetime(2026, 11, 2, 5, 0)        # a Monday, 05:00


def at(day: int, hour: int, minute: int = 0) -> dt.datetime:
    """A time in the week of 2 November 2026 (day 2 = Monday)."""
    return dt.datetime(2026, 11, day, hour, minute)


class Starts:
    """start() for the scheduler: records what it was asked to start; answers as told."""

    def __init__(self, answer: tuple[str, str] = (STARTED, "in the game")) -> None:
        self.answer = answer
        self.calls: list[tuple[str, dt.datetime]] = []

    def __call__(self, s: Schedule, due: dt.datetime) -> tuple[str, str]:
        self.calls.append((s["id"], due))
        return self.answer


def fresh(tmp_path: Path) -> Scheduler:
    return Scheduler(str(tmp_path / "schedules.json"))


def daily(time: str = "06:00", who: str = "Hero", item: str = "plan:Wolves") -> Schedule:
    return {"item": item, "character": who, "repeat": schedule.DAILY, "time": time, "enabled": True}


def run_ticks(sch: Scheduler, start: Starts, times: list[dt.datetime]) -> list[str]:
    said: list[str] = []
    for t in times:
        said += [line for _s, line in sch.tick(t, start)]
    return said


def outcomes(s: Schedule) -> list[str]:
    history: list[dict[str, Any]] = s["history"]
    return [h["outcome"] for h in history]


# ================================================================ when it comes round
def test_a_daily_schedule_runs_at_its_time_and_not_before(tmp_path: Path) -> None:
    sch, start = fresh(tmp_path), Starts()
    s = sch.add(daily("06:00"), T0)
    run_ticks(sch, start, [at(2, 5, 59)])
    assert start.calls == []
    said = run_ticks(sch, start, [at(2, 6, 0)])
    assert start.calls == [(s["id"], at(2, 6))]
    assert said == ["Scheduled: starting Wolves for Hero"]
    run_ticks(sch, start, [at(3, 6, 0, )])
    assert [due for _i, due in start.calls] == [at(2, 6), at(3, 6)]     # and the next day again


def test_each_occurrence_starts_once_however_often_it_is_looked_at(tmp_path: Path) -> None:
    sch, start = fresh(tmp_path), Starts()
    sch.add(daily("06:00"), T0)
    run_ticks(sch, start, [at(2, 6, 0), at(2, 6, 0), at(2, 6, 1), at(2, 6, 14), at(2, 23, 0)])
    assert len(start.calls) == 1


def test_a_weekly_schedule_runs_only_on_its_days(tmp_path: Path) -> None:
    sch, start = fresh(tmp_path), Starts()
    sch.add({**daily("22:00"), "repeat": schedule.WEEKLY, "days": [0, 4]}, T0)     # Monday, Friday
    run_ticks(sch, start, [at(d, 22, 0) for d in range(2, 10)])
    assert [due for _i, due in start.calls] == [at(2, 22), at(6, 22), at(9, 22)]


def test_a_once_schedule_runs_at_its_date_and_time_then_turns_itself_off(tmp_path: Path) -> None:
    sch, start = fresh(tmp_path), Starts()
    s = sch.add({**daily("07:30"), "repeat": schedule.ONCE, "date": "2026-11-04"}, T0)
    assert schedule.next_due(s, T0) == at(4, 7, 30)
    run_ticks(sch, start, [at(3, 7, 30), at(4, 7, 29)])
    assert start.calls == []
    run_ticks(sch, start, [at(4, 7, 30), at(5, 7, 30)])
    assert [due for _i, due in start.calls] == [at(4, 7, 30)]
    assert s["enabled"] is False and schedule.next_due(s, at(4, 8)) is None


def test_the_next_time_is_shown_for_each_kind() -> None:
    s: Schedule = {**daily("06:00"), "handled": schedule.stamp(T0)}
    assert schedule.next_due(s, T0) == at(2, 6)
    assert schedule.next_due(s, at(2, 6, 1)) == at(2, 6)            # waiting to start: now
    assert schedule.next_due(dict(s, handled=schedule.stamp(at(2, 6))), at(2, 7)) == at(3, 6)
    assert schedule.next_due(dict(s, enabled=False), T0) is None
    assert schedule.describe_when(s) == "every day at 06:00"
    assert schedule.describe_when({**s, "repeat": schedule.WEEKLY, "days": [0, 4]}) == "on Monday, Friday at 06:00"
    assert schedule.describe_when({**s, "repeat": schedule.ONCE, "date": "2026-11-05"}) == "once, 2026-11-05 at 06:00"


# ================================================================ missed while closed
def test_times_missed_while_the_app_was_closed_are_written_down_never_run_late(tmp_path: Path) -> None:
    sch, start = fresh(tmp_path), Starts()
    s = sch.add(daily("06:00"), T0)
    said = run_ticks(sch, start, [at(5, 12, 0)])          # closed from Monday 05:00 to Thursday noon
    assert start.calls == []
    assert outcomes(s) == ["missed"]
    assert "4 times" in s["history"][0]["detail"] and "wasn't running" in s["history"][0]["detail"]
    assert said and "missed" in said[0]
    run_ticks(sch, start, [at(5, 12, 1), at(6, 6, 0)])    # and the next one runs as usual
    assert [due for _i, due in start.calls] == [at(6, 6)]


def test_missed_days_before_a_time_still_in_its_window_dont_stop_that_one(tmp_path: Path) -> None:
    sch, start = fresh(tmp_path), Starts()
    s = sch.add(daily("06:00"), T0)
    run_ticks(sch, start, [at(4, 6, 10)])                 # opened 10 minutes after Wednesday's time
    assert [due for _i, due in start.calls] == [at(4, 6)]
    assert outcomes(s) == ["missed", STARTED]


def test_a_time_more_than_late_old_is_missed_even_with_the_app_open_from_then(tmp_path: Path) -> None:
    sch, start = fresh(tmp_path), Starts()
    sch.add(daily("06:00"), T0)
    run_ticks(sch, start, [at(2, 6) + schedule.LATE + dt.timedelta(minutes=1)])
    assert start.calls == []


# ================================================================ summer time
HOUR = dt.timedelta(hours=1)


class CentralEurope2026(dt.tzinfo):
    """Central European time for 2026 only, as PEP 495 asks (fold included): +1, summer time +2
    from 29 March (02:00 jumps to 03:00) to 25 October (03:00 goes back to 02:00). The tests set
    it as schedule.ZONE, so they never depend on the computer's own zone."""
    SPRING, FALL = dt.datetime(2026, 3, 29, 2), dt.datetime(2026, 10, 25, 2)       # local, the hour that is odd
    START, END = dt.datetime(2026, 3, 29, 1), dt.datetime(2026, 10, 25, 1)         # the same, in UTC

    def utcoffset(self, dt_: dt.datetime | None) -> dt.timedelta:
        assert dt_ is not None
        local = dt_.replace(tzinfo=None)
        if self.SPRING <= local < self.SPRING + HOUR:           # the hour the clock skips
            summer = bool(dt_.fold)
        elif self.FALL <= local < self.FALL + HOUR:             # the hour the clock shows twice
            summer = not dt_.fold
        else:
            summer = self.SPRING < local < self.FALL
        return 2 * HOUR if summer else HOUR

    def dst(self, dt_: dt.datetime | None) -> dt.timedelta:
        return self.utcoffset(dt_) - HOUR

    def tzname(self, dt_: dt.datetime | None) -> str:
        return "CEST" if self.dst(dt_) else "CET"

    def fromutc(self, dt_: dt.datetime) -> dt.datetime:
        u = dt_.replace(tzinfo=None)
        if self.START <= u < self.END:
            return (u + 2 * HOUR).replace(tzinfo=self)
        return (u + HOUR).replace(tzinfo=self, fold=int(self.END <= u < self.END + HOUR))


@pytest.fixture
def central(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(schedule, "ZONE", CentralEurope2026())


def spring(hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime(2026, 3, 29, hour, minute)


def fall(hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime(2026, 10, 25, hour, minute)


@pytest.mark.usefixtures("central")
def test_a_time_the_clock_skips_is_the_first_minute_after_the_gap() -> None:
    assert schedule.real(spring(2, 30)) == spring(3)
    assert schedule.real(spring(2, 0)) == spring(3)
    assert schedule.real(spring(2, 59)) == spring(3)
    assert schedule.real(spring(1, 59)) == spring(1, 59)
    assert schedule.real(spring(3, 0)) == spring(3, 0)
    assert schedule.real(fall(2, 30)) == fall(2, 30)                # shown twice: left as it is
    assert schedule.real(dt.datetime(2026, 3, 30, 2, 30)) == dt.datetime(2026, 3, 30, 2, 30)


@pytest.mark.usefixtures("central")
@pytest.mark.parametrize("time", ["02:00", "02:30", "02:59"])
def test_a_schedule_in_the_skipped_hour_runs_when_the_clock_comes_out_of_it(tmp_path: Path, time: str) -> None:
    sch, start = fresh(tmp_path), Starts()
    s = sch.add(daily(time), dt.datetime(2026, 3, 28, 12, 0))
    assert schedule.next_due(s, spring(1, 0)) == spring(3)
    said = run_ticks(sch, start, [spring(1, 59), spring(3, 0), spring(3, 3)])   # the clock goes 01:59 -> 03:00
    assert [due for _i, due in start.calls] == [spring(3)]
    assert outcomes(s) == [STARTED] and not any("missed" in line for line in said)
    hour, minute = schedule.parse_time(time)
    run_ticks(sch, start, [dt.datetime(2026, 3, 30, hour, minute)])
    assert start.calls[-1][1] == dt.datetime(2026, 3, 30, hour, minute)          # the next day as set


@pytest.mark.usefixtures("central")
def test_a_once_schedule_in_the_skipped_hour_runs_too(tmp_path: Path) -> None:
    sch, start = fresh(tmp_path), Starts()
    sch.add({**daily("02:15"), "repeat": schedule.ONCE, "date": "2026-03-29"}, dt.datetime(2026, 3, 28, 12, 0))
    run_ticks(sch, start, [spring(1, 59), spring(3, 0)])
    assert [due for _i, due in start.calls] == [spring(3)]


@pytest.mark.usefixtures("central")
def test_the_hour_the_clock_shows_twice_runs_a_schedule_once(tmp_path: Path) -> None:
    sch, start = fresh(tmp_path), Starts()
    s = sch.add(daily("02:30"), dt.datetime(2026, 10, 24, 12, 0))
    first = [fall(1, 45), fall(2, 29), fall(2, 30), fall(2, 31), fall(2, 59)]
    again = [fall(2, 0), fall(2, 29), fall(2, 30), fall(2, 31), fall(2, 59), fall(3, 0)]   # 03:00 went back to 02:00
    run_ticks(sch, start, first + again)
    assert [due for _i, due in start.calls] == [fall(2, 30)]
    assert outcomes(s) == [STARTED]


# ================================================================ busy, missing, broken
def test_a_busy_game_makes_it_wait_and_it_starts_once_the_game_is_free(tmp_path: Path) -> None:
    sch = fresh(tmp_path)
    s = sch.add(daily("06:00"), T0)
    busy = Starts((WAIT, "Hero's game is busy with Caves"))
    said = run_ticks(sch, busy, [at(2, 6, 0), at(2, 6, 1), at(2, 6, 2)])
    assert said == ["Wolves for Hero is waiting: Hero's game is busy with Caves"]      # said once
    assert outcomes(s) == []
    free = Starts()
    run_ticks(sch, free, [at(2, 6, 5)])
    assert [due for _i, due in free.calls] == [at(2, 6)] and outcomes(s) == [STARTED]


def test_two_schedules_at_once_for_one_character_never_run_together(tmp_path: Path) -> None:
    sch = fresh(tmp_path)
    first = sch.add(daily("06:00"), T0)
    second = sch.add(daily("06:00", item="script:Caves"), T0)
    running: set[str] = set()

    def start(s: Schedule, due: dt.datetime) -> tuple[str, str]:
        if s["character"] in running:
            return WAIT, "Hero's game is busy with Wolves"
        running.add(s["character"])
        return STARTED, "in the game"
    for minute in range(0, 20):
        sch.tick(at(2, 6, minute), start)
    assert outcomes(first) == [STARTED]
    assert outcomes(second) == ["skipped"]
    assert second["history"][0]["detail"] == "Hero's game is busy with Wolves"


def test_a_game_that_isn_t_open_is_waited_for_then_skipped_with_why(tmp_path: Path) -> None:
    sch = fresh(tmp_path)
    s = sch.add(daily("06:00"), T0)
    start = Starts((WAIT, "Hero isn't logged in to a game that Uncle Farmer sees"))
    run_ticks(sch, start, [at(2, 6, m) for m in range(0, 30, 5)])
    assert outcomes(s) == ["skipped"] and "isn't logged in" in s["history"][0]["detail"]
    assert len(start.calls) == 4                         # tried while the window was open, not after


def test_a_plan_that_is_gone_is_an_error_not_retried(tmp_path: Path) -> None:
    sch = fresh(tmp_path)
    s = sch.add(daily("06:00"), T0)
    start = Starts((FAILED, "the plan Wolves doesn't exist any more"))
    said = run_ticks(sch, start, [at(2, 6, 0), at(2, 6, 1)])
    assert len(start.calls) == 1 and outcomes(s) == [FAILED]
    assert "couldn't start" in said[0]


def test_a_start_that_blows_up_is_written_down_and_never_repeated(tmp_path: Path) -> None:
    sch = fresh(tmp_path)
    s = sch.add(daily("06:00"), T0)
    calls: list[dt.datetime] = []

    def start(sched: Schedule, due: dt.datetime) -> tuple[str, str]:
        calls.append(due)
        raise RuntimeError("the window went away")
    sch.tick(at(2, 6), start)
    sch.tick(at(2, 6, 1), start)
    assert calls == [at(2, 6)] and outcomes(s) == [FAILED]


def test_the_occurrence_is_saved_as_handled_before_the_run_starts(tmp_path: Path) -> None:
    """A crash right after the start must not start it again when the app comes back."""
    path = tmp_path / "schedules.json"
    sch = Scheduler(str(path))
    sch.add(daily("06:00"), T0)
    on_disk: list[str | None] = []

    def start(s: Schedule, due: dt.datetime) -> tuple[str, str]:
        on_disk.append(schedule.load(str(path))[0]["handled"])
        return STARTED, "in the game"
    sch.tick(at(2, 6), start)
    assert on_disk == ["2026-11-02 06:00"]
    again = Starts()
    run_ticks(Scheduler(str(path)), again, [at(2, 6, 1)])     # the app started again
    assert again.calls == []


# ================================================================ editing, turning off, deleting
def test_editing_keeps_the_history_and_a_time_moved_into_the_past_doesn_t_run(tmp_path: Path) -> None:
    sch, start = fresh(tmp_path), Starts()
    s = sch.add(daily("06:00"), T0)
    run_ticks(sch, start, [at(2, 6)])
    edited = sch.update(s["id"], daily("05:30", item="script:Caves"), at(3, 5, 45))
    assert edited["item"] == "script:Caves" and edited["time"] == "05:30" and outcomes(edited) == [STARTED]
    run_ticks(sch, start, [at(3, 5, 50)])
    assert len(start.calls) == 1                          # today's 05:30 was before the edit
    run_ticks(sch, start, [at(4, 5, 30)])
    assert start.calls[-1] == (s["id"], at(4, 5, 30))


def test_a_schedule_turned_off_doesn_t_run_and_on_again_doesn_t_make_up_for_it(tmp_path: Path) -> None:
    sch, start = fresh(tmp_path), Starts()
    s = sch.add(daily("06:00"), T0)
    sch.set_enabled(s["id"], False, T0)
    run_ticks(sch, start, [at(2, 6), at(3, 6)])
    assert start.calls == [] and schedule.next_due(s, at(3, 7)) is None
    sch.set_enabled(s["id"], True, at(3, 6, 5))
    run_ticks(sch, start, [at(3, 6, 6)])
    assert start.calls == []                              # Tuesday's came round while it was off
    run_ticks(sch, start, [at(4, 6)])
    assert [due for _i, due in start.calls] == [at(4, 6)]


def test_a_deleted_schedule_is_gone_from_the_file(tmp_path: Path) -> None:
    sch, start = fresh(tmp_path), Starts()
    keep = sch.add(daily("06:00"), T0)
    gone = sch.add(daily("07:00"), T0)
    sch.remove(gone["id"])
    assert [s["id"] for s in schedule.load(sch.path)] == [keep["id"]]
    run_ticks(sch, start, [at(2, 6), at(2, 7)])
    assert [i for i, _due in start.calls] == [keep["id"]]


# ================================================================ the file
def test_schedules_and_their_history_survive_a_restart(tmp_path: Path) -> None:
    sch, start = fresh(tmp_path), Starts()
    s = sch.add({**daily("22:00"), "repeat": schedule.WEEKLY, "days": [1, 3]}, T0)
    run_ticks(sch, start, [at(3, 22)])
    sch.ended(s["id"], "2026-11-03 22:00", "finished", "plan done; 120 kills", at(3, 23))
    back = Scheduler(sch.path)
    assert len(back.items) == 1
    again = back.items[0]
    assert {k: again[k] for k in ("item", "character", "repeat", "time", "days", "enabled")} == \
        {"item": "plan:Wolves", "character": "Hero", "repeat": "weekly", "time": "22:00", "days": [1, 3], "enabled": True}
    assert outcomes(again) == [STARTED, "finished"] and again["history"][1]["detail"] == "plan done; 120 kills"
    later = Starts()
    run_ticks(back, later, [at(3, 22, 5), at(5, 22)])
    assert [due for _i, due in later.calls] == [at(5, 22)]


def test_a_broken_file_or_entry_costs_only_itself(tmp_path: Path) -> None:
    path = tmp_path / "schedules.json"
    path.write_text('{"schedules": [{"id": "a", "item": "plan:Wolves", "character": "Hero", "repeat": "daily", '
                    '"time": "06:00"}, {"id": "b", "item": "plan:X", "character": "Hero", "repeat": "hourly", '
                    '"time": "06:00"}, {"id": "c", "item": "plan:X", "character": "", "repeat": "daily", '
                    '"time": "06:00"}, {"id": "d", "item": "plan:X", "character": "Hero", "repeat": "daily", '
                    '"time": "26:00"}, 7]}', encoding="utf-8")
    sch = Scheduler(str(path))
    assert [s["id"] for s in sch.items] == ["a"]
    start = Starts()
    run_ticks(sch, start, [at(2, 6)])                     # written by hand, no "handled": counts from now
    run_ticks(sch, start, [at(3, 6)])
    assert [due for _i, due in start.calls] == [at(3, 6)]
    path.write_text("not json", encoding="utf-8")
    assert Scheduler(str(path)).items == []
    assert Scheduler(str(tmp_path / "none.json")).items == []


def test_the_history_keeps_its_newest_entries_only(tmp_path: Path) -> None:
    sch, start = fresh(tmp_path), Starts()
    s = sch.add(daily("06:00"), T0)
    for d in range(schedule.HISTORY_KEEP + 5):
        sch.tick(T0 + dt.timedelta(days=d, hours=1), start)
    assert len(s["history"]) == schedule.HISTORY_KEEP
    assert len(start.calls) == schedule.HISTORY_KEEP + 5


@pytest.mark.parametrize("text, want", [("06:30", (6, 30)), ("6:05", (6, 5)), (" 23:59 ", (23, 59))])
def test_times_are_read_as_hours_and_minutes(text: str, want: tuple[int, int]) -> None:
    assert schedule.parse_time(text) == want


@pytest.mark.parametrize("text", ["", "6", "24:00", "12:60", "ab:cd", "-1:30"])
def test_a_time_that_isn_t_one_says_how_to_write_it(text: str) -> None:
    with pytest.raises(ValueError):
        schedule.parse_time(text)


def test_a_date_that_isn_t_one_says_how_to_write_it() -> None:
    assert schedule.parse_date("2026-11-05") == dt.date(2026, 11, 5)
    with pytest.raises(ValueError, match="year-month-day"):
        schedule.parse_date("05/11/2026")


# ================================================================ the main window's side
wx = pytest.importorskip("wx")

from unclefarmer.gui import main as gui_main, schedules as gui_schedules  # noqa: E402
from unclefarmer.gui.mainparts import scheduling  # noqa: E402


class ScheduledRun:
    def __init__(self, title: str) -> None:
        self.title = title
        self.schedule: tuple[str, str] | None = None
        self.ended_by_itself = False
        self.tally = None


class Window:
    """The main window's parts the scheduler uses; every other method is MainFrame's own."""

    def __init__(self, sch: Scheduler, games: list[tuple[int, str | None, str | None]],
                 runs: dict[int, ScheduledRun] | None = None, plans: tuple[str, ...] = ("Wolves",),
                 answer: str | None = None) -> None:
        self.scheduler, self.games, self.runs = sch, games, dict(runs or {})
        self.plans = plans
        self.answer = answer            # what start() answers when it refuses (None: it starts)
        self.started: list[tuple[int | None, tuple[str, str] | None, bool]] = []
        self.said: list[str] = []
        self.destroyed = False
        self.when = at(2, 6)

    def __getattr__(self, name: str) -> Any:
        attr = getattr(gui_main.MainFrame, name)
        return attr.__get__(self) if callable(attr) and hasattr(attr, "__get__") else attr

    def scheduled_items(self) -> list[tuple[str, str]]:
        return [("plan", n) for n in self.plans]

    def now(self) -> dt.datetime:
        return self.when

    def say(self, text: str) -> None:
        self.said.append(text)

    def start(self, pid: int | None = None, item: tuple[str, str] | None = None, remote: bool = False) -> str:
        """The Start button's path: here it only records, and the run appears as start() makes it."""
        self.started.append((pid, item, remote))
        if self.answer is not None:
            return self.answer
        if pid is not None and item is not None:
            self.runs[pid] = ScheduledRun(item[1])
        return "Starting %s." % (item[1] if item else "?")


def test_a_due_schedule_starts_through_the_start_button_s_path_in_its_character_s_game(tmp_path: Path) -> None:
    sch = fresh(tmp_path)
    s = sch.add(daily("06:00", who="hero"), T0)
    w = Window(sch, [(11, "Other", "Mario Basin"), (22, "Hero", "Giant Rock City")])
    w.schedule_tick()
    assert w.started == [(22, ("plan", "Wolves"), True)]          # remote: no message boxes
    assert w.runs[22].schedule == (s["id"], "2026-11-02 06:00")
    assert w.said == ["Scheduled: starting Wolves for hero"]
    w.schedule_tick()
    assert len(w.started) == 1


def test_the_window_waits_for_a_busy_or_missing_game_and_never_stops_a_run(tmp_path: Path) -> None:
    sch = fresh(tmp_path)
    sch.add(daily("06:00"), T0)
    busy = Window(sch, [(22, "Hero", None)], runs={22: ScheduledRun("Caves")})
    busy.schedule_tick()
    assert busy.started == [] and busy.runs[22].title == "Caves"
    assert busy.said == ["Wolves for Hero is waiting: Hero's game is busy with Caves"]
    nobody = Window(sch, [(11, "Other", None)])
    nobody.when = at(2, 6, 1)
    nobody.schedule_tick()
    assert nobody.started == [] and "isn't logged in" in nobody.said[0]


def test_a_scheduled_plan_that_was_deleted_is_an_error(tmp_path: Path) -> None:
    sch = fresh(tmp_path)
    s = sch.add(daily("06:00"), T0)
    w = Window(sch, [(22, "Hero", None)], plans=())
    w.schedule_tick()
    assert w.started == [] and outcomes(s) == [FAILED]
    assert "doesn't exist any more" in s["history"][0]["detail"]


def test_a_start_that_refuses_is_written_down_with_its_answer(tmp_path: Path) -> None:
    sch = fresh(tmp_path)
    s = sch.add(daily("06:00"), T0)
    w = Window(sch, [(22, "Hero", None)], answer="The script has an error on line 3.")
    w.schedule_tick()
    assert outcomes(s) == [FAILED] and s["history"][0]["detail"] == "The script has an error on line 3."


@pytest.mark.parametrize("by_itself, reason, want", [(True, "plan done", "finished"), (False, "stopped by you", "stopped"),
                                                      (False, "unexpected error: KeyError('x')", FAILED)])
def test_how_a_scheduled_run_ended_goes_into_its_history(tmp_path: Path, by_itself: bool, reason: str, want: str) -> None:
    sch = fresh(tmp_path)
    s = sch.add(daily("06:00"), T0)
    w = Window(sch, [(22, "Hero", None)])
    w.schedule_tick()
    run = w.runs[22]
    run.ended_by_itself = by_itself
    w.when = at(2, 8)
    w.schedule_ended(run, reason)
    assert outcomes(s) == [STARTED, want] and s["history"][1]["detail"] == reason
    assert s["history"][1]["at"] == "2026-11-02 08:00:00" and s["history"][1]["due"] == "2026-11-02 06:00"
    other = ScheduledRun("by hand")
    w.schedule_ended(other, "plan done")                 # a run no schedule started: nothing written
    assert len(s["history"]) == 2


def test_the_list_says_when_next_and_the_history_reads_newest_first() -> None:
    s: Schedule = {**daily("06:00"), "id": "x", "handled": schedule.stamp(T0), "history": [
        {"due": "2026-11-01 06:00", "at": "2026-11-01 06:00:05", "outcome": "started", "detail": "in Hero's game"},
        {"due": "2026-11-01 06:00", "at": "2026-11-01 09:00:00", "outcome": "finished", "detail": "plan done"}]}
    assert gui_schedules.when_next(s, T0) == "Mon 02 Nov 06:00"
    assert gui_schedules.when_next({**s, "enabled": False}, T0) == "off"
    assert gui_schedules.when_next(s, at(2, 6, 3)) == "now (waiting to start)"
    lines = gui_schedules.history_text(s).splitlines()
    assert lines[0] == "2026-11-01 09:00:00: finished (due 2026-11-01 06:00) - plan done"
    assert gui_schedules.history_text({**s, "history": []}) == "Nothing has happened yet."


class Field:
    def __init__(self, value: Any = "", selection: int = 0) -> None:
        self.value, self.selection = value, selection

    def GetValue(self) -> Any:
        return self.value

    def GetSelection(self) -> int:
        return self.selection


class Editor:
    """EditScheduleDialog's fields, as the player left them."""

    def __init__(self, repeat: str, time: str = "06:30", date: str = "2026-11-05", days: tuple[int, ...] = (),
                 who: str = "Hero", what: int = 0) -> None:
        self.items = [("plan", "Wolves"), ("script", "Caves")]
        self.what = Field(selection=what)
        self.who = Field(who)
        self.repeat = Field(selection=schedule.REPEATS.index(repeat))
        self.time, self.date = Field(time), Field(date)
        self.days = [Field(i in days) for i in range(7)]
        self.enabled = Field(True)

    def now(self) -> dt.datetime:
        return at(4, 12)

    def read(self) -> Schedule:
        reader: Any = gui_schedules.EditScheduleDialog.read
        return reader(self)


def test_the_editor_turns_its_fields_into_a_schedule() -> None:
    got = Editor(schedule.WEEKLY, days=(0, 6), what=1).read()
    assert got == {"item": "script:Caves", "character": "Hero", "repeat": "weekly", "time": "06:30", "enabled": True,
                   "date": "", "days": [0, 6]}
    once = Editor(schedule.ONCE, time="7:05").read()
    assert once["date"] == "2026-11-05" and once["time"] == "07:05" and once["days"] == []


@pytest.mark.parametrize("editor, says", [
    (Editor(schedule.DAILY, time="25:00"), "hours go from 0 to 23"),
    (Editor(schedule.WEEKLY), "Tick at least one day"),
    (Editor(schedule.ONCE, date="2026-11-04", time="11:00"), "already passed"),
    (Editor(schedule.ONCE, date="next week"), "year-month-day"),
    (Editor(schedule.DAILY, who="  "), "Choose a character"),
    (Editor(schedule.DAILY, what=5), "Choose a plan or script"),
])
def test_the_editor_refuses_what_can_t_run(editor: Editor, says: str) -> None:
    with pytest.raises(ValueError, match=says):
        editor.read()


def test_the_schedules_file_is_never_replaced_by_an_update() -> None:
    from unclefarmer import updater
    assert "schedules.json" in updater.NEVER
    assert scheduling.TICK_MS <= 60_000                  # looked at well inside the 15 minutes an occurrence waits
