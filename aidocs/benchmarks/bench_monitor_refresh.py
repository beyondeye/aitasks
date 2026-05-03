#!/usr/bin/env python3
"""Benchmark monitor refresh: subprocess vs tmux -C control-mode.

Spins up an isolated tmux server with N agent windows, then runs
TmuxMonitor.capture_all_async() M times under two configurations:

  * subprocess — control client never started; every per-tick
    list-panes/capture-pane spawns a fresh `tmux ...` subprocess.
  * control    — `await mon.start_control_client()` first; per-tick
    requests go over a single persistent `tmux -C` connection.

Reports median + p95 wall time, fork count per mode, and the
speedup / fork-reduction ratios.

Usage:
    python3 aidocs/benchmarks/bench_monitor_refresh.py [--panes N]
        [--iterations M] [--warmup K]
"""
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
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", session, "tail -f /dev/null"],
        check=True,
    )
    for i in range(panes):
        subprocess.run(
            [
                "tmux", "new-window", "-t", f"{session}:",
                "-n", f"agent-{i}", "tail -f /dev/null",
            ],
            check=True,
        )
    return session, tmpdir


def teardown_fixture(tmpdir: Path) -> None:
    subprocess.run(["tmux", "kill-server"], check=False)
    shutil.rmtree(tmpdir, ignore_errors=True)


async def measure(monitor, iterations: int, warmup: int) -> list[float]:
    for _ in range(warmup):
        await monitor.capture_all_async()
    times: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        await monitor.capture_all_async()
        times.append(time.perf_counter() - t0)
    return times


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panes", type=int, default=PANES_DEFAULT)
    parser.add_argument("--iterations", type=int, default=ITERATIONS_DEFAULT)
    parser.add_argument("--warmup", type=int, default=WARMUP_DEFAULT)
    args = parser.parse_args()

    if not shutil.which("tmux"):
        print("SKIP: tmux not available")
        return

    repo_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(repo_root / ".aitask-scripts"))
    from monitor.tmux_monitor import TmuxMonitor  # noqa: E402
    from monitor import tmux_monitor as _tm  # noqa: E402

    # Fork-count instrumentation: monkey-patch the module-level
    # `_run_tmux_async` with a counting wrapper so we can report fork
    # counts per mode. The control-client path bypasses this wrapper
    # entirely (it goes through self._control.request), so any non-zero
    # count in control mode reflects fallback subprocess invocations.
    _orig = _tm._run_tmux_async
    counts = {"n": 0}

    async def _counting(args, timeout: float = 5.0):
        counts["n"] += 1
        return await _orig(args, timeout=timeout)

    _tm._run_tmux_async = _counting

    session, tmpdir = setup_fixture(args.panes)
    try:
        async def run() -> tuple[list[float], list[float], int, int]:
            mon_sub = TmuxMonitor(session=session, multi_session=False)
            mon_ctrl = TmuxMonitor(session=session, multi_session=False)

            # start_control_client itself spawns one subprocess
            # (`tmux -C attach`) — reset the counter after that so the
            # measurement window only sees per-tick activity.
            await mon_ctrl.start_control_client()
            try:
                counts["n"] = 0
                t_sub = await measure(mon_sub, args.iterations, args.warmup)
                forks_sub = counts["n"]
                counts["n"] = 0
                t_ctrl = await measure(mon_ctrl, args.iterations, args.warmup)
                forks_ctrl = counts["n"]
            finally:
                await mon_ctrl.close_control_client()
            return t_sub, t_ctrl, forks_sub, forks_ctrl

        t_sub, t_ctrl, forks_sub, forks_ctrl = asyncio.run(run())

        for label, ts, forks in [
            ("subprocess", t_sub, forks_sub),
            ("control",    t_ctrl, forks_ctrl),
        ]:
            sorted_ts = sorted(ts)
            p95_idx = max(0, min(len(sorted_ts) - 1, int(len(sorted_ts) * 0.95)))
            p95 = sorted_ts[p95_idx]
            print(
                f"{label}: median={statistics.median(ts) * 1000:7.2f} ms  "
                f"p95={p95 * 1000:7.2f} ms  forks={forks}"
            )

        median_sub = statistics.median(t_sub)
        median_ctrl = statistics.median(t_ctrl)
        if median_ctrl > 0:
            print(f"speedup:    {median_sub / median_ctrl:.2f}x")
        if forks_ctrl > 0:
            print(f"fork ratio: {forks_sub / forks_ctrl:.1f}x")
        else:
            print(f"fork ratio: subprocess={forks_sub} forks vs control=0 forks")
    finally:
        _tm._run_tmux_async = _orig
        teardown_fixture(tmpdir)


if __name__ == "__main__":
    main()
