---
priority: high
effort: medium
depends: [t1118_2]
issue_type: feature
status: Ready
labels: [applink, applink_control, shadow]
gates: [risk_evaluated]
anchor: 1118
created_at: 2026-07-03 11:29
updated_at: 2026-07-03 11:29
---

## Context

Third child of t1118 (paired with `aitasks_mobile#32`). Adds the `spawn_shadow`
applink verb by extracting the desktop shadow-spawn flow into one shared
headless helper. Parent plan:
`aiplans/p1118_mobile_shadow_agent_driving_over_applink.md` (D2.1, D5).

## Key files to modify

- `.aitask-scripts/monitor/minimonitor_app.py` — `action_launch_shadow`
  (~1046-1147) body extracted; the action becomes a thin caller. Extraction
  covers: one-shadow-per-agent guard (`match_shadow_pane` pattern, ~99-119),
  task-id resolution, `resolve_dry_run_command(root, "shadow", pane_id[, task_id])`
  (`lib/agent_launch_utils.py:188`), `TmuxLaunchConfig` placement policy
  (`tmux.shadow_same_window` default True / `shadow_pane_width` default 60,
  from project tmux config), `launch_in_tmux`, `@aitask_shadow_target` stamping,
  `attach_shadow_cleanup_hook` (`agent_launch_utils.py:1303`).
- New shared helper `spawn_shadow_for_pane(...)` in `monitor_core.py` or
  `lib/agent_launch_utils.py` (choose the seam that avoids Textual imports —
  must be headless-safe for applink).
- `.aitask-scripts/applink/router.py` — new verb in `IMPLEMENTED_COMMAND_VERBS`
  + `_dispatch` branch: validate `pane_id` via `_req_pane_id` (`^%\d+$`) AND
  roster membership (`get_pane`/`_pane_cache`, reject unknown → `BAD_PAYLOAD`);
  existing shadow → `err BAD_PAYLOAD detail:{reason:"shadow_exists",
  shadow_pane}`; response `{ok, shadow_pane}`; audit-log attempts
  (SPAWN_TUI_REJECTED precedent, router.py:444-451). NOT a two-phase confirm
  verb (non-destructive; `spawn_tui` precedent).
- `aitasks/metadata/applink_profiles/full.yaml` + `applink/profiles.py`
  `DEFAULT_ALLOWED` (same commit — parallel surfaces) + flip the
  `permissions.md` row to implemented.

## Security constraints (t985 conventions)

- No shell interpolation of client input: `pane_id` is `%N`-format validated +
  roster-checked; `task_id` resolved server-side (never from the client).
- All tmux via the gateway (`lib/tmux_exec.py`); `tests/test_no_raw_tmux.sh`
  must stay green.

## Verification

- Router tests (StubMonitor): payload validation, `full` gating
  (`PERMISSION_DENIED` below), unknown-pane rejection, `shadow_exists` guard.
- Helper unit test with construction spies (launch config, stamp, cleanup hook
  invoked in order) — no live tmux needed.
- Minimonitor regression: `action_launch_shadow` still spawns via the helper
  (existing `tests/test_shadow_spawn_config.sh` family stays green).
