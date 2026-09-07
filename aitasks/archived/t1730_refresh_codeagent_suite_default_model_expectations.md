---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
archived_reason: superseded
labels: [backend]
gates: [risk_evaluated]
anchor: 1162
created_at: 2026-07-29 09:55
updated_at: 2026-09-07 18:20
completed_at: 2026-09-07 18:20
boardidx: 118784
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

## Resolution

Completed by **t1318** ("Fix stale learn default assertion in shadow spawn test"),
which landed as commit `173a51698` — *"test: Derive code-agent default expectations
instead of pinning models (t1318)"*. That change added `tests/lib/codeagent_defaults.sh`
and rewrote all three suites named above to cross-check `invoke` against `resolve`
rather than pinning a model literal, which is the "prefer deriving them from the
copied seed configuration" fix this task's `## Suggested fix` asked for.

Re-verified on 2026-09-07, all green:

- `tests/test_codeagent_work_report.sh` — 28/28
- `tests/test_codeagent_trail.sh` — 27/27
- `tests/test_shadow_spawn_learner.sh` — 22/22

The one remaining `claudecode/opus4_8` literal, at `tests/test_shadow_spawn_learner.sh:46`,
is the deliberate explicit-override case ("Preserve explicit old-model override tests
that intentionally exercise a named model") — not staleness.

This file carried **no task number** in its filename until now: it was hand-written
into `aitasks/` as a side-file of commit `9e7f18326` ("ait: Revert t1311 to Ready")
rather than created through `ait create`, so it never claimed an id. **t1721**
renumbered it to t1730 so it could be archived through the supported path, added the
`ait ls` guard that skips unaddressable listing rows, and added
`tests/test_task_filename_invariant.sh` so the class cannot recur.
