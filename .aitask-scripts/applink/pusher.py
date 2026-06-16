"""Per-connection binary push scheduler for the applink data plane (t822_8).

One :class:`PushScheduler` per WebSocket connection drives the snapshot push
loop: on each tick it captures pane content (via the shared
``monitor.capture_all_async``), encodes ``dim``/``keyframe`` frames for changed
panes (``content.py``), and sends them on the WebSocket **binary** channel, plus
a JSON ``pane_status`` push at the idle cadence for the pane list's badges.

The class is **dependency-injected and duck-typed** so it can be unit-tested
against a fake WebSocket (any object with an async ``send``) and a fake monitor
(``capture_all_async`` + ``capture_cursor_async``) — see
``tests/test_applink_pusher.sh``. ``_run_once`` is the single deterministic emit
pass; ``_loop`` is the thin timer driver.

Stage 1 emits ``keyframe`` (on change / forced / keyframe-interval) and ``dim``
(on resize). The ``cursor`` (0x04) encoder exists and is folded into keyframes;
standalone cursor-only frames are deferred so idle panes cost zero binary bytes
(detecting cursor-only motion would need a per-tick cursor fetch per pane).
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import sys
from pathlib import Path

_APPLINK_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _APPLINK_DIR.parent
for _p in (str(_APPLINK_DIR), str(_SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import content  # noqa: E402
from monitor.monitor_core import task_id_from_window_name  # noqa: E402

# Back-pressure high-water mark (content_transport.md §Back-pressure).
HIGH_WATER_BYTES = 256 * 1024


class PushScheduler:
    def __init__(self, conn, ws, monitor, *, clock=None) -> None:
        self._conn = conn
        self._ws = ws
        self._monitor = monitor
        # Injectable monotonic clock (tests pass a controllable one).
        if clock is None:
            import time
            clock = time.monotonic
        self._clock = clock
        self._wake = asyncio.Event()
        self._stopped = False
        self._task: asyncio.Task | None = None

    # -- Lifecycle -------------------------------------------------------------

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    def wake(self) -> None:
        """Signal the loop to run a pass immediately (flush the force set)."""
        self._wake.set()

    async def stop(self) -> None:
        """Stop the loop and await the task so teardown is deterministic."""
        self._stopped = True
        self._wake.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
            self._task = None

    async def _loop(self) -> None:
        try:
            while not self._stopped:
                sub = self._conn.subscription
                timeout = (sub.next_tick_ms() / 1000.0) if sub is not None else 1.0
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(self._wake.wait(), timeout=timeout)
                self._wake.clear()
                if self._stopped:
                    break
                await self._run_once()
        except asyncio.CancelledError:
            return

    # -- One emit pass (the testable unit) -------------------------------------

    async def _run_once(self) -> None:
        sub = self._conn.subscription
        if sub is None or not sub.panes:
            return
        if self._over_high_water():
            return  # coalesce: skip this tick's sends, keep force set intact
        snaps = await self._monitor.capture_all_async()
        now = self._clock()
        for pane_id in list(sub.panes):
            snap = snaps.get(pane_id)
            if snap is None:
                continue  # pane gone this tick
            await self._push_pane(sub, pane_id, snap, now)

    async def _push_pane(self, sub, pane_id, snap, now) -> None:
        st = sub.state_for(pane_id)
        pane = snap.pane
        dims = (pane.width, pane.height)
        forced = pane_id in sub.force
        cadence_s = sub.cadence_for(pane_id) / 1000.0
        due = (now - st.last_send_t) >= cadence_s

        # pane_status JSON heartbeat at the idle cadence (drives mobile badges).
        idle_s = sub.cadence_idle_ms / 1000.0
        if forced or (now - st.last_status_t) >= idle_s:
            await self._send_pane_status(snap)
            st.last_status_t = now

        # dim on resize (then force a fresh keyframe at the new size).
        dim_changed = st.last_dims is not None and st.last_dims != dims
        if dim_changed:
            await self._send(content.encode_dim(pane_id, dims[0], dims[1]))
            forced = True

        content_hash = hash(snap.content)
        changed = st.last_hash is None or content_hash != st.last_hash
        interval_due = (now - st.last_keyframe_t) >= (sub.keyframe_interval_ms / 1000.0)
        if not ((changed or forced or interval_due) and (due or forced)):
            return

        cursor = await self._monitor.capture_cursor_async(pane_id)
        cursor = list(cursor) if cursor is not None else [0, 0, False, 0]
        rows, osc8 = content.snapshot_to_rows(snap.content)
        frame_id = sub.next_frame_id(pane_id)
        await self._send(content.encode_keyframe(
            pane_id, frame_id, dims[0], dims[1], cursor, rows, osc8 or None,
        ))
        st.last_hash = content_hash
        st.last_dims = dims
        st.last_keyframe_t = now
        st.last_send_t = now
        sub.force.discard(pane_id)

    # -- Frame I/O -------------------------------------------------------------

    async def _send_pane_status(self, snap) -> None:
        pane = snap.pane
        category = getattr(pane.category, "value", str(pane.category))
        frame = {
            "v": 1, "kind": "push", "verb": "pane_status",
            "payload": {
                "pane_id": pane.pane_id,
                "idle_seconds": round(snap.idle_seconds, 2),
                "is_idle": snap.is_idle,
                "awaiting_input": snap.awaiting_input,
                "awaiting_input_kind": snap.awaiting_input_kind,
                "window_name": pane.window_name,
                "category": category,
                "session_name": pane.session_name,
                "task_id": task_id_from_window_name(pane.window_name),
            },
        }
        await self._send(json.dumps(frame))

    async def _send(self, data) -> None:
        try:
            await self._ws.send(data)
        except Exception:
            # A dead socket: stop pushing; the transport's _handle finally will
            # tear us down.
            self._stopped = True

    def _over_high_water(self) -> bool:
        transport = getattr(self._ws, "transport", None)
        getsize = getattr(transport, "get_write_buffer_size", None)
        if callable(getsize):
            try:
                return getsize() > HIGH_WATER_BYTES
            except Exception:
                return False
        return False
