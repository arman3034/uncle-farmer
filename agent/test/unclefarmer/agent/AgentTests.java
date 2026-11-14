package unclefarmer.agent;

import java.io.File;
import java.nio.file.Files;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * The agent's own checks, without the game: the byte rules, the own-HP answers, the chat queue's
 * parts and the command replies. Plain Java (the agent is built with javac alone, no JUnit):
 * run by agent/java_tests.py, which check.py runs whenever a JDK is installed.
 *
 * Everything that needs the game's classes (the world object, the speech patch) stays a live test.
 */
public final class AgentTests {

    private static int run;
    private static int failed;

    private AgentTests() { }

    public static void main(String[] args) throws Exception {
        Map<String, String> contract = contract(args.length > 0 ? args[0] : "agent/test/contract.txt");

        protocolReadsNumbersAndNeverPastTheEnd();
        protocolEscapesJson();
        protocolReadsMapAndEntityNames();
        protocolFindsThePositionAfterTheTimestamp();
        positionsSurviveTheClocksFiftyDayTurn();
        numbersStayJsonInACommaDecimalLocale();
        aTapLeavesAKeyAnotherConnectionHolds();
        theGameFolderIsWrittenForTheApp();
        vitalsCreditOnlyTheAnswerToOurOwnRequest(contract);
        vitalsForIdZeroAreThePets();
        aPriestsPointsRequestIsAnsweredToo();
        theAmiabilityIsTheThirdFieldForEveryClass();
        askPacketIsTheOwnHpKeysRequest(contract);
        usePacketIsTheUseKeysRequest(contract);
        aSheetWeAskedForIsReadAndKeptFromTheGame(contract);
        theExperienceCardIsReadAndToggledOnlyFromAFreshSheet();
        everyCastSaysWhomItStruck(contract);
        professionRanksAreKeptFromTheLoginList();
        corpseSkillsTakeOnlyAFreshCorpseInReach();
        aCorpseCastIsHeldLikeTheKeyAndAlwaysLetGo();
        theAttackKeyMethodIsFoundByItsShape();
        aSlotPressIsLetGoLikeAKey();
        chatQueueCutsLongTextAtSpaces();
        directShardPacketUsesTheVerifiedLayout();
        commandsAnswerWithoutTheGame();
        theStateServerListensOnLoopbackOnly();
        theLoggedShopAndMarketMenusAreRecognised();
        aVerifiedIndexIsChosenOnlyForItsItem();
        aChangedOrUnexpectedMenuIsRefused();
        theMenuReplyIsTheContracts(contract);
        aMenuEntryIsChosenOnlyInTheMenuItWasReadFrom();
        voiceFramesAndNames();
        voiceMessagesArriveWithTheirName();
        aChatSendersIdNeverJoinsTheirName();
        voiceIsCleanedAndCutIntoMessages();
        theVoicePlayerOpensEachMessageAtItsOwnRate();
        theVoicePlayerSkipsAHalfReadFile();
        theVoiceFixCanBeSwitchedOff();
        theVoicePlayerRateFixMatchesTheGamesCode();
        theSpeechSwitchStillSilences();
        SoundTests.run();

        System.out.println("agent tests: " + (run - failed) + " of " + run + " passed");
        if (failed > 0) System.exit(1);
    }

    // ---------------------------------------------------------------- protocol
    private static void protocolReadsNumbersAndNeverPastTheEnd() {
        byte[] m = {0x00, 0x12, (byte) 0xD6, (byte) 0x87, 0x7F};
        eq(Protocol.readInt(m, 0), 1234567, "readInt big-endian");
        eq(Protocol.readShort(m, 1), 0x12D6, "readShort big-endian");
        eq(Protocol.readInt(m, 2), 0, "readInt past the end is 0");
        eq(Protocol.readInt(m, -1), 0, "readInt before the start is 0");
        eq(Protocol.readShort(m, 4), 0, "readShort past the end is 0");
        eq(Protocol.readInt(null, 0), 0, "readInt of nothing is 0");
    }

    private static void protocolEscapesJson() {
        eq(Protocol.jsonEscape("a\"b\\c\nd\te\u0001"), "a\\\"b\\\\c\\nd\\te\\u0001", "jsonEscape");
        eq(Protocol.jsonEscape(null), "", "jsonEscape of null");
    }

    private static void protocolReadsMapAndEntityNames() {
        byte[] map = concat(new byte[] {6, 0, 1, 0, 2, 0, 0}, "Wolf Prairie".getBytes(Protocol.UTF8));
        eq(Protocol.mapName(map), "Wolf Prairie", "mapName");
        eq(Protocol.mapName(new byte[] {6, 0, 1, 0, 2, 0, 0}), null, "a 7-byte op=6 means the map was left");

        // op=32: a positive id is a player, its name at 41 ("name,title,set,"); a monster's at 37
        byte[] player = new byte[41];
        player[0] = 32;
        player[4] = 5;                                 // id 5
        player = concat(player, "Hero,Knight,,".getBytes(Protocol.UTF8));
        eq(Protocol.entityName(player), "Hero", "a player's name at 41");
        byte[] monster = new byte[37];
        monster[0] = 32;
        monster[1] = (byte) 0xFF;                      // a negative id
        monster = concat(monster, "Wolf".getBytes(Protocol.UTF8));
        eq(Protocol.entityName(monster), "Wolf", "a monster's name at 37");
        eq(Protocol.entityName(new byte[20]), null, "a record too short has no name");
    }

    private static void protocolFindsThePositionAfterTheTimestamp() {
        long now = System.currentTimeMillis();
        byte[] m = new byte[30];
        m[0] = 36;
        for (int i = 0; i < 8; i++) m[5 + i] = (byte) (now >>> (56 - 8 * i));   // after a 4-byte counter
        eq(Protocol.positionOffset(m), 13, "the position sits just past the timestamp");
        eq(Protocol.positionOffset(new byte[30]), -1, "no timestamp, no position");
    }

    private static byte[] movement(long stamp) {
        byte[] m = new byte[30];
        m[0] = 36;
        for (int i = 0; i < 8; i++) m[5 + i] = (byte) (stamp >>> (56 - 8 * i));
        return m;
    }

    private static void positionsSurviveTheClocksFiftyDayTurn() {
        long turn = 0x19AL << 32;                       // the top four bytes of the clock change here
        eq(Protocol.positionOffset(movement(turn - 3000), turn + 2000), 13,
                "a timestamp from just before the turn, read just after it");
        eq(Protocol.positionOffset(movement(turn + 2000), turn + 2000), 13, "and one after it");
        eq(Protocol.positionOffset(movement(turn + 2000), turn + (3L << 32)), -1,
                "a stamp from another era is no timestamp");
    }

    private static void numbersStayJsonInACommaDecimalLocale() {
        java.util.Locale was = java.util.Locale.getDefault();
        java.util.Locale.setDefault(java.util.Locale.GERMANY);
        try {
            check(World.snapshot().contains("\"x\":0.00,"), "World's numbers keep their point");
            byte[] member = new byte[13];
            member[0] = 59;
            member[4] = 7;                               // id 7
            member[7] = 0x05;                            // x 1500 = 1.50 tiles
            member[8] = (byte) 0xDC;
            Team.inbound(concat(member, "Mate".getBytes(Protocol.UTF8)));
            check(Team.snapshot().contains("\"x\":1.50,"), "Team's numbers keep their point");
        } finally {
            java.util.Locale.setDefault(was);
        }
    }

    @SuppressWarnings("unchecked")
    private static void aTapLeavesAKeyAnotherConnectionHolds() throws Exception {
        java.lang.reflect.Field f = Keys.class.getDeclaredField("HELD");
        f.setAccessible(true);
        Map<String, Long> held = (Map<String, Long>) f.get(null);
        held.put("w", Long.valueOf(System.currentTimeMillis()));     // another connection walks on w
        try {
            eq(Keys.tap("w", 30), "tapped w" + Keys.ALREADY, "the tap goes as the key already is");
            check(held.containsKey("w"), "and the key stays held for the one walking on it");
        } finally {
            held.remove("w");
        }
    }

    private static void theGameFolderIsWrittenForTheApp() throws Exception {
        java.nio.file.Path dir = java.nio.file.Files.createTempDirectory("uf-agent-test");
        try {
            BotAgent.writeGameFolder(dir);
            String got = new String(java.nio.file.Files.readAllBytes(dir.resolve("game_folder.txt")), Protocol.UTF8);
            eq(got, new File(System.getProperty("user.dir")).getAbsolutePath(), "the game's working folder, for the app");
            String pid = java.lang.management.ManagementFactory.getRuntimeMXBean().getName().split("@")[0];
            String mine = new String(java.nio.file.Files.readAllBytes(dir.resolve("agent." + pid + ".folder")), Protocol.UTF8);
            eq(mine, got, "and this game's own folder file");
        } finally {
            File[] left = dir.toFile().listFiles();
            if (left != null) for (File f : left) java.nio.file.Files.deleteIfExists(f.toPath());
            java.nio.file.Files.deleteIfExists(dir);
        }
    }

    // ---------------------------------------------------------------- own HP and MP
    private static void vitalsCreditOnlyTheAnswerToOurOwnRequest(Map<String, String> contract) {
        int us = 1234567;
        World.outbound(concat(Ask.packet(6, us), new byte[] {0, 0}));      // the map request: our id
        eq(World.selfId(), us, "our id comes from the map request");

        World.outbound(Ask.packet(22, 777));           // someone else selected
        World.inbound(answer(5000, 100, -1, -1));
        eq(Vitals.hp == 5000, false, "an answer about someone else isn't ours");

        World.outbound(Ask.packet(22, us));
        World.inbound(answer(91000, 82000, 2, 1));
        eq(Vitals.hp, 91000, "our HP from op=51");
        eq(Vitals.mp, 82000, "our MP from op=51");
        eq(Vitals.buffs, 2, "buffs from the status byte");
        eq(Vitals.debuffs, 1, "debuffs from the status byte");
        eq(Vitals.id, us, "the numbers are ours");

        World.outbound(Ask.packet(22, us));
        World.inbound(answer(90000, 80000, -1, -1));
        eq(Vitals.buffs, 0, "a short answer means no buffs");

        Vitals.hp = 91000;
        Vitals.mp = 82000;
        Vitals.buffs = 2;
        Vitals.debuffs = 1;
        Vitals.seen = 1000L;
        StringBuilder sb = new StringBuilder();
        Vitals.json(sb, 2500L);
        eq(sb.toString(), ",\"vitals\":" + contract.get("vitals"), "mem self vitals as in contract.txt");
    }

    private static void vitalsForIdZeroAreThePets() {
        World.outbound(Ask.packet(22, 0));
        World.inbound(answer(3000, 400, -1, -1));
        eq(PetInfo.vitalsHp, 3000, "id 0 is the pet: its HP");
        eq(PetInfo.vitalsMp, 400, "id 0 is the pet: its MP");
    }

    /** The points key (T): op=23 alone, or with the PK mode byte for a Priest (game.i.K). Both are
     *  our request, and the answer's amiability is kept; with no request, speech isn't taken. */
    private static void aPriestsPointsRequestIsAnsweredToo() {
        byte[] reply = concat(new byte[] {60, 0}, "0;100.0;64.5".getBytes(java.nio.charset.StandardCharsets.UTF_8));
        Points.pet = -1;
        World.inbound(reply);
        eq(Points.pet, -1.0, "no request: no amiability");
        for (byte[] ask : new byte[][] {{23}, {23, 2}}) {
            Points.pet = -1;
            World.outbound(ask);
            World.inbound(reply);
            eq(Points.pet, 64.5, "request of " + ask.length + " byte(s): the pet's amiability");
        }
    }

    /** The points key's answers as recorded from the game (56,269 replies to the one-byte request,
     *  the Priest's two-byte one too): "points;fusion[;amiability]". The amiability is always the
     *  third field - for a Priest as well, whose points are two counts ("s0 e1") - and a reply
     *  with two fields carries none: its second field is the fusion power, never the amiability. */
    private static void theAmiabilityIsTheThirdFieldForEveryClass() {
        Object[][] cases = {
            {new byte[] {23}, "0;100.0;8.5", 100.0, 8.5},           // a Hunter, pet out
            {new byte[] {23}, "300;61.0;69.9", 61.0, 69.9},         // a Warrior's full rage
            {new byte[] {23}, "0;100.0", 100.0, -1.0},              // no pet out
            {new byte[] {23, 1}, "s0 e1; 79.3; 64.5", 79.3, 64.5},  // a Priest with a pet
            {new byte[] {23, 1}, "s0 e0; 81.3", 81.3, -1.0},        // a Priest without one
        };
        for (Object[] c : cases) {
            byte[] text = ((String) c[1]).getBytes(java.nio.charset.StandardCharsets.UTF_8);
            Points.pet = -1;
            Points.fusion = -1;
            World.outbound((byte[]) c[0]);
            World.inbound(concat(new byte[] {60, 9}, text));
            eq(Points.fusion, (Double) c[2], c[1] + ": the fusion power is the second field");
            eq(Points.pet, (Double) c[3], c[1] + ": the amiability is the third field");
        }
    }

    private static void askPacketIsTheOwnHpKeysRequest(Map<String, String> contract) {
        StringBuilder sb = new StringBuilder();
        for (byte b : Ask.packet(Ask.OP_VITALS, 1234567)) sb.append(sb.length() == 0 ? "" : " ").append(b & 0xFF);
        eq(sb.toString(), contract.get("ask_packet"), "ask vitals sends what R sends");
    }

    /** `ask sheet`: the sheet key's bytes go out; the sheet that answers is read and held back from
     *  the game (World.inbound true), one sheet per request, never someone else's, never late. */
    private static void aSheetWeAskedForIsReadAndKeptFromTheGame(Map<String, String> contract) {
        eq(bytes(Ask.sheetPacket(1234567)), contract.get("sheet_packet"), "ask sheet sends what the sheet key sends");
        int us = 1234567;
        World.outbound(concat(Ask.packet(6, us), new byte[] {0, 0}));      // our id, from the map request
        long now = System.currentTimeMillis();

        eq(World.inbound(sheet(us, 1000)), false, "a sheet nobody asked for reaches the game as before");
        eq(Sheet.contribution, 1000L, "and is still read");

        Sheet.expectQuiet(now);
        eq(World.inbound(sheet(777, 5)), false, "someone else's sheet is the player's to see");
        eq(World.inbound(sheet(us, 1200)), true, "the sheet that answers ask sheet is kept from the game");
        eq(Sheet.contribution, 1200L, "and read all the same");
        eq(Sheet.dropSeconds, 3 * 3600 + 25 * 60, "the drop time with it");
        check(Sheet.vitality == 44.7, "and the Vitality left: " + Sheet.vitality);
        eq(World.inbound(sheet(us, 1300)), false, "one request, one sheet: the next is the player's");

        Sheet.expectQuiet(now - Sheet.QUIET_WAIT_MS - 1000);
        eq(World.inbound(sheet(us, 1400)), false, "an answer far too late is the player's own sheet");
        Sheet.expectQuiet(now);
        Sheet.expectQuiet(0);
        eq(World.inbound(sheet(us, 1500)), false, "a request that never went out holds nothing back");
    }

    /** The card's sheet entry, running and paused, as the recorder caught them (2026-11-11), and
     *  `xpbonus` sending its one toggle byte only when the sheet says the card is the other way. */
    private static void theExperienceCardIsReadAndToggledOnlyFromAFreshSheet() {
        int us = 1234567;
        World.outbound(concat(Ask.packet(6, us), new byte[] {0, 0}));
        String head = "(1(Someone)1)|||((," + us + ";))|||Hunter|||;|||male |||. level 79|||HP 1/2|||MP 3/4|||";
        String running = head + "14\r22\r\r\r\r\r\rPause EXP bonus will be deducted by one minute, and pause is"
                + " invalid in dungeon. Are you sure you want to pause?\r\r\r\r30% EXP bonus; press to pause\r"
                + "28 minutes 55 seconds remaining\r8\r14,16|||Morality 2000;white name";
        World.inbound(concat(new byte[] {62}, running.getBytes(Protocol.UTF8)));
        eq(Sheet.expBonus, 30, "the running card's bonus");
        eq(Sheet.expPaused, false, "running");
        eq(Sheet.expSeconds, 28 * 60 + 55, "its time left");
        eq(Sheet.morality, 2000L, "Morality");
        String paused = head + "12\r22\r\r\r\r\r\r\r\r\r\r30% EXP bonus\rPaused; press to resume\r1 hour 2 minutes"
                + " remaining|||Morality -1200;black name";
        World.inbound(concat(new byte[] {62}, paused.getBytes(Protocol.UTF8)));
        eq(Sheet.expPaused, true, "paused");
        eq(Sheet.expSeconds, 3720, "an hour and two minutes");
        eq(Sheet.morality, -1200L, "a black name");
        World.inbound(concat(new byte[] {62}, head.getBytes(Protocol.UTF8)));
        eq(Sheet.expBonus, 0, "no entry: no card");
        eq(Sheet.expSeconds, -1, "and no time left");

        eq(bytes(Ask.expTogglePacket()), "37 22", "pause and resume send 25 16");
        long now = 1_000_000L;
        eq(Ask.xpBonusRefusal("pause", true, now, now - 1000, 0, 30, false), null, "pause a running card");
        eq(Ask.xpBonusRefusal("resume", true, now, now - 1000, 0, 30, true), null, "resume a paused one");
        check(Ask.xpBonusRefusal("pause", true, now, now - 1000, 0, 30, true) != null, "not pause it twice");
        check(Ask.xpBonusRefusal("resume", true, now, now - 1000, 0, 30, false) != null, "not resume a running one");
        check(Ask.xpBonusRefusal("pause", true, now, now - 1000, 0, 0, false) != null, "no card, nothing sent");
        check(Ask.xpBonusRefusal("pause", true, now, now - Ask.EXP_SHEET_MS - 1, 0, 30, false) != null, "an old sheet");
        check(Ask.xpBonusRefusal("pause", true, now, now - 1000, now - 500, 30, false) != null,
              "no second toggle before a sheet that came after the first");
        check(Ask.xpBonusRefusal("pause", false, now, now - 1000, 0, 30, false) != null, "someone else's sheet");
        check(Ask.xpBonusRefusal("flip", true, now, now - 1000, 0, 30, false).startsWith("error"), "pause or resume only");
    }

    /** An IN op=62 character sheet as the server sends it (the parts Sheet reads). */
    private static byte[] sheet(int id, long contribution) {
        String text = "(1(Someone)1)|||((," + id + ";))|||Hunter|||;|||male |||. level 79|||; Contribution "
                + contribution + "|||HP 40000/50000|||MP 30000/45000|||marked targets 0|||fusion power 99.8|||"
                + "load 2000/4000|||Vitality 44.7; Press to buy|||public area drop 3 hours 25 minutes  remaining";
        return concat(new byte[] {62}, text.getBytes(Protocol.UTF8));
    }

    private static void usePacketIsTheUseKeysRequest(Map<String, String> contract) {
        eq(bytes(Act.packet(1234567)), contract.get("use_packet"), "use sends what the use key sends");
        eq(bytes(Act.discardPacket(1234567, 1)), "18 0 0 18 214 135 255 255 255 255",
                "discarding one sends what the game's discard sends");
        eq(bytes(Act.discardPacket(1234567, 3)), "18 0 0 18 214 135 255 255 255 253",
                "three of a stack go in one packet with minus three");
    }

    private static String bytes(byte[] packet) {
        StringBuilder sb = new StringBuilder();
        for (byte b : packet) sb.append(sb.length() == 0 ? "" : " ").append(b & 0xFF);
        return sb.toString();
    }

    // ---------------------------------------------------------------- chat queue
    private static void chatQueueCutsLongTextAtSpaces() {
        eq(ChatQueue.split("hello").size(), 1, "a short line is one part");
        eq(ChatQueue.split("   ").size(), 0, "nothing to send is no part");

        StringBuilder words = new StringBuilder();
        while (words.length() < 450) words.append("farming ");
        String text = words.toString().trim();
        List<String> parts = ChatQueue.split(text);
        eq(parts.size(), 3, "450 characters go in three parts");
        StringBuilder back = new StringBuilder();
        for (String p : parts) {
            check(p.length() <= ChatQueue.MOST, "a part fits the chat box: " + p.length());
            check(!p.startsWith(" ") && !p.endsWith(" "), "a part is cut at a space");
            back.append(back.length() == 0 ? "" : " ").append(p);
        }
        eq(back.toString(), text, "the parts put together are the text");

        StringBuilder word = new StringBuilder();
        for (int i = 0; i < 250; i++) word.append('x');
        parts = ChatQueue.split(word.toString());
        eq(parts.size(), 2, "a word longer than the box is cut hard");
        eq(parts.get(0).length(), ChatQueue.MOST, "the hard cut is at the limit");

        StringBuilder exact = new StringBuilder();
        for (int i = 0; i < ChatQueue.MOST; i++) exact.append('y');
        eq(ChatQueue.split(exact.toString()).size(), 1, "exactly the limit is one part");
    }

    // ---------------------------------------------------------------- commands
    private static void commandsAnswerWithoutTheGame() {
        boolean[] armed = {false};
        boolean[] guarded = {false};
        java.util.Set<String> mine = new java.util.HashSet<String>();
        eq(StateServer.handle("version", armed, mine, guarded), "mwagent " + StateServer.VERSION, "version");
        check(StateServer.handle("loginaccount", armed, mine, guarded).startsWith("{\"ok\":"), "saved account query");
        eq(StateServer.handle("autologin account@example.com 123", armed, mine, guarded),
                "refused: send 'arm' first", "automatic login needs arm");
        check(StateServer.handle("autologinstatus", armed, mine, guarded).startsWith("{\"ok\":"),
                "automatic login status");
        for (String sound : new String[] {"soundstatus", "sounds 0", "soundwatch off", "soundmute off", "soundlisten off"}) {
            check(!StateServer.handle(sound, armed, mine, guarded).startsWith("unknown command"),
                    "the Sound Silencer command stays: " + sound);
        }
        eq(StateServer.handle("ping", armed, mine, guarded), "pong", "ping");
        eq(StateServer.handle("voicefix off", armed, mine, guarded), "unknown", "no voice player loaded: nothing to switch");
        eq(StateServer.handle("frobnicate", armed, mine, guarded), "unknown command: frobnicate", "unknown");
        eq(StateServer.handle("ask vitals", armed, mine, guarded), "refused: send 'arm' first", "ask needs arm");
        eq(StateServer.handle("key j", armed, mine, guarded), "refused: send 'arm' first", "keys need arm");
        eq(StateServer.handle("say 1 hi", armed, mine, guarded), "refused: send 'arm' first", "say needs arm");
        eq(StateServer.handle("use 5", armed, mine, guarded), "refused: send 'arm' first", "use needs arm");
        eq(StateServer.handle("select 5", armed, mine, guarded), "refused: send 'arm' first", "select needs arm");
        eq(StateServer.handle("slot 1", armed, mine, guarded), "refused: send 'arm' first", "slot needs arm");
        eq(StateServer.handle("cast 21 -7", armed, mine, guarded), "refused: send 'arm' first", "cast needs arm");
        eq(StateServer.handle("shardsell 20385 1", armed, mine, guarded), "refused: send 'arm' first",
                "shardsell needs arm");
        eq(StateServer.handle("sharddirect 20385 1", armed, mine, guarded), "refused: send 'arm' first",
                "sharddirect needs arm");
        eq(StateServer.handle("sharddirectall 20385 1", armed, mine, guarded), "refused: send 'arm' first",
                "sharddirectall needs arm");
        eq(StateServer.handle("discarddirectall 5", armed, mine, guarded), "refused: send 'arm' first",
                "discarddirectall needs arm");
        eq(StateServer.handle("arm", armed, mine, guarded), "armed", "arm");
        check(StateServer.handle("autologin account@example.com bad", armed, mine, guarded).contains("invalid character id"),
                "automatic login validates the character id");
        eq(StateServer.handle("slot 1", armed, mine, guarded), "error: the attack page can't be read",
                "slot without a game says so instead of throwing");
        eq(StateServer.handle("slot 11", armed, mine, guarded), "error: slot 1-10", "a key number, not a page-2 slot");
        eq(StateServer.handle("slot 2 sideways", armed, mine, guarded), "error: slot <1-10> [sustain] [lock]",
                "slot with a word it doesn't know");
        eq(StateServer.handle("slot x", armed, mine, guarded), "bad number in: slot x", "slot a bad number");
        check(StateServer.handle("use 5", armed, mine, guarded).startsWith("error: nowin"),
                "use without a game says so instead of throwing");
        check(StateServer.handle("select 5", armed, mine, guarded).startsWith("error: nowin"),
                "select without a game says so instead of throwing");
        eq(StateServer.handle("use", armed, mine, guarded), "error: use <id>", "use what");
        eq(StateServer.handle("select x", armed, mine, guarded), "bad number in: select x", "select a bad id");
        check(StateServer.handle("cast 21 -7", armed, mine, guarded).startsWith("error: nowin"),
                "cast without a game says so instead of throwing");
        eq(StateServer.handle("cast 21", armed, mine, guarded), "error: cast <skill> <target>", "cast at what");
        eq(StateServer.handle("cast x -7", armed, mine, guarded), "bad number in: cast x -7", "cast a bad skill");
        eq(StateServer.handle("ask", armed, mine, guarded), "error: ask vitals|petvitals|sheet", "ask what");
        eq(StateServer.handle("ask vitals", armed, mine, guarded), "error: the game's connection wasn't found",
                "ask without a game says so instead of throwing");
        eq(StateServer.handle("say 1", armed, mine, guarded), "error: say <0-6> <text>", "say without text");
        eq(StateServer.handle("pms x", armed, mine, guarded), "bad number in: pms x", "a bad number is answered");
        check(StateServer.handle("menu", armed, mine, guarded).startsWith("{\"ok\":false"),
                "menu without a game answers with an error, not a throw");
        check(StateServer.handle("pick shard_market 20385", armed, mine, guarded).startsWith("error: "),
                "pick without a game says so and chooses nothing");
        eq(StateServer.handle("pick shard_market x", armed, mine, guarded), "bad number in: pick shard_market x",
                "pick a bad id");
        eq(StateServer.handle("pick shard_market", armed, mine, guarded), "error: pick <layout> <id> [buy|sell]",
                "pick what");
        eq(StateServer.handle("shardsell 20385", armed, mine, guarded), "error: shardsell <item id> <count>",
                "shardsell needs both numbers");
        eq(StateServer.handle("shardsell x 1", armed, mine, guarded), "bad number in: shardsell x 1",
                "shardsell checks the item id");
        eq(StateServer.handle("sharddirect 20385", armed, mine, guarded), "error: sharddirect <item id> <count>",
                "sharddirect needs both numbers");
        eq(StateServer.handle("sharddirectall 20385", armed, mine, guarded),
                "error: sharddirectall <item id> <count> ...", "sharddirectall needs pairs");
        eq(StateServer.handle("sharddirectall x 1", armed, mine, guarded), "bad number in: sharddirectall x 1",
                "sharddirectall checks item ids");
        eq(StateServer.handle("discarddirectall", armed, mine, guarded), "error: discarddirectall <uid> ...",
                "discarddirectall needs ids");
        eq(StateServer.handle("discarddirectall x", armed, mine, guarded), "bad number in: discarddirectall x",
                "discarddirectall checks item ids");
        boolean[] unarmed = {false};
        eq(StateServer.handle("pick shard_trade 20385 sell", unarmed, mine, guarded), "refused: send 'arm' first",
                "pick needs arm");
    }

    /** The state server takes keys and chat from whoever connects, so it must never be reachable
     *  from another machine: it binds 127.0.0.1 and nothing wider (not 0.0.0.0, not a LAN address). */
    private static void theStateServerListensOnLoopbackOnly() throws Exception {
        java.net.ServerSocket server = StateServer.bind();
        check(server != null, "the state server found a free port in its range");
        if (server == null) return;
        try {
            eq(server.getInetAddress().getHostAddress(), "127.0.0.1", "the state server binds 127.0.0.1");
            check(server.getInetAddress().isLoopbackAddress(), "a loopback address, nothing off this machine");
            check(server.getLocalPort() >= StateServer.FIRST_PORT && server.getLocalPort() <= StateServer.LAST_PORT,
                    "a port in the agent's own range");
        } finally {
            server.close();
        }
    }

    private static void directShardPacketUsesTheVerifiedLayout() {
        eq(bytes(Dialogs.shardPacket(-44, 20485, 24, 1)),
                "34 255 255 255 212 31 0 0 0 3 0 0 80 5 0 0 0 24 0 0 0 1",
                "direct shard sell is the verified broker command");
    }

    // ---------------------------------------------------------------- shop and Shard Market menus
    // The menus as dialogs.log recorded them (flags, options, cmd): the Shard Broker's list, what a
    // shard opens, and a potion seller's list.
    private static final String[][] MARKET_ROWS = {
        {"Weapon Enhance Crystal Shard", "4000"}, {"Equipment Enhance Crystal Shard", "1000"},
        {"Level 1 Ruby Shard", "2550"}, {"Level 1 Sapphire Shard", "20"}, {"Level 1 Tiger Eye Stone Shard", "2320"},
        {"Level 1 Opal Shard", "2540"}, {"Level 1 Spinel Shard", "20"}, {"Level 1 Aquamarine Shard", "22"},
        {"Level 1 Garnet Shard", "4020"}, {"Level 1 Blond Jade Shard", "5850"}, {"Level 1 Grape Stone Shard", "56"},
        {"Level 1 Olivine Shard", "22"}, {"Level 1 Topaz Shard", "535"}, {"Level 1 Obsidian Shard", "2635"},
        {"Level 1 Sunlight Stone Shard", "26"}, {"Level 1 Moonstone Shard", "2455"}, {"Level 1 Turquoise Shard", "1405"},
    };
    private static final String[] SHOP_ROWS = {"Small Red Potion", "Small Blue Potion", "Medium Red Potion",
        "Medium Blue Potion", "Large Red Potion", "Large Blue Potion", "Pet Small Red Potion", "Pet Small Blue Potion",
        "Pet Medium Red Potion", "Pet Medium Blue Potion", "Pet Large Red Potion", "Pet Large Blue Potion"};

    private static Menus.Entry z(int flags, int[] cmd, String... options) {
        return new Menus.Entry(flags, options, cmd);
    }

    private static java.util.List<Menus.Entry> row(Menus.Entry... cells) {
        return new java.util.ArrayList<Menus.Entry>(java.util.Arrays.asList(cells));
    }

    private static Menus.Menu market() {
        Menus.Menu m = new Menus.Menu();
        m.rows.add(row(z(0, null, "Welcome to Shard  Market"), z(8, new int[] {4}, "View description")));
        for (int i = 0; i < MARKET_ROWS.length; i++) {
            int price = Integer.parseInt(MARKET_ROWS[i][1]);
            m.rows.add(row(z(8, new int[] {1, Menus.SHARD_MARKET_IDS[i], price}, MARKET_ROWS[i][0],
                    "Unit price " + price + " arnebia")));
        }
        return m;
    }

    private static Menus.Menu trade(int id, int price) {
        Menus.Menu m = new Menus.Menu();
        m.rows.add(row(z(13, new int[] {2, id, price, 0}, "buy")));
        m.rows.add(row(z(13, new int[] {3, id, price, 0}, "sell")));
        return m;
    }

    private static Menus.Menu shop() {
        Menus.Menu m = new Menus.Menu();
        int[] prices = {60, 60, 150, 150, 450, 450, 120, 120, 300, 300, 1000, 1000};
        for (int i = 0; i < SHOP_ROWS.length; i++) {
            m.rows.add(row(z(9, new int[] {1, Menus.POTION_SHOP_IDS[i], 0}, SHOP_ROWS[i],
                    "unit price " + prices[i] + " arnebia", "Recover some HP")));
        }
        return m;
    }

    private static String placed(Menus.Menu m, String layout, int id, String action) {
        try {
            int[] at = Menus.place(m, layout, id, action);
            return "placed " + at[0] + "," + at[1];
        } catch (Menus.Refused r) {
            return "refused: " + r.getMessage();
        }
    }

    private static void theLoggedShopAndMarketMenusAreRecognised() {
        eq(Menus.classify(market()), Menus.SHARD_MARKET, "the Shard Broker's list");
        check(Menus.verified(market(), Menus.SHARD_MARKET), "in the verified order");
        eq(Menus.classify(trade(20425, 2175)), Menus.SHARD_TRADE, "what a shard opens");
        eq(Menus.classify(shop()), Menus.POTION_SHOP, "a potion seller's list");
        check(Menus.verified(shop(), Menus.POTION_SHOP), "in the verified order");
        Menus.Menu storehouse = new Menus.Menu();
        storehouse.rows.add(row(z(0, null, "item storage")));
        storehouse.rows.add(row(z(0, null, "deposit item")));
        eq(Menus.classify(storehouse), Menus.UNKNOWN, "a menu without commands is none of them");
        Menus.Menu marketplace = new Menus.Menu();      // the players' marketplace, also "buy"
        marketplace.rows.add(row(z(12, new int[] {2, -1, 0, 1}, "buy goods")));
        marketplace.rows.add(row(z(8, new int[] {4}, "sell goods")));
        eq(Menus.classify(marketplace), Menus.UNKNOWN, "the players' marketplace is not the shard trade");
        eq(Menus.classify(new Menus.Menu()), Menus.UNKNOWN, "an empty menu");
        eq(Menus.classify(null), Menus.UNKNOWN, "no menu");
    }

    private static void aVerifiedIndexIsChosenOnlyForItsItem() {
        eq(placed(market(), Menus.SHARD_MARKET, 20385, null), "placed 3,0", "Level 1 Ruby Shard is row 3");
        eq(placed(market(), Menus.SHARD_MARKET, 20665, null), "placed 17,0", "the last shard, row 17");
        eq(placed(shop(), Menus.POTION_SHOP, 23387, null), "placed 4,0", "Large Red Potion is row 4");
        eq(placed(trade(20425, 2175), Menus.SHARD_TRADE, 20425, "sell"), "placed 1,0", "sell is row 1");
        eq(placed(trade(20425, 2175), Menus.SHARD_TRADE, 20425, "buy"), "placed 0,0", "buy is row 0");
    }

    private static Menus.Menu npcMenu(String... texts) {
        Menus.Menu m = new Menus.Menu();
        for (int i = 0; i < texts.length; i++) {
            m.rows.add(row(new Menus.Entry(8, texts[i], new String[] {texts[i]}, new int[] {7, i})));
        }
        return m;
    }

    private static String chosenAt(Menus.Menu m, int row, int col, int sig) {
        try {
            Menus.Entry e = Menus.chosen(m, row, col, sig);
            return "chosen " + e.name();
        } catch (Menus.Refused r) {
            return "refused: " + r.getMessage();
        }
    }

    private static void aMenuEntryIsChosenOnlyInTheMenuItWasReadFrom() {
        Menus.Menu m = npcMenu("Fly to Tulip", "Fly to Holy Blood", "Leave");
        int sig = Menus.signature(m);
        eq(Menus.signature(npcMenu("Fly to Tulip", "Fly to Holy Blood", "Leave")), sig,
                "the same content reads the same signature every time");
        eq(chosenAt(m, 1, 0, sig), "chosen Fly to Holy Blood", "the entry at the row and column read");
        eq(chosenAt(m, 2, 0, sig), "chosen Leave", "the last row");
        check(Menus.signature(npcMenu("Fly to Holy Blood", "Fly to Tulip", "Leave")) != sig, "two rows swapped");
        check(Menus.signature(npcMenu("Fly to Tulip", "Fly to Holy Blood")) != sig, "a row gone");
        check(Menus.signature(npcMenu("Fly to Tulip", "Fly to Holy Blood", "Leave", "More")) != sig, "a row more");
        Menus.Menu other = npcMenu("Fly to Tulip", "Fly to Holy Blood", "Leave");
        other.rows.get(1).set(0, new Menus.Entry(8, "Fly to Holy Blood", new String[] {"Fly to Holy Blood"}, new int[] {7, 9}));
        check(Menus.signature(other) != sig, "the same text sending another command");
        eq(chosenAt(npcMenu("Fly to Holy Blood", "Fly to Tulip", "Leave"), 1, 0, sig),
                "refused: the menu changed since it was read", "another menu: nothing chosen");
        eq(chosenAt(m, 3, 0, sig), "refused: no entry at row 3 col 0", "past the last row");
        eq(chosenAt(m, 0, 1, sig), "refused: no entry at row 0 col 1", "past the row's last column");
        eq(chosenAt(m, -1, 0, sig), "refused: no entry at row -1 col 0", "before the first row");
        Menus.Menu gap = npcMenu("Ali");
        gap.rows.get(0).add(null);
        eq(chosenAt(gap, 0, 1, Menus.signature(gap)), "refused: no entry at row 0 col 1", "an empty cell");
        eq(chosenAt(new Menus.Menu(), 0, 0, Menus.signature(new Menus.Menu())), "refused: the menu has no rows",
                "an empty menu");
        eq(chosenAt(market(), 17, 0, Menus.signature(market())), "chosen Level 1 Turquoise Shard",
                "a verified layout's row too");
    }

    private static void aChangedOrUnexpectedMenuIsRefused() {
        Menus.Menu swapped = market();
        java.util.Collections.swap(swapped.rows, 3, 4);
        check(!Menus.verified(swapped, Menus.SHARD_MARKET), "two rows swapped: not the verified order");
        check(placed(swapped, Menus.SHARD_MARKET, 20385, null).startsWith("refused: shard_market changed"),
                "and nothing is chosen in it");
        Menus.Menu shorter = market();
        shorter.rows.remove(shorter.rows.size() - 1);
        check(placed(shorter, Menus.SHARD_MARKET, 20385, null).startsWith("refused: shard_market changed"),
                "a row gone: changed");
        Menus.Menu longer = shop();
        longer.rows.add(row(z(9, new int[] {1, 99999, 0}, "Huge Red Potion", "unit price 2000 arnebia")));
        check(placed(longer, Menus.POTION_SHOP, 23387, null).startsWith("refused: potion_shop changed"),
                "a new item in the shop: changed");
        check(placed(market(), Menus.SHARD_MARKET, 12345, null).startsWith("refused: item 12345 is not"),
                "an item the verified layout doesn't have");
        check(placed(shop(), Menus.SHARD_MARKET, 23387, null).startsWith("refused: the open menu is potion_shop"),
                "the shop is not the Shard Market");
        check(placed(market(), Menus.SHARD_TRADE, 20385, "sell").startsWith("refused: the open menu is shard_market"),
                "selling needs the buy/sell menu open");
        check(placed(trade(20425, 2175), Menus.SHARD_TRADE, 20385, "sell").startsWith("refused: row 1 holds item 20425"),
                "the buy/sell menu of another shard: refused, so the wrong shard is never sold");
        check(placed(trade(20425, 2175), Menus.SHARD_TRADE, 20425, null).startsWith("refused: shard_trade needs"),
                "buy or sell must be said");
        check(placed(trade(20425, 2175), Menus.SHARD_TRADE, 20425, "steal").startsWith("refused: shard_trade needs"),
                "and nothing else");
        check(placed(market(), Menus.SHARD_MARKET, 20385, "sell").startsWith("refused: shard_market takes no action"),
                "the list itself takes no buy or sell");
        Menus.Menu flipped = new Menus.Menu();          // sell on top: not the layout, so nothing chosen
        flipped.rows.add(row(z(13, new int[] {3, 20425, 2175, 0}, "sell")));
        flipped.rows.add(row(z(13, new int[] {2, 20425, 2175, 0}, "buy")));
        eq(Menus.classify(flipped), Menus.UNKNOWN, "buy and sell the other way round is not the verified layout");
        check(placed(flipped, Menus.SHARD_TRADE, 20425, "buy").startsWith("refused: the open menu is unknown"),
                "so a buy is never sent as a sell");
    }

    private static void theMenuReplyIsTheContracts(Map<String, String> contract) {
        eq(Menus.describe(trade(20425, 2175)), contract.get("menu_trade"), "the buy/sell menu's reply");
        String m = Menus.describe(market());
        check(m.startsWith("{\"ok\":true,\"layout\":\"shard_market\",\"verified\":true,\"items\":[{\"row\":1,"),
                "the market's reply: " + m.substring(0, Math.min(120, m.length())));
        check(m.contains("{\"row\":3,\"col\":0,\"id\":20385,\"name\":\"Level 1 Ruby Shard\",\"price\":2550}"),
                "each shard with its row, id and price");
        check(Menus.describe(shop()).contains("\"id\":23387,\"name\":\"Large Red Potion\",\"price\":450}"),
                "a shop row's price is the one it shows");
        eq(Menus.describe(new Menus.Menu()), "{\"ok\":true,\"layout\":\"unknown\",\"verified\":false,\"items\":[]}",
                "an unknown menu lists nothing");
    }

    // ---------------------------------------------------------------- voice
    private static final String VOICE_NAME = "0123456789abcdef0123456789ABCDEF";

    private static void voiceFramesAndNames() throws Exception {
        byte[] file = {1, 2, 9, 9, 7, 1, 5};                   // two frames of 2 bytes, then part of one
        List<byte[]> f = Voice.frames(file);
        eq(f.size(), 2, "voice frames: 01 <frame length>, then the frames; a part frame left out");
        eq(f.get(1)[0], (byte) 7, "the second frame's byte");
        eq(Voice.frames(new byte[] {2, 2, 9, 9}).size(), 0, "not a voice file");
        eq(Voice.millis(file), 40L, "20 ms a frame");
        check(Voice.validName(VOICE_NAME), "a 32-character name is a voice name");
        check(!Voice.validName("../../../../windows/system32/xx"), "a path is not");
        check(!Voice.validName("abc"), "nor a short one");
        java.io.ByteArrayOutputStream o = new java.io.ByteArrayOutputStream();
        Voice.writeWav(o, new byte[] {1, 0, 2, 0});
        byte[] wav = o.toByteArray();
        eq(wav.length, 48, "a WAV header of 44 bytes and the samples");
        eq(new String(wav, 0, 4, Protocol.UTF8), "RIFF", "RIFF");
        eq(wav[24] & 0xFF | (wav[25] & 0xFF) << 8, 16000, "16 kHz");
        eq(StateServer.handle("voice play ../x", new boolean[] {false}, new java.util.HashSet<String>(),
                new boolean[] {false}), "error: not a voice message name", "voice play checks the name");
        eq(StateServer.handle("voice record", new boolean[] {false}, new java.util.HashSet<String>(),
                new boolean[] {false}), "refused: send 'arm' first", "recording needs arm");
    }

    private static void voiceIsCleanedAndCutIntoMessages() throws Exception {
        int rate = Voice.RATE;
        // 1 s of silence, 2 s of a quiet 300 Hz "voice" (-30 dBFS), 1 s of silence
        short[] rec = new short[4 * rate];
        for (int i = rate; i < 3 * rate; i++) rec[i] = (short) (1000 * Math.sin(2 * Math.PI * 300 * i / rate));
        short[] c = Voice.clean(rec);
        check(c.length > 2 * rate && c.length < 2 * rate + 2 * Voice.MARGIN_FRAMES * Voice.FRAME + Voice.FRAME,
                "the silence before and after is cut, a little kept: " + c.length);
        double sum = 0;
        int peak = 0;
        for (short v : c) {
            sum += (double) v * v;
            peak = Math.max(peak, Math.abs(v));
        }
        double rms = Math.sqrt(sum / c.length);
        check(rms > 2500 && rms < 3600, "a quiet voice is brought up to an even level: " + rms);
        check(peak < 32767, "never clipped");
        eq(Voice.clean(new short[2 * rate]).length, 0, "nothing said: nothing to send");

        int[] cut = Voice.cuts(45 * rate);
        eq(cut.length - 1, 3, "45 s: three messages");
        eq(cut[1], 15 * rate, "of 15 s each, not 20 + 20 + 5");
        eq(cut[3], 45 * rate, "the last ends at the end");
        eq(Voice.cuts(10 * rate).length - 1, 1, "10 s: one message");
        check(cut[1] % Voice.FRAME == 0 && cut[2] % Voice.FRAME == 0, "cuts fall on frames");

        Voice.Encoder same = new Voice.Encoder() {
            public byte[] frame(short[] pcm) {
                return new byte[80];
            }
        };
        byte[] m = Voice.message(c, 0, c.length, same);
        eq(m[0], (byte) Voice.RATE_CODE, "the file says mono 16 kHz");
        eq(m[1] & 0xFF, 80, "and the frame length");
        eq(Voice.frames(m).size(), (c.length + Voice.FRAME - 1) / Voice.FRAME, "every frame in it");
        Voice.Encoder uneven = new Voice.Encoder() {
            int n;

            public byte[] frame(short[] pcm) {
                return new byte[n++ == 3 ? 79 : 80];
            }
        };
        check(Voice.message(c, 0, c.length, uneven) == null, "frames of different sizes aren't sent");
    }

    /**
     * IN op=55 as the game's own reader takes it apart (game.N.P): 37, the time (8), the message id
     * (4), the channel byte, 2 more bytes when the channel has flag 32, the room (4) when
     * (channel & 31) >= 15, the sender's id (4), then "name\ntext".
     */
    private static byte[] chatLine(int channel, int sender, String name, String text) {
        int b = channel;
        int extra = (b & 32) == 32 ? 2 : 0;
        if (extra > 0) b -= 32;
        int room = (b & 31) >= 15 ? 4 : 0;
        byte[] head = new byte[14 + extra + room + 4];
        head[0] = 55;
        head[13] = (byte) channel;
        if (room > 0) head[14 + extra + 3] = 7;                // room 7
        int at = 14 + extra + room;
        head[at] = (byte) (sender >>> 24);
        head[at + 1] = (byte) (sender >>> 16);
        head[at + 2] = (byte) (sender >>> 8);
        head[at + 3] = (byte) sender;
        return concat(head, (name + "\n" + text).getBytes(Protocol.UTF8));
    }

    private static String lastChatName(String chat) {
        int i = chat.lastIndexOf("\"name\":\"");
        return i < 0 ? null : chat.substring(i + 8, chat.indexOf('"', i + 8));
    }

    private static void aChatSendersIdNeverJoinsTheirName() {
        // a sender id whose last bytes are letters or digits ('2' is 0x32, "22" 0x3232, 'a' 0x61, '_' 0x5f)
        int[][] cases = {{3, 0x00000132}, {0, 0x00003232}, {6, 0x00000561}, {9, 0x0000075F}, {12, 0x0000082D},
            {15, 0x00000932}, {18, 0x00000A41}, {3 + 32, 0x00000B32}};
        for (int[] c : cases) {
            GameChat.inbound(chatLine(c[0], c[1], "magoestelar", "vete a escuchar musica feo persi"));
            String chat = GameChat.since(0, 0);
            eq(lastChatName(chat), "magoestelar", "channel " + c[0] + ", sender id 0x" + Integer.toHexString(c[1])
                    + ": the name alone");
            check(chat.endsWith("\"text\":\"vete a escuchar musica feo persi\"}]}") || chat.contains(
                    "\"name\":\"magoestelar\",\"text\":\"vete a escuchar musica feo persi\""), "and the text after it");
        }
        GameChat.inbound(chatLine(3, 0x00000132, "2Fast4u", "hi"));       // a name that starts with a number
        eq(lastChatName(GameChat.since(0, 0)), "2Fast4u", "a name beginning with digits keeps them");
        GameChat.inbound(chatLine(3, 0x00000100, "Ali", "hello"));
        eq(lastChatName(GameChat.since(0, 0)), "Ali", "a sender id with no letter in it, as before");
        byte[] voice = chatLine(12 + Voice.FLAG, 0x00000932, "magoestelar", VOICE_NAME);
        GameChat.inbound(concat(voice, new byte[] {1, 2, 10, 10}));
        eq(lastChatName(GameChat.since(0, 0)), "magoestelar", "a voice line's name, without the sender's id");
    }

    private static void voiceMessagesArriveWithTheirName() {
        byte[] head = new byte[18];
        head[0] = 55;
        head[13] = (byte) (12 + Voice.FLAG);                   // team (4, arriving as 12), a voice line
        head[17] = 9;                                          // the sender
        byte[] line = concat(head, "Ali\n".getBytes(Protocol.UTF8), VOICE_NAME.getBytes(Protocol.UTF8),
                new byte[] {1, 2, 10, 10});
        GameChat.inbound(line);
        String chat = GameChat.since(0, 0);
        check(chat.contains("\"channel\":12,\"name\":\"Ali\",\"text\":\"\",\"voice\":\"" + VOICE_NAME + "\""),
                "a voice line on a channel: " + chat);

        byte[] pm = new byte[21];
        pm[0] = 56;
        pm[17] = (byte) 0xFF;                                  // the sender's id negated: -2
        pm[18] = (byte) 0xFF;
        pm[19] = (byte) 0xFF;
        pm[20] = (byte) 0xFE;
        PrivateChat.inbound(concat(pm, "Bob\n".getBytes(Protocol.UTF8), VOICE_NAME.getBytes(Protocol.UTF8),
                new byte[] {1, 1, 0}));
        String pms = PrivateChat.since(0);
        check(pms.contains("\"id\":2,\"name\":\"Bob\",\"text\":\"\",\"voice\":\"" + VOICE_NAME + "\""),
                "a voice private message: " + pms);

        byte[] mine = concat(new byte[] {25, (byte) Voice.PRIVATE_OUT, 0, 0, 0, 2}, VOICE_NAME.getBytes(Protocol.UTF8),
                new byte[] {1, 1, 0});
        PrivateChat.outbound(mine);
        check(PrivateChat.since(0).contains("\"mine\":true,\"voice\":\"" + VOICE_NAME + "\""),
                "our own voice message shows too");
    }

    // ---------------------------------------------------------------- helpers
    /** IN op=51: hp, mp, then the buff and debuff bytes (-1 leaves one off). */
    private static byte[] answer(int hp, int mp, int buffs, int debuffs) {
        byte[] head = concat(new byte[] {51}, Ask.packet(0, hp), Ask.packet(0, mp));
        byte[] m = new byte[] {51, head[2], head[3], head[4], head[5], head[7], head[8], head[9], head[10]};
        if (buffs >= 0) m = concat(m, new byte[] {(byte) buffs});
        if (debuffs >= 0) m = concat(m, new byte[] {(byte) debuffs});
        return m;
    }

    private static byte[] concat(byte[]... parts) {
        int n = 0;
        for (byte[] p : parts) n += p.length;
        byte[] out = new byte[n];
        int at = 0;
        for (byte[] p : parts) {
            System.arraycopy(p, 0, out, at, p.length);
            at += p.length;
        }
        return out;
    }

    /** Another player's cast carries its targets and their HP after it (agent 44): a monster that
     *  someone else has started on is known at once. One struck to 0 is a death as before. */
    private static void everyCastSaysWhomItStruck(Map<String, String> contract) {
        String text = contract.get("cast_packet").replace("\\r", "\r").replace("\\n", "\n");
        byte[] body = text.getBytes(Protocol.UTF8);
        byte[] m = new byte[body.length + 1];
        m[0] = 41;
        System.arraycopy(body, 0, m, 1, body.length);
        long before = System.currentTimeMillis() - 1;
        World.inbound(m);
        String got = World.casts(before);
        check(got.contains("\"caster\":4152,\"seq\":7,\"skill\":\"Mind Whip\""), "the cast is read: " + got);
        check(got.contains("\"targets\":" + contract.get("cast_targets")), "with its targets: " + got);
        check(!got.contains("\"hits\""), "and no hits section, which this packet doesn't have: " + got);
        check(got.contains("[-6,"), "the one struck to 0 died: " + got);
        check(World.castSince(4152, before), "a held corpse cast sees its caster's cast come back");
        check(!World.castSince(4153, before), "not someone else's");
        check(!World.castSince(4152, System.currentTimeMillis() + 1000), "nor one from before it started");
        check(World.castSince(4152, before, "Mind Whip"), "the held skill's own cast ends a hold");
        check(!World.castSince(4152, before, "Draw Blood"),
                "another skill of ours doesn't (the last shots of a fight come back after the kill)");
        check(!World.castSince(4152, before, "Whip"), "nor a name that only ends the same way");
        World.inbound(op41("4152,9,Level 2 Draw Blood\n-6,-1\r\n0\r\n0"));
        check(World.castSince(4152, before, "Draw Blood"), "a ranked name of the skill counts");
        eq(World.targets(new String[] {"4152,8,Buff\n4152,64200"}), null, "a cast with no target line has none");
    }

    private static byte[] op41(String text) {
        byte[] body = text.getBytes(Protocol.UTF8);
        byte[] m = new byte[body.length + 1];
        m[0] = 41;
        System.arraycopy(body, 0, m, 1, body.length);
        return m;
    }

    /** The profession key's corpse rules (game.i.a, javap 2026-11-11): exactly 0 HP, within 20 tiles. */
    private static void corpseSkillsTakeOnlyAFreshCorpseInReach() {
        eq(String.valueOf(Memory.corpseCheck(0, 3.0)), "null", "a fresh corpse close by");
        eq(String.valueOf(Memory.corpseCheck(0, 4.5)), "null", "a fresh corpse at the edge of harvesting range");
        eq(Memory.corpseCheck(0, 4.6), "is too far to harvest from here",
                "past it: the server answers nothing from there (live 2026-11-12: 1.1-4.5 tiles)");
        eq(Memory.corpseCheck(0, 20.5), "is out of reach", "past 20 tiles");
        eq(Memory.corpseCheck(1, 3.0), "is alive", "a monster still alive");
        eq(Memory.corpseCheck(-1, 3.0), "is no fresh corpse (harvested or dried)", "the game's other dead state");
        eq(Memory.corpseCheck(-2, 3.0), "is no fresh corpse (harvested or dried)", "and the third");
        check(Act.castMethod(Object.class) == null, "no cast method on a class without one");
    }

    /** A stand-in for game.i with the cast method (world.a(ISIZ)) and the attack keys' release. */
    static final class CastWorld {
        final java.util.List<String> calls = java.util.Collections.synchronizedList(new java.util.ArrayList<String>());
        void a(int target, short skill, int pk, boolean stand) { calls.add("cast " + target); if (stand) calls.add("standing"); }
        void a(long delay) { calls.add("up"); }
        void a(int s, boolean sus, boolean lk, long delay) { calls.add("down " + s); }
        int count(String what) {
            int n = 0;
            synchronized (calls) {
                for (String c : calls) if (c.equals(what)) n++;
            }
            return n;
        }
    }

    /** Live night 2026-11-12: one cast and no release left the "attacking" bit up, and every walk
     *  failed. A held cast is sent again until a reason comes, then let go exactly once. */
    private static void aCorpseCastIsHeldLikeTheKeyAndAlwaysLetGo() throws Exception {
        java.lang.reflect.Method down = Act.castMethod(CastWorld.class);
        java.lang.reflect.Method up = Act.releaseMethod(CastWorld.class);
        check(down != null && up != null, "the cast method and the release are found by their shapes");

        final CastWorld answered = new CastWorld();
        Act.hold(answered, down, up, -7, (short) 21, 0, Act.CAST_STANDING, 10L, 2000L, new Act.StillOn() {
            @Override
            public String why() {
                return answered.count("cast -7") >= 3 ? "cast" : null;
            }
        });
        eq(answered.count("cast -7"), 1, "the first cast goes out before the command answers");
        Thread.sleep(300L);
        eq(answered.count("cast -7"), 3, "sent again until our cast came back");
        eq(answered.count("up"), 1, "then the key is let go, once");
        eq(answered.count("standing"), answered.count("cast -7"), "every send casts standing: no walk to the corpse");
        eq(String.valueOf(answered.calls.get(answered.calls.size() - 1)), "up", "and nothing is sent after it");

        CastWorld unanswered = new CastWorld();
        Act.hold(unanswered, down, up, -8, (short) 21, 0, false, 10L, 100L, new Act.StillOn() {
            @Override
            public String why() {
                return null;
            }
        });
        Thread.sleep(400L);
        check(unanswered.count("cast -8") >= 3, "a cast never answered is held for the whole hold");
        eq(unanswered.count("up"), 1, "and still let go when the hold is up");

        CastWorld fight = new CastWorld();
        Act.hold(fight, down, up, -9, (short) 21, 0, false, 10L, 5000L, new Act.StillOn() {
            @Override
            public String why() {
                return null;
            }
        });
        Act.press(fight, 2, false, false, 20L);
        Thread.sleep(200L);
        int sent = fight.count("cast -9");
        Thread.sleep(100L);
        eq(fight.count("cast -9"), sent, "an attack key press ends the held cast");
        eq(fight.count("up"), 1, "with the press's own release only");

        CastWorld again = new CastWorld();
        Act.hold(again, down, up, -10, (short) 21, 0, false, 10L, 5000L, new Act.StillOn() {
            @Override
            public String why() {
                return null;
            }
        });
        Act.endCast(true);
        Act.endCast(true);
        Thread.sleep(100L);
        eq(again.count("up"), 1, "ending a held cast twice lets go once");
    }

    /** IN op=17 lists the profession skills as "id,rank,name"; the client drops the rank (agent 49). */
    private static void professionRanksAreKeptFromTheLoginList() {
        byte[] body = "\n21,5,Draw Blood\n13,3,Fishing\n1,0,Snuggle".getBytes(Protocol.UTF8);
        byte[] m = new byte[body.length + 1];
        m[0] = 17;
        System.arraycopy(body, 0, m, 1, body.length);
        World.inbound(m);
        StringBuilder sb = new StringBuilder();
        Profession.json(sb);
        eq(sb.toString(), "{\"21\":5,\"13\":3,\"1\":0}", "each skill's rank, by its id");
        World.inbound(new byte[] {17, 'x', ','});
        sb.setLength(0);
        Profession.json(sb);
        eq(sb.toString(), "{\"21\":5,\"13\":3,\"1\":0}", "a list with no skill in it changes nothing");
    }

    /** Stand-ins for game.i: the one method of the attack keys' shape is found whatever its name. */
    static final class OneShape {
        int slot;
        boolean sustain;
        boolean lock;
        void q(int a, boolean b) { }
        void zz(int s, boolean sus, boolean lk, long delay) { slot = s; sustain = sus; lock = lk; }
    }

    static final class TwoShapes {
        void a(int s, boolean b, boolean c, long d) { }
        void b(int s, boolean b, boolean c, long d) { }
    }

    private static void theAttackKeyMethodIsFoundByItsShape() throws Exception {
        java.lang.reflect.Method m = Act.pressMethod(OneShape.class);
        eq(m == null ? null : m.getName(), "zz", "found by its parameters");
        OneShape w = new OneShape();
        m.invoke(w, 12, true, false, 0L);
        check(w.slot == 12 && w.sustain && !w.lock, "and called the way game.Win calls it");
        eq(Act.pressMethod(TwoShapes.class), null, "two of that shape: neither is guessed");
    }

    /** A stand-in for game.i with both halves of an attack key: down (slot) and up (release). */
    static final class KeyWorld {
        final java.util.List<String> calls = java.util.Collections.synchronizedList(new java.util.ArrayList<String>());
        void a(int s, boolean sus, boolean lk, long delay) { calls.add("down " + s); }
        void a(long delay) { calls.add("up"); }
        void b(int other) { }
    }

    private static void aSlotPressIsLetGoLikeAKey() throws Exception {
        KeyWorld w = new KeyWorld();
        eq(Act.press(w, 3, false, false, 20L), "pressed 3", "a slot press answers as before");
        eq(String.valueOf(w.calls), "[down 3]", "key down first, the release waits a key's hold");
        Thread.sleep(200L);
        eq(String.valueOf(w.calls), "[down 3, up]", "then the key comes back up, or the game thinks it is held");
        KeyWorld quick = new KeyWorld();
        Act.press(quick, 1, false, false, 100L);
        Act.press(quick, 2, false, false, 100L);
        Thread.sleep(400L);
        eq(String.valueOf(quick.calls), "[down 1, down 2, up]", "a press before the last let go takes its release over");
        eq(Act.releaseMethod(OneShape.class), null, "no release of that shape: not guessed");
    }

    // ---------------------------------------------------------------- patches of game classes

    /**
     * A stand-in for the game's voice player (game.ac), with its bug: a message whose rate differs
     * from the last opens its line at the last rate, then keeps the new one. `opened` stands for
     * the line's rate; nothing is played.
     */
    public static final class PlayerStandIn {
        public int rate = 16000;
        public float opened = 16000;
        public int decodedAt;
        public int frames;

        public synchronized void a(byte[] sound, float x, float y) {
            int channels = sound[0] / 10 + 1;
            int code = sound[0] % 10;
            int r = code == 0 ? 8000 : code == 1 ? 16000 : code == 2 ? 24000 : 48000;
            int frame = 255 & sound[1];
            if (r != rate) {
                javax.sound.sampled.AudioFormat f = new javax.sound.sampled.AudioFormat(
                        javax.sound.sampled.AudioFormat.Encoding.PCM_SIGNED, rate, 16, 2, 4, rate, false);
                try {
                    opened = f.getSampleRate();
                } catch (RuntimeException e) {
                    return;
                }
                rate = r;
            }
            decodedAt = rate * channels;
            for (int i = 2; i < sound.length; i += frame) frames++;
        }
    }

    /** PlayerStandIn as the agent changes it when the game loads it, in a loader of its own. */
    private static Object mendedPlayer() throws Exception {
        final String name = PlayerStandIn.class.getName();
        final byte[] mended = VoicePlayer.patch(classBytes("AgentTests$PlayerStandIn.class"));
        check(mended != null, "the stand-in is recognised as the voice player");
        check(VoicePlayer.patch(mended) == null, "and a mended player is left alone");
        ClassLoader loader = new ClassLoader(AgentTests.class.getClassLoader()) {
            @Override
            protected Class<?> loadClass(String n, boolean resolve) throws ClassNotFoundException {
                if (n.equals(name)) {
                    Class<?> c = findLoadedClass(n);
                    return c != null ? c : defineClass(n, mended, 0, mended.length);
                }
                return super.loadClass(n, resolve);
            }
        };
        return loader.loadClass(name).getConstructor().newInstance();     // the JVM verifies it here
    }

    private static byte[] classBytes(String resource) throws Exception {
        java.io.InputStream in = AgentTests.class.getResourceAsStream(resource);
        java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        for (int n; (n = in.read(buf)) > 0; ) bo.write(buf, 0, n);
        in.close();
        return bo.toByteArray();
    }

    private static void play(Object player, byte[] sound) throws Exception {
        player.getClass().getMethod("a", byte[].class, float.class, float.class).invoke(player, sound, 0f, 0f);
    }

    private static Object field(Object o, String name) throws Exception {
        return o.getClass().getField(name).get(o);
    }

    private static void theVoicePlayerOpensEachMessageAtItsOwnRate() throws Exception {
        byte[] at8k = {0, 2, 9, 9, 9, 9};
        byte[] at16k = {1, 2, 9, 9, 9, 9};
        PlayerStandIn game = new PlayerStandIn();
        game.a(at8k, 0f, 0f);
        game.a(at16k, 0f, 0f);
        eq(game.opened, 8000f, "the game as it is: after an 8 kHz message, 16 kHz plays on an 8 kHz line");

        Object mended = mendedPlayer();
        play(mended, at8k);
        eq(field(mended, "opened"), 8000f, "mended: an 8 kHz message gets an 8 kHz line");
        play(mended, at16k);
        eq(field(mended, "opened"), 16000f, "and the next 16 kHz message a 16 kHz line again");
        eq(field(mended, "decodedAt"), 16000, "decoded at its own rate");
        eq(field(mended, "frames"), 4, "every frame of both played");
    }

    private static void theVoiceFixCanBeSwitchedOff() throws Exception {
        byte[] at8k = {0, 2, 9, 9, 9, 9};
        byte[] at16k = {1, 2, 9, 9, 9, 9};
        Object p = mendedPlayer();
        java.lang.reflect.Field off = p.getClass().getField(VoicePlayer.FIELD);
        eq(off.getBoolean(null), false, "a game starts with the fix on");
        off.setBoolean(null, true);
        play(p, at8k);
        play(p, at16k);
        eq(field(p, "opened"), 8000f, "switched off: the game's own player, deep voice and all");
        eq(field(p, "frames"), 4, "and it still plays every frame");
        off.setBoolean(null, false);
        play(p, at8k);
        play(p, at16k);
        eq(field(p, "opened"), 16000f, "switched on again: each message at its own rate");
        play(p, new byte[] {0, 0, 0, 0});
        eq(field(p, "frames"), 8, "and a half-read file skipped again");
    }

    private static void theVoicePlayerSkipsAHalfReadFile() throws Exception {
        Object mended = mendedPlayer();
        play(mended, null);
        play(mended, new byte[0]);
        play(mended, new byte[] {1, 40});
        play(mended, new byte[] {0, 0, 0, 0, 0, 0});           // read while the other game rewrote it
        play(mended, new byte[] {121, 111, 5, 5});             // not mono or stereo
        play(mended, new byte[] {-3, 40, 5, 5});
        eq(field(mended, "rate"), 16000, "none of them changes the player's rate");
        eq(field(mended, "frames"), 0, "and none is played");
        play(mended, new byte[] {11, (byte) 200, 5, 5});       // stereo, a frame length over 127
        eq(field(mended, "frames"), 1, "a real message still plays");
    }

    /** The rate fix on the game's own bytes (javap of game.ac, 2026-10-29): `iload_3` holds the
     *  new rate, field #31 the old one; the block opens the line and stores the new rate. */
    private static void theVoicePlayerRateFixMatchesTheGamesCode() {
        byte[] c = {
            0x1D, 0x2A, (byte) 0xB4, 0x00, 0x1F, (byte) 0x9F, 0x00, 0x12,  // iload_3; aload_0; getfield c; if_icmpeq 23
            0x2A, (byte) 0xB4, 0x00, 0x1F, (byte) 0x86,                    // aload_0; getfield c; i2f   (sample rate)
            0x2A, (byte) 0xB4, 0x00, 0x1F, (byte) 0x86,                    // aload_0; getfield c; i2f   (frame rate)
            0x2A, 0x1D, (byte) 0xB5, 0x00, 0x1F,                           // aload_0; iload_3; putfield c
            0x2A, (byte) 0xB4, 0x00, 0x1F, 0x00, 0x00, 0x00, 0x00,         // after the block: the decoder's rate
        };
        check(VoicePlayer.openAtNewRate(c, 0, c.length), "the game's rate test is found");
        eq(String.format("%02x%02x%02x%02x %02x%02x%02x%02x", c[8], c[9], c[10], c[11], c[13], c[14], c[15], c[16]),
                "1d000000 1d000000", "both reads of the old rate become the new rate");
        eq(String.format("%02x%02x%02x%02x", c[23], c[24], c[25], c[26]), "2ab4001f",
                "the field read after the block stays");
    }

    /** A stand-in for the game's sound engine (game.aT): its speak method of the known shape. */
    public static final class SpeechStandIn {
        public int spoken;

        public void a(int kind, String text, int b, float x, float y, int c) {
            switch (kind) {
                case 0: spoken++; break;
                case 5: spoken += 2; break;
                default: spoken += 3;
            }
        }
    }

    private static void theSpeechSwitchStillSilences() throws Exception {
        final String name = SpeechStandIn.class.getName();
        final byte[] gated = SpeechSwitch.patch(classBytes("AgentTests$SpeechStandIn.class"));
        check(gated != null, "the speech switch finds the speak method");
        ClassLoader loader = new ClassLoader(AgentTests.class.getClassLoader()) {
            @Override
            protected Class<?> loadClass(String n, boolean resolve) throws ClassNotFoundException {
                if (n.equals(name)) {
                    Class<?> c = findLoadedClass(n);
                    return c != null ? c : defineClass(n, gated, 0, gated.length);
                }
                return super.loadClass(n, resolve);
            }
        };
        Class<?> c = loader.loadClass(name);
        Object o = c.getConstructor().newInstance();
        java.lang.reflect.Method speak = c.getMethod("a", int.class, String.class, int.class, float.class, float.class, int.class);
        speak.invoke(o, 5, "hi", 0, 0f, 0f, 0);
        eq(field(o, "spoken"), 2, "speaking: the method runs, its switch too");
        c.getField(SpeechSwitch.FIELD).setBoolean(null, true);
        speak.invoke(o, 0, "hi", 0, 0f, 0f, 0);
        eq(field(o, "spoken"), 2, "silenced: nothing is said");
        c.getField(SpeechSwitch.FIELD).setBoolean(null, false);
        speak.invoke(o, 7, "hi", 0, 0f, 0f, 0);
        eq(field(o, "spoken"), 5, "and speaking again");
    }

    private static Map<String, String> contract(String path) throws Exception {
        Map<String, String> out = new HashMap<String, String>();
        for (String line : Files.readAllLines(new File(path).toPath(), Protocol.UTF8)) {
            line = line.trim();
            int eq = line.indexOf('=');
            if (line.isEmpty() || line.startsWith("#") || eq < 0) continue;
            out.put(line.substring(0, eq), line.substring(eq + 1));
        }
        return out;
    }

    private static void eq(Object got, Object want, String what) {
        boolean same = got instanceof Number && want instanceof Number
                ? ((Number) got).longValue() == ((Number) want).longValue()     // an int field against a long one
                : got == null ? want == null : got.equals(want);
        check(same, what + ": got " + got + ", want " + want);
    }

    private static void check(boolean ok, String what) {
        run++;
        if (!ok) {
            failed++;
            System.out.println("FAILED " + what);
        }
    }
}
