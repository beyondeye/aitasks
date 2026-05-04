---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [testing, tui, monitor]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-03 19:14
updated_at: 2026-05-04 16:26
---

## Origin

Spawned from t732_1 during Step 8b review. Surfaced while running the adjacent regression sweep `for t in tests/test_*tui*.sh tests/test_*monitor*.sh; do bash "$t"; done` after fixing Cluster A. This test was already failing on `main` before t732_1's changes (verified by stashing t732_1 changes and re-running) — it is **NOT** in t732's listed scope (which only covered `test_multi_session_minimonitor.sh` + `test_tui_switcher_multi_session.sh`).

## Upstream defect

`tests/test_multi_session_monitor.sh` — multi-session `discover_panes` aggregation broken on `main` today. 6/43 failing assertions (all in the same test):

```
FAIL: multi-session discover_panes aggregates both sessions (expected 'COUNT:2', got 'COUNT:1')
FAIL: panes from sessA are tagged (expected to contain 'PANE:sessA:%1:agent-t42-claudecode', got 'COUNT:1
PANE:sessB:%2:agent-t43-claudecode')
FAIL: sessA panes come first after sort (expected to contain 'PANE:sessA:%1', got 'PANE:sessB:%2:agent-t43-claudecode')
FAIL: companion filter still excludes companions in multi mode (expected to contain 'COUNT:1', got 'COUNT:0')
FAIL: non-companion pane survives (expected to contain 'PANE:%1', got 'COUNT:0')
FAIL: real tmux: sessB pane discovered (expected to contain 'PANE:aitmon_<pid>_b:agent-t2', got 'COUNT:1
PANE:aitmon_<pid>_a:agent-t1')
```

## Diagnostic context

t732_1 fixed Cluster A (Textual API drift in `MiniMonitorApp` test scaffold + `tui_switcher._render_desync_line` query-before-mount). After landing those, the broader sweep revealed `test_multi_session_monitor.sh` still failing — a *different* test (note: `monitor`, not `minimonitor`) targeting the **monitor** TUI's `TmuxMonitor.discover_panes()` multi-session aggregation, not the **minimonitor** code path that t732_1 touched.

Stashing t732_1's two-line patches and re-running confirmed the failures were pre-existing on `main` @ `74c59788` (and 312fe99a after t732_5's scaffold restore). They're a parallel-but-distinct failure pattern: same-theme (multi-session TUI infrastructure) but a different module (TmuxMonitor / agent_launch_utils discovery, not the overlay or app-level threading).

## Suggested fix

Read `tests/test_multi_session_monitor.sh` for the exact test fixtures, then read `.aitask-scripts/monitor/tmux_monitor.py` (or wherever `discover_panes` lives — `grep -rn 'def discover_panes' .aitask-scripts/`). The `COUNT:1` vs `COUNT:2` failure suggests the multi-session iteration was either:

1. Regressed by a recent commit (check `git log --oneline -- .aitask-scripts/monitor/`).
2. Broken by a session-discovery API change in `agent_launch_utils.discover_aitasks_sessions()` (since `test_tui_switcher_multi_session.sh` Tier 2 still passes, that helper itself is fine — but the monitor's *consumer* of it may have drifted).

Start with `git log -p tests/test_multi_session_monitor.sh` to see whether the test was recently updated to a new contract that the production code never shipped.

## Verification

- `bash tests/test_multi_session_monitor.sh` reports 0 failures (or all 43/43).
- Adjacent sweep stays clean: `for t in tests/test_*monitor*.sh; do bash "$t" >/dev/null 2>&1 || echo "FAIL: $t"; done` reports nothing new.
