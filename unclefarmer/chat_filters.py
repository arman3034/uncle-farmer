"""Chat visibility rules. Only rules are persisted; messages remain in the existing Feed buffers.

Patterns are shell wildcards, not regular expressions. Compiled wildcard matchers are cached,
so incoming messages never recompile a pattern. A reply only decorates text; delivery stays with
the existing channel sender or Messenger.
"""
from __future__ import annotations

import fnmatch
import re
import uuid
from dataclasses import asdict, dataclass, replace
from functools import lru_cache
from typing import Any, cast

from .i18n import N_, _

MODES = ("exact", "contains", "wildcard")
MODE_NAMES = (N_("Exact message"), N_("Contains text"), N_("Wildcard"))


@dataclass(frozen=True)
class Filter:
    id: str
    mode: str
    text: str
    enabled: bool = True
    case_sensitive: bool = True

    def matches(self, text: str) -> bool:
        if not self.enabled:
            return False
        pattern = self.text
        if not self.case_sensitive:
            pattern, text = pattern.casefold(), text.casefold()
        if self.mode == "exact":
            return text == pattern
        if self.mode == "contains":
            return pattern in text
        return wildcard(pattern).fullmatch(text) is not None

    def key(self) -> tuple[str, str, bool]:
        return self.mode, self.text if self.case_sensitive else self.text.casefold(), self.case_sensitive


@lru_cache(maxsize=256)
def wildcard(pattern: str) -> re.Pattern[str]:
    return re.compile(fnmatch.translate(pattern))


def make_filter(mode: str, text: str, enabled: bool = True, case_sensitive: bool = True,
                id: str | None = None) -> Filter:
    if mode not in MODES:
        raise ValueError(_("Choose a filter matching type."))
    if not text.strip():
        raise ValueError(_("Enter filter text or a pattern."))
    return Filter(id or uuid.uuid4().hex, mode, text, enabled, case_sensitive)


def load(s: dict[str, Any]) -> list[Filter]:
    """Ignore malformed rules from hand-edited/older settings without breaking chat."""
    rows = s.get("chat_filters", [])
    if not isinstance(rows, list):
        return []
    out: list[Filter] = []
    keys: set[tuple[str, str, bool]] = set()
    ids: set[str] = set()
    for item in cast(list[Any], rows):
        if not isinstance(item, dict):
            continue
        row = cast(dict[str, Any], item)
        if (not isinstance(row.get("mode"), str) or not isinstance(row.get("text"), str)
                or not isinstance(row.get("enabled", True), bool)
                or not isinstance(row.get("case_sensitive", True), bool)):
            continue
        try:
            rule = make_filter(row["mode"], row["text"], row.get("enabled", True),
                               row.get("case_sensitive", True), row.get("id") if isinstance(row.get("id"), str) else None)
        except ValueError:
            continue
        if rule.key() in keys:
            continue
        if rule.id in ids:
            rule = replace(rule, id=uuid.uuid4().hex)
        keys.add(rule.key())
        ids.add(rule.id)
        out.append(rule)
    return out


def dump(rules: list[Filter]) -> list[dict[str, Any]]:
    return [asdict(rule) for rule in rules]


def add(rules: list[Filter], rule: Filter) -> list[Filter]:
    """Add/edit a rule, rejecting duplicates instead of silently replacing another rule."""
    if any(r.id != rule.id and r.key() == rule.key() for r in rules):
        raise ValueError(_("That filter already exists."))
    return [rule if r.id == rule.id else r for r in rules] if any(r.id == rule.id for r in rules) else [*rules, rule]


def matching(rules: list[Filter], text: str) -> list[Filter]:
    return [rule for rule in rules if rule.matches(text)]


def restore(rules: list[Filter], text: str) -> list[Filter]:
    """Disable every matching rule so a second rule cannot keep the restored message hidden."""
    return [replace(rule, enabled=False) if rule.matches(text) else rule for rule in rules]


def reply_text(name: str, text: str) -> str:
    """Exactly one sender prefix, including when Reply is selected repeatedly or text is pasted."""
    name = name.strip().lstrip("@")
    text = " ".join(text.split())
    if not name:
        return text
    prefix = "@" + name
    while text.casefold() == prefix.casefold() or text.casefold().startswith(prefix.casefold() + " "):
        text = text[len(prefix):].lstrip()
    return prefix + (" " + text if text else " ")
