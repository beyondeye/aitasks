---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [claudeskills]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1071
created_at: 2026-06-30 19:07
updated_at: 2026-07-01 10:40
completed_at: 2026-07-01 10:40
---

## Origin

Spawned from t1071_5 during Step 8b review.

## Upstream defect

`tests/test_shadow_spawn_config.sh:31-33` — stale default-agent assertion. The test
asserts that the **default** agent for the `shadow` operation resolves to claudecode
("default shadow resolves to claude" / "default shadow emits /aitask-shadow with
args"), but the project `aitasks/metadata/codeagent_config.json` now sets
`"shadow": "codex/gpt5_5"`. So `aitask_codeagent.sh --dry-run invoke shadow %5 ...`
resolves to a `codex -m gpt-5.5 …` command, and 2 assertions fail
(`13/15 passed, 2 failed`).

## Diagnostic context

Surfaced while running `tests/test_shadow_spawn_config.sh` as a regression check
during t1071_5 (which added a parallel `learn` codeagent op). The failures predate
t1071_5 and are not caused by it — t1071_5 does not touch the `shadow` default. The
test comment at line 30 still claims `defaults.shadow → claudecode/opus4_8`, which no
longer matches the committed config.

## Suggested fix

Pin the default-resolution assertions to an explicit `--agent-string claudecode/...`
(so the test is independent of the project's configurable `shadow` default), OR
update the expected default to match the current config and refresh the stale line-30
comment. Pinning to an explicit agent string is preferred — it keeps the test stable
across future per-project default changes (mirrors how the other per-agent assertions
already pass an explicit `--agent-string`).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **🔄 gate:risk_evaluated** run=2026-07-01T07:40:14Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:69a6dee0d843f7aa

> **✅ gate:risk_evaluated** run=2026-07-01T07:40:14Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1095/risk_evaluated_2026-07-01T07:40:14Z-risk_evaluated-a1.log`
