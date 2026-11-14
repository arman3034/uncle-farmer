"""Chat visibility rules never delete feed data and survive settings round-trips."""
from __future__ import annotations

from typing import Any

import pytest

from unclefarmer import chat, chat_filters as filters, settings


@pytest.mark.parametrize(("mode", "pattern", "text", "expected"), [
    ("exact", "hello", "hello", True), ("exact", "hello", "hello there", False),
    ("exact", "hello", "say hello", False), ("exact", " hello ", " hello ", True),
    ("contains", "hello", "say hello there", True), ("contains", "hello", "goodbye", False),
    ("wildcard", "*hello*", "say hello there", True), ("wildcard", "h?llo", "hello", True),
    ("wildcard", "h?llo", "heello", False), ("wildcard", "hello", "hello there", False),
    ("wildcard", "[", "[", True), ("contains", "(broken[regex", "a (broken[regex string", True),
    ("wildcard", "*", "line one\nline two", True),
])
def test_matching_modes(mode: str, pattern: str, text: str, expected: bool) -> None:
    assert filters.make_filter(mode, pattern).matches(text) is expected


@pytest.mark.parametrize("mode", filters.MODES)
def test_case_and_enabled_options(mode: str) -> None:
    assert not filters.make_filter(mode, "HELLO").matches("hello")
    assert filters.make_filter(mode, "HELLO", case_sensitive=False).matches("hello")
    assert not filters.make_filter(mode, "hello", enabled=False).matches("hello")


@pytest.mark.parametrize(("mode", "text"), [("regex", "hi"), ("exact", ""), ("contains", "  "), ("wildcard", "\n")])
def test_invalid_rules(mode: str, text: str) -> None:
    with pytest.raises(ValueError):
        filters.make_filter(mode, text)


def test_add_edit_duplicate_and_restore_multiple_rules() -> None:
    exact = filters.make_filter("exact", "hello")
    contains = filters.make_filter("contains", "hell")
    rules = filters.add(filters.add([], exact), contains)
    assert len(filters.matching(rules, "hello")) == 2
    with pytest.raises(ValueError, match="already exists"):
        filters.add(rules, filters.make_filter("exact", "hello"))
    edited = filters.make_filter("exact", "bye", id=exact.id)
    assert filters.add(rules, edited) == [edited, contains]
    restored = filters.restore(rules, "hello")
    assert not filters.matching(restored, "hello")
    assert len(restored) == 2 and all(not r.enabled for r in restored)
    assert all(r.enabled for r in rules)  # draft leaves original settings alone


def test_persistent_rules_but_memory_only_messages() -> None:
    rule = filters.make_filter("wildcard", "*sale*", case_sensitive=False)
    config = settings.load_app()
    config["chat_filters"] = filters.dump([rule])
    settings.save_app(config)
    reloaded = filters.load(settings.load_app())
    feed = chat.Feed(77)
    feed.add("4", "Prince", "SALE today")
    feed.add("4", "Kim", "hello")
    assert [line["text"] for line in feed.buffer("4") if not filters.matching(reloaded, line["text"])] == ["hello"]
    assert len(feed.buffer("4")) == 2 and len(feed.buffer("all")) == 2
    assert not chat.Feed(77).buffer("all")  # history is not silently persisted
    assert filters.load({"chat_filters": filters.dump(filters.restore(reloaded, "SALE today"))})[0].enabled is False


def test_malformed_settings_are_ignored_and_duplicate_ids_repaired() -> None:
    valid = filters.dump([filters.make_filter("exact", "hi")])[0]
    rows: list[Any] = [None, {}, {"mode": "regex", "text": "("}, {"mode": "exact", "text": 7},
                       {"mode": "exact", "text": "hi", "enabled": "false"}, valid, valid,
                       dict(valid, text="other")]
    rules = filters.load({"chat_filters": rows})
    assert len(rules) == 2 and len({r.id for r in rules}) == 2
    assert filters.load({"chat_filters": "broken"}) == []


@pytest.mark.parametrize(("name", "text", "expected"), [
    ("Prince", "you are right", "@Prince you are right"),
    ("Prince", "@prince @Prince hello", "@Prince hello"),
    ("Kim", "@Kimberly hi", "@Kim @Kimberly hi"),
    (" Prince ", "  hello   there ", "@Prince hello there"),
    ("2Fast4u", "", "@2Fast4u "), ("", "hello", "hello"),
])
def test_reply_prefix(name: str, text: str, expected: str) -> None:
    assert filters.reply_text(name, text) == expected
