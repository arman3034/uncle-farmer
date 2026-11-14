"""Character settings: the choices a player makes for one character, and the advanced ones.

The scan fills in keys, skills, potions, beasts and pets from the game, so the main window asks
only for real decisions (how to fight, which potion, which beast, which pets). Keys and timings
live behind Advanced, for the rare player who needs them.
"""

from __future__ import annotations

from typing import Any, TypedDict

import wx

from .. import gamekeys, scan, settings
from ..engine import combat, potions, triggers, xpcard
from ..i18n import N_, _
from ..link import AgentError, AgentLink, games
from .common import (Dialog, Form, Handler, KeyDialog, buttons, enable_label, error, first_selected, group, info, key_ok,
                     labeled, ok_cancel, opens, page, pick, read_decimal, save_file, select_row, tabs)

STYLES = ("auto", "follow", "stationary")
PK_MODE_LABELS = (N_("Pacifist mode"), N_("Pacifist mode with counterattack"), N_("Moral Mode"),
                  N_("Gang mode"), N_("Team mode"), N_("All mode"))
TARGET_MODE_LABELS = (N_("All"), N_("Own side"), N_("Enemies"), N_("NPCs"))

# A skill's choices in Advanced settings, in combat.SKILL_USES order.
USE_LABELS = (N_("The bot decides"), N_("Never"), N_("Only when HP is low"), N_("Whenever it's ready"))

# What each skill role in data/skills.json is, in the player's words.
ROLE_WORDS = {
    "base_attack": N_("basic attack"), "single_target": N_("attack"), "finisher": N_("finishing attack"),
    "lifesteal": N_("attack that heals you"), "aoe": N_("area attack"), "dot": N_("damage over time"),
    "debuff": N_("weakens the enemy"), "control": N_("stun or slow"), "heal": N_("heal"), "party_buff": N_("buff"),
    "self_buff": N_("buff"), "dispel": N_("removes debuffs"), "defensive": N_("shield"), "mobility": N_("movement"),
    "taunt": N_("taunt"), "anti_heal": N_("stops healing"), "teleport": N_("teleport"), "resurrect": N_("revive"),
    "engage": N_("charge in"), "reactive": N_("after a dodge or block"),
}

# (setting, label) for every key the bot presses; the scan or "Read keys from the game" fills them.
KEYS = (
    ("move.up", N_("Walk north")), ("move.down", N_("Walk south")), ("move.left", N_("Walk west")),
    ("move.right", N_("Walk east")),
    ("target.west", N_("Target west")), ("target.north", N_("Target north")), ("target.south", N_("Target south")),
    ("target.east", N_("Target east")),
    ("sheet_key", N_("Character sheet")), ("vitals_key", N_("Own HP")), ("points_key", N_("Accumulation points")),
    ("pet_vitals_key", N_("Pet HP")),
    ("pk_key", N_("Change PK mode")), ("target_mode_key", N_("Change target mode")),
    ("bag_up", N_("Previous item")), ("bag_down", N_("Next item")), ("bag_left", N_("Previous panel")),
    ("bag_right", N_("Next panel")), ("use_key", N_("Use item")), ("category_key", N_("Next category")),
    ("hearthstone_key", N_("Hearthstone hotkey")),
    ("discard_key", N_("Discard item")), ("enter_key", N_("Choose in a dialog")), ("esc_key", N_("Close a dialog")),
    ("action_menu_key", N_("Action menu")), ("teleport_key", N_("Teleport to the team leader")),
)
REQUIRED = {"move.up", "move.down", "move.left", "move.right", "target.west", "target.north", "target.south",
            "target.east", "pk_key", "target_mode_key", "bag_up", "bag_down", "bag_left", "bag_right",
            "use_key", "category_key"}


class PotionTiming(TypedDict):
    """potion_timing's fields: when to drink and how often, each "auto" unless ticked."""
    below_on: wx.CheckBox
    below: wx.SpinCtrl
    gap_on: wx.CheckBox
    gap: wx.TextCtrl


class PetCare(TypedDict):
    """pet_care's fields."""
    pet_heal: wx.CheckBox
    pet_heal_below: wx.SpinCtrl
    team_heal: wx.CheckBox
    team_heal_below: wx.SpinCtrl
    potions: dict[str, PotionTiming]
    food_on: wx.CheckBox
    food_below: wx.SpinCtrl


class PotionPick(TypedDict):
    """The character window's potion choice: its control, the plan line, and the choice's values."""
    choice: wx.Choice
    about: wx.TextCtrl
    values: list[str]


def get_key(p: dict[str, Any], k: str) -> str:
    if k.startswith("move."):
        return p["move_keys"].get(k[5:], "")
    if k.startswith("target."):
        return p["target_keys"].get(k[7:], "")
    return p.get(k, "") or ""


def set_key(p: dict[str, Any], k: str, v: str) -> None:
    if k.startswith("move."):
        p["move_keys"][k[5:]] = v
    elif k.startswith("target."):
        p["target_keys"][k[7:]] = v
    else:
        p[k] = v


def potion_timing(f: Form, p: dict[str, Any], kind: str) -> PotionTiming:
    """When to drink a kind of potion ("hp", "mp", "pet_hp", "pet_mp") and how often, each "auto"
    unless set by hand: {"below_on", "below", "gap_on", "gap"} for save_potion_timing."""
    below, gap = p.get(kind + "_below", "auto"), p.get(kind + "_cooldown", "auto")
    auto_below, auto_gap = below in (None, "", "auto"), gap in (None, "", "auto")
    below_on, below_ctrl = f.optional(
        _("Set when to drink myself"), not auto_below, _("Drink below (%):"), 80 if auto_below else below, 1, 99)
    gap_on, gap_ctrl = f.optional(
        _("Set the time between potions myself"), not auto_gap, _("Time between potions (seconds):"),
        3 if auto_gap else gap, 0.5, 120, decimal=True)
    return {"below_on": below_on, "below": below_ctrl, "gap_on": gap_on, "gap": gap_ctrl}


def save_potion_timing(p: dict[str, Any], kind: str, ui: PotionTiming) -> None:
    """The values of a potion_timing pair into the profile (ValueError on a bad number)."""
    gap = read_decimal(ui["gap"]) if ui["gap_on"].GetValue() else None
    p[kind + "_below"] = ui["below"].GetValue() if ui["below_on"].GetValue() else "auto"
    p[kind + "_cooldown"] = gap if gap is not None else "auto"


def _mark(v: object, default: float) -> float:
    """The profile's number, or default where it says auto (or nothing)."""
    return default if v in (None, "", "auto") else float(str(v))


def pet_care(panel: wx.Window, box: wx.Sizer, p: dict[str, Any]) -> PetCare:
    """Healing the pet, healing teammates while following, the pet's potions and its food. The
    same fields are on the character window's Travel and pets tab and on Advanced settings' Pets
    page: both edit one profile, and the character window reloads its copy when Advanced closes."""
    f = group(panel, box, _("Healing the pet"))
    pet_heal = f.check(_("Heal the pet with my healing &skill (Priest, Sorceress)"),
                       p.get("pet_heal_with_skill", True))
    pet_heal_below = f.number(_("Heal it when its HP is below (%):"), _mark(p.get("pet_heal_below"), 85), 1, 99)
    f = group(panel, box, _("Healing teammates while following"))
    team_heal = f.check(_("Heal the player I follow and our &teammates with my healing skill "
                          "(Priest, Sorceress)"), p.get("team_heal", True))
    team_heal_below = f.number(_("Heal a teammate when their HP is below (%):"),
                               _mark(p.get("team_heal_below"), 70), 1, 99)
    potions = {kind: potion_timing(group(panel, box, title), p, kind)
               for kind, title in (("pet_hp", _("Pet HP potions")), ("pet_mp", _("Pet MP potions")))}
    f = group(panel, box, _("Pet food"))
    food = p.get("pet_food_below", 70)
    food_on, food_below = f.optional(
        _("Feed the pet a Rice Roll"), bool(food), _("When its amiability is below:"), food or 70, 1, 99)
    return {"pet_heal": pet_heal, "pet_heal_below": pet_heal_below, "team_heal": team_heal,
            "team_heal_below": team_heal_below, "potions": potions, "food_on": food_on, "food_below": food_below}


def save_pet_care(p: dict[str, Any], ui: PetCare) -> None:
    """pet_care's fields into the profile (ValueError on a bad number, with nothing changed)."""
    staged = dict(p)
    for kind, pui in ui["potions"].items():
        save_potion_timing(staged, kind, pui)
    staged["pet_heal_with_skill"] = ui["pet_heal"].GetValue()
    staged["pet_heal_below"] = ui["pet_heal_below"].GetValue()
    staged["team_heal"] = ui["team_heal"].GetValue()
    staged["team_heal_below"] = ui["team_heal_below"].GetValue()
    staged["pet_food_below"] = ui["food_below"].GetValue() if ui["food_on"].GetValue() else 0
    p.update(staged)


def _set_optional(box: wx.CheckBox, ctrl: wx.SpinCtrl | wx.TextCtrl, on: bool, value: float) -> None:
    box.SetValue(bool(on))
    if isinstance(ctrl, wx.SpinCtrl):
        ctrl.SetValue(int(value))
    else:
        ctrl.ChangeValue("%g" % float(value))
    ctrl.Enable(bool(on))
    enable_label(ctrl, bool(on))


def load_pet_care(ui: PetCare, p: dict[str, Any]) -> None:
    """Show the profile's values again (after Advanced settings changed them)."""
    ui["pet_heal"].SetValue(bool(p.get("pet_heal_with_skill", True)))
    ui["pet_heal_below"].SetValue(int(_mark(p.get("pet_heal_below"), 85)))
    ui["team_heal"].SetValue(bool(p.get("team_heal", True)))
    ui["team_heal_below"].SetValue(int(_mark(p.get("team_heal_below"), 70)))
    for kind, pui in ui["potions"].items():
        below, gap = p.get(kind + "_below", "auto"), p.get(kind + "_cooldown", "auto")
        _set_optional(pui["below_on"], pui["below"], below not in (None, "", "auto"), _mark(below, 80))
        _set_optional(pui["gap_on"], pui["gap"], gap not in (None, "", "auto"), _mark(gap, 3))
    food = p.get("pet_food_below", 70)
    _set_optional(ui["food_on"], ui["food_below"], bool(food), food or 70)


def _tiles(v: float) -> str:
    return ("%.1f" % v).rstrip("0").rstrip(".")


def pull_label(p: dict[str, Any]) -> str:
    """The early-fire setting says what it adds to: the bot already fights from the class's base
    attack range (Bot.reach: just inside the base attack's range, or the range set by hand), so 0
    is "fire from there", not "walk into melee" as the old wording read."""
    r = p.get("attack_range", "auto")
    if isinstance(r, (int, float)) and r != 5.0:
        return _("Open fire up to this many tiles &early, beyond the {reach} tiles set above, while a monster "
                 "comes at you (0: wait until it is within {reach}):", reach=_tiles(r))
    scanned: dict[str, Any] = p.get("scan") or {}
    cls: str = scanned.get("class") or ""
    base = [x for x in combat.knowledge().get(cls, []) if x.get("role") == "base_attack" and x.get("range")]
    if base:
        skill = min(base, key=lambda x: x["range"])
        reach = combat.base_reach(skill["range"])
        return _("Open fire up to this many tiles &early, beyond the {reach} tiles the bot fights from "
                 "({skill} reaches {range}), while a monster comes at you (0: wait until it is within {reach}):",
                 reach=_tiles(reach), skill=skill["name"], range=_tiles(skill["range"]))
    return _("Open fire up to this many tiles &early, beyond your class's attack range, while a monster comes "
             "at you (0: wait until it is in range):")


class ProfileDialog(Dialog):
    def __init__(self, parent: wx.Window, character: str, game_folder: str = "") -> None:
        super().__init__(parent, title=_("Character settings - {name}", name=settings.profile_display(character)),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.character = character
        self.game_folder = game_folder
        self.p = settings.load_profile(character)
        root = wx.BoxSizer(wx.VERTICAL)
        nb = tabs(self)
        self.overview_page(nb)
        self.fighting_page(nb)
        self.potions_page(nb)
        self.travel_page(nb)
        self.triggers_page(nb)
        root.Add(nb, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        ok_cancel(self, root, _("Save"), extra=[(opens(_("Ad&vanced")), self.on_advanced)])
        self.SetSizerAndFit(root)
        self.SetMinSize(wx.Size(640, 520))
        # Bound on the dialog, not the button: Enter in a text box sends OK to the dialog directly,
        # skipping a handler bound on the button (the dialog then closed without saving).
        self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)
        self.fill_from_scan()

    # ------------------------------------------------------------ pages
    def overview_page(self, nb: wx.Notebook) -> None:
        panel, box = page(nb, _("Overview"))
        labeled(panel, box, _("Saved account email:"),
                lambda w: wx.TextCtrl(w, value=self.p.get("login_email", ""), style=wx.TE_READONLY))
        self.known = labeled(panel, box, _("What the bot knows about this character:"),
                             lambda w: wx.TextCtrl(w, style=wx.TE_MULTILINE | wx.TE_READONLY, size=wx.Size(-1, 200)), 1)
        buttons(panel, box, (_("S&can now"), self.on_scan))

    def fighting_page(self, nb: wx.Notebook) -> None:
        p = self.p
        panel, box = page(nb, _("Fighting"))
        f = group(panel, box, _("Combat"))
        self.attack_style = f.choice(_("&Attack style:"), [_("Automatic, by class"), _("Walk up to the enemy"),
                                                           _("Stand still")],
                                     pick(STYLES, p.get("attack_style", "auto")))
        self.fight_beast = f.choice(_("Fight as &fusion beast:"), [""])
        pk = p["pk_mode"] + 1 if p.get("set_modes") else 0
        self.pk_mode = f.choice(_("&PK mode:"), [_("Leave as it is")] + [_(n) for n in PK_MODE_LABELS],
                                pk if 0 <= pk <= len(settings.PK_MODES) else 0)
        self.fight_back = f.check(_("Fight &back when attacked while travelling"), p["fight_back"])
        self.nearest_monster = f.check(_("Always fight the &nearest monster (off: melee picks a calm one beside a pack)"),
                                       p.get("nearest_monster", True))
        self.fight_locked = f.check(_("Fight monsters another player is &already killing"),
                                    p.get("fight_locked", False))
        self.shoot_while_walking = f.check(
            _("&Shoot monsters in reach while walking to the next one (a character that fights from afar)"),
            p.get("shoot_while_walking", False))
        self.skills_by_slot = f.check(_("Press s&kills through the game, not the keyboard"),
                                      p.get("skills_by_slot", True))
        self.walk_diagonal = f.check(_("Walk d&iagonally across open ground (both direction keys at once)"),
                                     p.get("walk_diagonal", True))
        self.use_buffs = f.check(_("Keep the class's b&uffs up"), p.get("use_buffs", True))
        self.use_dispel = f.check(_("Re&move debuffs with the class's dispel"), p.get("use_dispel", True))
        self.use_combos = f.check(_("Use the &combos of the activated talents"), p.get("use_combos", True))
        self.fill_keys = f.check(_("Put needed skills and items on &empty keys (never on keys in use)"),
                                 p.get("fill_empty_keys", True))
        f = group(panel, box, _("Death"))
        self.crystals = f.check(_("Revive on the spot with &Resurrection Crystals"), p["use_resurrection_crystal"])
        self.death_stop, self.max_deaths = f.optional(
            _("Stop after too many &deaths"), p.get("stop_on_deaths", True) and p["max_deaths"] > 0,
            _("Deaths before stopping:"), max(1, p["max_deaths"]), 1, 999)
        f = group(panel, box, _("Low HP"))
        self.panic, self.panic_below = f.optional(_("Stop when HP stays &low"), p["stop_on_panic"],
                                                  _("Low HP (%):"), p["panic_below"], 1, 99)
        self.panic_after = f.number(_("For (seconds):"), int(p["panic_after"]), 1, 120)
        self.panic.Bind(wx.EVT_CHECKBOX, lambda e: (e.Skip(), self.panic_after.Enable(self.panic.GetValue())))
        self.panic_after.Enable(self.panic.GetValue())
        f = group(panel, box, _("Corpses"))
        self.corpse_skill, self.corpse_vitality = f.optional(
            _("&Harvest the monsters we kill with the learned Draw Blood, Skinning or Cut Flesh"),
            p.get("corpse_skill", False),
            _("Stop when &Vitality is down to (0: until it runs out):"), p.get("corpse_keep_vitality", 0), 0, 100)
        f = group(panel, box, _("Experience cards"))
        self.xp_card = f.choice(_("E&xperience card to keep running while farming:"), [""])
        self.xp_card_values: list[str] = [""]
        self.xp_card_pause = f.check(_("Pause the card while a&way from the monsters: town trips, the walk back after a "
                                       "death, the end of farming (each pause costs a minute of the card; never in a "
                                       "dungeon)"), p.get("xp_card_pause", False))
        f = group(panel, box, _("Gear"))
        self.repair = f.check(_("Repair &gear with toolboxes from the bag"), p.get("repair_with", "toolbox") != "off")
        self.gear_stop = f.check(_("Stop if broken gear ca&n't be repaired"), p.get("stop_when_gear_broken", True))

    def potions_page(self, nb: wx.Notebook) -> None:
        p = self.p
        panel, box = page(nb, _("Potions"))
        self.potion_ui: dict[str, PotionPick] = {}
        for kind, title in (("hp", _("HP")), ("mp", _("MP"))):
            f = group(panel, box, title)
            if kind == "mp":
                self.mp_use = f.check(_("Use &MP potions"), p.get("mp_use", True))
                self.mp_use.Bind(wx.EVT_CHECKBOX, lambda e: self.enable_mp())
            choice = f.choice(_("&HP potion:") if kind == "hp" else _("M&P potion:"), [""])
            if kind == "hp":
                self.heal_skill = f.check(_("Heal with the class's o&wn heal skill (Sorceress, Priest); "
                                            "red potions only under half HP"), p.get("heal_with_skill", True))
            about = f.readonly(_("Plan:"), lines=2)
            self.potion_ui[kind] = {"choice": choice, "about": about, "values": []}
            choice.Bind(wx.EVT_CHOICE, self.potion_shower(kind))
        f = group(panel, box, _("Running out"))
        self.potions_out = f.check(_("Stop when the potions run &out (unless a restock rule brings more)"),
                                   p.get("stop_when_out_of_potions", True))

    def travel_page(self, nb: wx.Notebook) -> None:
        p = self.p
        panel, box = page(nb, _("Travel and pets"))
        f = group(panel, box, _("Travel"))
        self.speed_beast = f.choice(_("&Travel on fusion beast:"), [""])
        self.end_hearth = f.check(_("End the run with the &hearthstone"), p.get("end_with_hearthstone", True))
        self.pet_list = labeled(panel, box, _("P&ets (ticked ones come out, first ready one first):"),
                                lambda w: wx.CheckListBox(w, size=wx.Size(-1, 120)), 1)
        buttons(panel, box, (_("Move &up"), lambda e: self.move_pet(-1)),
                (_("Move &down"), lambda e: self.move_pet(1)))
        f = Form(panel)
        self.pet_recall = f.check(_("Put the pet &away when the run ends"), p["pet_recall_at_end"])
        box.Add(f.grid, 0, wx.TOP, 10)
        self.pet_care = pet_care(panel, box, p)

    def triggers_page(self, nb: wx.Notebook) -> None:
        """Tools jobs the bot runs by itself (engine/triggers.py): one tick per job and stage, the
        two stages independent - a job ticked in both runs once before and once after farming."""
        p = self.p
        panel, box = page(nb, _("Triggers"))
        self.triggers: dict[str, wx.CheckBox] = {}
        labels = {
            "before": {"sell_shards": _("&Sell shards (game menu, Sell shards now)"),
                       "clean_bag": _("&Clean the bag (game menu, Clean the bag now)"),
                       "update_shard_prices": _("&Update shard prices (game menu, Update shard prices)"),
                       "gather": _("&Gathering (as set in Tools, Gathering)"),
                       "store_items": _("S&tore items (game menu, Store items now)"),
                       "restock": _("&Restock supplies (game menu, Restock now)"),
                       "lose_xp": _("Lose e&xperience (as set in Tools, XP loser)")},
            "after": {"sell_shards": _("Se&ll shards (game menu, Sell shards now)"),
                      "clean_bag": _("Clea&n the bag (game menu, Clean the bag now)"),
                      "update_shard_prices": _("Up&date shard prices (game menu, Update shard prices)"),
                      "gather": _("Gat&hering (as set in Tools, Gathering)"),
                      "store_items": _("St&ore items (game menu, Store items now)"),
                      "restock": _("Restoc&k supplies (game menu, Restock now)"),
                      "lose_xp": _("Lose experience (as set in Tools, XP lose&r)")},
        }
        titles = {"before": _("Before farming (when a plan or a script that farms starts)"),
                  "after": _("After farming (when farming finishes by itself, never after Stop)")}
        for stage in triggers.STAGES:
            f = group(panel, box, titles[stage])
            for job, _what in triggers.JOBS:
                key = triggers.setting(job, stage)
                self.triggers[key] = f.check(labels[stage][job], p.get(key, False) is True)
        f = group(panel, box, _("How they run"))
        f.readonly(_("About:"), _(
            "Ticked jobs run one after the other in this order, each exactly as from the game's Tools submenu. A job "
            "ticked in both lists runs once before and once after farming. A job that can't finish is said "
            "and the next one still runs; Stop ends them. Store items uses the bag manager's storage list "
            "as it is at that moment."), lines=4)
        f.readonly(_("Restock now"), _("Fills enabled supplies to their configured targets, even above their "
                                      "automatic refill thresholds."), lines=2)

    # ------------------------------------------------------------ from the scan
    def potion_shower(self, kind: str) -> Handler:
        """A potion choice's handler: the plan line for what is chosen now."""
        return lambda e: self.show_potion(kind)

    def fill_from_scan(self) -> None:
        p = self.p
        s: dict[str, Any] = p.get("scan") or {}
        self.known.ChangeValue(scan.summary(s) or _("Not scanned yet. Log in to this character in the game "
                                                   "and press Scan now. The bot also scans when a run starts."))
        beasts: list[dict[str, Any]] = s.get("beasts", [])
        swift = [b for b in beasts if b["kind"] == "swift"]
        fierce = [b for b in beasts if b["kind"] == "fierce"]
        self.speed_values = ["auto", "none"] + [b["name"] for b in swift]
        self.speed_labels = [_("The fastest one"), _("None")] + \
                            [_("{name} (speed +{speed}, level {level})", **b) for b in swift]
        sel: str = p["speed_beast"]
        if sel not in self.speed_values:      # a beast the latest scan didn't see: keep the choice
            self.speed_values.append(sel)
            self.speed_labels.append(sel)
        self.speed_beast.Set(self.speed_labels)
        self.speed_beast.SetSelection(self.speed_values.index(sel))
        self.fight_values = ["none", "auto"] + [b["name"] for b in fierce]
        self.fight_labels = [_("None"), _("The strongest one")] + \
                            [_("{name} (level {level})", **b) for b in fierce]
        sel = p["fight_beast"]
        if sel not in self.fight_values:
            self.fight_values.append(sel)
            self.fight_labels.append(sel)
        self.fight_beast.Set(self.fight_labels)
        self.fight_beast.SetSelection(self.fight_values.index(sel))
        chosen: list[dict[str, Any]] = p.get("pets", [])
        self.pets = [dict(x) for x in chosen]
        scanned_pets: list[str] = s.get("pets", [])
        for name in scanned_pets:
            if name not in {x["name"] for x in self.pets}:
                self.pets.append({"name": name, "use": False})
        self.show_pets()
        self.fill_potions()
        self.fill_xp_cards()

    def fill_xp_cards(self) -> None:
        """The experience cards the last scan saw in the bag, weakest first, and None. A card that
        isn't in the bag is no choice: a chosen one that ran out goes back to None."""
        s: dict[str, Any] = self.p.get("scan") or {}
        found = xpcard.cards_in(s.get("bag", []))
        self.xp_card_values = [""] + [name for _power, name, _count in found]
        self.xp_card.Set([_("None")] + [_("{card} ({n} in the bag)", card=name, n=count)
                                        for _power, name, count in found])
        want = (self.p.get("xp_card_name") or "").strip().lower()
        pick = next((i for i, v in enumerate(self.xp_card_values) if v and v.lower() == want), 0)
        self.xp_card.SetSelection(pick)

    def fill_potions(self) -> None:
        """Potion choices from the last scan: what is on the hotkeys and in the bag."""
        p = self.p
        s: dict[str, Any] = p.get("scan") or {}
        have: dict[str, list[str | None]] = {}
        hotkeys: list[dict[str, Any]] = s.get("hotkeys", [])
        for h in hotkeys:
            if h.get("item") and h.get("count"):
                have.setdefault(h["item"], []).append(h.get("key"))
        rows: list[dict[str, Any]] = s.get("bag", [])
        bag: dict[str, int] = {b["name"]: b.get("count", 0) for b in rows if "potion" in b["name"].lower()}
        older: list[str] = s.get("potions_in_bag", [])
        for n in older:      # older scans: names only
            bag.setdefault(n, 0)
        for kind, colour in (("hp", ("red",)), ("mp", ("blue", "magic"))):
            ui = self.potion_ui[kind]
            names = sorted({n for n in list(have) + list(bag) if "potion" in n.lower() and "pet" not in n.lower()
                            and any(c in n.lower() for c in colour)})
            want: str = p.get(kind + "_potion", "auto") or "auto"
            if want != "auto" and want not in names:
                names.append(want)
            ui["values"] = ["auto"] + names
            labels = [_("The best one on my hotkeys")]
            for n in names:
                where = (_("key {key}", key=", ".join(k for k in have[n] if k)) if n in have
                         else _("bag only, used between fights"))
                labels.append(_("{item} ({count}, {where})", item=n, count=bag.get(n, 0), where=where))
            ui["choice"].Set(labels)
            ui["choice"].SetSelection(ui["values"].index(want) if want in ui["values"] else 0)
            self.show_potion(kind)
        self.enable_mp()

    def enable_mp(self) -> None:
        on = self.mp_use.GetValue()
        mp = self.potion_ui["mp"]
        for c in (mp["choice"], mp["about"]):
            c.Enable(on)
            enable_label(c, on)

    def show_potion(self, kind: str) -> None:
        ui = self.potion_ui[kind]
        what = kind.upper()
        s: dict[str, Any] = self.p.get("scan") or {}
        name: str | None = ui["values"][max(0, ui["choice"].GetSelection())]
        if name == "auto":
            hotkeys: list[dict[str, Any]] = s.get("hotkeys", [])
            hot: list[str] = [h["item"] for h in hotkeys if h.get("item") and h.get("count")
                   and "pet" not in h["item"].lower()
                   and any(c in h["item"].lower() for c in (("red",) if kind == "hp" else ("blue", "magic")))]
            rank = ("small", "medium", "large", "super", "potent")
            name = max(hot, key=lambda n: max([i for i, w in enumerate(rank) if w in n.lower()] or [0]), default=None)
        if not name:
            ui["about"].ChangeValue(_("No {what} potion on your hotkeys. Put one on a hotkey and scan, "
                                      "or choose one from the bag.", what=what))
            return
        text = potions.describe(name, what)
        inf = potions.info(name)
        top = s.get("maxhp") if kind == "hp" else None
        custom = self.p.get(kind + "_below", "auto")
        if inf and top and custom in (None, "", "auto"):
            text += " " + _("With your {top} max HP that is below {pct}%.", top=top,
                            pct="%.0f" % potions.mark(inf, top))
        ui["about"].ChangeValue(text)

    def show_pets(self, select: int = 0) -> None:
        self.pet_list.Set([x["name"] for x in self.pets])
        for i, x in enumerate(self.pets):
            self.pet_list.Check(i, bool(x["use"]))
        if self.pets:
            self.pet_list.SetSelection(max(0, min(select, len(self.pets) - 1)))

    def read_pets(self) -> None:
        for i, x in enumerate(self.pets):
            x["use"] = self.pet_list.IsChecked(i)

    def move_pet(self, step: int) -> None:
        i = self.pet_list.GetSelection()
        j = i + step
        if i < 0 or not 0 <= j < len(self.pets):
            return
        self.read_pets()
        self.pets[i], self.pets[j] = self.pets[j], self.pets[i]
        self.show_pets(j)
        self.pet_list.SetFocus()

    # ------------------------------------------------------------ buttons
    def on_scan(self, _evt: wx.Event) -> None:
        pid = next((g[0] for g in games() if settings.is_profile_of(g[1], self.character)), None)
        if pid is None:
            error(self, _("{name} isn't logged in to a game that has the agent.", name=settings.profile_display(self.character)))
            return
        try:
            with wx.BusyCursor(), AgentLink(pid=pid, timeout=5) as a:
                s = scan.scan(a, self.game_folder)
        except (AgentError, OSError, ValueError) as e:
            error(self, _("Couldn't read the game: {err}", err=e))
            return
        self.read_pets()
        self.p["pets"] = self.pets
        scan.apply(self.p, s)
        self.fill_from_scan()
        info(self, _("Scan complete."))

    def on_advanced(self, _evt: wx.Event) -> None:
        with AdvancedDialog(self, self.character, self.p, self.game_folder) as d:
            if d.ShowModal() == wx.ID_OK:
                for kind in ("hp", "mp"):
                    self.show_potion(kind)
                load_pet_care(self.pet_care, self.p)

    def on_ok(self, _evt: wx.Event) -> None:
        p = self.p
        p["attack_style"] = STYLES[max(0, self.attack_style.GetSelection())]
        p["fight_beast"] = self.fight_values[max(0, self.fight_beast.GetSelection())]
        mode = self.pk_mode.GetSelection()
        p["set_modes"] = mode > 0
        if mode > 0:
            p["pk_mode"] = mode - 1
        p["fight_back"] = self.fight_back.GetValue()
        p["nearest_monster"] = self.nearest_monster.GetValue()
        p["fight_locked"] = self.fight_locked.GetValue()
        p["shoot_while_walking"] = self.shoot_while_walking.GetValue()
        p["skills_by_slot"] = self.skills_by_slot.GetValue()
        p["walk_diagonal"] = self.walk_diagonal.GetValue()
        p["use_buffs"] = self.use_buffs.GetValue()
        p["use_dispel"] = self.use_dispel.GetValue()
        p["use_combos"] = self.use_combos.GetValue()
        p["fill_empty_keys"] = self.fill_keys.GetValue()
        p["respawn"] = "city"
        p["use_resurrection_crystal"] = self.crystals.GetValue()
        p["stop_on_deaths"] = self.death_stop.GetValue()
        p["max_deaths"] = self.max_deaths.GetValue()
        p["stop_on_panic"] = self.panic.GetValue()
        p["panic_below"] = self.panic_below.GetValue()
        p["panic_after"] = float(self.panic_after.GetValue())
        p["corpse_skill"] = self.corpse_skill.GetValue()
        p["corpse_keep_vitality"] = self.corpse_vitality.GetValue()
        p["xp_card_name"] = self.xp_card_values[max(0, self.xp_card.GetSelection())]
        p["xp_card_pause"] = self.xp_card_pause.GetValue()
        p["repair_with"] = "toolbox" if self.repair.GetValue() else "off"
        p["stop_when_gear_broken"] = self.gear_stop.GetValue()
        for kind, ui in self.potion_ui.items():
            p[kind + "_potion"] = ui["values"][max(0, ui["choice"].GetSelection())]
            p[kind + "_key"] = "auto"          # the key follows the potion's hotkey slot
        p["mp_use"] = self.mp_use.GetValue()
        p["heal_with_skill"] = self.heal_skill.GetValue()
        p["stop_when_out_of_potions"] = self.potions_out.GetValue()
        p["speed_beast"] = self.speed_values[max(0, self.speed_beast.GetSelection())]
        p["end_with_hearthstone"] = self.end_hearth.GetValue()
        for key, box in self.triggers.items():
            p[key] = box.GetValue()
        self.read_pets()
        p["pets"] = self.pets
        p["pet_recall_at_end"] = self.pet_recall.GetValue()
        try:
            save_pet_care(p, self.pet_care)
        except ValueError as e:
            error(self, str(e))
            return
        if save_file(self, settings.save_profile, self.character, p):
            self.EndModal(wx.ID_OK)


class AdvancedDialog(Dialog):
    """Keys and fine tuning. Changes go into the profile dict; the character window saves it."""

    def __init__(self, parent: wx.Window, character: str, profile: dict[str, Any], game_folder: str = "") -> None:
        super().__init__(parent, title=_("Advanced settings - {name}", name=settings.profile_display(character)),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.p = profile
        self.game_folder = game_folder
        self.keys = {k: get_key(profile, k) for k, _l in KEYS}
        root = wx.BoxSizer(wx.VERTICAL)
        nb = tabs(self)
        self.keys_page(nb)
        self.skills_page(nb)
        self.fighting_page(nb)
        self.health_page(nb)
        self.potions_page(nb)
        self.pets_page(nb)
        self.travel_page(nb)
        self.other_page(nb)
        root.Add(nb, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        ok_cancel(self, root)
        self.SetSizerAndFit(root)
        self.SetMinSize(wx.Size(620, 500))
        self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)

    def keys_page(self, nb: wx.Notebook) -> None:
        panel, box = page(nb, _("Keys"))
        self.key_list = labeled(panel, box, _("&Keys the bot presses:"),
                                lambda w: wx.ListCtrl(w, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=wx.Size(-1, 260)), 1)
        self.key_list.InsertColumn(0, _("Action"), width=260)
        self.key_list.InsertColumn(1, _("Key"), width=180)
        for i, (k, label) in enumerate(KEYS):
            self.key_list.InsertItem(i, _(label))
            self.key_list.SetItem(i, 1, self.keys[k] or _("none"))
        select_row(self.key_list, 0)
        self.key_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: self.change_key())
        buttons(panel, box, (opens(_("&Change key")), lambda e: self.change_key()),
                (_("&Read keys from the game"), self.on_read))
        f = Form(panel)
        self.attack_keys = f.text(_("&Attack keys when skills can't be read:"), " ".join(self.p["attack_keys"]))
        box.Add(f.grid, 0, wx.EXPAND | wx.TOP, 10)

    def change_key(self) -> None:
        i = first_selected(self.key_list)
        if i < 0:
            return
        k, label = KEYS[i]
        with KeyDialog(self, _(label), self.keys[k]) as d:
            if d.ShowModal() == wx.ID_OK:
                self.keys[k] = d.value
                self.key_list.SetItem(i, 1, d.value)
        self.key_list.SetFocus()

    def on_read(self, _evt: wx.Event) -> None:
        binds = gamekeys.read(self.game_folder)
        if not binds:
            error(self, _("The game's key settings weren't found. Set the game folder in Settings first."))
            return
        got = gamekeys.profile_keys(binds)
        move, turn = got.get("move_keys"), got.get("target_keys")
        for d in ("up", "down", "left", "right"):
            if isinstance(move, dict):
                self.keys["move." + d] = move[d] or ""
        for d in ("west", "north", "south", "east"):
            if isinstance(turn, dict):
                self.keys["target." + d] = turn[d] or ""
        for k, _l in KEYS:
            key = got.get(k)
            if isinstance(key, str):
                self.keys[k] = key
        for i, (k, _l) in enumerate(KEYS):
            self.key_list.SetItem(i, 1, self.keys[k] or _("none"))
        info(self, _("Keys read from the game."))

    def skills_page(self, nb: wx.Notebook) -> None:
        """Each skill on the keys (and each learned one) with the player's say over it."""
        p = self.p
        panel, box = page(nb, _("Skills"))
        f = Form(panel)
        self.smart = f.check(_("Choose &skills from what the game says about them (off: press the attack "
                               "keys in turn)"), p.get("smart_skills", True))
        box.Add(f.grid, 0, wx.EXPAND)
        self.skill_list = labeled(panel, box, _("S&kills:"),
                                  lambda w: wx.ListCtrl(w, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=wx.Size(-1, 200)), 1)
        for i, (title, width) in enumerate(((_("Skill"), 190), (_("Key"), 80), (_("Kind"), 150), (_("Use"), 170))):
            self.skill_list.InsertColumn(i, title, width=width)
        scanned: dict[str, Any] = p.get("scan") or {}
        info = {x["name"]: x for x in combat.knowledge().get(scanned.get("class") or "", [])}
        self.skill_info = info
        keys: dict[str, list[str]] = {}
        skill_keys: list[dict[str, Any]] = scanned.get("skill_keys", [])
        for x in skill_keys:
            if str(x["skill"]).isdigit():
                continue          # an empty key: the scan names it by its skill id, 0
            keys.setdefault(x["skill"], []).append(
                x["key"] if x.get("page", 1) == 1 else _("{key} (page {page})", key=x["key"], page=x["page"]))
        self.skill_rows = list(keys)
        learned: list[str] = scanned.get("skills", [])
        set_uses: dict[str, str] = p.get("skill_use") or {}
        for name in learned + sorted(set_uses):
            if name not in self.skill_rows:
                self.skill_rows.append(name)
        others: str = p.get("skill_use_others", "auto")
        self.uses = {n: set_uses.get(n) or others for n in self.skill_rows}
        for i, name in enumerate(self.skill_rows):
            role = info.get(name, {}).get("role")
            self.skill_list.InsertItem(i, name)
            self.skill_list.SetItem(i, 1, ", ".join(keys.get(name, [])) or _("none"))
            self.skill_list.SetItem(i, 2, _(ROLE_WORDS[role]) if role in ROLE_WORDS else "")
            self.skill_list.SetItem(i, 3, self.use_label(self.uses[name]))
        f = Form(panel)
        self.skill_use = f.choice(_("&Use the selected skill:"), [_(x) for x in USE_LABELS])
        self.skill_about = f.readonly(_("About the skill:"), lines=3)
        self.skill_others = f.choice(_("Skills not in this &list (learned or put on a key later):"),
                                     [_("The bot decides"), _("Never")], 1 if others == "never" else 0)
        box.Add(f.grid, 0, wx.EXPAND | wx.TOP, 10)
        if not self.skill_rows:
            self.skill_about.ChangeValue(_("No skills yet: log in to this character and press Scan now in "
                                           "the character window."))
            self.skill_use.Enable(False)
        else:
            select_row(self.skill_list, 0)
            self.show_skill()
        self.skill_list.Bind(wx.EVT_LIST_ITEM_SELECTED, lambda e: self.show_skill())
        self.skill_use.Bind(wx.EVT_CHOICE, lambda e: self.set_skill_use())

    @staticmethod
    def use_label(use: str) -> str:
        return _(USE_LABELS[combat.SKILL_USES.index(use)] if use in combat.SKILL_USES else USE_LABELS[0])

    def show_skill(self) -> None:
        i = first_selected(self.skill_list)
        if i < 0:
            return
        name = self.skill_rows[i]
        use = self.uses[name]
        self.skill_use.SetSelection(combat.SKILL_USES.index(use) if use in combat.SKILL_USES else 0)
        x = self.skill_info.get(name, {})
        bits: list[str] = []
        if x.get("role") in ROLE_WORDS:
            bits.append(_(ROLE_WORDS[x["role"]]).capitalize())
        if x.get("cd"):
            bits.append(_("cooldown {n} s", n="%g" % x["cd"]))
        if x.get("range"):
            bits.append(_("range {n}", n="%g" % x["range"]))
        text = ", ".join(bits)
        if x.get("text"):
            text = (text + ". " if text else "") + x["text"]
        self.skill_about.ChangeValue(text or _("The game's skill texts don't describe this one."))

    def set_skill_use(self) -> None:
        i = first_selected(self.skill_list)
        if i < 0:
            return
        use = combat.SKILL_USES[max(0, self.skill_use.GetSelection())]
        self.uses[self.skill_rows[i]] = use
        self.skill_list.SetItem(i, 3, self.use_label(use))

    def fighting_page(self, nb: wx.Notebook) -> None:
        p = self.p
        panel, box = page(nb, _("Fighting"))
        f = group(panel, box, _("Fighting"))
        rng = p["attack_range"] if isinstance(p["attack_range"], (int, float)) else 0
        self.range_on, self.attack_range = f.optional(_("Set the attack &range myself"), bool(rng),
                                                      _("Range (tiles):"), rng or 3, 0.5, 30, decimal=True)
        self.attack_gap = f.decimal(_("&Pause between attack keys (seconds):"), p["attack_gap"], 0.05, 5)
        self.pull = f.decimal(pull_label(p), p.get("pull_range", 0), 0, 15)
        self.fight_timeout = f.number(_("&Give up a fight after (seconds):"), p["fight_timeout"], 5, 600)
        self.no_damage = f.number(_("Give up when the enemy takes no &damage for (seconds):"),
                                  p["no_damage_timeout"], 3, 120)
        self.no_damage_casts = f.number(_("Or after this many casts that do &no damage:"),
                                        p.get("no_damage_casts", 3), 1, 20)
        self.press_burst = f.check(_("Press a skill again and &again until the game casts it"),
                                   p.get("press_burst", True))
        self.chase = f.number(_("&Chase monsters up to this many steps away (patrol loops):"),
                              p.get("chase_range", 40), 5, 150)
        keep = p.get("boss_distance", 40)
        self.boss_on, self.boss_keep = f.optional(
            _("Keep away from bosses"), bool(keep), _("Steps to keep from a boss:"), keep or 40, 5, 150)
        self.target_mode = f.choice(_("&Target keys pick:"), [_(n) for n in TARGET_MODE_LABELS],
                                    pick(list(range(len(settings.TARGET_MODES))), p.get("target_mode"), 0))
        f = group(panel, box, _("Walking"))
        self.stuck = f.number(_("Stop after this many &stuck walks in a row:"), p["stuck_limit"], 1, 50)

    def health_page(self, nb: wx.Notebook) -> None:
        p = self.p
        panel, box = page(nb, _("Low HP"))
        f = group(panel, box, _("Between fights"))
        self.rest_below = f.number(_("&Rest before the next fight below HP (%):"), p.get("rest_below", 60), 1, 99)
        self.rest_until = f.number(_("Rest &until HP (%):"), p.get("rest_until", 90), 1, 100)
        f = group(panel, box, _("Skills"))
        self.defend_below = f.number(_("&Defensive skills below HP (%):"), p.get("defend_below", 40), 1, 99)
        self.emergency_below = f.number(_("&Shields and big heals below HP (%):"), p.get("emergency_below", 50), 1, 99)
        self.heal_below = f.number(_("&Heal skill below HP (%):"), p.get("heal_below", 85), 1, 100)
        self.heal_potion_below = f.number(_("With a heal skill, red &potions only below HP (%):"),
                                          p.get("heal_potion_below", 50), 1, 100)

    def travel_page(self, nb: wx.Notebook) -> None:
        p = self.p
        panel, box = page(nb, _("Travel"))
        f = group(panel, box, _("Getting there"))
        self.prefer_walking = f.check(_("&Walk whenever the maps connect on foot"), p.get("prefer_walking", False))
        self.use_transport = f.check(_("Use &cable cars and teleport circles"), p.get("use_transport", True))
        self.use_airships = f.check(_("Use &airships (they may cost Arnebia)"), p.get("use_airships", True))
        self.vip = f.check(_("I'm a &VIP (cable cars and airships are free)"), p.get("vip", False))
        self.travel_items = f.check(_("Use &teleport stones and the hearthstone from the bag"),
                                    p.get("use_travel_items", False))
        self.teleport_skills = f.check(_("Use the class's teleport &skill (Mage, Elf)"),
                                       p.get("use_teleport_skills", True))
        f = group(panel, box, _("Ending a run"))
        self.end_safe = f.check(_("End on a map &without monsters"), p.get("end_safe", True))

    def potions_page(self, nb: wx.Notebook) -> None:
        p = self.p
        panel, box = page(nb, _("Potions"))
        self.potion_ui: dict[str, PotionTiming] = {}
        for kind, title in (("hp", _("HP")), ("mp", _("MP"))):
            self.potion_ui[kind] = potion_timing(group(panel, box, title), p, kind)

    def pets_page(self, nb: wx.Notebook) -> None:
        panel, box = page(nb, _("Pets"))
        self.pet_care = pet_care(panel, box, self.p)

    def other_page(self, nb: wx.Notebook) -> None:
        p = self.p
        panel, box = page(nb, _("Other"))
        f = group(panel, box, _("Going home"))
        self.hearth_item = f.text(_("&Hearthstone item:"), p["hearthstone_item"])
        f = group(panel, box, _("Reading the game"))
        self.sheet_every = f.number(_("Open the character sheet every (seconds):"), p["sheet_every"], 10, 3600)
        self.drop_tail = f.number(_("Drop time used after reaching safety (seconds):"),
                                  p.get("drop_tail_seconds", 300), 0, 1800)
        self.close_popups = f.check(_("&Close windows the game opens by itself"), p.get("close_popups", True))
        self.points_every = f.decimal(_("Read rage, marks or combos in fights every (seconds):"),
                                      p.get("points_every", 1.5), 0.5, 30)
        self.mp_every = f.number(_("Read MP near the potion mark every (seconds):"), p.get("mp_check_every", 10), 2, 120)
        f = group(panel, box, _("Bag"))
        self.only_this_run = f.check(_("Items with no rule: touch &only what this run picked up"),
                                     p.get("only_this_run", True))
        self.restock_every = f.number(_("Check the bag for restocking every (seconds):"),
                                      p.get("restock_check_every", 30), 5, 600)

    def on_ok(self, _evt: wx.Event) -> None:
        for k, label in KEYS:
            v = (self.keys[k] or "").strip().lower()
            if (k in REQUIRED or v not in ("", "auto")) and not key_ok(v):
                error(self, _("{action}: '{value}' isn't a key the bot can press.", action=_(label), value=v))
                return
        attack = self.attack_keys.GetValue().split()
        if not attack or not all(key_ok(k) for k in attack):
            error(self, _("Attack keys: enter keys separated by spaces, for example: j y . h"))
            return
        if not self.keys["hearthstone_key"].strip() and not self.hearth_item.GetValue().strip():
            error(self, _("Enter the hearthstone item's name, or give it a hotkey."))
            return
        try:
            gap = read_decimal(self.attack_gap)
            pull = read_decimal(self.pull)
            rng = read_decimal(self.attack_range) if self.range_on.GetValue() else None
            cool = {k: read_decimal(ui["gap"]) if ui["gap_on"].GetValue() else None
                    for k, ui in self.potion_ui.items()}
            points_every = read_decimal(self.points_every)
            save_pet_care(self.p, self.pet_care)
        except ValueError as e:
            error(self, str(e))
            return
        p = self.p
        for k, _l in KEYS:
            set_key(p, k, (self.keys[k] or "").strip().lower())
        p["attack_keys"] = [k.lower() for k in attack]
        p["attack_gap"] = gap
        p["attack_range"] = rng if rng else "auto"
        p["pull_range"] = pull
        p["fight_timeout"] = self.fight_timeout.GetValue()
        p["no_damage_timeout"] = self.no_damage.GetValue()
        p["no_damage_casts"] = self.no_damage_casts.GetValue()
        p["press_burst"] = self.press_burst.GetValue()
        p["chase_range"] = self.chase.GetValue()
        p["boss_distance"] = self.boss_keep.GetValue() if self.boss_on.GetValue() else 0
        p["smart_skills"] = self.smart.GetValue()
        others = "never" if self.skill_others.GetSelection() == 1 else "auto"
        p["skill_use_others"] = others
        # only what differs from the "not in this list" choice: a skill left there follows it
        p["skill_use"] = {n: u for n, u in self.uses.items() if u != others}
        p["rest_below"] = self.rest_below.GetValue()
        p["rest_until"] = self.rest_until.GetValue()
        p["defend_below"] = self.defend_below.GetValue()
        p["emergency_below"] = self.emergency_below.GetValue()
        p["heal_below"] = self.heal_below.GetValue()
        p["heal_potion_below"] = self.heal_potion_below.GetValue()
        p["prefer_walking"] = self.prefer_walking.GetValue()
        p["use_transport"] = self.use_transport.GetValue()
        p["use_airships"] = self.use_airships.GetValue()
        p["vip"] = self.vip.GetValue()
        p["use_travel_items"] = self.travel_items.GetValue()
        p["use_teleport_skills"] = self.teleport_skills.GetValue()
        p["end_safe"] = self.end_safe.GetValue()
        p["points_every"] = points_every
        p["mp_check_every"] = self.mp_every.GetValue()
        p["only_this_run"] = self.only_this_run.GetValue()
        p["restock_check_every"] = self.restock_every.GetValue()
        p["target_mode"] = self.target_mode.GetSelection()
        p["stuck_limit"] = self.stuck.GetValue()
        for kind, ui in self.potion_ui.items():
            p[kind + "_below"] = ui["below"].GetValue() if ui["below_on"].GetValue() else "auto"
            p[kind + "_cooldown"] = cool[kind] if cool[kind] is not None else "auto"
        p["hearthstone_item"] = self.hearth_item.GetValue().strip()
        p["sheet_every"] = self.sheet_every.GetValue()
        p["drop_tail_seconds"] = self.drop_tail.GetValue()
        p["close_popups"] = self.close_popups.GetValue()
        self.EndModal(wx.ID_OK)
