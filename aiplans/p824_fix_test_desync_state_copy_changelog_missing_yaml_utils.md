---
Task: t824_fix_test_desync_state_copy_changelog_missing_yaml_utils.md
Worktree: (current branch — no separate worktree)
Branch: main
Base branch: main
---

# Plan: Add missing `yaml_utils.sh` to `copy_changelog()` test scaffold

## Diagnosis

`.aitask-scripts/lib/task_utils.sh:16` sources `yaml_utils.sh`
unconditionally. `tests/test_desync_state.py::copy_changelog()` copies
`task_utils.sh` into the test project but omits `yaml_utils.sh` from its
file list, so any test invoking `aitask_changelog.sh` after
`copy_changelog()` fails before the script body executes.

Reproduced on clean `main`: `test_changelog_warns_for_data_desync_and_ignores_bad_helper_output`
fails with `yaml_utils.sh: No such file or directory`.

Verified `yaml_utils.sh` itself has **no further** `source`/`.`
dependencies — adding it alone closes the gap (no further sibling libs
required).

## Change

`tests/test_desync_state.py:49` — extend the file list inside
`copy_changelog()`:

```python
for name in ["desync_state.py", "task_utils.sh", "terminal_compat.sh",
             "archive_utils.sh", "yaml_utils.sh"]:
```

No other source edits.

## Verification

- `python3 -m unittest tests.test_desync_state` runs all 6 tests green.

## Step 9: Post-Implementation

- Commit `tests/test_desync_state.py` with `bug: …` subject + `(t824)`.
- Plan file commit via `./ait git`.
- Archive via `aitask_archive.sh 824`; merge approval still required.

## Final Implementation Notes

- **Actual work done:** Added `"yaml_utils.sh"` to the file list inside `tests/test_desync_state.py::copy_changelog()` (line 49). One-line change as prescribed in the task.
- **Deviations from plan:** None.
- **Issues encountered:** None. Pre-fix reproduction confirmed the `yaml_utils.sh: No such file or directory` failure on `test_changelog_warns_for_data_desync_and_ignores_bad_helper_output`; post-fix run shows all 6 tests green.
- **Key decisions:** Verified `yaml_utils.sh` has no further `source`/`.` dependencies, so the file list closes at this single addition — no need to audit additional sibling libs.
- **Upstream defects identified:** None.

