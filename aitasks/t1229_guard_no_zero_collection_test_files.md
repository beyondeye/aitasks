---
priority: medium
effort: low
depends: []
issue_type: test
status: Ready
labels: [testing, python]
gates: [risk_evaluated]
anchor: 1211
created_at: 2026-07-24 10:56
updated_at: 2026-07-24 10:56
---

## Origin

Risk-mitigation ("after") follow-up for t1211, created at Step 8d after implementation landed.

## Risk addressed

Addresses the goal-achievement risk recorded in t1211's plan:

- AC 2's negative control is a manual, non-committed step; if skipped, a
  "passing" aggregate suite could still be pinning nothing · severity: low ·
  → mitigation: guard_no_zero_collection_test_files

It also guards the whole *defect-2 class*: a script-style or import-guarded test
file that contributes zero collected tests silently drops out of the aggregate
gate. t1211 found six such files (102 previously-unrun checks); nothing
currently prevents a seventh.

## Goal

Add a discovery guard asserting that every `tests/test_*.py` contributes at
least one collected test, so a script-style or import-guarded file can never
again silently drop out of the aggregate suite.

Implementation constraints (measured during t1211 planning — carry into the
task body, do not re-derive):

- The guard MUST inspect discovery **externally** — run `unittest discover` in a
  subprocess and count collected tests per module. Do NOT implement it as an
  in-process `TestCase` that imports its siblings: that is circular and
  re-triggers import-time side effects.
- It MUST also assert there are no `unittest.loader._FailedTest` entries. An
  import-failing module is attributed to the `unittest.loader` module rather than
  its own name, so a broken file would otherwise still register as a passing
  "test".
- Baseline at t1211 completion is an **empty** zero-collection set across all
  `tests/test_*.py` files, so no exclusion list is needed on day one. If one
  becomes necessary later it must be an explicit, commented allowlist — never a
  silent skip.
- `tests/run_all_python_tests.sh` prefers pytest when installed and falls back to
  unittest discovery; the two branches name modules differently, so the guard
  must state which branch it validates.

## Acceptance criteria

- [ ] A guard test fails when any `tests/test_*.py` contributes zero collected tests.
- [ ] The guard fails when a test module fails to import (no `_FailedTest` masking).
- [ ] The guard passes on the current tree with no exclusion list.
- [ ] The guard documents which `run_all_python_tests.sh` branch (pytest vs unittest) it validates.
- [ ] A negative control proves the guard is falsifiable (e.g. temporarily re-guarding a file to zero collection makes it fail).
