---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: high
depends: []
issue_type: refactor
status: Implementing
labels: [aitask_monitormini, aitask_monitor, tmux, python]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-14 16:02
updated_at: 2026-06-14 16:38
---

## Context

Foundation child of t986 (shadow agent). The shadow companion is a *second*
coding-agent CLI spawned in the **same tmux window** as the agent it shadows.
Today the tmux gateway + capture are pane-keyed (safe), but six monitor
app-layer sites assume **one agent per window**. This child makes a window
robustly hold N real agents by re-keying monitor state on `pane_id`, and
classifies the `shadow` pane as a helper/companion so it is **never listed among
agents** in monitor/minimonitor (an explicit user requirement).

**True deps:** none (this is the foundation). **Coordinates t719** (monitor
tmux-control-mode refactor touches the same `monitor_core.py` — rebase/coordinate
to avoid conflicts).

## Key Files to Modify

- `.aitask-scripts/monitor/monitor_core.py`
  - `TaskInfoCache` (~1398-1450) + `_TASK_ID_RE` (~1381): key task lookup by
    `pane_id` (or `(window_index, pane_index)`), not bare `window_name`.
  - `kill_agent_pane_smart()` (1278-1318): count *agent* panes in the window
    correctly; only `kill_window()` when ALL agent panes are gone, else
    `kill_pane()`.
  - `_is_companion_process()` (152-170) + `classify_pane()` (~877-944): recognize
    a `shadow` pane as a companion/helper (excluded from agent snapshots, like
    minimonitor/monitor are today).
- `.aitask-scripts/monitor/minimonitor_app.py`
  - `_find_sibling_pane_id()` (674-697): resolve the *intended* agent pane by id,
    not `other_panes[0]`. The followed agent is identified via
    `_find_own_agent_snapshot()` (~403-422) — reuse that pane id.
  - `monitor_app.py` display sites (~982, 1120, 1509-1513): derive task-id per
    pane, not per window.
- `.aitask-scripts/lib/agent_launch_utils.py`
  - pane-`.0` refocus after companion spawn (754-758): refocus the
    just-launched pane (captured from `new-window`/`split-window -P`), not `.0`.
  - `maybe_spawn_minimonitor()` 3-pane skip (728-740): account for a possible
    shadow pane so the companion still spawns correctly.
- `.aitask-scripts/aitask_companion_cleanup.sh`: per-pane `pane-died` accounting
  so killing one agent in a shared window does not despawn the companion while
  another agent still lives.

## Reference Files for Patterns

- Capture is already pane-keyed: `monitor_core.py:capture_pane()` /
  `capture_all_async()` (1112-1170) key by `pane_id` — mirror that keying.
- Companion detection precedent: `_is_companion_process()` checks
  `/proc/<pid>/cmdline` for `minimonitor`/`monitor_app` — extend with the shadow
  marker (window name `agent-shadow-*` and/or the shadow op in cmdline).
- `find_companion_pane_id()` (monitor_core.py ~1233-1256) — example of
  pane-in-window discovery by PID.

## Implementation Plan

1. Extract the pure pane→task-id mapping and the per-window agent-pane-count
   logic into small testable helpers (no Textual imports — keep in
   `monitor_core.py` headless layer or a new headless helper module).
2. Re-key `TaskInfoCache` on `pane_id`; thread pane id through the monitor/
   minimonitor display + sibling/kill paths.
3. Extend companion classification to flag shadow panes; ensure
   `discover_panes()`/`classify_pane()` filter them out of agent lists.
4. Fix the launch-path refocus + 3-pane-skip and the cleanup hook for the
   multi-pane case.
5. Keep all raw tmux behind the gateway (`tests/test_no_raw_tmux.sh` must stay
   green).

## Verification Steps

- `bash tests/test_<new>.sh` covering: pane_id-keyed task map; two agents in one
  window → killing one leaves the other alive with correct task-ids; sibling
  resolution returns the intended agent pane; a `shadow`-classified pane is
  absent from agent snapshots.
- `shellcheck .aitask-scripts/aitask_companion_cleanup.sh`.
- `bash tests/test_no_raw_tmux.sh` (allowlist unchanged).
- Manual smoke (covered by the t986 aggregate manual-verification sibling):
  open two agent panes in one tmux window via the gateway and confirm monitor +
  minimonitor behave.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-14T13:38:38Z status=pass attempt=1 type=human
