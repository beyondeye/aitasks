---
Task: t719_4_pipe_pane_push.md
Parent Task: aitasks/t719_monitor_tmux_control_mode_refactor.md
Sibling Tasks: aitasks/t719/t719_1_control_client_module.md, aitasks/t719/t719_2_hot_path_integration.md, aitasks/t719/t719_3_adaptive_polling.md
Archived Sibling Plans: aiplans/archived/p719/p719_*_*.md
Worktree: aiwork/t719_4_pipe_pane_push
Branch: aitask/t719_4_pipe_pane_push
Base branch: main
---

# Plan — t719_4: pipe-pane push model (Phase 3)

## Goal

Investigate (always) and conditionally implement (gated on a measured
≥2× win over `t719_2 + t719_3`) replacing periodic `capture-pane` polling
with `tmux pipe-pane` writing each pane's output to a per-pane fifo / pipe.

## Phase 4a — Investigation (always done)

### Prototype

A throwaway script (kept in `/tmp/`, not committed) that:

1. Subscribes a single pane: `tmux pipe-pane -O -t %<id> 'cat > <fifo>'`
   where `<fifo>` is `mkfifo`-created under `mktemp -d`.
2. Reads the fifo asynchronously:

   ```python
   loop = asyncio.get_running_loop()
   def _open_fifo():
       return open(fifo_path, "rb", buffering=0)
   fd = await loop.run_in_executor(None, _open_fifo)
   ```

   (Or use `asyncio.open_connection` over the fifo; benchmark both.)
3. Measures, on a fixture session with N ∈ {5, 10, 20} panes:
   - CPU utilization sampled via `ps -o pcpu` over a 30 s window.
   - Refresh latency: time from `tmux send-keys '<marker>'` to subscriber
     observing the marker bytes.
   - Compares against `t719_2 + t719_3` baseline numbers
     (run `aidocs/benchmarks/bench_monitor_refresh.py` first to capture
     baseline median + p95).

### Caveats catalog

Document each in the investigation section of `aidocs/python_tui_performance.md`:

- **Stale fifos on monitor crash** — strategy: `atexit` handler +
  per-session cleanup of `/tmp/ait-pipe-pane-<session>-*` on `start()`.
- **fd ceiling** — N panes = 2N fds (one per fifo, one per ring buffer).
  Default `RLIMIT_NOFILE` of 1024 is fine; document if breached.
- **ANSI escape handling** — `pipe-pane` sends raw terminal output (the
  bytes the agent writes), not the rendered scrollback. `_strip_ansi` in
  `tmux_monitor.py:66-67` should still work, but verify by piping output
  with rich SGR sequences and checking the stripped form matches
  `capture-pane -e -p` output for the same pane.
- **Backpressure** — `pipe-pane -O` (open mode) blocks the pane on a slow
  reader. Without `-O` the pipe is non-blocking but tmux drops bytes if
  the pipe buffer fills. Pick `-O` and ensure the reader keeps up.

### Decision gate (write up in the doc section before deciding)

If prototype median refresh latency is **≥2×** below the
`t719_2 + t719_3` baseline for N=10, proceed to Phase 4b. Otherwise:

- Document the result with concrete numbers.
- Skip Phase 4b.
- Archive the child with the investigation doc as the deliverable.

## Phase 4b — Implementation (conditional)

### `tmux_pipe_pane.py`

```python
class TmuxPipePaneSubscriber:
    def __init__(self, control_client: TmuxControlClient, fifo_dir: Path,
                 ring_lines: int = 200): ...

    async def subscribe(self, pane_id: str) -> None: ...
    async def unsubscribe(self, pane_id: str) -> None: ...
    def get_buffered_content(self, pane_id: str, lines: int) -> str | None: ...
    async def close(self) -> None: ...
```

Per-pane state:

- `mkfifo` → start `pipe-pane -O -t %<id> 'cat > <fifo>'` via the control
  client.
- Spawn a per-pane reader task that decodes UTF-8 (errors=replace) into a
  bounded `collections.deque[str]` of recent lines (size `ring_lines`).
- `get_buffered_content(pane_id, lines)` returns the last `lines` joined
  with `\n` if the pane is subscribed, else `None`.

### `TmuxMonitor.capture_all_async()` consult-then-fallback

```python
async def capture_all_async(self) -> dict[str, PaneSnapshot]:
    panes = await self.discover_panes_async()
    self._clean_stale({p.pane_id for p in panes})

    # Auto-subscribe new panes (if subscriber present)
    if self._subscriber is not None:
        for p in panes:
            if p.category == PaneCategory.AGENT and not self._subscriber.is_subscribed(p.pane_id):
                await self._subscriber.subscribe(p.pane_id)

    snapshots: dict[str, PaneSnapshot] = {}
    cold = []
    for p in panes:
        if self._subscriber is not None:
            content = self._subscriber.get_buffered_content(p.pane_id, self.capture_lines)
            if content is not None:
                snapshots[p.pane_id] = self._finalize_capture(p, content)
                continue
        cold.append(p)

    # Cold-pane fallback (asyncio.gather subset)
    results = await asyncio.gather(*(self.capture_pane_async(p.pane_id) for p in cold), return_exceptions=True)
    for p, r in zip(cold, results):
        if isinstance(r, PaneSnapshot):
            snapshots[p.pane_id] = r

    self._settle_tick()  # if t719_3 already merged
    return snapshots
```

### Lifecycle in `monitor_app.py` / `minimonitor_app.py`

After `start_control_client()` succeeds, instantiate subscriber and pass
to monitor (or set `monitor._subscriber`). In `on_unmount`:

```python
async def on_unmount(self) -> None:
    if self._monitor is not None:
        try:
            if self._monitor._subscriber is not None:
                await self._monitor._subscriber.close()  # MUST run BEFORE close_control_client
            await self._monitor.close_control_client()
        except Exception:
            pass
```

The subscriber's `close()` issues `pipe-pane -t %<id>` (no command — turns
off the pipe) for each subscribed pane via the control client, then closes
fifo readers and removes the fifo dir. Order matters: control client must
still be alive when unsubscribing.

### `tests/test_tmux_pipe_pane.sh`

Same fixture pattern as `tests/test_tmux_control.sh`. Cases:

1. **Lifecycle** — subscribe pane, write to it via `tmux send-keys`,
   assert content visible in `get_buffered_content`.
2. **Unsubscribe** — write more, assert content stops growing in the ring.
3. **Crash recovery** — kill the test process; on next process, confirm no
   stale fifo files remain (atexit + start-time cleanup).
4. **Parity** — fixture with N panes, fixed input sequence, compare
   polling-mode and pipe-pane-mode snapshot content byte-for-byte after
   `_strip_ansi`.

### `bench_monitor_refresh.py` extension

Add a third mode:

```python
mon_pp = TmuxMonitor(session=session, multi_session=False)
await mon_pp.start_control_client()
sub = TmuxPipePaneSubscriber(mon_pp._control, fifo_dir=tmpdir / "fifos")
mon_pp._subscriber = sub
# ... measure
```

Output:

```
subprocess: median=… p95=…
control:    median=… p95=…
pipe-pane:  median=… p95=…
```

## Verification

### If gate fails (Phase 4a only)

- The investigation section in `aidocs/python_tui_performance.md` is
  committed with measured numbers + caveats.
- `git diff --stat` shows only `aidocs/python_tui_performance.md` modified.
- Mark child as Done; `t719_5` skips pipe-pane verification.

### If gate passes (Phase 4b)

- `bash tests/test_tmux_pipe_pane.sh` — passes.
- `bash tests/test_tmux_control.sh` (from `t719_1`) — still passes.
- `bash tests/test_adaptive_polling.sh` (from `t719_3`) — still passes.
- `python3 aidocs/benchmarks/bench_monitor_refresh.py --panes 5 --iterations 50`
  reports a third mode "pipe-pane" with median refresh latency ≥2× below
  the control-client median.
- Manual smoke: agent activity reflects in pane preview within ~sub-second;
  idle detection still fires; `q` cleans up all fifos
  (`ls /tmp/ait-pipe-pane-* 2>/dev/null` empty after exit).
- `git diff --stat` confined to: tmux_monitor.py, monitor_app.py,
  minimonitor_app.py, plus new `tmux_pipe_pane.py` and tests.

## Out of bounds

- Does NOT replace control client with pipe-pane-only — control client is
  still needed for `list-panes`, `display-message`, etc. Pipe-pane is
  *additive*, replacing only per-pane content polling.
- Does NOT change idle detection logic (still operates on bytes after
  `_strip_ansi`).

## Step 9 — Post-Implementation

Standard archival per `task-workflow/SKILL.md` Step 9.

## Notes for sibling tasks

- The investigation section in `aidocs/python_tui_performance.md` is
  load-bearing input for `t719_6`'s architecture evaluation, regardless
  of whether Phase 4b shipped.
- If Phase 4b ships, the parent plan's "Serialization design note"
  premise changes — the control-client serialization is no longer on the
  hot path. `t719_6` should re-frame the trade-off accordingly.
