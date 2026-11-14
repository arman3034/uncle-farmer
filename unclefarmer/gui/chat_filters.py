"""Native, accessible chat filter editor and a view of hidden messages in the live buffers."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import wx

from .. import chat, chat_filters as filters
from ..i18n import _
from .common import Dialog, buttons, error, labeled, ok_cancel, opens, page, tabs


def describe(rule: filters.Filter) -> str:
    mode = _(filters.MODE_NAMES[filters.MODES.index(rule.mode)])
    return _("{mode}: {pattern} ({state})", mode=mode, pattern=rule.text,
             state=_("Enabled") if rule.enabled else _("Disabled"))


class FilterEditor(Dialog):
    def __init__(self, parent: wx.Window, rule: filters.Filter | None = None) -> None:
        super().__init__(parent, title=_("Edit filter") if rule else _("Add new filter"))
        self.rule = rule
        box = wx.BoxSizer(wx.VERTICAL)
        self.mode = labeled(self, box, _("Matching &type:"),
                            lambda w: wx.Choice(w, choices=[_(n) for n in filters.MODE_NAMES]))
        self.mode.SetSelection(filters.MODES.index(rule.mode) if rule else 0)
        self.text = labeled(self, box, _("Filter text or &pattern:"), lambda w: wx.TextCtrl(w, size=wx.Size(420, -1)))
        self.text.SetValue(rule.text if rule else "")
        box.Add(wx.StaticText(self, label=_("Wildcards: * matches any text; ? matches one character. Not a regular expression.")),
                0, wx.TOP, 8)
        self.enabled = wx.CheckBox(self, label=_("&Enabled"))
        self.enabled.SetValue(rule.enabled if rule else True)
        box.Add(self.enabled, 0, wx.TOP, 8)
        self.case = wx.CheckBox(self, label=_("Match &case"))
        self.case.SetValue(rule.case_sensitive if rule else True)
        box.Add(self.case, 0, wx.TOP, 8)
        self.sample = labeled(self, box, _("Test &message:"), lambda w: wx.TextCtrl(w))
        buttons(self, box, (_("&Test filter"), lambda e: self.test()))
        self.result = wx.StaticText(self, label="")
        box.Add(self.result, 0, wx.TOP, 8)
        ok_cancel(self, box)
        self.SetSizerAndFit(box)
        self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)

    def value(self) -> filters.Filter:
        return filters.make_filter(filters.MODES[self.mode.GetSelection()], self.text.GetValue(),
                                   self.enabled.GetValue(), self.case.GetValue(), self.rule.id if self.rule else None)

    def test(self) -> None:
        try:
            rule = self.value()
        except ValueError as e:
            error(self, str(e))
            return
        self.result.SetLabel(_("Matches") if replace(rule, enabled=True).matches(self.sample.GetValue()) else _("Does not match"))
        self.Layout()

    def on_ok(self, _evt: wx.Event) -> None:
        try:
            self.value()
        except ValueError as e:
            error(self, str(e))
            return
        self.EndModal(wx.ID_OK)


class FilterManager(Dialog):
    def __init__(self, parent: wx.Window, rules: list[filters.Filter], feed: Callable[[], chat.Feed | None],
                 render: Callable[[chat.Line], str], save: Callable[[list[filters.Filter]], bool]) -> None:
        super().__init__(parent, title=_("Chat filters"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.rules = list(rules)
        self.feed, self.render, self.save = feed, render, save
        self.hidden: list[chat.Line] = []
        box = wx.BoxSizer(wx.VERTICAL)
        self.nb = tabs(self)
        box.Add(self.nb, 1, wx.EXPAND)
        panel, body = page(self.nb, _("Filter list"))
        body.Add(wx.StaticText(panel, label=_("Hidden messages stay in the current chat buffers. Only filter rules are saved.")),
                 0, wx.TOP, 8)
        self.messages = labeled(panel, body, _("Hidden &messages and matching filters:"),
                                lambda w: wx.ListBox(w, size=wx.Size(570, 230)), 1)
        self.restore_button = buttons(panel, body, (_("&Restore selected message"), lambda e: self.restore_selected()))[0]
        body.Add(wx.StaticText(panel, label=_("Restoring disables all matching rules, also restoring other messages they hide.")),
                 0, wx.TOP, 8)
        panel, body = page(self.nb, _("Filter settings"))
        self.list = labeled(panel, body, _("&Filters:"), lambda w: wx.ListBox(w, size=wx.Size(570, 230)), 1)
        self.rule_buttons = buttons(panel, body, (opens(_("&Add new filter")), lambda e: self.edit()),
                (opens(_("&Edit filter")), lambda e: self.edit(self.selected())),
                (_("&Delete filter"), lambda e: self.delete()),
                (_("Enable/&disable filter"), lambda e: self.toggle()))
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self.edit(self.selected()))
        self.status = wx.StaticText(self, label=_("Changes apply when you save."))
        box.Add(self.status, 0, wx.ALL, 8)
        ok_cancel(self, box, _("&Save"))
        self.SetSizerAndFit(box)
        self.Bind(wx.EVT_BUTTON, self.on_save, id=wx.ID_OK)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda e: self.refresh_hidden(), self.timer)
        self.timer.Start(1000)
        self.refresh()

    def selected(self) -> filters.Filter | None:
        i = self.list.GetSelection()
        return self.rules[i] if 0 <= i < len(self.rules) else None

    def refresh(self, id: str | None = None) -> None:
        self.list.Set([describe(r) for r in self.rules])
        if self.rules:
            self.list.SetSelection(next((i for i, r in enumerate(self.rules) if r.id == id), 0))
        for button in self.rule_buttons[1:]:
            button.Enable(bool(self.rules))
        self.refresh_hidden()

    def refresh_hidden(self) -> None:
        feed = self.feed()
        lines = [line for key in [*chat.CHANNEL_KEYS, chat.NOTICE, chat.PRIVATE]
                 for line in (feed.buffer(key) if feed else [])]
        hidden = sorted((line for line in lines if filters.matching(self.rules, line["text"])), key=lambda x: x["when"])
        rows = [_("{message} — hidden by {filters}", message=self.render(line),
                  filters="; ".join(describe(r) for r in filters.matching(self.rules, line["text"]))) for line in hidden]
        if rows != self.messages.GetStrings():
            i = self.messages.GetSelection()
            selected = self.hidden[i] if 0 <= i < len(self.hidden) else None
            self.messages.Set(rows)
            if hidden:
                self.messages.SetSelection(next((n for n, line in enumerate(hidden) if line is selected), 0))
        self.hidden = hidden
        self.restore_button.Enable(bool(hidden))

    def edit(self, rule: filters.Filter | None = None) -> None:
        with FilterEditor(self, rule) as d:
            if d.ShowModal() != wx.ID_OK:
                return
            value = d.value()
            try:
                self.rules = filters.add(self.rules, value)
            except ValueError as e:
                error(self, str(e))
                return
            self.refresh(value.id)

    def delete(self) -> None:
        rule = self.selected()
        if rule:
            self.rules = [r for r in self.rules if r.id != rule.id]
            self.refresh()

    def toggle(self) -> None:
        rule = self.selected()
        if rule:
            self.rules = [replace(r, enabled=not r.enabled) if r.id == rule.id else r for r in self.rules]
            self.refresh(rule.id)

    def restore_selected(self) -> None:
        i = self.messages.GetSelection()
        if 0 <= i < len(self.hidden):
            self.rules = filters.restore(self.rules, self.hidden[i]["text"])
            self.status.SetLabel(_("Matching filters disabled. Save to restore these messages in chat."))
            self.refresh()

    def on_save(self, _evt: wx.Event) -> None:
        if self.save(self.rules):
            self.timer.Stop()
            self.EndModal(wx.ID_OK)
