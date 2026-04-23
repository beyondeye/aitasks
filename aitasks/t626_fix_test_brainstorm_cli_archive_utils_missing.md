---
priority: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [testing, bash_scripts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-23 12:32
updated_at: 2026-04-23 12:34
---

## Context

`tests/test_brainstorm_cli.sh` fails on Test 1 ("brainstorm init basic")
on `main` with:

```
.aitask-scripts/lib/task_utils.sh: line 14:
  .aitask-scripts/lib/archive_utils.sh: No such file or directory
```

Discovered during t573_2 implementation — pre-existing on `main`, not
caused by that task (verified via `git stash` test).

## Root Cause

The test's `setup_test_repo()` helper copies `lib/terminal_compat.sh`,
`lib/agentcrew_utils.sh`, and `lib/task_utils.sh` into the scratch repo
but does NOT copy `lib/archive_utils.sh`. However `task_utils.sh:13-14`
unconditionally sources `archive_utils.sh`:

```bash
# shellcheck source=archive_utils.sh
source "${SCRIPT_DIR}/lib/archive_utils.sh"
```

So any test that exercises a script that sources `task_utils.sh` (via
the aitask_query_files.sh path taken by aitask_brainstorm_init.sh) dies
at source-time.

## Key Files

- `tests/test_brainstorm_cli.sh` — the `setup_test_repo()` function
  (around line 80 onwards); add `archive_utils.sh` to the `cp
  .../lib/...` list.

## Implementation Plan

1. In `tests/test_brainstorm_cli.sh`, find the `cp
   .../terminal_compat.sh .../agentcrew_utils.sh .../task_utils.sh`
   line and add `archive_utils.sh` to it. (Or add a separate `cp` line —
   match the existing style.)
2. Re-run `bash tests/test_brainstorm_cli.sh` from the repo root and
   confirm all tests pass.
3. While there: also audit whether any OTHER tests copy `task_utils.sh`
   without `archive_utils.sh` — likely candidates are any `test_*.sh`
   with a scratch-repo setup. Fix any found.

## Verification

- `bash tests/test_brainstorm_cli.sh` exits 0 and prints all PASS lines.
- `shellcheck tests/test_brainstorm_cli.sh` stays clean.
- `grep -l 'task_utils.sh' tests/*.sh | xargs grep -L 'archive_utils.sh'`
  returns nothing (or only tests that don't set up a scratch repo).
