---
priority: high
effort: medium
depends: [t1118_2]
issue_type: feature
status: Ready
labels: [applink, applink_control, shadow, tmux_destructive]
gates: [risk_evaluated]
anchor: 1118
created_at: 2026-07-03 11:29
updated_at: 2026-07-28 18:38
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1118** id=2026-11-09T08:33:48Z.9feb6837038d541b44c3669a from=t1118 at=2026-11-09T08:33:48Z base=87b720e7ce727f7a18ece35fa8a70c070fc81f9a base_branch=main dirty=yes host=omg16
>
> | Advisory from the user-requested review of t1118; not an implementation approval. Source inspected at aitasks HEAD 87b720e7ce727f7a18ece35fa8a70c070fc81f9a.
> | 
> | The proposed extraction from minimonitor.action_launch_shadow has already happened. monitor_core.spawn_shadow is the shared, Textual-free mechanics seam behind BOTH monitor and minimonitor e/E flows (t1216_4); each app retains a _spawn_shadow policy adapter. match_shadow_pane/find_shadow_pane_status are already shared too. Re-extracting the historical minimonitor body or copying launch_in_tmux + resolve_pane_id_by_pid would duplicate the seam and drop later fixes.
> | 
> | Current spawn_shadow uses launch_split_pane / launch_window_pane -P identity on both placement branches, guarded recovery only when needed, a last-moment fail-closed duplicate lookup, _stamp_or_remove on binding failure, and attach_companion_cleanup_hook. It accepts explicit companion_pane and select_window policy, notify/schedule_refresh callbacks, and optional phase_signal. For a headless/server consumer, companion_pane=None safely binds cleanup to the new shadow and avoids treating the applink server pane as a disposable minimonitor companion; select_window=False avoids stealing desktop focus. These are existing helper semantics, not a request for a new spawn subsystem. See monitor_core.py:spawn_shadow and both desktop _spawn_shadow adapters; aidocs/framework/shadow_agent.md documents the policy split and identity/cleanup safeguards.
> | 
> | find_shadow_pane_status returns (verified, existing): unverifiable is not 'no shadow'. spawn_shadow's None result also covers more than duplicate refusal, so the router's shadow_exists response cannot be inferred from every None return. The helper's final recheck remains important even if the router checks before invoking it. Existing tests/test_monitor_shadow_pick.py, test_minimonitor_shadow_pick.py, test_monitor_shadow_spawn_live.sh and test_shadow_spawn_config.sh cover the evolved seam.
> | 
> | As of this audit applink/server.py still constructs TmuxMonitor, and t2037_4 is in flight to move status reads onto MonitorClient. The helper only needs the gateway surface; subscription-backed producer reads and local action routing must remain distinct when the migration lands. In particular MonitorClient.get_pane intentionally excludes shadows, so this task's existing followed-agent validation should remain agent-facing while its sibling supplies an applink-specific shadow projection.
