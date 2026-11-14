"""Scheduled runs in the main window: the timer that starts what is due, and Run, Schedules.

A scheduled plan or script is started by start(), the Start button's own path, in the game its
character is logged in to; schedule.Scheduler decides when, and keeps it from running twice.
"""

from __future__ import annotations

import datetime as dt

import wx

from ... import applog, schedule, settings, stats
from ...errors import carry_on
from ...engine import plan as plans
from ...engine.runner import Run
from ...i18n import _
from ..schedules import SchedulesDialog
from .base import FrameParts

TICK_MS = 20_000          # how often the schedules are looked at


class SchedulingMixin(FrameParts):
    scheduler: schedule.Scheduler
    schedule_timer: wx.Timer

    def start_schedules(self) -> None:
        self.scheduler = schedule.Scheduler()
        self.schedule_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda e: self.schedule_tick(), self.schedule_timer)
        self.schedule_timer.Start(TICK_MS)
        applog.bootup.note("schedules: %d, looked at every %d s" % (len(self.scheduler.items), TICK_MS // 1000))
        wx.CallAfter(self.schedule_tick)     # times missed while the app was closed are written down now

    @staticmethod
    def now() -> dt.datetime:
        return dt.datetime.now()

    def schedule_tick(self) -> None:
        if self.destroyed or getattr(self, "updating", False):
            return
        try:
            told = self.scheduler.tick(self.now(), self.start_scheduled)
        except OSError as e:          # the file couldn't be written: say so, try again next time
            self.say(_("Couldn't save the schedules: {err}", err=e))
            return
        for _s, line in told:
            self.say(line)

    def scheduled_items(self) -> list[tuple[str, str]]:
        return [("plan", n) for n in plans.names()] + [("script", n) for n in plans.script_names()]

    def start_scheduled(self, s: schedule.Schedule, due: dt.datetime) -> tuple[str, str]:
        """Start one due occurrence: (schedule.STARTED | WAIT | FAILED, what happened)."""
        item = schedule.item_of(s)
        if item not in self.scheduled_items():
            return schedule.FAILED, _("the {kind} {name} doesn't exist any more",
                                      kind=_("plan") if item[0] == "plan" else _("script"), name=item[1])
        who = s["character"].strip().casefold()
        candidates = [profile for profile, _email in settings.automatic_login_profiles()
                      if who in (profile.casefold(), settings.profile_display(profile).casefold(),
                                 settings.profile_name(profile).casefold())]
        target = candidates[0] if len(candidates) == 1 else None
        if target:
            pid, waiting = self.automatic_login_window(target)
            if pid is None:
                return schedule.WAIT, waiting
        else:                                    # older schedules stored a plain character name
            pid = next((g[0] for g in self.games if settings.profile_name(g[1]).casefold() == who), None)
        if pid is None:
            return schedule.WAIT, _("{who} isn't logged in to one available game", who=s["character"])
        busy = self.runs.get(pid)
        if busy is not None:
            return schedule.WAIT, _("{who}'s game is busy with {what}", who=s["character"], what=busy.title)
        answer = (self.start(pid, item, remote=True, profile=target) if target else
                  self.start(pid, item, remote=True)) or ""
        run = self.runs.get(pid)
        if run is None or run.title != item[1]:
            return schedule.FAILED, answer or _("it didn't start")
        run.schedule = (s["id"], schedule.stamp(due))
        return schedule.STARTED, _("in {who}'s game", who=s["character"])

    def schedule_ended(self, run: Run, reason: str) -> None:
        """A scheduled run has ended: its history says how."""
        mark: tuple[str, str] | None = getattr(run, "schedule", None)
        if mark is None:
            return
        if reason.startswith(_("unexpected error: {err}", err="").rstrip()):
            outcome = schedule.FAILED
        elif run.ended_by_itself:
            outcome = "finished"
        else:
            outcome = "stopped"
        tally = getattr(run, "tally", None)
        detail = reason
        if tally is not None:
            try:
                detail += "; " + stats.short(tally.result(), tally.drop_left)
            except Exception as e:    # the results are a convenience here; the end is still written down
                carry_on(e, "the results of a scheduled run")
        try:
            self.scheduler.ended(mark[0], mark[1], outcome, detail, self.now())
        except OSError as e:
            self.say(_("Couldn't save the schedules: {err}", err=e))

    def open_schedules(self) -> None:
        names = sorted({profile for profile, _email in settings.automatic_login_profiles()} |
                       {g[1] for g in self.games if g[1]} | set(stats.characters()), key=settings.profile_display)
        with SchedulesDialog(self, self.scheduler, self.scheduled_items(), self.item_label, names, self.now) as d:
            d.ShowModal()
