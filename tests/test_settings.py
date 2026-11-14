# pyright: reportPrivateUsage=false
# White-box tests: they check this module's internal helpers (leading-underscore names) directly.
"""Settings and profiles: the defaults fill what a file is missing, unknown keys survive, and a
value of the wrong shape falls back to its default on its own (a copy of the file is kept aside)."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any, NoReturn

import pytest

from unclefarmer import paths, settings
from pathlib import Path


def test_app_settings_defaults_and_unknown_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths, "SETTINGS", str(tmp_path / "settings.json"))
    assert settings.load_app()["language"] == "en"
    with open(paths.SETTINGS, "w", encoding="utf-8") as f:
        json.dump({"language": "ru", "future_key": 7}, f)
    s = settings.load_app()
    assert s["language"] == "ru"
    assert s["future_key"] == 7          # a key this version doesn't know is kept
    assert s["speak"] is True


def test_app_settings_of_the_wrong_shape_are_kept_aside(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths, "SETTINGS", str(tmp_path / "settings.json"))
    with open(paths.SETTINGS, "w", encoding="utf-8") as f:
        json.dump({"speak": "sometimes", "results_every": "soon", "language": "ru"}, f)
    s = settings.load_app()
    assert s["speak"] is True and s["results_every"] == 0
    assert s["language"] == "ru"         # the good values in the same file are kept
    assert os.path.exists(paths.SETTINGS + ".corrupt")
    assert os.path.exists(paths.SETTINGS)


def test_a_profile_of_the_wrong_shape_falls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths, "PROFILES", str(tmp_path))
    with open(tmp_path / "_bad_.json", "w", encoding="utf-8") as f:
        json.dump({"attack_gap": "wide", "chase_range": 25}, f)
    p = settings.load_profile("_bad_")
    assert p["attack_gap"] == settings.PROFILE_DEFAULTS["attack_gap"]
    assert p["chase_range"] == 25
    assert os.path.exists(str(tmp_path / "_bad_.json.corrupt"))


def test_the_defaults_pass_their_own_check() -> None:
    # live 2026-10-22: the pet potion defaults ("auto") failed the check, so every profile was
    # read as broken and the player's settings were replaced by the defaults
    settings.Profile.model_validate(settings.PROFILE_DEFAULTS)
    settings.AppSettings.model_validate(settings.APP_DEFAULTS)


def test_a_profile_with_auto_pet_potions_loads_as_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths, "PROFILES", str(tmp_path))
    with open(tmp_path / "pets.json", "w", encoding="utf-8") as f:
        json.dump({"pet_hp_below": "auto", "pet_hp_cooldown": "auto", "chase_range": 25}, f)
    p = settings.load_profile("pets")
    assert p["chase_range"] == 25 and p["pet_hp_below"] == "auto"
    assert not os.path.exists(str(tmp_path / "pets.json.corrupt"))


def test_same_name_characters_keep_independent_profiles_and_are_named_clearly(tmp_path: Path,
                                                                                monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths, "PROFILES", str(tmp_path))
    first = settings.character_profile("Hero", 1717)
    second = settings.character_profile("Hero", 4242)
    settings.save_profile(first, dict(settings.PROFILE_DEFAULTS, attack_gap=0.2))
    settings.save_profile(second, dict(settings.PROFILE_DEFAULTS, attack_gap=0.8))

    assert settings.load_profile(first)["attack_gap"] == 0.2
    assert settings.load_profile(second)["attack_gap"] == 0.8
    assert settings.profile_display(first) == "Hero - character 1717"
    assert settings.profile_display(second) == "Hero - character 4242"
    assert settings.profiles() == [first, second]


def test_an_identified_character_starts_from_its_legacy_name_only_choices(tmp_path: Path,
                                                                            monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths, "PROFILES", str(tmp_path))
    settings.save_profile("Hero", dict(settings.PROFILE_DEFAULTS, attack_gap=0.65))
    identified = settings.character_profile("Hero", 1717)

    copied = settings.load_profile(identified)
    assert copied["attack_gap"] == 0.65
    settings.save_profile(identified, copied)
    copied["attack_gap"] = 0.9
    settings.save_profile(identified, copied)

    assert settings.load_profile("Hero")["attack_gap"] == 0.65
    assert settings.load_profile(identified)["attack_gap"] == 0.9


def test_a_server_label_is_visible_and_can_adopt_an_existing_id_profile(tmp_path: Path,
                                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths, "PROFILES", str(tmp_path))
    identified = settings.character_profile("Hero", 1717)
    on_s1 = settings.character_profile("Hero", 1717, "S1")
    settings.save_profile(identified, dict(settings.PROFILE_DEFAULTS, attack_gap=0.4))

    assert settings.profile_display(on_s1) == "Hero - S1"
    assert settings.load_profile(on_s1)["attack_gap"] == 0.4
    assert settings.has_profile(on_s1)


def test_a_server_label_can_be_told_from_the_id_only_fallback() -> None:
    fallback = settings.character_profile("Killua", 2905)
    on_s1 = settings.character_profile("Killua", 2905, "S1")
    assert settings.profile_server(fallback) == ""
    assert settings.profile_server(on_s1) == "S1"


def test_a_profile_key_gives_back_the_name_and_a_state_key_that_keeps_the_server() -> None:
    on_s1 = settings.character_profile("Killua", 2905, "S1")
    fallback = settings.character_profile("Killua", 2905)
    assert settings.profile_name(on_s1) == settings.profile_name(fallback) == settings.profile_name("Killua") == "Killua"
    assert settings.profile_name(None) == ""
    assert settings.stable_key(on_s1) == on_s1
    assert settings.stable_key(fallback) == fallback
    assert settings.stable_key("Killua") == "Killua"
    assert settings.profile_id(on_s1) == "2905" and settings.profile_id("Killua") is None


def test_a_game_matches_its_own_profile_and_an_old_name_only_one() -> None:
    on_s1 = settings.character_profile("Killua", 2905, "S1")
    assert settings.is_profile_of(on_s1, settings.character_profile("Killua", 2905))
    assert settings.is_profile_of(on_s1, "Killua")                                    # an old name-only profile
    assert not settings.is_profile_of(on_s1, settings.character_profile("Killua", 77, "S2"))
    assert not settings.is_profile_of(on_s1, settings.character_profile("Killua", 2905, "S2"))
    assert not settings.is_profile_of(None, "Killua")


def test_the_last_run_is_found_under_the_full_key_or_an_unambiguous_old_key() -> None:
    on_s1 = settings.character_profile("Killua", 2905, "S1")
    assert settings.last_run_of({"last_runs": {"Killua": "plan:old"}}, on_s1) == "plan:old"
    app = {"last_runs": {"Killua": "plan:old", settings.character_profile("Killua", 2905): "plan:new"}}
    assert settings.last_run_of(app, on_s1) == "plan:new"
    assert settings.last_run_of(app, None) is None


def test_same_id_on_two_servers_never_shares_a_last_run() -> None:
    on_s1 = settings.character_profile("Killua", 2905, "S1")
    on_s2 = settings.character_profile("Killua", 2905, "S2")
    app = {"last_runs": {settings.stable_key(on_s1): "plan:s1", settings.stable_key(on_s2): "plan:s2"}}
    assert settings.last_run_of(app, on_s1) == "plan:s1"
    assert settings.last_run_of(app, on_s2) == "plan:s2"

    # An old ID-only value cannot be attributed safely once S1 has its own value.
    app = {"last_runs": {settings.stable_key(on_s1): "plan:s1", settings.character_profile("Killua", 2905): "plan:old"}}
    assert settings.last_run_of(app, on_s2) is None


def test_a_connected_character_remembers_its_saved_account_in_its_profile(tmp_path: Path,
                                                                            monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths, "PROFILES", str(tmp_path))
    first = settings.character_profile("First", 1, "S1")
    second = settings.character_profile("Second", 2, "S1")
    assert settings.remember_character_account(first, "account@example.com")
    assert not settings.remember_character_account(first, "account@example.com")
    assert settings.remember_character_account(second, "account@example.com")
    assert settings.automatic_login_profiles() == [(first, "account@example.com"), (second, "account@example.com")]


def test_automatic_login_requires_a_confirmed_character_identity() -> None:
    with pytest.raises(ValueError, match="no game id"):
        settings.remember_character_account("Hero", "account@example.com")


def test_a_locked_settings_file_is_moved_aside_and_the_save_goes_on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "_unreadable", set[str]())
    p = tmp_path / "settings.json"
    p.write_text('{"language": "ru"}', encoding="utf-8")
    real_open: Callable[..., Any] = open

    def deny(file: str | os.PathLike[str], *a: Any, **k: Any) -> Any:
        if os.path.abspath(str(file)) == os.path.abspath(str(p)):
            raise PermissionError("in use")
        return real_open(file, *a, **k)

    monkeypatch.setattr("builtins.open", deny)
    assert settings._read(str(p), settings.APP_DEFAULTS, settings.AppSettings)["language"] == "en"
    assert os.path.exists(str(p) + ".corrupt")
    settings._write(str(p), {"language": "ru"})
    assert json.loads(p.read_text(encoding="utf-8"))["language"] == "ru"


def test_a_file_that_cannot_be_moved_aside_is_never_overwritten(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "_unreadable", set[str]())
    p = tmp_path / "settings.json"
    p.write_text('{"language": "ru"}', encoding="utf-8")
    real_open: Callable[..., Any] = open

    def deny(file: str | os.PathLike[str], *a: Any, **k: Any) -> Any:
        if os.path.abspath(str(file)) == os.path.abspath(str(p)):
            raise PermissionError("in use")
        return real_open(file, *a, **k)

    def locked(*_a: object, **_k: object) -> NoReturn:
        raise PermissionError("locked")

    monkeypatch.setattr("builtins.open", deny)
    monkeypatch.setattr(settings.os, "replace", locked)
    assert settings._read(str(p), settings.APP_DEFAULTS, settings.AppSettings)["language"] == "en"
    assert str(p) in settings._unreadable
    with pytest.raises(OSError, match="close whatever holds it"):
        settings._write(str(p), {"language": "en"})
    assert p.read_text(encoding="utf-8") == '{"language": "ru"}'


def test_every_profile_moves_onto_its_class_attack_range_once() -> None:
    # a range typed in by hand before the class's own distance became the rule goes back to auto;
    # one set after that is the player's and stays
    settings.save_profile("Old", dict(settings.PROFILE_DEFAULTS, attack_range=8.0))
    p = settings.load_profile("Old")
    assert p["attack_range"] == "auto" and p["class_reach"] is True
    p["attack_range"] = 12.0
    settings.save_profile("Old", p)
    assert settings.load_profile("Old")["attack_range"] == 12.0


def test_character_settings_export_round_trips_choices_but_not_game_facts(tmp_path: Path,
                                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths, "PROFILES", str(tmp_path / "profiles"))
    original = dict(settings.PROFILE_DEFAULTS, attack_gap=0.7, bag_rules={"red potion": {"action": "keep", "keep": 4}},
                    scan={"class": "Hunter", "pets": ["Source pet"]}, hearth_home="Source town",
                    login_email="source@example.com", future_key=7)
    settings.save_profile("Source", original)
    export = tmp_path / "source.unclefarmer-profile.json"
    settings.export_profile("Source", str(export))
    source, imported = settings.read_profile_export(str(export))
    assert source == "Source"
    assert imported["attack_gap"] == 0.7
    assert imported["bag_rules"] == {"red potion": {"action": "keep", "keep": 4}}
    assert imported["future_key"] == 7
    assert "scan" not in imported and "hearth_home" not in imported and "login_email" not in imported


def test_character_settings_import_keeps_destination_game_facts(tmp_path: Path,
                                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths, "PROFILES", str(tmp_path / "profiles"))
    settings.save_profile("Destination", dict(settings.PROFILE_DEFAULTS, attack_gap=0.2,
                                                scan={"class": "Priest"}, hearth_home="Destination town"))
    settings.import_profile("Destination", dict(settings.PROFILE_DEFAULTS, attack_gap=0.8, scan={"class": "Hunter"},
                                                 hearth_home="Source town"))
    got = settings.load_profile("Destination")
    assert got["attack_gap"] == 0.8
    assert got["scan"] == {"class": "Priest"}
    assert got["hearth_home"] == "Destination town"


def test_plain_existing_profile_can_be_imported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths, "PROFILES", str(tmp_path / "profiles"))
    source_file = tmp_path / "okyanus.json"
    source_file.write_text(json.dumps(dict(settings.PROFILE_DEFAULTS, attack_gap=0.65,
                                           scan={"class": "Hunter"}, hearth_home="Source town")), encoding="utf-8")
    source, imported = settings.read_profile_export(str(source_file))
    assert source == "okyanus"
    assert imported["attack_gap"] == 0.65
    assert "scan" not in imported and "hearth_home" not in imported


def test_unrelated_plain_json_cannot_be_imported(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"language": "en", "speak": True}), encoding="utf-8")
    with pytest.raises(ValueError, match="doesn't contain character settings"):
        settings.read_profile_export(str(path))


@pytest.mark.parametrize("raw, message", [
    ({}, "doesn't contain character settings"),
    ({"format": settings.PROFILE_EXPORT_FORMAT, "version": 99, "character": "A", "settings": {}}, "unsupported"),
    ({"format": settings.PROFILE_EXPORT_FORMAT, "version": 1, "character": "A", "settings": {"attack_gap": "wide"}},
     "invalid setting"),
])
def test_bad_character_settings_exports_are_rejected(tmp_path: Path, raw: dict[str, Any], message: str) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        settings.read_profile_export(str(path))
