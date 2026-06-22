"""monitor_core - Headless core for the monitor pipeline (no Textual).

The non-UI half of `ait monitor` / `ait minimonitor`: tmux pane discovery,
content capture, idle/awaiting-input detection, pane categorization, the
persistent `tmux -C` control-mode client, and the task-metadata cache. Shared
by both Textual TUIs and the future `ait applink` WebSocket listener — so it
carries **no Textual / rich imports**.

tmux execution is delegated to the gateway `lib/tmux_exec.py`
(`TmuxClient.run_via_control` / `run_async_via_control`); this module does not
re-own the control-client-vs-subprocess dispatch (t952_3).

Extracted from `tmux_monitor.py`, `tmux_control.py`, and `monitor_shared.py`
in t822_6; those modules now re-export from here for backwards compatibility.
"""
from __future__ import annotations

import asyncio
import collections
import contextlib
import enum
import os
import re
import subprocess
import sys
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
# `lib/` holds the gateway + launch/registry helpers; `board/` holds task_yaml
# (the frontmatter parser used by TaskInfoCache). Both are needed here.
for _extra_path in (_SCRIPTS_DIR / "lib", _SCRIPTS_DIR / "board"):
    if str(_extra_path) not in sys.path:
        sys.path.insert(0, str(_extra_path))
from tui_registry import BRAINSTORM_PREFIX, TUI_NAMES  # noqa: E402
from tmux_exec import TmuxClient, tmux_socket_args  # noqa: E402  (gateway: exec-strategy dispatch + socket flag)
from agent_launch_utils import (  # noqa: E402
    AitasksSession,
    discover_aitasks_sessions,
    switch_to_pane_anywhere,
    tmux_session_target,
    tmux_window_target,
)
from task_yaml import parse_frontmatter  # noqa: E402
import gate_ledger  # noqa: E402  (shared gate-ledger parser; single derivation path)

try:
    from .prompt_patterns import PromptPattern, all_patterns
except ImportError:  # imported top-level (tests put MONITOR_DIR on PYTHONPATH)
    from prompt_patterns import PromptPattern, all_patterns  # noqa: E402


# Abstract key name → tmux send-keys argument (for special keys). Lives here in
# the headless core (not monitor_app) so both the desktop preview-zone key
# forwarding and the applink `forward_key` verb translate identically
# server-side (t822_7). monitor_app re-exports this name for back-compat.
_TEXTUAL_TO_TMUX = {
    "enter": "Enter",
    "escape": "Escape",
    "backspace": "BSpace",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "space": "Space",
    "delete": "DC",
    "home": "Home",
    "end": "End",
    "pageup": "PPage",
    "pagedown": "NPage",
    "insert": "IC",
    "f1": "F1",
    "f2": "F2",
    "f3": "F3",
    "f4": "F4",
    "f5": "F5",
    "f6": "F6",
    "f7": "F7",
    "f8": "F8",
    "f9": "F9",
    "f10": "F10",
    "f11": "F11",
    "f12": "F12",
}


def translate_key(key: str, character: str | None = None) -> tuple[str, bool] | None:
    """Translate an abstract key name into tmux ``send-keys`` arguments.

    Returns ``(keys, literal)`` suitable for :meth:`TmuxMonitor.send_keys`, or
    ``None`` when the key cannot be mapped. Shared by the desktop key-forward
    path (``monitor_app._forward_key_to_tmux``) and the applink ``forward_key``
    verb so both sides resolve keys identically:

      * special keys (``up``, ``escape``, ``f5`` …) → the tmux key name, non-literal
      * ``ctrl+x`` → ``C-x``, non-literal
      * a single printable character → sent literally

    ``character`` is the desktop ``event.character`` (the resolved glyph for
    keys whose abstract name is not itself the character, e.g. ``!`` arrives as
    ``exclamation_mark``); mobile clients pass only ``key`` (the literal glyph
    for plain characters) and leave ``character`` as ``None``.
    """
    if key in _TEXTUAL_TO_TMUX:
        return _TEXTUAL_TO_TMUX[key], False
    if key.startswith("ctrl+"):
        return f"C-{key[5:]}", False
    if character and len(character) == 1:
        return character, True
    if len(key) == 1:
        return key, True
    return None


class PaneCategory(Enum):
    AGENT = "agent"
    TUI = "tui"
    OTHER = "other"


DEFAULT_AGENT_PREFIXES = ["agent-"]
DEFAULT_TUI_NAMES = TUI_NAMES

# Idle-detection comparison modes.
#   stripped — strip ANSI escape codes from captured pane content before
#     equality check. Required to detect Codex CLI agents as idle: Codex
#     animates the spinner color via SGR escape codes even while waiting
#     on user input, so a raw byte-equal comparison declares the pane
#     "changed" every refresh tick and idle is never reached.
#   raw — compare the full captured bytes including escape codes. Legacy
#     behavior; only useful as a fallback if a future agent renders idle
#     UI by toggling escape codes that semantically matter.
COMPARE_MODE_STRIPPED = "stripped"
COMPARE_MODE_RAW = "raw"
COMPARE_MODES = (COMPARE_MODE_STRIPPED, COMPARE_MODE_RAW)
DEFAULT_COMPARE_MODE = COMPARE_MODE_STRIPPED

# CSI escape sequence (covers SGR colors plus any other animated CSI tokens).
_ANSI_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _strip_ansi(s: str) -> str:
    return _ANSI_CSI_RE.sub("", s)


_COMPANION_KEYWORDS = ("minimonitor", "monitor_app")


def _is_companion_process(pid: int) -> bool:
    """Check if a process is a companion pane (minimonitor/monitor) via cmdline."""
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            cmdline = f.read().decode("utf-8", errors="replace")
        return any(kw in cmdline for kw in _COMPANION_KEYWORDS)
    except (OSError, PermissionError):
        pass
    # Fallback for non-Linux (macOS)
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "args="],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            return any(kw in result.stdout for kw in _COMPANION_KEYWORDS)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return False


# -- Shadow companion panes (t986) --------------------------------------------
#
# A "shadow" is a second coding-agent CLI spawned in (by default) the same tmux
# window as the agent it follows. Because splitting a window does not rename it,
# a same-window shadow shares the *agent's* window name — so it cannot be told
# apart by window name. Instead the spawner (t986_5) records the shadowed
# agent's pane id in the pane-scoped tmux user option below. A pane carrying a
# non-empty value is a shadow *helper*: excluded from agent lists exactly like
# the minimonitor/monitor companion panes, and never resolved to a task. The
# value also drives lifecycle cleanup — when the shadowed agent's pane dies,
# `aitask_companion_cleanup.sh` kills the bound shadow.
SHADOW_TARGET_OPTION = "@aitask_shadow_target"


def is_shadow_target(shadow_target: str) -> bool:
    """True when a pane's ``@aitask_shadow_target`` value marks it a shadow.

    Pure: takes the already-read option value (empty/whitespace ⇒ not a
    shadow), so the tmux read stays at the call site and this stays
    unit-testable.
    """
    return bool(shadow_target.strip())


def count_other_real_agents(
    pane_records: Iterable[tuple[str, bool]], exclude_pane_id: str
) -> int:
    """Count panes that are *real* agents (not helper panes), excluding one.

    ``pane_records`` is an iterable of ``(pane_id, is_helper)`` pairs. Helper
    classification (companion process or shadow marker) is decided by the
    caller, keeping this counting logic pure and import-free for unit tests.
    Used by :meth:`TmuxMonitor.kill_agent_pane_smart` to decide whether the
    window should collapse (no real agents left) or only the pane be killed.
    """
    return sum(
        1
        for pane_id, is_helper in pane_records
        if pane_id != exclude_pane_id and not is_helper
    )


@dataclass
class TmuxPaneInfo:
    window_index: str
    window_name: str
    pane_index: str
    pane_id: str        # e.g., %3
    pane_pid: int
    current_command: str
    width: int
    height: int
    category: PaneCategory
    session_name: str = ""   # populated by discovery; "" only when constructed outside a list-panes path


@dataclass
class PaneSnapshot:
    pane: TmuxPaneInfo
    content: str            # last N lines of captured text
    timestamp: float        # time.monotonic()
    idle_seconds: float     # seconds since last content change
    is_idle: bool           # idle_seconds > threshold (only meaningful for AGENT panes)
    awaiting_input: bool = False
    awaiting_input_kind: str = ""   # name of the first matching prompt pattern


# %begin / %end / %error <epoch> <cmd_id> <flags>
# Flags is a bitmask; bit 1 means the block is the response to a command
# issued via this control client. Server-emitted blocks (e.g., the implicit
# attach acknowledgment) have bit 1 unset and must not be delivered to
# pending callers.
_HEAD_RE = re.compile(r"^%(begin|end|error)\s+\d+\s+(\d+)\s+(\d+)\s*$")
_EXIT_RE = re.compile(r"^%exit(?:\s+.*)?$")

_DEFAULT_STREAM_LIMIT = 4 * 1024 * 1024  # 4 MiB; default asyncio is 64 KiB
_DEFAULT_CLOSE_TIMEOUT = 2.0


def _quote_arg(arg: str) -> str:
    """Quote one tmux command argument for the control-mode wire format.

    tmux's command parser tokenizes on whitespace outside quotes; inside
    `"..."` it interprets `\\\\`, `\\"`, and a few other escapes. We escape
    only `\\` → `\\\\` and `"` → `\\"`. Literal tab bytes (`0x09`) inside
    the quoted string are preserved — tmux's lexer accepts them, and this
    matches the byte-for-byte wire format the existing subprocess path
    passes via argv (notably the format string for `list-panes -F`).
    """
    return '"' + arg.replace("\\", "\\\\").replace('"', '\\"') + '"'


class TmuxControlClient:
    """Single persistent `tmux -C` control client."""

    def __init__(
        self,
        session: str,
        command_timeout: float = 5.0,
        socket_args: list[str] | None = None,
    ):
        self.session = session
        self.command_timeout = command_timeout
        # Socket flag (``-L <name>`` or ``[]``) cached once — never re-read
        # per request (this client serves the monitor refresh hot path). When
        # not supplied, resolved from ``AITASKS_TMUX_SOCKET`` via the gateway so
        # the control attach converges on the same socket as TmuxClient (t952_3).
        self._socket_args = (
            list(socket_args) if socket_args is not None else tmux_socket_args()
        )
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._pending: "collections.deque[asyncio.Future]" = collections.deque()
        # (cmd_id, buf, deliver) — `deliver` is False for server-emitted
        # blocks (flags bit 1 unset); their bodies are dropped at end/error.
        self._capturing: Optional[tuple[int, list[str], bool]] = None
        self._write_lock = asyncio.Lock()
        self._alive = False

    @property
    def is_alive(self) -> bool:
        return self._alive

    def _attach_argv(self) -> list[str]:
        """Build the ``tmux -C attach`` argv, with the socket flag threaded in.

        The cached socket flag goes between ``"tmux"`` and ``"-C"`` so a
        dedicated-socket move (``AITASKS_TMUX_SOCKET``) reaches the control
        channel exactly as it reaches TmuxClient's subprocess path. Extracted as
        a method so the argv is unit-testable without spawning a process.
        """
        return [
            "tmux", *self._socket_args, "-C", "attach", "-t", self.session,
            "-f", "no-output,ignore-size",
        ]

    async def start(self) -> bool:
        """Spawn `tmux -C attach` and start the reader task.

        Returns False if `tmux` is not on PATH or the attach fails (e.g.,
        the target session does not exist). Does not raise on those paths
        — callers fall back to subprocess.
        """
        if self._proc is not None:
            return self._alive
        try:
            self._proc = await asyncio.create_subprocess_exec(
                *self._attach_argv(),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                limit=_DEFAULT_STREAM_LIMIT,
            )
        except (FileNotFoundError, OSError):
            self._proc = None
            return False

        # Attach can fail asynchronously — give the child a brief moment to
        # decide. If it has already exited by the time we look, the attach
        # failed (typically: session does not exist). asyncio's Process
        # exposes `returncode` which is non-None once exited.
        await asyncio.sleep(0.05)
        if self._proc.returncode is not None:
            self._proc = None
            return False

        self._alive = True
        self._reader_task = asyncio.create_task(self._reader_loop())
        return True

    async def _reader_loop(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        try:
            while True:
                line_bytes = await self._proc.stdout.readline()
                if not line_bytes:
                    break  # EOF
                line = line_bytes.decode("utf-8", errors="replace")
                if line.endswith("\n"):
                    line = line[:-1]

                if self._capturing is not None:
                    cmd_id, buf, deliver = self._capturing
                    m = _HEAD_RE.match(line)
                    if m and m.group(1) in ("end", "error") and int(m.group(2)) == cmd_id:
                        rc = 0 if m.group(1) == "end" else 1
                        body = "\n".join(buf) + ("\n" if buf else "")
                        self._capturing = None
                        if deliver:
                            self._resolve_next((rc, body))
                        # Server-emitted block (e.g., attach ack): drop.
                    else:
                        buf.append(line)
                    continue

                m = _HEAD_RE.match(line)
                if m and m.group(1) == "begin":
                    deliver = (int(m.group(3)) & 1) != 0
                    self._capturing = (int(m.group(2)), [], deliver)
                elif _EXIT_RE.match(line):
                    break  # tmux server is going away
                # Any other %-line outside a Capturing block is an async
                # event (filtered to `no-output`-only by the spawn flags,
                # but tmux can still emit %sessions-changed, %client-detached,
                # etc.). Discard.
        except (asyncio.CancelledError, ConnectionResetError, OSError):
            pass
        finally:
            self._teardown_pending()

    def _resolve_next(self, result: tuple[int, str]) -> None:
        if not self._pending:
            return  # spurious response (no caller waiting); drop on the floor
        fut = self._pending.popleft()
        if not fut.done():
            fut.set_result(result)

    def _teardown_pending(self) -> None:
        self._alive = False
        # If a capture was in flight, drop it — the corresponding future is
        # the leftmost in _pending and gets resolved with (-1, "") below.
        self._capturing = None
        while self._pending:
            fut = self._pending.popleft()
            if not fut.done():
                fut.set_result((-1, ""))

    async def request(
        self, args: list[str], timeout: float | None = None
    ) -> tuple[int, str]:
        """Issue one tmux command; return `(rc, stdout_text)`.

        rc semantics mirror `lib.tmux_exec.TmuxClient.run_async`:
        - `0` on success
        - `1` on tmux command error (`%error` reply)
        - `-1` on transport failure (client dead, broken pipe, timeout)

        On `-1`, the client is marked dead; the next `request()` will also
        return `(-1, "")` until `start()` is called again.
        """
        if not self._alive or self._proc is None or self._proc.stdin is None:
            return (-1, "")

        cmd_line = " ".join(_quote_arg(a) for a in args) + "\n"
        fut: asyncio.Future = asyncio.get_running_loop().create_future()

        async with self._write_lock:
            if not self._alive or self._proc.stdin is None:
                return (-1, "")
            self._pending.append(fut)
            try:
                self._proc.stdin.write(cmd_line.encode("utf-8"))
                await self._proc.stdin.drain()
            except (BrokenPipeError, ConnectionResetError, OSError):
                self._teardown_pending()
                return (-1, "")

        try:
            effective_timeout = timeout if timeout is not None else self.command_timeout
            return await asyncio.wait_for(fut, timeout=effective_timeout)
        except asyncio.TimeoutError:
            # We can't reliably correlate any future responses to in-flight
            # callers anymore — mark dead and let everyone fall back.
            self._teardown_pending()
            return (-1, "")

    async def close(self) -> None:
        """Shut down the control client cleanly.

        Closes stdin (tmux drops the control client on EOF), waits briefly
        for `proc.wait()`, kills if it's still running, then cancels the
        reader task. Resolves any remaining futures with `(-1, "")`.
        Idempotent.
        """
        self._alive = False
        proc = self._proc
        if proc is None:
            self._teardown_pending()
            return

        if proc.stdin is not None and not proc.stdin.is_closing():
            with contextlib.suppress(Exception):
                proc.stdin.close()

        try:
            await asyncio.wait_for(proc.wait(), timeout=_DEFAULT_CLOSE_TIMEOUT)
        except asyncio.TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            with contextlib.suppress(Exception):
                await proc.wait()

        if self._reader_task is not None and not self._reader_task.done():
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._reader_task

        self._teardown_pending()
        self._proc = None
        self._reader_task = None


_BACKEND_READY_TIMEOUT = 2.0
_BACKEND_START_TIMEOUT = 5.0
_BACKEND_STOP_TIMEOUT = 3.0
_BACKEND_THREAD_JOIN_TIMEOUT = 3.0

# Supervisor / reconnect tuning. Backoffs are seconds between successive
# reconnect attempts; the supervisor sleeps the backoff *before* each
# attempt, so the first respawn is delayed by 0.5 s after the prior client
# is observed dead. After `_RECONNECT_MAX_ATTEMPTS` consecutive failed
# spawns the supervisor exits and the backend stays in `FALLBACK` for the
# rest of its life. `_DEATH_POLL_INTERVAL` is the cadence at which the
# supervisor polls `client.is_alive` while the channel is healthy — kept
# tighter than the typical monitor refresh so the badge flips quickly when
# the channel breaks.
_RECONNECT_BACKOFFS = (0.5, 1.0, 2.0, 4.0, 8.0)
_RECONNECT_MAX_ATTEMPTS = 5
_DEATH_POLL_INTERVAL = 0.5


class TmuxControlState(enum.Enum):
    """Lifecycle state of a `TmuxControlBackend`'s control channel."""
    CONNECTED = "connected"        # client attached and serving requests
    RECONNECTING = "reconnecting"  # supervisor is respawning the client
    FALLBACK = "fallback"          # max attempts exhausted; subprocess only
    STOPPED = "stopped"            # backend.stop() called or never started


class TmuxControlBackend:
    """Owns a dedicated asyncio loop in a background thread that drives a
    `TmuxControlClient`.

    Provides sync (`request_sync`) and async (`request_async`) entry points;
    both route through `asyncio.run_coroutine_threadsafe` so callers on any
    thread/loop see consistent semantics. The backend exists so that sync
    user-action call sites (Textual handlers, etc.) can reach the control
    client without deadlocking the reader task — the reader runs on the
    backend's bg loop, not on the calling thread's loop.

    Subprocess fallback is the caller's responsibility: this class only
    surfaces `(-1, "")` on transport failure.
    """

    def __init__(
        self,
        session: str,
        command_timeout: float = 5.0,
        socket_args: list[str] | None = None,
    ):
        self.session = session
        self.command_timeout = command_timeout
        # Cached socket flag, passed to every client this backend constructs
        # (initial start + every supervisor reconnect) so a reconnected channel
        # keeps the same socket. Resolved from AITASKS_TMUX_SOCKET when not
        # supplied (unset env → dedicated `-L ait` socket, t953).
        self._socket_args = (
            list(socket_args) if socket_args is not None else tmux_socket_args()
        )
        self._client: Optional[TmuxControlClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._state: TmuxControlState = TmuxControlState.STOPPED
        self._state_lock = threading.Lock()
        self._reconnect_task: Optional[asyncio.Task] = None
        self._stop_requested: bool = False

    @property
    def is_alive(self) -> bool:
        return self._client is not None and self._client.is_alive

    @property
    def state(self) -> TmuxControlState:
        """Current channel state. Thread-safe; safe to call from the UI loop."""
        with self._state_lock:
            return self._state

    def _set_state(self, s: TmuxControlState) -> None:
        with self._state_lock:
            self._state = s

    def start(self) -> bool:
        """Start bg thread + loop, then start the client on it.

        Returns True iff the client successfully attached. Idempotent: a
        second call while already started returns the current `is_alive`
        without spawning a second thread.
        """
        if self._thread is not None:
            return self.is_alive
        self._stop_requested = False
        self._ready.clear()
        thread = threading.Thread(
            target=self._thread_main, name="tmux-control-loop", daemon=True
        )
        thread.start()
        if not self._ready.wait(timeout=_BACKEND_READY_TIMEOUT) or self._loop is None:
            # Loop never came up — abandon the thread (daemon=True will clean
            # it up at process exit). Reset state so a future start() retries.
            self._thread = None
            self._loop = None
            return False
        self._thread = thread
        client = TmuxControlClient(
            self.session, self.command_timeout, socket_args=self._socket_args
        )
        cf = asyncio.run_coroutine_threadsafe(client.start(), self._loop)
        try:
            ok = cf.result(timeout=_BACKEND_START_TIMEOUT)
        except Exception:
            ok = False
        if ok:
            self._client = client
            self._set_state(TmuxControlState.CONNECTED)
            self._spawn_supervisor()
            return True
        # Client did not attach. Tear down the thread so we don't leak it.
        self.stop()
        return False

    def _spawn_supervisor(self) -> None:
        """Schedule the reconnect supervisor on the bg loop (fire-and-forget).

        Stores the resulting `asyncio.Task` in `self._reconnect_task` from
        the bg loop's thread, so cancellation in `stop()` always reads a
        consistent value.
        """
        loop = self._loop
        if loop is None:
            return

        def _create_task() -> None:
            self._reconnect_task = loop.create_task(self._supervisor_loop())

        loop.call_soon_threadsafe(_create_task)

    async def _supervisor_loop(self) -> None:
        """Watch the active client; respawn on death with bounded backoff.

        Runs on the bg loop. Polls `client.is_alive` at
        `_DEATH_POLL_INTERVAL`; on death, attempts up to
        `_RECONNECT_MAX_ATTEMPTS` reconnects spaced by `_RECONNECT_BACKOFFS`.
        On success, swaps `self._client` to the fresh client and returns to
        polling. On exhaustion, sets `FALLBACK` and exits — the backend
        stays subprocess-only for the rest of its life.

        Cooperative shutdown: `stop()` sets `_stop_requested = True` and
        cancels the task. Both paths exit cleanly.
        """
        try:
            while not self._stop_requested:
                # Phase 1: wait for the current client to die.
                while (
                    self._client is not None
                    and self._client.is_alive
                    and not self._stop_requested
                ):
                    await asyncio.sleep(_DEATH_POLL_INTERVAL)
                if self._stop_requested:
                    return

                # Phase 2: client is dead. Try to reconnect with backoff.
                self._set_state(TmuxControlState.RECONNECTING)
                attempts = 0
                reconnected = False
                while (
                    attempts < _RECONNECT_MAX_ATTEMPTS
                    and not self._stop_requested
                ):
                    delay = _RECONNECT_BACKOFFS[
                        min(attempts, len(_RECONNECT_BACKOFFS) - 1)
                    ]
                    await asyncio.sleep(delay)
                    if self._stop_requested:
                        return
                    new_client = TmuxControlClient(
                        self.session, self.command_timeout,
                        socket_args=self._socket_args,
                    )
                    if await new_client.start():
                        self._client = new_client
                        self._set_state(TmuxControlState.CONNECTED)
                        reconnected = True
                        break
                    attempts += 1

                if not reconnected:
                    self._set_state(TmuxControlState.FALLBACK)
                    return
        except asyncio.CancelledError:
            # Cooperative shutdown — fall through. State is updated by stop().
            return

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()

    def stop(self) -> None:
        """Close the client (on bg loop), stop the loop, join the thread.

        Idempotent. Safe to call when start() failed partway through. Also
        cancels the reconnect supervisor (if any) before tearing down the
        client, so an in-flight reconnect attempt cannot create a new
        `tmux -C attach` subprocess after `stop()` returns.
        """
        self._stop_requested = True
        loop = self._loop
        client = self._client
        thread = self._thread
        # Cancel the supervisor before closing the client so it can't
        # respawn a fresh one in the gap between client.close() and the
        # loop stopping.
        if loop is not None and self._reconnect_task is not None:
            with contextlib.suppress(Exception):
                cf = asyncio.run_coroutine_threadsafe(
                    self._cancel_reconnect_task(), loop
                )
                cf.result(timeout=1.0)
        if loop is not None and client is not None:
            with contextlib.suppress(Exception):
                cf = asyncio.run_coroutine_threadsafe(client.close(), loop)
                cf.result(timeout=_BACKEND_STOP_TIMEOUT)
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        if thread is not None and thread.is_alive():
            thread.join(timeout=_BACKEND_THREAD_JOIN_TIMEOUT)
        self._client = None
        self._loop = None
        self._thread = None
        self._reconnect_task = None
        self._ready.clear()
        self._set_state(TmuxControlState.STOPPED)

    async def _cancel_reconnect_task(self) -> None:
        """Cancel the supervisor task and wait for it to finish.

        Runs on the bg loop. Reads `self._reconnect_task` from the same
        loop that created it, so the read is consistent. Idempotent —
        safe if the task already finished or was never created.
        """
        task = self._reconnect_task
        if task is None or task.done():
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task

    def request_sync(
        self, args: list[str], timeout: Optional[float] = None
    ) -> tuple[int, str]:
        """Issue a tmux command and block until the response arrives.

        Returns `(rc, stdout)`. `(-1, "")` on transport failure (client
        dead, loop unavailable, or future timeout). Safe to call from any
        thread, including from inside an asyncio handler running on a
        different loop than the backend.
        """
        loop = self._loop
        client = self._client
        if loop is None or client is None or not client.is_alive:
            return (-1, "")
        eff = timeout if timeout is not None else self.command_timeout
        try:
            cf = asyncio.run_coroutine_threadsafe(
                client.request(args, timeout=eff), loop
            )
        except RuntimeError:
            # Loop closed between the alive check and scheduling.
            return (-1, "")
        try:
            return cf.result(timeout=eff + 1.0)
        except Exception:
            with contextlib.suppress(Exception):
                cf.cancel()
            return (-1, "")

    async def request_async(
        self, args: list[str], timeout: Optional[float] = None
    ) -> tuple[int, str]:
        """Issue a tmux command from an async caller on a different loop.

        The caller awaits the result on its own loop; the request executes
        on the backend's bg loop.
        """
        loop = self._loop
        client = self._client
        if loop is None or client is None or not client.is_alive:
            return (-1, "")
        eff = timeout if timeout is not None else self.command_timeout
        try:
            cf = asyncio.run_coroutine_threadsafe(
                client.request(args, timeout=eff), loop
            )
        except RuntimeError:
            return (-1, "")
        try:
            return await asyncio.wrap_future(cf)
        except Exception:
            return (-1, "")


class TmuxMonitor:
    # Session-discovery cache TTL: `discover_aitasks_sessions()` runs `tmux
    # list-sessions` plus a serial `list-panes -s` per session, which is
    # wasteful to redo every refresh tick. Ten seconds keeps the view snappy
    # without re-querying on every paint. The `M` runtime toggle invalidates
    # the cache so the first post-toggle refresh re-discovers immediately.
    _SESSIONS_CACHE_TTL = 10.0

    def __init__(
        self,
        session: str,
        capture_lines: int = 200,
        idle_threshold: float = 5.0,
        exclude_pane: str | None = None,
        agent_prefixes: list[str] | None = None,
        tui_names: set[str] | None = None,
        multi_session: bool = True,
        compare_mode_default: str = DEFAULT_COMPARE_MODE,
        prompt_patterns: list[PromptPattern] | None = None,
    ):
        self.session = session
        self.capture_lines = capture_lines
        self.idle_threshold = idle_threshold
        self.exclude_pane = exclude_pane or os.environ.get("TMUX_PANE")
        self.agent_prefixes = agent_prefixes if agent_prefixes is not None else list(DEFAULT_AGENT_PREFIXES)
        self.tui_names = tui_names if tui_names is not None else set(DEFAULT_TUI_NAMES)
        self.multi_session = multi_session
        if compare_mode_default not in COMPARE_MODES:
            compare_mode_default = DEFAULT_COMPARE_MODE
        self.compare_mode_default = compare_mode_default
        self.prompt_patterns = list(prompt_patterns) if prompt_patterns is not None else all_patterns()

        self._last_content: dict[str, str] = {}
        self._last_change_time: dict[str, float] = {}
        self._pane_cache: dict[str, TmuxPaneInfo] = {}
        self._sessions_cache: tuple[float, list[AitasksSession]] | None = None
        self._compare_mode_overrides: dict[str, str] = {}
        self._backend: TmuxControlBackend | None = None
        # Gateway owns the exec strategy (control-client-vs-subprocess dispatch)
        # and the socket flag; tmux_run / _tmux_async delegate to it (t952_3).
        self._tmux = TmuxClient()

    async def start_control_client(self) -> bool:
        """Start the persistent `tmux -C` backend on a dedicated bg thread.

        Kept `async` so existing call sites (`await monitor.start_control_client()`)
        do not need to change. The body is synchronous — the bg thread does
        the actual asyncio work — so awaiting it just yields once.
        """
        backend = TmuxControlBackend(session=self.session)
        if backend.start():
            self._backend = backend
            return True
        backend.stop()
        return False

    async def close_control_client(self) -> None:
        if self._backend is not None:
            with contextlib.suppress(Exception):
                self._backend.stop()
            self._backend = None

    def has_control_client(self) -> bool:
        return self._backend is not None and self._backend.is_alive

    def control_state(self) -> TmuxControlState:
        """Backend channel state, or `STOPPED` if no backend is attached."""
        if self._backend is None:
            return TmuxControlState.STOPPED
        return self._backend.state

    async def _tmux_async(
        self, args: list[str], timeout: float = 5.0
    ) -> tuple[int, str]:
        # Thin delegation: the gateway owns the control-client-vs-subprocess
        # dispatch (t952_3). Signature unchanged so all monitor call sites stay.
        return await self._tmux.run_async_via_control(
            self._backend, args, timeout=timeout
        )

    def tmux_run(
        self, args: list[str], timeout: float = 5.0
    ) -> tuple[int, str]:
        """Sync user-action wrapper — control-client when alive, subprocess fallback.

        Returns `(rc, stdout)`. `rc` semantics:
          * `0` on success
          * `1` on tmux command error
          * `-1` on transport failure or subprocess error.

        Safe to call from sync Textual handlers because the control client
        runs on a background loop; this method blocks the caller's thread,
        not the bg loop's reader task. The dispatch itself lives in the gateway
        (`TmuxClient.run_via_control`, t952_3); this is a thin delegation.
        """
        return self._tmux.run_via_control(self._backend, args, timeout=timeout)

    async def tmux_run_async(
        self, args: list[str], timeout: float = 5.0
    ) -> tuple[int, str]:
        """Async sibling of :meth:`tmux_run` — same ``(rc, stdout)`` contract.

        Use from async Textual handlers / the refresh loop so a tmux stall never
        blocks the event loop (the sync :meth:`tmux_run` would block the calling
        thread, which on an async path is the loop thread). Thin public alias for
        the internal :meth:`_tmux_async`.
        """
        return await self._tmux_async(args, timeout=timeout)

    def resize_pane(
        self, pane: str, *, x: int | None = None, y: int | None = None,
        timeout: float = 2.0,
    ) -> tuple[int, str]:
        """Resize a pane via the gateway's subprocess path.

        ``resize-pane`` is still owned by ``TmuxClient.resize_pane`` so socket
        selection and argv construction stay centralized. This intentionally
        does not pass the control backend: minimonitor re-pinning happens from
        Textual's resize handler, and tmux can lose immediate control-mode
        resize commands during a window-growth reflow.
        """
        return self._tmux.resize_pane(pane, x=x, y=y, timeout=timeout)

    def _discover_sessions_cached(self) -> list[AitasksSession]:
        """Return the list of aitasks-like tmux sessions, memoized for TTL seconds."""
        now = time.monotonic()
        if self._sessions_cache is not None:
            cached_at, sessions = self._sessions_cache
            if now - cached_at < self._SESSIONS_CACHE_TTL:
                return sessions
        sessions = discover_aitasks_sessions()
        self._sessions_cache = (now, sessions)
        return sessions

    def invalidate_sessions_cache(self) -> None:
        """Force the next `_discover_sessions_cached` call to re-query tmux."""
        self._sessions_cache = None

    def get_session_to_project_mapping(self) -> dict[str, Path]:
        """Map session_name → project_root for all discovered aitasks sessions.

        Piggybacks on the `_discover_sessions_cached` TTL — no extra tmux
        calls. Used by monitor TUIs to resolve task data from the project that
        owns each codeagent's tmux session.
        """
        return {s.session: s.project_root for s in self._discover_sessions_cached()}

    def classify_pane(self, window_name: str) -> PaneCategory:
        for prefix in self.agent_prefixes:
            if window_name.startswith(prefix):
                return PaneCategory.AGENT
        if window_name in self.tui_names:
            return PaneCategory.TUI
        if window_name.startswith(BRAINSTORM_PREFIX):
            return PaneCategory.TUI
        return PaneCategory.OTHER

    _LIST_PANES_FORMAT = "\t".join([
        "#{window_index}", "#{window_name}", "#{pane_index}",
        "#{pane_id}", "#{pane_pid}", "#{pane_current_command}",
        "#{pane_width}", "#{pane_height}",
        "#{@aitask_shadow_target}",   # shadow helper marker (t986); "" when unset
    ])

    def _parse_list_panes(self, stdout: str, session_name: str) -> list[TmuxPaneInfo]:
        panes: list[TmuxPaneInfo] = []
        # Preserve an empty final @aitask_shadow_target field on non-shadow panes.
        for line in stdout.splitlines():
            parts = line.split("\t")
            if len(parts) != 9:
                continue
            pane_id = parts[3]
            if self.exclude_pane and pane_id == self.exclude_pane:
                continue
            # Shadow companion panes (t986) are helpers — drop them from
            # discovery entirely so they never appear in agent lists, snapshots,
            # or kill/sibling logic, exactly like the minimonitor/monitor panes
            # filtered below. The marker is authoritative even for a same-window
            # shadow, which shares the agent's window name.
            if is_shadow_target(parts[8]):
                continue
            try:
                pane_pid = int(parts[4])
                width = int(parts[6])
                height = int(parts[7])
            except ValueError:
                continue
            window_name = parts[1]
            category = self.classify_pane(window_name)
            # Filter companion panes (minimonitor/monitor) in agent windows
            if category == PaneCategory.AGENT and _is_companion_process(pane_pid):
                continue
            pane = TmuxPaneInfo(
                window_index=parts[0],
                window_name=window_name,
                pane_index=parts[2],
                pane_id=pane_id,
                pane_pid=pane_pid,
                current_command=parts[5],
                width=width,
                height=height,
                category=category,
                session_name=session_name,
            )
            panes.append(pane)
            self._pane_cache[pane_id] = pane
        return panes

    def _target_sessions(self) -> list[str]:
        """Session names to enumerate in multi mode (sorted for stable display)."""
        return sorted(s.session for s in self._discover_sessions_cached())

    def _discover_panes_multi(self) -> list[TmuxPaneInfo]:
        panes: list[TmuxPaneInfo] = []
        for sess in self._target_sessions():
            rc, stdout = self.tmux_run([
                "list-panes", "-s", "-t", tmux_session_target(sess),
                "-F", self._LIST_PANES_FORMAT,
            ])
            if rc != 0:
                continue
            panes.extend(self._parse_list_panes(stdout, sess))
        panes.sort(key=lambda p: (p.session_name, p.window_index, p.pane_index))
        return panes

    async def _discover_panes_multi_async(self) -> list[TmuxPaneInfo]:
        sessions = self._target_sessions()
        if not sessions:
            return []
        results = await asyncio.gather(*[
            self._tmux_async([
                "list-panes", "-s", "-t", tmux_session_target(sess),
                "-F", self._LIST_PANES_FORMAT,
            ])
            for sess in sessions
        ])
        panes: list[TmuxPaneInfo] = []
        for sess, (rc, stdout) in zip(sessions, results):
            if rc != 0:
                continue
            panes.extend(self._parse_list_panes(stdout, sess))
        panes.sort(key=lambda p: (p.session_name, p.window_index, p.pane_index))
        return panes

    def discover_panes(self) -> list[TmuxPaneInfo]:
        if self.multi_session:
            return self._discover_panes_multi()
        rc, stdout = self.tmux_run([
            "list-panes", "-s", "-t", tmux_session_target(self.session),
            "-F", self._LIST_PANES_FORMAT,
        ])
        if rc != 0:
            return []
        return self._parse_list_panes(stdout, self.session)

    async def discover_panes_async(self) -> list[TmuxPaneInfo]:
        if self.multi_session:
            return await self._discover_panes_multi_async()
        rc, stdout = await self._tmux_async(
            ["list-panes", "-s", "-t", tmux_session_target(self.session),
             "-F", self._LIST_PANES_FORMAT],
        )
        if rc != 0:
            return []
        return self._parse_list_panes(stdout, self.session)

    def discover_window_panes(self, window_id: str) -> list[TmuxPaneInfo]:
        """Discover panes in a specific window (not session-wide).

        Uses 'tmux list-panes -t window_id' (no -s flag).
        Does not filter by exclude_pane or update _pane_cache.
        """
        fmt = "\t".join([
            "#{window_index}", "#{window_name}", "#{pane_index}",
            "#{pane_id}", "#{pane_pid}", "#{pane_current_command}",
            "#{pane_width}", "#{pane_height}",
        ])
        rc, stdout = self.tmux_run(["list-panes", "-t", window_id, "-F", fmt])
        if rc != 0:
            return []

        panes: list[TmuxPaneInfo] = []
        for line in stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) != 8:
                continue
            try:
                pane_pid = int(parts[4])
                width = int(parts[6])
                height = int(parts[7])
            except ValueError:
                continue
            window_name = parts[1]
            pane = TmuxPaneInfo(
                window_index=parts[0],
                window_name=window_name,
                pane_index=parts[2],
                pane_id=parts[3],
                pane_pid=pane_pid,
                current_command=parts[5],
                width=width,
                height=height,
                category=self.classify_pane(window_name),
                session_name=self.session,
            )
            panes.append(pane)
        return panes

    def get_compare_mode(self, pane_id: str) -> str:
        """Effective idle-detection compare mode for a pane.

        Returns the per-pane override if set, otherwise the global default.
        """
        return self._compare_mode_overrides.get(pane_id, self.compare_mode_default)

    def is_compare_mode_overridden(self, pane_id: str) -> bool:
        return pane_id in self._compare_mode_overrides

    def set_compare_mode(self, pane_id: str, mode: str | None) -> str:
        """Set per-pane compare mode override; pass None to clear and follow default.

        Clears the stored last-content for the pane so the next capture
        re-baselines under the new comparison form, avoiding one tick of
        spurious "changed" right after the toggle.
        """
        if mode is None:
            self._compare_mode_overrides.pop(pane_id, None)
        else:
            if mode not in COMPARE_MODES:
                raise ValueError(f"unknown compare mode: {mode!r}")
            self._compare_mode_overrides[pane_id] = mode
        self._last_content.pop(pane_id, None)
        return self.get_compare_mode(pane_id)

    def cycle_compare_mode(self, pane_id: str) -> tuple[str, bool]:
        """Cycle a pane through default → raw → stripped → default.

        Returns (effective_mode, is_following_default).
        """
        current_override = self._compare_mode_overrides.get(pane_id)
        if current_override is None:
            new_override: str | None = COMPARE_MODE_RAW
        elif current_override == COMPARE_MODE_RAW:
            new_override = COMPARE_MODE_STRIPPED
        else:
            new_override = None
        effective = self.set_compare_mode(pane_id, new_override)
        return effective, (new_override is None)

    def _finalize_capture(
        self, pane: TmuxPaneInfo, content: str
    ) -> PaneSnapshot:
        now = time.monotonic()
        pane_id = pane.pane_id

        mode = self.get_compare_mode(pane_id)
        compare_value = _strip_ansi(content) if mode == COMPARE_MODE_STRIPPED else content

        prev = self._last_content.get(pane_id)
        if prev is None or compare_value != prev:
            self._last_content[pane_id] = compare_value
            self._last_change_time[pane_id] = now

        last_change = self._last_change_time.get(pane_id, now)
        idle_seconds = now - last_change
        is_idle = (
            idle_seconds > self.idle_threshold
            if pane.category == PaneCategory.AGENT
            else False
        )

        awaiting_input = False
        awaiting_input_kind = ""
        if pane.category == PaneCategory.AGENT and self.prompt_patterns:
            stripped_text = compare_value if mode == COMPARE_MODE_STRIPPED else _strip_ansi(content)
            for p in self.prompt_patterns:
                if p.regex.search(stripped_text):
                    awaiting_input = True
                    awaiting_input_kind = p.name
                    break

        return PaneSnapshot(
            pane=pane,
            content=content,
            timestamp=now,
            idle_seconds=idle_seconds,
            is_idle=is_idle,
            awaiting_input=awaiting_input,
            awaiting_input_kind=awaiting_input_kind,
        )

    def _capture_args(self, pane_id: str) -> list[str]:
        return [
            "capture-pane", "-p", "-e", "-t", pane_id,
            "-S", f"-{self.capture_lines}",
        ]

    def capture_pane(self, pane_id: str) -> PaneSnapshot | None:
        pane = self._pane_cache.get(pane_id)
        if pane is None:
            return None
        rc, content = self.tmux_run(self._capture_args(pane_id))
        if rc != 0:
            return None
        return self._finalize_capture(pane, content)

    def get_pane(self, pane_id: str) -> "TmuxPaneInfo | None":
        """Return the cached pane metadata for ``pane_id`` (no subprocess).

        Lightweight accessor over ``_pane_cache`` (populated by discovery) for
        callers that need a pane's ``window_name`` / ``session_name`` without a
        live ``capture-pane`` — e.g. the applink router resolving a pane to its
        task family for the modal handshakes (t822_11). Returns ``None`` when the
        pane is unknown (not yet discovered or already gone).
        """
        return self._pane_cache.get(pane_id)

    async def capture_pane_async(self, pane_id: str) -> PaneSnapshot | None:
        pane = self._pane_cache.get(pane_id)
        if pane is None:
            return None
        rc, content = await self._tmux_async(self._capture_args(pane_id))
        if rc != 0:
            return None
        return self._finalize_capture(pane, content)

    async def capture_cursor_async(
        self, pane_id: str
    ) -> tuple[int, int, bool, int] | None:
        """Return the pane cursor as ``(row, col, visible, style)`` or ``None``.

        Used by the applink push loop (t822_8) to populate the ``cursor`` field of
        a ``keyframe`` (``capture-pane`` carries no cursor). ``row``/``col`` are
        the cursor's 0-based position within the visible pane; ``visible`` from
        ``cursor_flag``; ``style`` is block (``0``) in Stage 1 (tmux exposes no
        portable cursor-shape field here).
        """
        rc, out = await self._tmux_async([
            "display-message", "-p", "-t", pane_id,
            "-F", "#{cursor_y} #{cursor_x} #{cursor_flag}",
        ])
        if rc != 0:
            return None
        parts = out.strip().split()
        if len(parts) < 3:
            return None
        try:
            return (int(parts[0]), int(parts[1]), parts[2] == "1", 0)
        except ValueError:
            return None

    def _clean_stale(self, current_ids: set[str]) -> None:
        stale = [pid for pid in self._last_content if pid not in current_ids]
        for pid in stale:
            del self._last_content[pid]
            self._last_change_time.pop(pid, None)
            self._pane_cache.pop(pid, None)
        for pid in list(self._compare_mode_overrides):
            if pid not in current_ids:
                self._compare_mode_overrides.pop(pid, None)

    def capture_all(self) -> dict[str, PaneSnapshot]:
        panes = self.discover_panes()
        self._clean_stale({p.pane_id for p in panes})

        snapshots: dict[str, PaneSnapshot] = {}
        for pane in panes:
            snap = self.capture_pane(pane.pane_id)
            if snap is not None:
                snapshots[pane.pane_id] = snap
        return snapshots

    async def capture_all_async(self) -> dict[str, PaneSnapshot]:
        panes = await self.discover_panes_async()
        self._clean_stale({p.pane_id for p in panes})

        # Capture all panes concurrently; skip any that error out.
        results = await asyncio.gather(
            *(self.capture_pane_async(p.pane_id) for p in panes),
            return_exceptions=True,
        )
        snapshots: dict[str, PaneSnapshot] = {}
        for pane, snap in zip(panes, results):
            if isinstance(snap, PaneSnapshot):
                snapshots[pane.pane_id] = snap
        return snapshots

    def send_enter(self, pane_id: str) -> bool:
        rc, _ = self.tmux_run(["send-keys", "-t", pane_id, "Enter"])
        return rc == 0

    def send_keys(self, pane_id: str, keys: str, literal: bool = False) -> bool:
        """Send arbitrary key(s) to a tmux pane.

        If literal=True, uses -l flag to send raw text without interpretation.
        If literal=False, sends as tmux key name (Enter, Up, C-c, etc.).
        """
        cmd = ["send-keys", "-t", pane_id]
        if literal:
            cmd.append("-l")
        cmd.append(keys)
        rc, _ = self.tmux_run(cmd)
        return rc == 0

    def forward_key(
        self, pane_id: str, key: str, character: str | None = None
    ) -> bool:
        """Translate an abstract key name and forward it to a tmux pane.

        Backs both the desktop preview-zone key forwarding and the applink
        ``forward_key`` verb (t822_7). Returns ``False`` when the key is
        unmappable (no tmux equivalent).
        """
        translated = translate_key(key, character)
        if translated is None:
            return False
        keys, literal = translated
        return self.send_keys(pane_id, keys, literal=literal)

    def switch_to_pane(self, pane_id: str, prefer_companion: bool = False) -> bool:
        pane = self._pane_cache.get(pane_id)
        if pane is None:
            return False
        # Cross-session: teleport via the shared primitive. `prefer_companion`
        # is intentionally ignored — companion lookup is an intra-session UX
        # affordance (the minimonitor lives in the same window as its agent).
        if (
            self.multi_session
            and pane.session_name
            and pane.session_name != self.session
        ):
            return switch_to_pane_anywhere(pane_id)
        # Same-session: existing companion-aware path.
        target_session = pane.session_name or self.session
        self.tmux_run([
            "select-window", "-t",
            tmux_window_target(target_session, pane.window_index),
        ])
        target_pane = pane_id
        if prefer_companion:
            companion = self.find_companion_pane_id(
                pane.window_index, target_session
            )
            if companion:
                target_pane = companion
        rc, _ = self.tmux_run(["select-pane", "-t", target_pane])
        return rc == 0

    def find_companion_pane_id(
        self, window_index: str, session: str | None = None
    ) -> str | None:
        """Find the minimonitor/companion pane ID in a given window."""
        target_session = session if session is not None else self.session
        fmt = "#{pane_id}\t#{pane_pid}"
        rc, stdout = self.tmux_run([
            "list-panes", "-t",
            tmux_window_target(target_session, window_index), "-F", fmt,
        ])
        if rc != 0:
            return None
        for line in stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) != 2:
                continue
            pane_id_str, pid_str = parts
            try:
                pid = int(pid_str)
            except ValueError:
                continue
            if _is_companion_process(pid):
                return pane_id_str
        return None

    def kill_pane(self, pane_id: str) -> bool:
        """Kill a tmux pane by its ID."""
        rc, _ = self.tmux_run(["kill-pane", "-t", pane_id])
        if rc == 0:
            self._pane_cache.pop(pane_id, None)
            self._last_content.pop(pane_id, None)
            self._last_change_time.pop(pane_id, None)
            return True
        return False

    def kill_window(self, pane_id: str) -> bool:
        """Kill the entire tmux window containing the given pane."""
        rc, _ = self.tmux_run(["kill-window", "-t", pane_id])
        if rc == 0:
            self._pane_cache.pop(pane_id, None)
            self._last_content.pop(pane_id, None)
            self._last_change_time.pop(pane_id, None)
            return True
        return False

    def kill_agent_pane_smart(self, pane_id: str) -> tuple[bool, bool]:
        """Kill an agent pane, collapsing the window if it was the last agent.

        Returns (ok, killed_window). If no other agent panes remain in the
        window after removing this one, the whole window is killed — which
        also cleans up any companion minimonitor pane. Otherwise only the
        requested pane is killed, preserving the minimonitor for surviving
        siblings.
        """
        pane = self._pane_cache.get(pane_id)
        if pane is None:
            return self.kill_pane(pane_id), False

        # Use the pane's own session so cross-session kills target the right
        # window; fall back to self.session for legacy single-session paths.
        target_session = pane.session_name or self.session
        window_target = tmux_window_target(target_session, pane.window_index)
        rc, stdout = self.tmux_run([
            "list-panes", "-t", window_target,
            "-F", "#{pane_id}\t#{pane_pid}\t#{@aitask_shadow_target}",
        ])
        if rc != 0:
            return self.kill_pane(pane_id), False
        records: list[tuple[str, bool]] = []
        for line in stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            other_id, pid_str, shadow_target = parts
            try:
                pid = int(pid_str)
            except ValueError:
                continue
            # A pane is a helper (does NOT keep the window alive) when it is a
            # companion (minimonitor/monitor) OR a shadow bound to an agent.
            is_helper = is_shadow_target(shadow_target) or _is_companion_process(pid)
            records.append((other_id, is_helper))
        others = count_other_real_agents(records, pane_id)

        if others == 0:
            return self.kill_window(pane_id), True
        return self.kill_pane(pane_id), False

    def spawn_tui(self, tui_name: str) -> bool:
        rc, _ = self.tmux_run([
            "new-window", "-t", tmux_window_target(self.session, ""),
            "-n", tui_name, f"ait {tui_name}",
        ])
        return rc == 0

    def get_running_tuis(self) -> set[str]:
        return {
            pane.window_name
            for pane in self._pane_cache.values()
            if pane.category == PaneCategory.TUI
        }

    def get_missing_tuis(self) -> set[str]:
        return self.tui_names - self.get_running_tuis()


def load_monitor_config(project_root: Path) -> dict:
    """Load monitor config from project_config.yaml tmux.monitor section.

    Returns dict suitable for passing as kwargs to TmuxMonitor (minus session).
    """
    defaults = {
        "capture_lines": 200,
        "idle_threshold": 5.0,
        "agent_prefixes": list(DEFAULT_AGENT_PREFIXES),
        "tui_names": set(DEFAULT_TUI_NAMES),
        "compare_mode_default": DEFAULT_COMPARE_MODE,
    }
    config_path = project_root / "aitasks" / "metadata" / "project_config.yaml"
    if not config_path.is_file():
        return defaults
    try:
        import yaml
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        monitor = data.get("tmux", {}).get("monitor", {})
        if not isinstance(monitor, dict):
            return defaults
        if "capture_lines" in monitor:
            defaults["capture_lines"] = int(monitor["capture_lines"])
        if "idle_threshold_seconds" in monitor:
            defaults["idle_threshold"] = float(monitor["idle_threshold_seconds"])
        if "agent_window_prefixes" in monitor:
            defaults["agent_prefixes"] = list(monitor["agent_window_prefixes"])
        if "tui_window_names" in monitor:
            # Merge with registry defaults so new framework TUIs are never
            # masked by a stale override list in project_config.yaml.
            defaults["tui_names"] = set(TUI_NAMES) | set(monitor["tui_window_names"])
        if "compare_mode_default" in monitor:
            val = str(monitor["compare_mode_default"])
            if val in COMPARE_MODES:
                defaults["compare_mode_default"] = val
    except Exception:
        pass
    return defaults


# -- Task context --------------------------------------------------------------

_TASK_ID_RE = re.compile(r'^agent-(?:pick|qa)-(\d+(?:_\d+)?)$')


def task_id_from_window_name(window_name: str) -> str | None:
    """Pure pane→task mapping: extract the task id from an agent window name.

    Returns the captured id (e.g. ``"100"`` or ``"100_1"``) or ``None`` when the
    window name is not an ``agent-(pick|qa)-<id>`` window. Kept import-free and
    side-effect-free so it can be unit-tested directly.
    """
    m = _TASK_ID_RE.match(window_name)
    return m.group(1) if m else None


@dataclass
class TaskInfo:
    """Resolved task metadata and content for display in the monitor."""
    task_id: str
    task_file: str
    title: str
    priority: str
    effort: str
    issue_type: str
    status: str
    body: str
    plan_content: str | None
    # Absolute path to the task file. ``task_file`` stays relative to the owning
    # project root (display value, asserted by tests); ``task_file_abs`` is what
    # gate-ledger parsing must use, since a relative path is cwd-dependent and
    # wrong under cross-session / multi-project monitoring. Defaulted so the one
    # keyword-arg test stub keeps constructing TaskInfo unchanged.
    task_file_abs: str = ""


class GateSummaryCache:
    """Per-refresh compact gate-summary cache for the monitor TUIs.

    Mirrors the board's gate cache (``aitask_board.TaskManager.gate_state_for``):
    cleared each refresh cycle so a live-growing ledger updates, while a re-read
    is avoided when the same card is formatted twice within one frame. Fails
    closed to ``""`` (no column) on any parse/IO error — a malformed ledger must
    never break the monitor. Keyed by the resolved **absolute** task-file path
    (``TaskInfo.task_file_abs``), so it is correct under cross-session /
    multi-project monitoring regardless of the process's working directory.
    """

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}

    def clear(self) -> None:
        self._cache.clear()

    def summary_for(self, info: "TaskInfo | None") -> str:
        # Key + parse off the ABSOLUTE path, never the relative ``task_file`` —
        # the relative form is cwd-dependent and resolves wrong in cross-session
        # monitor mode.
        if info is None or not info.task_file_abs:
            return ""
        key = info.task_file_abs
        if key in self._cache:
            return self._cache[key]
        summary = ""
        try:
            # Cheap prefilter on the already-loaded body before the full parse;
            # the full state re-reads the file (matches the board: has_ledger
            # from content, state from filepath).
            if gate_ledger.has_gate_markers(info.body or ""):
                state = gate_ledger.read_task_gate_state(info.task_file_abs)
                summary = gate_ledger.compact_gate_summary(state)
        except Exception:
            summary = ""
        self._cache[key] = summary
        return summary


class TaskInfoCache:
    """Cache for resolved task info — avoids file I/O on every refresh.

    Cross-project aware: when callers provide a tmux ``session_name`` the cache
    resolves the task file from the project root that owns that session (via
    ``session_to_project``). An empty/unknown ``session_name`` falls back to
    the local ``project_root`` — preserving single-session behaviour.
    """

    def __init__(
        self,
        project_root: Path,
        session_to_project: dict[str, Path] | None = None,
    ):
        self._project_root = project_root
        self._session_to_project: dict[str, Path] = dict(session_to_project or {})
        # Keyed by (session_name, task_id) so two projects can both have t100
        # without clobbering each other.
        self._cache: dict[tuple[str, str], TaskInfo | None] = {}
        self._window_to_task_id: dict[str, str | None] = {}
        # Pane-keyed task-id cache (t986). Keyed by pane_id so panes sharing a
        # window are never conflated; see get_task_id_for_pane.
        self._pane_to_task_id: dict[str, str | None] = {}

    def update_session_mapping(self, mapping: dict[str, Path]) -> None:
        """Replace the session→project_root mapping (idempotent).

        Clears the resolved-task cache when the mapping changes, since entries
        for a session may have been resolved against a stale (or absent)
        mapping and now point at the wrong project's task data.
        """
        if mapping != self._session_to_project:
            self._session_to_project = dict(mapping)
            self._cache.clear()

    def _root_for_session(self, session_name: str) -> Path:
        """Resolve the project root for a tmux session, falling back to local."""
        if session_name and session_name in self._session_to_project:
            return self._session_to_project[session_name]
        return self._project_root

    def get_task_id(self, window_name: str) -> str | None:
        """Extract task ID from agent window name. Cached.

        Window-keyed; retained for callers that only have a window name. Pane
        display sites should prefer :meth:`get_task_id_for_pane`.
        """
        if window_name not in self._window_to_task_id:
            self._window_to_task_id[window_name] = task_id_from_window_name(window_name)
        return self._window_to_task_id[window_name]

    def get_task_id_for_pane(self, pane: TmuxPaneInfo) -> str | None:
        """Resolve the task id for a specific pane, cached by ``pane_id``.

        Pane-keyed rather than window-keyed (t986): a tmux window may hold more
        than one pane (an agent plus a shadow/minimonitor helper, or — in
        future — more than one agent), so conflating panes by their shared
        window name is unsafe. The task id is still *derived* from the agent
        window name today; keying the cache on ``pane_id`` is the seam a future
        per-pane task source can slot into without touching call sites. Helper
        panes do not reach this method (discovery already drops shadow/companion
        panes), and a stray helper window name resolves to ``None`` anyway.
        """
        pane_id = pane.pane_id
        if pane_id not in self._pane_to_task_id:
            self._pane_to_task_id[pane_id] = task_id_from_window_name(pane.window_name)
        return self._pane_to_task_id[pane_id]

    def get_task_info(
        self, task_id: str, session_name: str = ""
    ) -> TaskInfo | None:
        """Resolve task info from task ID. Cached after first lookup."""
        key = (session_name, task_id)
        if key not in self._cache:
            self._cache[key] = self._resolve(task_id, session_name)
        return self._cache[key]

    def invalidate(self, task_id: str, session_name: str = "") -> None:
        self._cache.pop((session_name, task_id), None)

    def get_parent_id(self, task_id: str) -> str | None:
        """Extract parent task number from a child task ID."""
        if "_" not in task_id:
            return None
        return task_id.split("_", 1)[0]

    def find_next_sibling(
        self, task_id: str, session_name: str = ""
    ) -> tuple[str, str] | None:
        """Find the next Ready sibling/child task.

        If task_id is a child (e.g. "123_4"), returns the next Ready sibling
        under the same parent, excluding the current task. If task_id is a
        parent (e.g. "123"), returns the first Ready child of that parent.

        Returns (task_id, title) or None.
        """
        if "_" in task_id:
            parent, _child = task_id.split("_", 1)
            exclude_id: str | None = task_id
        else:
            parent = task_id
            exclude_id = None

        root = self._root_for_session(session_name)
        search_dir = root / "aitasks" / f"t{parent}"
        if not search_dir.is_dir():
            return None

        candidates = []
        child_re = re.compile(rf'^t{re.escape(parent)}_(\d+)_')
        for path in sorted(search_dir.glob(f"t{parent}_*_*.md")):
            m = child_re.match(path.stem)
            if not m:
                continue
            sib_child = m.group(1)
            sib_id = f"{parent}_{sib_child}"
            if exclude_id is not None and sib_id == exclude_id:
                continue
            try:
                raw = path.read_text(encoding="utf-8")
            except OSError:
                continue
            parsed = parse_frontmatter(raw)
            if parsed is None:
                continue
            metadata, body, _ = parsed
            if str(metadata.get("status", "")).strip() != "Ready":
                continue
            title = None
            for line in body.splitlines():
                ls = line.strip()
                if ls.startswith("# "):
                    title = ls[2:].strip()
                    break
            if not title:
                parts = path.stem.split("_", 2)
                title = parts[2].replace("_", " ") if len(parts) > 2 else path.stem
            candidates.append((int(sib_child), sib_id, title))

        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0])
        _, sib_id, title = candidates[0]
        return (sib_id, title)

    def find_ready_siblings(
        self, task_id: str, session_name: str = ""
    ) -> list[tuple[str, str, list[str]]]:
        """List pending Ready siblings of ``task_id``.

        Returns rows of ``(sib_id, title, blocking_sibling_ids)`` sorted by
        child number ascending. ``blocking_sibling_ids`` lists sibling ids
        under the same parent that appear in this sibling's ``depends``
        field and are not yet ``Done`` — so callers can show a
        "blocked by tX" hint while still allowing the row to be picked.

        Same parent/exclude rules as ``find_next_sibling``: when ``task_id``
        is a child, the current sibling is excluded; when ``task_id`` is a
        parent, all Ready children are returned.
        """
        if "_" in task_id:
            parent, _child = task_id.split("_", 1)
            exclude_id: str | None = task_id
        else:
            parent = task_id
            exclude_id = None

        root = self._root_for_session(session_name)
        search_dir = root / "aitasks" / f"t{parent}"
        if not search_dir.is_dir():
            return []

        # First pass: collect every sibling's status + parsed metadata so
        # the second pass can compute "blocked by sibling" without re-reading.
        sib_status: dict[str, str] = {}
        parsed_rows: list[tuple[int, str, str, list[str]]] = []
        child_re = re.compile(rf'^t{re.escape(parent)}_(\d+)_')
        for path in sorted(search_dir.glob(f"t{parent}_*_*.md")):
            m = child_re.match(path.stem)
            if not m:
                continue
            sib_child = m.group(1)
            sib_id = f"{parent}_{sib_child}"
            try:
                raw = path.read_text(encoding="utf-8")
            except OSError:
                continue
            parsed = parse_frontmatter(raw)
            if parsed is None:
                continue
            metadata, body, _ = parsed
            status = str(metadata.get("status", "")).strip()
            sib_status[sib_id] = status
            if status != "Ready":
                continue
            if exclude_id is not None and sib_id == exclude_id:
                continue
            title = None
            for line in body.splitlines():
                ls = line.strip()
                if ls.startswith("# "):
                    title = ls[2:].strip()
                    break
            if not title:
                parts = path.stem.split("_", 2)
                title = parts[2].replace("_", " ") if len(parts) > 2 else path.stem
            depends_raw = metadata.get("depends", []) or []
            # Normalize "t42" / "42" / 42 to bare numeric strings.
            depends_norm = [str(d).lstrip("t") for d in depends_raw]
            parsed_rows.append((int(sib_child), sib_id, title, depends_norm))

        if not parsed_rows:
            return []

        # Second pass: a blocker is a depends entry whose normalized form
        # matches "<parent>_<n>" of another sibling whose status is not Done.
        rows: list[tuple[str, str, list[str]]] = []
        for _child_num, sib_id, title, depends_norm in sorted(parsed_rows, key=lambda r: r[0]):
            blocking: list[str] = []
            for dep in depends_norm:
                # Only sibling deps shaped as "<parent>_<n>" are relevant
                # here; cross-parent deps are not surfaced (the "blocked by
                # sibling" hint is intentionally scoped to siblings).
                if not dep.startswith(f"{parent}_"):
                    continue
                if sib_status.get(dep, "") != "Done":
                    blocking.append(dep)
            rows.append((sib_id, title, blocking))
        return rows

    def _resolve(self, task_id: str, session_name: str = "") -> TaskInfo | None:
        """Look up task file and parse its content. Pure Python, no subprocess.

        Searches both the active location (``aitasks/``) and the archived
        location (``aitasks/archived/``) so that monitor TUIs can keep
        showing task info for an agent pane whose task has already been
        archived. Active dirs win when the same id is present in both.
        Tasks bundled into ``aitasks/archived/_b0/old<N>.tar.zst`` are not
        extracted — those agents are old enough that lookup misses are
        acceptable.
        """
        root = self._root_for_session(session_name)
        tasks_dir = root / "aitasks"
        plans_dir = root / "aiplans"
        archived_tasks_dir = tasks_dir / "archived"
        archived_plans_dir = plans_dir / "archived"

        if "_" in task_id:
            parent, child = task_id.split("_", 1)
            pattern = f"t{parent}_{child}_*.md"
            search_dirs = (
                tasks_dir / f"t{parent}",
                archived_tasks_dir / f"t{parent}",
            )
        else:
            pattern = f"t{task_id}_*.md"
            search_dirs = (tasks_dir, archived_tasks_dir)

        task_path = None
        for d in search_dirs:
            if not d.is_dir():
                continue
            matches = list(d.glob(pattern))
            if matches:
                task_path = matches[0]
                break
        if task_path is None:
            return None

        try:
            raw = task_path.read_text(encoding="utf-8")
        except OSError:
            return None

        parsed = parse_frontmatter(raw)
        if parsed is None:
            return None
        metadata, body, _ = parsed

        # Extract title: first markdown heading or derive from filename
        title = None
        for line in body.splitlines():
            line_s = line.strip()
            if line_s.startswith("# "):
                title = line_s[2:].strip()
                break
        if not title:
            stem = task_path.stem
            parts = stem.split("_", 1)
            title = parts[1].replace("_", " ") if len(parts) > 1 else stem

        # Find plan file (active dir first, archived as fallback).
        plan_content = None
        if "_" in task_id:
            parent, child = task_id.split("_", 1)
            plan_pattern = f"p{parent}_{child}_*.md"
            plan_dirs = (
                plans_dir / f"p{parent}",
                archived_plans_dir / f"p{parent}",
            )
        else:
            plan_pattern = f"p{task_id}_*.md"
            plan_dirs = (plans_dir, archived_plans_dir)

        for pd in plan_dirs:
            if not pd.is_dir():
                continue
            plan_matches = list(pd.glob(plan_pattern))
            if not plan_matches:
                continue
            try:
                plan_raw = plan_matches[0].read_text(encoding="utf-8")
                if plan_raw.startswith("---"):
                    fm_parts = plan_raw.split("---", 2)
                    if len(fm_parts) >= 3:
                        plan_content = fm_parts[2].strip()
                    else:
                        plan_content = plan_raw
                else:
                    plan_content = plan_raw
            except OSError:
                pass
            break

        return TaskInfo(
            task_id=task_id,
            task_file=str(task_path.relative_to(root)),
            title=title,
            priority=str(metadata.get("priority", "")),
            effort=str(metadata.get("effort", "")),
            issue_type=str(metadata.get("issue_type", "")),
            status=str(metadata.get("status", "")),
            body=body,
            plan_content=plan_content,
            task_file_abs=str(task_path),
        )
