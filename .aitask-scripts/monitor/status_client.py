"""status_client - ``MonitorClient``, the subscription-backed ``TmuxMonitor`` stand-in.

``ait monitor``, ``ait minimonitor`` and applink each read a ``TmuxMonitor``. A
``MonitorClient`` wraps the ``TmuxMonitor`` the app already builds (its *local*
instance) and offers the same read surface, served from ONE of three places:

- **server** — the shared status server (``status_server.py``) for this tmux
  server and framework ``VERSION``. Producer state (snapshots, shadows, the
  session map, compare modes, discovery facts) comes from the subscription
  (``status_protocol.StreamState``); the local instance does no scan and runs no
  control client and is only the action gateway (send-keys, kill, ``tmux_run``,
  raw-tail captures), its pane cache seeded from the subscription.
- **fallback** — the server cannot be reached or started (or
  ``AITASKS_MONITOR_SERVER=0``): every call goes to the local instance, which is
  exactly the in-process code. A reconnect loop keeps trying the server and
  switches back when it answers.
- **replay** — a recorded stream (``status_recording.ReplayServer`` on a
  temporary socket). Read-only: actions refuse, nothing reaches a real tmux.

The client returns producer-equivalent, **unprojected** snapshot dicts: the own
pane, the ``M`` session filter and parked placeholders stay the app's job
(``client_view_snapshots``, ``AgentMarksMixin._project_snapshots``).

Specification: ``aidocs/framework/monitor_status_protocol.md`` ("Python client").
Headless: no Textual import. Logging only through the injected ``log`` callable —
the client lives inside Textual apps, where stderr would garble the screen.
"""
from __future__ import annotations

import asyncio
import contextlib
import enum
import itertools
import os
import re
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
for _extra in (_SCRIPTS_DIR / "lib", _SCRIPTS_DIR):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

try:  # imported as part of the `monitor` package
    from . import status_protocol as sp
    from . import status_recording as sr
    from . import status_server as ss
    from .monitor_core import (
        CAPTURE_PIN_ALL,
        COMPARE_MODE_RAW,
        COMPARE_MODE_STRIPPED,
        DEFAULT_COMPARE_MODE,
        TmuxControlState,
    )
except ImportError:  # imported top-level (script run / MONITOR_DIR on sys.path)
    import status_protocol as sp  # noqa: E402
    import status_recording as sr  # noqa: E402
    import status_server as ss  # noqa: E402
    from monitor_core import (  # noqa: E402
        CAPTURE_PIN_ALL,
        COMPARE_MODE_RAW,
        COMPARE_MODE_STRIPPED,
        DEFAULT_COMPARE_MODE,
        TmuxControlState,
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Opt-out: ``AITASKS_MONITOR_SERVER=0`` keeps the client in fallback forever.
ENV_SWITCH = "AITASKS_MONITOR_SERVER"

DEFAULT_CONNECT_DEADLINE = 3.0
DEFAULT_REQUEST_TIMEOUT = 10.0
DEFAULT_PING_AFTER = 10.0
DEFAULT_PING_TIMEOUT = 10.0
DEFAULT_RESYNC_TIMEOUT = 10.0
#: How long ``close()`` waits for a local control-client start to retire its
#: backend (``TmuxMonitor.start_control_client`` worst case is ~14 s).
DEFAULT_CONTROL_DRAIN_TIMEOUT = 15.0
#: How long entering a subscribed mode waits for in-flight local captures.
DEFAULT_LOCAL_DRAIN_TIMEOUT = 5.0
#: Reconnect delays in seconds; the last entry repeats.
DEFAULT_BACKOFF = (0.0, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 30.0)

#: ``sun_path`` headroom for the replay socket's temporary directory.
_MAX_TMP_DIR_CHARS = 80
_PANE_ID_RE = re.compile(r"%[0-9]{1,10}")

#: Names delegated to the local ``TmuxMonitor`` in every mode but replay: the
#: action and tmux gateway, the raw-tail capture paths (which stay client-side,
#: t2037_3), and the instance config. Everything else the apps read is served
#: from the subscription (``READ_SURFACE_NAMES``) or raises in server mode.
#: ``tests/test_monitor_client_surface.py`` pins this list against the apps.
GATEWAY_NAMES = frozenset({
    "tmux_run", "tmux_run_async",
    "send_keys", "send_enter", "forward_key",
    "switch_to_pane", "find_companion_pane_id",
    "kill_pane", "kill_window", "kill_agent_pane_smart", "kill_agent_run_guarded",
    "spawn_tui", "get_running_tuis", "get_missing_tuis",
    "resize_pane", "get_pane_option", "get_pane_option_sync",
    "capture_pane", "capture_pane_async", "capture_pane_content_async",
    "capture_cursor_async",
    "discover_window_panes", "discover_window_panes_async",
    "invalidate_sessions_cache", "_run_offloaded",
    "session", "capture_lines", "idle_threshold", "agent_prefixes", "tui_names",
    "compare_mode_default", "prompt_patterns",
})

#: The producer read surface ``MonitorClient`` defines itself: served from the
#: subscription in server and replay mode, delegated in fallback.
READ_SURFACE_NAMES = frozenset({
    "capture_all_async", "capture_all_classified_async", "capture_generation",
    "commit_snapshots", "capture_pane_classified_async", "commit_snapshot",
    "refresh_shadow_snapshot", "get_shadow_snapshot", "shadow_snapshots",
    "get_pane", "discover_panes",
    "get_session_to_project_mapping", "get_session_to_project_mapping_async",
    "get_compare_mode", "is_compare_mode_overridden", "get_last_change_wall",
    "set_compare_mode", "cycle_compare_mode", "control_state",
    "last_enumerated_sessions", "last_discovered_agents", "last_discovered_panes",
    "set_parked_agents", "start_control_client", "close_control_client",
})


class ClientMode(enum.Enum):
    CONNECTING = "connecting"
    SERVER = "server"
    FALLBACK = "fallback"
    REPLAY = "replay"


_SUBSCRIBED = (ClientMode.SERVER, ClientMode.REPLAY)


class ConnectionLost(Exception):
    """The connection a request was waiting on is gone."""


class RequestFailed(Exception):
    """The server answered a request with an ``error``."""

    def __init__(self, code: str, message: str = ""):
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code


class ReplayReadOnly(AttributeError):
    """Replay mode never acts: fixture pane ids must not reach a real tmux.

    An ``AttributeError`` so ``getattr(client, name, None)`` probes still fall
    back to their default."""


def pins_to_wire(pins):
    """``CAPTURE_PIN_ALL`` → ``"all"``; a set of ``(session, window)`` → sorted pairs."""
    if pins is CAPTURE_PIN_ALL:
        return sp.PINS_ALL
    return sorted([str(s), str(w)] for s, w in pins)


def _normalize_pins(pins):
    if pins is CAPTURE_PIN_ALL:
        return pins
    return frozenset((str(s), str(w)) for s, w in (pins or ()))


def _short_tmp_dir() -> str | None:
    base = tempfile.gettempdir()
    return base if len(base) <= _MAX_TMP_DIR_CHARS else "/tmp"


@dataclass
class _Pending:
    """The opaque middle of the two-phase capture API (``content`` / ``classified``).

    The apps pass it from ``capture_*_classified_async`` back into
    ``commit_snapshot[s]`` untouched; the client routes the commit by ``mode``."""
    mode: ClientMode
    inner_gen: int | None = None
    inner: object = None
    snaps: object = None


# ---------------------------------------------------------------------------
# One connection
# ---------------------------------------------------------------------------

class _Link:
    """One connection: a reader the client's reader task drains, a writer
    serialized by a lock, and the pending-request map keyed by integer id.

    Every request carries an ``id``. The reader resolves the future on a
    ``result``, an ``error`` **or** a ``snapshot`` carrying that id — the replies
    to ``subscribe`` and ``set_content`` are snapshots."""

    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.pending: dict[int, asyncio.Future] = {}
        self._ids = itertools.count(1)
        self._wlock = asyncio.Lock()
        self.reader_task: asyncio.Task | None = None
        self.ping_task: asyncio.Task | None = None
        self.resync_task: asyncio.Task | None = None

    async def send(self, msg: dict) -> None:
        raw = sp.encode(msg, direction=sp.CLIENT)
        async with self._wlock:
            self.writer.write(raw)
            await self.writer.drain()

    async def request(self, msg: dict, timeout: float) -> dict:
        """Send ``msg`` with a fresh id and return its reply message.

        ONE deadline covers the whole exchange — the write lock, the write, the
        ``drain()`` (which blocks under socket backpressure) and the reply — so a
        stuck send reaches the caller's failure handling like a missing reply.
        Raises ``asyncio.TimeoutError`` past ``timeout``, :class:`ConnectionLost`
        when the link drops first. An ``error`` reply is returned, not raised."""
        rid = next(self._ids)
        fut = asyncio.get_running_loop().create_future()
        self.pending[rid] = fut

        async def exchange() -> dict:
            try:
                await self.send({**msg, "id": rid})
            except (OSError, ConnectionError) as exc:
                raise ConnectionLost(f"send failed: {exc!r}") from None
            return await fut

        try:
            return await asyncio.wait_for(exchange(), timeout)
        finally:
            self.pending.pop(rid, None)

    def resolve(self, msg: dict) -> None:
        fut = self.pending.get(msg.get("id"))
        if fut is not None and not fut.done():
            fut.set_result(msg)

    def fail_all(self, exc: Exception) -> None:
        for fut in list(self.pending.values()):
            if not fut.done():
                fut.set_exception(exc)
                # Retrieved by the awaiting request; marking it avoids a
                # "never retrieved" warning when nobody awaits any more.
                fut.exception()

    def close_now(self) -> None:
        """Synchronous half of :meth:`close` — safe in a ``finally`` that runs
        during cancellation."""
        with contextlib.suppress(Exception):
            self.writer.close()

    async def close(self) -> None:
        self.close_now()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(self.writer.wait_closed(), 2.0)


# ---------------------------------------------------------------------------
# The client
# ---------------------------------------------------------------------------

class MonitorClient:
    """A ``TmuxMonitor`` stand-in served by the shared status server.

    See the module docstring for the three modes. Construction does nothing;
    :meth:`start` (also reachable as ``start_control_client``, the call the apps
    already make) runs the first attempt. Async read methods start the client on
    first use and wait for that attempt, so a first refresh never reads an empty
    state."""

    def __init__(
        self, local, *, kind: str, own_pane: str | None = None, session: str = "",
        project_root=None, content=sp.CONTENT_ALL, include_shadows: bool = True,
        pins=frozenset(), version: str | None = None, ensure=None, replay=None,
        replay_speed: float = 1.0, enabled: bool | None = None, log=None,
        connect_deadline: float = DEFAULT_CONNECT_DEADLINE,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
        ping_after: float = DEFAULT_PING_AFTER,
        ping_timeout: float = DEFAULT_PING_TIMEOUT,
        resync_timeout: float = DEFAULT_RESYNC_TIMEOUT,
        backoff=DEFAULT_BACKOFF,
        control_drain_timeout: float = DEFAULT_CONTROL_DRAIN_TIMEOUT,
        local_drain_timeout: float = DEFAULT_LOCAL_DRAIN_TIMEOUT,
    ):
        if local is None and replay is None:
            raise ValueError("MonitorClient needs a local TmuxMonitor unless it replays")
        self._mode = ClientMode.CONNECTING
        self._local = local
        self._kind = kind
        self._own_pane = own_pane
        self._session = session
        self._project_root = project_root
        self._content = content
        self._include_shadows = include_shadows
        self._pins = _normalize_pins(pins)
        self._version = version or ss.framework_version()
        self._ensure = ensure or ss.ensure_server
        self._replay = replay
        self._replay_speed = replay_speed
        if enabled is None:
            enabled = os.environ.get(ENV_SWITCH, "1").strip() != "0"
        self._enabled = enabled
        self._log_cb = log
        self._connect_deadline = connect_deadline
        self._request_timeout = request_timeout
        self._ping_after = ping_after
        self._ping_timeout = ping_timeout
        self._resync_timeout = resync_timeout
        self._backoff = tuple(backoff) or (0.0,)
        self._control_drain_timeout = control_drain_timeout
        self._local_drain_timeout = local_drain_timeout

        self._state: sp.StreamState | None = None
        self._link: _Link | None = None
        self._started = False
        self._closed = False
        self._ready = asyncio.Event()
        self._gen = 0
        self._resyncing = False
        self._last_msg = time.monotonic()
        self._snap_cache: dict | None = None
        self._shadow_cache: dict | None = None
        self._record_index: dict | None = None
        self._local_control_on = False
        #: Every local ``start_control_client`` still running. NEVER cancelled:
        #: cancelling one while it awaits ``to_thread(backend.start)`` abandons
        #: the stale-generation ``backend.stop`` that would retire the backend
        #: its worker thread goes on to start. ``close_control_client`` bumps
        #: the generation instead, and each start retires its own backend.
        self._control_starts: set = set()
        #: In-flight local (fallback) producer operations — their discovery
        #: writes the local pane cache, so a subscribed mode takes the cache
        #: only once they drained (``_local_ops`` / ``_local_idle``).
        self._local_ops = 0
        self._local_idle = asyncio.Event()
        self._local_idle.set()
        #: Links between ``open_unix_connection`` and adoption as ``_link``.
        self._connecting: set = set()
        #: A subscribed mode is being entered: new local captures are refused.
        self._switch_pending = False
        self._start_task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._bg: set = set()
        #: The last ``set_pins`` send (see :meth:`flush_pins`).
        self._pins_send: asyncio.Task | None = None
        self._update_listeners: list = []
        self._mode_listeners: list = []
        self._replay_server = None
        self._replay_dir: str | None = None
        #: The last welcome's ``server`` member, plus ``replay`` when a replayer answered.
        self.server_info: dict | None = None
        #: Why the client is not (or no longer) subscribed; ``""`` when it is.
        self.last_error = ""

    # -- public state --------------------------------------------------------

    @property
    def mode(self) -> ClientMode:
        return self._mode

    @property
    def connected(self) -> bool:
        """Subscribed right now (server or replay mode with a live link)."""
        return self._mode in _SUBSCRIBED and self._link is not None

    def add_update_listener(self, callback) -> None:
        """``callback(Applied)`` after every snapshot or delta applied in a
        subscribed mode — lets an app render on push instead of on a timer."""
        self._update_listeners.append(callback)

    def add_mode_listener(self, callback) -> None:
        """``callback(ClientMode)`` on every mode change (and on a replay
        disconnect, with the mode unchanged)."""
        self._mode_listeners.append(callback)

    # -- lifecycle -----------------------------------------------------------

    async def start(self) -> bool:
        """Run the first attempt: replay, server, or fallback. Returns True once
        it resolved either way (the ``start_control_client`` contract)."""
        if self._started:
            await self._ready.wait()
            return True
        self._started = True
        # An owned task, so close() can cancel and drain connection setup too.
        # Cancelling this caller cancels the task with it (awaiting a task
        # propagates cancellation), and _connect's cleanup closes its socket.
        self._start_task = asyncio.create_task(self._start_body())
        try:
            await self._start_task
        except asyncio.CancelledError:
            # close() cancelled the start: not this caller's cancellation.
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise
        return True

    async def _start_body(self) -> None:
        try:
            if self._replay is not None:
                await self._start_replay()
            elif not self._enabled:
                self._enter_fallback(f"disabled by {ENV_SWITCH}=0", reconnect=False)
            elif not await self._attempt() and not self._closed:
                self._enter_fallback(self.last_error, reconnect=True)
        finally:
            self._ready.set()

    async def start_control_client(self) -> bool:
        """Alias of :meth:`start` — the call the apps make at mount."""
        return await self.start()

    async def close(self) -> None:
        """Stop everything; idempotent. Releases the seeded pane cache and
        closes the local control client."""
        if self._closed:
            return
        self._closed = True
        current = asyncio.current_task()
        link = self._link
        self._link = None
        # Connection setup first: a socket still in its handshake is not yet
        # `_link`, and closing it unblocks the handshake read.
        for pending in list(self._connecting):
            pending.close_now()
        tasks = [self._start_task, self._reconnect_task, *self._bg]
        if link is not None:
            tasks += [link.reader_task, link.ping_task, link.resync_task]
            link.fail_all(ConnectionLost("client closed"))
        tasks = [t for t in tasks if t is not None and t is not current and not t.done()]
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        if link is not None:
            await link.close()
        if self._mode in _SUBSCRIBED:
            self._release_cache()
        if self._replay_server is not None:
            with contextlib.suppress(Exception):
                await self._replay_server.close()
            self._replay_server = None
        if self._replay_dir is not None:
            shutil.rmtree(self._replay_dir, ignore_errors=True)
            self._replay_dir = None
        if self._local is not None:
            self._local_control_on = False
            with contextlib.suppress(Exception):
                await self._local.close_control_client()
            # Let every in-flight start see the bumped generation and retire its
            # own backend; shielded, so a bounded wait never cancels one.
            starts = [t for t in self._control_starts if not t.done()]
            if starts:
                with contextlib.suppress(asyncio.TimeoutError, Exception):
                    await asyncio.wait_for(asyncio.shield(asyncio.gather(
                        *starts, return_exceptions=True)), self._control_drain_timeout)
        self._ready.set()

    async def close_control_client(self) -> None:
        """Alias of :meth:`close` — the call the apps make at unmount."""
        await self.close()

    # -- attempts and the connection -----------------------------------------

    async def _attempt(self) -> bool:
        try:
            res = await asyncio.to_thread(
                self._ensure, version=self._version, session=self._session,
                project_root=self._project_root, deadline=self._connect_deadline)
        except Exception as exc:  # noqa: BLE001 - an injected ensure may raise
            self.last_error = f"ensure failed: {exc!r}"
            return False
        if self._closed:
            return False
        if res.state == "UNAVAILABLE":
            self.last_error = f"unavailable:{res.reason}"
            return False
        return await self._connect(res.socket, ClientMode.SERVER)

    def _hello(self) -> dict:
        client = {"kind": self._kind, "pid": os.getpid()}
        if self._own_pane and _PANE_ID_RE.fullmatch(self._own_pane):
            client["pane"] = self._own_pane
        return {"type": "hello", "proto": sp.PROTO, "version": self._version,
                "client": client}

    def _subscribe_msg(self) -> dict:
        return {"type": "subscribe", "content": self._content,
                "include_shadows": self._include_shadows,
                "pins": pins_to_wire(self._pins)}

    async def _connect(self, socket_path, mode: ClientMode) -> bool:
        """Handshake inline, then start the reader and subscribe through it."""
        timeout = self._request_timeout
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(str(socket_path),
                                             limit=sp.MAX_SERVER_LINE_BYTES),
                timeout)
        except (OSError, asyncio.TimeoutError, ValueError) as exc:
            self.last_error = f"connect failed: {exc!r}"
            return False
        link = _Link(reader, writer)
        self._connecting.add(link)
        adopted = False
        try:
            adopted = await self._handshake_and_subscribe(link, mode, timeout)
            return adopted
        finally:
            self._connecting.discard(link)
            if not adopted:
                # Every exit that did not adopt the link — a failure, close(),
                # or a cancelled start — closes its socket, synchronously first.
                if self._link is link:
                    self._link = None
                for task in (link.reader_task, link.ping_task, link.resync_task):
                    if task is not None and task is not asyncio.current_task():
                        task.cancel()
                link.close_now()

    async def _handshake_and_subscribe(self, link: _Link, mode: ClientMode,
                                       timeout: float) -> bool:
        reader = link.reader
        try:
            await link.send(self._hello())
            line = await asyncio.wait_for(sp.read_line(reader), timeout)
            if line is None:
                raise ConnectionLost("closed during the handshake")
            welcome = sp.decode(line, direction=sp.SERVER)
            if welcome["type"] == "error":
                raise RequestFailed(welcome["code"], welcome["message"])
            if welcome["type"] != "welcome":
                raise sp.ProtocolError(f"expected welcome, got {welcome['type']!r}")
            if welcome["proto"] != sp.PROTO:
                raise RequestFailed("proto_mismatch", f"server proto {welcome['proto']}")
            if "replay" not in welcome and welcome["version"] != self._version:
                raise RequestFailed("version_mismatch",
                                    f"server version {welcome['version']!r}")
        except (OSError, ConnectionError, asyncio.TimeoutError, ConnectionLost,
                RequestFailed, sp.ProtocolError) as exc:
            self.last_error = f"handshake failed: {exc}"
            return False
        if self._closed:
            return False

        info = dict(welcome["server"])
        if "replay" in welcome:
            info["replay"] = dict(welcome["replay"])
        self._link = link
        self._state = sp.StreamState()
        self._resyncing = False
        self._last_msg = time.monotonic()
        link.reader_task = asyncio.create_task(self._reader_loop(link))
        try:
            reply = await link.request(self._subscribe_msg(), timeout)
        except ConnectionLost as exc:
            self.last_error = f"subscribe failed: {exc}"
            return False   # the reader's loss handling already ran
        except asyncio.TimeoutError:
            await self._drop(link, "subscribe timed out")
            return False
        if reply["type"] != "snapshot":
            await self._drop(link, f"subscribe failed: {reply.get('code')}")
            return False
        if self._link is not link:
            return False
        # Ownership invariant: a subscribed mode never coexists with an
        # in-flight local capture (its discovery writes the local pane cache).
        # New local captures are refused while the switch is pending; the ones
        # already running must drain, or the attach is abandoned.
        self._switch_pending = True
        try:
            drained = await self._drain_local_ops()
            if self._link is not link or self._closed:
                return False
            if not drained:
                await self._drop(link, "local capture did not drain")
                return False
            self.server_info = info
            self.last_error = ""
            # Synchronous from here to the seed: no await between them.
            self._switch_subscribed(mode)
        finally:
            self._switch_pending = False
        link.ping_task = asyncio.create_task(self._ping_loop(link))
        await self._retire_local_control()
        # The link may have been lost during that await: report what is true now,
        # so a reconnect loop keeps retrying instead of exiting on a stale success.
        return self._link is link and self._mode is mode

    async def _drop(self, link: _Link, reason: str) -> None:
        """Close a link that never became the subscribed one, without the
        fallback transition (the caller decides what happens next)."""
        if self._link is link:
            self._link = None
        self.last_error = reason
        link.fail_all(ConnectionLost(reason))
        for task in (link.reader_task, link.ping_task, link.resync_task):
            if task is not None and task is not asyncio.current_task():
                task.cancel()
        await link.close()

    async def _reader_loop(self, link: _Link) -> None:
        reason = "server closed the connection"
        try:
            while True:
                line = await sp.read_line(link.reader)
                if line is None:
                    break
                self._last_msg = time.monotonic()
                try:
                    msg = sp.decode(line, direction=sp.SERVER)
                except sp.UnknownMessageType:
                    continue   # a server type this client does not know: ignored
                kind = msg["type"]
                if kind in ("result", "error"):
                    link.resolve(msg)
                elif kind == "snapshot":
                    # Applied FIRST, then the request resolved: the caller of
                    # subscribe / set_content returns with the state current.
                    applied = self._state.apply(msg)
                    self._resyncing = False
                    self._on_applied(link, applied)
                    link.resolve(msg)
                elif kind == "delta":
                    if self._resyncing:
                        continue   # ordered before the coming reply snapshot
                    try:
                        applied = self._state.apply(msg)
                    except sp.StreamGap:
                        self._begin_resync(link)
                        continue
                    if applied is not None:
                        self._on_applied(link, applied)
                # a stray welcome is ignored
        except asyncio.CancelledError:
            raise
        except sp.FramingError as exc:
            reason = f"framing error: {exc}"
        except sp.ProtocolError as exc:
            reason = f"protocol violation: {exc}"
        except (OSError, ConnectionError) as exc:
            reason = f"read failed: {exc!r}"
        except Exception as exc:  # noqa: BLE001 - never let the reader die silently
            reason = f"reader failed: {exc!r}"
        await self._lost(link, reason)

    def _begin_resync(self, link: _Link) -> None:
        """A gap: resubscribe as an ordinary bounded request, OUTSIDE the reader
        (which must stay free to read the reply)."""
        self._resyncing = True
        if link.resync_task is None or link.resync_task.done():
            link.resync_task = asyncio.create_task(self._resync(link))

    async def _resync(self, link: _Link) -> None:
        """Resubscribe until no gap is pending. The reply snapshot clears
        ``_resyncing`` in the reader before this task resumes, so a gap that
        arrived right behind it found this task still running and started none:
        looping while the flag is set again means every paused state owns a live,
        bounded request."""
        while self._link is link:
            try:
                reply = await link.request(self._subscribe_msg(), self._resync_timeout)
            except ConnectionLost:
                return
            except asyncio.TimeoutError:
                await self._lost(link, "resync timed out")
                return
            if reply["type"] != "snapshot":
                await self._lost(link, f"resync failed: {reply.get('code')}")
                return
            if not self._resyncing:
                return

    async def _ping_loop(self, link: _Link) -> None:
        """After ``ping_after`` s of silence, ping with an idempotent ``set_pins``;
        no reply within ``ping_timeout`` means the server is hung."""
        while self._link is link:
            idle = time.monotonic() - self._last_msg
            if idle < self._ping_after:
                await asyncio.sleep(self._ping_after - idle)
                continue
            try:
                await link.request({"type": "set_pins", "pins": pins_to_wire(self._pins)},
                                   self._ping_timeout)
            except ConnectionLost:
                return
            except asyncio.TimeoutError:
                await self._lost(link, "liveness ping timed out")
                return

    async def _lost(self, link: _Link, reason: str) -> None:
        """The established loss handling. Idempotent per link."""
        if link is not self._link or self._closed:
            return
        self._link = None
        self.last_error = reason
        self._log(f"monitor status server connection lost: {reason}")
        link.fail_all(ConnectionLost(reason))
        current = asyncio.current_task()
        for task in (link.reader_task, link.ping_task, link.resync_task):
            if task is not None and task is not current:
                task.cancel()
        await link.close()
        if self._mode is ClientMode.REPLAY:
            # No fallback for a replay: keep the last state, say it stopped.
            self._notify_mode()
            return
        # Release ONLY a subscription-owned cache. A reconnect lost while still
        # in FALLBACK (e.g. waiting for local captures to drain) never seeded
        # it: the cache then holds the fallback producer's valid discovery.
        if self._mode is ClientMode.SERVER:
            # Only seeded entries; release them before any fallback discovery
            # (``_clean_stale`` never reaps a seeded pane).
            self._release_cache()
        self._state = None
        self._enter_fallback(reason, reconnect=True)

    # -- modes ---------------------------------------------------------------

    def _set_mode(self, mode: ClientMode) -> None:
        self._gen += 1
        self._invalidate()
        if mode is self._mode:
            return
        self._mode = mode
        self._notify_mode()

    def _switch_subscribed(self, mode: ClientMode) -> None:
        """Mode and seed, synchronously (callers rely on no await in between)."""
        self._set_mode(mode)
        self._seed_cache()

    async def _retire_local_control(self) -> None:
        if self._local_control_on and self._local is not None:
            self._local_control_on = False
            # Never cancel an in-flight start (see `_control_starts`): bumping the
            # generation makes it retire its own backend when it finishes.
            with contextlib.suppress(Exception):
                await self._local.close_control_client()

    def _enter_fallback(self, reason: str, *, reconnect: bool) -> None:
        self.last_error = reason
        self._set_mode(ClientMode.FALLBACK)
        self._start_local_control()
        if reconnect:
            self._ensure_reconnect()

    def _start_local_control(self) -> None:
        if self._local is None or self._local_control_on or self._closed:
            return
        self._local_control_on = True

        async def _run():
            try:
                ok = await self._local.start_control_client()
                if not ok:
                    self._log("tmux control mode unavailable; using subprocess fallback")
            except Exception as exc:  # noqa: BLE001
                self._log(f"tmux control mode init failed: {exc!r}")

        task = asyncio.create_task(_run())
        self._control_starts.add(task)
        task.add_done_callback(self._control_starts.discard)

    # -- local (fallback) producer operations ----------------------------------

    @contextlib.asynccontextmanager
    async def _local_op(self):
        """Mark one local producer operation in flight. Its discovery writes the
        local pane cache, which a subscribed mode owns — so a switch drains these
        first (`_drain_local_ops`) and refuses new ones (`_switch_pending`)."""
        self._local_ops += 1
        self._local_idle.clear()
        try:
            yield
        finally:
            self._local_ops -= 1
            if self._local_ops == 0:
                self._local_idle.set()

    async def _drain_local_ops(self) -> bool:
        """True once no local capture is in flight; False past the deadline."""
        if self._local_ops == 0:
            return True
        try:
            await asyncio.wait_for(self._local_idle.wait(), self._local_drain_timeout)
        except asyncio.TimeoutError:
            return False
        return True

    def _ensure_reconnect(self) -> None:
        if self._closed or not self._enabled or self._replay is not None:
            return
        if self._reconnect_task is not None and not self._reconnect_task.done():
            return
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        attempt = 0
        while not self._closed and self._mode is ClientMode.FALLBACK:
            delay = self._backoff[min(attempt, len(self._backoff) - 1)]
            if delay:
                await asyncio.sleep(delay)
            attempt += 1
            if self._closed or self._mode is not ClientMode.FALLBACK:
                return
            if await self._attempt() and self._mode is not ClientMode.FALLBACK:
                self._log("monitor status server connected")
                return

    async def _start_replay(self) -> None:
        self._mode = ClientMode.REPLAY
        try:
            self._replay_dir = tempfile.mkdtemp(prefix="ait-replay-", dir=_short_tmp_dir())
            sock = os.path.join(self._replay_dir, "r.sock")
            server = sr.ReplayServer(self._replay, sock, speed=self._replay_speed)
            await server.start()
            self._replay_server = server
        except Exception as exc:  # noqa: BLE001 - a bad recording is reported, not raised
            self.last_error = f"replay failed to start: {exc}"
            self._notify_mode()
            return
        if not await self._connect(sock, ClientMode.REPLAY):
            self._notify_mode()

    # -- after each applied message -------------------------------------------

    def _on_applied(self, link: _Link, applied) -> None:
        if link is not self._link or applied is None:
            return
        self._gen += 1
        self._invalidate()
        if self._mode not in _SUBSCRIBED:
            return   # the first snapshot of a (re)connect: seeded on entering
        self._seed_cache()
        for callback in list(self._update_listeners):
            try:
                callback(applied)
            except Exception as exc:  # noqa: BLE001
                self._log(f"update listener failed: {exc!r}")

    def _notify_mode(self) -> None:
        for callback in list(self._mode_listeners):
            try:
                callback(self._mode)
            except Exception as exc:  # noqa: BLE001
                self._log(f"mode listener failed: {exc!r}")

    def _invalidate(self) -> None:
        self._snap_cache = None
        self._shadow_cache = None
        self._record_index = None

    def _seed_cache(self) -> None:
        seed = getattr(self._local, "seed_pane_cache", None)
        if seed is None or not self._serving():
            return
        seed({pid: snap.pane for pid, snap in self._snapshots_view().items()})

    def _release_cache(self) -> None:
        seed = getattr(self._local, "seed_pane_cache", None)
        if seed is not None:
            seed({})

    def _log(self, message: str) -> None:
        if self._log_cb is not None:
            with contextlib.suppress(Exception):
                self._log_cb(message)

    def _spawn(self, coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._bg.add(task)
        task.add_done_callback(self._bg.discard)
        return task

    # -- state views ---------------------------------------------------------

    def _serving(self) -> bool:
        return (self._mode in _SUBSCRIBED and self._state is not None
                and self._state.subscribed)

    def _snapshots_view(self) -> dict:
        if self._snap_cache is None:
            self._snap_cache = self._state.snapshots()
        return self._snap_cache

    def _shadows_view(self) -> dict:
        if self._shadow_cache is None:
            self._shadow_cache = self._state.shadow_snapshots()
        return self._shadow_cache

    def _record_for(self, pane_id: str) -> dict | None:
        """A pane's record (or a shadow's, by its own pane id) through an index
        built once per applied generation — renderers query this per pane."""
        if self._record_index is None:
            index = {}
            for shadow in self._state.shadow_records().values():
                index.setdefault(shadow["pane"]["pane_id"], shadow)
            index.update(self._state.records())   # an agent pane wins over a shadow
            self._record_index = index
        return self._record_index.get(pane_id)

    async def _await_ready(self) -> None:
        if not self._started:
            await self.start()
        elif not self._ready.is_set():
            await self._ready.wait()

    def _default_compare_mode(self) -> str:
        if self._local is not None:
            return getattr(self._local, "compare_mode_default", DEFAULT_COMPARE_MODE)
        return DEFAULT_COMPARE_MODE

    # -- the two-phase capture API --------------------------------------------

    @property
    def capture_generation(self) -> int:
        """The client's own generation token: bumped by every capture call, every
        applied message and every mode switch. A payload whose token is no longer
        current commits ``None`` — the "superseded, skip" contract the apps
        already honour."""
        return self._gen

    async def capture_all_classified_async(self):
        await self._await_ready()
        if self._serving():
            self._gen += 1
            return self._gen, _Pending(ClientMode.SERVER, snaps=dict(self._snapshots_view()))
        if self._mode in _SUBSCRIBED:   # replay that never subscribed
            self._gen += 1
            return self._gen, _Pending(ClientMode.SERVER, snaps={})
        self._gen += 1
        token = self._gen
        if self._switch_pending:
            return token, None          # superseded: commits None
        async with self._local_op():
            inner_gen, classified = await self._local.capture_all_classified_async()
        return token, _Pending(ClientMode.FALLBACK, inner_gen=inner_gen, inner=classified)

    def commit_snapshots(self, gen, classified):
        if gen != self._gen or not isinstance(classified, _Pending):
            return None
        if classified.mode is ClientMode.FALLBACK:
            return self._local.commit_snapshots(classified.inner_gen, classified.inner)
        return classified.snaps

    async def capture_all_async(self):
        """All snapshots. In a subscribed mode this READS the current state — it
        never asks the server to scan (that is :meth:`request_refresh`)."""
        await self._await_ready()
        if self._mode in _SUBSCRIBED:
            token, payload = await self.capture_all_classified_async()
            return self.commit_snapshots(token, payload)
        self._gen += 1
        token = self._gen
        if self._switch_pending:
            return None                 # superseded
        async with self._local_op():
            snaps = await self._local.capture_all_async()
        return snaps if token == self._gen else None

    async def capture_pane_classified_async(self, pane_id: str, capture_lines=None):
        """The fast preview path. Subscribed: ``refresh{panes:[id]}``, then the
        refreshed record (results follow their delta). ``pane`` is ``None`` when
        the record is gone or the request failed."""
        await self._await_ready()
        if self._mode not in _SUBSCRIBED:
            self._gen += 1
            token = self._gen
            if self._switch_pending:
                return token, None, None, None
            async with self._local_op():
                inner_gen, pane, content, result = \
                    await self._local.capture_pane_classified_async(pane_id, capture_lines)
            return token, pane, _Pending(ClientMode.FALLBACK, inner_gen=inner_gen,
                                         inner=content), result
        reply = await self._quiet_request({"type": "refresh", "panes": [pane_id]})
        self._gen += 1
        token = self._gen
        if reply is None or reply["type"] != "result" or not self._serving():
            return token, None, None, None
        snap = self._snapshots_view().get(pane_id)
        if snap is None:
            return token, None, None, None
        return token, snap.pane, _Pending(ClientMode.SERVER, snaps=snap), None

    def commit_snapshot(self, gen, pane, content, result):
        if gen != self._gen or not isinstance(content, _Pending):
            return None
        if content.mode is ClientMode.FALLBACK:
            return self._local.commit_snapshot(content.inner_gen, pane, content.inner, result)
        return content.snaps

    async def refresh_shadow_snapshot(self, followed_pane_id: str):
        await self._await_ready()
        if self._mode not in _SUBSCRIBED:
            if self._switch_pending:
                return None
            async with self._local_op():
                return await self._local.refresh_shadow_snapshot(followed_pane_id)
        reply = await self._quiet_request({"type": "refresh", "shadows": [followed_pane_id]})
        if reply is None or reply["type"] != "result":
            return None
        return self.get_shadow_snapshot(followed_pane_id)

    async def request_refresh(self, panes=None, shadows=None) -> int | None:
        """Ask the server to scan now (the keypress refresh sites); returns the
        generation that carries the effects. ``None`` in fallback (the app's own
        next capture scans in-process anyway) or on failure."""
        await self._await_ready()
        if self._mode not in _SUBSCRIBED:
            return None
        msg: dict = {"type": "refresh"}
        if panes:
            msg["panes"] = list(panes)
        if shadows:
            msg["shadows"] = list(shadows)
        reply = await self._quiet_request(msg)
        if reply is None or reply["type"] != "result":
            return None
        return reply["gen"]

    async def capture(self, pane_id: str, lines: int) -> str | None:
        """A raw one-off read of the pane's last ``lines`` lines — the wire
        ``capture`` in a subscribed mode, the local capture in fallback."""
        await self._await_ready()
        if self._mode in _SUBSCRIBED:
            reply = await self._quiet_request({"type": "capture", "pane": pane_id,
                                               "lines": lines})
            if reply is None or reply["type"] != "result":
                return None
            return reply["content"]
        got = await self._local.capture_pane_content_async(pane_id, capture_lines=lines)
        if got is None:
            return None
        return sp.tail_lines(got[1], lines)

    async def _quiet_request(self, msg: dict) -> dict | None:
        """A request whose failure is answered by ``None``, never raised. A
        missing reply is the liveness ping's business, not this caller's."""
        link = self._link
        if link is None:
            return None
        try:
            return await link.request(msg, self._request_timeout)
        except (ConnectionLost, asyncio.TimeoutError):
            return None

    # -- sync read surface ----------------------------------------------------

    def get_shadow_snapshot(self, followed_pane_id: str):
        if self._serving():
            return self._shadows_view().get(followed_pane_id)
        if self._mode in _SUBSCRIBED:
            return None
        return self._local.get_shadow_snapshot(followed_pane_id)

    def shadow_snapshots(self) -> dict:
        if self._serving():
            return dict(self._shadows_view())
        if self._mode in _SUBSCRIBED:
            return {}
        return self._local.shadow_snapshots()

    def get_pane(self, pane_id: str):
        """Agent-facing pane info, never a shadow (cache-boundary invariant)."""
        if self._serving():
            snap = self._snapshots_view().get(pane_id)
            return snap.pane if snap is not None else None
        if self._mode in _SUBSCRIBED:
            return None
        return self._local.get_pane(pane_id)

    def discover_panes(self) -> list:
        """The agent-facing panes. Subscribed: the panes of the current state
        (applink's empty-subscribe expansion); fallback: a live discovery."""
        if self._serving():
            return [snap.pane for snap in self._snapshots_view().values()]
        if self._mode in _SUBSCRIBED:
            return []
        return self._local.discover_panes()

    def get_session_to_project_mapping(self) -> dict:
        if self._serving():
            return {s: Path(r) for s, r in self._state.session_roots().items()}
        if self._mode in _SUBSCRIBED:
            return {}
        return self._local.get_session_to_project_mapping()

    async def get_session_to_project_mapping_async(self) -> dict:
        await self._await_ready()
        if self._mode in _SUBSCRIBED:
            return self.get_session_to_project_mapping()
        # Not a local op: it reads the sessions cache, never the pane cache.
        return await self._local.get_session_to_project_mapping_async()

    def get_compare_mode(self, pane_id: str) -> str:
        if self._serving():
            rec = self._record_for(pane_id)
            if rec is not None:
                return rec["compare_mode"]
            return self._default_compare_mode()
        if self._mode in _SUBSCRIBED:
            return self._default_compare_mode()
        return self._local.get_compare_mode(pane_id)

    def is_compare_mode_overridden(self, pane_id: str) -> bool:
        if self._serving():
            rec = self._record_for(pane_id)
            return bool(rec["compare_override"]) if rec is not None else False
        if self._mode in _SUBSCRIBED:
            return False
        return self._local.is_compare_mode_overridden(pane_id)

    def get_last_change_wall(self, pane_id: str):
        if self._serving():
            rec = self._record_for(pane_id)
            return rec["last_change"] if rec is not None else None
        if self._mode in _SUBSCRIBED:
            return None
        return self._local.get_last_change_wall(pane_id)

    def control_state(self):
        """The producer's control-channel state as a ``TmuxControlState``; an
        open value this client does not know is returned as its raw string (it
        compares unequal to every member, so no badge shows)."""
        if self._serving():
            value = self._state.control_state
            try:
                return TmuxControlState(value)
            except ValueError:
                return value
        if self._mode in _SUBSCRIBED:
            return TmuxControlState.STOPPED
        return self._local.control_state()

    def last_enumerated_sessions(self) -> frozenset:
        if self._serving():
            return frozenset(self._state.discovery["enumerated"])
        if self._mode in _SUBSCRIBED:
            return frozenset()
        return self._local.last_enumerated_sessions()

    def last_discovered_agents(self) -> frozenset:
        if self._serving():
            return frozenset((s, w) for s, w in self._state.discovery["agents"])
        if self._mode in _SUBSCRIBED:
            return frozenset()
        return self._local.last_discovered_agents()

    def last_discovered_panes(self) -> dict:
        if self._serving():
            return {
                (w["session"], w["window"]): [(p["id"], p["pid"], p["dead"])
                                              for p in w["panes"]]
                for w in self._state.discovery["windows"]
            }
        if self._mode in _SUBSCRIBED:
            return {}
        return self._local.last_discovered_panes()

    # -- capture policy ------------------------------------------------------

    def set_parked_agents(self, pairs) -> None:
        """The app's per-tick skip set. Always handed to the local instance (it
        only matters for local captures, and keeps a fallback's first capture
        correct); the server computes its own skip set from pins."""
        if self._local is not None:
            self._local.set_parked_agents(pairs)

    def set_capture_pins(self, pins) -> None:
        """This client's capture pins (pairs, or ``CAPTURE_PIN_ALL``). Sent as
        ``set_pins`` only when they changed; every (re)subscribe carries them."""
        pins = _normalize_pins(pins)
        if pins == self._pins:
            return
        self._pins = pins
        if self._link is not None and self._mode in _SUBSCRIBED:
            self._pins_send = self._spawn(
                self._quiet_request({"type": "set_pins", "pins": pins_to_wire(pins)}))

    async def flush_pins(self) -> None:
        """Wait until the last ``set_pins`` this client sent is answered.

        :meth:`set_capture_pins` sends without waiting, so a request sent right
        after it could reach the server first. Awaiting this before
        :meth:`request_refresh` makes the requested scan run under the new
        pins: the server handles one connection's requests in order and
        answers ``set_pins`` only after applying it and republishing the skip
        set. Bounded by the request timeout; never raises for the send's
        outcome; a no-op when nothing is pending."""
        task = self._pins_send
        if task is None or task.done():
            return
        # `asyncio.wait`, not `wait_for(shield(task))`: it never cancels the
        # send on timeout and never re-raises the send's own cancellation (a
        # `close()` cancels it) into this caller.
        await asyncio.wait({task}, timeout=self._request_timeout)

    async def set_content(self, selection) -> bool:
        """Change whose ``content`` this client receives (``"all"``, ``"none"`` or
        pane ids). Subscribed — replay included — it returns once the reply
        snapshot is applied. A failed reply fails the connection (the server may
        already have switched the selection) and returns False."""
        await self._await_ready()
        self._content = selection
        link = self._link
        if link is None or self._mode not in _SUBSCRIBED:
            return True
        try:
            reply = await link.request({"type": "set_content", "content": selection},
                                       self._request_timeout)
        except ConnectionLost:
            return False
        except asyncio.TimeoutError:
            await self._lost(link, "set_content timed out")
            return False
        if reply["type"] != "snapshot":
            await self._lost(link, f"set_content failed: {reply.get('code')}")
            return False
        return True

    # -- compare mode --------------------------------------------------------

    async def cycle_compare_mode_async(self, pane_id: str) -> tuple[str, bool]:
        """Authoritative cycle: ``(mode, following_default)`` from the server."""
        return await self._compare_request({"type": "cycle_compare_mode", "pane": pane_id},
                                           lambda: self._local.cycle_compare_mode(pane_id))

    async def set_compare_mode_async(self, pane_id: str, mode) -> tuple[str, bool]:
        """Authoritative set (``None`` follows the default again)."""
        def local():
            new = self._local.set_compare_mode(pane_id, mode)
            return new, not self._local.is_compare_mode_overridden(pane_id)
        return await self._compare_request(
            {"type": "set_compare_mode", "pane": pane_id, "mode": mode}, local)

    async def _compare_request(self, msg: dict, local):
        await self._await_ready()
        if self._mode is ClientMode.REPLAY:
            raise ReplayReadOnly("replay mode is read-only: compare mode")
        link = self._link
        if self._mode is not ClientMode.SERVER or link is None:
            return local()
        reply = await link.request(msg, self._request_timeout)
        if reply["type"] == "error":
            raise RequestFailed(reply["code"], reply["message"])
        return reply["mode"], bool(reply["following_default"])

    def cycle_compare_mode(self, pane_id: str) -> tuple[str, bool]:
        """Sync cycle for the existing call sites. In server mode it sends the
        request and returns a PREDICTION from the record (default → raw →
        stripped → default); the next delta carries the server's answer. Use
        :meth:`cycle_compare_mode_async` for the authoritative result."""
        if self._mode is ClientMode.REPLAY:
            return self.get_compare_mode(pane_id), not self.is_compare_mode_overridden(pane_id)
        if self._mode is not ClientMode.SERVER or self._link is None:
            return self._local.cycle_compare_mode(pane_id)
        override = self.is_compare_mode_overridden(pane_id)
        mode = self.get_compare_mode(pane_id)
        if not override:
            predicted = (COMPARE_MODE_RAW, False)
        elif mode == COMPARE_MODE_RAW:
            predicted = (COMPARE_MODE_STRIPPED, False)
        else:
            predicted = (self._default_compare_mode(), True)
        self._spawn(self._quiet_request({"type": "cycle_compare_mode", "pane": pane_id}))
        return predicted

    def set_compare_mode(self, pane_id: str, mode) -> str:
        """Sync set; in server mode a prediction, like :meth:`cycle_compare_mode`."""
        if self._mode is ClientMode.REPLAY:
            return self.get_compare_mode(pane_id)
        if self._mode is not ClientMode.SERVER or self._link is None:
            return self._local.set_compare_mode(pane_id, mode)
        self._spawn(self._quiet_request({"type": "set_compare_mode", "pane": pane_id,
                                         "mode": mode}))
        return mode if mode is not None else self._default_compare_mode()

    # -- delegation ----------------------------------------------------------

    def __getattr__(self, name: str):
        # Only reached for names the class does not define.
        if name.startswith("__"):
            raise AttributeError(name)
        d = self.__dict__
        if "_mode" not in d:
            raise AttributeError(name)
        mode = d["_mode"]
        local = d.get("_local")
        if mode is ClientMode.REPLAY:
            if name in GATEWAY_NAMES:
                raise ReplayReadOnly(f"replay mode is read-only: {name}")
            raise AttributeError(f"MonitorClient (replay): no {name!r}")
        if mode is ClientMode.SERVER and name not in GATEWAY_NAMES:
            raise AttributeError(
                f"MonitorClient: {name!r} is producer state, not served by the subscription")
        if local is None:
            raise AttributeError(name)
        return getattr(local, name)
