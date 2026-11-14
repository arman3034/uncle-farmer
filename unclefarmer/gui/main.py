"""The main window: three tabs - Bot (games, start and stop, live status), Plans (plans and
scripts), Log.

Several game clients can run at once (the agent lets each one start), and each can run its own
plan: self.runs holds one Run per game process. Start, Stop and the status fields are about the
game selected in the Games list; the Pause key is about the game window in front, if it is one of
ours.
"""

from __future__ import annotations

import os

import wx

from .. import __version__, applog, messages, paths, settings
from ..clock import CLOCK, Clock
from ..i18n import _
from .common import Handler, ask, buttons, group, guide_text, info, labeled, opens, popup_actions, shortcut_label, show_text, tabs
from .mainparts.editing import EditingMixin
from .mainparts.games import GamesMixin
from .mainparts.logpane import LogMixin
from .mainparts.results import ResultsMixin
from .mainparts.runs import RunsMixin
from .mainparts.scheduling import SchedulingMixin
from .mainparts.talk import TalkMixin
from .mainparts.updates import UpdatesMixin
from .silencer import SilencerDialog
from .. import updater
from ..soundrestore import SoundRestore

HOTKEY_ID = 0xBF01
RESULTS_HOTKEY_ID = 0xBF02
VK_PAUSE = 0x13
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
BOT_STOP_WAIT = 5.0         # seconds each running bot gets to end when the app closes


def action_menu_states(*, available: bool, running: bool, any_running: bool, has_items: bool,
                       has_messengers: bool, selected: tuple[str, str] | None) -> dict[str, bool]:
    """The menu availability matrix, kept separate from wx so every game and plan state is testable."""
    plan = bool(selected and selected[0] == "plan")
    return {
        "run_start": available and not running and has_items, "run_stop": running,
        "run_pause": running, "run_stop_all": any_running, "run_walk": available and not running,
        "run_schedules": True, "run_results": True, "run_speak_results": True,
        "game_mute": available, "game_unmute": available, "game_mute_all": True, "game_unmute_all": True,
        "game_open": True, "messages_private": True, "messages_chat": available,
        "messages_reset": has_messengers, "character_settings": available, "character_bag": available,
        "character_scan": available and not running, "character_other": True,
        "character_export": True, "character_import": True,
        "tools_gem": available and not running, "tools_enhance": available and not running,
        "tools_chores": available and not running, "tools_gather": available and not running,
        "tools_dungeon": available and not running, "tools_xploss": available and not running,
        "tools_silencer": available,
        **{key: available and not running for key in ("tools_collection", "tools_shards", "tools_clean",
                                                     "tools_store", "tools_restock", "tools_prices")},
        "plans_new": True, "plans_new_script": True,
        "plans_edit": bool(selected), "plans_duplicate": plan, "plans_delete": bool(selected),
        "plans_export": plan, "plans_import": True,
    }


class MainFrame(GamesMixin, RunsMixin, LogMixin, TalkMixin, ResultsMixin, EditingMixin,
                UpdatesMixin, SchedulingMixin, wx.Frame):
    """The window, its three tabs and its menus; what each part does is in gui/mainparts."""
    clock: Clock = CLOCK

    def __init__(self, clock: Clock = CLOCK) -> None:
        super().__init__(None, title=_("Uncle Farmer"), size=wx.Size(860, 640))
        self.clock = clock
        self.s = settings.load_app()
        self.runs = {}           # pid -> Run, one per game client
        self.farm_starts = {}    # pid -> (map, x, y) where that game's last farming run started (`home`)
        self.messengers = {}     # pid -> messages.Messenger, private messages of that game
        self.chats = {}          # pid -> chat.Feed, that game's chat (memory only, never saved)
        self.chat_windows = {}   # pid -> its open Chat window
        self.silencer_windows: dict[int, SilencerDialog] = {}
        self.sound_restorer = SoundRestore()
        self.pending_update: updater.ApplyProcess | None = None
        self.games = []          # [(pid, character, map name)]
        self.unavailable_agents = {}  # pid -> (port, secret) for stale or unreachable agent records
        self.items = []          # [("plan"|"script", name)]
        self.log_lines = []      # [(text, important)]
        self.last_line = {}      # pid -> the latest log line of that game's run
        self.silenced = set()    # games this window silenced because game_speech is "always"
        self.voice_fixed = {}    # pid -> what that game's voice player was last told (fix_voice)
        self.filling = False     # the Games list is being remade: its selection events mean nothing
        self.destroyed = False
        self.snap = None         # (pid, snapshot, when): the last reading of a game
        self.snap_busy = False
        self.scanning = set()    # characters being scanned on a worker thread
        self.pending_logins = {} # profile -> when automatic login opened its client
        self.updating = False
        self.close_reason = ""   # why the window closes, when it isn't the player (teardown.log)
        self.hotkeys: list[int] = []     # the global hotkeys this window holds

        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.VERTICAL)
        self.nb = tabs(panel)
        self.bot_page()
        self.plans_page()
        self.log_page()
        root.Add(self.nb, 1, wx.EXPAND | wx.ALL, 8)
        panel.SetSizer(root)
        self.CreateStatusBar()

        self.build_menu()
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda e: self.poll(), self.timer)
        self.timer.Start(3000)
        applog.bootup.note("game list timer started (every 3 s)")
        if self.RegisterHotKey(HOTKEY_ID, MOD_NOREPEAT, VK_PAUSE):
            self.hotkeys.append(HOTKEY_ID)
            self.Bind(wx.EVT_HOTKEY, lambda e: self.toggle(), id=HOTKEY_ID)
        else:
            applog.bootup.problem("the Pause key is taken by another program: the Pause shortcut won't work")
            self._append(_("Another program is using the Pause key; the Pause shortcut won't work."), False)
        if self.RegisterHotKey(RESULTS_HOTKEY_ID, MOD_SHIFT | MOD_NOREPEAT, VK_PAUSE):
            self.hotkeys.append(RESULTS_HOTKEY_ID)
            self.Bind(wx.EVT_HOTKEY, lambda e: self.speak_results(front=True), id=RESULTS_HOTKEY_ID)
        else:
            applog.bootup.problem("Shift+Pause is taken by another program: it won't speak the results")
        applog.bootup.note("hotkeys held: %d of 2" % len(self.hotkeys))

        self.fill_runs()
        self.refresh_games()
        self.update_buttons()
        self.start_schedules()
        self.game_list.SetFocus()
        wx.CallAfter(self.first_run)

    # ------------------------------------------------------------ tabs
    def bot_page(self) -> None:
        panel = wx.Panel(self.nb)
        box = wx.BoxSizer(wx.VERTICAL)
        self.game_list = labeled(panel, box, _("&Games:"), lambda w: wx.ListCtrl(
            w, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=wx.Size(-1, 110)), 1)
        for i, (title, width) in enumerate(((_("Character"), 200), (_("Map"), 240), (_("Bot"), 300))):
            self.game_list.InsertColumn(i, title, width=width)
        self.game_list.Bind(wx.EVT_LIST_ITEM_SELECTED, lambda e: None if self.filling else self.game_changed())
        self.game_list.Bind(wx.EVT_CONTEXT_MENU, self.game_context_menu)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(panel, label=_("Pla&n:")), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.what = wx.Choice(panel, size=wx.Size(320, -1))
        self.what.SetName(_("Plan"))
        row.Add(self.what, 1, wx.RIGHT, 12)
        self.start_btn = wx.Button(panel, label=_("&Start"))
        self.pause_btn = wx.Button(panel, label=_("&Pause"))
        self.stop_btn = wx.Button(panel, label=_("S&top"))
        row.Add(self.start_btn, 0, wx.RIGHT, 8)
        row.Add(self.pause_btn, 0, wx.RIGHT, 8)
        row.Add(self.stop_btn)
        box.Add(row, 0, wx.EXPAND | wx.TOP, 12)
        self.start_btn.Bind(wx.EVT_BUTTON, lambda e: self.start())
        self.pause_btn.Bind(wx.EVT_BUTTON, lambda e: self.toggle_pause())
        self.stop_btn.Bind(wx.EVT_BUTTON, lambda e: self.stop())

        f = group(panel, box, _("Status"))
        self.fields = {}
        for key, label in (("activity", _("Activity:")), ("where", _("Location:")), ("hp", _("HP:")),
                           ("mp", _("MP:")), ("pet", _("Pet:")), ("players", _("Players near:")),
                           ("bag", _("Bag:")), ("drop", _("Drop time:")),
                           ("run", _("This run:"))):
            self.fields[key] = f.readonly(label)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(box, 1, wx.EXPAND | wx.ALL, 12)
        panel.SetSizer(outer)
        self.nb.AddPage(panel, _("Bot"))

    def plans_page(self) -> None:
        panel = wx.Panel(self.nb)
        box = wx.BoxSizer(wx.VERTICAL)
        row = wx.BoxSizer(wx.HORIZONTAL)
        left = wx.BoxSizer(wx.VERTICAL)
        self.plan_list = labeled(panel, left, _("Plans and &scripts:"), lambda w: wx.ListBox(w, size=wx.Size(280, -1)), 1)
        row.Add(left, 2, wx.EXPAND | wx.RIGHT, 12)
        right = wx.BoxSizer(wx.VERTICAL)
        self.summary = labeled(panel, right, _("Summary:"), lambda w: wx.TextCtrl(
            w, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP), 1)
        row.Add(right, 3, wx.EXPAND)
        box.Add(row, 1, wx.EXPAND)
        buttons(panel, box, (opens(_("&New plan")), lambda e: self.new_plan()),
                (opens(_("New sc&ript")), lambda e: self.new_script()))
        self.plan_list.Bind(wx.EVT_LISTBOX, lambda e: self.show_summary())
        self.plan_list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self.edit_selected())
        self.plan_list.Bind(wx.EVT_CONTEXT_MENU, self.plan_context_menu)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_plan_key)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(box, 1, wx.EXPAND | wx.ALL, 12)
        panel.SetSizer(outer)
        self.nb.AddPage(panel, _("Plans"))

    def log_page(self) -> None:
        panel = wx.Panel(self.nb)
        box = wx.BoxSizer(wx.VERTICAL)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(wx.StaticText(panel, label=_("Sho&w:")), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.log_filter = wx.Choice(panel, choices=[_("Everything"), _("Important events only")])
        self.log_filter.SetName(_("Show"))
        self.log_filter.SetSelection(0)
        self.log_filter.Bind(wx.EVT_CHOICE, lambda e: self.show_log())
        row.Add(self.log_filter)
        box.Add(row)
        self.log_box = labeled(panel, box, _("&Log:"), lambda w: wx.TextCtrl(
            w, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2), 1)
        buttons(panel, box, (_("Cop&y all"), lambda e: self.copy_log()), (_("Cl&ear"), lambda e: self.clear_log()),
                (_("&Open the log folder"), lambda e: os.startfile(_logs())))
        self.log_box.Bind(wx.EVT_CONTEXT_MENU, self.log_context_menu)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(box, 1, wx.EXPAND | wx.ALL, 12)
        panel.SetSizer(outer)
        self.nb.AddPage(panel, _("Log"))

    # ------------------------------------------------------------ menus
    def build_menu(self) -> None:
        bar = wx.MenuBar()

        def command(label: str, handler: Handler, shortcut: str = "") -> tuple[str, Handler]:
            """Add an accelerator after translating its menu label, not inside the catalog key."""
            return shortcut_label(label, shortcut), handler

        self.action_items: dict[str, wx.MenuItem] = {}
        accelerators: list[wx.AcceleratorEntry] = []

        def add(menu: wx.Menu, entries: list[tuple[str, Handler]], keys: tuple[str, ...] = (),
                *, context: bool = False) -> None:
            # No separator lines: a screen reader counts each one as an entry, so a menu of four
            # read "1 of 5".
            for index, (label, handler) in enumerate(entries):
                item = menu.Append(wx.ID_ANY, label)
                if context:
                    self.Bind(wx.EVT_MENU, self.context_handler(item, handler), item)
                else:
                    self.Bind(wx.EVT_MENU, handler, item)
                shortcut = label.partition("\t")[2]
                if shortcut:
                    entry = wx.AcceleratorEntry()
                    if entry.FromString(shortcut):
                        entry.Set(entry.GetFlags(), entry.GetKeyCode(), item.GetId())
                        accelerators.append(entry)
                if keys:
                    self.action_items[keys[index]] = item

        self.context_menu = wx.Menu()

        def menu(title: str, entries: list[tuple[str, Handler]], keys: tuple[str, ...] = (),
                 *, context: bool = False) -> wx.Menu:
            result = wx.Menu()
            add(result, entries, keys, context=context)
            if context:
                self.context_menu.AppendSubMenu(result, title)
            else:
                bar.Append(result, title)
            return result

        tools_menu = menu(_("&Tools"), [command(_("&Gem Maker"), lambda e: self.open_tool("gem"), "Ctrl+G"),
                           command(_("&Equipment Enhancer"), lambda e: self.open_tool("enhance"), "Ctrl+Shift+E"),
                           command(_("&Daily chores"), lambda e: self.open_tool("chores"), "Ctrl+Shift+D"),
                           command(_("Gathe&ring"), lambda e: self.open_tool("gather"), "Ctrl+Shift+F"),
                           command(_("D&ungeons"), lambda e: self.open_tool("dungeon"), "Ctrl+Shift+G"),
                           command(_("&XP loser"), lambda e: self.open_tool("xploss"), "Ctrl+Shift+X"),
                           command(_("Sell the &collection now"), lambda e: self.sell_collection_now()),
                           command(_("Sell s&hards now"), lambda e: self.sell_shards_now()),
                           command(_("Clean the &bag now"), lambda e: self.clean_bag_now()),
                           command(_("S&tore items now"), lambda e: self.store_items_now()),
                           command(_("Restock &now"), lambda e: self.restock_now()),
                           command(_("Update shard &prices"), lambda e: self.update_shard_prices_now()),
                           command(_("Sound Silencer"), lambda e: self.open_silencer())],
                          ("tools_gem", "tools_enhance", "tools_chores", "tools_gather", "tools_dungeon", "tools_xploss",
                           "tools_collection", "tools_shards", "tools_clean", "tools_store", "tools_restock", "tools_prices",
                           "tools_silencer"),
                          context=True)
        character = menu(_("&Character"), [command(_("&Settings"), lambda e: self.edit_profile(), "Ctrl+P"),
                                             command(_("&Bag and supplies"), lambda e: self.edit_bag(), "Ctrl+B"),
                                             command(_("S&can now"), lambda e: self.scan_now()),
                                             command(_("&Another character"), lambda e: self.edit_other_profile()),
                                             command(_("E&xport character settings"), lambda e: self.export_character_settings()),
                                             command(_("&Import character settings"), lambda e: self.import_character_settings())],
                         ("character_settings", "character_bag", "character_scan", "character_other",
                          "character_export", "character_import"), context=True)
        menu(_("&File"), [command(_("&Settings"), lambda e: self.open_setup()),
                          command(_("Open the &log folder"), lambda e: os.startfile(_logs())),
                          command(_("Open the &results folder"), lambda e: self.open_results_folder()),
                          command(_("E&xit"), lambda e: self.Close())])
        menu(_("&View"), [command(_("&Bot"), lambda e: self.go_tab(0), "Ctrl+1"),
                          command(_("&Plans"), lambda e: self.go_tab(1), "Ctrl+2"),
                          command(_("&Log"), lambda e: self.go_tab(2), "Ctrl+3")])
        run_menu = menu(_("&Run"), [command(_("&Start"), lambda e: self.start(), "F5"),
                         command(_("S&top"), lambda e: self.stop(), "Shift+F5"),
                         command(_("P&ause or go on"), lambda e: self.toggle_pause(), "F6"),
                         command(_("Stop &every bot"), lambda e: self.stop_all(), "Ctrl+Shift+S"),
                         command(_("Wa&lk to a dungeon or map"), lambda e: self.walk(), "Ctrl+W"),
                         command(_("Sche&dules"), lambda e: self.open_schedules(), "Ctrl+Shift+H"),
                         command(_("&Results"), lambda e: self.show_results(), "Ctrl+R"),
                         command(_("Spea&k the results"), lambda e: self.speak_results(), "Ctrl+Shift+R")],
                        ("run_start", "run_stop", "run_pause", "run_stop_all", "run_walk", "run_schedules",
                         "run_results", "run_speak_results"), context=True)
        game_menu = menu(_("&Game"), [command(_("&Mute this game"), lambda e: self.set_game_speech(False), "Ctrl+M"),
                         command(_("&Unmute this game"), lambda e: self.set_game_speech(True), "Ctrl+U"),
                         command(_("Mute e&very game"), lambda e: self.set_game_speech(False, every=True)),
                         command(_("Unmute every &game"), lambda e: self.set_game_speech(True, every=True)),
                         command(_("Open another game &window"), lambda e: self.open_client(), "Ctrl+O")],
                         ("game_mute", "game_unmute", "game_mute_all", "game_unmute_all", "game_open"))
        messages_menu = menu(_("&Messages"), [command(_("&Private messages"), lambda e: self.edit_messages(), "Ctrl+Shift+M"),
                         command(_("C&hat"), lambda e: self.open_chat(), "Ctrl+T"),
                         command(_("Let everyone get replies &again"), lambda e: self.forget_answered())],
                         ("messages_private", "messages_chat", "messages_reset"))
        plans = menu(_("&Plans"), [command(_("&New plan"), lambda e: self.new_plan(), "Ctrl+N"),
                                    command(_("New &script"), lambda e: self.new_script(), "Ctrl+Shift+N"),
                                    command(_("&Edit"), lambda e: self.edit_selected(), "Ctrl+E"),
                                    command(_("D&uplicate"), lambda e: self.copy_plan(), "Ctrl+D"),
                                    command(_("&Delete"), lambda e: self.delete_selected())],
                     ("plans_new", "plans_new_script", "plans_edit", "plans_duplicate", "plans_delete"))
        plan_transfer = wx.Menu()
        add(plan_transfer, [command(_("E&xport plan"), lambda e: self.export_plan()),
                            command(_("&Import plan"), lambda e: self.import_plan())],
            ("plans_export", "plans_import"))
        plans.AppendSubMenu(plan_transfer, _("Import or export plans"))
        self.action_menus = {"run": run_menu, "game": game_menu, "messages": messages_menu,
                             "character": character, "tools": tools_menu,
                             "plans": plans, "plan_transfer": plan_transfer}
        for current in self.action_menus.values():
            current.Bind(wx.EVT_MENU_OPEN, self.sync_action_menus)
        menu(_("&Help"), [command(_("&Quick guide"), lambda e: show_text(self, _("Quick guide"), GUIDE), "F1"),
                          command(_("&User guide (opens in your browser)"), lambda e: self.open_user_guide()),
                          command(_("&Keyboard shortcuts"), lambda e: show_text(self, _("Keyboard shortcuts"), SHORTCUTS)),
                          command(_("Ho&w the game works"), lambda e: show_text(self, _("How the game works"),
                                                                          guide_text("GAME_GUIDE.md"))),
                          command(_("Script &guide"), lambda e: show_text(self, _("Script guide"), guide_text("SCRIPTING.md"))),
                          command(_("&Script commands"), lambda e: self.script_help()),
                          command(_("&Commands for trusted players"),
                           lambda e: show_text(self, _("Commands for trusted players"), messages.__doc__ or "")),
                          command(_("Check for &updates"), lambda e: self.check_updates()),
                          command(_("Contact the &developer"), lambda e: self.contact_developer()),
                          command(_("Join the &Telegram group"), lambda e: self.join_telegram()),
                          command(_("&About Uncle Farmer"), lambda e: info(self, _("Uncle Farmer {v}\nA farming bot for Mist World.",
                                                                        v=__version__)))])
        self.SetMenuBar(bar)
        self.SetAcceleratorTable(wx.AcceleratorTable(accelerators))
        self.Bind(wx.EVT_WINDOW_DESTROY, self.destroy_context_menu)
        self.sync_action_menus()

    def context_handler(self, item: wx.MenuItem, handler: Handler) -> Handler:
        """Popup choices and their accelerators share the current selection's availability checks."""
        def invoke(event: wx.CommandEvent) -> object:
            self.sync_action_menus()
            if item.IsEnabled():
                return handler(event)
            return None
        return invoke

    def destroy_context_menu(self, event: wx.WindowDestroyEvent) -> None:
        if event.GetEventObject() is self:
            self.context_menu.Destroy()
        event.Skip()

    def sync_action_menus(self, event: wx.MenuEvent | None = None) -> None:
        """Make every selection-dependent menu action agree with the focused game and plan."""
        pid = self.selected_pid()
        running = pid in self.runs
        available = pid is not None
        selected = self.active_item()
        enabled = action_menu_states(available=available, running=running, any_running=bool(self.runs),
                                     has_items=bool(self.items), has_messengers=bool(self.messengers), selected=selected)
        for key, value in enabled.items():
            self.action_items[key].Enable(value)
        if event is not None:
            event.Skip()

    def game_context_menu(self, event: wx.ContextMenuEvent) -> None:
        pos = event.GetPosition()
        if pos != wx.DefaultPosition:
            index, _flags = self.game_list.HitTest(self.game_list.ScreenToClient(pos))
            if index != wx.NOT_FOUND:
                state = wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED
                self.game_list.SetItemState(index, state, state)
        self.sync_action_menus()
        try:
            self.game_list.PopupMenu(self.context_menu)
        finally:
            if not self.game_list.IsBeingDeleted():
                self.game_list.SetFocus()

    def plan_context_menu(self, event: wx.ContextMenuEvent) -> None:
        pos = event.GetPosition()
        if pos != wx.DefaultPosition:
            index = self.plan_list.HitTest(self.plan_list.ScreenToClient(pos))
            if index != wx.NOT_FOUND:
                self.plan_list.SetSelection(index)
        item = self.listed_item()
        plan = bool(item and item[0] == "plan")
        can_run = self.selected_pid() is not None and self.selected_pid() not in self.runs
        popup_actions(self.plan_list, [
            (_("&Run selected"), lambda e: self.start(item=self.listed_item()), bool(item) and can_run),
            (shortcut_label(_("&Edit"), "Ctrl+E"), lambda e: self.edit_selected(), bool(item)),
            (shortcut_label(_("D&uplicate"), "Ctrl+D"), lambda e: self.copy_plan(), plan),
            (_("E&xport"), lambda e: self.export_plan(), plan),
            (_("&Delete"), lambda e: self.delete_selected(), bool(item)),
            (shortcut_label(_("&New plan"), "Ctrl+N"), lambda e: self.new_plan(), True),
            (shortcut_label(_("New &script"), "Ctrl+Shift+N"), lambda e: self.new_script(), True),
            (_("&Import"), lambda e: self.import_plan(), True),
        ])

    def log_context_menu(self, _event: wx.ContextMenuEvent) -> None:
        start, end = self.log_box.GetSelection()
        popup_actions(self.log_box, [
            (_("Copy &selection"), lambda e: self.copy_log_selection(), start != end),
        ])

    def join_telegram(self) -> None:
        from .contact import join_telegram
        join_telegram(self)

    def contact_developer(self) -> None:
        from .contact import ContactDialog
        with ContactDialog(self) as d:
            d.ShowModal()

    def open_silencer(self) -> None:
        pid = self.selected_pid()
        if pid is None:
            return
        window = self.silencer_windows.get(pid)
        if window is None:
            name = self.character(pid)
            def closed() -> None:
                self.silencer_windows.pop(pid, None)
            window = SilencerDialog(self, pid, settings.profile_display(name) if name else None, closed)
            self.silencer_windows[pid] = window
        try:
            window.ShowModal()
        finally:
            if window:
                window.finish()
                window.Destroy()

    def go_tab(self, i: int) -> None:
        self.nb.SetSelection(i)
        (self.game_list, self.plan_list, self.log_box)[i].SetFocus()

    def on_close(self, evt: wx.CloseEvent) -> None:
        """Stop what runs, let go of the hotkeys and the timer, and go. Each step is in
        teardown.log; one that fails is written down there and the others still happen, so the
        window always closes. __main__ writes the END once the main loop is over."""
        down = applog.teardown
        down.begin("close requested (%s)" % (self.close_reason or (
            "the window" if evt.CanVeto() else "Windows is ending the session")))
        if self.runs:
            if not ask(self, _("A bot is running. Stop it and quit?")):
                evt.Veto()
                down.end("cancelled: the player kept the bots running")
                return
            runs = list(self.runs.values())
            with down.step("ask %d bot%s to stop" % (len(runs), "" if len(runs) == 1 else "s"), must=False):
                for run in runs:
                    run.stop()
            with down.step("wait for the bots to end", must=False):
                for run in runs:
                    run.join(BOT_STOP_WAIT)
                    if run.is_alive():
                        down.problem("the bot of game %d still runs after %g s" % (run.pid, BOT_STOP_WAIT))
        pending = getattr(self, "pending_update", None)
        if pending is not None and evt.CanVeto() and (any(run.is_alive() for run in self.runs.values())
                                                     or pending.process.poll() is not None):
            evt.Veto()
            down.end("update cancelled: shutdown is not safe (a bot is still running or the copier stopped)")
            return
        with down.step("ask the private messages and chat readers to stop", must=False):
            for m in self.messengers.values():
                m.stop()
            for f in self.chats.values():
                f.stop()
        with down.step("stop the sound readers", must=False):
            restorer = getattr(self, "sound_restorer", None)
            if restorer is not None:
                restorer.close()
            for window in list(getattr(self, "silencer_windows", {}).values()):
                window.Close()
        with down.step("release the hotkeys", must=False):
            for hotkey in self.hotkeys:
                if not self.UnregisterHotKey(hotkey):
                    down.problem("Windows didn't take back hotkey %#x" % hotkey)
        with down.step("stop the game list timer", must=False):
            self.timer.Stop()
        timer: wx.Timer | None = getattr(self, "schedule_timer", None)   # none if the window never got that far
        if timer is not None:
            with down.step("stop the schedules timer", must=False):
                timer.Stop()
        with down.step("destroy the window", must=False):
            self.destroyed = self.Destroy()  # only successful destruction authorizes the paused updater


def _logs() -> str:
    return paths.LOGS


SHORTCUTS = """KEYBOARD SHORTCUTS

Anywhere, even inside the game
  Pause               Start or stop the bot (in a game window: that game's bot)
  Shift+Pause         Speak the results of the game in front

Main window
  Ctrl+1, 2, 3        Bot, Plans and Log tabs (Ctrl+Tab also moves between tabs)
  F5                  Start the selected game's bot
  Shift+F5            Stop it
  F6                  Pause it where it is, or let a paused bot go on (you can play by hand meanwhile)
  Ctrl+Shift+S       Stop every bot
  Ctrl+W              Walk to a dungeon entrance or a map (Pause stops the walk)
  Ctrl+Shift+H        Schedules: plans and scripts started at set times
  Ctrl+R              Results
  Ctrl+Shift+R        Speak the results
  Ctrl+M              Mute the selected game (Ctrl+U lets it talk again; Game menu: every game)
  Ctrl+O              Open another game window
  Ctrl+G              Gem Maker
  Ctrl+Shift+E        Equipment Enhancer
  Ctrl+Shift+D        Daily chores
  Ctrl+Shift+F        Gathering: fishing, mining or collecting herbs
  Ctrl+Shift+G        Dungeons: Scorpion Cave and Spider cave, once a day
  Ctrl+Shift+X        XP loser: die to guards so the next level stays far away
  Ctrl+P              Character settings
  Ctrl+B              Bag and supplies
  Ctrl+N              New plan
  Ctrl+Shift+N        New script
  Ctrl+E              Edit the selected plan
  Ctrl+D              Duplicate the selected plan
  Ctrl+Shift+M        Private messages
  Ctrl+T              Chat: read and write the game's chat while the bot farms
  F1                  Quick guide

Games list
  Applications key    The game's menu: Tools, Character and Run submenus
  Shift+F10           The same context menu; arrows open submenus, Escape closes them

Plans tab
  Enter               Edit the selected plan or script
  Delete              Delete it
  Applications key    Its menu: Run selected, Edit, Duplicate, Export, Delete, New, Import

Log tab
  Applications key    Copy the selected text

Plan editor, Farming spots
  Enter               Edit the selected spot
  Delete              Remove it
  Applications key    Its menu: Add, Edit, Move up, Move down, Remove

Schedules
  Enter               Edit the selected schedule
  Delete              Delete it
  Applications key    Its menu: Add, Edit, Turn on or off, History, Delete

Gathering, Gangs and Your places
  Delete              Remove the selected gang or place
  Applications key    Its menu: move a gang up or down, rename or remove a place

Bag and supplies, Shards and Other items
  Applications key    Move the selected item to another list

Script editor
  F1                  Script commands
  F5                  Check the script
  Ctrl+S              Save
"""


GUIDE = """UNCLE FARMER - QUICK GUIDE

1. FIRST TIME
File, Settings, Game tab: choose the Mist World folder (or press "Find the running game" while it
runs), then press Install and restart the game. Do this once per computer.

2. YOUR CHARACTER
Select your game in the Games list and press the Applications key or Shift+F10, or right-click it.
Its context menu holds Tools, Character and Run. These submenu names are used throughout this
guide. Their keyboard shortcuts still work without opening the menu. Game and Messages stay in
the menu bar for sound, chat and private messages.
Log in to the game. The bot scans the character by itself: class, skills, keys, potions, fusion
beasts and pets. Character, Settings (Ctrl+P) holds the choices that are yours to make: how to
fight, which potion, which beast, which pets. Keys and timings are under Advanced; most players
never need them.

3. THE BAG
Character, Bag and supplies (Ctrl+B). Shards tab: sort every shard into Throw away, Keep or Sell
with the Move buttons (or the Applications key). To make gems, use Tools, Gem Maker. Other items: Keep, Store, Sell or Throw away.
Supplies: tick the potions and food to refill, and from where. Full bag: what happens when the bag
is full, and stopping when the day's drop time runs out.

TOOLS
Tools, Gem Maker (Ctrl+G): make a gem (choose which, its level and how many, or as many as you
can; it gets more Level 1 shards from the storehouse or the Shard Market when you let it), or make
the most of your bag (every shard into gems, then every colour up as far as it goes). Tools, Equipment Enhancer (Ctrl+Shift+E): your
equipment up to +N (+12 at most), with protection runes; it makes the Enhance Crystals from crystal
shards it takes from the storehouse or buys at the Shard Broker, keeps a stock of them in the bag
if you want, and makes more when they run out. Use
your own gang's craftsmen (cheaper), another gang's by its name, or the nearest city's. Press Check only first: the bot walks there,
reads the real prices and chances, says what it would do, and spends nothing.
Tools, Daily chores (Ctrl+Shift+D): once a game day (from 00:00 GMT) the bank's incomes, hunting
bounties, the free rebirths of the pet you choose, the gang donation, and construction builds at
every place the gang has to build (the inner and outer halls, the highland). Sharing arnebia in a
secret room: once in each half hour, 5 a day; the bot goes in just before a half hour, shares, shares
again as it starts, and leaves, and while farming it leaves for that and comes back by itself. Tick
"at the start of the first farming run" and a farming run does the chores first.
Tools, Gathering (Ctrl+Shift+F): fishing, mining or collecting herbs, whichever skill the character
has. First gangs' Lakes, Mining Areas or Herbal Gardens: your own gang's and other gangs' by name,
in the order you list them (each once a game day, half an hour inside), then outside: at a place of your own (stand where you gather by hand and press "Add where I stand")
or one the bot knows, the best area for your level. It fights whatever attacks it, starts again,
sells the collection to the Aquaculture, Ore or Herb Buyer when the bag is full and comes back, and
stops when Vitality runs out.
The game's Tools submenu (select it in the Games list, then the Applications key or Shift+F10) runs these
jobs right away. Sell the collection now: sells it from wherever you are. Sell shards now: sells
the shards the bag manager says to sell, at this city's Shard Market (or the nearest one). Clean
the bag now: throws away, where you stand, only what is on the bag manager's throw-away list,
after you say yes. Update shard prices: reads the nearest Shard Market's prices into the price
list the bag manager and the results use; a price that can't be read keeps its old value. Store
items now: puts into the storehouse what is on the bag manager's storage list (Move to
storehouse), keeping what each rule keeps, and nothing else. Restock now: fills the enabled
supplies to their targets, withdrawing or buying only what is missing, even when they are not
down to their refill points yet.
Character, Settings, Triggers: tick any of these jobs (and Gathering) to run by themselves before
farming starts, after farming ends, or both - each stage has its own ticks.
Tools, Dungeons (Ctrl+Shift+G): Scorpion Cave and Spider cave, each once a game day, for as many
kills as their 15 minutes give. Before setting out it tops up what you set on the Supplies tab (the
pet's blue potions and Rice Rolls, your blue and red potions) from the storehouse or the shop; then
it rides to the entrance, goes in, goes round the whole cave fighting whatever is in reach (area
skills on two or more close together, potions instead of resting, the pet kept out and fed) until
the game moves it out, and ends where the Where to end tab says, as a plan does.
Tools, XP loser (Ctrl+Shift+X): for a character that shouldn't level up. Say how much experience
the next level should need at least (or how much to lose); the bot finds a guard - in sight, where
one was seen before, or in the nearest town - switches the PK mode to all mode, hits the guard once
and lets it kill the character (no potions, heals or fighting back), respawns in the city and goes
again until the character sheet says so, or after the most deaths you allow. The pet is put away
first and the PK mode put back at the end. Not for a black-name character: it can lose worn gear
when it dies. The Triggers tab can run it before or after farming.

UPDATES
At start Uncle Farmer looks on GitHub for a new version; if there is one it says what's new and
asks. Yes: it downloads it, closes, updates and starts again, keeping your characters, plans,
scripts and settings. Close the games and stop the bots first. Help, Check for updates looks any
time; Settings, Updater turns the start-up check off and picks the release channel.

WALKING
Run, Walk to a dungeon or map (Ctrl+W). Dungeon entrance tab: the dungeons whose entrance NPC the
bot knows (a teleport circle or the NPC at the cave mouth); it walks up to the NPC and, if you
like, opens its menu so you choose. Map tab: any map of the open world (the ones you can walk to and
back from; closed maps and the maps inside dungeons aren't listed), or a cell on it. Show the route says the way
before you go. The whole way it rides your fastest Swift fusion beast, in towns and through
monster ground alike, and it doesn't stop to fight; potions still keep your HP up. Pause stops it.

4. A PLAN
Plans tab, New plan (Ctrl+N). Three tabs, three questions. Where to farm: one or more farming spots
(a map, how to move around, which monsters); with several, it goes round them in turn or through
them once. When to stop: a time, a clock time, a kill count or an item running low (the drop time,
a full bag and deaths stop it by themselves). Where to end: back where you started it (the
default), a place you choose, home with the hearthstone, the nearest map without monsters, or
where it is - every end goes there. In the Plans list, a plan's own menu (the Applications key)
has Run selected, Edit, Duplicate, Export and Delete.

5. RUN IT
Bot tab: choose the game in the Games list, choose the plan, press Start (F5). The Pause key
starts and stops the bot from anywhere, even inside the game. The Status fields show what the bot
is doing, HP, MP, the bag and the drop time. Important events are spoken with NVDA, and the Log tab
keeps everything.

6. MORE THAN ONE GAME
Game, Open another game window (Ctrl+O). Every game shows in the Games list with its character;
each runs its own plan. Inside a game window, Pause starts and stops that game's bot.
Ctrl+Shift+S stops them all. Each game needs about 1 GB of memory.
Run, Schedules (Ctrl+Shift+H) starts a plan or script for a character at a set time: once, every
day or on chosen days. Each time runs once; a time missed while Uncle Farmer was closed doesn't run
later, and a game busy with another run waits up to 15 minutes. History says what happened.

7. RESULTS
Run, Results (Ctrl+R): arnebia, shards, contribution, experience, levels and items, for this run,
today, a week, a month or ever, and the arnebia the items used up cost (shop items at their fixed
price, shards at the last Shard Market price, an estimate). Shift+Pause speaks a short summary from
anywhere.

8. PRIVATE MESSAGES
Messages, Private messages (Ctrl+Shift+M). Strangers get a few of your reply lines, then a goodbye and
silence. Trusted players can send commands; send "help" to the character to get the list.

9. SCRIPTS
For anything a plan can't do: Plans tab, New script. Help, Script commands lists every command.
Questions, ideas or donations: Help, Contact the developer.
Talk with other players: Help, Join the Telegram group.

SAFETY
Stop always lets go of every key. The bot stops by itself when it gets stuck again and again, dies
too often, or can't read the game. If the bot says it can't find the game, a tool such as mwMod
may have removed the agent: open File, Settings and press Install again.
"""
