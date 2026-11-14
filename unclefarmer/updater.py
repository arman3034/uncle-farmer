"""Updates from the GitHub releases of Uncle Farmer, on one of two channels.

  master  stable releases: a tag "v<version>" (v0.2.0) with one asset, UncleFarmer-<version>.zip,
          published by hand (release.py). GitHub's "latest release", which never is a pre-release.
  dev     development builds of the dev branch, published by CI (ci.yml, ci_build.py publish-dev):
          a PRE-release tagged "v<version>-dev.<build>" with UncleFarmer-<version>-dev.<build>.zip.
          <version> is the last stable release's, <build> the CI run number, so 0.9.0-dev.57 is a
          build made after 0.9.0, newer than 0.9.0 and older than 0.10.0 (version_tuple orders them).

The player picks the channel in Settings (update_channel, master when never set). Each channel
reads only its own releases: master never takes a pre-release or a "-dev." version, dev only
pre-releases whose tag, version and asset name all have the dev shape. A built copy says which
build it is in build.json beside the exe (write_build); a copy without one is __version__.

Updating goes in three steps:

  1. latest() asks GitHub for the newest release of the channel; the window says what's new and asks.
  2. download() + unpack() put the new folder in update/new, next to the exe.
  3. start_apply() verifies a paused NEW UncleFarmer.exe from update/new. Only after the window
     closes and __main__ releases its locks is copying authorized. The helper also verifies that
     the old process exited, prepares a complete release on the same volume, and swaps entries
     with rollback. It reports the result and restarts the application separately.

update/ is the staging folder: only the download, the unpacked copy, the result and busy.json
(who is using it) live there, and clean() empties and removes it once nothing uses it. Every step
is written to logs/update.log with the app's other logs, so a cleanup never takes the log away.

The Nuitka release is flat: exe, DLLs, package folders, agent/, data/, lang/, docs/ and files beside
the exe. Shipped folders are replaced, preserving KEEP_IN entries; build inventories identify
obsolete runtime entries. Character profiles, plans, scripts, settings, logs, messages,
results and anything learned (data/game_texts.json, agent/run) are never in a release, so they stay.

The releases are public, so no login is needed. UNCLEFARMER_GITHUB_TOKEN (a read-only token)
still works for a private fork's releases; without one, a private repository has no update to offer.
"""

from __future__ import annotations

import ctypes
import glob
import hashlib
import http.client
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import threading
import tempfile
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import IO, Any, TypedDict, cast

from . import __version__, applog, jsonio as json, paths, update_recovery as recovery

# Where releases are published ("owner/name" on GitHub). Empty: there is no place to look, so the
# app never asks the network for one. Only ever a repository the project controls: a name nobody
# controls any more could be taken by someone else, whose "release" every copy would then offer
# and install.
REPO = "afnannasir/uncle-farmer"
LATEST = "https://api.github.com/repos/%s/releases/latest"      # % REPO, when asked
RELEASES = "https://api.github.com/repos/%s/releases?per_page=%d"   # % (REPO, DEV_PAGE)
DEV_PAGE = 30               # the newest releases looked through for dev builds (CI keeps 10)
ASSET = re.compile(r"^UncleFarmer-[\w.\-]+\.zip$", re.I)
# the dev channel's shapes; ci_build.py checks its own copy of DEV_VERSION against this one
DEV_VERSION = re.compile(r"^\d+\.\d+\.\d+-dev\.\d+$")
CHANNELS = ("master", "dev")
DEFAULT_CHANNEL = "master"
EXE = "UncleFarmer.exe"
# In the native front door (native/bootstrap.c). A copy older than the two-exe layout has its Nuitka
# app as UncleFarmer.exe instead; the first update into the new layout puts the front door there.
LAUNCHER_MARKER = b"UNCLEFARMER-NATIVE-LAUNCHER-1"
LAUNCHER_SECONDS = 60.0
BUILD_FILE = "build.json"   # beside the exe in a CI build: which build this copy is
UPDATE = os.path.join(paths.APP, "update")
NEW = os.path.join(UPDATE, "new")
RESULT = os.path.join(UPDATE, "result.json")
BUSY = "busy.json"          # in UPDATE while a download, an unpack or the copier uses it
STALE_SECONDS = 6 * 3600    # a busy.json older than this is a leftover, whoever wrote it
LOG = os.path.join(paths.LOGS, "update.log")
# Incoming runtime folders are replaced whole. These also identify legacy runtime folders
# that can be removed when absent from a release; new builds record their full shipped inventory.
REPLACE = ("_internal", "unclefarmer", "numpy", "orjson", "pydantic_core", "wx")
KEEP_IN = {"agent": ("run",), "data": ("game_texts.json",)}
# never copied, even if a release carried them: the player's own things
NEVER = {"profiles", "plans", "scripts", "logs", "messages", "results", "survey", "update", "settings.json",
         "schedules.json", ".recovery", "unclefarmer.exe"}

_lock = threading.Lock()    # the staging folder, inside this process: a claim or a cleanup at a time
_claims: int = 0            # nested claims of this process (busy.json is written for the first)
APPLY_SECONDS = 180.0       # one budget for preparation, retries and installing the whole release
SPACE_MARGIN = 16 * 1024 * 1024
# The runtime's flat Nuitka layout. build_exe uses the same list to verify its output.
REQUIRED = ("UncleFarmer.exe", recovery.PAYLOAD, "python3*.dll", "wxmsw*_core_*.dll", "wxbase*.dll", "agent/unclefarmer-agent.jar",
            "nvdaControllerClient64.dll", "unclefarmer/native/_routing-*.dll", "data/knowledge.json",
            "data/atlas.json", "data/skills.json", "lang/unclefarmer.pot", "lang/ur/LC_MESSAGES/unclefarmer.mo",
            "docs/USER_GUIDE.md", "README.html", "LICENSE", "numpy", "orjson", "pydantic_core", "wx")
RUNTIME_DIRS = ("numpy", "orjson", "pydantic_core", "wx")
VERSION = re.compile(r"\d+\.\d+\.\d+(?:-dev\.\d+)?")


class UpdateError(Exception):
    pass


class RollbackError(UpdateError):
    """The old files remain in the backup because the filesystem also refused recovery."""


class Release(TypedDict):
    """The newest release, as latest() reads it from GitHub."""
    version: str
    tag: str | None
    notes: str
    asset: str          # the zip's file name
    size: int
    url: str
    sha256: str         # "" when GitHub gives no digest


class UpdateResult(TypedDict):
    """What the update copier reports to the restarted app (update/result.json)."""
    version: str
    ok: bool
    error: str


def frozen() -> bool:
    """True in the built exe (paths.frozen); from source, updating is git's job."""
    return paths.frozen()


def version_tuple(v: str | None) -> tuple[int, ...]:
    """The numbers to compare: 1.0.1 is (1, 0, 1), a dev build 1.0.1-dev.129 is (1, 0, 1, 129).
    A dev build is made from dev AFTER its release (dev keeps the last release's version), so it
    sorts after 1.0.1 and before 1.0.2, not before 1.0.1 as a semver pre-release would."""
    return tuple(int(n) for n in re.findall(r"\d+", v or "")[:4]) or (0,)


def is_newer(v: str, than: str = __version__) -> bool:
    return version_tuple(v) > version_tuple(than)


def channel(value: object) -> str:
    """The channel a setting names; anything else (never set, a typo) is the default, master."""
    return value if isinstance(value, str) and value in CHANNELS else DEFAULT_CHANNEL


def is_dev(version: str) -> bool:
    """A development build's version (0.9.0-dev.57), as no stable release ever has."""
    return bool(DEV_VERSION.match(version or ""))


def log(text: str, level: str = "INFO") -> None:
    """One line to logs/update.log (applog.update), never an error of its own."""
    applog.update(text, level)


# ---------------------------------------------------------------------------------- this copy
def write_build(folder: str, version: str, build_channel: str, commit: str = "") -> str:
    """build.json in a built folder (ci_build.py, release.py): this copy's version and channel.
    Every build writes one, so an update always replaces the one before."""
    path = os.path.join(folder, BUILD_FILE)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"version": version, "channel": channel(build_channel), "commit": commit,
                   "files": sorted(n.replace(os.sep, "/") for n in _inventory(folder)
                                   if n.split(os.sep)[0].casefold() not in NEVER or n.casefold() == EXE.casefold())}, f)
    return path


def installed_version() -> str:
    """This copy's version: a dev build's from build.json (0.9.0-dev.57), else __version__.
    A build.json that doesn't belong to this __version__ is a leftover (a copy unpacked over
    another by hand) and counts for nothing, so it can't hide a stable release."""
    try:
        with open(os.path.join(paths.APP, BUILD_FILE), encoding="utf-8") as f:
            data = json.load(f)
        found = _obj(data)
        v = str(found.get("version") or "") if found is not None else ""
    except (OSError, ValueError):
        return __version__
    if v != __version__ and not (is_dev(v) and version_tuple(v)[:3] == version_tuple(__version__)[:3]):
        return __version__
    return v


# ---------------------------------------------------------------------------------------- GitHub
def _token() -> str:
    return os.environ.get("UNCLEFARMER_GITHUB_TOKEN", "").strip()


class _NoAuthElsewhere(urllib.request.HTTPRedirectHandler):
    """An asset download redirects to GitHub's file storage, which refuses a second login: the
    token goes to api.github.com only."""

    def redirect_request(self, req: urllib.request.Request, fp: IO[bytes], code: int, msg: str,
                         headers: http.client.HTTPMessage, newurl: str) -> urllib.request.Request | None:
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and (urllib.parse.urlparse(newurl).hostname != "api.github.com"
                                or urllib.parse.urlparse(newurl).scheme != "https"):
            new.remove_header("Authorization")
        return new


def _open(url: str, accept: str, timeout: float) -> http.client.HTTPResponse:
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "UncleFarmer/" + __version__})
    if _token() and urllib.parse.urlparse(url).hostname == "api.github.com" and urllib.parse.urlparse(url).scheme == "https":
        req.add_header("Authorization", "Bearer " + _token())
    return urllib.request.build_opener(_NoAuthElsewhere).open(req, timeout=timeout)


def _ask(url: str, timeout: float) -> Any:
    """GitHub's JSON answer; None for a 404 (nothing to see), UpdateError when it can't be had."""
    try:
        with _open(url, "application/vnd.github+json", timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise UpdateError("GitHub answered %s" % e.code)
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise UpdateError(str(getattr(e, "reason", e)))


def _release(rel: dict[str, Any], version: str, asset: dict[str, Any]) -> Release:
    digest = asset.get("digest") or ""
    return {"version": version, "tag": rel.get("tag_name"),
            "notes": (rel.get("body") or "").strip(), "asset": asset["name"], "size": asset.get("size", 0),
            # with a token the API's own asset link (a private repository has no public one)
            "url": asset["url"] if _token() else asset["browser_download_url"],
            "sha256": digest[7:].lower() if digest.startswith("sha256:") else ""}


def _obj(value: object) -> dict[str, Any] | None:
    """A JSON object from GitHub (or a file) as a dict, or None when it is something else."""
    return cast(dict[str, Any], value) if isinstance(value, dict) else None


def _assets(rel: dict[str, Any]) -> list[dict[str, Any]]:
    found = rel.get("assets")
    items = cast(list[object], found) if isinstance(found, list) else []
    return [a for a in (_obj(x) for x in items) if a is not None]


def _stable(answer: object) -> Release | None:
    """GitHub's latest release as a master release, or None when it isn't one."""
    rel = _obj(answer)
    if rel is None or rel.get("draft") or rel.get("prerelease"):
        return None
    tag = str(rel.get("tag_name") or "")
    version = tag[1:] if tag[:1] in ("v", "V") else ""
    if VERSION.fullmatch(version) is None or is_dev(version):
        return None
    asset = next((a for a in _assets(rel) if a.get("name") == "UncleFarmer-%s.zip" % version
                  and a.get("state") == "uploaded"), None)
    return None if asset is None else _release(rel, version, asset)


def _dev(answer: object) -> Release | None:
    """One release from the list as a dev build, or None: a pre-release, not a draft, tagged
    v<dev version>, carrying exactly UncleFarmer-<dev version>.zip."""
    rel = _obj(answer)
    if rel is None or rel.get("draft") or not rel.get("prerelease"):
        return None
    tag = str(rel.get("tag_name") or "")
    version = tag[1:] if tag[:1] in ("v", "V") else ""
    if not is_dev(version):
        return None
    want = "UncleFarmer-%s.zip" % version
    # an asset still being uploaded (CI publishing right now) is not one yet
    asset = next((a for a in _assets(rel) if a.get("name") == want
                  and a.get("state") == "uploaded"), None)
    return None if asset is None else _release(rel, version, asset)


def latest(timeout: float=10, update_channel: str = DEFAULT_CHANNEL) -> Release | None:
    """The newest release of the channel: {"version", "tag", "notes", "asset", "size", "url",
    "sha256"}, or None when there is none to see (no release yet, or a private repository).
    UpdateError when GitHub can't be reached. None, without asking anyone, while no repository is set."""
    if not REPO:
        return None
    if channel(update_channel) == "dev":
        answer = _ask(RELEASES % (REPO, DEV_PAGE), timeout)
        if answer is None:
            return None
        if not isinstance(answer, list):
            raise UpdateError("GitHub's list of releases isn't a list")
        builds = [b for b in (_dev(r) for r in cast(list[object], answer)) if b is not None]
        return max(builds, key=lambda b: version_tuple(b["version"]), default=None)
    return _stable(_ask(LATEST % REPO, timeout))


def check(timeout: float=10, update_channel: str = DEFAULT_CHANNEL) -> Release | None:
    """The channel's newest release if it is newer than this copy, else None (errors too: None)."""
    ch = channel(update_channel)
    try:
        rel = latest(timeout, ch)
    except UpdateError as e:
        log("update check (%s) failed: %s" % (ch, e), "WARNING")
        return None
    mine = installed_version()
    if rel is None:
        log("update check (%s): no release to see; this copy is %s" % (ch, mine))
        return None
    newer = is_newer(rel["version"], mine)
    log("update check (%s): newest %s, this copy %s: %s" % (ch, rel["version"], mine,
                                                             "newer, offered" if newer else "nothing newer"))
    return rel if newer else None


# ---------------------------------------------------------------------------------- staging
def _junction(path: str) -> bool:
    try:
        return os.path.isjunction(path)
    except (AttributeError, OSError):
        return False


def _link(path: str) -> bool:
    return os.path.islink(path) or _junction(path)


def _same(a: str, b: str) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def _inside(path: str, folder: str) -> bool:
    """path is folder itself or below it, after every link is resolved."""
    p, f = os.path.normcase(os.path.realpath(path)), os.path.normcase(os.path.realpath(folder))
    try:
        return os.path.commonpath([p, f]) == f
    except ValueError:                   # another drive
        return False


def _checked_staging(staging: str, app: str) -> str | None:
    """staging when it is exactly <app>/update, a real folder (no link or junction that could lead
    elsewhere); else None, and nothing in it may be deleted. Nothing but that one folder ever
    qualifies, so the app folder, settings, profiles and logs can never be taken for it."""
    if os.path.normcase(os.path.basename(os.path.normpath(staging))) != "update":
        return None
    if _link(staging) or not _same(os.path.dirname(os.path.abspath(staging)), app):
        return None
    if not _inside(staging, app) or _same(staging, app):
        return None
    return staging


def _staging(staging: str | None = None, app: str | None = None) -> str:
    staging, app = staging or UPDATE, app or paths.APP
    if _checked_staging(staging, app) is None:
        raise UpdateError("%s is not the app's own update folder" % staging)
    return staging


def _safe_entry(path: str, root: str) -> None:
    """Reject links in any existing component before reading/writing an update-owned entry."""
    if not _inside(path, root):
        raise UpdateError("unsafe update path: %s" % path)
    current = os.path.abspath(path)
    while True:
        if _link(current):
            raise UpdateError("linked update path: %s" % current)
        if _same(current, root):
            return
        parent = os.path.dirname(current)
        if parent == current:
            raise UpdateError("unsafe update path: %s" % path)
        current = parent


def _alive(pid: int) -> bool:
    """A process with this id is running (this one always is)."""
    if pid == os.getpid():
        return True
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
    kernel = _kernel32()
    h = kernel.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        code = kernel.GetLastError()
        if code != 87:  # ERROR_INVALID_PARAMETER: this PID does not exist
            log("cannot inspect process %d: Windows error %d; treating it as active" % (pid, code), "WARNING")
        return code != 87
    try:
        code = ctypes.c_ulong()
        return not kernel.GetExitCodeProcess(h, ctypes.byref(code)) or code.value == 259
    finally:
        kernel.CloseHandle(h)


def busy(staging: str | None = None) -> dict[str, Any] | None:
    """Who uses the staging folder: busy.json's {"pid", "what", "since"} while that process still
    runs; None when nobody does (no file, a broken one, a process that is gone, or older than
    STALE_SECONDS)."""
    path = os.path.join(staging or UPDATE, BUSY)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        pid, since = int(data["pid"]), float(data["since"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if time.time() - since > STALE_SECONDS or not _alive(pid):
        return None
    return {"pid": pid, "what": str(data.get("what") or "update"), "since": since}


def _mark_busy(staging: str, what: str) -> None:
    _staging(staging, os.path.dirname(staging))
    _safe_entry(os.path.join(staging, BUSY), staging)
    os.makedirs(staging, exist_ok=True)
    json.save(os.path.join(staging, BUSY), {"pid": os.getpid(), "what": what, "since": time.time()})


@contextmanager
def claimed(what: str) -> Generator[None]:
    """Hold the staging folder for a download or an unpack: busy.json says so, cleanup leaves it
    alone, and another copy of the app can't start its own update into it. Nested claims of this
    process are one claim. UpdateError when another running process holds it."""
    global _claims
    _staging()
    with _lock:
        if _claims == 0:
            holder = busy(UPDATE)
            if holder and holder["pid"] != os.getpid():
                raise UpdateError("another update is under way (%s, process %d)" % (holder["what"], holder["pid"]))
            _mark_busy(UPDATE, what)
        _claims += 1
    try:
        yield
    finally:
        with _lock:
            _claims -= 1
            if _claims == 0:
                try:
                    _staging()
                    holder = busy(UPDATE)
                    if holder is None or holder["pid"] == os.getpid():
                        os.remove(os.path.join(UPDATE, BUSY))
                except (OSError, UpdateError) as error:
                    if not isinstance(error, FileNotFoundError):
                        log("could not release staging claim: %s" % error, "WARNING")


def _remove(path: str, staging: str, left: list[str]) -> None:
    """Delete one entry of the staging folder. A link or junction goes itself, never what it points
    at; anything that resolves outside the folder is left alone; read-only files are made writable
    once; what can't go (in use, no permission) is added to left."""
    if _link(path):
        try:
            if os.path.isdir(path) and _junction(path):
                os.rmdir(path)
            else:
                os.unlink(path)
        except OSError as e:
            left.append("%s (%s)" % (path, e))
        return
    if not _inside(path, staging) or _same(path, staging):
        left.append("%s (outside the staging folder: left alone)" % path)
        return

    def retry(func: Callable[..., object], p: str, exc: BaseException) -> None:
        if isinstance(exc, PermissionError):
            try:
                os.chmod(p, stat.S_IWRITE)
                func(p)
                return
            except OSError as again:
                exc = again
        if not isinstance(exc, FileNotFoundError):
            left.append("%s (%s)" % (p, exc))

    if os.path.isdir(path):
        shutil.rmtree(path, onexc=retry)
    else:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except OSError as e:
            retry(os.remove, path, e)


def _move_old_log(staging: str, app: str) -> None:
    """Older versions wrote update/update.log: it joins logs/update.log before the folder goes."""
    old = os.path.join(staging, "update.log")
    if not os.path.isfile(old) or _link(old):
        return
    try:
        with open(old, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return
    if applog.update("---- the update log of an older version, from the staging folder ----\n" + text.rstrip("\n"),
                     logs=os.path.join(app, "logs")) is None:
        try:
            os.remove(old)
        except OSError:
            pass


def _purge(staging: str, app: str, keep: tuple[str, ...]) -> list[str]:
    """Empty the (checked) staging folder but for keep, and remove it when nothing is left.
    Returns what couldn't go."""
    left: list[str] = []
    _staging(staging, app)
    if not os.path.isdir(staging):
        return left
    _move_old_log(staging, app)
    for name in os.listdir(staging):
        _staging(staging, app)
        if name in keep:
            continue
        _remove(os.path.join(staging, name), staging, left)
    try:
        if not os.listdir(staging):
            os.rmdir(staging)
    except OSError:
        pass
    return left


def clean(wait: float = 0.0) -> bool:
    """Empty the staging folder (update/) and remove it: old downloads, a half download, the
    unpacked copy, the old update.log (moved to logs/ first). Never while a running process holds
    it (busy): wait up to that many seconds for it to finish (the update copier is closing just
    as the updated app starts), else leave it for the next start. Only <app>/update itself is
    ever emptied. True when it is empty (but for a result still to be read); what couldn't go is
    in logs/update.log."""
    staging, app = UPDATE, paths.APP
    try:
        transaction = recovery.load(app)
        if transaction and transaction["state"] not in recovery.TERMINAL:
            log("staging cleanup deferred: persistent update recovery is pending", "WARNING")
            return False
    except recovery.RecoveryError as error:
        log("staging cleanup refused: %s" % error, "ERROR")
        return False
    if not os.path.exists(staging):
        return True
    if _checked_staging(staging, app) is None:
        log("staging cleanup refused: %s is not the app's own update folder" % staging, "WARNING")
        return False
    holder = busy(staging)
    if holder and wait > 0 and holder["pid"] != os.getpid():
        try:
            _wait_for_exit(holder["pid"], wait)
        except UpdateError:
            return False
    with _lock:
        if _checked_staging(staging, app) is None:
            log("staging cleanup refused: the folder changed while waiting", "WARNING")
            return False
        holder = busy(staging)
        if holder or _claims:
            who = holder or {"what": "update", "pid": os.getpid()}
            log("staging cleanup put off: the %s of process %d still uses it" % (who["what"], who["pid"]))
            return False
        left = _purge(staging, app, (os.path.basename(RESULT),))
    if left:
        log("staging cleanup left %d item(s), tried again at the next start: %s" % (len(left), "; ".join(left[:5])),
            "WARNING")
        return False
    log("staging folder cleaned")
    return True


# ---------------------------------------------------------------------------------------- download
def ensure_recovery_runtime(app: str, source: str) -> None:
    """Publish once, before any journal or install mutation; never update this rescue copy in place."""
    with recovery.locked(app):
        _ensure_recovery_runtime_locked(app, source)


def _ensure_recovery_runtime_locked(app: str, source: str) -> None:
    recovery.ntfs(app)
    root = os.path.join(app, recovery.HERE)
    recovery.safe(root, app)
    os.makedirs(root, exist_ok=True)
    runtime = os.path.join(root, "runtime")
    manifest = os.path.join(root, "runtime-manifest.json")
    recovery.safe(runtime, app)
    recovery.safe(manifest, app)
    def arm() -> None:
        armed = os.path.join(root, "armed")
        recovery.safe(armed, app)
        recovery.atomic(armed, {"protocol": 1}, envelope=False)
    if os.path.isdir(runtime):
        with open(manifest, encoding="utf-8") as stream:
            expected = json.load(stream)
        if recovery.fingerprint(runtime) != expected:
            raise UpdateError("the independent recovery runtime failed verification")
        arm()
        return
    for name in os.listdir(root):
        if name.startswith("runtime-preparing-"):
            abandoned = os.path.join(root, name)
            recovery.safe(abandoned, app)
            recovery.fingerprint(abandoned)
            shutil.rmtree(abandoned)
    files = _verify_release(source)
    needed = sum(size for name, size in files.items() if name.split(os.sep)[0].casefold() not in NEVER
                 or name.casefold() == EXE.casefold()) + SPACE_MARGIN
    if shutil.disk_usage(root).free < needed:
        raise UpdateError("not enough free space for the independent recovery runtime")
    deadline = time.monotonic() + APPLY_SECONDS
    temporary = tempfile.mkdtemp(prefix="runtime-preparing-", dir=root)
    # A killed preparation leaves only private artifacts. No installed entry was touched.
    for name in os.listdir(source):
        if name.casefold() not in NEVER or name.casefold() == EXE.casefold():
            _copy_entry(os.path.join(source, name), os.path.join(temporary, name), log, deadline)
    _verify_release(temporary)
    recovery.durable_tree(temporary)
    json.save(manifest, recovery.fingerprint(temporary))
    recovery.flush(manifest)
    recovery.rename(temporary, runtime)
    arm()


@contextmanager
def _early_transaction(phase: str, version: str = "") -> Generator[None]:
    if not frozen():
        yield
        return
    ensure_recovery_runtime(paths.APP, paths.APP)
    with recovery.locked(paths.APP):
        current = recovery.load(paths.APP)
        target = version or (str(current["target"]) if current else "?")
        record = recovery.begin(paths.APP, installed_version(), target, phase)
    try:
        yield
    except Exception:
        with recovery.locked(paths.APP):
            recovery.save(paths.APP, record, "ROLLED_BACK", "early-operation-failed")
        raise


def download(rel: Release, progress: Callable[[int, int], object] | None = None) -> str:
    """Download the release's zip into update/; progress(done, total) -> False cancels. Returns
    the zip's path. Checks the size and, when GitHub gives one, the SHA-256. Older downloads in
    the staging folder go first; a failed or cancelled one leaves no partial file behind."""
    _staging()
    if os.path.basename(rel["asset"]) != rel["asset"] or any(c in rel["asset"] for c in "\\/:"):
        raise UpdateError("invalid release asset name")
    with claimed("download"), _early_transaction("DOWNLOADING", rel["version"]):
        if _checked_staging(UPDATE, paths.APP) is not None:
            with _lock:
                left = _purge(UPDATE, paths.APP, (BUSY, os.path.basename(RESULT)))
            if left:
                log("older staging files still in use, left: %s" % "; ".join(left[:3]), "WARNING")
        os.makedirs(UPDATE, exist_ok=True)
        path = os.path.join(UPDATE, rel["asset"])
        _safe_entry(path, UPDATE)
        _safe_entry(path + ".part", UPDATE)
        log("download of %s (%s) started" % (rel["asset"], rel["version"]))
        try:
            got = _fetch(rel, path, progress)
        except Exception as e:
            try:
                _staging()
                _safe_entry(path + ".part", UPDATE)
                os.remove(path + ".part")
            except (OSError, UpdateError) as cleanup_error:
                if not isinstance(cleanup_error, FileNotFoundError):
                    log("partial download cleanup failed: %s" % cleanup_error, "WARNING")
            log("download of %s %s" % (rel["asset"], "cancelled" if str(e) == "cancelled" else "FAILED: %s" % e),
                "INFO" if str(e) == "cancelled" else "WARNING")
            raise
        log("download of %s done: %d bytes, %s" % (rel["asset"], got,
                                                   "checksum ok" if rel.get("sha256") else "no checksum given"))
        return path


def _fetch(rel: Release, path: str, progress: Callable[[int, int], object] | None) -> int:
    sha, done, total = hashlib.sha256(), 0, int(rel.get("size") or 0)
    try:
        with _open(rel["url"], "application/octet-stream", 60) as r, open(path + ".part", "wb") as f:
            try:
                total = int(r.headers.get("Content-Length") or total)
                if total < 0:
                    raise ValueError("negative length")
            except (ValueError, TypeError) as e:
                raise UpdateError("invalid Content-Length header") from e
            while True:
                _staging()
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                recovery.checkpoint("download-chunk")
                sha.update(chunk)
                done += len(chunk)
                if progress and progress(done, total) is False:
                    raise UpdateError("cancelled")
    except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
        raise UpdateError("the download failed: %s" % getattr(e, "reason", e))
    if total and done != total:
        raise UpdateError("the download stopped at %d of %d bytes" % (done, total))
    if rel.get("sha256") and sha.hexdigest() != rel["sha256"]:
        raise UpdateError("the downloaded file is damaged (its checksum is wrong)")
    _staging()
    _safe_entry(path, UPDATE)
    _safe_entry(path + ".part", UPDATE)
    os.replace(path + ".part", path)
    return done


def unpack(zip_path: str) -> str:
    """Unpack the release into update/new and return the folder holding the new exe."""
    _staging()
    _safe_entry(NEW, UPDATE)
    with claimed("unpack"), _early_transaction("EXTRACTING"):
        if os.path.exists(NEW):
            left: list[str] = []
            if _checked_staging(UPDATE, paths.APP) is None:
                raise UpdateError("%s is not the app's own update folder" % UPDATE)
            _remove(NEW, UPDATE, left)
            if left or os.path.exists(NEW):
                raise UpdateError("the last unpacked update is still in use: %s" % "; ".join(left[:2]))
        os.makedirs(NEW)
        root = os.path.realpath(NEW)
        try:
            try:
                with zipfile.ZipFile(zip_path) as z:
                    seen: set[str] = set()
                    for entry in z.infolist():
                        name = entry.filename
                        if ("\\" in name or ":" in name or name.startswith("/") or
                                stat.S_ISLNK(entry.external_attr >> 16) or any(
                                    p in (".", "..") or p.endswith((".", " ")) for p in name.rstrip("/").split("/"))):
                            raise UpdateError("unsafe update archive entry: %s" % name)
                        key = name.rstrip("/").casefold()
                        if key in seen:
                            raise UpdateError("duplicate update archive entry: %s" % name)
                        seen.add(key)
                        target = os.path.realpath(os.path.join(NEW, name))
                        if target != root and not target.startswith(root + os.sep):
                            raise UpdateError("the update holds a file outside its folder: %s" % name)
                        _staging()
                        _safe_entry(target, NEW)
                        if entry.is_dir():
                            os.makedirs(target, exist_ok=True)
                        else:
                            os.makedirs(os.path.dirname(target), exist_ok=True)
                            _safe_entry(target, NEW)
                            with z.open(entry) as source, open(target, "wb") as output:
                                shutil.copyfileobj(source, output)
                            recovery.checkpoint("extraction-file")
                            if os.path.getsize(target) != entry.file_size:
                                raise UpdateError("incomplete extracted file: %s" % name)
            except zipfile.BadZipFile:
                raise UpdateError("the downloaded file is not a zip")
            for folder, _dirs, files in os.walk(NEW):
                if EXE in files:
                    log("unpacked %s" % os.path.basename(zip_path))
                    return folder
            raise UpdateError("the update has no %s" % EXE)
        except UpdateError as e:
            log("unpacking %s FAILED: %s" % (os.path.basename(zip_path), e), "WARNING")
            raise


@dataclass
class ApplyProcess:
    process: subprocess.Popen[bytes]
    staging: str
    app: str
    token: str
    version: str

    def cancel(self) -> None:
        """No authorization was issued: this child may be stopped without interrupting copying."""
        try:
            if self.process.poll() is None:
                self.process.terminate()
        except OSError:
            log("could not terminate the paused copier; it has no copy authorization\n" + traceback.format_exc(), "ERROR")
        log("the paused update copier was cancelled")

    def activate(self) -> None:
        if self.process.poll() is not None:
            raise OSError("the paused update copier exited before shutdown completed")
        _staging(self.staging, self.app)
        target = os.path.join(self.staging, "apply.json")
        _safe_entry(target, self.staging)
        json.save(target, {"token": self.token})


_pending_apply: ApplyProcess | None = None


def start_apply(new_folder: str, version: str) -> ApplyProcess:
    """Start a paused copier and verify its PID/token readiness before allowing app shutdown."""
    if not frozen():
        raise UpdateError("updates cannot run from source")
    _staging()
    _safe_entry(new_folder, NEW)
    _verify_release(new_folder, version)
    token = secrets.token_hex(16)
    # The running installation is known to boot. A staged copier may fail its
    # handshake, so it must not become the first/only rescue runtime here.
    ensure_recovery_runtime(paths.APP, paths.APP)
    args = [os.path.join(new_folder, recovery.PAYLOAD), "--apply-update", paths.APP, str(os.getpid()), version, token]
    process = subprocess.Popen(args, cwd=new_folder, close_fds=True,
                               creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) |
                               getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    handle = ApplyProcess(process, UPDATE, paths.APP, token, version)
    deadline = time.monotonic() + 5
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise OSError("the update copier exited before reporting readiness")
            with _lock:
                _staging()
                try:
                    with open(os.path.join(UPDATE, BUSY), encoding="utf-8") as f:
                        signal = _obj(json.load(f))
                except (OSError, ValueError):
                    signal = None
            if signal and signal.get("pid") == process.pid and signal.get("token") == token:
                log("the update copier for %s started and is paused for app shutdown" % version)
                return handle
            time.sleep(0.05)
        raise OSError("the update copier did not report readiness within five seconds")
    except Exception:
        handle.cancel()
        raise


def schedule_apply(handle: ApplyProcess) -> None:
    """The window closed; activation waits until __main__ releases data/instance locks."""
    global _pending_apply
    _pending_apply = handle


def finish_apply() -> None:
    global _pending_apply
    handle, _pending_apply = _pending_apply, None
    if handle is None:
        return
    try:
        handle.activate()
    except Exception as error:
        log("cannot activate the update copier: %s\n%s" % (error, traceback.format_exc()), "ERROR")
        handle.cancel()
        _finish_copier(handle.app, None, {"version": handle.version, "ok": False, "error": str(error)})


# ---------------------------------------------------------------------------------------- applying
def _kernel32() -> Any:
    kernel = ctypes.windll.kernel32
    # Win32 HANDLEs are pointer-sized; ctypes' default c_int truncates them on 64-bit Windows.
    for name in ("OpenProcess", "CloseHandle", "WaitForSingleObject", "GetExitCodeProcess"):
        method = getattr(kernel, name, None)
        if method is not None and hasattr(method, "restype"):
            if name == "OpenProcess":
                method.restype = ctypes.c_void_p
                method.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
            else:
                method.argtypes = [ctypes.c_void_p, ctypes.c_void_p] if name == "GetExitCodeProcess" else (
                    [ctypes.c_void_p, ctypes.c_ulong] if name == "WaitForSingleObject" else [ctypes.c_void_p])
    return kernel


def _wait_for_exit(pid: int, seconds: float=120) -> None:
    if pid <= 0:
        raise UpdateError("invalid old application process")
    kernel = _kernel32()
    h = kernel.OpenProcess(0x00100000, False, pid)          # SYNCHRONIZE
    if h:
        try:
            status = kernel.WaitForSingleObject(h, int(seconds * 1000))
            if status != 0:
                raise UpdateError("the old app is still running" if status == 258 else "cannot check the old app process")
        finally:
            kernel.CloseHandle(h)
    if _alive(pid):
        raise UpdateError("the old app is still running")


def _copy(src: str, dst: str, log: Callable[[str], None], tries: int = 30, *, deadline: float | None = None) -> None:
    """Copy one file, waiting a while for one still in use (an antivirus scan, a closing game)."""
    for i in range(tries):
        _before_deadline(deadline)
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            _before_deadline(deadline)
            return
        except PermissionError:
            if i == tries - 1:
                raise
            log("in use, waiting: %s" % dst)
            time.sleep(min(2, max(0, deadline - time.monotonic())) if deadline is not None else 2)


def _before_deadline(deadline: float | None) -> None:
    if deadline is not None and time.monotonic() >= deadline:
        raise UpdateError("the update operation timed out (overall deadline)")


def _inventory(folder: str, deadline: float | None = None) -> dict[str, int]:
    result: dict[str, int] = {}
    for parent, dirs, files in os.walk(folder):
        _before_deadline(deadline)
        names: set[str] = set()
        for name in dirs + files:
            if name.casefold() in names:
                raise UpdateError("duplicate update entry: %s" % name)
            names.add(name.casefold())
            _safe_entry(os.path.join(parent, name), folder)
        for name in files:
            path = os.path.join(parent, name)
            result[os.path.relpath(path, folder)] = os.path.getsize(path)
    return result


def _verify_release(src: str, version: str | None = None, deadline: float | None = None) -> dict[str, int]:
    if not os.path.isdir(src) or _link(src):
        raise UpdateError("the staged release is not a safe directory")
    files = _inventory(src, deadline)
    missing = missing_runtime(src)
    if missing:
        raise UpdateError("the update is missing or has an invalid required entry: %s" % ", ".join(missing))
    try:
        with open(os.path.join(src, BUILD_FILE), encoding="utf-8") as f:
            info = _obj(json.load(f))
        found = info.get("version") if info else None
        if not isinstance(found, str) or VERSION.fullmatch(found) is None or version is not None and found != version:
            raise ValueError("release version mismatch")
    except (OSError, ValueError) as e:
        raise UpdateError("invalid update build.json: %s" % e) from e
    return files


def missing_runtime(folder: str) -> list[str]:
    """One shared file/type/size contract for the release builder and updater."""
    missing: list[str] = []
    for pattern in REQUIRED:
        matches = glob.glob(os.path.join(folder, *pattern.split("/")))
        if not matches or not all(os.path.isdir(p) if pattern in RUNTIME_DIRS else
                                  os.path.isfile(p) and os.path.getsize(p) > 0 for p in matches):
            missing.append(pattern)
    return missing


def _copy_entry(src: str, dst: str, report: Callable[[str], None], deadline: float) -> None:
    _before_deadline(deadline)
    if os.path.isdir(src):
        os.makedirs(dst, exist_ok=True)
        for name in sorted(os.listdir(src)):
            _copy_entry(os.path.join(src, name), os.path.join(dst, name), report, deadline)
    else:
        _copy(src, dst, report, deadline=deadline)
        recovery.checkpoint("staging-file")
        _before_deadline(deadline)
        if os.path.getsize(src) != os.path.getsize(dst):
            raise UpdateError("incomplete prepared update file: %s" % src)


def _shipped_files(app: str) -> set[str]:
    """Read either an older top-level inventory or the current relative-file inventory."""
    names: set[str] = set()
    try:
        with open(os.path.join(app, BUILD_FILE), encoding="utf-8") as f:
            info = _obj(json.load(f))
        entries: object = info.get("files") if info else None
        if isinstance(entries, list):
            for entry in cast(list[object], entries):
                if isinstance(entry, str):
                    parts = entry.replace("\\", "/").split("/")
                    if all(p not in ("", ".", "..") and ":" not in p for p in parts):
                        names.add("/".join(parts).casefold())
    except (OSError, ValueError):
        pass  # older releases did not carry an inventory
    return names


def _old_managed(app: str) -> set[str]:
    """Only a build's own inventory and recognizable runtime files may become obsolete."""
    names = {n.casefold() for n in os.listdir(app) if n.casefold() in REPLACE or n.casefold().endswith((".dll", ".pyd"))}
    names.update(n.split("/")[0] for n in _shipped_files(app))
    return names - NEVER


def _keep_learned_data(app: str, target: str, report: Callable[[str], None], deadline: float) -> None:
    old = os.path.join(app, "data")
    if not os.path.isdir(old):
        return
    shipped = _shipped_files(app)
    for relative in _inventory(old, deadline):
        # Unshipped files were retained by the old data merge. Keep that behavior;
        # remove only obsolete data that an actual previous release inventory identifies.
        key = "data/" + relative.replace(os.sep, "/").casefold()
        if key not in shipped:
            _copy_entry(os.path.join(old, relative), os.path.join(target, relative), report, deadline)


def _prepare_tree(app: str, src: str, prepared: str, report: Callable[[str], None], deadline: float) -> None:
    for name in sorted(os.listdir(src)):
        key = name.casefold()
        if key == EXE.casefold():
            _copy_entry(os.path.join(app, EXE), os.path.join(prepared, EXE), report, deadline)
            continue
        if key in NEVER:
            continue
        source, target = os.path.join(src, name), os.path.join(prepared, name)
        keep = KEEP_IN.get(key, ())
        if not keep or not os.path.isdir(source):
            _copy_entry(source, target, report, deadline)
            continue
        os.makedirs(target)
        if key == "data":
            _keep_learned_data(app, target, report, deadline)
        for child in os.listdir(source):
            if child.casefold() not in keep:
                _copy_entry(os.path.join(source, child), os.path.join(target, child), report, deadline)
        old = next((n for n in os.listdir(app) if n.casefold() == key), name)
        old_folder = os.path.join(app, old)
        if os.path.isdir(old_folder):
            for child in os.listdir(old_folder):
                if child.casefold() in keep:
                    entry = os.path.join(old_folder, child)
                    _safe_entry(entry, app)
                    _inventory(entry, deadline) if os.path.isdir(entry) else None
                    _copy_entry(entry, os.path.join(target, child), report, deadline)


def _rename_entry(source: str, target: str, report: Callable[[str], None], deadline: float, *, rollback: bool = False) -> None:
    while True:
        if not rollback:
            _before_deadline(deadline)
        try:
            recovery.move(source, target)
            return
        except PermissionError:
            _before_deadline(deadline)
            report("in use, waiting: %s" % target)
            time.sleep(min(0.2, max(0, deadline - time.monotonic())))


def _install_tree(app: str, src: str, prepared: str, backup: str, report: Callable[[str], None], deadline: float,
                  transaction: dict[str, Any]) -> None:
    incoming = {name.casefold(): name for name in os.listdir(prepared)}
    existing = {name.casefold(): name for name in os.listdir(app)}
    keys = (set(incoming) | _old_managed(app)) - NEVER
    ordered = sorted(keys - {recovery.PAYLOAD.casefold(), BUILD_FILE}) + [recovery.PAYLOAD.casefold(), BUILD_FILE]
    names = [existing.get(k) or incoming[k] for k in ordered if k in existing or k in incoming]
    # Retain installed casing in both the prepared tree and durable plan.
    for key, new_name in incoming.items():
        if key in existing and existing[key] != new_name:
            os.rename(os.path.join(prepared, new_name), os.path.join(prepared, existing[key]))
            incoming[key] = existing[key]
    recovery.plan(app, transaction, names)
    try:
        for key in ordered:
            _before_deadline(deadline)
            old_name, new_name = existing.get(key), incoming.get(key)
            if old_name is None and new_name is None:
                continue
            # Retain the installed spelling on Windows, including protected folder casing.
            name = old_name or new_name
            assert name is not None
            destination = os.path.join(app, name)
            if _same(destination, app):
                raise UpdateError("invalid managed application entry")
            _safe_entry(destination, app)
            saved: str | None = None
            if old_name is not None:
                saved = os.path.join(backup, old_name)
                recovery.save(app, transaction, "BACKING_UP", "backup-intent:" + name)
                _copy_entry(destination, saved, report, deadline)
                recovery.checkpoint("backup-copied:" + name)
                entry = next(e for e in transaction["entries"] if e["name"] == name)
                if recovery.fingerprint(saved) != entry["old"]:
                    raise UpdateError("backup verification failed: " + name)
                recovery.durable_tree(saved)
                transaction["backed_up"].append(name)
                recovery.save(app, transaction, "BACKING_UP", "backup-verified:" + name)
                retired = os.path.join(os.path.dirname(backup), "retired")
                os.makedirs(retired, exist_ok=True)
                recovery.save(app, transaction, "APPLYING", "retire-intent:" + name)
                _rename_entry(destination, os.path.join(retired, name), report, deadline)
                recovery.checkpoint("original-retired:" + name)
            if new_name is not None:
                recovery.save(app, transaction, "APPLYING", "replace-intent:" + name)
                _rename_entry(os.path.join(prepared, new_name), destination, report, deadline)
                recovery.checkpoint("replacement-moved:" + name)
            transaction["replaced"].append(name)
            transaction["waiting"].remove(name)
            recovery.save(app, transaction, "APPLYING", "replacement-recorded:" + name)
            report(("updated " if key in KEEP_IN or not os.path.isdir(destination) else "replaced ") + name)
            _before_deadline(deadline)
        recovery.save(app, transaction, "VERIFYING", "verify-installed")
        _verify_release(app, transaction["target"], deadline)
        if not recovery.complete(app, transaction):
            raise UpdateError("the installed files do not match the complete staged release")
        recovery.durable_tree_for_entries(app, transaction)
        recovery.save(app, transaction, "COMMITTING", "installation-verified")
        recovery.save(app, transaction, "COMMITTED", "committed")
    except Exception as failure:
        recovery_deadline = time.monotonic() + APPLY_SECONDS
        try:
            recovery.rollback(app, transaction, lambda a, b: _rename_entry(a, b, report, recovery_deadline, rollback=True))
        except Exception as error:
            try:
                recovery.save(app, transaction, "RECOVERY_REQUIRED", "rollback-incomplete")
            except Exception:
                report("could not record rollback failure: " + traceback.format_exc())
            raise RollbackError("%s; rollback incomplete; backup retained at %s: %s" % (
                failure, backup, error)) from failure
        raise


def apply(app: str, src: str, log: Callable[[str], None], *, deadline: float | None = None) -> None:
    if not os.path.isdir(app) or not os.path.isfile(os.path.join(app, EXE)) or _link(app) or _same(app, src):
        raise UpdateError("invalid destination application directory")
    try:
        with recovery.locked(app):
            _apply_locked(os.path.abspath(app), src, log, deadline=deadline)
            durable = recovery.load(os.path.abspath(app))
            if durable and durable["state"] == "COMMITTED":
                # only after the commit: a rolled-back copy has no UncleFarmerApp.exe for a front door to start
                _migrate_launcher(os.path.abspath(app), src, log)
    except recovery.RecoveryError as error:
        raise UpdateError(str(error)) from error


def _apply_locked(app: str, src: str, log: Callable[[str], None], *, deadline: float | None = None) -> None:
    """Prepare on the same volume, swap entries, and roll every swap back on failure."""
    deadline = deadline if deadline is not None else time.monotonic() + APPLY_SECONDS
    if not os.path.isdir(app) or not os.path.isfile(os.path.join(app, EXE)) or _link(app) or _same(app, src):
        raise UpdateError("invalid destination application directory")
    files = _verify_release(src, deadline=deadline)
    needed = sum(files.values()) + SPACE_MARGIN
    backup_sizes: list[int] = []
    managed = _old_managed(app) | {n.casefold() for n in os.listdir(src)}
    for name in os.listdir(app):
        if name.casefold() in managed - NEVER:
            path = os.path.join(app, name)
            _safe_entry(path, app)
            backup_sizes.append(sum(_inventory(path, deadline).values()) if os.path.isdir(path) else os.path.getsize(path))
    needed += sum(backup_sizes) + max(backup_sizes, default=0)  # verified backups and one recovery copy
    for folder, names in KEEP_IN.items():
        if folder == "data" and os.path.isdir(os.path.join(app, folder)):
            needed += sum(_inventory(os.path.join(app, folder), deadline).values())
            continue
        for name in names:
            preserved = os.path.join(app, folder, name)
            if os.path.isdir(preserved):
                needed += sum(_inventory(preserved, deadline).values())
            elif os.path.isfile(preserved):
                needed += os.path.getsize(preserved)
    if shutil.disk_usage(os.path.dirname(os.path.abspath(app))).free < needed:
        raise UpdateError("not enough free space to prepare the update safely")
    with open(os.path.join(src, BUILD_FILE), encoding="utf-8") as f:
        target = _obj(json.load(f))
    assert target is not None
    try:
        with open(os.path.join(app, BUILD_FILE), encoding="utf-8") as f:
            previous = _obj(json.load(f))
    except (OSError, ValueError):
        previous = None
    transaction = recovery.begin(app, str(previous.get("version", "?")) if previous else "?", str(target["version"]))
    work = os.path.dirname(transaction["backup"])
    prepared, backup = os.path.join(work, "new"), os.path.join(work, "old")
    try:
        os.makedirs(prepared)
        os.mkdir(backup)
        _prepare_tree(app, src, prepared, log, deadline)
        _verify_release(prepared, deadline=deadline)
        _install_tree(app, src, prepared, backup, log, deadline, transaction)
    except Exception:
        if not transaction["entries"] or all(recovery.fingerprint(os.path.join(app, e["name"])) == e["old"]
                                              for e in transaction["entries"]):
            recovery.save(app, transaction, "ROLLED_BACK", "preparation-failed")
        raise
    finally:
        durable = recovery.load(app)
        if durable and durable["state"] in recovery.TERMINAL:
            try:
                recovery.cleanup(app, durable)
            except OSError as error:
                log("temporary update files retained at %s: %s" % (work, error))


def is_launcher(path: str) -> bool:
    """Whether this exe is the native front door (not an older copy's Nuitka app)."""
    try:
        with open(path, "rb") as f:
            return LAUNCHER_MARKER in f.read()
    except OSError:
        return False


def _migrate_launcher(app: str, src: str, log: Callable[[str], None]) -> None:
    """Put the release's front door in place of an older copy's Nuitka UncleFarmer.exe, once.

    The transactional install never touches UncleFarmer.exe (it is protected, so a running front door
    is never replaced). A copy from before the two-exe layout would keep its old app there and start
    it again: the old code, with the shortcut and the restart both pointing at it."""
    installed, shipped = os.path.join(app, EXE), os.path.join(src, EXE)
    if is_launcher(installed) or not is_launcher(shipped):
        return
    _safe_entry(installed, app)
    staged = os.path.join(app, recovery.HERE, "launcher-%s.tmp" % secrets.token_hex(8))
    recovery.safe(staged, app)
    shutil.copyfile(shipped, staged)
    recovery.flush(staged)
    deadline = time.monotonic() + LAUNCHER_SECONDS
    try:
        while True:
            try:
                os.replace(staged, installed)       # one same-volume rename over the old exe
                break
            except PermissionError:
                if time.monotonic() >= deadline:
                    raise UpdateError("the old UncleFarmer.exe stayed in use; the update is installed, "
                                      "but start UncleFarmerApp.exe until the next update") from None
                time.sleep(0.2)
    finally:
        if os.path.exists(staged):
            os.remove(staged)
    recovery.flush(installed)
    log("the native UncleFarmer.exe front door replaced the old app executable")


def _copier_app(src: str) -> str | None:
    """Derive the sole writable destination from this helper's trusted update/new location."""
    current = os.path.abspath(src)
    while os.path.dirname(current) != current:
        parent = os.path.dirname(current)
        if os.path.basename(current).casefold() == "new" and os.path.basename(parent).casefold() == "update":
            app = os.path.dirname(parent)
            _staging(parent, app)
            _safe_entry(src, parent)
            if not _link(app) and os.path.isfile(os.path.join(app, EXE)):
                return app
            return None
        current = parent
    return None


def _report_result(app: str, result: UpdateResult) -> None:
    try:
        staging = _staging(os.path.join(app, "update"), app)
        target = os.path.join(staging, "result.json")
        _safe_entry(target, staging)
        json.save(target, result)
    except Exception:
        applog.update("FAILED to write update result\n" + traceback.format_exc(), "ERROR", logs=os.path.join(app, "logs"))


def _restart(app: str) -> str | None:
    try:
        target = os.path.join(app, EXE)
        _safe_entry(target, app)
        if not os.path.isfile(target):
            raise UpdateError("the application executable is unavailable")
        subprocess.Popen([target], cwd=app, close_fds=True,
                         creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
        return None
    except Exception as error:
        applog.update("FAILED to restart the application\n" + traceback.format_exc(), "ERROR", logs=os.path.join(app, "logs"))
        return "%s: %s" % (type(error).__name__, error)


def _await_activation(update: str, token: str) -> None:
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        _staging(update, os.path.dirname(update))
        path = os.path.join(update, "apply.json")
        _safe_entry(path, update)
        try:
            with open(path, encoding="utf-8") as f:
                signal = _obj(json.load(f))
            if signal and signal.get("token") == token:
                return
        except (OSError, ValueError):
            pass
        time.sleep(0.05)
    raise UpdateError("the application did not authorize the update")


def _finish_copier(app: str, pid: int | None, result: UpdateResult, *, safe_restart: bool = True) -> None:
    """Report and recovery must not block one another, even when either operation fails."""
    _report_result(app, result)
    if not safe_restart:
        applog.update("FAILED rollback: automatic restart withheld; use the retained backup named in the update result",
                       "ERROR", logs=os.path.join(app, "logs"))
        return
    try:
        if pid is None or not _alive(pid):
            restart_error = _restart(app)
            if restart_error:
                result["ok"] = False
                result["error"] += "; could not restart the app: " + restart_error
                _report_result(app, result)
    except Exception:
        applog.update("FAILED to check recovery process\n" + traceback.format_exc(), "ERROR",
                       logs=os.path.join(app, "logs"))


def run_apply(argv: list[str]) -> None:
    """Validate the staged helper, wait for authorization and exit, then report/recover separately."""
    app: str | None = None
    pid: int | None = None
    safe_restart = True
    result: UpdateResult = {"version": "?", "ok": False, "error": ""}
    try:
        src = os.path.dirname(os.path.abspath(sys.executable))
        app = _copier_app(src)
        if app is None:
            raise UpdateError("the updater is not inside a valid application's update/new folder")
        if len(argv) not in (3, 4):
            raise UpdateError("expected application path, old process ID and version")
        try:
            pid = int(argv[1])
        except ValueError as error:
            raise UpdateError("invalid old application process ID") from error
        if pid <= 0 or VERSION.fullmatch(argv[2]) is None:
            raise UpdateError("invalid process ID or update version")
        result["version"] = argv[2]
        if not _same(argv[0], app):
            raise UpdateError("invalid destination application directory")
        if not frozen():
            raise UpdateError("updates cannot run from source")
        _verify_release(src, argv[2])
        update = _staging(os.path.join(app, "update"), app)
        _mark_busy(update, "update copier")
        if len(argv) == 4:
            token = argv[3]
            if re.fullmatch(r"[0-9a-f]{32}", token) is None:
                raise UpdateError("invalid update authorization token")
            _staging(update, app)
            _safe_entry(os.path.join(update, BUSY), update)
            json.save(os.path.join(update, BUSY), {"pid": os.getpid(), "what": "update copier",
                                                  "since": time.time(), "token": token})
            _await_activation(update, token)
        def report(text: str) -> None:
            applog.update("copier: " + text, logs=os.path.join(app or "", "logs"))
        report("updating %s to %s" % (app, result["version"]))
        _wait_for_exit(pid)
        if _alive(pid):
            raise UpdateError("the old app is still running")
        ensure_recovery_runtime(app, src)
        apply(app, src, report)
        result["ok"] = True
    except Exception as error:
        safe_restart = not isinstance(error, RollbackError)
        result["error"] = "%s: %s" % (type(error).__name__, error)
        applog.update("copier: FAILED " + result["error"] + "\n" + traceback.format_exc(), "ERROR",
                       logs=os.path.join(app, "logs") if app else paths.LOGS)
    finally:
        if app is not None:
            _finish_copier(app, pid, result, safe_restart=safe_restart)


def take_result() -> UpdateResult | None:
    """After an update: {"version", "ok", "error"}, once. None when there was no update. The
    caller cleans the staging folder afterwards (clean(wait=...)), which it does either way: a
    failed update's copy is of no further use, and the log in logs/ says what happened."""
    try:
        with open(RESULT, encoding="utf-8") as f:
            data = _obj(json.load(f))
        if (data is None or not isinstance(data.get("version"), str) or type(data.get("ok")) is not bool
                or not isinstance(data.get("error"), str)):
            raise ValueError("invalid update result structure")
        result: UpdateResult = {"version": data["version"], "ok": data["ok"], "error": data["error"]}
    except OSError:
        return None
    except ValueError:
        result = {"version": "?", "ok": False, "error": "the update's result file is unreadable"}
    try:
        os.remove(RESULT)
    except OSError:
        pass
    log("the update to %s %s" % (result.get("version"), "finished" if result.get("ok") else
                                 "didn't finish: %s" % result.get("error")), "INFO" if result.get("ok") else "WARNING")
    return result
