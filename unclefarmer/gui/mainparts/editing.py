"""More game clients, editing plans, scripts and settings, the tools and the guide."""

from __future__ import annotations

import os
import subprocess

import wx

from ... import applog, filelock, gameinstall, i18n, paths, settings
from ...engine import dungeon, plan as plans, script, town
from ...i18n import _
from .. import agentfix
from ..common import ask, ask_ok, error, info, save_file, show_text, modal
from ..plan import PlanDialog
from ..profile import ProfileDialog
from ..scripts import ScriptDialog
from ..setup import CHECK_UPDATES, SetupDialog
from .base import FrameParts, character_of


def import_confirmation(character: str, source: str, exists: bool) -> str:
    """The last clear warning before an import creates or replaces a profile file."""
    character = settings.profile_display(character)
    if exists:
        return _("Replace the saved Uncle Farmer settings for {character} with those exported from {source}?\n\n"
                 "This replaces combat, key, potion, bag, pet, travel and restock choices. "
                 "It keeps {character}'s own scan and learned hearthstone location. Nothing changes "
                 "until you choose Yes.", character=character, source=source)
    return _("Create Uncle Farmer settings for {character} from {source}?\n\n"
             "This creates settings for that name only. It doesn't create or log in to a Mist World "
             "character. The choices take effect when that character is scanned or run. Nothing changes "
             "until you choose Yes.", character=character, source=source)


def active_profile(owner: FrameParts) -> str | None:
    """The selected game's distinct profile; simple callers can still provide only a snapshot."""
    try:
        return owner.selected_profile() or character_of(owner.snapshot())
    except AttributeError:
        return character_of(owner.snapshot())


def import_destinations(source: str, profiles: list[str]) -> tuple[list[str], str]:
    """The destination choices and the canonical name selected for an imported profile.

    Windows profile paths are case-insensitive: ``atomix`` and ``Atomix`` are one file, not two
    possible destinations.  Keep the spelling already used by this copy when it has one.
    """
    character = next((name for name in profiles if name.casefold() == source.casefold()), source)
    names = list(profiles)
    if character not in names:
        names.append(character)
    names.sort(key=str.casefold)
    return names, character


class EditingMixin(FrameParts):
    # ------------------------------------------------------------ more game clients
    def open_client_for_login(self) -> str | None:
        """Start a client for automatic login, or return the reason it cannot be started.

        This deliberately has no dialog: schedules and scripts use the same path as a manual run
        without unexpectedly moving focus to Settings.
        """
        folder = self.remember_game_folder()
        if not gameinstall.is_game_folder(folder) or gameinstall.status(folder) != "installed":
            return _("The agent isn't installed in the game yet. Install it in Settings first.")
        try:
            subprocess.Popen([os.path.join(folder, "mw.exe")], cwd=folder, close_fds=True,
                             creationflags=getattr(subprocess, "DETACHED_PROCESS", 0x8))
        except OSError as e:
            return _("Couldn't start the game: {err}", err=e)
        return None

    def open_client(self) -> None:
        """Start one more Mist World from the menu, offering Setup when it is needed."""
        folder = self.remember_game_folder()
        if not gameinstall.is_game_folder(folder) or gameinstall.status(folder) != "installed":
            if ask(self, _("The agent isn't installed in the game yet, and without it a second game closes "
                           "right after it starts. Open Settings now?")):
                self.open_setup()
            return
        problem = self.open_client_for_login()
        if problem:
            error(self, problem)
            return
        self.say(_("Opening another game window. Log in, then choose it in the Games list."))
        wx.CallLater(8000, self.refresh_games)

    # ------------------------------------------------------------ editing
    def new_plan(self) -> None:
        with PlanDialog(self, dict(plans.PLAN_DEFAULTS, spots=[], end={"how": "start"}), self.snapshot) as d:
            if d.ShowModal() == wx.ID_OK:
                self.fill_runs(("plan", d.plan["name"]))

    def copy_plan(self) -> None:
        item = self.active_item()
        if not item or item[0] != "plan":
            self.say(_("Select a plan first."))
            return
        p = plans.load(item[1])
        p["name"] = _("{name} copy", name=p["name"])
        with PlanDialog(self, p, self.snapshot) as d:
            d.original_name = ""
            if d.ShowModal() == wx.ID_OK:
                self.fill_runs(("plan", d.plan["name"]))

    def new_script(self) -> None:
        with ScriptDialog(self) as d:
            d.ShowModal()
            name = d.original
        self.fill_runs(("script", name) if name else None)

    def edit_selected(self) -> None:
        item = self.active_item()
        if not item:
            self.new_plan()
            return
        if item[0] == "plan":
            with PlanDialog(self, plans.load(item[1]), self.snapshot) as d:
                if d.ShowModal() == wx.ID_OK:
                    self.fill_runs(("plan", d.plan["name"]))
        else:
            with ScriptDialog(self, item[1]) as d:
                d.ShowModal()
                name = d.original
            self.fill_runs(("script", name))

    def delete_selected(self) -> None:
        item = self.active_item()
        if not item:
            return
        if not ask(self, _("Delete {name}? This can't be undone.", name=item[1])):
            return
        try:
            if item[0] == "plan":
                plans.delete(item[1])
            else:
                filelock.delete(plans.script_path(item[1]))
        except OSError as e:
            error(self, _("Couldn't delete it: {err}", err=e))
            return
        self.fill_runs()

    def export_plan(self) -> None:
        """Plans, Export: make a portable copy of the selected saved plan."""
        item = self.active_item()
        if not item or item[0] != "plan":
            self.say(_("Select a plan first."))
            return
        name = item[1]
        wildcard = _("Uncle Farmer plan exports (*.unclefarmer-plan.json)|*.unclefarmer-plan.json|") + \
                   _("JSON files (*.json)|*.json")
        with modal(wx.FileDialog(self, _("Export plan"), wildcard=wildcard,
                                 defaultFile=paths.safe_name(name) + ".unclefarmer-plan.json",
                                 style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)) as d:
            if d.ShowModal() != wx.ID_OK:
                return
            target = d.GetPath()
        try:
            plans.export(name, target)
        except (OSError, ValueError) as e:
            error(self, _("Couldn't export the plan: {err}", err=e))
            return
        info(self, _("Plan {name} was exported to:\n{path}", name=name, path=target))

    def import_plan(self) -> None:
        """Plans, Import: validate a portable or ordinary plan before an atomic save."""
        wildcard = _("Uncle Farmer plan exports and plans (*.unclefarmer-plan.json;*.json)|*.unclefarmer-plan.json;*.json|") + \
                   _("All files (*.*)|*.*")
        with modal(wx.FileDialog(self, _("Import plan"), wildcard=wildcard,
                                 style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)) as d:
            if d.ShowModal() != wx.ID_OK:
                return
            source = d.GetPath()
        try:
            plan = plans.read_import(source)
        except ValueError as e:
            error(self, _("Couldn't import the plan: {err}", err=e))
            return
        existing = next((name for name in plans.names() if name.casefold() == plan["name"].casefold()), None)
        if existing:
            plan["name"] = existing
            if not ask(self, _("Replace the saved plan {name}? Nothing changes until you choose Yes.", name=existing),
                       _("Import plan")):
                return
        try:
            plans.save(plan)
        except (OSError, ValueError) as e:
            error(self, _("Couldn't import the plan: {err}", err=e))
            return
        self.fill_runs(("plan", plan["name"]))
        info(self, _("Plan {name} was imported.", name=plan["name"]))

    def script_help(self) -> None:
        show_text(self, _("Script commands"), script.__doc__ or "")

    def edit_profile(self) -> None:
        name = active_profile(self)
        if not name:
            error(self, _("Log in to the character in the game first, or use Character, Another character."))
            return
        with ProfileDialog(self, name, self.s.get("game_folder", "")) as d:
            d.ShowModal()

    def walk(self) -> None:
        """Run, Walk to: the walking assistant takes the selected game's character to a dungeon
        entrance or a map on the fastest Swift fusion beast, never stopping to fight."""
        from ..walk import WalkDialog
        if self.selected_pid() is None:
            self.refresh_games()
        if self.selected_pid() is None:
            self.say(_("No game with the agent is running."))
            return
        if self.selected_pid() in self.runs:
            self.say(_("Stop the bot first."))
            return
        with WalkDialog(self, self.snapshot) as d:
            if d.ShowModal() != wx.ID_OK:
                return
            text, title = d.script, d.title
        self.run_errand(text, title, walk=True)

    def open_tool(self, which: str) -> None:
        """Tools, Gem Maker / Equipment Enhancer / Daily chores / Gathering / Dungeons: set up for the
        logged-in character, then check or start it as a job on that game."""
        from ..crafting import CHECK, START, EnhancerDialog, GemMakerDialog
        name = active_profile(self)
        if not name:
            error(self, _("Log in to the character in the game first."))
            return
        if self.selected_pid() not in self.runs:
            self.scanned = getattr(self, "scanned", {})
            self.scanned.pop(name, None)
            with wx.BusyCursor():
                self.auto_scan(name)          # a fresh look at the bag and gear first
        from ..chores import ChoresDialog
        from ..dungeon import DungeonDialog
        from ..gathering import GatheringDialog
        from ..xploss import XpLoserDialog
        cls, cmd, title = {"gem": (GemMakerDialog, "gem_maker", _("Gem Maker")),
                           "enhance": (EnhancerDialog, "enhance", _("Equipment Enhancer")),
                           "chores": (ChoresDialog, "chores", _("Daily chores")),
                           "gather": (GatheringDialog, "gather", _("Gathering")),
                           "dungeon": (DungeonDialog, "dungeon", _("Dungeons")),
                           "xploss": (XpLoserDialog, "lose_xp", _("XP loser"))}[which]
        # "Add where I stand" and "Use where I stand now" read the game
        extra = (self.snapshot,) if which in ("gather", "dungeon", "xploss") else ()
        with cls(self, name, *extra) as d:
            code = d.ShowModal()
            cfg = getattr(d, "cfg", None)
        if code == CHECK:
            self.run_errand(cmd + " check\n", _("{tool} check", tool=title))
        elif code == START and which == "dungeon":
            self.run_errand(dungeon.script(cfg or {}), title)     # its end place, then the caves
        elif code == START:
            self.run_errand(cmd + "\n", title)

    def edit_bag(self) -> None:
        name = active_profile(self)
        if not name:
            error(self, _("Log in to the character in the game first."))
            return
        from ..bagmanager import BagManagerDialog
        if self.selected_pid() not in self.runs:
            self.scanned = getattr(self, "scanned", {})
            self.scanned.pop(name, None)
            with wx.BusyCursor():
                self.auto_scan(name)          # a fresh look at the bag before choosing
        with BagManagerDialog(self, name) as d:
            d.ShowModal()

    def sell_shards_now(self) -> None:
        """The game menu's Sell shards now: the shards the bag manager says to sell, at this city's Shard
        Market or the nearest one - a job of its own, like selling the collection. Started by hand,
        whatever Character settings says about selling after farming."""
        self.log(_("Sell shards now: started by hand"))
        self.run_errand("sell_shards\n", _("Selling shards"))

    def restock_now(self) -> None:
        """Run an explicit supply top-up through the same job as farming triggers."""
        self.run_errand("restock\n", _("Restocking supplies"))

    def sell_collection_now(self) -> None:
        """Sell the selected character's gathered fish, ore, or herbs right away."""
        self.run_errand("sell_collection\n", _("Selling the collection"))

    def store_items_now(self) -> None:
        """The game menu's Store items now: put into the storehouse what the bag manager's storage list says
        (Character, Bag and supplies, "Move to storehouse"), keeping what each rule keeps - the same
        job the Triggers tab can run before or after farming. Storing loses nothing, so no question."""
        name = active_profile(self)
        if name and not town.store_list(settings.load_profile(name)):
            info(self, _("The storage list is empty. Choose what to move to the storehouse in Character, Bag and "
                         "supplies first."))
            return
        self.log(_("Store items now: started by hand"))
        self.run_errand("store_items\n", _("Storing items"))

    def update_shard_prices_now(self) -> None:
        """The game menu's Update shard prices: read the nearest Shard Market's list into data/shards.json
        (only the prices it shows and sends alike; every other price stays as it was)."""
        self.run_errand("update_shard_prices\n", _("Updating shard prices"))

    def clean_bag_now(self) -> None:
        """The game menu's Clean the bag now: throw away what is on the bag manager's throw-away list, after
        the player has seen the list and said yes (thrown items are gone for good)."""
        name = active_profile(self)
        if not name:
            error(self, _("Log in to the character in the game first."))
            return
        if self.selected_pid() in self.runs:
            self.say(_("Stop the bot first."))
            return
        listed = town.throw_list(settings.load_profile(name))
        if not listed:
            info(self, _("The throw-away list is empty. Choose what to throw away in Character, Bag and supplies "
                         "first."))
            return
        what = "\n".join(_("{item}, keeping {n}", item=item, n=keep) if keep else item for item, keep in listed)
        if not ask(self, _("Throw away whatever of these is in the bag, right where you stand?\n\n{list}\n\n"
                           "Nothing else is touched. Thrown items are gone for good.", list=what),
                   _("Clean the bag")):
            return
        self.log(_("Clean the bag now: started by hand"))
        self.run_errand("clean_bag\n", _("Cleaning the bag"))

    def edit_other_profile(self) -> None:
        profiles = settings.profiles()
        if not profiles:
            info(self, _("No character has settings yet. Log in to one in the game and the bot scans it."))
            return
        labels = [settings.profile_display(profile) for profile in profiles]
        with modal(wx.SingleChoiceDialog(self, _("Character:"), _("Another character"), labels)) as d:
            if d.ShowModal() != wx.ID_OK:
                return
            name = profiles[d.GetSelection()]
        with ProfileDialog(self, name, self.s.get("game_folder", "")) as d:
            d.ShowModal()

    def export_character_settings(self) -> None:
        """Character, Export settings: a portable copy of choices, never game readings."""
        profiles = settings.profiles()
        if not profiles:
            info(self, _("No character has settings to export yet. Log in to one and let the bot scan it first."))
            return
        labels = [settings.profile_display(profile) for profile in profiles]
        with modal(wx.SingleChoiceDialog(self, _("Character:"), _("Export character settings"), labels)) as d:
            if d.ShowModal() != wx.ID_OK:
                return
            character = profiles[d.GetSelection()]
        filename = paths.safe_name(settings.profile_display(character)) + ".unclefarmer-profile.json"
        wildcard = _("Uncle Farmer character settings and profiles (*.unclefarmer-profile.json;*.json)|*.unclefarmer-profile.json;*.json|") + \
                   _("All files (*.*)|*.*")
        with modal(wx.FileDialog(self, _("Export character settings"), wildcard=wildcard, defaultFile=filename,
                                 style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)) as d:
            if d.ShowModal() != wx.ID_OK:
                return
            path = d.GetPath()
        try:
            settings.export_profile(character, path)
        except (OSError, ValueError) as e:
            error(self, _("Couldn't export the settings: {err}", err=e))
            return
        info(self, _("Settings for {character} were exported to:\n{path}\n\nThe file has combat, keys, potions, "
                     "bag, pet, travel and restock choices. It doesn't contain scans or the learned hearthstone "
                     "location.", character=settings.profile_display(character), path=path))

    def import_character_settings(self) -> None:
        """Character, Import settings: validate first, confirm, then atomically replace choices."""
        # Profiles from older/local copies are ordinary .json files, as are the new exports.
        # The initially selected Windows filter explicitly includes both, so either appears at once.
        wildcard = _("Uncle Farmer character settings and profiles (*.unclefarmer-profile.json;*.json)|*.unclefarmer-profile.json;*.json|") + \
                   _("All files (*.*)|*.*")
        with modal(wx.FileDialog(self, _("Import character settings"), wildcard=wildcard,
                                 style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)) as d:
            if d.ShowModal() != wx.ID_OK:
                return
            path = d.GetPath()
        try:
            source, imported = settings.read_profile_export(path)
        except ValueError as e:
            error(self, _("Couldn't import the settings: {err}", err=e))
            return
        profiles, suggested = import_destinations(source, settings.profiles())
        labels = [settings.profile_display(profile) for profile in profiles]
        with modal(wx.SingleChoiceDialog(self, _("Import settings into this character:"),
                                         _("Import character settings"), labels)) as d:
            d.SetSelection(profiles.index(suggested))
            if d.ShowModal() != wx.ID_OK:
                return
            character = profiles[d.GetSelection()]
        exists = settings.has_profile(character)
        if not ask(self, import_confirmation(character, source, exists),
                   _("Import character settings")):
            return
        try:
            settings.import_profile(character, imported)
        except (OSError, ValueError) as e:
            error(self, _("Couldn't import the settings: {err}", err=e))
            return
        info(self, _("Settings were imported into {character}. Scan this character before farming if its skills, "
                     "hotkeys, bag, pets or beasts changed.", character=settings.profile_display(character)))

    # ------------------------------------------------------------ settings
    def first_run(self) -> None:
        """The first thing the main loop does: how an update went, the agent, and then the END of
        bootup.log. A check that fails is written there with its traceback; the window stays."""
        boot = applog.bootup
        with boot.step("update result and check", must=False):
            self.after_update()
        with boot.step("game folder and agent", must=False):
            self.check_game()
        boot.end("ready")

    def check_game(self) -> None:
        folder = self.remember_game_folder()
        if not gameinstall.is_game_folder(folder):
            applog.bootup.note("no game folder set yet: the welcome message offers Settings")
            if ask(self, _("Welcome to Uncle Farmer. The agent needs to be installed in Mist World first. "
                           "Open Settings now?")):
                self.open_setup()
            return
        self.check_agent(folder)

    def check_agent(self, folder: str) -> None:
        """The agent must be in the game's settings, pointing at this copy, and every open game
        must have loaded this version of it. Otherwise it is reinstalled (reinstall_agent)."""
        st = gameinstall.status(folder)
        applog.bootup.note("agent in the game's settings: %s" % st)
        if st == "missing":
            why = _("Mist World's settings don't load it (it was never installed there, or another tool "
                    "removed it)")
        elif st == "other":
            why = _("Mist World loads another Uncle Farmer's agent (an older copy, or this one before it "
                    "moved)")
        else:
            stale = gameinstall.stale_games()
            if not stale:
                applog.bootup.note("no open game lacks this version's agent")
                return
            applog.bootup.note("open games without this version's agent: %d - asking to reinstall" % len(stale))
            why = _("open games started without this version's agent: {n}", n=len(stale))
        self.reinstall_agent(folder, why)

    def reinstall_agent(self, folder: str, why: str) -> None:
        """Ask; on OK close every open game (a game loads the agent only as it starts), then
        install the agent again. Nothing happens while a bot runs: its game would close under it."""
        if self.runs:
            error(self, _("Uncle Farmer's agent needs to be reinstalled: {why}. Stop every running bot, then "
                          "use File, Settings, Install.", why=why))
            return
        games = agentfix.running_pids()
        if games:
            text = _("Uncle Farmer's agent needs to be reinstalled: {why}.\n\nPress OK to close every Mist "
                     "World window ({n} open) and reinstall it. A game loads the agent only as it starts, so "
                     "start Mist World again afterwards.", why=why, n=len(games))
        else:
            text = _("Uncle Farmer's agent needs to be reinstalled: {why}.\n\nPress OK to reinstall it.", why=why)
        if not ask_ok(self, text, _("Reinstall the agent")):
            return
        if not games:
            self._install_agent(folder, [])
            return
        self.say(_("Closing every Mist World window to reinstall the agent"))
        agentfix.close_then(games, lambda left: self._install_agent(folder, left))

    def _install_agent(self, folder: str, left: list[int]) -> None:
        if self.destroyed:
            return
        if left:
            error(self, _("Mist World windows that didn't close: {n}. The agent wasn't reinstalled: close them, "
                          "then use File, Settings, Install.", n=len(left)))
            return
        try:
            gameinstall.install(folder)
        except OSError as e:
            error(self, _("Couldn't change the game's settings: {err}", err=e))
            return
        if self.s.get("game_folder") != folder:
            self.s["game_folder"] = folder
            save_file(self, settings.save_app, self.s)
        info(self, _("The agent is reinstalled. Start Mist World again: it loads the agent as it starts."))

    def remember_game_folder(self) -> str:
        """The game folder in the settings, or - when that is empty or holds no agent - the one
        the agent is installed in, found and saved (gameinstall.find_installed)."""
        folder = self.s.get("game_folder", "")
        if gameinstall.status(folder) == "installed":
            return folder
        found = gameinstall.find_installed(folder)
        if found:
            self.s["game_folder"] = found
            save_file(self, settings.save_app, self.s)
            return found
        return folder

    def open_setup(self) -> None:
        with SetupDialog(self, self.s) as d:
            code = d.ShowModal()
            if code not in (wx.ID_OK, CHECK_UPDATES):
                return
            old_lang = self.s.get("language", "en")
            try:
                d.apply()
            except (ValueError, IndexError) as e:
                error(self, _("Couldn't apply the settings: {err}", err=e))
                return
            if save_file(self, settings.save_app, self.s) and self.s["language"] != old_lang:
                i18n.load(self.s["language"])
                info(self, _("Restart Uncle Farmer to switch the language."))
        if code == CHECK_UPDATES:
            self.check_updates()          # Help, Check for updates, on the channel just saved

    def open_user_guide(self) -> None:
        """README.html beside the exe (build_exe.py makes it from docs/USER_GUIDE.md)."""
        page = os.path.join(paths.APP, "README.html")
        if not os.path.exists(page):
            page = os.path.join(paths.DOCS, "USER_GUIDE.md")       # running from source
        os.startfile(page)
