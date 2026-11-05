"""status_recording - recorder, replayer and checker for monitor status streams.

A recording (``.jsonl``) is a ``recording`` header line followed by the stream a
subscriber received: ``welcome``, ``snapshot``, then deltas with contiguous
``gen``. It always carries FULL content (recorded with ``content:"all"``), so a
replay subscriber can select any pane later. See
``aidocs/framework/monitor_status_protocol.md`` ("Recording format",
"Recorder and replayer").

- :func:`record_connect` — a socket client that saves a server's stream. Every
  stop path goes through one completion guard: ``<out>`` is published only when
  a welcome and an initial snapshot were received and every delta applied.
- :class:`ReplayServer` — serves a recording over a Unix socket, one playback
  per connection, with the protocol's resync and ordering rules.
- :func:`check_recording` — validates a recording file.

CLI::

    python3 .aitask-scripts/monitor/status_recording.py check FILE
    python3 .aitask-scripts/monitor/status_recording.py replay FILE --socket SOCK [--speed X] [--exit-at-end]
    python3 .aitask-scripts/monitor/status_recording.py record --connect SOCK --out FILE [--duration S] [--max-deltas N]
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import math
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
for _extra in (_SCRIPTS_DIR / "lib", _SCRIPTS_DIR):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

try:  # imported as part of the `monitor` package
    from . import status_protocol as sp
except ImportError:  # run as a script
    import status_protocol as sp  # noqa: E402

from framework_version import read_installed_version  # noqa: E402


class RecordingError(sp.ProtocolError):
    """A recording file that violates the recording format."""


# ---------------------------------------------------------------------------
# Reading and checking
# ---------------------------------------------------------------------------

@dataclass
class Recording:
    """A parsed recording. ``lines`` / ``messages`` hold everything after the
    header, in file order: the welcome, the snapshot, then the deltas."""
    header: dict
    lines: list = field(default_factory=list)
    messages: list = field(default_factory=list)
    path: str | None = None

    @property
    def welcome(self) -> dict:
        return self.messages[0]

    @property
    def snapshot(self) -> dict:
        return self.messages[1]

    @property
    def snapshot_line(self) -> bytes:
        return self.lines[1]

    @property
    def deltas(self) -> list:
        return self.messages[2:]

    @property
    def delta_lines(self) -> list:
        return self.lines[2:]


def _check_versions(header: dict, welcome: dict, where: str) -> None:
    """Revision and protocol gates for a recording, shared by every entry
    point (a parsed file, a directly supplied ``Recording``).

    The recorded FRAMEWORK version may be anything — replaying an old
    recording is the point of a fixture — but the file revision and the
    protocol must be ones this codec speaks, and the header must describe the
    welcome it precedes."""
    if header.get("rev") != sp.RECORDING_REV:
        raise RecordingError(f"{where}:1: unsupported recording rev {header.get('rev')!r} "
                             f"(this codec reads rev {sp.RECORDING_REV})")
    if header.get("proto") != sp.PROTO:
        raise RecordingError(f"{where}:1: unsupported proto {header.get('proto')!r} "
                             f"(this codec speaks proto {sp.PROTO})")
    if welcome.get("proto") != header["proto"]:
        raise RecordingError(f"{where}:2: welcome proto {welcome.get('proto')!r} does not "
                             f"match the header's {header['proto']!r}")
    if welcome.get("version") != header.get("version"):
        raise RecordingError(f"{where}:2: welcome version {welcome.get('version')!r} does not "
                             f"match the header's {header.get('version')!r}")


def parse_recording(data: bytes, *, path: str | None = None) -> Recording:
    """Parse and order-check a recording's bytes (no stream application)."""
    where = path or "<recording>"
    raw_lines = data.splitlines(keepends=True)
    if not raw_lines:
        raise RecordingError(f"{where}: empty recording")
    if not raw_lines[-1].endswith(b"\n"):
        raise RecordingError(f"{where}: last line is not terminated by a newline")
    decoded = []
    for number, raw in enumerate(raw_lines, start=1):
        try:
            decoded.append(sp.decode(raw, direction=sp.RECORDING))
        except sp.ProtocolError as exc:
            raise RecordingError(f"{where}:{number}: {exc}") from None
    expected = ["recording", "welcome", "snapshot"]
    for number, (want, msg) in enumerate(zip(expected, decoded), start=1):
        if msg["type"] != want:
            raise RecordingError(f"{where}:{number}: expected {want!r}, got {msg['type']!r}")
    if len(decoded) < 3:
        raise RecordingError(f"{where}: a recording needs a header, a welcome and a snapshot")
    for number, msg in enumerate(decoded[3:], start=4):
        if msg["type"] != "delta":
            raise RecordingError(f"{where}:{number}: expected 'delta', got {msg['type']!r}")
    _check_versions(decoded[0], decoded[1], where)
    return Recording(header=decoded[0], lines=list(raw_lines[1:]),
                     messages=decoded[1:], path=path)


def read_recording(path) -> Recording:
    path = str(path)
    with open(path, "rb") as fh:
        return parse_recording(fh.read(), path=path)


def check_recording(path) -> dict:
    """Validate a recording file and return a summary.

    Checks the header/welcome/snapshot/delta order, decodes every line, applies
    the stream through a full-content :class:`~status_protocol.StreamState`
    (contiguous ``gen``; ``content`` on every full record) and refuses a stale
    delta — a recording is strictly contiguous."""
    rec = path if isinstance(path, Recording) else read_recording(path)
    where = rec.path or "<recording>"
    types = [rec.header.get("type")] + [m.get("type") for m in rec.messages]
    if types[:3] != ["recording", "welcome", "snapshot"] or any(
            t != "delta" for t in types[3:]):
        raise RecordingError(f"{where}: expected header, welcome, snapshot, then deltas; "
                             f"got {types[:4]}…")
    if len(rec.lines) != len(rec.messages):
        raise RecordingError(f"{where}: {len(rec.lines)} lines for {len(rec.messages)} messages")
    _check_versions(rec.header, rec.welcome, where)
    state = sp.StreamState(require_content=True)
    kinds: set = set()
    sessions: set = set()
    pane_ids: set = set()
    shadows = 0
    for number, msg in enumerate(rec.messages[1:], start=3):
        try:
            applied = state.apply(msg)
        except sp.ProtocolError as exc:
            raise RecordingError(f"{where}:{number}: {exc}") from None
        if applied is None:
            raise RecordingError(f"{where}:{number}: stale delta gen {msg['gen']}")
        for pane_id, record in state.records().items():
            pane_ids.add(pane_id)
            if record["awaiting_input"]:
                kinds.add(record["awaiting_input_kind"])
        sessions.update(state.sessions)
        shadows = max(shadows, len(state.shadow_records()))
    return {
        "path": rec.path,
        "proto": rec.header["proto"],
        "version": rec.header["version"],
        "source": rec.header["source"],
        "gen_first": rec.snapshot["gen"],
        "gen_last": state.gen,
        "deltas": len(rec.deltas),
        "panes_seen": len(pane_ids),
        "sessions": sorted(sessions),
        "awaiting_kinds": sorted(kinds),
        "max_shadows": shadows,
    }


def recording_header(*, version: str, source: str, created: float,
                     note: str | None = None) -> dict:
    header = {
        "type": "recording", "rev": sp.RECORDING_REV, "proto": sp.PROTO,
        "version": version, "source": source, "created": round(created, 3),
    }
    if note:
        header["note"] = note
    return header


def framework_version() -> str:
    return read_installed_version(_SCRIPTS_DIR.parent) or "unknown"


# ---------------------------------------------------------------------------
# Recorder
# ---------------------------------------------------------------------------

@dataclass
class RecordResult:
    published: bool
    path: str | None
    reason: str
    deltas: int = 0
    skipped: int = 0


def _finalize(partial: Path, out: Path, *, got_welcome: bool, got_snapshot: bool,
              error: str | None, stop_reason: str, deltas: int,
              skipped: int) -> RecordResult:
    """The ONE completion guard every recorder stop path passes through.

    ``<out>`` is published only with a welcome, an initial snapshot and no
    error; otherwise the partial file is removed and nothing is published."""
    usable = error is None and got_welcome and got_snapshot
    if not usable:
        with contextlib.suppress(FileNotFoundError):
            partial.unlink()
        if error is not None:
            why = error
        elif not got_welcome:
            why = f"{stop_reason} before the welcome"
        else:
            why = f"{stop_reason} before the snapshot"
        return RecordResult(False, None, f"no usable recording captured: {why}",
                            deltas, skipped)
    os.replace(partial, out)
    return RecordResult(True, str(out), stop_reason, deltas, skipped)


async def record_connect(socket_path, out_path, *, duration: float | None = None,
                         max_deltas: int | None = None,
                         source: str | None = None) -> RecordResult:
    """Record a status server's stream into ``out_path``.

    Subscribes with ``content:"all", include_shadows:true`` — there is no
    content option: a recording always carries full content. Writes to
    ``<out>.partial`` and promotes it only through :func:`_finalize`. A
    cancellation after the snapshot is a clean stop (the recording is
    published) and the ``CancelledError`` still propagates."""
    out = Path(out_path)
    partial = out.with_name(out.name + ".partial")
    state = sp.StreamState(require_content=True)
    got_welcome = got_snapshot = False
    error: str | None = None
    stop_reason = "stopped"
    deltas = skipped = 0
    writer = None
    loop = asyncio.get_running_loop()
    deadline = None if duration is None else loop.time() + duration
    own_version = framework_version()
    fh = open(partial, "wb")
    try:
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(socket_path), limit=sp.MAX_SERVER_LINE_BYTES)
            writer.write(sp.encode({
                "type": "hello", "proto": sp.PROTO, "version": own_version,
                "client": {"kind": "recorder", "pid": os.getpid()},
            }, direction=sp.CLIENT))
            writer.write(sp.encode({
                "type": "subscribe", "content": sp.CONTENT_ALL, "include_shadows": True,
            }, direction=sp.CLIENT))
            await writer.drain()
            while True:
                if max_deltas is not None and got_snapshot and deltas >= max_deltas:
                    stop_reason = "max_deltas reached"
                    break
                timeout = None
                if deadline is not None:
                    timeout = deadline - loop.time()
                    if timeout <= 0:
                        stop_reason = "duration elapsed"
                        break
                try:
                    line = await asyncio.wait_for(sp.read_line(reader), timeout)
                except asyncio.TimeoutError:
                    stop_reason = "duration elapsed"
                    break
                if line is None:
                    stop_reason = "server closed the stream"
                    break
                try:
                    msg = sp.decode(line, direction=sp.SERVER)
                except sp.UnknownMessageType:
                    skipped += 1
                    continue
                kind = msg["type"]
                if kind == "welcome" and not got_welcome:
                    # The handshake gates: the server must speak this proto and
                    # answer for this client's version. (A replayer echoes the
                    # client's version, so replayed recordings of any framework
                    # version still record — their recorded version travels in
                    # welcome.replay.)
                    if msg["proto"] != sp.PROTO:
                        error = (f"proto mismatch: the server speaks proto {msg['proto']}, "
                                 f"this recorder proto {sp.PROTO}")
                        break
                    if msg["version"] != own_version:
                        error = (f"version mismatch: the server answered for version "
                                 f"{msg['version']!r}, this recorder is {own_version!r}")
                        break
                    got_welcome = True
                    header = recording_header(
                        version=msg["version"], created=time.time(),
                        source=source or f"connect:{socket_path}")
                    fh.write(sp.encode(header, direction=sp.RECORDING))
                    fh.write(line)
                elif kind == "error" and not got_snapshot:
                    error = f"server error {msg['code']}: {msg['message']}"
                    break
                elif kind == "snapshot" and got_welcome and not got_snapshot:
                    state.apply(msg)
                    got_snapshot = True
                    fh.write(line)
                elif kind == "snapshot" and got_snapshot:
                    # A server-initiated resync: the recording format holds one
                    # snapshot, and what was recorded so far is complete.
                    stop_reason = "server resynced"
                    break
                elif kind == "delta" and got_snapshot:
                    if state.apply(msg) is None:
                        raise sp.StreamError(f"stale delta gen {msg['gen']}")
                    fh.write(line)
                    deltas += 1
                elif kind in ("welcome", "snapshot", "delta"):
                    error = f"unexpected {kind!r} at this point in the stream"
                    break
                else:
                    skipped += 1
        except asyncio.CancelledError:
            stop_reason = "cancelled"
            raise
        except sp.ProtocolError as exc:
            error = f"{exc.code}: {exc}"
        except OSError as exc:
            error = f"connection failed: {exc}"
        except Exception as exc:  # noqa: BLE001 - never publish after a surprise
            error = f"internal error: {exc!r}"
    finally:
        fh.close()
        if writer is not None:
            writer.close()
            with contextlib.suppress(Exception):
                await asyncio.shield(writer.wait_closed())
        result = _finalize(partial, out, got_welcome=got_welcome,
                           got_snapshot=got_snapshot, error=error,
                           stop_reason=stop_reason, deltas=deltas, skipped=skipped)
    return result


# ---------------------------------------------------------------------------
# Replayer
# ---------------------------------------------------------------------------

def check_speed(speed) -> float:
    """A replay speed: a finite number >= 0 (``0`` = unpaced playback)."""
    if (type(speed) is bool or not isinstance(speed, (int, float))
            or not math.isfinite(speed) or speed < 0):
        raise ValueError(f"speed must be a finite number >= 0, got {speed!r}")
    return float(speed)


def replay_delays(recording: Recording, speed: float) -> list[float]:
    """Seconds to wait before each delta: its ``ts`` minus the previous
    message's, divided by ``speed`` (``0`` = no waiting). Never negative."""
    speed = check_speed(speed)
    delays = []
    prev = recording.snapshot["ts"]
    for msg in recording.deltas:
        gap = max(0.0, msg["ts"] - prev)
        prev = msg["ts"]
        delays.append(0.0 if speed == 0 else gap / speed)
    return delays


async def _sleep_pacer(_index: int, delay: float) -> None:
    if delay > 0:
        await asyncio.sleep(delay)


#: The ``capture`` tail rule, shared with the status server (t2037_1).
_tail = sp.tail_lines


class _ReplayConnection:
    """One client's playback. ONE outbound queue drained by one writer task;
    the request handler and the playback task share ``lock`` across "read
    state + enqueue", so every reply falls between two deltas."""

    def __init__(self, server: "ReplayServer", reader, writer):
        self.server = server
        self.reader = reader
        self.writer = writer
        self.state = sp.StreamState()
        self.content = sp.CONTENT_ALL
        self.include_shadows = True
        self.hello_done = False
        self.playback: asyncio.Task | None = None
        self.lock = asyncio.Lock()
        self.outq: asyncio.Queue = asyncio.Queue()
        #: Set when the server side ends the connection (playback failure, or
        #: the end of the recording under exit_at_end): the reader stops.
        self.closing = asyncio.Event()

    def _full_view(self) -> bool:
        return self.content == sp.CONTENT_ALL and self.include_shadows

    def _send(self, msg: dict) -> None:
        self.outq.put_nowait(sp.encode(msg, direction=sp.SERVER))

    def _send_error(self, code: str, message: str, *, id=None, request=None,
                    **extra) -> None:
        """An error reply. Echoed fields are bounded: ``message`` is clipped,
        ``request`` is sent only when it fits its schema — an error reply must
        never itself fail to encode."""
        msg = {"type": "error", "ts": round(time.time(), 3), "code": code,
               "message": message[:sp.MAX_TEXT_CHARS]}
        if id is not None:
            msg["id"] = id
        if type(request) is str and 0 < len(request) <= 64:
            msg["request"] = request
        msg.update(extra)
        self._send(msg)

    def _send_result(self, request: str, *, id=None, **extra) -> None:
        msg = {"type": "result", "ts": round(time.time(), 3), "request": request}
        if id is not None:
            msg["id"] = id
        msg.update(extra)
        self._send(msg)

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
            self.writer.close()
            with contextlib.suppress(Exception):
                await self.writer.wait_closed()

    async def _playback_loop(self) -> None:
        try:
            await self._play()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - surface, never hang the client
            # A recording is validated before it is served, so this is a
            # defect; the client is told and the connection closes rather than
            # leaving it waiting for deltas that will never come.
            async with self.lock:
                self._send_error("internal", f"replay stopped: {exc}")
            self.outq.put_nowait(None)
            self.closing.set()

    async def _play(self) -> None:
        rec = self.server.recording
        delays = replay_delays(rec, self.server.speed)
        for index, (raw, msg) in enumerate(zip(rec.delta_lines, rec.deltas)):
            await self.server.pacer(index, delays[index])
            async with self.lock:
                if self.state.apply(msg) is None:
                    raise sp.StreamError(f"stale delta gen {msg['gen']} in the recording")
                if self._full_view():
                    self.outq.put_nowait(raw)
                else:
                    self._send(sp.filter_message(
                        msg, content=self.content, include_shadows=self.include_shadows))
        if self.server.exit_at_end:
            self.outq.put_nowait(None)
            self.closing.set()

    def _record_by_pane_id(self, pane_id: str):
        """The reconstructed record whose ``pane.pane_id`` is ``pane_id`` —
        an ordinary pane or a shadow (shadows are keyed by the FOLLOWED pane
        id, so they are matched on their own id, never on the key)."""
        if not self.state.subscribed:
            return None
        record = self.state.records().get(pane_id)
        if record is not None:
            return record
        for shadow in self.state.shadow_records().values():
            if shadow["pane"]["pane_id"] == pane_id:
                return shadow
        return None

    def _apply_settings(self, msg: dict) -> None:
        if "content" in msg:
            self.content = msg["content"]
        if "include_shadows" in msg:
            self.include_shadows = msg["include_shadows"]

    def _current_snapshot(self, id=None) -> dict:
        return sp.snapshot_message(
            self.state.frame(), gen=self.state.gen, ts=self.state.ts,
            content=self.content, include_shadows=self.include_shadows, id=id)

    async def _handle(self, msg: dict) -> bool:
        """Handle one decoded request. Returns False to close the connection."""
        kind = msg["type"]
        rid = msg.get("id")
        if kind == "hello":
            if self.hello_done:
                self._send_error("bad_message", "hello already received")
                return True
            if msg["proto"] != sp.PROTO:
                self._send_error("proto_mismatch",
                                 f"replayer speaks proto {sp.PROTO}",
                                 server_proto=sp.PROTO)
                return False
            self.hello_done = True
            header = self.server.recording.header
            self._send({
                "type": "welcome", "ts": round(time.time(), 3), "proto": sp.PROTO,
                # A replayer echoes the client's version: it is a fixture
                # server, not "the wrong server" for that client.
                "version": msg["version"],
                "server": {"impl": "replay", "pid": os.getpid()},
                "replay": {"recorded_version": header["version"],
                           "source": header["source"]},
            })
            return True
        if not self.hello_done:
            self._send_error("bad_message", "hello required first", id=rid, request=kind)
            return False
        if kind == "subscribe":
            async with self.lock:
                self._apply_settings(msg)
                if self.playback is None:
                    rec = self.server.recording
                    self.state.apply(rec.snapshot)
                    if self._full_view() and rid is None:
                        self.outq.put_nowait(rec.snapshot_line)
                    else:
                        self._send(self._current_snapshot(id=rid))
                    self.playback = asyncio.create_task(self._playback_loop())
                else:
                    # Resync: a snapshot of the CURRENT state, between two
                    # deltas; the one playback continues from gen + 1.
                    self._send(self._current_snapshot(id=rid))
            return True
        if kind == "set_content":
            async with self.lock:
                if self.playback is None:
                    self._send_error("not_subscribed", "subscribe first", id=rid,
                                     request=kind)
                    return True
                self.content = msg["content"]
                self._send(self._current_snapshot(id=rid))
            return True
        if kind == "set_pins":
            async with self.lock:
                self._send_result("set_pins", id=rid)
            return True
        if kind == "refresh":
            async with self.lock:
                self._send_result("refresh", id=rid, gen=self.state.gen or 0)
            return True
        if kind in ("set_compare_mode", "cycle_compare_mode"):
            async with self.lock:
                self._send_error("unavailable", "replay is read-only", id=rid,
                                 request=kind)
            return True
        if kind == "capture":
            async with self.lock:
                record = self._record_by_pane_id(msg["pane"])
                if record is None or "content" not in record:
                    self._send_error("not_found", f"no content for {msg['pane']}",
                                     id=rid, request=kind)
                else:
                    self._send_result("capture", id=rid, pane=msg["pane"],
                                      content=_tail(record["content"], msg["lines"]))
            return True
        self._send_error("unknown_type", f"unhandled request {kind!r}", id=rid,
                         request=kind)
        return True

    async def _next_line(self) -> bytes | None:
        """The next client line; ``None`` at EOF or once the server side is
        closing. Its two child tasks are always cancelled and awaited — also
        when this coroutine is itself cancelled by server shutdown — so no
        reader or ``closing.wait()`` outlives the connection."""
        read = asyncio.create_task(sp.read_line(self.reader), name="replay-read")
        stop = asyncio.create_task(self.closing.wait(), name="replay-closing")
        try:
            done, _pending = await asyncio.wait(
                {read, stop}, return_when=asyncio.FIRST_COMPLETED)
            return read.result() if read in done else None
        finally:
            for task in (read, stop):
                task.cancel()
            for task in (read, stop):
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task

    async def run(self) -> None:
        writer_task = asyncio.create_task(self._writer_loop())
        try:
            while not self.closing.is_set():
                try:
                    line = await self._next_line()
                except sp.FramingError as exc:
                    # Terminal: never re-frame inside the stream.
                    async with self.lock:
                        self._send_error("too_long", str(exc))
                    break
                if line is None:
                    break
                try:
                    msg = sp.decode(line, direction=sp.CLIENT)
                except sp.ProtocolError as exc:
                    # Covers UnknownMessageType too (code "unknown_type"). The
                    # request's id and type are echoed when they are readable,
                    # so the client can match the error to its request.
                    async with self.lock:
                        self._send_error(exc.code, str(exc), id=exc.request_id,
                                         request=exc.request_type)
                    if not self.hello_done:
                        break
                    continue
                if not await self._handle(msg):
                    break
        except (ConnectionError, OSError):
            pass
        finally:
            if self.playback is not None:
                self.playback.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await self.playback
            self.outq.put_nowait(None)
            with contextlib.suppress(Exception):
                await writer_task


class ReplayServer:
    """Serve a recording over a Unix socket.

    Each connection gets its own playback of the recorded stream: the first
    ``subscribe`` sends the recorded snapshot and starts playback; a repeated
    ``subscribe`` or a ``set_content`` answers with a snapshot of that
    connection's CURRENT reconstructed state and never restarts playback.
    ``pacer(index, delay)`` is awaited before each delta (tests inject a gate);
    the default sleeps ``delay``. Replay is read-only: compare-mode requests
    answer ``unavailable``; ``refresh`` / ``set_pins`` answer ``result``."""

    def __init__(self, recording, socket_path, *, speed: float = 1.0,
                 exit_at_end: bool = False, pacer=None):
        self.recording = (recording if isinstance(recording, Recording)
                          else read_recording(recording))
        # Validate the WHOLE stream before serving it — including a directly
        # supplied Recording — so a gap or a stale delta is refused here, not
        # discovered mid-playback by a waiting client.
        check_recording(self.recording)
        self.socket_path = str(socket_path)
        # Refuse a bad speed at start-up, not in every subscriber's playback.
        self.speed = check_speed(speed)
        self.exit_at_end = exit_at_end
        self.pacer = pacer or _sleep_pacer
        self._server: asyncio.base_events.Server | None = None
        self._tasks: set = set()

    async def start(self) -> None:
        self._server = await asyncio.start_unix_server(
            self._on_connect, path=self.socket_path, limit=sp.MAX_CLIENT_LINE_BYTES)

    async def _on_connect(self, reader, writer) -> None:
        task = asyncio.current_task()
        self._tasks.add(task)
        try:
            await _ReplayConnection(self, reader, writer).run()
        finally:
            self._tasks.discard(task)

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            for task in list(self._tasks):
                task.cancel()
            for task in list(self._tasks):
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
            with contextlib.suppress(Exception):
                await self._server.wait_closed()
            self._server = None
        with contextlib.suppress(FileNotFoundError):
            os.unlink(self.socket_path)

    async def __aenter__(self) -> "ReplayServer":
        await self.start()
        return self

    async def __aexit__(self, *_exc) -> None:
        await self.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_check(args) -> int:
    try:
        summary = check_recording(args.file)
    except (OSError, sp.ProtocolError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _cmd_record(args) -> int:
    result = asyncio.run(record_connect(
        args.connect, args.out, duration=args.duration, max_deltas=args.max_deltas,
        source=args.source))
    if result.published:
        print(f"RECORDED: {result.path} ({result.deltas} deltas; {result.reason})")
        return 0
    print(result.reason, file=sys.stderr)
    return 1


def _cmd_replay(args) -> int:
    if os.path.lexists(args.socket):
        print(f"refusing to replace existing path: {args.socket}", file=sys.stderr)
        return 1
    try:
        recording = read_recording(args.file)
    except (OSError, sp.ProtocolError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    async def main() -> None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, stop.set)
        async with ReplayServer(recording, args.socket, speed=args.speed,
                                exit_at_end=args.exit_at_end):
            print(f"REPLAYING: {args.file} on {args.socket}", flush=True)
            await stop.wait()

    asyncio.run(main())
    return 0


def _speed_arg(text: str) -> float:
    try:
        return check_speed(float(text))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="status_recording.py",
        description="Record, replay and check monitor status streams.")
    sub = parser.add_subparsers(dest="command", required=True)
    p_check = sub.add_parser("check", help="validate a recording file")
    p_check.add_argument("file")
    p_check.set_defaults(func=_cmd_check)
    p_record = sub.add_parser("record", help="record a status server's stream")
    p_record.add_argument("--connect", required=True, metavar="SOCK")
    p_record.add_argument("--out", required=True, metavar="FILE")
    p_record.add_argument("--duration", type=float, metavar="S")
    p_record.add_argument("--max-deltas", type=int, metavar="N")
    p_record.add_argument("--source", metavar="TEXT")
    p_record.set_defaults(func=_cmd_record)
    p_replay = sub.add_parser("replay", help="serve a recording over a Unix socket")
    p_replay.add_argument("file")
    p_replay.add_argument("--socket", required=True, metavar="SOCK")
    p_replay.add_argument("--speed", type=_speed_arg, default=1.0,
                          help="playback speed, a finite number >= 0 (0 = unpaced)")
    p_replay.add_argument("--exit-at-end", action="store_true")
    p_replay.set_defaults(func=_cmd_replay)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
