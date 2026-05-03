---
priority: high
effort: medium
depends: [t719_1]
issue_type: performance
status: Implementing
labels: [performance, monitor, tui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-30 10:26
updated_at: 2026-05-03 08:52
---

## Context

Second step of t719. With `t719_1` shipping a working `TmuxControlClient` module + tests, this child wires it into `TmuxMonitor`'s async hot-path, adds lifecycle in both apps, and proves the ≥5× speedup with a microbenchmark. **This child delivers the user-visible performance win.**

Depends on `t719_1` (sibling auto-dep). The serialization design choice (single client, FIFO `deque[Future]`, `asyncio.Lock`) is documented in the parent plan's "Serialization design note" — it's a deliberate Phase-1 trade-off, evaluated retrospectively in `t719_6`.

## Key Files to Modify

- **MODIFY** `.aitask-scripts/monitor/tmux_monitor.py`
  - Add `self._control: TmuxControlClient | None = None` in `__init__`.
  - Add `start_control_client()`, `close_control_client()`, `has_control_client()` methods.
  - Add `_tmux_async(args, timeout)` private method that prefers the client, falls back to subprocess on `is_alive == False` or transport rc `-1`.
  - Update three async-path call sites — `tmux_monitor.py:284` (`_discover_panes_multi_async`), `:317` (`discover_panes_async`), `:469` (`capture_pane_async`) — to call `self._tmux_async(...)` instead of the module-level `_run_tmux_async`. The free function stays as the subprocess fallback.
  - **Sync paths untouched** (kill, switch, send-keys, spawn-tui, has-session, find_companion_pane_id, discover_window_panes — all user-action triggered, not per-tick).
- **MODIFY** `.aitask-scripts/monitor/monitor_app.py`
  - In `_start_monitoring` (line 579), spawn a Textual worker that runs `await self._monitor.start_control_client()` with `exit_on_error=False` (best-effort; logs if it fails; subprocess fallback kicks in automatically).
  - Add `async def on_unmount()` (no existing unmount hook in this file — confirmed) that calls `self._monitor.close_control_client()` under try/except.
- **MODIFY** `.aitask-scripts/monitor/minimonitor_app.py`
  - Same lifecycle pattern in `_start_monitoring` (line 189) + new `on_unmount`.
- **NEW** `aidocs/benchmarks/bench_monitor_refresh.py` (~200 LOC)

## Reference Files for Patterns

- `.aitask-scripts/monitor/tmux_control.py` — added in `t719_1`. The `start_control_client` method instantiates `TmuxControlClient(session=self.session)` and awaits `start()`.
- `aidocs/benchmarks/bench_archive_formats.py` — pattern for the new benchmark (argparse, warmup + iterations, `statistics`, dataclass capabilities, single-file convention).
- `tests/test_tmux_exact_session_targeting.sh:86-97` and `tests/test_multi_session_monitor.sh:702-705` — tmux fixture patterns reused for the benchmark's `TMUX_TMPDIR` setup.

## Implementation Plan

### 1. `tmux_monitor.py` async helper

```python
async def _tmux_async(self, args: list[str], timeout: float = 5.0) -> tuple[int, str]:
    if self._control is not None and self._control.is_alive:
        rc, out = await self._control.request(args, timeout=timeout)
        if rc != -1:
            return rc, out
        # transport failure: fall through this call to subprocess
    return await _run_tmux_async(args, timeout=timeout)
```

The free `_run_tmux_async` stays as the fallback. `grep -rn "_run_tmux_async" .aitask-scripts/` confirms it has no external callers (verified during planning).

### 2. Lifecycle methods on `TmuxMonitor`

```python
async def start_control_client(self) -> bool:
    from .tmux_control import TmuxControlClient
    client = TmuxControlClient(session=self.session)
    if await client.start():
        self._control = client
        return True
    return False

async def close_control_client(self) -> None:
    if self._control is not None:
        await self._control.close()
        self._control = None

def has_control_client(self) -> bool:
    return self._control is not None and self._control.is_alive
```

### 3. monitor_app.py lifecycle wiring

In `_start_monitoring` (line 579), after `self._monitor = TmuxMonitor(...)`:

```python
async def _connect_control_client() -> None:
    try:
        ok = await self._monitor.start_control_client()
        if not ok:
            self.log("tmux control mode unavailable; using subprocess fallback")
    except Exception as exc:
        self.log(f"tmux control mode init failed: {exc!r}")

self.run_worker(
    _connect_control_client(),
    exclusive=False,
    exit_on_error=False,
    group="tmux-control-init",
)
```

Add at the same scope:

```python
async def on_unmount(self) -> None:
    if self._monitor is not None:
        try:
            await self._monitor.close_control_client()
        except Exception:
            pass
```

### 4. minimonitor_app.py lifecycle wiring

Identical pattern in `_start_monitoring` (line 189) + new `on_unmount`.

### 5. Benchmark `aidocs/benchmarks/bench_monitor_refresh.py`

1. Setup: `TMUX_TMPDIR=$(mktemp -d)`, `unset TMUX`, `tmux new-session -d -s bench`.
2. Spawn N agent windows (default 5) — each running `tail -f /dev/null` so `capture-pane` has stable content.
3. Construct two `TmuxMonitor` instances with `multi_session=False`:
   - `mon_sub` — control client never started (subprocess path).
   - `mon_ctrl` — `await mon_ctrl.start_control_client()`.
4. For each, run `capture_all_async()` × M (default 50) after warmup of 3.
5. Instrument fork count via a counter monkey-patched onto `_run_tmux_async`.
6. Print summary: median, p95, mean ratio, fork count, fork count ratio.
7. Cleanup via `tmux kill-server` and `rm -rf $TMUX_TMPDIR`.
8. Skip cleanly if `tmux` is unavailable (mirrors test pattern).

CLI: `python3 aidocs/benchmarks/bench_monitor_refresh.py [--panes N] [--iterations M] [--warmup K]`.

## Verification Steps

- `bash tests/test_tmux_control.sh` (from `t719_1`) still passes — no regression in the standalone client.
- `python3 aidocs/benchmarks/bench_monitor_refresh.py --panes 5 --iterations 50` reports control-client median wall time at least **5×** below subprocess median; per-tick subprocess spawn count drops from ~6 (1 list-panes + 5 capture-pane) to **0** in steady state.
- Smoke-launch `ait monitor` and `ait minimonitor` against a real session with 5+ agent panes:
  - Pane list populates within one tick.
  - Idle indicator fires after the configured threshold.
  - Multi-session toggle (`M`) refreshes correctly.
  - Compare-mode toggle (`d`) still flips per-pane mode.
  - `q` exits cleanly (no zombie tmux clients in `tmux list-clients`).
- Deeper qualitative verification deferred to `t719_5` (manual-verification sibling).
- `git diff --stat` shows changes confined to: tmux_monitor.py, monitor_app.py, minimonitor_app.py, and one new benchmark file.
