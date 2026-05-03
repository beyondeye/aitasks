"""tmux_control - Persistent `tmux -C` (control mode) client.

Opens a single long-lived `tmux -C attach` connection to a session, lets
callers issue commands via `request()`, parses `%begin/%end/%error` reply
blocks, and demultiplexes responses back to per-call futures.

Used by `tmux_monitor.py` to replace per-tick `subprocess` spawns in the
async hot path with one persistent connection. See
`aiplans/p719/p719_1_control_client_module.md` for the design rationale.

Key design choices:

- Spawned with `-f no-output,ignore-size`. `no-output` is load-bearing —
  without it the client receives every byte of pane output as `%output`
  async events, which adds work instead of removing it.
- StreamReader buffer raised to 4 MiB so a dense `capture-pane -e` can't
  raise `LimitOverrunError` only under load.
- Requests serialize through a FIFO `deque[Future]` + `asyncio.Lock`. The
  cmd_id in `%begin` is server-assigned (we only learn it by reading the
  response), so per-id demultiplexing buys nothing over FIFO ordering,
  and a write-lock is required anyway to prevent interleaved bytes on
  stdin.
- On EOF / `%exit` / broken pipe / timeout: mark `is_alive = False`,
  resolve all queued and in-flight futures with `(-1, "")`, do not
  auto-restart. Callers (e.g., `TmuxMonitor._tmux_async`) check
  `is_alive` and fall back to subprocess.
"""
from __future__ import annotations

import asyncio
import collections
import contextlib
import re
import threading
from typing import Optional

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

    def __init__(self, session: str, command_timeout: float = 5.0):
        self.session = session
        self.command_timeout = command_timeout
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
                "tmux", "-C", "attach", "-t", self.session,
                "-f", "no-output,ignore-size",
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

        rc semantics mirror `tmux_monitor._run_tmux_async`:
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

    def __init__(self, session: str, command_timeout: float = 5.0):
        self.session = session
        self.command_timeout = command_timeout
        self._client: Optional[TmuxControlClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()

    @property
    def is_alive(self) -> bool:
        return self._client is not None and self._client.is_alive

    def start(self) -> bool:
        """Start bg thread + loop, then start the client on it.

        Returns True iff the client successfully attached. Idempotent: a
        second call while already started returns the current `is_alive`
        without spawning a second thread.
        """
        if self._thread is not None:
            return self.is_alive
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
        client = TmuxControlClient(self.session, self.command_timeout)
        cf = asyncio.run_coroutine_threadsafe(client.start(), self._loop)
        try:
            ok = cf.result(timeout=_BACKEND_START_TIMEOUT)
        except Exception:
            ok = False
        if ok:
            self._client = client
            return True
        # Client did not attach. Tear down the thread so we don't leak it.
        self.stop()
        return False

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

        Idempotent. Safe to call when start() failed partway through.
        """
        loop = self._loop
        client = self._client
        thread = self._thread
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
        self._ready.clear()

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
