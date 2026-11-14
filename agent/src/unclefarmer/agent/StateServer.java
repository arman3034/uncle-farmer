package unclefarmer.agent;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.lang.management.ManagementFactory;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.SecureRandom;

/**
 * Exposes the world state to a controller outside the JVM, over a line protocol on loopback.
 *
 * Connecting: the server takes the first free port in {@link #FIRST_PORT}..{@link #LAST_PORT}, so
 * several game clients can run side by side, and makes up a fresh random secret every launch. Both
 * go in the port file `agent.<pid>.port` in the output folder, as "port pid secret". The first line
 * of every connection must be `auth <secret>`; anything else is refused and the connection closed.
 * That keeps other programs on this PC (and web pages poking at localhost) from driving the game.
 * tools/agentlink.py does all of this for the Python side.
 *
 * After that, send a command line, get one line back:
 *
 *   state          -> the JSON snapshot from {@link World} (built from packets)
 *   mem            -> the JSON snapshot from {@link Memory} (read from the game's own objects)
 *   mem <section>  -> one part of it: map, self, entities, bag, slots, modes, ui or state
 *                     (state is map+self+entities, the lean snapshot the bot reads each iteration)
 *   memprobe       -> our own entity field by field, beside the packet view, to check the field map
 *   memfind <n>    -> every field under the world holding n (or 'text'), to locate a stat
 *   menu           -> the open menu's verified layout (Menus): shard_market, shard_trade, potion_shop
 *                     or unknown, each item's row, id and price, and whether it is the verified one
 *   ping           -> pong
 *   health         -> whether the game is still sound: out-of-memory errors so far, threads, heap
 *   version        -> "mwagent <VERSION>"; the bot refuses an agent older than it needs
 *   keys           -> whether the game's key handler is resolved
 *   speech [on|off] -> the game's own speech: report, restore or silence it (sounds keep playing)
 *   voicefix [on|off] -> the game's voice message player: mended (on, the default) or as the game plays it
 *   wear [since]   -> equipment wear warnings from combat (about to break / broken) after since (ms)
 *   pms [after] [ms] -> private messages received after message number `after`, oldest first;
 *                     with ms, waits up to that long for one to arrive (answers the moment it does)
 *   pm <id> <text> -> send a private message, as the game's private chat line does (armed)
 *   closegame      -> close the game, as its window's close button does (armed)
 *   arm            -> allow this connection to act; everything below needs it
 *   team             -> teammates on our map, as the game answered the quick phrase "/6"
 *   phrase <slot> <text> -> set quick phrase 1-12 the way its window does (armed)
 *   pick <layout> <id> [buy|sell] -> choose that item of a verified menu by its index, after
 *                     checking it (armed); `refused: <why>` and nothing pressed otherwise
 *   shardsell <id> <count> -> choose a verified shard, sell it, and enter its quantity as one
 *                     stateful local transaction (armed)
 *   sharddirect <id> <count> -> send one verified sale command from the currently verified Shard
 *                     Market (armed)
 *   sharddirectall <id> <count> ... -> validate all entries, then send that market plan in order
 *                     without closing the market between sales (armed)
 *   discarddirectall <uid> ... -> validate every requested bag unit, then send all direct discard
 *                     requests in order (armed)
 *   xpbonus pause|resume -> pause or resume the running experience card as its sheet entry
 *                     does, only when a fresh sheet shows it in the other state (armed)
 *   guardmods on|off -> while on, the player's own Shift/Ctrl/Alt are not recorded in this game
 *                    (the connection closing turns it off again)
 *   key <k> [ms]   -> press and release a key, held for ms (default 60). Names: a..z 0..9,
 *                     num0..num9, up down left right, space enter esc tab backspace, f1..f12,
 *                     . , ; / ' - = [ ] \, lctrl rctrl alt shift. Combinations: lctrl+alt+up
 *   keydown <k> / keyup <k> / keysup -> hold, release, release everything. Held keys are
 *                     released automatically when this connection closes.
 *
 * Bound to 127.0.0.1 only, so nothing off this machine can reach it.
 */
final class StateServer implements Runnable {

    /** Bumped whenever a command or reply changes, so the bot can tell a stale agent apart. */
    static final int VERSION = 67;   // 4: dialog, real selected target; 5: input/type/typeenter/typeclear; 6: mem beasts/equipment/skills/pets/bagfull, input mode; 7: typeesc, attack_page; 8: capslock key; 9: casts, bag item type; 10: F1 options in mem modes; 11: ` key, sheet load/fusion/counter; 12: drop time; 13: several clients at once (GamePorts), window titles; 14: speech on/off, vitals (R key), sheet contribution/xp_needed/merit; 15: pms, pm, closegame; 16: pms waits for a message; 17: a failing command answers {"ok":false,"error"} instead of dropping the connection, and a closing connection lets go only of the keys it held; 18: casts are read from lines that carry equipment wear, and `wear` reports that wear; 19: vitals carry how many buffs and debuffs are on us; 20: speech off also silences the voices themselves (screen reader, SAPI, own voices), so the combat announcer goes quiet too; 21: speech off also gates the screen reader's cancel, so a silenced game no longer cuts the player's NVDA off; 22: `mem self` points (T key: rage/marks/combos, fusion, pet amiability), entities carry the game's side and kind npc/monster/other; 23: a key we send no longer counts as Left Ctrl + key when the player is holding Left Ctrl in another window (it re-bound hotkeys), and the bot's keys go straight onto the game's input queue instead of through its keyboard hook with focus faked; 24: the points key's answer is read at last (its one-byte request was dropped, so `mem self` never had rage, marks or combos); 25: `said`: the game's last spoken lines (an NPC that answers without a menu); 26: `guardmods on|off`: the player's Shift/Ctrl/Alt are not recorded in this game while a run has it on (they turned the bot's keys into Ctrl+key hotkey bindings); 27: `team` (teammates on our map, from the "/6" quick phrase's answer) and `phrase <slot> <text>`; 28: `casts` rows carry the cast's hit results (critical hits, dodges) when the game sent them; 29: with guardmods on, the game's keyboard hook still sees the player's own Alt (and Shift, Ctrl) - only the hook - so Alt+Tab leaves the game again; the bot's keys still never pick them up; 30: `casts` also carries the monster deaths the game reported (`deaths`: [id, ms]) and keeps 256 casts, so the bot counts every kill it had a hand in; 31: `mem self` carries the pet's HP and MP (pet_vitals, the pet HP key's answer) and its description (pet_info: amiability, HP and MP with their maximums, from the pet panel); 32: `chat <after> [ms]` (the chat channels' lines, in memory only) and `say <channel> <text>` (a line through the game's own sender, no keys); 33: `say 6` (the private channel players join, not private messages), and `say 5`/`say 6` go to the international room and private channel the game's chat model has joined; 34: `pms` also carries the private messages we sent (typed in the game or by the bot, "mine": true, id and name = who it went to), and `idof <name>` finds a player's id from the players seen and messaged this game; 35: every line we send (`say`, `pm`) goes through one queue that waits for the game's own last-sent time (2 s, 3 s on global, shared by all channels and private messages), resends a line the game dropped, and cuts a text over 200 characters into parts at a space; 36: `health` (out-of-memory errors in any game thread or the agent, thread count, heap), so the bot tells a game that ran out of memory and froze from a stuck walk; 37: `mem state` (map+self+entities without bag/slots/modes/ui), and TCP_NODELAY on both ends of the reply; 38: `keysup` and `keyup` release only the keys this connection holds, so one controller in a game can't drop another's; 39: `ask vitals` / `ask petvitals` send the own-HP and pet HP keys' request without a key (the same bytes through the game's own connection); 40: `use <uid>` uses a bag item as its use key and hotkeys do (no arrow keys), `select <id>` makes a monster the game's target as the target keys do; 41: `select` takes only what the target keys would (their reach, the game's line of sight with door edges, unselectable flags) and answers `refused: <id> <why>` otherwise; 42: voice messages - `chat` and `pms` rows carry "voice": <name> for one, `voice play <name>` decodes it with the game's codec into a WAV file, `voice record`, `voice send <3|4>`, `voice send pm <id>` and `voice cancel` record from the game's microphone and send it as the game does; 43: `ask sheet` asks for our character sheet as the sheet key does and keeps the answer off the screen (read into `mem self` sheet, no window), and two connections pressing one key at once can't both count it as theirs; 44: every cast in `casts` says whom it struck and their HP after it ("targets"), other players' casts too; 45: `slot <n> [sustain] [lock]` does what attack key n does on the page that is up, through the game's own key method, without the keyboard; 46: a `slot` press is let go 30 ms later as the key is (world.a(0L)), so the game no longer takes the attack key for held down and stops every walk after it; 47: a key tap (or a combination's modifier) another connection is holding is no longer let go, a held key's repeat can't put it down again just after it was let go, `use` retries a bag the game is changing, `state`/`team` numbers keep a decimal point in every locale, and positions survive the clock's 50-day turn; 48: the game's folder goes into game_folder.txt beside the logs, so the app finds the game it is installed in, and into agent.<pid>.folder for that game alone (the copy a character's phrases are in); 49: `mem skills` carries each profession skill's rank (profession_ranks, from the login list the client drops it from), so gathering knows how far the character's Fishing, Mining or Collect Herbs goes; 50: `mem self` sheet carries the Vitality left (the sheet's "Vitality 44.7"), which gathering spends; 51: the game's voice player opens each message at its own rate and skips a half-read one (VoicePlayer), so a second game no longer plays every voice message slow and deep; `voicefix [on|off]` switches that off and on; 52: a Priest's points key request (op=23 with the PK mode byte) counts too, so a Priest's `mem self` points carry the pet's amiability; 53: `menu` (the open menu's verified layout: shard_market, shard_trade, potion_shop or unknown, with each item's row, id and price) and `pick <layout> <id> [buy|sell]` (choose that item by its verified index, after checking the whole menu, the row's item and the buy/sell command, or answer `refused: <why>` and touch nothing); 54: a channel chat line's sender name is read from where the game's own reader puts it (after the sender's id), so an id whose last byte is a letter or digit no longer joins the name ("2magoestelar"); 55: `dialog` gives the open menu's signature ("sig", its whole content) and `choose <row> <col> <sig>` chooses that entry of any menu as Enter does, with no walk down the list a key at a time, when the menu still has that signature, or answers `refused: <why>` and touches nothing; 56: `number <n>` clears, types and submits a quantity box in one event-queue turn, `shardsell <id> <count>` (one verified market row -> sell -> quantity) and `sharddirect`/`sharddirectall <id> <count> ...` (with the verified Shard Market open, send the sale command the game itself sends after the quantity box, for each pair, after checking every row first); 57: `discarddirectall <uid> ...` (a uid once per unit) checks every unit against one bag snapshot, then discards each stack as the game's discard does, one op=18 packet with minus the count; 58: `server` answers the port of the game's own connection (which server the game is on), reading it without sending anything; 59: `cast <skill> <target>` casts one of our corpse skills (Draw Blood, Skinning, Cut Flesh) at a fresh corpse through the game's own cast method, after the profession key's own checks (a learned corpse skill, a creature at exactly 0 HP within 20 tiles in sight), with no key and no selected target; or answers `refused: <why>` and sends nothing; 60: `mem self` sheet carries the experience card (exp_bonus percent, exp_paused, exp_seconds left) and Morality, and `xpbonus pause|resume` pauses or resumes the card as its sheet entry does, only when a fresh sheet shows it in the other state; 61: `cast` is held as the profession key is (sent again every 60 ms until our cast comes back, the corpse changes or 1.2 s pass) and always let go (world.a(0L)), so it no longer leaves our character marked as attacking - which made every walk fail until the next fight - and a cast sent in the pause after a kill is sent again; 62: `cast` takes only a corpse within 4.5 tiles (the server answered no harvest from further, measured live) and casts standing, never walking there; only that skill's own report ends the hold (any cast of ours did, so the last shots of the fight stopped it at once); 63: sound request observation, WATCH/MUTE filters, connection-scoped listening and live audio muting; 64-67: `loginaccount` (the saved account the game is on or has selected), `autologin <email> <id>` (armed: start that saved account's own login and choose that character in the picker, then wait for its loaded world) and `autologinstatus`

    static final int FIRST_PORT = 17311;
    static final int LAST_PORT = 17330;

    /** A controller that goes this long without a command is dropped. */
    private static final int IDLE_MS = 120000;

    private final String secret;

    private StateServer(String secret) {
        this.secret = secret;
    }

    static void start() {
        byte[] raw = new byte[16];
        new SecureRandom().nextBytes(raw);
        StringBuilder hex = new StringBuilder(32);
        for (byte b : raw) hex.append(String.format("%02x", b & 0xFF));

        Thread t = new Thread(new StateServer(hex.toString()), "mwagent-state");
        t.setDaemon(true);
        t.start();
    }

    @Override
    public void run() {
        ServerSocket server = bind();
        if (server == null) return;
        int port = server.getLocalPort();
        Log.info("state server listening on 127.0.0.1:" + port);
        writePortFile(port);

        while (true) {
            try {
                final Socket socket = server.accept();
                // One request, one reply: never let Nagle hold a reply back waiting for more.
                socket.setTcpNoDelay(true);
                // One thread per controller, so a bot holding its connection open doesn't lock out
                // a second tool (mem.py, the radar) at the same time.
                Thread t = new Thread(new Runnable() {
                    @Override
                    public void run() {
                        try {
                            socket.setSoTimeout(IDLE_MS);
                            serve(socket);
                        } catch (Throwable ignored) {
                            // The peer went away or idled out.
                        } finally {
                            close(socket);
                        }
                    }
                }, "mwagent-conn");
                t.setDaemon(true);
                t.start();
            } catch (Throwable t) {
                Log.error("state server accept", t);
            }
        }
    }

    /** The first free port of ours, on 127.0.0.1 only (AgentTests checks it never listens wider). */
    static ServerSocket bind() {
        for (int port = FIRST_PORT; port <= LAST_PORT; port++) {
            try {
                return new ServerSocket(port, 8, InetAddress.getByName("127.0.0.1"));
            } catch (Throwable t) {
                // Taken, most likely by another game client: try the next one.
            }
        }
        Log.info("state server: no free port in " + FIRST_PORT + ".." + LAST_PORT);
        return null;
    }

    /** "port pid secret", removed again when the game exits. */
    private void writePortFile(int port) {
        try {
            String pid = ManagementFactory.getRuntimeMXBean().getName().split("@")[0];
            Path file = Log.dir().resolve("agent." + pid + ".port");
            Files.write(file, (port + " " + pid + " " + secret).getBytes(Protocol.UTF8));
            file.toFile().deleteOnExit();
        } catch (Throwable t) {
            Log.error("port file", t);
        }
    }

    /** One connection may issue several commands; it ends when the peer closes or goes quiet. */
    private void serve(Socket socket) throws Exception {
        BufferedReader in = new BufferedReader(
                new InputStreamReader(socket.getInputStream(), Protocol.UTF8));
        OutputStream out = socket.getOutputStream();
        boolean[] armed = {false};
        boolean[] guarded = {false};      // this connection turned the modifier guard on (guardmods)
        // Keys this connection holds down. Only these are let go when it closes: the bot and the
        // private-message helper both hold armed connections, and one closing must not stop the
        // other's character mid-walk.
        java.util.Set<String> mine = new java.util.HashSet<String>();

        String line = in.readLine();
        if (line == null) return;
        if (!authorised(line.trim())) {
            out.write("refused: send 'auth <secret>' first\n".getBytes(Protocol.UTF8));
            out.flush();
            return;
        }
        out.write("ok\n".getBytes(Protocol.UTF8));
        out.flush();

        try {
            while ((line = in.readLine()) != null) {
                String reply;
                try {
                    reply = handle(line.trim(), armed, mine, guarded);
                } catch (Throwable t) {
                    // One bad command (a stray number, a game object caught mid-change) must not
                    // drop the connection: the bot would see "closed" and stop the whole run.
                    Log.error("command: " + line.trim(), t);
                    reply = "{\"ok\":false,\"error\":\"" + Protocol.jsonEscape(String.valueOf(t)) + "\"}";
                }
                if (reply == null) break;
                out.write((reply + "\n").getBytes(Protocol.UTF8));
                out.flush();
            }
        } finally {
            // A controller that pressed keys and then went away (crash, Ctrl+C, timeout) must not
            // leave the character walking.
            for (String k : mine) Keys.up(k);
            if (!mine.isEmpty()) Log.info("ACTION released " + mine.size() + " key(s) a closed connection held");
            if (guarded[0]) Keys.guardModifiers(false);
            SoundControl.unlisten(mine);
        }
    }

    /** Constant-time, so the secret can't be guessed a character at a time from reply timing. */
    private boolean authorised(String line) {
        if (!line.startsWith("auth ")) return false;
        byte[] given = line.substring(5).trim().getBytes(Protocol.UTF8);
        return MessageDigest.isEqual(given, secret.getBytes(Protocol.UTF8));
    }

    /** The same as the window's close button: the game exits (it sets EXIT_ON_CLOSE). */
    private static String closeGame() {
        final java.awt.Frame win = Memory.window();
        if (win == null) return "error: no game window";
        Log.info("closing the game on request");
        java.awt.EventQueue.invokeLater(new Runnable() {
            @Override
            public void run() {
                try {
                    win.dispatchEvent(new java.awt.event.WindowEvent(win, java.awt.event.WindowEvent.WINDOW_CLOSING));
                } catch (Throwable ignored) {
                    // The window closed while this event was queued.
                }
            }
        });
        return "closing";
    }

    static String handle(String command, boolean[] armed, java.util.Set<String> mine, boolean[] guarded) {
        String[] parts = command.split("\\s+");
        String verb = parts[0].toLowerCase();

        if (verb.equals("state")) return World.snapshot();
        if (verb.equals("ping")) return "pong";
        if (verb.equals("soundstatus")) return SoundControl.status();
        if (verb.equals("sounds")) return SoundControl.since(parts.length > 1 ? Long.parseLong(parts[1]) : 0L);
        if (verb.equals("soundwatch")) return SoundControl.watch(command.substring(verb.length()).trim());
        if (verb.equals("soundmute")) return SoundControl.mute(command.substring(verb.length()).trim());
        if (verb.equals("soundlisten")) return SoundControl.listen(mine, command.substring(verb.length()).trim());
        if (verb.equals("server")) return Ask.server();
        if (verb.equals("health")) return Health.snapshot();
        if (verb.equals("version")) return "mwagent " + VERSION;
        if (verb.equals("loginaccount")) return AutomaticLogin.account();
        if (verb.equals("mem")) {
            return parts.length > 1 ? Memory.section(parts[1].toLowerCase()) : Memory.snapshot();
        }
        if (verb.equals("dialog")) return Dialogs.read();
        if (verb.equals("menu")) return Dialogs.menu();
        if (verb.equals("input")) return TextInput.state();
        if (verb.equals("casts")) return World.casts(parts.length > 1 ? Long.parseLong(parts[1]) : 0L);
        if (verb.equals("wear")) return World.wear(parts.length > 1 ? Long.parseLong(parts[1]) : 0L);
        if (verb.equals("team")) return Team.snapshot();
        if (verb.equals("said")) return Said.since(parts.length > 1 ? Long.parseLong(parts[1]) : 0L);
        if (verb.equals("memprobe")) return Memory.probe();
        if (verb.equals("memfind")) return MemFind.find(command.substring(verb.length()));
        if (verb.equals("quit")) return null;

        // Anything that sends must be armed first, per connection. A stray script that connects
        // and starts issuing commands does nothing until it says so explicitly.
        if (verb.equals("arm")) {
            armed[0] = true;
            return "armed";
        }

        if (verb.equals("autologin")) {
            if (!armed[0]) return "refused: send 'arm' first";
            return AutomaticLogin.start(parts.length > 1 ? parts[1] : "", parts.length > 2 ? parts[2] : "");
        }
        if (verb.equals("autologinstatus")) return AutomaticLogin.status();

        if (verb.equals("keys")) return Keys.status();
        if (verb.equals("pms")) {
            try {
                long after = parts.length > 1 ? Long.parseLong(parts[1]) : 0L;
                return parts.length > 2 ? PrivateChat.await(after, Long.parseLong(parts[2]))
                        : PrivateChat.since(after);
            } catch (NumberFormatException e) {
                return "bad number in: " + command;
            }
        }
        if (verb.equals("idof")) {
            String[] who = command.trim().split("\\s+", 2);
            return who.length < 2 ? "0" : PrivateChat.idOf(who[1]);
        }
        if (verb.equals("chat")) {
            try {
                long after = parts.length > 1 ? Long.parseLong(parts[1]) : 0L;
                return GameChat.since(after, parts.length > 2 ? Long.parseLong(parts[2]) : 0L);
            } catch (NumberFormatException e) {
                return "bad number in: " + command;
            }
        }
        if (verb.equals("say")) {
            if (!armed[0]) return "refused: send 'arm' first";
            String[] sy = command.trim().split("\\s+", 3);
            if (sy.length < 3) return "error: say <0-6> <text>";
            try {
                return GameChat.say(Integer.parseInt(sy[1]), sy[2]);
            } catch (NumberFormatException e) {
                return "bad number in: " + command;
            }
        }
        // Sending a private message and closing the game act on the game: armed connections only.
        if ((verb.equals("pm") || verb.equals("closegame")) && !armed[0]) return "refused: send 'arm' first";
        if (verb.equals("pm")) {
            String[] pm = command.trim().split("\\s+", 3);
            if (pm.length < 3) return "error: pm <id> <text>";
            try {
                return PrivateChat.send(Integer.parseInt(pm[1]), pm[2]);
            } catch (NumberFormatException e) {
                return "bad number in: " + command;
            }
        }
        if (verb.equals("closegame")) return closeGame();
        if (verb.equals("voice")) {
            String what = parts.length > 1 ? parts[1].toLowerCase() : "";
            if (what.equals("play")) return parts.length > 2 ? Voice.play(parts[2]) : "error: voice play <name>";
            if (what.equals("status")) return Voice.status();
            if (!armed[0]) return "refused: send 'arm' first";
            if (what.equals("record")) return Voice.record();
            if (what.equals("cancel")) return Voice.cancel();
            if (what.equals("send")) return Voice.send(java.util.Arrays.copyOfRange(parts, 1, parts.length));
            return "error: voice play <name> | record | send <3|4> | send pm <id> | cancel | status";
        }
        if (verb.equals("use") || verb.equals("select")) {
            if (!armed[0]) return "refused: send 'arm' first";
            if (parts.length < 2) return "error: " + verb + " <id>";
            try {
                int id = Integer.parseInt(parts[1]);
                return verb.equals("use") ? Act.use(id) : Act.select(id);
            } catch (NumberFormatException e) {
                return "bad number in: " + command;
            }
        }
        if (verb.equals("cast")) {
            if (!armed[0]) return "refused: send 'arm' first";
            if (parts.length != 3) return "error: cast <skill> <target>";
            try {
                return Act.cast(Integer.parseInt(parts[1]), Integer.parseInt(parts[2]));
            } catch (NumberFormatException e) {
                return "bad number in: " + command;
            }
        }
        if (verb.equals("slot")) {
            if (!armed[0]) return "refused: send 'arm' first";
            if (parts.length < 2) return "error: slot <1-10> [sustain] [lock]";
            try {
                int n = Integer.parseInt(parts[1]);
                boolean sustain = false;
                boolean lock = false;
                for (int i = 2; i < parts.length; i++) {
                    if (parts[i].equals("sustain")) sustain = true;
                    else if (parts[i].equals("lock")) lock = true;
                    else return "error: slot <1-10> [sustain] [lock]";
                }
                return Act.slot(n, sustain, lock);
            } catch (NumberFormatException e) {
                return "bad number in: " + command;
            }
        }
        if (verb.equals("pick")) {
            if (!armed[0]) return "refused: send 'arm' first";
            if (parts.length < 3 || parts.length > 4) return "error: pick <layout> <id> [buy|sell]";
            try {
                return Dialogs.pick(parts[1].toLowerCase(), Integer.parseInt(parts[2]),
                        parts.length > 3 ? parts[3].toLowerCase() : null);
            } catch (NumberFormatException e) {
                return "bad number in: " + command;
            }
        }
        if (verb.equals("shardsell")) {
            if (!armed[0]) return "refused: send 'arm' first";
            if (parts.length != 3) return "error: shardsell <item id> <count>";
            try {
                return Dialogs.shardSell(Integer.parseInt(parts[1]), Integer.parseInt(parts[2]));
            } catch (NumberFormatException e) {
                return "bad number in: " + command;
            }
        }
        if (verb.equals("sharddirect")) {
            if (!armed[0]) return "refused: send 'arm' first";
            if (parts.length != 3) return "error: sharddirect <item id> <count>";
            try {
                return Dialogs.shardSellDirect(Integer.parseInt(parts[1]), Integer.parseInt(parts[2]));
            } catch (NumberFormatException e) {
                return "bad number in: " + command;
            }
        }
        if (verb.equals("sharddirectall")) {
            if (!armed[0]) return "refused: send 'arm' first";
            if (parts.length < 3 || parts.length % 2 == 0) return "error: sharddirectall <item id> <count> ...";
            try {
                int[] ids = new int[(parts.length - 1) / 2];
                int[] counts = new int[ids.length];
                for (int i = 0; i < ids.length; i++) {
                    ids[i] = Integer.parseInt(parts[1 + 2 * i]);
                    counts[i] = Integer.parseInt(parts[2 + 2 * i]);
                }
                return Dialogs.shardSellDirectAll(ids, counts);
            } catch (NumberFormatException e) {
                return "bad number in: " + command;
            }
        }
        if (verb.equals("discarddirectall")) {
            if (!armed[0]) return "refused: send 'arm' first";
            if (parts.length < 2) return "error: discarddirectall <uid> ...";
            try {
                int[] ids = new int[parts.length - 1];
                for (int i = 0; i < ids.length; i++) ids[i] = Integer.parseInt(parts[i + 1]);
                return Act.discardAll(ids);
            } catch (NumberFormatException e) {
                return "bad number in: " + command;
            }
        }
        if (verb.equals("choose")) {
            if (!armed[0]) return "refused: send 'arm' first";
            if (parts.length != 4) return "error: choose <row> <col> <sig>";
            try {
                return Dialogs.choose(Integer.parseInt(parts[1]), Integer.parseInt(parts[2]), Integer.parseInt(parts[3]));
            } catch (NumberFormatException e) {
                return "bad number in: " + command;
            }
        }
        if (verb.equals("xpbonus")) {
            if (!armed[0]) return "refused: send 'arm' first";
            return Ask.xpBonus(parts.length > 1 ? parts[1].toLowerCase() : "");
        }
        if (verb.equals("ask")) {
            if (!armed[0]) return "refused: send 'arm' first";
            return Ask.handle(parts.length > 1 ? parts[1].toLowerCase() : "");
        }
        // A quick phrase changes the player's own setup: armed connections only.
        if (verb.equals("phrase")) {
            if (!armed[0]) return "refused: send 'arm' first";
            String[] ph = command.trim().split("\\s+", 3);
            if (ph.length < 3) return "error: phrase <slot> <text>";
            try {
                return Phrases.set(Integer.parseInt(ph[1]), ph[2]);
            } catch (NumberFormatException e) {
                return "bad number in: " + command;
            }
        }
        // The player's own Shift/Ctrl/Alt ignored in this game for as long as a run asks (Keys.GuardedKeys).
        if (verb.equals("guardmods")) {
            if (!armed[0]) return "refused: send 'arm' first";
            boolean on = parts.length < 2 || !parts[1].equalsIgnoreCase("off");
            if (on == guarded[0]) return on ? "on" : "off";
            String r = Keys.guardModifiers(on);
            if (r.equals("on") || r.equals("off")) guarded[0] = on;
            return r;
        }
        // The game's own speech: "speech" -> on/off/unknown; "speech off" silences, "speech on" restores.
        if (verb.equals("speech")) {
            if (parts.length > 1 && parts[1].equalsIgnoreCase("off")) return SpeechSwitch.set(true);
            if (parts.length > 1 && parts[1].equalsIgnoreCase("on")) return SpeechSwitch.set(false);
            return SpeechSwitch.state();
        }

        // The game's voice message player: "voicefix" -> on/off/unknown; "voicefix on" mends it (the
        // default), "voicefix off" lets it play as the game does, deep voices and all (VoicePlayer).
        if (verb.equals("voicefix")) {
            if (parts.length > 1 && parts[1].equalsIgnoreCase("on")) return VoicePlayer.set(true);
            if (parts.length > 1 && parts[1].equalsIgnoreCase("off")) return VoicePlayer.set(false);
            return VoicePlayer.state();
        }

        // Keys are pressed through the game's own key handler, so they don't need the protocol
        // senders resolved -- only arming.
        boolean keying = verb.equals("key") || verb.equals("keydown") || verb.equals("keyup")
                || verb.equals("keysup") || verb.equals("type") || verb.equals("typeenter") || verb.equals("number")
                || verb.equals("typeclear") || verb.equals("typeesc");
        if (keying && !armed[0]) return "refused: send 'arm' first";
        // The input box (quantities): its own AWT handler, not the keyboard hook.
        if (verb.equals("type")) {
            int sp = command.indexOf(' ');
            return sp < 0 ? "missing argument in: " + command : TextInput.type(command.substring(sp + 1));
        }
        if (verb.equals("typeenter")) return TextInput.enter();
        if (verb.equals("number")) return parts.length == 2 ? TextInput.number(parts[1]) : "missing number";
        if (verb.equals("typeclear")) return TextInput.clear();
        if (verb.equals("typeesc")) return TextInput.escape();
        try {
            if (verb.equals("key")) {
                return Keys.tap(parts[1].toLowerCase(), parts.length > 2 ? Long.parseLong(parts[2]) : 60);
            }
            if (verb.equals("keydown")) {
                String k = parts[1].toLowerCase();
                String r = Keys.down(k);
                if (r.equals("down " + k)) mine.add(k);
                return r;
            }
            if (verb.equals("keyup")) {
                String k = parts[1].toLowerCase();
                if (!mine.remove(k)) return "up " + k + " (not held by this connection)";
                return Keys.up(k);
            }
            if (verb.equals("keysup")) {
                return Keys.release(mine);
            }
        } catch (NumberFormatException e) {
            return "bad number in: " + command;
        } catch (ArrayIndexOutOfBoundsException e) {
            return "missing argument in: " + command;
        }

        return "unknown command: " + verb;
    }

    private static void close(Socket socket) {
        if (socket == null) return;
        try {
            socket.close();
        } catch (Throwable ignored) { }
    }
}
