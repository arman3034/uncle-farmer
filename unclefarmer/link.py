"""Talking to the agent inside a running game.

The agent picks a free port in 17311..17330 and writes agent.<pid>.port ("port pid secret") into
agent\\run. A connection must start with `auth <secret>`. One request line, one reply line.
"""

from __future__ import annotations

import ctypes
import glob
import os
import socket
import threading
from typing import Any, Protocol

from . import gamelang, jsonio as json, paths, settings

HOST = "127.0.0.1"

# Confirmed against the game client's live server routes.  The agent reports only the port; this
# turns that stable route into the name players use in the UI.
SERVER_NAMES = {8767: "S1", 8769: "S2"}


class JsonLink(Protocol):
    """A link only read from: a request line and the agent's JSON answer (the scan, the kill count)."""

    def json(self, line: str) -> Any: ...


class SendLink(Protocol):
    """A link only told things: a request line and the agent's answer as text (trust's `idof`)."""

    def send(self, line: str) -> str: ...


class GameLink(JsonLink, SendLink, Protocol):
    """What the bot asks of its link to the game: a request line and its answer, as text or as
    the agent's JSON. AgentLink is the real one; the tests hand the bot stand-ins of their own."""


class OpenLink(GameLink, Protocol):
    """A link its holder also closes when done (the private-message thread's own link)."""

    def close(self) -> None: ...


class AgentError(RuntimeError):
    pass


def _alive(pid: int) -> bool:
    kernel = ctypes.windll.kernel32
    h = kernel.OpenProcess(0x1000, False, pid)
    if not h:
        return False
    try:
        code = ctypes.c_ulong()
        return bool(kernel.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == 259
    finally:
        kernel.CloseHandle(h)


def agents(run_dir: str | None = None) -> list[tuple[int, int, str]]:
    """Every live agent as (port, pid, secret), newest first."""
    found: list[tuple[float, int, int, str]] = []
    for path in glob.glob(os.path.join(run_dir or paths.AGENT_RUN, "agent.*.port")):
        try:
            with open(path, encoding="utf-8") as f:
                port_text, pid_text, secret = f.read().split()
            port, pid = int(port_text), int(pid_text)
        except (OSError, ValueError):
            continue
        if _alive(pid):
            found.append((os.path.getmtime(path), port, pid, secret))
    found.sort(reverse=True)
    return [(port, pid, secret) for _, port, pid, secret in found]


class AgentLink:
    """One authenticated connection. Thread-safe: one request at a time.

    A request that fails half way (the reply took longer than the timeout, the socket broke)
    ends the connection: the reply may still arrive, and the next request would read it as its
    own answer - and every one after that the answer before. So the link closes, and this and
    every later request raise AgentError: a run stops as "lost the connection" instead of
    reading one reply as the answer to another."""

    broken: str | None = None       # why the link can no longer be used (a request failed half way)

    def __init__(self, pid: int | None = None, run_dir: str | None = None, timeout: float = 10.0) -> None:
        live = agents(run_dir)
        if pid is not None:
            live = [a for a in live if a[1] == pid]
        if not live:
            raise AgentError("no_game")
        self.port, self.pid, secret = live[0]
        self.lock = threading.Lock()
        self.sock = socket.create_connection((HOST, self.port), timeout=timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.buf = b""
        if self.send("auth " + secret) != "ok":
            self.close()
            raise AgentError("refused")

    def send(self, line: str) -> str:
        return self._ask(line).decode("utf-8")

    def _ask(self, line: str) -> bytes:
        """The reply line to one request line, as bytes (json() hands them to orjson as they are)."""
        with self.lock:
            if self.broken:
                raise AgentError(self.broken)
            try:
                self.sock.sendall((line + "\n").encode("utf-8"))
                buf = self.buf
                end = buf.find(b"\n")
                while end < 0:
                    chunk = self.sock.recv(65536)
                    if not chunk:
                        raise AgentError("closed")
                    start = len(buf)
                    buf += chunk
                    end = buf.find(b"\n", start)        # only the new part can hold the line's end
            except (OSError, AgentError) as e:
                self.broken = ("timed out" if isinstance(e, TimeoutError)
                               else str(e) if isinstance(e, AgentError) else "closed: %s" % e)
                self.close()
                raise AgentError(self.broken) from None
            self.buf = buf[end + 1:]
            return buf[:end]

    def json(self, line: str) -> Any:
        """The agent's JSON answer to one request line. Any: each command answers its own shape
        (a dict, a list, {"error": ...}); the callers check what they use."""
        try:
            data = json.loads(self._ask(line))
        except ValueError:
            # An answer we cannot read came from the agent, not from us: report it as a link
            # problem, or a garbled reply would look like a bug in the bot's own code.
            raise AgentError("bad reply") from None
        if line.split(" ", 1)[0] in gamelang.COMMANDS:
            data = gamelang.english(data)      # the game's words back in English (another language pack)
        return data

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass

    def __enter__(self) -> "AgentLink":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def server_name(link: JsonLink) -> str:
    """The familiar server label for an agent's live game route, if this agent can report it."""
    try:
        data = link.json("server")
    except (AgentError, OSError, ValueError):
        return ""
    if not json.is_object(data):
        return ""
    port = data.get("port")
    return SERVER_NAMES.get(port, "") if isinstance(port, int) else ""


def games() -> list[tuple[int, str | None, str | None]]:
    """[(pid, character name or None, map name or None)] for every running game with the agent."""
    out: list[tuple[int, str | None, str | None]] = []
    for _port, pid, _secret in agents():
        name: str | None = None
        where: str | None = None
        try:
            with AgentLink(pid=pid, timeout=3) as a:
                s = a.json("mem")
                if s.get("ok"):
                    me = s["self"]
                    name = settings.character_profile(me["name"], me.get("id"), server_name(a))
                    where = s["map"]["name"]
        except (AgentError, OSError, ValueError):
            # A crashed game's port file can outlive it; later Windows PID reuse made those stale
            # records look alive and produced phantom "Not logged in" rows.
            continue
        out.append((pid, name, where))
    return out
