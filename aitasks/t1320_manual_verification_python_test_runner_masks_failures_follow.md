---
priority: medium
effort: medium
depends: [1179]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1179]
created_at: 2026-07-29 10:26
updated_at: 2026-07-29 10:26
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1179

## Verification Checklist

- [ ] On a machine WITH real pytest installed, run `bash tests/run_all_python_tests.sh` and confirm the last line reads `PYTHON SUITE: PASSED (runner=pytest, exit=0)` — the pytest branch was covered here only by a cwd-resolved stub, since no interpreter in this checkout has pytest
- [ ] On a machine WITH real pytest, run the same command against a fixture dir holding a failing test and confirm it exits non-zero and ends with `PYTHON SUITE: FAILED (runner=pytest, exit=<n>)`
- [ ] In a real terminal, run `bash tests/run_all_python_tests.sh --test-dir <dir-with-a-failing-test> 2>&1 | tail -40` and confirm the `PYTHON SUITE: FAILED` banner is visibly present in the scrollback (the stderr-adjacency claim), and that `$?` is 0 while `${PIPESTATUS[0]}` is non-zero
- [ ] Run `bash tests/run_all_python_tests.sh --test-dir <a real subdirectory of tests/>` by hand and confirm the subset-run ergonomics are usable
