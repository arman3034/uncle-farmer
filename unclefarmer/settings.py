"""App settings (settings.json) and character profiles (profiles/<character>.json)."""

from __future__ import annotations

import copy
import os
import shutil
from collections.abc import Callable, Collection
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from . import filelock, jsonio as json, paths
from .i18n import _

APP_DEFAULTS: dict[str, Any] = {
    "chat_filters": [],        # visibility only: chat messages themselves are never saved
    "language": "en",
    "language_prompted": False,
    "game_folder": "",
    "speak": True,            # announce important events through NVDA when it is running
    "last_run": "",           # what was selected to run last time
    "last_runs": {},          # character -> what it ran last ("plan:name"), for several games at once
    "game_speech": "running",  # silence the game's own speech: "running" (while a bot runs), "always", "never"
    "fix_voice": True,        # mend the game's voice message player (off: deep, slow voices come back, as the game has it)
    "results_speak": "end",   # speak a run's results: "end" (once, when it stops) or "never"
    "results_every": 0,       # minutes between spoken progress lines while running (0 = never)
    "daily_stop": True,       # every run ends at the daily stop time, before the game's day turns over
    "daily_stop_at": "",      # "HH:MM" on this computer's clock; empty = the drop reset (00:00 GMT) - 10 min
    "after_stop": "nothing",  # when farming stops by itself (never after Stop): nothing | close_game | shutdown
    "shutdown_delay": 60,     # seconds of warning before the computer shuts down (shutdown /s /f /t N)
    "check_updates": True,    # look for a new release on GitHub when the app starts
    "skip_version": "",       # a release the player said no to: not offered again at start
    "update_channel": "master",  # where updates come from: "master" (stable releases) or "dev" (development builds)
    "log_level": "INFO",      # DEBUG | INFO | WARNING | ERROR: what the files in logs/ get
    "log_max_mb": 5,          # start a new log file after this many megabytes (0: never rotate)
    "log_backups": 5,         # old log files kept as name.1 ... name.N
}

# The portable character-settings file is intentionally narrower than a profile on disk.  A scan
# describes the particular character the game last showed us (skills, bag, pets and hotkeys), and
# the hearthstone home is learned from that character's travel.  Copying either to another
# character can make the bot act on facts that are not true there.
PROFILE_EXPORT_FORMAT = "unclefarmer-character-settings"
PROFILE_EXPORT_VERSION = 1
CHARACTER_SPECIFIC_PROFILE_KEYS = frozenset(("scan", "hearth_home", "login_email"))

# One per character. Everything the bot needs to know about how YOU play.
PROFILE_DEFAULTS: dict[str, Any] = {
    "move_keys": {"up": "w", "down": "s", "left": "a", "right": "d"},
    # Target keys pick the nearest target in one direction (the game's "turn" keys); the bot presses
    # the one pointing at the monster it chose, then checks the game selected that monster.
    "target_keys": {"west": "k", "north": "o", "south": "l", "east": ";"},
    "attack_keys": ["j", "y", ".", "h"],
    "attack_gap": 0.35,
    "attack_range": "auto",   # "auto": the base attack's range from the skill texts, less 2 (a number: fixed)
    "attack_style": "auto",   # "auto": melee classes walk to the enemy, ranged ones stand still; "follow"/"stationary"
    "pull_range": 0.0,        # yards past our reach to open fire on a monster that is closing in (0: walk all the way)
    "end_safe": True,         # when a run finishes, go to the nearest map where no monsters spawn
    "fight_timeout": 45.0,
    "no_damage_timeout": 6.0,     # seconds a target may go without losing HP (a kill takes ~2-4 s)
    "no_damage_casts": 3,     # or this many of our own casts landing with no damage
    "press_burst": True,      # press a skill again and again until the game casts it (most casts per cooldown)
    "hp_potion": "auto",      # "auto": the strongest red potion on the hotkeys; or a potion's name
    "hp_key": "auto",         # old profiles: a key typed by hand; "auto" = the slot holding hp_potion
    "hp_below": "auto",       # percent, or "auto": as soon as one potion's worth is missing (engine/potions.py)
    "hp_cooldown": "auto",    # seconds, or "auto": the potion's own cooldown from the game's text
    "mp_use": True,           # MP comes from the character sheet
    "mp_potion": "auto",
    "mp_key": "auto",
    "mp_below": "auto",
    "mp_cooldown": "auto",
    "sheet_key": "",          # key that opens the character sheet (MP, bag load, fusion power); the scan fills it in
    "bag_full_at": 100,       # percent of the bag's load limit that counts as full (100: really full)
    "when_bag_full": "stop",  # after throwing what the rules say: "stop" go somewhere safe and stop; "unload" sell/store and come back; "nothing"
    "stop_on_drop_time": True,  # end the run when the day's drop time is down to drop_keep_minutes
    "drop_keep_minutes": 0,   # drop time to leave unused (minutes)
    "drop_tail_seconds": 300,  # drop time keeps running this long after we reach safety
    "gem_keep_arnebia": 20000,  # making gems never spends arnebia below this (fares and potions)
    "bag_rules": {},          # the bag manager: item (lower case) -> {"action": keep|store|sell|throw, "keep": n}
    "only_this_run": True,    # items without a rule of the player's: touch only what this run picked up
    "discard_key": "shift+delete",  # the game's "discard item" key
    "sheet_every": 600,       # seconds between character sheet readings (bag load, drop time); sooner near a full bag
    "vitals_key": "",         # the game's "own HP" key (W_SELF_HP, R): the server answers HP and MP, no window
    "points_key": "",         # the game's "accumulation points" key (W_SELF_LJ, T): rage, marks or
                              # combos, then fusion power and the pet's amiability
    "points_every": 1.5,      # seconds between those readings in fights, for classes whose skills spend them
    "mp_check_every": 10,     # seconds between MP readings with that key when MP is near the potion mark (30 otherwise)
    "close_popups": True,     # close windows the game opens on its own (team invites...) with Escape
    "end_with_hearthstone": True,   # end a run with the hearthstone when one is at hand, else walk
    # Character settings, Triggers (engine/triggers.py): Tools jobs run by themselves before a farming
    # run starts / after one finished. Every job has a tick per stage, the two independent.
    "sell_shards_before_farming": False,  # the game menu's Sell shards now, before a farming run starts
    "clean_bag_before_farming": False,    # the game menu's Clean the bag now, before a farming run starts
    "update_shard_prices_before_farming": False,   # the game menu's Update shard prices, before a farming run starts
    "gather_before_farming": False,       # Tools, Gathering (as set there), before a farming run starts
    "store_items_before_farming": False,  # the game menu's Store items now, before a farming run starts
    "restock_before_farming": False,      # the game menu's Restock now, before a farming run starts
    "sell_shards_after_farming": False,   # the game menu's Sell shards now, by itself after a farming run that finished
    "clean_bag_after_farming": False,     # the game menu's Clean the bag now, by itself after a farming run that finished
    "update_shard_prices_after_farming": False,    # the game menu's Update shard prices, after a farming run that finished
    "gather_after_farming": False,        # Tools, Gathering (as set there), after a farming run that finished
    "store_items_after_farming": False,   # the game menu's Store items now, after a farming run that finished
    "restock_after_farming": False,       # the game menu's Restock now, after a farming run that finished
    "lose_xp_before_farming": False,      # Tools, XP loser (as set there), before a farming run starts
    "lose_xp_after_farming": False,       # Tools, XP loser (as set there), after a farming run that finished
    "hearthstone_item": "Hearthstone",   # used from the bag; see bag keys below
    "hearthstone_key": "",    # or a hotkey instead of the bag (empty = use the bag)
    "bag_up": "up", "bag_down": "down", "bag_left": "left", "bag_right": "right",
    "use_key": "rctrl",       # uses the item under the cursor
    "category_key": "lctrl+alt+down",   # next category in a panel (the bag needs category 0)
    "panic_below": 25,        # percent: with stop_on_panic, stop if HP stays under this...
    "stop_on_panic": False,   # stop the run when HP stays under panic_below (off: keep fighting; deaths are handled)
    "respawn": "city",        # after dying: back to the city; "map" exists but isn't offered
    "use_resurrection_crystal": False,  # respawn with Resurrection Crystals (bag items: only if allowed)
    "stop_on_deaths": True,   # stop the run after dying max_deaths times (off: farm on, however often)
    "max_deaths": 3,          # stop the run after dying this many times (0 also means never)
    "panic_after": 10.0,      # ...for this many seconds
    "stop_when_out_of_potions": True,  # the last red (or blue) potion is gone: end the run (restocked ones excepted)
    "walk_diagonal": True,    # walk on the slant across open ground (both direction keys held at once)
    "chase_range": 40,        # on a patrol loop: chase monsters at most this many walking steps away
    "boss_distance": 40,      # steps kept from a boss in sight (engine/bosses.py); 0: no keeping away
    "rest_below": 60,         # HP % under which we rest (drinking) before taking on the next monster
    "rest_until": 90,         # HP % a rest waits for
    "repair_with": "toolbox",  # repair the gear when the game warns: "toolbox" (from the bag) or "off"
    "stop_when_gear_broken": True,  # gear broke and nothing can repair it: go somewhere safe and stop
    "stuck_limit": 6,         # stop after this many stuck walks in a row
    "fight_back": True,       # when hit while walking or travelling, fight back, then go on
    "nearest_monster": True,  # always fight the nearest monster (off: melee picks a calm one beside a pack)
    "fight_locked": False,    # fight monsters another player (or their pet) is already killing, while a hit can still land in time (off: leave the close calls too)
    "shoot_while_walking": False,  # farming: a character that fights from afar shoots what comes into reach on its walk to a monster (dungeons have their own setting)
    "corpse_skill": False,    # farming: the learned Draw Blood, Skinning or Cut Flesh on our kills (engine/corpses.py)
    "corpse_keep_vitality": 0,  # ... until Vitality is down to this (0: until it runs out)
    "xp_card_name": "",       # farming: keep this experience card running, that kind only ("": none) (engine/xpcard.py)
    "xp_card_pause": False,   # ... and pause it while a farming run is away from the monsters
    "skills_by_slot": True,   # press attack skills through the game's own key method (agent 45), not the keyboard
    "set_modes": True,        # before farming, set the game's modes below
    "pk_key": "b",            # cycles the PK mode
    "pk_mode": 1,             # PK_MODES index: pacifist mode with counterattack
    "target_mode_key": "v",   # cycles who the target key picks
    "target_mode": 2,         # TARGET_MODES index: enemies
    # Talking to NPCs (cable cars, airships, teleport circles). Inside a dialog the game moves the
    # cursor with the walking keys (W/S rows, A/D columns), Enter chooses, Esc closes.
    "enter_key": "enter",
    "esc_key": "esc",
    "prefer_walking": False,  # True: walk whenever the maps connect on foot (off: shortest way, cable cars and airships included)
    "use_transport": True,    # cable cars and teleport circles when travelling
    "speed_beast": "auto",    # fusion beast to travel on: "auto" the fastest Swift one, "none", or its name
    "fight_beast": "none",    # fusion beast to fight as: "none" (most players, for long farms), "auto", or its name
    "pets": [],               # pets in order, [{"name", "use"}]: the first ticked one that is ready comes out
    "pet_hp_below": "auto",   # pet HP % under which a pet red potion is used ("auto": as soon as one potion's worth is missing)
    "pet_mp_below": "auto",   # the same for the pet's MP and a pet blue potion
    "pet_hp_cooldown": "auto",  # seconds between pet red potions at least ("auto": the potion's own cooldown)
    "pet_mp_cooldown": "auto",
    "pet_hp_key": "auto",     # "auto": the hotkey slot holding a Pet ... Red Potion, else the bag
    "pet_food": "Pet Rice Roll",  # fed when the pet's amiability is low (the game: "Increase 30% Amiability")
    "pet_food_below": 70,     # amiability under which the pet is fed (0: never)
    "pet_vitals_key": "",     # the game's pet HP key (W_PET_HP, Shift+R): the server answers the pet's HP and MP
    "pet_recall_at_end": False,  # put the pet away when a run finishes
    "pet_heal_with_skill": True,  # a class with a quick heal (Priest, Sorceress) heals the pet with it
    "pet_heal_below": 85,     # the pet's HP (%) under which it is healed with the skill
    "team_heal": True,        # while following, a class with a quick heal heals teammates with it
    "team_heal_below": 70,    # a teammate's HP (%) under which they are healed
    "smart_skills": True,     # pick skills from the game's own skill list and texts (off: cycle attack_keys)
    # The player's say over each skill on the keys, by name (engine/combat.py SKILL_USES):
    #   auto       the bot decides when (the default)
    #   never      never pressed
    #   emergency  only when HP is low (under emergency_below or defend_below)
    #   ready      pressed whenever it is ready in a fight, before the bot's own choice
    "skill_use": {},
    "skill_use_others": "auto",   # skills skill_use doesn't name (learned or put on a key later): auto or never
    "defend_below": 40,       # HP % under which the class's defensive skill is used
    "heal_with_skill": True,  # a class with its own quick heal (Healing Wave, Heal) heals with it
    "heal_below": 85,         # HP % under which that heal is cast, in fights and between them
    "heal_potion_below": 50,  # with that heal, red potions only under this HP %
    "fill_empty_keys": True,  # put the heals, shields, buffs, dispels and items the bot uses on EMPTY keys
    "fill_empty_phrases": True,  # put useful quick phrase codes (/6 /5 /4, /7 for healers) on EMPTY phrase slots
    "teleport_key": "shift+p",   # the game's "teleport to the team leader" key (W_AMOVE): same map, 50 s cooldown
    "emergency_below": 50,    # HP % that (or a pack on us under 75%) calls for shields and big heals
    "use_buffs": True,        # keep the class's long buffs up; short ones at the start of hard fights
    "use_dispel": True,       # remove debuffs from ourselves with the class's dispel
    "use_combos": True,       # skill combos from the activated talents and the skill texts (engine/combos.py)
    "use_airships": True,     # airships too (they may cost Arnebia)
    "vip": False,             # VIPs ride cable cars and airships free (the menu's free entry)
    "use_travel_items": False, # teleport stones / hearthstone from the bag: only when the player allows (off: never)
    "use_teleport_skills": True,  # a Mage's / Elf's teleport skill (mana only, no item): when it saves walking
    "hearth_home": "",        # the square the hearthstone takes this character to (learned)
    "action_menu_key": "lctrl+enter",   # the game's Action menu (W_LOCAL_OPTION): has "leave" in instances
    # Restock: [{"item": "Large Red Potion", "min": 20, "stock": 200, "storage_first": true, "buy": true}]
    # A run starts by filling every item to its stock; while farming, a trip is made when one drops
    # below its min (and then everything short is topped up). Storehouse first (free), then the shop.
    "restock": [],
    "restock_check_every": 30,   # seconds between bag checks while farming
    "login_email": "",          # the saved Mist World account this character was last seen on
}

# The shape of each file, checked by Pydantic when it is read (see _read below). A value of the
# wrong type - a hand-edited file, or one an older version wrote differently - falls back to its
# default on its own; the rest of the file is kept, and a copy of it is kept aside. Unknown keys are kept, so the markers the
# app adds itself (_upgrade) and any key a newer version wrote are never lost. On many fields "auto"
# and a number mean the same, hence Auto.
Auto = str | float | int


class AppSettings(BaseModel):
    """settings.json."""
    model_config = ConfigDict(extra="allow")

    chat_filters: list[dict[str, Any]] = APP_DEFAULTS["chat_filters"]

    language: str = APP_DEFAULTS["language"]
    language_prompted: bool = APP_DEFAULTS["language_prompted"]
    game_folder: str = APP_DEFAULTS["game_folder"]
    speak: bool = APP_DEFAULTS["speak"]
    last_run: str = APP_DEFAULTS["last_run"]
    last_runs: dict[str, str] = APP_DEFAULTS["last_runs"]
    game_speech: str = APP_DEFAULTS["game_speech"]
    fix_voice: bool = APP_DEFAULTS["fix_voice"]
    results_speak: str = APP_DEFAULTS["results_speak"]
    results_every: int = APP_DEFAULTS["results_every"]
    daily_stop: bool = APP_DEFAULTS["daily_stop"]
    daily_stop_at: str = APP_DEFAULTS["daily_stop_at"]
    after_stop: str = APP_DEFAULTS["after_stop"]
    shutdown_delay: int = APP_DEFAULTS["shutdown_delay"]
    check_updates: bool = APP_DEFAULTS["check_updates"]
    skip_version: str = APP_DEFAULTS["skip_version"]
    update_channel: Literal["master", "dev"] = APP_DEFAULTS["update_channel"]
    log_level: str = APP_DEFAULTS["log_level"]
    log_max_mb: int = APP_DEFAULTS["log_max_mb"]
    log_backups: int = APP_DEFAULTS["log_backups"]


class Profile(BaseModel):
    """profiles/<character>.json."""
    model_config = ConfigDict(extra="allow")

    move_keys: dict[str, str] = PROFILE_DEFAULTS["move_keys"]
    target_keys: dict[str, str] = PROFILE_DEFAULTS["target_keys"]
    attack_keys: list[str] = PROFILE_DEFAULTS["attack_keys"]
    attack_gap: float = PROFILE_DEFAULTS["attack_gap"]
    attack_range: Auto = PROFILE_DEFAULTS["attack_range"]
    attack_style: str = PROFILE_DEFAULTS["attack_style"]
    pull_range: float = PROFILE_DEFAULTS["pull_range"]
    end_safe: bool = PROFILE_DEFAULTS["end_safe"]
    fight_timeout: float = PROFILE_DEFAULTS["fight_timeout"]
    no_damage_timeout: float | None = PROFILE_DEFAULTS["no_damage_timeout"]
    no_damage_casts: int = PROFILE_DEFAULTS["no_damage_casts"]
    press_burst: bool = PROFILE_DEFAULTS["press_burst"]
    hp_potion: str = PROFILE_DEFAULTS["hp_potion"]
    hp_key: str = PROFILE_DEFAULTS["hp_key"]
    hp_below: Auto | None = PROFILE_DEFAULTS["hp_below"]
    hp_cooldown: Auto | None = PROFILE_DEFAULTS["hp_cooldown"]
    mp_use: bool = PROFILE_DEFAULTS["mp_use"]
    mp_potion: str = PROFILE_DEFAULTS["mp_potion"]
    mp_key: str = PROFILE_DEFAULTS["mp_key"]
    mp_below: Auto | None = PROFILE_DEFAULTS["mp_below"]
    mp_cooldown: Auto | None = PROFILE_DEFAULTS["mp_cooldown"]
    sheet_key: str = PROFILE_DEFAULTS["sheet_key"]
    bag_full_at: int | None = PROFILE_DEFAULTS["bag_full_at"]
    when_bag_full: str = PROFILE_DEFAULTS["when_bag_full"]
    stop_on_drop_time: bool = PROFILE_DEFAULTS["stop_on_drop_time"]
    drop_keep_minutes: int = PROFILE_DEFAULTS["drop_keep_minutes"]
    drop_tail_seconds: int = PROFILE_DEFAULTS["drop_tail_seconds"]
    gem_keep_arnebia: int = PROFILE_DEFAULTS["gem_keep_arnebia"]
    bag_rules: dict[str, Any] = PROFILE_DEFAULTS["bag_rules"]
    only_this_run: bool = PROFILE_DEFAULTS["only_this_run"]
    discard_key: str = PROFILE_DEFAULTS["discard_key"]
    sheet_every: int | None = PROFILE_DEFAULTS["sheet_every"]
    vitals_key: str = PROFILE_DEFAULTS["vitals_key"]
    points_key: str = PROFILE_DEFAULTS["points_key"]
    points_every: float = PROFILE_DEFAULTS["points_every"]
    mp_check_every: int = PROFILE_DEFAULTS["mp_check_every"]
    close_popups: bool = PROFILE_DEFAULTS["close_popups"]
    end_with_hearthstone: bool = PROFILE_DEFAULTS["end_with_hearthstone"]
    sell_shards_before_farming: bool = PROFILE_DEFAULTS["sell_shards_before_farming"]
    clean_bag_before_farming: bool = PROFILE_DEFAULTS["clean_bag_before_farming"]
    update_shard_prices_before_farming: bool = PROFILE_DEFAULTS["update_shard_prices_before_farming"]
    gather_before_farming: bool = PROFILE_DEFAULTS["gather_before_farming"]
    store_items_before_farming: bool = PROFILE_DEFAULTS["store_items_before_farming"]
    restock_before_farming: bool = PROFILE_DEFAULTS["restock_before_farming"]
    sell_shards_after_farming: bool = PROFILE_DEFAULTS["sell_shards_after_farming"]
    clean_bag_after_farming: bool = PROFILE_DEFAULTS["clean_bag_after_farming"]
    update_shard_prices_after_farming: bool = PROFILE_DEFAULTS["update_shard_prices_after_farming"]
    gather_after_farming: bool = PROFILE_DEFAULTS["gather_after_farming"]
    store_items_after_farming: bool = PROFILE_DEFAULTS["store_items_after_farming"]
    restock_after_farming: bool = PROFILE_DEFAULTS["restock_after_farming"]
    lose_xp_before_farming: bool = PROFILE_DEFAULTS["lose_xp_before_farming"]
    lose_xp_after_farming: bool = PROFILE_DEFAULTS["lose_xp_after_farming"]
    hearthstone_item: str = PROFILE_DEFAULTS["hearthstone_item"]
    hearthstone_key: str = PROFILE_DEFAULTS["hearthstone_key"]
    bag_up: str = PROFILE_DEFAULTS["bag_up"]
    bag_down: str = PROFILE_DEFAULTS["bag_down"]
    bag_left: str = PROFILE_DEFAULTS["bag_left"]
    bag_right: str = PROFILE_DEFAULTS["bag_right"]
    use_key: str = PROFILE_DEFAULTS["use_key"]
    category_key: str = PROFILE_DEFAULTS["category_key"]
    panic_below: int = PROFILE_DEFAULTS["panic_below"]
    stop_on_panic: bool = PROFILE_DEFAULTS["stop_on_panic"]
    respawn: str = PROFILE_DEFAULTS["respawn"]
    use_resurrection_crystal: bool = PROFILE_DEFAULTS["use_resurrection_crystal"]
    stop_on_deaths: bool = PROFILE_DEFAULTS["stop_on_deaths"]
    max_deaths: int = PROFILE_DEFAULTS["max_deaths"]
    panic_after: float = PROFILE_DEFAULTS["panic_after"]
    stop_when_out_of_potions: bool = PROFILE_DEFAULTS["stop_when_out_of_potions"]
    walk_diagonal: bool = PROFILE_DEFAULTS["walk_diagonal"]
    chase_range: int = PROFILE_DEFAULTS["chase_range"]
    rest_below: int = PROFILE_DEFAULTS["rest_below"]
    rest_until: int = PROFILE_DEFAULTS["rest_until"]
    repair_with: str = PROFILE_DEFAULTS["repair_with"]
    stop_when_gear_broken: bool = PROFILE_DEFAULTS["stop_when_gear_broken"]
    stuck_limit: int = PROFILE_DEFAULTS["stuck_limit"]
    fight_back: bool = PROFILE_DEFAULTS["fight_back"]
    nearest_monster: bool = PROFILE_DEFAULTS["nearest_monster"]
    fight_locked: bool = PROFILE_DEFAULTS["fight_locked"]
    shoot_while_walking: bool = PROFILE_DEFAULTS["shoot_while_walking"]
    corpse_skill: bool = PROFILE_DEFAULTS["corpse_skill"]
    corpse_keep_vitality: float = PROFILE_DEFAULTS["corpse_keep_vitality"]
    xp_card_name: str = PROFILE_DEFAULTS["xp_card_name"]
    xp_card_pause: bool = PROFILE_DEFAULTS["xp_card_pause"]
    skills_by_slot: bool = PROFILE_DEFAULTS["skills_by_slot"]
    set_modes: bool = PROFILE_DEFAULTS["set_modes"]
    pk_key: str = PROFILE_DEFAULTS["pk_key"]
    pk_mode: int = PROFILE_DEFAULTS["pk_mode"]
    target_mode_key: str = PROFILE_DEFAULTS["target_mode_key"]
    target_mode: int = PROFILE_DEFAULTS["target_mode"]
    enter_key: str = PROFILE_DEFAULTS["enter_key"]
    esc_key: str = PROFILE_DEFAULTS["esc_key"]
    prefer_walking: bool = PROFILE_DEFAULTS["prefer_walking"]
    use_transport: bool = PROFILE_DEFAULTS["use_transport"]
    speed_beast: str | bool = PROFILE_DEFAULTS["speed_beast"]
    fight_beast: str | bool = PROFILE_DEFAULTS["fight_beast"]
    pets: list[Any] = PROFILE_DEFAULTS["pets"]
    pet_hp_below: Auto | None = PROFILE_DEFAULTS["pet_hp_below"]
    pet_hp_cooldown: Auto | None = PROFILE_DEFAULTS["pet_hp_cooldown"]
    pet_hp_key: str = PROFILE_DEFAULTS["pet_hp_key"]
    pet_recall_at_end: bool = PROFILE_DEFAULTS["pet_recall_at_end"]
    pet_heal_with_skill: bool = PROFILE_DEFAULTS["pet_heal_with_skill"]
    pet_heal_below: Auto = PROFILE_DEFAULTS["pet_heal_below"]
    team_heal: bool = PROFILE_DEFAULTS["team_heal"]
    team_heal_below: Auto = PROFILE_DEFAULTS["team_heal_below"]
    smart_skills: bool = PROFILE_DEFAULTS["smart_skills"]
    skill_use: dict[str, str] = PROFILE_DEFAULTS["skill_use"]
    skill_use_others: str = PROFILE_DEFAULTS["skill_use_others"]
    defend_below: int = PROFILE_DEFAULTS["defend_below"]
    heal_with_skill: bool = PROFILE_DEFAULTS["heal_with_skill"]
    heal_below: int = PROFILE_DEFAULTS["heal_below"]
    heal_potion_below: int = PROFILE_DEFAULTS["heal_potion_below"]
    fill_empty_keys: bool = PROFILE_DEFAULTS["fill_empty_keys"]
    fill_empty_phrases: bool = PROFILE_DEFAULTS["fill_empty_phrases"]
    teleport_key: str = PROFILE_DEFAULTS["teleport_key"]
    emergency_below: int = PROFILE_DEFAULTS["emergency_below"]
    use_buffs: bool = PROFILE_DEFAULTS["use_buffs"]
    use_dispel: bool = PROFILE_DEFAULTS["use_dispel"]
    use_combos: bool = PROFILE_DEFAULTS["use_combos"]
    use_airships: bool = PROFILE_DEFAULTS["use_airships"]
    vip: bool = PROFILE_DEFAULTS["vip"]
    use_travel_items: bool = PROFILE_DEFAULTS["use_travel_items"]
    use_teleport_skills: bool = PROFILE_DEFAULTS["use_teleport_skills"]
    hearth_home: str = PROFILE_DEFAULTS["hearth_home"]
    action_menu_key: str = PROFILE_DEFAULTS["action_menu_key"]
    restock: list[Any] = PROFILE_DEFAULTS["restock"]
    restock_check_every: int = PROFILE_DEFAULTS["restock_check_every"]
    login_email: str = PROFILE_DEFAULTS["login_email"]


# The game's own order (game.i.l(int) and k(int), read 2026-10-01). The bot reads the current value
# from the game and presses the key until it matches.
PK_MODES = ["pacifist mode", "pacifist mode with counterattack", "Moral Mode", "gang mode", "team mode",
            "all mode"]
TARGET_MODES = ["all", "own side", "enemies", "NPCs"]


_unreadable: set[str] = set()          # files that exist but could not be read: never overwrite them blindly


def _aside_name(path: str) -> str:
    """<name>.corrupt, or .corrupt.2, .corrupt.3 ... when that is taken: a second broken file never
    overwrites the copy of the first."""
    name = path + ".corrupt"
    n = 1
    while os.path.exists(name):
        n += 1
        name = "%s.corrupt.%d" % (path, n)
    return name


def _keep_aside(path: str) -> bool:
    """Move a file we could not read to <name>.corrupt, when the file system lets us."""
    try:
        filelock.move(path, _aside_name(path))
        return True
    except OSError:
        return False


def _copy_aside(path: str) -> None:
    """A copy of a file with values we could not use, as <name>.corrupt; the file itself stays."""
    try:
        shutil.copyfile(path, _aside_name(path))
    except OSError:
        pass


def _read(path: str, defaults: dict[str, Any], model: type[BaseModel]) -> dict[str, Any]:
    if os.path.exists(path):
        try:
            # utf-8-sig: a file saved by Notepad starts with a byte order mark, which the JSON
            # reader takes for broken JSON - the player's settings went to .corrupt and defaults
            with open(path, encoding="utf-8-sig") as f:
                raw = json.load(f)
            if not json.is_object(raw):
                raise ValueError("not a JSON object")
            # Pydantic checks the shape; the defaults fill whatever the file doesn't carry.
            merged = {**copy.deepcopy(defaults), **raw}
            try:
                data = model.model_validate(merged).model_dump()
            except ValidationError as e:
                # One value of the wrong type cost the player the whole profile (live 2026-10-22: two
                # pet settings typed as numbers held "auto", so every profile fell back to the
                # defaults). Only those values go back to their defaults; a copy keeps the originals.
                _copy_aside(path)
                for err in e.errors():
                    if err["loc"]:
                        key = str(err["loc"][0])          # a top-level field name
                        merged[key] = copy.deepcopy(defaults[key]) if key in defaults else None
                data = model.model_validate(merged).model_dump()
            _unreadable.discard(path)
            return data
        except ValueError:
            # Unreadable: the defaults are used, and the next save would overwrite the player's
            # file with them. Keep the broken one aside so nothing is lost for good.
            _keep_aside(path)
        except OSError:
            # There but unreadable right now (another program holding it): defaults for this
            # reading, and _write will not save over it until it can be moved aside.
            if not _keep_aside(path):
                _unreadable.add(path)
    return copy.deepcopy(defaults)


def _write(path: str, data: dict[str, Any]) -> None:
    if path in _unreadable:
        if not _keep_aside(path):
            raise OSError("can't read or move aside %s - close whatever holds it and try again" % path)
        _unreadable.discard(path)
    json.save(path, data, indent=2)


def load_app() -> dict[str, Any]:
    # An existing installation predates the first-launch prompt: keep its preferences.
    defaults = {**APP_DEFAULTS, "language_prompted": os.path.exists(paths.SETTINGS)}
    return _read(paths.SETTINGS, defaults, AppSettings)


def save_app(data: dict[str, Any]) -> None:
    _write(paths.SETTINGS, data)


_PROFILE_ID_SEPARATOR = "\x1f"
_PROFILE_ID_KEY = "_unclefarmer_character_identity"


def character_profile(name: str, entity_id: object, server: str = "") -> str:
    """An internal, per-character profile key from a game reading.

    Names are not unique: the same player name can exist on more than one server.  The game gives
    every logged-in character an entity id, which distinguishes those characters without making a
    network address part of the player's settings.  Keep the separator out of the visible name so
    callers can still pass a legacy, name-only profile unchanged.
    """
    if not name or entity_id in (None, ""):
        return name
    return name + _PROFILE_ID_SEPARATOR + server + _PROFILE_ID_SEPARATOR + str(entity_id) if server \
        else name + _PROFILE_ID_SEPARATOR + str(entity_id)


def profile_display(character: str) -> str:
    """The unambiguous, screen-reader-friendly label for a profile key."""
    name, server, entity_id = _profile_parts(character)
    if server:
        return _("{name} - {server}", name=name, server=server)
    return _("{name} - character {id}", name=name, id=entity_id) if entity_id else name


def _profile_parts(character: str) -> tuple[str, str | None, str | None]:
    name, separator, rest = character.partition(_PROFILE_ID_SEPARATOR)
    if not separator:
        return name, None, None
    server, separator, entity_id = rest.partition(_PROFILE_ID_SEPARATOR)
    return (name, server, entity_id) if separator else (name, None, server)


def same_character(first: str, second: str) -> bool:
    """Whether two profile keys name the same game character.

    An old, ID-only key can still match either server while it is being upgraded.  Once both keys
    name a server, though, the server is part of the identity: entity IDs are not known to be
    global across Mist World's servers.
    """
    first_name, first_server, first_id = _profile_parts(first)
    second_name, second_server, second_id = _profile_parts(second)
    return bool(first_id and first_name == second_name and first_id == second_id
                and (not first_server or not second_server or first_server == second_server))


def is_character_profile(character: str) -> bool:
    return _profile_parts(character)[2] is not None


def profile_server(character: str) -> str:
    """The known player-facing server label, or empty while only the entity ID is available."""
    return _profile_parts(character)[1] or ""


def profile_name(character: str | None) -> str:
    """The character's name as the game and the player write it, from a profile key or a name."""
    return _profile_parts(character or "")[0]


def profile_id(character: str | None) -> str | None:
    """The game's id for the character in a profile key; None for a name-only key."""
    return _profile_parts(character or "")[2]


def stable_key(character: str | None) -> str:
    """The durable key for character-scoped application state.

    Keep every confirmed part of the live identity.  In particular, S1 and S2 must not share a
    last-run choice merely because their character IDs happen to agree.  An ID-only key remains
    the best available fallback for an older agent that cannot report its server.
    """
    name, server, entity_id = _profile_parts(character or "")
    return character_profile(name, entity_id, server or "") if entity_id else name


def is_profile_of(game: str | None, profile: str | None) -> bool:
    """Whether a game's profile key is this profile's character. A name-only (old) profile still
    matches its name, as it did before characters had their own keys."""
    if not game or not profile:
        return False
    if game == profile or same_character(game, profile):
        return True
    return not is_character_profile(profile) and profile_name(game) == profile


def last_run_of(app: dict[str, Any], character: str | None) -> str | None:
    """What a character ran last ("plan:name"), without borrowing another server's state.

    Older name-only and ID-only entries are adopted as a one-way compatibility fallback.  They
    stop being safe to adopt as soon as a different confirmed server identity with the same name
    and ID has its own entry.
    """
    if not character:
        return None
    runs: dict[str, str] = app.get("last_runs") or {}
    key = stable_key(character)
    if key in runs:
        return runs[key]
    name, _server, entity_id = _profile_parts(character)
    if entity_id:
        other_server = any(profile_name(candidate) == name and profile_id(candidate) == entity_id
                           and profile_server(candidate) and candidate != key for candidate in runs)
        if not other_server:
            legacy = character_profile(name, entity_id)
            if legacy in runs:
                return runs[legacy]
    other_character = any(profile_name(candidate) == name and profile_id(candidate)
                          and candidate != key for candidate in runs)
    return None if other_character else runs.get(name)


def remember_character_account(character: str, email: str) -> bool:
    """Record the saved account a live character belongs to, returning whether it changed."""
    key = stable_key(character)
    if not is_character_profile(key):
        raise ValueError("the character has no game id")
    profile = load_profile(key)
    changed = profile.get("login_email") != email
    if changed:
        profile["login_email"] = email
        save_profile(key, profile)
    return changed


def automatic_login_profiles() -> list[tuple[str, str]]:
    """Identified profiles with a saved account learned from a live connected character."""
    choices: list[tuple[str, str]] = []
    for character in profiles():
        email = load_profile(character).get("login_email")
        if is_character_profile(character) and isinstance(email, str) and email:
            choices.append((character, email))
    return sorted(choices, key=lambda choice: profile_display(choice[0]).casefold())


def profile_path(character: str) -> str:
    name, server, entity_id = _profile_parts(character)
    stem = paths.safe_name(name)
    if entity_id:
        if server:
            stem += "--" + paths.safe_name(server)
        stem += "--" + paths.safe_name(entity_id)
    return os.path.join(paths.PROFILES, stem + ".json")


def profiles() -> list[str]:
    """Known profile keys, including the identity stored by newer profile files.

    Old name-only files remain selectable.  A newer file carries its key inside the JSON because
    filenames are deliberately safe and cannot retain the private separator used by the key.
    """
    found: list[str] = []
    for filename in os.listdir(paths.PROFILES):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(paths.PROFILES, filename)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            identity: object = data.get(_PROFILE_ID_KEY) if json.is_object(data) else None
        except (OSError, ValueError):
            identity = None
        found.append(identity if isinstance(identity, str) and identity else filename[:-5])
    return sorted(found, key=lambda value: profile_display(value).casefold())


def load_profile(character: str) -> dict[str, Any]:
    """The character's profile; a new one from the defaults if there is none yet."""
    path = profile_path(character)
    # On first use of an identified character, retain its old name-only choices.  The first save
    # writes a separate file, so the two same-name characters become independent without deleting
    # or changing the legacy file.
    name, server, entity_id = _profile_parts(character)
    if entity_id and not os.path.exists(path):
        if server:
            identified = profile_path(character_profile(name, entity_id))
            if os.path.exists(identified):
                return _upgrade(_read(identified, PROFILE_DEFAULTS, Profile))
        legacy = profile_path(name)
        if os.path.exists(legacy):
            return _upgrade(_read(legacy, PROFILE_DEFAULTS, Profile))
    return _upgrade(_read(path, PROFILE_DEFAULTS, Profile))


def _upgrade_xp_card(p: dict[str, Any]) -> None:
    """2026-11-12: the on/off "xp_card" (it used the strongest card in the bag) became the card the
    player chooses (xp_card_name). The old tick named no card, so it carries no choice over."""
    p.pop("xp_card", None)


def _upgrade(p: dict[str, Any]) -> dict[str, Any]:
    """A profile saved by an older version, brought up to date: each step below once, in order."""
    for step in UPGRADES:
        step(p)
    return p


def _upgrade_choices(p: dict[str, Any]) -> None:
    """Profiles saved before 2026-10-04's choices: on/off beasts, a single pet name, shard lists."""
    shards: list[str] | None = p.pop("sell_shards", None)
    if shards:
        rules: dict[str, Any] = p.setdefault("bag_rules", {})
        for n in shards:
            rules.setdefault(n.lower(), {"action": "sell", "keep": 0})
    for k in ("sell_shards_on_trip", "sell_loot", "store_loot"):
        p.pop(k, None)
    if isinstance(p.get("fight_beast"), bool):
        p["fight_beast"] = "auto" if p["fight_beast"] else "none"
    if p.pop("fusion_beasts", True) is False:
        p["speed_beast"] = "none"
    old = p.pop("pet", None)
    if old and not p.get("pets"):
        p["pets"] = [] if old == "auto" else [{"name": old, "use": True}]
        p["pets_any"] = old == "auto"
    for k in ("hp_key", "mp_key"):
        if p.get(k) in ("num1", "num2"):      # the old default pressed the keypad, which does nothing
            p[k] = "auto"
    if isinstance(p.get("attack_range"), (int, float)) and p["attack_range"] == 5.0:
        p["attack_range"] = "auto"


def _upgrade_shard_lists(p: dict[str, Any]) -> None:
    """2026-10-06: the player sorts shards into throw / keep / sell lists. Before, a shard with no
    rule was thrown when the Shard Market paid under 1000. A profile saved before gets that as its
    lists once, so nothing changes until the player moves a shard; a new profile starts with all
    kept. The "Make into gems" list went out of the bag (gem making is the Gem Maker's job): shards
    that were in it stay in the bag."""
    if not p.get("shard_lists"):
        if p.get("potions_auto"):
            from .engine.town import shard_catalog
            known: dict[str, Any] = p.setdefault("bag_rules", {})
            for n, v in shard_catalog()[0].items():
                if n.lower() not in known and (v.get("price") or 0) < 1000:
                    known[n.lower()] = {"action": "throw", "keep": 0}
        p["shard_lists"] = True
    bag_rules: dict[str, dict[str, Any]] = p.get("bag_rules") or {}
    for name, r in list(bag_rules.items()):
        if r.get("action") == "gem":
            del p["bag_rules"][name]


def _upgrade_potions(p: dict[str, Any]) -> None:
    """Potions before 2026-10-04 evening: fixed 80% / 3 s, MP off at 0. The bot now works the mark
    and cooldown out from the potion itself; old defaults become "auto" once (marker saved with
    the profile), numbers a player changed stay as they are."""
    if p.get("potions_auto"):
        return
    if p.get("hp_below") == 80:
        p["hp_below"] = "auto"
    if p.get("mp_below") in (0, 40, None):
        p["mp_below"] = "auto"
    for k in ("hp_cooldown", "mp_cooldown"):
        if p.get(k) == 3.0:
            p[k] = "auto"
    p["mp_use"] = True
    p.pop("mp_checked", None)
    p["potions_auto"] = True


def _upgrade_pet_potions(p: dict[str, Any]) -> None:
    """Pet potions before 2026-10-21: red only, at a fixed 50% with 10 s between. Pets died with
    potions in the bag; the marks now work like our own. A number the player chose stays."""
    if p.get("pet_potions_auto"):
        return
    if p.get("pet_hp_below") in (50, None):
        p["pet_hp_below"] = "auto"
    if p.get("pet_hp_cooldown") in (10, 10.0, None):
        p["pet_hp_cooldown"] = "auto"
    p["pet_potions_auto"] = True


def _upgrade_once(marker: str, key: str, old: Collection[object], new: object) -> Callable[[dict[str, Any]], None]:
    """A default that changed: the old one becomes the new once (the marker is saved with the
    profile); a number the player chose stays."""
    def step(p: dict[str, Any]) -> None:
        if not p.get(marker):
            if p.get(key) in old:
                p[key] = new
            p[marker] = True
    return step


def _upgrade_dropped(p: dict[str, Any]) -> None:
    """Pulling back from a pack is gone: the monsters followed at our own speed and kept hitting a
    character that had stopped attacking, so every pull-back cost potions and most ended in death."""
    for k in ("retreat", "retreat_below", "retreat_pack", "retreats_warn"):
        p.pop(k, None)


def _upgrade_class_reach(p: dict[str, Any]) -> None:
    """Every class fights from its own base attack's distance (Bot.reach, "auto"): a range typed in
    by hand before that became the rule goes back to auto, once. One set after this is kept."""
    if not p.get("class_reach"):
        p["attack_range"] = "auto"
        p["class_reach"] = True


UPGRADES: list[Callable[[dict[str, Any]], None]] = [
    _upgrade_choices, _upgrade_shard_lists, _upgrade_potions, _upgrade_pet_potions,
    # Before 2026-10-04 night the sheet was the only way to read MP and opened every minute (every
    # 15 s near the potion mark). MP now comes from the own-HP key; the sheet is for load and drop time.
    _upgrade_once("sheet_quiet", "sheet_every", (60, None), 600),
    # Before 2026-10-07 a target could go 15 s without losing HP before we left it; a whole kill
    # takes 2-4 s, so that was standing still for several kills' time.
    _upgrade_once("no_damage_quick", "no_damage_timeout", (15, 15.0, None), 6.0),
    # Before 2026-10-08 the bag counted as full at 90% of its load: a run went home with a tenth
    # of the bag still free. Full now means full.
    _upgrade_once("bag_really_full", "bag_full_at", (90, None), 100),
    _upgrade_dropped,
    _upgrade_class_reach,
    _upgrade_xp_card,
]


def save_profile(character: str, data: dict[str, Any]) -> None:
    saved = copy.deepcopy(data)
    if _profile_parts(character)[2]:
        saved[_PROFILE_ID_KEY] = character
    _write(profile_path(character), saved)


def has_profile(character: str) -> bool:
    if os.path.exists(profile_path(character)):
        return True
    name, server, entity_id = _profile_parts(character)
    if not entity_id:
        return False
    return os.path.exists(profile_path(character_profile(name, entity_id))) if server else os.path.exists(profile_path(name))


def export_profile(character: str, path: str) -> None:
    """Write the character's portable, player-chosen settings to *path* atomically.

    The file has an explicit format/version rather than being a bare profile, so an app settings
    file or a random JSON file cannot be mistaken for a character import.  Character-specific
    readings stay in the destination profile when it is imported; see
    CHARACTER_SPECIFIC_PROFILE_KEYS.
    """
    profile = copy.deepcopy(load_profile(character))
    for key in CHARACTER_SPECIFIC_PROFILE_KEYS:
        profile.pop(key, None)
    json.save(path, {"format": PROFILE_EXPORT_FORMAT, "version": PROFILE_EXPORT_VERSION,
                     "character": character, "settings": profile}, indent=2)


def read_profile_export(path: str) -> tuple[str, dict[str, Any]]:
    """Read a portable export or an ordinary existing profile without changing a profile.

    Before this feature existed, profiles were the portable format: players naturally keep and
    share ``profiles\\<character>.json``.  Those files remain supported.  An envelope is still
    preferred for new exports because it carries the source character and an explicit version.
    """
    try:
        with open(path, encoding="utf-8-sig") as f:
            raw = json.load(f)
    except (OSError, ValueError) as e:
        raise ValueError("couldn't read the file: %s" % e) from None
    if not json.is_object(raw):
        raise ValueError("this isn't a character-settings file")
    if "format" in raw:
        if raw.get("format") != PROFILE_EXPORT_FORMAT:
            raise ValueError("this isn't an Uncle Farmer character-settings file")
        if raw.get("version") != PROFILE_EXPORT_VERSION:
            raise ValueError("this character-settings file is from an unsupported version")
        source = raw.get("character")
        data = raw.get("settings")
        if not isinstance(source, str) or not source.strip():
            raise ValueError("the character-settings file has no character name")
        if not json.is_object(data):
            raise ValueError("the character-settings file has no settings")
    else:
        # A plain profile must actually contain at least one recognised profile choice.  Without
        # this a settings.json or any unrelated JSON object would silently become default profile
        # settings at import time.
        if not set(raw).intersection(PROFILE_DEFAULTS):
            raise ValueError("this JSON file doesn't contain character settings")
        data = raw
        base = os.path.basename(path)
        source = base[:-len(".unclefarmer-profile.json")] if base.endswith(".unclefarmer-profile.json") \
                 else os.path.splitext(base)[0]
    try:
        # Validate every known field before a caller asks to replace anything.  Extra fields are
        # retained by Profile so a newer Uncle Farmer can share settings with an older one.
        profile = Profile.model_validate({**copy.deepcopy(PROFILE_DEFAULTS), **copy.deepcopy(data)}).model_dump()
    except ValidationError as e:
        fields = ", ".join(str(err["loc"][0]) for err in e.errors() if err["loc"])
        raise ValueError("the character-settings file has invalid setting%s: %s" %
                         ("s" if "," in fields else "", fields or "data")) from None
    for key in CHARACTER_SPECIFIC_PROFILE_KEYS:
        profile.pop(key, None)
    return str(source).strip(), _upgrade(profile)


def import_profile(character: str, imported: dict[str, Any]) -> None:
    """Replace player choices for *character*, retaining its own learned game facts.

    Call read_profile_export first, show the user what will happen, then call this routine.  The
    final write uses save_profile's normal atomic, locked-file-aware path.
    """
    current = load_profile(character)
    profile = copy.deepcopy(imported)
    for key in CHARACTER_SPECIFIC_PROFILE_KEYS:
        if key in current:
            profile[key] = current[key]
    save_profile(character, profile)
