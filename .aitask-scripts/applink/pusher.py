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

Stage 2 (t822_9): on a content change ``_push_pane`` emits a ``delta`` (0x02,
changed rows only against the per-connection ``PaneState.row_sigs`` baseline) and
falls back to a full ``keyframe`` (0x01) on the first / forced / keyframe-interval
frame or when the delta is not cheaper. ``dim`` (0x05) is sent on resize. The
``cursor`` (0x04) encoder is folded into keyframes/deltas; standalone cursor-only
frames remain deferred so idle panes cost zero binary bytes (detecting cursor-only
motion would need a per-tick cursor fetch per pane).

Stage 3 (t822_10): before the delta path, ``_push_pane`` tries the ``append``
(0x03) fast path for log-streaming panes — when the new grid is the baseline
scrolled up by ``k`` rows with ``k`` brand-new bottom rows
(:func:`content.detect_append`) and the cursor is unchanged and at the bottom row,
it sends only the new bottom rows. It falls back to ``delta`` when the shift does
not hold, the cursor moved, or an appended row carries a hyperlink (``append``
carries no cursor and no ``osc8`` sidecar).
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
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

# Hard ceiling on a single outbound binary frame (t1007). A legit dense full-screen
# keyframe is low-hundreds-of-KB and HIGH_WATER_BYTES already coalesces below this, so
# this only trips on genuinely pathological/adversarial pane content (or a dense
# max-`count` history pull) — bounding the mobile decode-bomb + server write-buffer
# blowup. An oversize frame is dropped (audited), never sent.
MAX_PUSH_FRAME_BYTES = 2 * 1024 * 1024   # 2 MiB

# Ceiling on a single on-demand history (scrollback pull) capture depth (t1092).
# Decoupled from the monitor's live `capture_lines` (~200): live frames only need
# the viewport, but a history pull wants deep scrollback. The per-request depth is
# sized to `viewport + count` and clamped to this ceiling, which is aligned with
# tmux's own default server `history-limit` (~2000, the real hard ceiling on what
# `capture-pane -S` can ever retrieve). The server overrides this from
# `tmux.applink.history_capture_lines` (clamped at load).
DEFAULT_HISTORY_CAPTURE_LINES = 2000


class PushScheduler:
    def __init__(
        self, conn, ws, monitor, *, clock=None, audit=None,
        history_capture_lines=DEFAULT_HISTORY_CAPTURE_LINES,
        task_resolver=None,
    ) -> None:
        self._conn = conn
        self._ws = ws
        self._monitor = monitor
        # Optional TaskInfoCache-like resolver. Kept optional so focused pusher
        # tests and non-server callers preserve the pre-title pane_status payload.
        self._tasks = task_resolver
        # Ceiling on a single history-pull capture depth (t1092); server-overridden
        # from tmux.applink.history_capture_lines (clamped at load).
        self._history_capture_lines = history_capture_lines
        # Security/resilience audit logger (oversize-frame drops, per-pane faults).
        # The server threads its own logger in; default to the package logger so a
        # bare-constructed scheduler (unit tests) stays silent (no handlers).
        self._audit = audit if audit is not None else logging.getLogger("applink.audit")
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
                try:
                    await self._run_once()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    # Resilience (t1007): a whole-pass fault (e.g. capture_all_async
                    # raised) must not kill the connection's push loop — log and
                    # recover on the next tick.
                    self._audit.warning("PUSH_RUN_ONCE_ERROR", exc_info=True)
        except asyncio.CancelledError:
            return

    # -- One emit pass (the testable unit) -------------------------------------

    async def _run_once(self) -> None:
        if self._conn.paused:
            # `pause` verb (t1055): halt ALL pushes — binary frames and the
            # pane_status heartbeat — until `resume` clears the flag. The
            # subscription/force set is left intact (content_transport.md
            # §Back-pressure: "no state lost").
            return
        sub = self._conn.subscription
        if sub is None or not sub.panes:
            return
        if self._over_high_water():
            return  # coalesce: skip this tick's sends, keep force set intact
        snaps = await self._monitor.capture_all_async()
        if self._tasks is not None:
            update_mapping = getattr(self._tasks, "update_session_mapping", None)
            get_mapping = getattr(self._monitor, "get_session_to_project_mapping", None)
            if callable(update_mapping) and callable(get_mapping):
                try:
                    update_mapping(get_mapping())
                except Exception:
                    pass
        now = self._clock()
        for pane_id in list(sub.panes):
            if self._stopped:
                return  # a send failed earlier this pass: stop cleanly, don't
                        # touch a dead socket for the remaining panes
            snap = snaps.get(pane_id)
            if snap is None:
                continue  # pane gone this tick
            try:
                await self._push_pane(sub, pane_id, snap, now)
            except asyncio.CancelledError:
                raise
            except Exception:
                # Resilience (t1007): one pane's encode/capture fault must not abort
                # the pass or kill the loop — log and continue to the next pane.
                self._audit.warning("PUSH_PANE_ERROR pane=%s", pane_id, exc_info=True)
                continue

        # Stage 5 (t1057): drain queued scrollback (history RPC) pulls AFTER the
        # live loop. Ordering matters: the live loop above emits each subscribed
        # pane's forced keyframe first (subscribe seeds `force`), so a
        # `subscribe`+immediate-`history` can never deliver a negative-row history
        # keyframe before the pane's first live keyframe.
        if self._stopped:
            return  # a live send failed: do not touch a dead socket
        if sub.has_pending_history():
            await self._drain_history(sub)

    async def _drain_history(self, sub) -> None:
        """Serve queued scrollback pulls as single negative-row-id keyframes.

        Takes a **fresh, request-sized, non-finalizing** capture per pull (t1092):
        the depth is sized to `viewport + count` and clamped to
        `self._history_capture_lines`, so a history pull reaches deep scrollback
        without taxing the monitor's shallow live capture or perturbing its idle
        state (capture_pane_content_async does NOT touch _last_content). It is
        NOT the same buffer as this tick's live frame — history is best-effort and
        not anchored to the exact rendered frame (content_transport.md
        §Scrollback): a pane that has vanished (capture returns None) is silently
        skipped (the control-plane token acked acceptance, not delivery). The
        history keyframe reads the pane's current `frame_id` WITHOUT advancing the
        live monotonic chain; the negative row_ids are the sole signal that
        distinguishes it from a live keyframe.
        """
        for pane_id, before_line, count, _token in sub.take_pending_history():
            if self._stopped:
                return
            cached = self._monitor.get_pane(pane_id)   # _pane_cache read (no subprocess)
            # Capture only what THIS request can use (viewport + count + scroll
            # offset), clamped to the configured ceiling. Bounds the tmux capture
            # regardless of config; the keyframe size is separately bounded by
            # `count` (<= _MAX_HISTORY_ROWS) and the 2 MiB frame drop.
            depth = self._history_capture_lines
            if cached is not None:
                depth = min(depth, cached.height + count + max(0, -before_line))
            cap = await self._monitor.capture_pane_content_async(pane_id, depth)
            if cap is None:
                continue
            try:
                pane, text = cap
                cols, rows_h = pane.width, pane.height
                rows, osc8 = content.history_rows(text, rows_h, before_line, count)
                frame_id = sub.state_for(pane_id).frame_id  # read; do NOT advance the chain
                cursor = [0, 0, False, 0]                    # history has no cursor (hidden)
                # Best-effort: an oversize history keyframe is dropped by _send (its
                # token acked acceptance, not delivery); off the live frame_id chain,
                # so a drop corrupts no live state (t1007).
                await self._send(content.encode_keyframe(
                    pane_id, frame_id, cols, rows_h, cursor, rows, osc8 or None))
            except asyncio.CancelledError:
                raise
            except Exception:
                # Resilience (t1007): one history pane's encode fault must not abort
                # the remaining best-effort drains — log and skip.
                self._audit.warning("HISTORY_DRAIN_ERROR pane=%s", pane_id, exc_info=True)
                continue

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

        # Roster-vs-content split (t1045): a status-only pane gets the pane_status
        # heartbeat above but NO binary frames. Clear its force seed and return
        # before the per-pane cursor capture / parse / binary encode below — so a
        # status-only pane costs zero per-pane capture_cursor_async calls and zero
        # binary bytes (the shared roster snapshot in _run_once is taken anyway).
        if not sub.streams_content(pane_id):
            sub.force.discard(pane_id)
            return

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

        if self._stopped:
            # A pre-content send (pane_status / dim) hit a dead socket: bail before
            # the cursor capture / parse / encode rather than doing doomed work
            # (t1007). `force`/state are left intact (mirrors the tail hardening).
            return
        cursor = await self._monitor.capture_cursor_async(pane_id)
        cursor = list(cursor) if cursor is not None else [0, 0, False, 0]
        # Live frames carry only the visible viewport (content_transport.md §Row
        # schema: row_id 0 == top of the viewport). The capture holds ~200
        # scrollback rows above the viewport (-S -capture_lines); trimming to the
        # trailing `dims[1]` (pane height) rows here makes every downstream frame
        # type — keyframe, delta, append, osc8 — viewport-only and aligns row_ids
        # with the viewport-relative cursor row (t1054). Scrollback is reachable
        # via the (future) history RPC with negative row_ids.
        parsed = content.parse_snapshot(snap.content, dims[1])
        new_sigs = {row_id: content.row_signature(spans) for row_id, spans, _u in parsed}

        # Stage 2 (t822_9): emit a `delta` (changed rows only) against the
        # per-connection baseline when one exists; fall back to a full `keyframe`
        # on the first / forced / keyframe-interval frame, or when the delta would
        # not be cheaper than a keyframe.
        emit_keyframe = forced or interval_due or st.row_sigs is None
        sent_keyframe = False
        sent_append = False
        delivered = True       # set False if _send drops an oversize content frame (t1007)
        bottom_row = dims[1] - 1
        if not emit_keyframe:
            # Stage 3 (t822_10): try the `append` (0x03) fast path before the delta
            # path. It applies only when the new grid is the baseline scrolled up by
            # k with k brand-new bottom rows (detect_append), the cursor is UNCHANGED
            # from the last sent frame and at the bottom row (append carries no
            # cursor, so the client keeps the prior one), and no appended row carries
            # a hyperlink (append carries no osc8 sidecar). Otherwise fall back to a
            # delta, which carries both the cursor and the osc8 sidecar.
            k = content.detect_append(st.row_sigs, new_sigs)
            if (k is not None
                    and cursor[0] == bottom_row
                    and st.last_cursor == cursor):
                appended = parsed[len(parsed) - k:]          # (row_id, spans, urls)
                if not any(u for _r, _s, urls in appended for u in urls):
                    append_wire = [[row_id, spans] for row_id, spans, _u in appended]
                    frame_id = sub.next_frame_id(pane_id)    # bump the monotonic chain
                    delivered = await self._send(content.encode_append(pane_id, frame_id, append_wire))
                    sent_append = True

        if not emit_keyframe and not sent_append:
            changed_wire, removed, _ns, changed_subset = content.deltify(st.row_sigs, parsed)
            if not changed_wire and not removed:
                # Whole-pane hash moved but no visible row changed (e.g. a trailing
                # blank line dropped by parse_snapshot) -> nothing to send.
                st.last_hash = content_hash
                return
            # Cost proxy: a delta covering >= every row is never smaller than a
            # keyframe (each row is bounded by pane width), so use the row count to
            # decide and skip a second full encode. Errs CONSERVATIVELY (may pick a
            # keyframe when a byte-accurate compare would have kept a delta) — never
            # incorrect, only more keyframes; single encode per tick. The escape
            # hatch if dense-terminal keyframe frequency ever bites is a byte-accurate
            # compare (encode both, send the smaller).
            if len(changed_wire) + len(removed) >= len(parsed):
                emit_keyframe = True
            else:
                delta_wire = changed_wire + [[row_id, []] for row_id in removed]
                prev_frame_id = st.frame_id
                frame_id = sub.next_frame_id(pane_id)        # = prev_frame_id + 1
                delivered = await self._send(content.encode_delta(
                    pane_id, frame_id, prev_frame_id, cursor, delta_wire,
                    content.build_osc8(changed_subset) or None,
                ))

        if emit_keyframe:
            full_rows = [[row_id, spans] for row_id, spans, _u in parsed]
            frame_id = sub.next_frame_id(pane_id)
            delivered = await self._send(content.encode_keyframe(
                pane_id, frame_id, dims[0], dims[1], cursor, full_rows,
                content.build_osc8(parsed) or None,
            ))
            sent_keyframe = True

        if self._stopped:
            # A send failed mid-pass (_send swallowed the exception and set
            # _stopped): do NOT advance per-pane state or clear `force`. A
            # forced keyframe whose send failed then survives in `force` for a
            # future (re)send instead of being silently dropped — correct
            # regardless of when the connection is actually torn down.
            return
        if not delivered:
            # An oversize content frame was dropped by _send (t1007). Re-anchor:
            # row_sigs=None forces the NEXT emit through the self-contained keyframe
            # path (never an append/delta against a baseline the client never
            # received — which would silently mis-render). Advance the seen/cadence
            # markers so a *static* oversize pane does not re-encode every tick (the
            # retry is throttled to the keyframe interval); a change to sub-cap
            # content still emits a fresh keyframe at once (row_sigs is None). `force`
            # is cleared — the drop is final for this exact content.
            st.row_sigs = None
            st.last_hash = content_hash
            st.last_dims = dims
            st.last_cursor = list(cursor)
            st.last_keyframe_t = now
            st.last_send_t = now
            sub.force.discard(pane_id)
            return
        st.row_sigs = new_sigs
        st.last_hash = content_hash
        st.last_dims = dims
        st.last_cursor = list(cursor)     # full before-cursor for the next tick's append gate
        if sent_keyframe:
            st.last_keyframe_t = now      # any keyframe (forced/interval/cost-fallback) resets drift
        st.last_send_t = now
        sub.force.discard(pane_id)

    # -- Frame I/O -------------------------------------------------------------

    async def _send_pane_status(self, snap) -> None:
        pane = snap.pane
        category = getattr(pane.category, "value", str(pane.category))
        task_id = task_id_from_window_name(pane.window_name)
        title = None
        if task_id and self._tasks is not None:
            try:
                info = self._tasks.get_task_info(task_id, pane.session_name)
                raw_title = getattr(info, "title", None) if info is not None else None
                if isinstance(raw_title, str) and raw_title:
                    title = raw_title
            except Exception:
                title = None
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
                "task_id": task_id,
            },
        }
        if title is not None:
            frame["payload"]["title"] = title
        await self._send(json.dumps(frame))

    async def _send(self, data) -> bool:
        """Send one frame. Returns True if sent, False if dropped or the socket died.

        The single outbound sink, so it carries the oversize-frame cap (t1007): a
        binary frame over MAX_PUSH_FRAME_BYTES is audited and dropped (NOT sent, and
        NOT a dead socket — `_stopped` is left clear so the loop keeps serving other
        panes). `pane_status` JSON text frames are bounded by construction, so only
        binary frames are capped."""
        if isinstance(data, (bytes, bytearray)) and len(data) > MAX_PUSH_FRAME_BYTES:
            self._audit.warning(
                "PUSH_FRAME_OVERSIZE bytes=%d cap=%d", len(data), MAX_PUSH_FRAME_BYTES)
            return False
        try:
            await self._ws.send(data)
        except Exception:
            # A dead socket: stop pushing; the transport's _handle finally will
            # tear us down.
            self._stopped = True
            return False
        return True

    def _over_high_water(self) -> bool:
        transport = getattr(self._ws, "transport", None)
        getsize = getattr(transport, "get_write_buffer_size", None)
        if callable(getsize):
            try:
                return getsize() > HIGH_WATER_BYTES
            except Exception:
                return False
        return False
