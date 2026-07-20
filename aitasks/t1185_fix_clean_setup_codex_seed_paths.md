---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [codexcli, codeagent]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1171
implemented_with: claudecode/opus4_8
created_at: 2026-07-20 17:23
updated_at: 2026-07-20 22:52
boardidx: 70
---

## Origin

Spawned from t1180 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:2067 and :2081 — clean data-branch initialization does not seed codex_config.seed.toml or codex_rules.default.rules into aitasks/metadata, while setup reads only those paths; fresh ait setup therefore omits the default_mode_request_user_input feature required by t1171.`

## Diagnostic context

A disposable clean clone and home completed `ait setup` with no `pexpect` in its dependency declarations. Its resulting `.codex/config.toml` lacked `[features]` and `default_mode_request_user_input = true`.

The fresh data branch contained `codex_instructions.seed.md`, but not the Codex config or rules seed files. The source repository contains those missing seeds under `seed/`, while setup reads only the task-data metadata paths.

## Suggested fix

Seed the Codex config and rules files into fresh task-data initialization, or make setup fall back to the repository `seed/` paths when their task-data copies are absent. Add a clean-install regression test covering the merged default-mode prompt feature.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-20T19:51:54Z status=pass attempt=1 type=human
