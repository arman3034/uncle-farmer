"""Exercise the real chat controls with an in-memory feed; no game or messages are sent."""
from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, cast

import pytest
import wx

from unclefarmer import chat, chat_filters as filters, settings
from unclefarmer.gui import chat as gui
from unclefarmer.gui.chat_filters import FilterEditor, FilterManager
from conftest import returning

if TYPE_CHECKING:
    from unclefarmer.gui.mainparts.base import FrameParts


@pytest.fixture
def window(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[gui.ChatFrame, Any, chat.Feed]]:
    app = wx.GetApp() or wx.App(False)
    host: Any = wx.Frame(None)
    host.s = settings.load_app()
    windows: dict[int, gui.ChatFrame] = {}
    host.chat_windows = windows
    feed = chat.Feed(77)
    host.chats = {77: feed}
    host.messengers = {}
    notices: list[str] = []
    host.notices = notices
    host.say = notices.append
    host.cached = returning(None)
    frame = gui.ChatFrame(cast("FrameParts", host), 77, "Hero")
    windows[77] = frame
    yield frame, host, feed
    frame.Destroy()
    host.Destroy()
    app.ProcessPendingEvents()


def arrive(frame: gui.ChatFrame, feed: chat.Feed, channel: str, name: str, text: str, peer_id: int = 0) -> chat.Line:
    feed.add(channel, name, text, peer_id=peer_id)
    line = feed.buffer(channel)[-1]
    frame.add(line)
    return line


def test_context_filter_hides_existing_incoming_and_restores(window: Any) -> None:
    frame, host, feed = window
    line = arrive(frame, feed, "4", "Prince", "hello")
    arrive(frame, feed, "4", "Kim", "other")
    frame.filter_message(line)
    assert [x["text"] for x in frame.ch_lines] == ["other"]
    assert len(feed.buffer("4")) == 2
    frame.filter_message(line)  # repeated invocation never duplicates the rule
    assert len(frame.filters) == 1
    arrive(frame, feed, "4", "Ali", "hello")
    assert [x["text"] for x in frame.ch_lines] == ["other"]
    frame.show_channel()
    assert len(frame.ch_lines) == 1
    assert filters.load(settings.load_app()) == frame.filters
    assert frame.save_filters(filters.restore(frame.filters, "hello"))
    assert [x["text"] for x in frame.ch_lines] == ["hello", "other", "hello"]
    assert host.notices[-1] == "Message added to the filter list."


def test_save_failure_does_not_apply_rules(window: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    frame, host, feed = window
    arrive(frame, feed, "4", "Kim", "keep")
    monkeypatch.setattr(gui, "save_file", returning(False))
    assert not frame.save_filters([filters.make_filter("exact", "keep")])
    assert not frame.filters and not host.s["chat_filters"]
    assert frame.ch_lines[0]["text"] == "keep"


def test_saved_filters_update_other_open_games(window: Any) -> None:
    frame, host, feed = window
    second_feed = chat.Feed(88)
    host.chats[88] = second_feed
    second = gui.ChatFrame(cast("FrameParts", host), 88, "Other hero")
    host.chat_windows[88] = second
    try:
        original = arrive(frame, feed, "4", "Kim", "sale")
        arrive(second, second_feed, "4", "Prince", "sale")
        frame.filter_message(original)
        assert second.ch_lines == [] and len(second_feed.buffer("4")) == 1
        assert second.filters == frame.filters
    finally:
        host.chat_windows.pop(88)
        second.Destroy()


def test_reply_stays_on_original_channel_and_prevents_duplicate_prefix(window: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    frame, _host, feed = window
    sent: list[tuple[int, str]] = []
    def say(channel: int, text: str) -> None:
        sent.append((channel, text))
    monkeypatch.setattr(feed, "say", say)
    original = arrive(frame, feed, "3", "Prince", "hello")
    frame.begin_reply(False, original)
    assert frame.ch_text.GetValue() == "@Prince "
    assert frame.reply_controls[False][1].IsShown()
    arrive(frame, feed, "4", "Kim", "different channel")
    frame.ch_list.SetSelection(len(frame.ch_lines) - 1)
    assert frame.channel_target() == "3"
    frame.ch_text.SetValue("@prince @Prince yes")
    frame.send()
    assert sent == [(3, "@Prince yes")]
    assert not frame.replies and frame.ch_text.GetValue() == ""


def test_failed_reply_keeps_draft_and_cancel_preserves_body(window: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    frame, host, feed = window
    original = arrive(frame, feed, "4", "Kim", "hello")
    frame.begin_reply(False, original)
    frame.ch_text.SetValue("@Kim hello back")
    monkeypatch.setattr(feed, "say", returning("offline"))
    frame.send()
    assert host.notices[-1] == "offline" and False in frame.replies
    frame.cancel_reply(False)
    assert frame.ch_text.GetValue() == "hello back" and not frame.replies
    assert not frame.reply_controls[False][1].IsShown()


def test_reply_prefix_alone_is_not_sent_and_escape_keeps_window(window: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    frame, _host, feed = window
    original = arrive(frame, feed, "4", "Kim", "hello")
    def forbid(*_args: object) -> None:
        pytest.fail("A username alone is not a reply")
    monkeypatch.setattr(feed, "say", forbid)
    frame.begin_reply(False, original)
    frame.begin_reply(False, original)
    assert frame.ch_text.GetValue() == "@Kim "
    frame.send()
    assert False in frame.replies
    frame.ch_text.SetValue("@Kim draft")
    event = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
    event.SetKeyCode(wx.WXK_ESCAPE)
    frame.on_key(event)
    assert not frame.replies and frame.ch_text.GetValue() == "draft"


def test_private_reply_cancel_updates_recipient_label(window: Any) -> None:
    frame, _host, feed = window
    original = arrive(frame, feed, chat.PRIVATE, "Prince", "hello", 2001)
    arrive(frame, feed, chat.PRIVATE, "Kim", "other", 3005)
    frame.begin_reply(True, original)
    frame.refresh_people("id:3005")
    assert "Prince" in frame.pm_label.GetLabel()
    frame.cancel_reply(True)
    assert "Kim" in frame.pm_label.GetLabel()


def test_private_reply_remembers_recipient_and_filters_private_messages(window: Any) -> None:
    frame, host, feed = window
    original = arrive(frame, feed, chat.PRIVATE, "Prince", "private hello", 2001)
    arrive(frame, feed, chat.PRIVATE, "Kim", "other", 3005)
    frame.nb.SetSelection(1)
    frame.begin_reply(True, original)
    frame.refresh_people("id:3005")
    assert frame.peer()["name"] == "Kim"
    sent: list[tuple[int, str, str]] = []
    class Messenger:
        ready = True
        def send(self, id: int, name: str, text: str, *, first: bool) -> None:
            sent.append((id, name, text))
    host.messengers[77] = Messenger()
    frame.pm_text.SetValue("yes")
    frame.send()
    assert sent == [(2001, "Prince", "@Prince yes")]
    frame.filter_message(original)
    frame.refresh_people("id:2001")
    assert frame.pm_lines == [] and len(feed.buffer(chat.PRIVATE)) == 2


def test_keyboard_context_menu_has_reply_and_filter_actions(window: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    frame, _host, feed = window
    arrive(frame, feed, "4", "Prince", "hello")
    labels: list[str] = []
    def popup(menu: wx.Menu) -> bool:
        labels.extend(item.GetItemLabelText() for item in menu.GetMenuItems())
        return True
    monkeypatch.setattr(frame.ch_list, "PopupMenu", popup)
    evt = wx.ContextMenuEvent(wx.EVT_CONTEXT_MENU.typeId)
    evt.SetPosition(wx.DefaultPosition)
    frame.message_menu(evt, False)
    assert labels == ["Reply", "Add to filter list"]


def test_filter_manager_shows_reasons_and_restores_all_matches(window: Any) -> None:
    frame, _host, feed = window
    arrive(frame, feed, "4", "Kim", "hello")
    rules = [filters.make_filter("exact", "hello"), filters.make_filter("contains", "hell")]
    with FilterManager(frame, rules, frame.feed, gui.line_text, frame.save_filters) as manager:
        assert len(manager.hidden) == 1  # All plus Team must not duplicate the same line
        assert "Exact message" in manager.messages.GetString(0) and "Contains text" in manager.messages.GetString(0)
        manager.messages.SetSelection(0)
        manager.restore_selected()
        assert not manager.hidden and all(not r.enabled for r in manager.rules)
        assert all(r.enabled for r in rules)  # Cancel does not change the originals
        manager.list.SetSelection(0)
        manager.toggle()
        assert manager.rules[0].enabled
        manager.delete()
        assert len(manager.rules) == 1


def test_filter_editor_tests_without_saving(window: Any) -> None:
    frame, _host, _feed = window
    with FilterEditor(frame) as editor:
        editor.mode.SetSelection(2)
        editor.text.SetValue("*hello*")
        editor.sample.SetValue("say hello there")
        editor.test()
        assert editor.result.GetLabel() == "Matches"
        editor.sample.SetValue("goodbye")
        editor.test()
        assert editor.result.GetLabel() == "Does not match"
    assert not frame.filters


def test_filter_manager_save_persists_and_closes(window: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    frame, _host, feed = window
    arrive(frame, feed, "4", "Kim", "hello")
    rule = filters.make_filter("exact", "hello")
    with FilterManager(frame, [rule], frame.feed, gui.line_text, frame.save_filters) as manager:
        ended: list[int] = []
        monkeypatch.setattr(manager, "EndModal", ended.append)
        manager.on_save(wx.CommandEvent())
        assert ended == [wx.ID_OK] and not manager.timer.IsRunning()
        assert frame.ch_lines == [] and filters.load(settings.load_app()) == [rule]
