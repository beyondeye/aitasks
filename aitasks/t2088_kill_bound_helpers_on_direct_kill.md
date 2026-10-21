---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitask_monitormini, tmux, scratchpad]
gates: [risk_evaluated]
anchor: 2073
followup_kind: risk_mitigation
created_at: 2026-10-21 08:43
updated_at: 2026-10-21 08:43
---

## Origin

Risk-mitigation ("after") follow-up for t2073_4, created at Step 8d after implementation landed.

## Risk addressed

bound helpers survive direct kill-pane paths

- Bound helpers survive the direct `kill-pane` paths (the pane branch of `kill_agent_pane_smart`, and a frozen-record drop) because no `pane-died` fires. Live case D asserts this · severity: medium · → mitigation: kill_bound_helpers_on_direct_kill

## Goal

Kill panes bound to an agent (shadow/scratchpad target options) when kill_agent_pane_smart's pane branch or a frozen-record drop kills that agent directly, with tests for both paths.

Concretely:

- Both paths kill the agent with a plain `kill-pane`, which fires no `pane-died`, so `aitask_companion_cleanup.sh` job 1 never runs:
  - `monitor_core.TmuxMonitor.kill_agent_pane_smart`, the pane branch taken when other real agents remain in the window;
  - `lib/agent_freeze.drop_record`, via `frozen_ops.kill_if_stamped`, when a real sibling keeps the window.
- After the kill, also kill every pane whose `@aitask_shadow_target` or `@aitask_scratchpad_target` (`lib/helper_panes.BOUND_HELPER_TARGET_OPTIONS`) equals the killed pane. Apply frozen-first: a pane carrying `@aitask_frozen` is never treated as a helper.
- Never touch helpers bound to a sibling that is still alive. Keep the shared rule in `lib/helper_panes.py`, so there is no third hard-coded marker list.
- Tests for both paths (mocked), plus the live flip: `tests/test_scratchpad_spawn_live.sh` case D currently ASSERTS the pad is left behind (known gap). Flip it to assert the pad is killed, and add the same for a shadow.
