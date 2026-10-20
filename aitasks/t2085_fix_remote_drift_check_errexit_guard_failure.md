---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [testing, gates]
anchor: 1852
followup_kind: upstream_defect
created_at: 2026-10-20 18:40
updated_at: 2026-10-20 18:40
---

## Origin

Spawned from t1859_1 during Step 8b review.

## Upstream defect

- `.claude/skills/task-workflow/remote-drift-check.md:27` — `tests/test_skill_errexit_capture.sh`'s errexit-unsafe `$?` guard fails on the `./.aitask-scripts/aitask_remote_drift_check.sh "<base_branch>" "<plan_file>"; echo "DRIFT_RC:$?"` capture that t2061 (`c643a8390`) added. It was already failing at HEAD; it is unrelated to t1859_1.

## Diagnostic context

While verifying t1859_1 (2026-10-20, main @ `e2116c90a`), `bash tests/test_skill_errexit_capture.sh` reported `Results: 65/66 passed, 1 failed`:

```
FAIL: guard: no errexit-unsafe $? read in any authoring skill file (expected '', got '.claude/skills/task-workflow/remote-drift-check.md:27: ./.aitask-scripts/aitask_remote_drift_check.sh "<base_branch>" "<plan_file>"; echo "DRIFT_RC:$?"
```

t1859_1 did not touch `remote-drift-check.md` or the guard test. The last commit to touch the procedure is t2061 `c643a8390`, which introduced the `DRIFT_RC:` capture line.

## Suggested fix

Two options:

- Rewrite the documented capture into the errexit-safe `if …; then rc=0; else rc=$?; fi` form the guard enforces (the same form `build-verification.md` uses), keeping the `DRIFT_RC:<rc>` contract the procedure parses.
- Or, if `; echo "DRIFT_RC:$?"` is deliberately safe here (the agent runs it as a non-errexit one-liner), add a narrowly scoped, justified allowlist entry to the guard. Do not weaken the guard globally.

Re-render the task-workflow goldens and prerenders after the edit.
