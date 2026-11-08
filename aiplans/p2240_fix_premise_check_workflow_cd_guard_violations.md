---
Task: t2240_fix_premise_check_workflow_cd_guard_violations.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2240 — Fix the two cd-guard violations in test_premise_check_workflow.sh

## Context

`bash tests/test_cd_guard_lint.sh` is red on the live tree (91/92) because of two
`unconfined-andchain` sites committed in 620039d7b (t1663_4):

- `tests/test_premise_check_workflow.sh:154` (inside `padv()`):
  `( cd "$d" && { lock --check … \⏎ || lock --lock …; } )` — the `||` after the
  continuation is at group depth 1, so the scanner (`tests/lib/cd_guard_scan.py`,
  `_confined_andchain`) rejects it. Semantically it is safe today (a failed cd
  skips the brace group), but it is not an accepted form.
- `tests/test_premise_check_workflow.sh:487` (J5): a two-line subshell
  `( cd "$P" && unlock …⏎  AIT_AGENT_PID=$FORCER lock … )` — a **real**
  fall-through: if the cd fails, the second line still runs in the caller's cwd.

Accepted form per the scanner docstring / `aidocs/framework/testing_conventions.md`:
`cd "$X" || exit 1` (guarded). Inside a `( … )` subshell, `exit 1` leaves only the
subshell, so the caller's behaviour is unchanged (both sites already ignore the
subshell's status / redirect output).

## Implementation

Single file: `tests/test_premise_check_workflow.sh`.

1. Line 154–155 (in `padv()`), replace with:
   ```bash
   ( cd "$d" || exit 1
     ./.aitask-scripts/aitask_lock.sh --check "$id" >/dev/null 2>&1 \
       || ./.aitask-scripts/aitask_lock.sh --lock "$id" --email "$OWNER" >/dev/null 2>&1 )
   ```
2. Lines 487–488 (J5), replace with:
   ```bash
   ( cd "$P" || exit 1
     ./.aitask-scripts/aitask_lock.sh --unlock 606 >/dev/null 2>&1
     AIT_AGENT_PID=$FORCER ./.aitask-scripts/aitask_lock.sh --lock 606 --email "$OWNER" >/dev/null 2>&1 )
   ```

Pre-checked in planning: piping both rewritten snippets through
`python3 tests/lib/cd_guard_scan.py --check /dev/stdin` → rc 0, while the original
J5 lines through the same route → `unconfined-andchain`, rc 1 (negative control).

## Verification

- `bash tests/test_cd_guard_lint.sh` → all pass (92/92).
- `bash tests/test_premise_check_workflow.sh` → still passes (its own summary + exit 0).
- `shellcheck tests/test_premise_check_workflow.sh` — no new warnings vs. before.
- `git diff --stat` shows only this file.

Commit: `bug: Exit-guard the two cd sites in test_premise_check_workflow.sh (t2240)`.
Then Step 9 (Post-Implementation): archival via the task-workflow.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
