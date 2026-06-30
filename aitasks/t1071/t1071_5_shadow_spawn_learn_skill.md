---
priority: medium
effort: high
depends: [t1071_2]
issue_type: feature
status: Implementing
labels: [shadow, claudeskills]
assigned_to: dario-e@beyond-eye.com
anchor: 1071
implemented_with: claudecode/opus4_8
created_at: 2026-06-30 11:16
updated_at: 2026-06-30 18:54
---

Let the shadow agent, on user request while shadowing, **spawn a dedicated learner
agent** to learn a skill from the followed agent's executed workflow — WITHOUT running
the learn itself (the shadow's mandate is advisory/read-only, and a learn run would
occupy it). Depends on t1071_2 (the `/aitask-learn-skill` engine, which already accepts a
tmux pane id and does the capture/analysis), so this task is reduced to "spawn the
learner pointed at the followed pane".

## Design (from t1071_2 planning, see aiplans/archived/p1071/p1071_2_*)
- The shadow spawns a normal code agent (NOT another shadow) running
  `/aitask-learn-skill <followed_pane_id>` in a new tmux pane.
- The spawned learner captures the followed pane read-only and generates the skill in
  its own pane; the original shadow stays advisory and free to keep advising.

## Key files / mechanism
- NEW shadow Step 3 routing entry in `.claude/skills/aitask-shadow/SKILL.md` (greeting
  derives from Step 3 — do not hardcode).
- Reuse the spawn machinery used by minimonitor's shadow launch:
  `agent_launch_utils.launch_in_tmux()` + a new `aitask_codeagent.sh` invoke op
  (e.g. `invoke learn <pane_id>`, per-agent argv), routed through the tmux gateway
  (`lib/tmux_exec.*`). Model on `monitor/minimonitor_app.py action_launch_shadow()`.
- Learner-pane lifecycle/cleanup (it is a transient worker, not a shadow — decide whether
  it needs a classifier pane option or just user-managed cleanup).
- Keep the shadow advisory-only: it spawns; it never generates or drives the followed pane.

## Verification
- Spawning a learner from the shadow opens a new pane running `/aitask-learn-skill <pane>`;
  the original shadow remains responsive; the followed pane is never written to.
- tmux access stays within the gateway (`tests/test_no_raw_tmux.sh` passes).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-30T15:54:27Z status=pass attempt=1 type=human
