"""Run, Schedules: plans and scripts started at set times (unclefarmer/schedule.py does the timing).

The list says what runs, for whom, when, when next, and whether it is on; Add, Edit, Turn on or
off, Delete and History act on the selected one. Every change is saved straight away.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Sequence
from typing import Any, cast

import wx

from .. import schedule, settings
from ..i18n import _
from .common import (ContextAction, Dialog, Form, ask, buttons, error, first_selected, labeled, ok_cancel,
                     opens, pick, popup_actions, select_row, show_text)

Item = tuple[str, str]          # ("plan" | "script", name), as the Plans tab lists them
Now = Callable[[], dt.datetime]


def when_next(s: schedule.Schedule, now: dt.datetime) -> str:
    t = schedule.next_due(s, now)
    if t is None:
        return _("never again") if s.get("enabled") else _("off")
    if t <= now:
        return _("now (waiting to start)")
    return t.strftime("%a %d %b %H:%M")


def history_text(s: schedule.Schedule) -> str:
    rows = list(reversed(s.get("history") or []))
    if not rows:
        return _("Nothing has happened yet.")
    out: list[str] = []
    for h in rows:
        outcome = schedule.OUTCOMES.get(str(h.get("outcome")), str(h.get("outcome")))
        line = _("{at}: {outcome} (due {due})", at=h.get("at"), outcome=_(outcome), due=h.get("due"))
        if h.get("detail"):
            line += " - " + str(h["detail"])
        out.append(line)
    return "\n".join(out)


class EditScheduleDialog(Dialog):
    """One schedule's fields. fields: what to save once OK is pressed."""

    def __init__(self, parent: wx.Window, items: Sequence[Item], label: Callable[[Item], str],
                 characters: Sequence[str], now: Now, s: schedule.Schedule | None = None) -> None:
        super().__init__(parent, title=_("Edit schedule") if s else _("New schedule"))
        self.items, self.now = list(items), now
        self.character_keys = list(characters)
        self.fields: schedule.Schedule = {}
        start = now() + dt.timedelta(hours=1)
        s = s or {"item": "", "character": characters[0] if characters else "", "repeat": schedule.DAILY,
                  "time": start.strftime("%H:%M"), "date": start.strftime("%Y-%m-%d"), "days": [], "enabled": True}
        root = wx.BoxSizer(wx.VERTICAL)
        f = Form(self)
        saved = tuple(str(s.get("item", "")).partition(":")[::2])
        self.what = f.choice(_("&Plan or script:"), [label(i) for i in self.items], pick(self.items, saved))
        current = str(s.get("character") or "")
        labels = [settings.profile_display(character) for character in self.character_keys]
        selected = pick(self.character_keys, current)
        if selected < 0:
            selected = pick(labels, current)
        self.who = f.choice(_("&Character:"), labels, selected)
        self.repeat = f.choice(_("&Repeat:"), [_(schedule.REPEAT_NAMES[r]) for r in schedule.REPEATS],
                               pick(list(schedule.REPEATS), s.get("repeat"), 1))
        self.date = f.text(_("&Date (year-month-day):"), s.get("date") or start.strftime("%Y-%m-%d"))
        self.time = f.text(_("&Time (hours:minutes):"), s.get("time") or "")
        self.days = [f.check(_(name), i in (s.get("days") or [])) for i, name in enumerate(schedule.DAY_NAMES)]
        self.enabled = f.check(_("Turned &on"), s.get("enabled", True))
        root.Add(f.grid, 0, wx.EXPAND | wx.ALL, 12)
        ok_cancel(self, root, _("&Save"))
        self.SetSizerAndFit(root)
        self.repeat.Bind(wx.EVT_CHOICE, lambda e: self.sync())
        self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)
        self.sync()

    def sync(self) -> None:
        repeat = schedule.REPEATS[self.repeat.GetSelection()]
        self.date.Enable(repeat == schedule.ONCE)
        for c in self.days:
            c.Enable(repeat == schedule.WEEKLY)

    def read(self) -> schedule.Schedule:
        """The fields, checked; ValueError with a message for the player otherwise."""
        i = self.what.GetSelection()
        if not 0 <= i < len(self.items):
            raise ValueError(_("Choose a plan or script to run."))
        keys = getattr(self, "character_keys", ())
        selection = self.who.GetSelection()
        who = keys[selection] if 0 <= selection < len(keys) else cast(Any, self.who).GetValue().strip()
        if not who:
            raise ValueError(_("Choose a character."))
        repeat = schedule.REPEATS[self.repeat.GetSelection()]
        hour, minute = schedule.parse_time(self.time.GetValue())
        fields: schedule.Schedule = {"item": "%s:%s" % self.items[i], "character": who, "repeat": repeat,
                                     "time": "%02d:%02d" % (hour, minute), "enabled": self.enabled.GetValue(),
                                     "date": "", "days": []}
        if repeat == schedule.ONCE:
            day = schedule.parse_date(self.date.GetValue())
            if dt.datetime.combine(day, dt.time(hour, minute)) <= self.now():
                raise ValueError(_("That time has already passed: choose a later one."))
            fields["date"] = day.strftime("%Y-%m-%d")
        if repeat == schedule.WEEKLY:
            fields["days"] = [d for d, c in enumerate(self.days) if c.GetValue()]
            if not fields["days"]:
                raise ValueError(_("Tick at least one day."))
        return fields

    def on_ok(self, evt: wx.CommandEvent) -> None:
        try:
            self.fields = self.read()
        except ValueError as e:
            error(self, str(e))
            return
        self.EndModal(wx.ID_OK)


class SchedulesDialog(Dialog):
    def __init__(self, parent: wx.Window, scheduler: schedule.Scheduler, items: Sequence[Item],
                 label: Callable[[Item], str], characters: Sequence[str], now: Now) -> None:
        super().__init__(parent, title=_("Schedules"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.scheduler, self.items, self.label, self.characters, self.now = scheduler, list(items), label, list(characters), now
        root = wx.BoxSizer(wx.VERTICAL)
        box = wx.BoxSizer(wx.VERTICAL)
        self.list = labeled(self, box, _("&Schedules:"), lambda p: wx.ListCtrl(
            p, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=wx.Size(-1, 200)), 1)
        for i, (title, width) in enumerate(((_("Plan or script"), 180), (_("Character"), 120), (_("When"), 200),
                                            (_("Next"), 150), (_("On"), 50))):
            self.list.InsertColumn(i, title, width=width)
        self.add_btn = buttons(self, box, (opens(_("&Add")), lambda e: self.add()))[0]
        note = wx.StaticText(self, label=_(
            "A scheduled plan starts in the game the character is logged in to, as the Start button would. "
            "A time missed while Uncle Farmer was closed doesn't run later; a game busy with another run "
            "waits up to 15 minutes."))
        note.Wrap(560)
        box.Add(note, 0, wx.TOP, 10)
        root.Add(box, 1, wx.EXPAND | wx.ALL, 12)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.AddStretchSpacer()
        close = wx.Button(self, wx.ID_CANCEL, _("&Close"))
        row.Add(close)
        root.Add(row, 0, wx.EXPAND | wx.ALL, 12)
        self.SetSizerAndFit(root)
        self.SetMinSize(wx.Size(640, 400))
        self.list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: self.edit())
        self.list.Bind(wx.EVT_LIST_ITEM_SELECTED, lambda e: self.sync())
        self.list.Bind(wx.EVT_CONTEXT_MENU, self.context_menu)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key)
        self.fill()

    def on_key(self, evt: wx.KeyEvent) -> None:
        if wx.Window.FindFocus() is self.list and evt.GetKeyCode() == wx.WXK_DELETE:
            self.delete()
        else:
            evt.Skip()

    def context_menu(self, event: wx.ContextMenuEvent) -> None:
        pos = event.GetPosition()
        if pos != wx.DefaultPosition:
            index, _flags = self.list.HitTest(self.list.ScreenToClient(pos))
            if index != wx.NOT_FOUND:
                state = wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED
                self.list.SetItemState(index, state, state)
        selected = self.selected() is not None
        entries: list[ContextAction] = [
                (opens(_("&Add")), lambda e: self.add(), bool(self.items)),
                (opens(_("&Edit")), lambda e: self.edit(), selected),
                (_("Turn on or o&ff"), lambda e: self.toggle(), selected),
                (opens(_("&History")), lambda e: self.history(), selected),
                (_("&Delete"), lambda e: self.delete(), selected)]
        popup_actions(self.list, entries)

    def selected(self) -> schedule.Schedule | None:
        i = first_selected(self.list)
        return self.scheduler.items[i] if 0 <= i < len(self.scheduler.items) else None

    def fill(self, select: str | None = None) -> None:
        self.list.DeleteAllItems()
        now = self.now()
        for i, s in enumerate(self.scheduler.items):
            self.list.InsertItem(i, self.label(schedule.item_of(s)))
            self.list.SetItem(i, 1, settings.profile_display(s["character"]))
            self.list.SetItem(i, 2, schedule.describe_when(s))
            self.list.SetItem(i, 3, when_next(s, now))
            self.list.SetItem(i, 4, _("on") if s.get("enabled") else _("off"))
        ids = [s["id"] for s in self.scheduler.items]
        if ids:
            select_row(self.list, ids.index(select) if select in ids else 0)
        self.sync()

    def sync(self) -> None:
        self.add_btn.Enable(bool(self.items))

    def add(self) -> None:
        if not self.items:
            error(self, _("Make a plan or script first, in the Plans tab."))
            return
        with EditScheduleDialog(self, self.items, self.label, self.characters, self.now) as d:
            if d.ShowModal() != wx.ID_OK:
                return
            try:
                s = self.scheduler.add(d.fields, self.now())
            except (OSError, ValueError) as e:
                error(self, _("Couldn't save: {err}", err=e))
                return
        self.fill(s["id"])

    def edit(self) -> None:
        s = self.selected()
        if s is None:
            return
        with EditScheduleDialog(self, self.items, self.label, self.characters, self.now, s) as d:
            if d.ShowModal() != wx.ID_OK:
                return
            try:
                self.scheduler.update(s["id"], d.fields, self.now())
            except (OSError, ValueError) as e:
                error(self, _("Couldn't save: {err}", err=e))
                return
        self.fill(s["id"])

    def toggle(self) -> None:
        s = self.selected()
        if s is None:
            return
        try:
            self.scheduler.set_enabled(s["id"], not s.get("enabled"), self.now())
        except OSError as e:
            error(self, _("Couldn't save: {err}", err=e))
        self.fill(s["id"])

    def delete(self) -> None:
        s = self.selected()
        if s is None or not ask(self, _("Delete the schedule for {what} ({who})?", what=schedule.item_of(s)[1],
                                        who=s["character"])):
            return
        try:
            self.scheduler.remove(s["id"])
        except OSError as e:
            error(self, _("Couldn't save: {err}", err=e))
        self.fill()

    def history(self) -> None:
        s = self.selected()
        if s is not None:
            show_text(self, _("History of {what} for {who}", what=schedule.item_of(s)[1], who=s["character"]),
                      history_text(s))
