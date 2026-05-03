---
priority: medium
effort: high
depends: []
issue_type: performance
status: Ready
labels: [performance, monitor, tui]
children_to_implement: [t719_3, t719_4, t719_5, t719_6]
created_at: 2026-04-30 08:34
updated_at: 2026-05-03 09:02
boardidx: 60
---

## Goal

Replace per-tick `subprocess` spawns in `tmux_monitor.py` with a single persistent `tmux -C` (control-mode) connection so monitor/minimonitor refresh time is not bound by `fork()` + `exec(tmux)` overhead.

## Background

`aidocs/python_tui_performance.md` documents the analysis. Key facts:

- `monitor_app.py` (1778 LOC) and `minimonitor_app.py` (733 LOC) refresh every 3 s. On each tick `tmux_monitor.py::capture_all_async()` spawns one `tmux capture-pane` subprocess per agent pane via `asyncio.create_subprocess_exec`. With 5–10 agents that's 6–15 fork+exec cycles per tick. Aux subprocesses (list-panes, display-message, has-session, etc.) add more.
- Per-call cost is ~1–10 ms of OS-level fork+exec. **Compile/JIT options (PyPy, Nuitka, mypyc) give ~0% here.** The fix is architectural.
- `tmux -C` (control mode) opens a single persistent tmux client that accepts commands on stdin and emits structured `%begin/%end/%output` blocks on stdout. One connection replaces N forks per tick.
- Alternative `tmux pipe-pane` could push pane content continuously to a fifo, eliminating polling entirely. Worth investigating but more invasive.

## Approach

Phase 1 — Control-mode connection layer:

1. **`.aitask-scripts/monitor/tmux_monitor.py`**: introduce `TmuxControlClient` class:
   - On start, spawn `tmux -C attach -t <session>` (or `tmux -CC` for a control-mode session) once.
   - Implement an async request/response queue parsing `%begin <id> <time> <flags>` … `%end <id> …` blocks.
   - Replace `subprocess.run(["tmux", ...])` and `_run_tmux_async(...)` paths in the hot loop (`capture_all_async`, `discover_panes_async`, `_capture_args` callers) with `client.send_command(...)`.
   - Keep one-shot subprocess fallback for cold init / availability check.
2. **Aux subprocesses in `monitor_app.py` and `minimonitor_app.py`** (display-message, list-windows, has-session, send-keys for jump): route through the same client.
3. **Lifecycle**: client owned by the Textual app; close cleanly on exit / mount failure.
4. **Error handling**: if control mode connection drops (tmux server exit), fall back to per-call subprocess and try to reconnect.

Phase 2 — Adaptive polling (optional, smaller win):

- If no pane content has changed across the last K ticks, double the poll interval up to a cap. Reset to base interval on any change.

Phase 3 — `pipe-pane`-based push model (optional follow-up):

- Investigate replacing periodic `capture-pane` polling with `pipe-pane` writing to per-pane fifos that the monitor reads asynchronously. Eliminates the polling entirely. Defer unless Phase 1 doesn't yield enough.

## Validation

- Add a microbenchmark script (e.g., `bench/bench_monitor_refresh.py`) that runs N refresh ticks against a fixture session and reports total time and per-tick subprocess count. Compare before/after.
- Manual verification: launch `ait monitor` and `ait minimonitor` against a session with 5+ agent panes; confirm UI feel and idle-detection accuracy unchanged.

## Out of scope

- Any TUI re-design or visual changes.
- PyPy/Nuitka work — handled by sibling task `t<pypy_task_id>`.
- Replacing `subprocess` for short-lived non-monitor scripts.

## Acceptance Criteria

- Per-refresh subprocess count for `monitor_app` and `minimonitor_app` drops from `1 + N + aux` to roughly 0 (steady state) — verified by microbenchmark.
- Refresh wall-time reduced significantly (target ≥ 5× on a 5-pane fixture).
- Idle-detection behavior, focus restoration, and auto-close logic remain identical (no regressions in existing manual flows).
- Falls back gracefully to subprocess mode if `tmux -C` is unavailable or disconnects mid-run.

## Reference

`aidocs/python_tui_performance.md` — full background and analysis.
