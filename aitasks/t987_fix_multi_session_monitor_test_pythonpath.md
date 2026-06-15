---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_monitor, python]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-14 17:06
updated_at: 2026-06-15 16:06
boardidx: 50
---

## Origin

Spawned from t986_1 during Step 8b review.

## Upstream defect

tests/test_multi_session_monitor.sh:1 — fails on a clean tree with `ModuleNotFoundError: No module named 'monitor'`; the test's `python` invocation does not put `.aitask-scripts` on `PYTHONPATH` (reproduced after stashing all t986_1 changes). Pre-existing, almost certainly since the t822_6 monitor_core extraction, and out of scope for t986_1.

## Diagnostic context

While verifying t986_1 (multi-agent-per-window substrate), the monitor test suite was run. `tests/test_multi_session_monitor.sh` aborts immediately when its embedded Python imports `monitor.tmux_monitor` / `monitor.monitor_core`: `ModuleNotFoundError: No module named 'monitor'`. Stashing all t986_1 changes reproduced the same failure on a clean tree, confirming it is pre-existing (not introduced by t986_1). The sibling tests `tests/test_kill_agent_pane_smart.sh` and `tests/test_multi_agent_window_substrate.sh` set `PYTHONPATH="$REPO_ROOT/.aitask-scripts"` before invoking python and run fine; `test_multi_session_monitor.sh` appears to lack (or to have lost, post-t822_6) that path setup.

## Suggested fix

Set `PYTHONPATH="$REPO_ROOT/.aitask-scripts"` (or source the same venv/path bootstrap the passing monitor tests use) before the embedded `python` invocation in `tests/test_multi_session_monitor.sh`, then confirm the test exercises the multi-session discovery path end-to-end (it covers the live `_LIST_PANES_FORMAT` / `_parse_list_panes` discovery path that t986_1's 9-field change touched).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-15T13:06:24Z status=pass attempt=1 type=human
