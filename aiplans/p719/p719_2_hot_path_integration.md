---
Task: t719_2_hot_path_integration.md
Parent Task: aitasks/t719_monitor_tmux_control_mode_refactor.md
Sibling Tasks: aitasks/t719/t719_1_control_client_module.md, aitasks/t719/t719_3_adaptive_polling.md, aitasks/t719/t719_4_pipe_pane_push.md
Archived Sibling Plans: aiplans/archived/p719/p719_*_*.md
Worktree: aiwork/t719_2_hot_path_integration
Branch: aitask/t719_2_hot_path_integration
Base branch: main
---

# Plan — t719_2: Hot-path integration + lifecycle + benchmark

## Goal

Wire `TmuxControlClient` (from `t719_1`) into `TmuxMonitor`'s async paths,
add lifecycle in monitor/minimonitor, and prove the ≥5× speedup with a
microbenchmark. This child delivers the user-visible performance win.

## Files to modify

- `.aitask-scripts/monitor/tmux_monitor.py` — async hot-path + control-client
  lifecycle methods.
- `.aitask-scripts/monitor/monitor_app.py` — start/close client; new
  `on_unmount`.
- `.aitask-scripts/monitor/minimonitor_app.py` — same as monitor_app.

## Files to add

- `aidocs/benchmarks/bench_monitor_refresh.py` (~200 LOC).

## Step 1 — `tmux_monitor.py` async helper + lifecycle

In `TmuxMonitor.__init__`:

```python
self._control: TmuxControlClient | None = None
```

Add three new methods:

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
        with contextlib.suppress(Exception):
            await self._control.close()
        self._control = None

def has_control_client(self) -> bool:
    return self._control is not None and self._control.is_alive

async def _tmux_async(self, args: list[str], timeout: float = 5.0) -> tuple[int, str]:
    if self._control is not None and self._control.is_alive:
        rc, out = await self._control.request(args, timeout=timeout)
        if rc != -1:
            return rc, out
        # transport failure on this call — fall back to subprocess.
    return await _run_tmux_async(args, timeout=timeout)
```

## Step 2 — Update three async-path call sites

Change three sites from `await _run_tmux_async(...)` to
`await self._tmux_async(...)`:

| File | Line | Function |
|------|------|----------|
| `tmux_monitor.py` | 284 | `_discover_panes_multi_async` |
| `tmux_monitor.py` | 317 | `discover_panes_async` (single-session branch) |
| `tmux_monitor.py` | 469 | `capture_pane_async` |

The free `_run_tmux_async` (lines 94–119) stays as the subprocess fallback.

**Sync paths untouched:** `discover_panes`, `capture_pane`, `send_enter`,
`send_keys`, `switch_to_pane`, `find_companion_pane_id`, `kill_pane`,
`kill_window`, `kill_agent_pane_smart`, `spawn_tui`, `discover_window_panes`.
All user-action triggered, not per-tick.

## Step 3 — `monitor_app.py` lifecycle

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

Add `on_unmount` at class scope (no existing hook — confirmed):

```python
async def on_unmount(self) -> None:
    if self._monitor is not None:
        try:
            await self._monitor.close_control_client()
        except Exception:
            pass
```

## Step 4 — `minimonitor_app.py` lifecycle

Identical pattern in `_start_monitoring` (line 189) + new `on_unmount`.

## Step 5 — `aidocs/benchmarks/bench_monitor_refresh.py`

Pattern matches `aidocs/benchmarks/bench_archive_formats.py`. Outline:

```python
#!/usr/bin/env python3
"""Benchmark monitor refresh: subprocess vs tmux -C control-mode."""
from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

WARMUP_DEFAULT = 3
ITERATIONS_DEFAULT = 50
PANES_DEFAULT = 5

def setup_fixture(panes: int) -> tuple[str, Path]:
    tmpdir = Path(tempfile.mkdtemp(prefix="ait_bench_"))
    os.environ["TMUX_TMPDIR"] = str(tmpdir)
    os.environ.pop("TMUX", None)
    session = f"bench_{os.getpid()}"
    subprocess.run(["tmux", "new-session", "-d", "-s", session, "tail -f /dev/null"], check=True)
    for i in range(panes):
        subprocess.run(["tmux", "new-window", "-t", f"{session}:", "-n", f"agent-{i}", "tail -f /dev/null"], check=True)
    return session, tmpdir

def teardown_fixture(tmpdir: Path) -> None:
    subprocess.run(["tmux", "kill-server"], check=False)
    shutil.rmtree(tmpdir, ignore_errors=True)

async def measure(monitor, iterations: int, warmup: int):
    for _ in range(warmup):
        await monitor.capture_all_async()
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        await monitor.capture_all_async()
        times.append(time.perf_counter() - t0)
    return times

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--panes", type=int, default=PANES_DEFAULT)
    parser.add_argument("--iterations", type=int, default=ITERATIONS_DEFAULT)
    parser.add_argument("--warmup", type=int, default=WARMUP_DEFAULT)
    args = parser.parse_args()

    if not shutil.which("tmux"):
        print("SKIP: tmux not available")
        return

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / ".aitask-scripts"))
    from monitor.tmux_monitor import TmuxMonitor

    session, tmpdir = setup_fixture(args.panes)
    try:
        async def run():
            mon_sub = TmuxMonitor(session=session, multi_session=False)
            mon_ctrl = TmuxMonitor(session=session, multi_session=False)
            await mon_ctrl.start_control_client()
            try:
                t_sub = await measure(mon_sub, args.iterations, args.warmup)
                t_ctrl = await measure(mon_ctrl, args.iterations, args.warmup)
            finally:
                await mon_ctrl.close_control_client()
            return t_sub, t_ctrl

        t_sub, t_ctrl = asyncio.run(run())
        for label, ts in [("subprocess", t_sub), ("control", t_ctrl)]:
            print(f"{label}: median={statistics.median(ts)*1000:.2f} ms p95={sorted(ts)[int(len(ts)*0.95)]*1000:.2f} ms")
        print(f"speedup: {statistics.median(t_sub)/statistics.median(t_ctrl):.2f}x")
    finally:
        teardown_fixture(tmpdir)

if __name__ == "__main__":
    main()
```

Add fork-count instrumentation by monkey-patching `_run_tmux_async` with
a counter; report fork counts alongside wall-time numbers.

## Verification

- `bash tests/test_tmux_control.sh` (from `t719_1`) — still passes.
- `python3 aidocs/benchmarks/bench_monitor_refresh.py --panes 5 --iterations 50`
  reports control-client median ≥ **5×** below subprocess median; per-tick
  subprocess spawn count drops from ~6 to **0** in steady state.
- Smoke launch `ait monitor` and `ait minimonitor` against a real session
  with 5+ agent panes:
  - Pane list populates within one tick.
  - Idle indicator fires after the configured threshold.
  - Multi-session toggle (`M`) refreshes correctly.
  - Compare-mode toggle (`d`) flips per-pane mode.
  - `q` exits cleanly (no zombie tmux clients in `tmux list-clients`).
- `git diff --stat` confined to: tmux_monitor.py, monitor_app.py,
  minimonitor_app.py, plus one new benchmark file.

## Step 9 — Post-Implementation

Standard archival per `task-workflow/SKILL.md` Step 9. Run
`tests/test_tmux_control.sh` and `bench_monitor_refresh.py` in
`verify_build` if configured.

## Notes for sibling tasks

- The `on_unmount` hook added here is the canonical place for `t719_4`'s
  pipe-pane subscriber teardown (must run before `close_control_client`).
- `_tmux_async` returns `(-1, "")` from the fallback path on hard failure
  (matches `_run_tmux_async`'s contract). Callers don't need to change.
- The benchmark's CLI is the harness `t719_4` and `t719_6` extend with
  additional modes ("pipe-pane", and a 10/20 panes scaling sweep).
