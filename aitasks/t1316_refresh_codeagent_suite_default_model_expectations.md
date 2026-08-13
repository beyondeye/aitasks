---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [backend]
gates: [risk_evaluated]
anchor: 1162
followup_kind: upstream_defect
created_at: 2026-07-29 09:56
updated_at: 2026-08-13 23:06
boardidx: 80896
---

## Origin

Spawned from t1221 during Step 8b review.

## Upstream defect

- `tests/test_codeagent_work_report.sh:80` — seeded and fallback model assertions still expect `sonnet4_6` / `opus4_8` after configuration moved to `sonnet5` / `opus5`.
- `tests/test_codeagent_trail.sh:81` — seeded and fallback model assertions still expect `opus4_8` after configuration moved to `opus5`.
- `tests/test_shadow_spawn_learner.sh:67` — default learn resolution still expects `opus4_8` after configuration moved to `opus5`.

## Diagnostic context

While verifying t1221's skill-launch composer hardening, `tests/test_codeagent.sh` passed 156/156 and every composer-specific assertion in the auxiliary suites passed. `tests/test_codeagent_work_report.sh`, `tests/test_codeagent_trail.sh`, and `tests/test_shadow_spawn_learner.sh` remained red solely because their seeded/default resolution assertions name obsolete Claude models. The current seed configuration and fallback resolve to `sonnet5` and `opus5`.

## Suggested fix

Update the obsolete expected defaults, preferably deriving them from the copied seed configuration where that keeps the tests meaningful and prevents harmless model rotations from making unrelated composer suites red. Preserve explicit old-model override tests that intentionally exercise a named model.
