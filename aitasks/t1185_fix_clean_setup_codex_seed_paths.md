---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [codexcli, codeagent]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1171
created_at: 2026-07-20 17:23
updated_at: 2026-07-20 18:13
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
