---
priority: low
effort: low
depends: []
issue_type: chore
status: Ready
labels: [task_workflow, claudeskills]
created_at: 2026-06-02 13:38
updated_at: 2026-06-02 13:38
boardidx: 120
boardcol: now
---

## Origin

Spawned from t909 during Step 8b review.

## Upstream defect

- `tests/test_skill_render_task_workflow.sh` (Test 5 header comment block) — the comment states "No committed profile sets the key", but `aitasks/metadata/profiles/fast.yaml` now sets `risk_evaluation: true`. As a result `planning-fast.md` (and the `SKILL-fast` golden) already render the gated risk steps. The comment is therefore stale/inaccurate.

## Diagnostic context

Noticed while implementing t909 (restructuring `planning.md` §6.1 risk-evaluation steps). The `risk_evaluation` gate is keyed off `profile.risk_evaluation`; only `fast.yaml` sets it among committed profiles. Test 5's assertions still pass because they use a synthetic `risk_evaluation: true` profile to prove the branch fires and check the `default` profile for absence — so the inaccuracy is comment-only, not a functional test defect. No behavior is wrong; only the explanatory comment misleads a future reader into thinking no committed profile activates the gate.

## Suggested fix

Update the Test 5 comment block in `tests/test_skill_render_task_workflow.sh` to say that `fast.yaml` sets `risk_evaluation: true` (so the committed `fast` goldens carry the gated steps), while the synthetic profile still exists to prove the branch fires independently of any committed profile and the `default` profile proves absence. Pure comment edit — no assertion changes, no golden regeneration.
