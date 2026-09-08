---
priority: medium
effort: medium
depends: [1725_1]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 1599
followup_kind: verification_failure
created_at: 2026-09-08 17:16
updated_at: 2026-09-08 17:16
---

## Failed verification item from t1725_1

> Run the full suite without piping away the exit status (`set -o pipefail; bash tests/run_all_python_tests.sh 2>&1 | tail -20`); expect `PYTHON SUITE: PASSED`, and note whether the parallel (pytest+xdist) or serial unittest lane ran — t1729 was verified on the serial lane only.

### Source

- **Manual-verification task:** `aitasks/t1737_verify_macos_fixes_on_linux.md` (item #1)
- **Origin feature task:** t1725_1
- **Origin archived plan:** `aiplans/archived/p1725/p1725_1_abort_conflicted_pull_rebase_in_task_utils.md`

### Commits that introduced the failing behavior

- 42ee07791 bug: Abort a conflicted pull --rebase, but only ever our own (t1725_1)

### Files touched by those commits

- .aitask-scripts/aitask_pick_own.sh
- .aitask-scripts/lib/task_utils.sh
- tests/lib/test_scaffold.sh
- tests/test_task_push.sh

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1737 item #1.
