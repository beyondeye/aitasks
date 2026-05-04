---
priority: low
effort: high
depends: [t719_3]
issue_type: performance
status: Ready
labels: [performance, monitor, tui]
created_at: 2026-04-30 10:28
updated_at: 2026-05-04 10:00
---

## Context

Phase 3 of t719. Investigates (and conditionally implements) replacing periodic `capture-pane` polling with `tmux pipe-pane`-driven push: each pane writes its output to a per-pane fifo / pipe that the monitor reads asynchronously. Eliminates polling entirely.

**Two-phase structure** — investigation always runs; implementation is gated on a measured ≥2× win over `t719_2 + t719_3` combined. If the prototype doesn't meet the gate, document the result and archive the child without code changes.

Sibling auto-dep on `t719_3`. Independent of `t719_3` semantically — could be picked first if `t719_2`'s benchmark already meets the SLO and `t719_3` is deferred. The user can pick `t719_4` ahead of `t719_3` manually if desired.

## Key Files to Modify

### Phase 4a — Investigation (always done)

- **MODIFY** `aidocs/python_tui_performance.md` — append a new section "pipe-pane investigation" with measured results.
- Prototype lives in a throwaway branch / scratch script under `/tmp/` — not committed.

### Phase 4b — Implementation (conditional, only if gate passes)

- **NEW** `.aitask-scripts/monitor/tmux_pipe_pane.py` (~200–300 LOC) — class `TmuxPipePaneSubscriber` managing per-pane fifos, subscriptions, and async reads.
- **MODIFY** `.aitask-scripts/monitor/tmux_monitor.py`
  - `capture_all_async()` consults the subscriber's buffered content for known panes; falls back to `capture-pane` for cold panes / when subscriber is unavailable.
- **MODIFY** `.aitask-scripts/monitor/monitor_app.py` and `minimonitor_app.py`
  - Subscriber owned by the apps; started after the control client; torn down in `on_unmount` (added in `t719_2`).
- **NEW** `tests/test_tmux_pipe_pane.sh` — subscriber lifecycle, fifo cleanup on crash, parity-with-polling content.
- **MODIFY** `aidocs/benchmarks/bench_monitor_refresh.py` — add a third mode "pipe-pane" producing comparable numbers alongside subprocess and control.

## Reference Files for Patterns

- `.aitask-scripts/monitor/tmux_monitor.py:414-442` — `_finalize_capture` is the place where compare-mode logic (stripped/raw) operates on captured bytes. Subscriber-supplied content must reach this function in the same shape so idle detection is unchanged.
- `.aitask-scripts/monitor/tmux_control.py` (from `t719_1`) — pattern for an asyncio-driven subprocess wrapper with reader task + state machine.
- `tests/test_tmux_control.sh` (from `t719_1`) — bash test pattern with isolated `TMUX_TMPDIR`.

## Implementation Plan

### Phase 4a — Investigation

1. Scratch script: subscribe a single pane via `tmux pipe-pane -O 'cat > <fifo>'` (where `<fifo>` is a `mkfifo`'d path under `mktemp -d`).
2. Read it with `asyncio.open_connection` (or directly `open(fifo, 'rb')` on a thread / via `loop.run_in_executor`).
3. Measure on a representative session (5, 10, 20 panes):
   - CPU utilization (sampled via `ps -o pcpu` over a 30s window).
   - Refresh latency (time from agent emitting bytes to subscriber observing them).
   - Compare against the `t719_2 + t719_3` baseline.
4. Catalog caveats discovered:
   - Stale fifos on monitor crash → cleanup strategy (atexit? signal handlers? per-pane `pipe-pane -O ''` to unsubscribe?).
   - Multiple panes need multiple fifos → fd ceiling? memory cost?
   - ANSI escape handling vs. `capture-pane -e` output (pipe-pane sends raw terminal output, not the rendered scrollback; compare-mode's `_strip_ansi` should still work, but verify).
   - Backpressure: what if the monitor's reader is slow? `pipe-pane -O` (open mode) blocks the pane; without `-O` it would silently drop.
5. Document findings in `aidocs/python_tui_performance.md` with concrete numbers.

### Decision gate

If the prototype's median refresh latency is **≥2×** below the baseline for the same fixture, proceed to Phase 4b. Otherwise:
- Document the result.
- Skip Phase 4b.
- Archive the child with the investigation document as the deliverable.

### Phase 4b — Implementation (conditional)

#### `tmux_pipe_pane.py` — `TmuxPipePaneSubscriber`

Public API:

```python
class TmuxPipePaneSubscriber:
    def __init__(self, control_client: TmuxControlClient, fifo_dir: Path): ...
    async def subscribe(self, pane_id: str) -> None: ...   # creates fifo + pipe-pane -O cmd via control client
    async def unsubscribe(self, pane_id: str) -> None: ...
    def get_buffered_content(self, pane_id: str, lines: int) -> str | None: ...
    async def close(self) -> None: ...                      # unsubscribe all + rm fifo dir
```

Owns per-pane reader tasks that ingest bytes into a ring buffer.

#### `TmuxMonitor.capture_all_async()` consult-then-fallback

```python
async def capture_all_async(self):
    panes = await self.discover_panes_async()
    snapshots = {}
    for p in panes:
        if self._subscriber is not None:
            content = self._subscriber.get_buffered_content(p.pane_id, self.capture_lines)
            if content is not None:
                snapshots[p.pane_id] = self._finalize_capture(p, content)
                continue
        snap = await self.capture_pane_async(p.pane_id)  # cold-pane fallback
        if snap is not None:
            snapshots[p.pane_id] = snap
    return snapshots
```

Subscriber is auto-subscribed on first sight of a new pane and unsubscribed on `_clean_stale`.

#### Lifecycle in monitor_app.py / minimonitor_app.py

After `start_control_client()` succeeds, instantiate subscriber and pass it to monitor. In `on_unmount`, call `subscriber.close()` BEFORE `close_control_client()` (so unsubscribe commands can flow).

#### Test cases

- Lifecycle: subscribe pane, write to it, assert content visible in `get_buffered_content`.
- Unsubscribe: write more, assert content stops growing.
- Crash recovery: simulate process kill; ensure fifo files cleaned up by atexit handler.
- Parity: launch fixture with N panes, compare polling-mode and pipe-pane-mode `_finalize_capture` outputs byte-for-byte after a fixed input sequence.

## Verification Steps

### If gate fails (Phase 4a only)

- The investigation section in `aidocs/python_tui_performance.md` is committed with measured numbers + caveats.
- `git diff --stat` shows only `aidocs/python_tui_performance.md` modified.
- Mark child as Done; the t719_5 manual-verification sibling skips pipe-pane verification.

### If gate passes (Phase 4b)

- `bash tests/test_tmux_pipe_pane.sh` — passes.
- `bash tests/test_tmux_control.sh` (from `t719_1`) — still passes.
- `bash tests/test_adaptive_polling.sh` (from `t719_3`) — still passes.
- `python3 aidocs/benchmarks/bench_monitor_refresh.py --panes 5 --iterations 50` reports a third mode "pipe-pane" with median refresh latency ≥2× below the control-client median.
- Manual smoke: launch `ait monitor` and `ait minimonitor`; agent activity reflects in the pane preview within sub-second; idle detection still fires; `q` cleans up all fifo files (`ls /tmp/ait-pipe-pane-* 2>/dev/null` is empty after exit).
- Deeper manual verification deferred to `t719_5`.

## Out of Bounds

- Does NOT attempt to replace control-client architecture with pipe-pane-only — the control client is still needed for `list-panes`, `display-message`, etc. Pipe-pane is *additive*, replacing only the per-pane content polling.
- Does NOT change idle-detection logic.

## Stability caveats (added 2026-05-04 by t733)

Prior to implementation, weigh these stability concerns surfaced during
the t733 channel-resilience investigation. Pipe-pane introduces strictly
more failure surface than the current control-mode polling, in exchange
for sub-second update latency:

- **OOM-on-tmux risk.** tmux uses libevent `bufferevent` for `pipe-pane`
  output. If the Python consumer cannot drain fast enough, tmux buffers
  in *its own* memory — unbounded growth, not byte-drop. A busy code
  agent (Claude Code can burst >100 KB/s during streaming) × N panes ×
  M monitors increases the probability that a slow Python tick triggers
  tmux server OOM kill — exactly the "tmux crashed and took everything
  down" symptom that motivated t733.
- **Per-pane fd cost.** Each subscribed pane is one fifo + one consumer
  stdin; on a multi-session dev box (e.g. `aitasks` + `aitasks_mob`)
  × multiple monitor / minimonitor instances, the count grows quickly.
  Audit the hard fd ceiling on the user's host before subscribing
  unconditionally.
- **Raw VT-stream complexity.** Pipe-pane emits the unrendered terminal
  byte stream (cursor moves, alt-screen toggles, clearing). The Python
  consumer must implement a terminal emulator or round-trip through
  `capture-pane` after the fact to recover the rendered text the
  compare-mode logic relies on. This is more code than the bench
  prototype would suggest.
- **Single-threaded tmux event loop.** Per-pane pipe-pane I/O competes
  with control-mode + real-terminal rendering on the same loop. Many
  fifos = more fd-event work per tick.

**Pre-condition:** Do not implement Phase 4b until the t733 resilience
deliverables (reconnect + transition tests) have landed and been
validated on a real workload. The investigation phase (4a) can proceed
independently — the gate's ≥2× decision criterion is the right place
to weigh the latency win against this risk surface.
