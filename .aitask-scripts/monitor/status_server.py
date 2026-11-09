"""status_server - the shared monitor status server and its ``ensure`` entry point.

ONE ``TmuxMonitor`` producer per (tmux server, framework ``VERSION``), served to
every subscriber over the monitor status protocol (newline-delimited JSON on a
Unix socket; ``status_protocol.py`` is the codec). The specification, including
the lifecycle this module implements, is
``aidocs/framework/monitor_status_protocol.md`` ("Lifecycle and socket path").

- :func:`ensure_server` — reach the server for this tmux server and VERSION, or
  start it detached under an exclusive file lock. Returns ``RUNNING`` /
  ``STARTED`` / ``UNAVAILABLE`` (a client falls back to in-process scanning).
- :class:`StatusServer` — the asyncio server: one producer, one encoder, one
  ordered outbound queue per connection, and the exit conditions (idle grace,
  socket replaced, tmux server gone).

tmux is reached only through ``TmuxMonitor`` and ``lib/tmux_exec.TmuxClient``
(``tests/test_no_raw_tmux.sh``). Headless: no Textual import, so the server
never pays for one (``monitor_shared`` would pull it in).

CLI::

    python3 .aitask-scripts/monitor/status_server.py ensure [--version V] [--session S] [--grace G] [--deadline D]
    python3 .aitask-scripts/monitor/status_server.py serve --socket SOCK [--lock-fd N] [--version V] ...
    python3 .aitask-scripts/monitor/status_server.py path [--version V]
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import errno
import fcntl
import hashlib
import math
import os
import re
import signal
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
for _extra in (_SCRIPTS_DIR / "lib", _SCRIPTS_DIR):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

try:  # imported as part of the `monitor` package
    from . import status_protocol as sp
    from .monitor_core import (
        CAPTURE_PIN_ALL,
        SESSION_CONFIG_KEYS,
        PaneCategory,
        TaskInfoCache,
        TmuxMonitor,
        is_task_completed,
        load_monitor_config,
        load_project_tmux_config,
        parked_capture_skip,
    )
except ImportError:  # run as a script
    import status_protocol as sp  # noqa: E402
    from monitor_core import (  # noqa: E402
        CAPTURE_PIN_ALL,
        SESSION_CONFIG_KEYS,
        PaneCategory,
        TaskInfoCache,
        TmuxMonitor,
        is_task_completed,
        load_monitor_config,
        load_project_tmux_config,
        parked_capture_skip,
    )

import agent_marks  # noqa: E402
from framework_version import read_installed_version  # noqa: E402
from tmux_exec import TmuxClient  # noqa: E402


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Seconds with no subscriber before the server exits.
DEFAULT_GRACE = 30.0
#: Seconds a connection has to complete its ``hello``.
HELLO_TIMEOUT = 10.0
#: Messages a connection may have queued before it is dropped as too slow.
OUTBOUND_LIMIT = 128
#: Watchdog cadence (idle grace, socket inode, ``%exit``).
WATCHDOG_INTERVAL = 0.5
#: Seconds a closing connection's writer gets to flush before it is cancelled.
WRITER_CLOSE_TIMEOUT = 2.0
#: Tick interval bounds and the per-project default (``tmux.monitor.refresh_seconds``).
DEFAULT_REFRESH = 3.0
MIN_REFRESH = 1.0
MAX_REFRESH = 60.0
#: How long :func:`ensure_server` waits for a lock or a starting server.
ENSURE_DEADLINE = 10.0
PROBE_TIMEOUT = 1.0
_POLL = 0.05
#: ``sun_path`` is 104 bytes on macOS (108 on Linux), terminator included.
MAX_SOCKET_PATH_BYTES = 103

RUNTIME_SUBDIR = "aitasks"
FALLBACK_RUNTIME_DIR = "~/.aitask/run"
SERVER_SCRIPT = Path(__file__).resolve()

#: ``ALREADY_RUNNING`` exit status of ``serve``.
EXIT_ALREADY_RUNNING = 3
#: ``serve`` refused: its tmux server is not the one it was keyed under.
EXIT_TMUX_MISMATCH = 4

_SLUG_RE = re.compile(r"[A-Za-z0-9._+-]{1,64}")


def _log(message: str) -> None:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    print(f"{stamp} status_server[{os.getpid()}]: {message}", file=sys.stderr, flush=True)


def framework_version() -> str:
    return read_installed_version(_SCRIPTS_DIR.parent) or "unknown"


# ---------------------------------------------------------------------------
# Paths, key and lock
# ---------------------------------------------------------------------------

class Unavailable(Exception):
    """The server cannot be reached or started; ``reason`` is a stable token."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class RuntimePaths:
    directory: Path
    socket: Path
    lock: Path
    log: Path


def runtime_dir(environ=None) -> Path:
    """``$XDG_RUNTIME_DIR/aitasks`` when that is an existing directory, else
    ``~/.aitask/run``. Resolution only — :func:`ensure_runtime_dir` creates and
    checks it."""
    env = os.environ if environ is None else environ
    xdg = env.get("XDG_RUNTIME_DIR")
    if xdg and os.path.isdir(xdg):
        return Path(xdg) / RUNTIME_SUBDIR
    return Path(os.path.expanduser(FALLBACK_RUNTIME_DIR))


def ensure_runtime_dir(path: Path) -> Path:
    """Create ``path`` (mode 0700) and prove it is ours and private.

    It must be a real directory (never a symlink), owned by this uid, with no
    group/other bits. A directory we own with loose bits is tightened; anything
    else raises :class:`Unavailable` ``unsafe_runtime_dir``."""
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        st = os.lstat(path)
    except OSError as exc:
        raise Unavailable("unsafe_runtime_dir", str(exc)) from None
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid():
        raise Unavailable("unsafe_runtime_dir", f"{path} is not a directory owned by uid {os.getuid()}")
    if st.st_mode & 0o077:
        try:
            os.chmod(path, 0o700)
            st = os.lstat(path)
        except OSError as exc:
            raise Unavailable("unsafe_runtime_dir", str(exc)) from None
        if st.st_mode & 0o077:
            raise Unavailable("unsafe_runtime_dir", f"{path} is not private")
    return path


def version_slug(version: str) -> str:
    """``version`` itself when it is filename-safe, else ``v`` + a hash."""
    if _SLUG_RE.fullmatch(version):
        return version
    return "v" + hashlib.sha256(version.encode("utf-8", "surrogatepass")).hexdigest()[:12]


def server_paths(tmux_socket: str, version: str, directory: Path | None = None) -> RuntimePaths:
    """The socket / lock / log paths for (tmux server, VERSION).

    The key is the tmux server's own ``#{socket_path}``, hashed, so every way of
    naming that server (``-L``, ``AITASKS_TMUX_SOCKET``, ``TMUX_TMPDIR``, ambient
    ``$TMUX``) converges on one socket."""
    key = hashlib.sha256(tmux_socket.encode("utf-8", "surrogateescape")).hexdigest()[:16]
    stem = f"monitor-{key}-{version_slug(version)}"
    base = runtime_dir() if directory is None else Path(directory)
    return RuntimePaths(
        directory=base,
        socket=base / f"{stem}.sock",
        lock=base / f"{stem}.lock",
        log=base / f"{stem}.log",
    )


def lock_path_for(socket_path) -> Path:
    socket_path = Path(socket_path)
    return socket_path.with_name(socket_path.stem + ".lock")


def tmux_socket_path(client: TmuxClient | None = None) -> str | None:
    """The answering tmux server's socket path, or ``None`` when no server
    answers. Asked of tmux itself (``list-sessions -F #{socket_path}``) through
    the gateway, so it is authoritative for whatever socket the environment
    resolves to."""
    client = client or TmuxClient()
    rc, out = client.run(["list-sessions", "-F", "#{socket_path}"])
    if rc != 0:
        return None
    first = out.split("\n", 1)[0].strip()
    if not first or not os.path.isabs(first):
        return None
    return first


def _try_lock(fd: int) -> bool:
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        if exc.errno in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES):
            return False
        raise
    return True


def _open_lock(path: Path) -> int:
    return os.open(path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)


def _remove_stale_socket(path: Path) -> None:
    """Unlink a leftover socket file. Called only while holding the lock, so
    no live server owns it. Refuses anything that is not a socket we own."""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return
    if not stat.S_ISSOCK(st.st_mode) or st.st_uid != os.getuid():
        raise Unavailable("unsafe_socket_path", f"{path} exists and is not our socket")
    with contextlib.suppress(FileNotFoundError):
        os.unlink(path)


# ---------------------------------------------------------------------------
# Probe and ensure
# ---------------------------------------------------------------------------

async def probe_async(socket_path, version: str, timeout: float = PROBE_TIMEOUT) -> dict | None:
    """Send ``hello`` and return the decoded answer (a ``welcome`` or an
    ``error``), or ``None`` when nothing answers. Never subscribes, so a probe
    never counts as a subscriber."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(str(socket_path), limit=sp.MAX_SERVER_LINE_BYTES),
            timeout)
    except (OSError, asyncio.TimeoutError, ValueError):
        return None
    try:
        writer.write(sp.encode({
            "type": "hello", "proto": sp.PROTO, "version": version,
            "client": {"kind": "probe", "pid": os.getpid()},
        }, direction=sp.CLIENT))
        await writer.drain()
        line = await asyncio.wait_for(sp.read_line(reader), timeout)
        if line is None:
            return None
        return sp.decode(line, direction=sp.SERVER)
    except (OSError, asyncio.TimeoutError, sp.ProtocolError):
        return None
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()


def probe(socket_path, version: str, timeout: float = PROBE_TIMEOUT) -> dict | None:
    """Synchronous :func:`probe_async` — for a thread with no running loop."""
    return asyncio.run(probe_async(socket_path, version, timeout))


def _welcome_pid(msg: dict | None, version: str) -> tuple[bool, int | None]:
    """``(answered_by_our_server, pid)`` for a probe answer."""
    if msg is None or msg.get("type") != "welcome" or msg.get("version") != version:
        return False, None
    return True, msg.get("server", {}).get("pid")


@dataclass(frozen=True)
class EnsureResult:
    state: str              # RUNNING | STARTED | UNAVAILABLE
    socket: str | None = None
    pid: int | None = None
    reason: str = ""

    def line(self) -> str:
        if self.state == "UNAVAILABLE":
            return f"UNAVAILABLE:{self.reason}"
        return f"{self.state}:{self.socket}|{self.pid if self.pid is not None else ''}"


def _last_log_line(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    except OSError:
        return ""
    return lines[-1][:200] if lines else ""


def _spawn_server(paths: RuntimePaths, lock_fd: int, *, version: str, tmux_socket: str,
                  session: str, project_root: Path, grace: float | None,
                  python: str | None) -> subprocess.Popen:
    argv = [
        python or sys.executable, str(SERVER_SCRIPT), "serve",
        "--socket", str(paths.socket), "--lock-fd", str(lock_fd),
        "--version", version, "--tmux-socket-path", tmux_socket,
        "--session", session or "", "--project-root", str(project_root),
    ]
    if grace is not None:
        argv += ["--grace", str(grace)]
    log_fd = os.open(paths.log, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW
                     | os.O_CLOEXEC, 0o600)
    try:
        # start_new_session == setsid: no controlling terminal, so closing the
        # pane that started it does not SIGHUP the shared server.
        return subprocess.Popen(
            argv, stdin=subprocess.DEVNULL, stdout=log_fd, stderr=log_fd,
            start_new_session=True, close_fds=True, pass_fds=(lock_fd,),
            cwd=str(project_root),
        )
    finally:
        os.close(log_fd)


def ensure_server(*, version: str | None = None, session: str = "",
                  project_root=None, deadline: float = ENSURE_DEADLINE,
                  grace: float | None = None, tmux_client: TmuxClient | None = None,
                  python: str | None = None) -> EnsureResult:
    """Reach — or start — the status server for this tmux server and VERSION.

    1. No tmux server answering → ``UNAVAILABLE:no_tmux_server``.
    2. A ``hello`` probe answers with our version → ``RUNNING``.
    3. Otherwise take the exclusive lock (non-blocking, retried until
       ``deadline``, probing between tries — another caller may be starting it).
       Holding it proves no server is alive, so a leftover socket is stale and is
       removed; then the server is spawned with the lock fd **inherited**, so
       the lock stays held for the server's whole life, and the call waits for
       its ``welcome`` → ``STARTED``.

    Synchronous on purpose (a client calls it from a worker thread). Never
    raises for an environment problem — every one is an ``UNAVAILABLE`` reason.
    """
    version = version or framework_version()
    root = Path(project_root) if project_root else _SCRIPTS_DIR.parent
    tmux_socket = tmux_socket_path(tmux_client)
    if tmux_socket is None:
        return EnsureResult("UNAVAILABLE", reason="no_tmux_server")
    try:
        directory = ensure_runtime_dir(runtime_dir())
    except Unavailable as exc:
        return EnsureResult("UNAVAILABLE", reason=exc.reason)
    paths = server_paths(tmux_socket, version, directory)
    if len(os.fsencode(str(paths.socket))) > MAX_SOCKET_PATH_BYTES:
        return EnsureResult("UNAVAILABLE", reason="socket_path_too_long")

    end = time.monotonic() + deadline
    ok, pid = _welcome_pid(probe(paths.socket, version), version)
    if ok:
        return EnsureResult("RUNNING", str(paths.socket), pid)
    try:
        fd = _open_lock(paths.lock)
    except OSError as exc:
        return EnsureResult("UNAVAILABLE", reason=f"lock_failed:{exc.strerror}")
    try:
        while not _try_lock(fd):
            ok, pid = _welcome_pid(probe(paths.socket, version), version)
            if ok:
                return EnsureResult("RUNNING", str(paths.socket), pid)
            if time.monotonic() >= end:
                return EnsureResult("UNAVAILABLE", reason="lock_timeout")
            time.sleep(_POLL)
        # The lock is ours: no server (and no other starter) is alive.
        try:
            _remove_stale_socket(paths.socket)
        except Unavailable as exc:
            return EnsureResult("UNAVAILABLE", reason=exc.reason)
        try:
            proc = _spawn_server(paths, fd, version=version, tmux_socket=tmux_socket,
                                 session=session, project_root=root, grace=grace,
                                 python=python)
        except OSError as exc:
            return EnsureResult("UNAVAILABLE", reason=f"spawn_failed:{exc.strerror}")
        while True:
            ok, pid = _welcome_pid(probe(paths.socket, version), version)
            if ok:
                return EnsureResult("STARTED", str(paths.socket), pid)
            if proc.poll() is not None:
                return EnsureResult("UNAVAILABLE",
                                    reason=f"server_failed:{_last_log_line(paths.log)}")
            if time.monotonic() >= end:
                # Left running: it holds the lock and may still come up; if it
                # does and nobody subscribes, its idle grace ends it.
                return EnsureResult("UNAVAILABLE", reason="start_timeout")
            time.sleep(_POLL)
    finally:
        # Never LOCK_UN: the open file description is shared with the server,
        # and unlocking it would release the server's lock too.
        os.close(fd)


# ---------------------------------------------------------------------------
# Per-project config
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProjectConfig:
    #: :func:`load_monitor_config`, filtered to ``SESSION_CONFIG_KEYS``.
    monitor: dict
    #: ``tmux.monitor.refresh_seconds``, or :data:`DEFAULT_REFRESH` when it is
    #: missing or invalid — resolved PER PROJECT, as ``ait monitor`` does.
    refresh_seconds: float


def refresh_seconds_of(tmux_config) -> float:
    """``tmux.monitor.refresh_seconds`` from a ``tmux`` section, else 3.

    Only a finite number ``> 0`` counts (``bool`` is not a number here)."""
    monitor = tmux_config.get("monitor") if isinstance(tmux_config, dict) else None
    value = monitor.get("refresh_seconds") if isinstance(monitor, dict) else None
    if type(value) is int:
        # Compared as an int and capped BEFORE converting: YAML integers are
        # unbounded and `float(10**400)` overflows. The cap is the tick
        # interval's upper clamp, so nothing observable changes.
        return float(min(value, int(MAX_REFRESH))) if value > 0 else DEFAULT_REFRESH
    if type(value) is float and math.isfinite(value) and value > 0:
        return value
    return DEFAULT_REFRESH


def tick_interval(configs) -> float:
    """The minimum interval over every mapped project, clamped to [1, 60];
    3 when nothing is mapped."""
    values = [c.refresh_seconds for c in configs]
    value = min(values) if values else DEFAULT_REFRESH
    return min(MAX_REFRESH, max(MIN_REFRESH, value))


class ProjectConfigCache:
    """``ProjectConfig`` per project root, re-read only when the root's
    ``project_config.yaml`` changes (``(st_mtime_ns, st_size, st_ino)``)."""

    def __init__(self, load_monitor=None, load_tmux=None):
        self._load_monitor = load_monitor or load_monitor_config
        self._load_tmux = load_tmux or load_project_tmux_config
        self._cache: dict[Path, tuple] = {}

    def get(self, root) -> ProjectConfig:
        root = Path(root)
        path = root / "aitasks" / "metadata" / "project_config.yaml"
        try:
            st = os.stat(path)
            stamp = (st.st_mtime_ns, st.st_size, st.st_ino)
        except OSError:
            stamp = None
        hit = self._cache.get(root)
        if hit is not None and hit[0] == stamp:
            return hit[1]
        monitor = self._load_monitor(root) or {}
        cfg = ProjectConfig(
            monitor={k: monitor[k] for k in SESSION_CONFIG_KEYS if k in monitor},
            refresh_seconds=refresh_seconds_of(self._load_tmux(root)),
        )
        self._cache[root] = (stamp, cfg)
        return cfg


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------

def _pins_from_wire(pins):
    if pins == sp.PINS_ALL:
        return CAPTURE_PIN_ALL
    return frozenset(tuple(p) for p in pins)


class _Connection:
    """One client. ONE bounded outbound queue drained by one writer task.

    Every enqueue of a delta or a reply snapshot happens in a synchronous
    section (no ``await`` between reading the encoder and enqueueing), which is
    the asyncio form of the spec's "lock held across read state + enqueue": a
    reply snapshot always falls between two deltas."""

    def __init__(self, server: "StatusServer", reader, writer):
        self.server = server
        self.reader = reader
        self.writer = writer
        self.content = sp.CONTENT_ALL
        self.include_shadows = True
        self.hello_done = False
        #: Receives deltas (set once its first snapshot is enqueued).
        self.subscribed = False
        #: Pins count toward the skip set (set when it starts subscribing).
        self.pins_active = False
        self.pins = frozenset()
        self.outq: asyncio.Queue = asyncio.Queue()
        self.closing = asyncio.Event()

    # -- outbound ------------------------------------------------------------

    def full_view(self) -> bool:
        return self.content == sp.CONTENT_ALL and self.include_shadows

    def enqueue(self, raw: bytes) -> None:
        if self.closing.is_set():
            return
        if self.outq.qsize() >= self.server.outbound_limit:
            _log(f"dropping a connection {self.outq.qsize()} messages behind")
            self.close_now()
            return
        self.outq.put_nowait(raw)

    def send(self, msg: dict) -> None:
        try:
            raw = sp.encode(msg, direction=sp.SERVER)
        except sp.ProtocolError as exc:
            if msg.get("type") == "error":
                _log(f"unencodable error reply dropped: {exc}")
                return
            self.send_error("internal", f"reply could not be encoded: {exc}",
                            id=msg.get("id"), request=msg.get("request"))
            return
        self.enqueue(raw)

    def send_error(self, code: str, message: str, *, id=None, request=None, **extra) -> None:
        msg = {"type": "error", "ts": round(time.time(), 3), "code": code,
               "message": message[:sp.MAX_TEXT_CHARS]}
        if id is not None:
            msg["id"] = id
        if type(request) is str and 0 < len(request) <= 64:
            msg["request"] = request
        msg.update(extra)
        self.send(msg)

    def send_result(self, request: str, *, id=None, **extra) -> None:
        msg = {"type": "result", "ts": round(time.time(), 3), "request": request}
        if id is not None:
            msg["id"] = id
        msg.update(extra)
        self.send(msg)

    def close_now(self) -> None:
        """End the connection from the server side: drop what is queued, abort
        the transport (a client that stopped reading would otherwise keep the
        writer blocked in ``drain()`` forever), and wake the reader."""
        if self.closing.is_set():
            return
        self.closing.set()
        while not self.outq.empty():
            self.outq.get_nowait()
        self.outq.put_nowait(None)
        transport = getattr(self.writer, "transport", None)
        if transport is not None:
            with contextlib.suppress(Exception):
                transport.abort()

    async def _writer_loop(self) -> None:
        try:
            while True:
                item = await self.outq.get()
                if item is None:
                    break
                self.writer.write(item)
                await self.writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            self.closing.set()
            self.writer.close()
            with contextlib.suppress(Exception):
                await self.writer.wait_closed()

    # -- inbound -------------------------------------------------------------

    async def _next_line(self, timeout: float | None) -> bytes | None:
        read = asyncio.create_task(sp.read_line(self.reader), name="status-read")
        stop = asyncio.create_task(self.closing.wait(), name="status-closing")
        try:
            done, _pending = await asyncio.wait(
                {read, stop}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
            if read in done:
                return read.result()
            if stop in done:
                return None
            raise asyncio.TimeoutError
        finally:
            for task in (read, stop):
                task.cancel()
            for task in (read, stop):
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task

    async def run(self) -> None:
        writer_task = asyncio.create_task(self._writer_loop(), name="status-writer")
        deadline = time.monotonic() + self.server.hello_timeout
        try:
            while not self.closing.is_set():
                timeout = None if self.hello_done else max(0.0, deadline - time.monotonic())
                try:
                    line = await self._next_line(timeout)
                except asyncio.TimeoutError:
                    self.send_error("bad_message", "no hello within the handshake timeout")
                    break
                except sp.FramingError as exc:
                    # Terminal: never re-frame inside the stream.
                    self.send_error("too_long", str(exc))
                    break
                if line is None:
                    break
                try:
                    msg = sp.decode(line, direction=sp.CLIENT)
                except sp.ProtocolError as exc:
                    self.send_error(exc.code, str(exc), id=exc.request_id,
                                    request=exc.request_type)
                    if not self.hello_done:
                        break
                    continue
                if not await self._handle(msg):
                    break
        except (ConnectionError, OSError):
            pass
        finally:
            self.server._drop(self)
            if not self.closing.is_set():
                self.outq.put_nowait(None)
            # Bounded: a writer stuck in drain() is cancelled, never awaited
            # forever (wait_for cancels it on timeout).
            with contextlib.suppress(asyncio.TimeoutError, asyncio.CancelledError, Exception):
                await asyncio.wait_for(writer_task, timeout=self.server.writer_close_timeout)

    async def _handle(self, msg: dict) -> bool:
        """Handle one decoded request. Returns False to close the connection."""
        kind = msg["type"]
        rid = msg.get("id")
        server = self.server
        if kind == "hello":
            if self.hello_done:
                self.send_error("bad_message", "hello already received")
                return True
            if msg["proto"] != sp.PROTO:
                self.send_error("proto_mismatch", f"server speaks proto {sp.PROTO}",
                                server_proto=sp.PROTO)
                return False
            if msg["version"] != server.version:
                self.send_error("version_mismatch",
                                f"server is version {server.version!r}",
                                server_version=server.version)
                return False
            self.hello_done = True
            self.send({
                "type": "welcome", "ts": round(time.time(), 3), "proto": sp.PROTO,
                "version": server.version,
                "server": {"impl": "python", "pid": os.getpid()},
            })
            return True
        if not self.hello_done:
            self.send_error("bad_message", "hello required first", id=rid, request=kind)
            return False
        if kind == "subscribe":
            await server._subscribe(self, msg)
            return True
        if kind == "set_content":
            if not self.subscribed:
                self.send_error("not_subscribed", "subscribe first", id=rid, request=kind)
                return True
            self.content = msg["content"]
            self.send(server._snapshot_for(self, id=rid))
            return True
        if kind == "set_pins":
            await server._set_pins(self, msg)
            return True
        if kind == "refresh":
            await server._refresh(self, msg)
            return True
        if kind in ("set_compare_mode", "cycle_compare_mode"):
            await server._compare_mode(self, msg)
            return True
        if kind == "capture":
            await server._capture(self, msg)
            return True
        self.send_error("unknown_type", f"unhandled request {kind!r}", id=rid, request=kind)
        return True


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

class StatusServer:
    """One producer, served to every subscriber.

    ``monitor`` is a ``TmuxMonitor`` (``serve`` builds one with default config;
    per-session config is published each tick). ``_producer_lock`` serializes
    every operation that captures or changes a capture input — ticks,
    ``refresh``, compare-mode changes, ``set_pins`` — so a single-pane capture
    never supersedes a full tick's generation and a mode change never lands
    between a capture and its commit."""

    def __init__(self, monitor, *, socket_path, version: str, project_root=None,
                 grace: float = DEFAULT_GRACE, clock=time.monotonic, probe_tmux=None,
                 expected_tmux_socket: str | None = None, marks_view=None,
                 task_cache=None, config_cache=None, hello_timeout: float = HELLO_TIMEOUT,
                 outbound_limit: int = OUTBOUND_LIMIT,
                 watchdog_interval: float = WATCHDOG_INTERVAL,
                 interval_override: float | None = None,
                 start_control_client: bool = True):
        self.monitor = monitor
        self.socket_path = str(socket_path)
        self.version = version
        self.project_root = Path(project_root) if project_root else _SCRIPTS_DIR.parent
        self.grace = grace
        self.hello_timeout = hello_timeout
        self.outbound_limit = outbound_limit
        self.writer_close_timeout = WRITER_CLOSE_TIMEOUT
        self.watchdog_interval = watchdog_interval
        self._clock = clock
        self._probe_tmux = probe_tmux or (lambda: tmux_socket_path())
        self._expected_tmux_socket = expected_tmux_socket
        self._marks = marks_view if marks_view is not None else agent_marks.MarksView()
        self._task_cache = task_cache if task_cache is not None else TaskInfoCache(self.project_root)
        self._configs = config_cache if config_cache is not None else ProjectConfigCache()
        self._interval_override = interval_override
        self._start_control = start_control_client
        self._encoder = sp.StreamEncoder()
        self._connections: set[_Connection] = set()
        self._snaps: dict = {}
        self._mapping: dict = {}
        self._global_parked: frozenset = frozenset()
        #: When the last FULL tick committed. Partial refreshes commit too, but
        #: they never discover, so they must not postpone the next full scan.
        self._last_full_tick: float | None = None
        #: Earliest time the next full tick may be attempted after a failed one,
        #: so a persistent failure is retried at the tick cadence, not in a loop.
        self._retry_at: float = -math.inf
        self.interval = DEFAULT_REFRESH if interval_override is None else interval_override
        self.exit_reason: str | None = None
        self._idle_since = clock()
        self._bound_ino: int | None = None
        self._server: asyncio.base_events.Server | None = None
        self._tasks: list[asyncio.Task] = []
        self._conn_tasks: set[asyncio.Task] = set()
        self._producer_lock: asyncio.Lock | None = None
        self._exit: asyncio.Event | None = None
        self._has_subscribers: asyncio.Event | None = None

    # -- lifecycle -----------------------------------------------------------

    async def start(self) -> None:
        self._producer_lock = asyncio.Lock()
        self._exit = asyncio.Event()
        self._has_subscribers = asyncio.Event()
        self._idle_since = self._clock()
        self._server = await asyncio.start_unix_server(
            self._on_connect, path=self.socket_path, limit=sp.MAX_CLIENT_LINE_BYTES)
        st = os.lstat(self.socket_path)
        self._bound_ino = st.st_ino
        with contextlib.suppress(OSError):
            os.chmod(self.socket_path, 0o600)
        self._tasks = [
            asyncio.create_task(self._tick_loop(), name="status-ticks"),
            asyncio.create_task(self._watchdog(), name="status-watchdog"),
        ]
        if self._start_control:
            self._tasks.append(asyncio.create_task(self._start_control_client(),
                                                   name="status-control"))

    def request_exit(self, reason: str) -> None:
        if self.exit_reason is None:
            self.exit_reason = reason
            _log(f"exit requested: {reason}")
        if self._exit is not None:
            self._exit.set()

    async def serve_until_exit(self) -> str:
        await self._exit.wait()
        await self.close()
        return self.exit_reason or "unknown"

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
        for conn in list(self._connections):
            conn.close_now()
        for task in list(self._tasks) + list(self._conn_tasks):
            task.cancel()
        for task in list(self._tasks) + list(self._conn_tasks):
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        if self._server is not None:
            with contextlib.suppress(Exception):
                await self._server.wait_closed()
            self._server = None
        with contextlib.suppress(Exception):
            await self.monitor.close_control_client()
        self._unlink_own_socket()

    def _unlink_own_socket(self) -> None:
        """Remove the socket only if it is still the one we bound."""
        try:
            st = os.lstat(self.socket_path)
        except FileNotFoundError:
            return
        if self._bound_ino is not None and st.st_ino == self._bound_ino:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(self.socket_path)

    async def _on_connect(self, reader, writer) -> None:
        task = asyncio.current_task()
        self._conn_tasks.add(task)
        conn = _Connection(self, reader, writer)
        self._connections.add(conn)
        try:
            await conn.run()
        finally:
            self._conn_tasks.discard(task)

    def _subscriber_count(self) -> int:
        return sum(1 for c in self._connections if c.subscribed)

    def _drop(self, conn: _Connection) -> None:
        """A connection ended. Synchronous: its pins stop counting at once."""
        was = conn.subscribed
        self._connections.discard(conn)
        conn.subscribed = conn.pins_active = False
        if conn.pins:
            self._publish_skip_set()
        if was and self._subscriber_count() == 0:
            self._idle_since = self._clock()
            if self._has_subscribers is not None:
                self._has_subscribers.clear()

    async def _start_control_client(self, *, live_mapping: bool = False) -> None:
        try:
            await self._pick_control_session(live_mapping=live_mapping)
            if self.monitor.session:
                ok = await self.monitor.start_control_client()
                if not ok:
                    _log("tmux control mode unavailable; using subprocess fallback")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - the subprocess path still works
            _log(f"control client start failed: {exc!r}")

    async def _pick_control_session(self, *, live_mapping: bool = False) -> None:
        """Attach to the session named at start when it is live, else to any
        live aitasks session (sorted, for a stable choice).

        ``live_mapping`` re-reads the sessions instead of using the last tick's
        mapping. The restart after ``%exit`` needs it: the session that just
        went away is still in that mapping, so picking from it would re-attach
        to the destroyed session, fail, and leave the server on the subprocess
        fallback while another aitasks session is live. The producer's session
        discovery is TTL-cached for the same reason, so it is invalidated too."""
        if live_mapping:
            self.monitor.invalidate_sessions_cache()
        mapping = None if live_mapping else self._mapping
        mapping = mapping or dict(
            await self.monitor.get_session_to_project_mapping_async() or {})
        if self.monitor.session and self.monitor.session in mapping:
            return
        self.monitor.session = sorted(mapping)[0] if mapping else ""

    async def _watchdog(self) -> None:
        while True:
            await asyncio.sleep(self.watchdog_interval)
            if self._subscriber_count() == 0 and self._clock() - self._idle_since >= self.grace:
                self.request_exit("idle")
                return
            try:
                st = os.lstat(self.socket_path)
                replaced = st.st_ino != self._bound_ino
            except FileNotFoundError:
                replaced = True
            if replaced:
                self.request_exit("socket_replaced")
                return
            try:
                exit_seen = bool(self.monitor.control_exit_seen())
            except Exception:  # noqa: BLE001
                exit_seen = False
            if exit_seen and await self._handle_exit_seen():
                return

    async def _handle_exit_seen(self) -> bool:
        """``%exit`` reached the control client. Exit when the tmux server is
        gone (or is no longer ours); otherwise it was a session detach, and the
        control client is restarted on a live session. True when exiting."""
        alive = await asyncio.to_thread(self._probe_tmux)
        if alive is None or (self._expected_tmux_socket and alive != self._expected_tmux_socket):
            self.request_exit("exit_seen")
            return True
        _log("%exit from a session detach; restarting the control client")
        async with self._producer_lock:
            await self.monitor.close_control_client()
        await self._start_control_client(live_mapping=True)
        return False

    async def _tick_loop(self) -> None:
        while True:
            if self._subscriber_count() == 0:
                await self._has_subscribers.wait()
                continue
            last = self._last_full_tick if self._last_full_tick is not None else -math.inf
            due = max(last + self.interval, self._retry_at)
            wait = due - self._clock()
            if wait > 0:
                # Chunked: an interval lowered by a config change (or a retry
                # deadline) is noticed within MIN_REFRESH, not after the old one.
                await asyncio.sleep(min(wait, MIN_REFRESH))
                continue
            await self.run_tick()

    # -- producer operations (all under the producer lock) --------------------

    async def run_tick(self) -> int | None:
        async with self._producer_lock:
            return await self._tick_locked()

    def _stale(self) -> bool:
        if self._clock() < self._retry_at:
            return False   # a full tick failed moments ago; do not hammer it
        return (self._last_full_tick is None
                or self._clock() - self._last_full_tick >= self.interval)

    async def _tick_locked(self) -> int | None:
        try:
            mapping = dict(await self.monitor.get_session_to_project_mapping_async() or {})
            configs = {s: self._configs.get(root) for s, root in mapping.items()}
            self.monitor.set_session_configs({s: c.monitor for s, c in configs.items()})
            self.interval = (self._interval_override if self._interval_override is not None
                             else tick_interval(configs.values()))
            self._task_cache.update_session_mapping(mapping)
            self._mapping = mapping
            # BEFORE the capture: publishing after it would capture every
            # already-parked agent once.
            self._publish_skip_set()
            gen, classified = await self.monitor.capture_all_classified_async()
            snaps = self.monitor.commit_snapshots(gen, classified)
            if snaps is None:
                _log(f"capture generation {gen} was superseded; no commit")
                self._retry_at = self._clock() + self.interval
                return None
            self._snaps = dict(snaps)
            gen = self._commit()
            self._last_full_tick = self._clock()
            self._retry_at = -math.inf
            return gen
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - a bad tick must not end the server
            # No generation is pretended: the encoder did not advance. The next
            # attempt waits one interval, so a persistent failure is retried at
            # the tick cadence instead of in a tight loop.
            self._retry_at = self._clock() + self.interval
            _log(f"tick failed: {exc!r}")
            return None

    def _publish_skip_set(self) -> None:
        """Re-derive the capture skip set — the global parked set minus every
        subscriber's pins — and publish it to the producer. Runs before every
        capture route (tick and partial refresh) and whenever pins change."""
        try:
            self._marks.refresh()
        except Exception as exc:  # noqa: BLE001 - advisory data must never break a tick
            _log(f"marks refresh failed: {exc!r}")
        try:
            self._global_parked = agent_marks.parked_session_windows(
                self._marks.parked_windows(), self._mapping)
        except Exception as exc:  # noqa: BLE001
            _log(f"parked set failed: {exc!r}")
        pins = [c.pins for c in self._connections if c.pins_active]
        self.monitor.set_parked_agents(parked_capture_skip(self._global_parked, pins))

    def _completed(self) -> frozenset:
        """AGENT panes whose task is Done or archived — excluding parked and
        frozen ones, including agents pinned live by some subscriber but
        globally parked (so the set is the same for every client)."""
        done = set()
        for pane_id, snap in self._snaps.items():
            pane = snap.pane
            if pane.category != PaneCategory.AGENT or snap.parked or snap.frozen:
                continue
            if (pane.session_name, pane.window_name) in self._global_parked:
                continue
            try:
                task_id = self._task_cache.get_task_id_for_pane(pane)
                if task_id and is_task_completed(
                        self._task_cache.get_task_info(task_id, pane.session_name)):
                    done.add(pane_id)
            except Exception:  # noqa: BLE001 - one unreadable task must not end the tick
                continue
        return frozenset(done)

    def _build_frame(self) -> sp.StreamFrame:
        monitor = self.monitor
        return sp.StreamFrame(
            panes={pid: sp.monitor_pane_record(monitor, s) for pid, s in self._snaps.items()},
            shadows={key: sp.monitor_pane_record(monitor, s)
                     for key, s in monitor.shadow_snapshots().items()},
            completed=self._completed(),
            sessions=sp.sessions_member({s: str(r) for s, r in self._mapping.items()}),
            parked=self._global_parked,
            discovery=sp.discovery_member(
                monitor.last_enumerated_sessions(), monitor.last_discovered_agents(),
                monitor.last_discovered_panes()),
            control_state=monitor.control_state().value,
        )

    def _commit(self) -> int:
        """Encode the current state as the next generation and broadcast it.
        Synchronous from encoder update to the last enqueue."""
        delta = self._encoder.update(self._build_frame(), ts=time.time())
        full = None
        for conn in list(self._connections):
            if not conn.subscribed:
                continue
            if conn.full_view():
                if full is None:
                    full = sp.encode(delta, direction=sp.SERVER)
                conn.enqueue(full)
            else:
                conn.send(sp.filter_message(delta, content=conn.content,
                                            include_shadows=conn.include_shadows))
        return delta["gen"]

    def _snapshot_for(self, conn: _Connection, *, id=None) -> dict:
        return self._encoder.snapshot(content=conn.content,
                                      include_shadows=conn.include_shadows, id=id)

    # -- requests ------------------------------------------------------------

    async def _subscribe(self, conn: _Connection, msg: dict) -> None:
        async with self._producer_lock:
            # Pins are capture policy and count for the prerequisite tick.
            if "pins" in msg:
                conn.pins = _pins_from_wire(msg["pins"])
            conn.pins_active = True
            if self._stale():
                # Fresh state for the reply. A first subscriber is not yet
                # `subscribed`, so this tick's delta does not reach it ahead of
                # its snapshot; a resyncing one gets it before the reply — under
                # its OLD selection, which is why content/include_shadows are
                # applied only after this await.
                await self._tick_locked()
            else:
                self._publish_skip_set()
            if conn.closing.is_set():
                return
            # Synchronous from here: switch the selection and enqueue the
            # snapshot with no delta in between.
            if "content" in msg:
                conn.content = msg["content"]
            if "include_shadows" in msg:
                conn.include_shadows = msg["include_shadows"]
            conn.send(self._snapshot_for(conn, id=msg.get("id")))
            if not conn.subscribed:
                conn.subscribed = True
                self._has_subscribers.set()

    async def _set_pins(self, conn: _Connection, msg: dict) -> None:
        async with self._producer_lock:
            conn.pins = _pins_from_wire(msg["pins"])
            if conn.pins_active:
                self._publish_skip_set()
            conn.send_result("set_pins", id=msg.get("id"))

    async def _refresh(self, conn: _Connection, msg: dict) -> None:
        rid = msg.get("id")
        async with self._producer_lock:
            panes = msg.get("panes")
            shadows = msg.get("shadows")
            if not panes and not shadows:
                gen = await self._tick_locked()
            else:
                gen = await self._partial_refresh_locked(panes or [], shadows or [])
            if gen is None:
                conn.send_error("internal", "refresh produced no generation", id=rid,
                                request="refresh")
                return
            conn.send_result("refresh", id=rid, gen=gen)

    async def _partial_refresh_locked(self, panes, shadows) -> int | None:
        try:
            # The single-pane capture refuses a parked pane by reading the
            # PREVIOUSLY published skip set: republish it so pins changed since
            # the last tick take effect on this capture.
            self._publish_skip_set()
            monitor = self.monitor
            for pane_id in panes:
                gen, pane, content, result = await monitor.capture_pane_classified_async(pane_id)
                if pane is None:
                    continue   # a failed capture keeps the prior record
                snap = monitor.commit_snapshot(gen, pane, content, result)
                if snap is not None:
                    self._snaps[pane_id] = snap
            for followed in shadows:
                await monitor.refresh_shadow_snapshot(followed)
            return self._commit()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            _log(f"partial refresh failed: {exc!r}")
            return None

    async def _compare_mode(self, conn: _Connection, msg: dict) -> None:
        kind = msg["type"]
        rid = msg.get("id")
        pane_id = msg["pane"]
        async with self._producer_lock:
            if pane_id not in self._snaps:
                conn.send_error("not_found", f"no pane {pane_id}", id=rid, request=kind)
                return
            if kind == "set_compare_mode":
                mode = self.monitor.set_compare_mode(pane_id, msg["mode"])
                following = not self.monitor.is_compare_mode_overridden(pane_id)
            else:
                mode, following = self.monitor.cycle_compare_mode(pane_id)
            conn.send_result(kind, id=rid, mode=mode, following_default=bool(following))

    async def _capture(self, conn: _Connection, msg: dict) -> None:
        """A raw one-off read: no generation, no idle clock, so no lock."""
        rid = msg.get("id")
        pane_id = msg["pane"]
        lines = msg["lines"]
        pane = None
        snap = self._snaps.get(pane_id)
        if snap is not None:
            pane = snap.pane
        else:
            for shadow in self.monitor.shadow_snapshots().values():
                if shadow.pane.pane_id == pane_id:
                    pane = shadow.pane
                    break
        if pane is None:
            conn.send_error("not_found", f"no pane {pane_id}", id=rid, request="capture")
            return
        try:
            raw = await self.monitor.capture_pane_content_async(
                pane_id, capture_lines=lines, pane=pane)
        except Exception as exc:  # noqa: BLE001
            raw = None
            _log(f"capture {pane_id} failed: {exc!r}")
        if raw is None:
            conn.send_error("unavailable", f"capture of {pane_id} failed", id=rid,
                            request="capture")
            return
        conn.send_result("capture", id=rid, pane=pane_id,
                         content=sp.tail_lines(raw[1], lines))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _hold_lock(args) -> int | None:
    """The lock fd ``serve`` runs under, or None when another server holds it."""
    if args.lock_fd is not None:
        fd = args.lock_fd
    else:
        fd = _open_lock(lock_path_for(args.socket))
    return fd if _try_lock(fd) else None


async def _serve_main(server: StatusServer) -> str:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError, RuntimeError):
            loop.add_signal_handler(sig, server.request_exit, "signal")
    await server.start()
    print(f"SERVING:{server.socket_path}", file=sys.stderr, flush=True)
    return await server.serve_until_exit()


def _cmd_serve(args) -> int:
    version = args.version or framework_version()
    if _hold_lock(args) is None:
        print("ALREADY_RUNNING", file=sys.stderr, flush=True)
        return EXIT_ALREADY_RUNNING
    actual = tmux_socket_path()
    if args.tmux_socket_path and actual != args.tmux_socket_path:
        print(f"EXIT:tmux_socket_mismatch ({actual!r} != {args.tmux_socket_path!r})",
              file=sys.stderr, flush=True)
        return EXIT_TMUX_MISMATCH
    if _welcome_pid(probe(args.socket, version), version)[0]:
        print("ALREADY_RUNNING", file=sys.stderr, flush=True)
        return EXIT_ALREADY_RUNNING
    if Path(args.socket).exists():
        _remove_stale_socket(Path(args.socket))
    monitor = TmuxMonitor(session=args.session or "")
    server = StatusServer(
        monitor, socket_path=args.socket, version=version,
        project_root=args.project_root, grace=args.grace,
        expected_tmux_socket=args.tmux_socket_path or actual,
        interval_override=args.interval,
    )
    reason = asyncio.run(_serve_main(server))
    print(f"EXIT:{reason}", file=sys.stderr, flush=True)
    return 0


def _cmd_ensure(args) -> int:
    result = ensure_server(version=args.version, session=args.session,
                           project_root=args.project_root, deadline=args.deadline,
                           grace=args.grace)
    print(result.line(), flush=True)
    return 1 if result.state == "UNAVAILABLE" else 0


def _cmd_path(args) -> int:
    tmux_socket = tmux_socket_path()
    if tmux_socket is None:
        print("UNAVAILABLE:no_tmux_server")
        return 1
    print(server_paths(tmux_socket, args.version or framework_version()).socket)
    return 0


def _positive(text: str) -> float:
    value = float(text)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError(f"must be a finite number > 0, got {text!r}")
    return value


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="status_server.py", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="run the server (normally started by ensure)")
    s.add_argument("--socket", required=True)
    s.add_argument("--lock-fd", type=int, default=None)
    s.add_argument("--version", default=None)
    s.add_argument("--tmux-socket-path", default=None)
    s.add_argument("--session", default="")
    s.add_argument("--project-root", default=None)
    s.add_argument("--grace", type=_positive, default=DEFAULT_GRACE)
    s.add_argument("--interval", type=_positive, default=None,
                   help="fixed tick interval (debugging); default: from project config")
    s.set_defaults(func=_cmd_serve)

    e = sub.add_parser("ensure", help="reach or start the server; print one status line")
    e.add_argument("--version", default=None)
    e.add_argument("--session", default="")
    e.add_argument("--project-root", default=None)
    e.add_argument("--grace", type=_positive, default=None)
    e.add_argument("--deadline", type=_positive, default=ENSURE_DEADLINE)
    e.set_defaults(func=_cmd_ensure)

    q = sub.add_parser("path", help="print the socket path for this tmux server and version")
    q.add_argument("--version", default=None)
    q.set_defaults(func=_cmd_path)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
