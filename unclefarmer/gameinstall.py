"""Finding Mist World, and adding Uncle Farmer's agent to it.

The game is a Java program launched by mw.exe, which passes every line of mw.exe.vmoptions to Java.
One line there loads our agent:

    -javaagent:<Uncle Farmer>\\agent\\unclefarmer-agent.jar=<Uncle Farmer>\\agent\\run

Nothing else in the game folder is changed. The original file is kept once as
mw.exe.vmoptions.bak-unclefarmer. Some other tools (mwMod) delete every -javaagent line when they start
the game; if the agent stops answering after using one, install it again.

A game loads the agent only as it starts, so a reinstall (the line gone or pointing at another
Uncle Farmer, or a game running without this copy's agent) closes the open games first:
stale_games() finds them, close_games() closes them.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import shutil
from collections.abc import Callable

from . import paths
from .clock import CLOCK, Clock

VMOPTIONS = "mw.exe.vmoptions"
MARKER = "unclefarmer-agent.jar"
# Lines an older build added (MW Farmer, before the rename): replaced on install and removed on
# uninstall, so the game never loads two copies of the agent.
LEGACY = ("mwfarmer-agent.jar",)
# The agent version this copy ships (StateServer.VERSION in agent/src; a test keeps them equal).
# A running game whose agent answers an older one loaded it before this copy was installed.
AGENT_VERSION = 67
CLOSE_WAIT = 20.0       # seconds a game gets to close through its own close button before it is ended


def _ours(line: str) -> bool:
    return MARKER in line or any(m in line for m in LEGACY)


def agent_line() -> str:
    return "-javaagent:%s=%s" % (paths.AGENT_JAR, paths.AGENT_RUN)


def is_game_folder(folder: str | None) -> bool:
    return bool(folder) and os.path.isfile(os.path.join(folder or "", "mw.exe"))


def running_game_folders() -> list[str]:
    """Folders of every running mw.exe (so the user rarely has to browse)."""
    out: list[str] = []
    for _pid, folder in running_games():
        if folder not in out:
            out.append(folder)
    return out


def running_games() -> list[tuple[int, str]]:
    """(pid, folder) of every running mw.exe. The game's Java runs inside mw.exe, so the pid is
    also the one its agent writes in agent.<pid>.port."""
    out: list[tuple[int, str]] = []
    psapi, kernel = ctypes.windll.psapi, ctypes.windll.kernel32
    pids = (wt.DWORD * 4096)()
    got = wt.DWORD()
    if not psapi.EnumProcesses(ctypes.byref(pids), ctypes.sizeof(pids), ctypes.byref(got)):
        return out
    for pid in pids[:got.value // ctypes.sizeof(wt.DWORD)]:
        h = kernel.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            continue
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wt.DWORD(1024)
            if kernel.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                if os.path.basename(buf.value).lower() == "mw.exe":
                    out.append((int(pid), os.path.dirname(buf.value)))
        finally:
            kernel.CloseHandle(h)
    return out


def _agent_version(pid: int) -> int:
    """The version the game's agent answers; 0 when it doesn't answer."""
    from .link import AgentError, AgentLink     # link reads settings; this module stays light
    try:
        with AgentLink(pid=pid, timeout=3) as a:
            return int(a.send("version").split()[1])
    except (AgentError, OSError, ValueError, IndexError):
        return 0


def stale_games() -> list[tuple[int, int]]:
    """(pid, agent version) of every running game without this copy's agent loaded: version 0 for
    one with no agent at all (started before the install, or after a tool removed the line), an
    older number for one that loaded an older Uncle Farmer's agent."""
    from .link import agents
    loaded = {pid for _port, pid, _secret in agents()}
    out: list[tuple[int, int]] = []
    for pid, _folder in running_games():
        version = _agent_version(pid) if pid in loaded else 0
        if version < AGENT_VERSION:
            out.append((pid, version))
    return out


def _alive(pid: int) -> bool:
    from .link import _alive  # pyright: ignore[reportPrivateUsage]
    return _alive(pid)


def _end(pid: int) -> None:
    """End the game's process (one that didn't close through its own close button)."""
    kernel = ctypes.windll.kernel32
    h = kernel.OpenProcess(0x0001, False, pid)      # PROCESS_TERMINATE
    if h:
        try:
            kernel.TerminateProcess(h, 1)
        finally:
            kernel.CloseHandle(h)


def _ask_to_close(pid: int) -> bool:
    """The game closes as its window's close button does (agent 15's closegame). False when its
    agent can't be asked."""
    from .link import AgentError, AgentLink
    try:
        with AgentLink(pid=pid, timeout=3) as a:
            a.send("arm")
            return a.send("closegame") == "closing"
    except (AgentError, OSError):
        return False


def close_games(pids: list[int], wait: float = CLOSE_WAIT, clock: Clock = CLOCK,
                alive: Callable[[int], bool] = _alive) -> list[int]:
    """Close every game in pids: through its own close button where its agent answers, then
    whatever is still open after `wait` seconds (or has no agent to ask) is ended. Returns the
    pids still running after that (normally none)."""
    asked = [pid for pid in pids if alive(pid) and _ask_to_close(pid)]
    for pid in pids:
        if pid not in asked and alive(pid):
            _end(pid)
    until = clock.time() + wait
    while any(alive(pid) for pid in asked) and clock.time() < until:
        clock.sleep(0.5)
    for pid in asked:
        if alive(pid):
            _end(pid)
    left = [pid for pid in pids if alive(pid)]
    until = clock.time() + 5.0              # an ended process lets go of its files a moment later
    while left and clock.time() < until:
        clock.sleep(0.25)
        left = [pid for pid in left if alive(pid)]
    return left


def _read_lines(folder: str) -> tuple[str, list[str], str]:
    path = os.path.join(folder, VMOPTIONS)
    if not os.path.exists(path):
        return path, [], "\r\n"
    with open(path, "rb") as f:
        raw = f.read()
    newline = "\r\n" if b"\r\n" in raw or not raw else "\n"
    text = raw.decode("utf-8", errors="replace")
    return path, [l for l in text.splitlines() if l.strip()], newline


def status(folder: str | None) -> str:
    """'installed', 'other' (an older Uncle Farmer path), 'missing', or 'nogame'."""
    if not is_game_folder(folder):
        return "nogame"
    _path, lines, _nl = _read_lines(folder or "")
    ours = [l for l in lines if _ours(l)]
    if not ours:
        return "missing"
    return "installed" if agent_line() in ours else "other"


FOLDER_FILE = "game_folder.txt"     # the agent writes the folder of the game it runs in here


def agent_folder() -> str:
    """The game folder the agent last ran in (agent/run/game_folder.txt, written as the game
    starts), or ""."""
    try:
        with open(os.path.join(paths.AGENT_RUN, FOLDER_FILE), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def folder_of(pid: int | None, fallback: str = "") -> str:
    """The folder of the game running as pid (agent 48 writes agent.<pid>.folder as it starts),
    else fallback (the settings' game folder). Several copies of the game can run at once, and a
    character's phrases and key settings are in the copy it runs from."""
    if pid is None:
        return fallback
    try:
        with open(os.path.join(paths.AGENT_RUN, "agent.%d.folder" % int(pid)), encoding="utf-8") as f:
            folder = f.read().strip()
    except (OSError, TypeError, ValueError):
        return fallback
    return folder if is_game_folder(folder) else fallback


def find_installed(remembered: str | None = "") -> str | None:
    """The game folder our agent is installed in: the remembered one while it still is, else a
    running game's, else the one the agent last ran in. None when there is none. The setting can
    be empty while the agent is in the game (the line was added by hand, or Settings was saved with
    the box left empty): asking to install it at every start then was wrong, and without the
    folder the game's key settings and texts weren't read either."""
    if remembered and status(remembered) == "installed":
        return remembered
    for folder in running_game_folders() + [agent_folder()]:
        if folder and status(folder) == "installed":
            return folder
    return None


def install(folder: str) -> None:
    path, lines, nl = _read_lines(folder)
    backup = path + ".bak-unclefarmer"
    if os.path.exists(path) and not os.path.exists(backup):
        shutil.copyfile(path, backup)
    lines = [l for l in lines if not _ours(l)] + [agent_line()]
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(nl.join(lines) + nl)
    os.makedirs(paths.AGENT_RUN, exist_ok=True)


def uninstall(folder: str) -> None:
    path, lines, nl = _read_lines(folder)
    if not os.path.exists(path):
        return
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(nl.join(l for l in lines if not _ours(l)) + nl)
