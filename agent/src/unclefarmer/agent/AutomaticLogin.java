package unclefarmer.agent;

import java.awt.Frame;
import java.io.File;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.util.Collection;
import java.util.List;
import java.util.regex.Pattern;

/**
 * Starts one of the game's already saved accounts and chooses a known character without keyboard
 * input. The game continues to own its saved credential file; its bytes stay in the game JVM and
 * are never converted to text, returned, logged, or saved by Uncle Farmer.
 */
final class AutomaticLogin {

    private static final Pattern EMAIL = Pattern.compile("[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}",
            Pattern.CASE_INSENSITIVE);
    private static final long PICKER_TIMEOUT_MILLIS = 30000L;
    private static final long WORLD_TIMEOUT_MILLIS = 30000L;
    private static final Object LOCK = new Object();
    private static volatile boolean running;
    private static volatile String status = "idle";

    private AutomaticLogin() { }

    /** The saved account currently in use, or selected at the game's sign-in screen. */
    static String account() {
        String email = connectedAccount();
        if (email == null) email = selectedAccount();
        return email == null ? "{\"ok\":false,\"error\":\"no saved account selected\"}"
                : "{\"ok\":true,\"email\":\"" + Protocol.jsonEscape(email) + "\"}";
    }

    /** Starts the native saved-account connection, then selects only when this ID is in its picker. */
    static String start(String email, String idText) {
        final int id;
        try {
            id = Integer.parseInt(idText);
        } catch (RuntimeException ignored) {
            return "{\"ok\":false,\"error\":\"invalid character id\"}";
        }
        if (id <= 0) return "{\"ok\":false,\"error\":\"invalid character id\"}";
        if (email == null || !EMAIL.matcher(email).matches()) {
            return "{\"ok\":false,\"error\":\"invalid saved account\"}";
        }
        synchronized (LOCK) {
            if (running) return "{\"ok\":false,\"error\":\"automatic login is already running\"}";
            String connected = connectedAccount();
            if (connected != null && !connected.equalsIgnoreCase(email)) {
                return "{\"ok\":false,\"error\":\"another saved account is already connecting\"}";
            }
            if (connected == null) {
                String problem = startSavedAccount(email);
                if (problem != null) return "{\"ok\":false,\"error\":\"" + Protocol.jsonEscape(problem) + "\"}";
            }
            running = true;
            status = "waiting for character picker";
        }
        waitForPicker(id);
        return "{\"ok\":true,\"id\":" + id + ",\"state\":\"waiting for character picker\"}";
    }

    static String status() {
        return "{\"ok\":true,\"running\":" + running + ",\"status\":\""
                + Protocol.jsonEscape(status) + "\"}";
    }

    private static void waitForPicker(final int id) {
        Thread worker = new Thread(new Runnable() {
            @Override public void run() {
                long deadline = System.currentTimeMillis() + PICKER_TIMEOUT_MILLIS;
                try {
                    while (System.currentTimeMillis() < deadline) {
                        Object menu = activeCharacterMenu();
                        if (menu != null) {
                            if (!hasCharacter(menu, id)) {
                                status = "character is not in the account picker";
                                return;
                            }
                            if (!select(menu, id)) {
                                status = "character selection could not start";
                                return;
                            }
                            status = "loading character";
                            long worldDeadline = System.currentTimeMillis() + WORLD_TIMEOUT_MILLIS;
                            status = waitForCharacter(id, worldDeadline) ? "ready" : "timed out loading character";
                            return;
                        }
                        Thread.sleep(50L);
                    }
                    status = "timed out waiting for character picker";
                } catch (InterruptedException ignored) {
                    Thread.currentThread().interrupt();
                    status = "cancelled";
                } finally {
                    running = false;
                }
            }
        }, "Uncle Farmer automatic login");
        worker.setDaemon(true);
        worker.start();
    }

    /** The picker action only begins loading. Do not let the Python bot read the old empty world. */
    private static boolean waitForCharacter(int id, long deadline) throws InterruptedException {
        while (System.currentTimeMillis() < deadline) {
            try {
                if (Memory.selfId() == id && Memory.snapshot().startsWith("{\"ok\":true")) return true;
            } catch (Memory.Unavailable ignored) { }
            Thread.sleep(50L);
        }
        return false;
    }

    /** The exact native constructor the Login button uses for an existing saved account. */
    private static String startSavedAccount(String email) {
        Frame window = Memory.window();
        if (window == null) return "no game window";
        File savedFile = new File("user", email);
        if (!savedFile.isFile()) return "this is not a saved account";
        try {
            Object model = field(window, Memory.WIN_WORLD);
            if (model == null) return "game model is not ready";
            Class<?> network = Class.forName("game.N");
            byte[] saved = Files.readAllBytes(savedFile.toPath());
            Constructor<?> connection = network.getConstructor(window.getClass(), model.getClass(), byte.class,
                    String.class, byte[].class, boolean.class, boolean.class);
            Object client = connection.newInstance(window, model, Byte.valueOf((byte) 1), email, saved,
                    Boolean.TRUE, Boolean.TRUE);
            network.getMethod("a", network).invoke(null, client);
            Object bootstrap = Class.forName("game.w").getConstructor().newInstance();
            Object channel = field(bootstrap, "a");
            if (channel == null) {
                network.getMethod("a", network).invoke(null, new Object[] {null});
                return "saved-account connection failed";
            }
            Field clientChannel = network.getDeclaredField("c");
            clientChannel.setAccessible(true);
            clientChannel.set(client, channel);
            startCompanionConnection();
            return null;
        } catch (Throwable ignored) {
            return "saved-account login could not start";
        }
    }

    /** The game's saved-account Login action also starts its companion connection after Netty. */
    private static void startCompanionConnection() throws ReflectiveOperationException {
        Class<?> companion = Class.forName("game.x");
        Object connection = companion.getConstructor().newInstance();
        companion.getMethod("a", companion).invoke(null, connection);
        companion.getMethod("a").invoke(null);
    }

    private static String connectedAccount() {
        try {
            Class<?> network = Class.forName("game.N");
            Object client = network.getMethod("a").invoke(null);
            Object account = field(client, "f");
            return account instanceof String && EMAIL.matcher((String) account).matches() ? (String) account : null;
        } catch (Throwable ignored) {
            return null;
        }
    }

    private static String selectedAccount() {
        Frame window = Memory.window();
        if (window == null) return null;
        try {
            Object screens = staticField(window.getClass(), "h");
            if (!(screens instanceof Collection)) return null;
            for (Object entry : (Collection<?>) screens) {
                Object text = field(entry, "c");
                if (text instanceof String && EMAIL.matcher((String) text).matches()) return (String) text;
            }
        } catch (Throwable ignored) { }
        return null;
    }

    /** The client only accepts an action for the topmost menu, never a stale one. */
    private static Object activeCharacterMenu() {
        Frame window = Memory.window();
        Object model = window == null ? null : field(window, Memory.WIN_WORLD);
        Object menus = field(model, "U");
        if (!(menus instanceof List) || ((List<?>) menus).isEmpty()) return null;
        Object menu = ((List<?>) menus).get(((List<?>) menus).size() - 1);
        Object type = field(menu, "b"), page = field(menu, "c");
        return type instanceof Integer && ((Integer) type).intValue() == 11
                && page instanceof Integer && ((Integer) page).intValue() == 2 ? menu : null;
    }

    /** The picker is a normal dialog grid: find the requested character before selecting it. */
    private static boolean hasCharacter(Object menu, int wanted) {
        Object groups = field(menu, "g");
        if (!(groups instanceof Collection)) return false;
        for (Object group : (Collection<?>) groups) {
            if (group instanceof Collection) {
                for (Object entry : (Collection<?>) group) {
                    if (characterId(entry) == wanted) return true;
                }
            }
        }
        return false;
    }

    /** Calls the client's character-picker action, not the ordinary dialog Enter action. */
    private static boolean select(Object menu, int id) {
        Frame window = Memory.window();
        Object model = window == null ? null : field(window, Memory.WIN_WORLD);
        if (model == null) return false;
        try {
            Method select = model.getClass().getMethod("a", menu.getClass(), window.getClass(), int.class);
            synchronized (model) {
                Object result = select.invoke(model, menu, window, Integer.valueOf(id));
                if (result instanceof Boolean && !((Boolean) result).booleanValue()) return false;
            }
            return true;
        } catch (Throwable error) {
            Log.error("automatic character selection", error);
            return false;
        }
    }

    private static int characterId(Object entry) {
        Object kind = field(entry, "a"), ids = field(entry, "d");
        if (!(kind instanceof Integer) || ((Integer) kind).intValue() != 12
                || !(ids instanceof int[]) || ((int[]) ids).length == 0) return 0;
        return ((int[]) ids)[0];
    }

    private static Object field(Object target, String name) {
        if (target == null) return null;
        try {
            for (Class<?> type = target.getClass(); type != null && type != Object.class; type = type.getSuperclass()) {
                try {
                    Field field = type.getDeclaredField(name);
                    field.setAccessible(true);
                    return field.get(target);
                } catch (NoSuchFieldException ignored) { }
            }
        } catch (Throwable ignored) { }
        return null;
    }

    private static Object staticField(Class<?> type, String name) throws ReflectiveOperationException {
        Field field = type.getDeclaredField(name);
        field.setAccessible(true);
        return field.get(null);
    }
}
