---
Task: t883_fix_desync_test_fixture_python_resolve.md
Worktree: (none — profile 'fast', worked on current branch)
Branch: main
Base branch: main
---

# Plan: Fix test_desync_state.py fixture — add python_resolve.sh (t883)

## Problem

`tests/test_desync_state.py::test_changelog_warns_for_data_desync_and_ignores_bad_helper_output`
builds a self-contained fixture project and runs
`bash .aitask-scripts/aitask_changelog.sh --gather` inside it. The fixture
builder `copy_changelog()` (line 49) copies a **hardcoded** list of lib files
into the fixture's `.aitask-scripts/lib/`, but the list omitted
`python_resolve.sh`. Since `task_utils.sh:18` sources `python_resolve.sh`
unconditionally (and `aitask_changelog.sh:9` sources `task_utils.sh`), the
fixture's changelog run failed with
`python_resolve.sh: No such file or directory`. Pre-existing; surfaced during
t881's Python suite run, unrelated to t881.

## Fix

Add `python_resolve.sh` to the copy list at `tests/test_desync_state.py:49`,
grouped with the other base shell libs (after `terminal_compat.sh`):

```python
for name in ["desync_state.py", "task_utils.sh", "terminal_compat.sh", "python_resolve.sh", "archive_utils.sh", "yaml_utils.sh"]:
```

## Dependency analysis (blast radius)

Full source chain for `aitask_changelog.sh --gather` inside the fixture:

- `aitask_changelog.sh:9` → `task_utils.sh`
- `task_utils.sh` → `terminal_compat.sh` (12), `archive_utils.sh` (14),
  `yaml_utils.sh` (16), `python_resolve.sh` (18)
- `python_resolve.sh:41` → `terminal_compat.sh` (already present)
- `archive_utils.sh:22` → `terminal_compat.sh` (already present)

All transitive deps are now satisfied. `python_resolve.sh` does **not** require
`aitask_path.sh` at runtime (the `aitask_path.sh` mention in its header is a
documentation comment about PATH-based subprocess resolution), so no further
additions are needed. Minimal one-line change is the complete fix.

## Verification

`python3 tests/test_desync_state.py` → `Ran 6 tests in 0.779s — OK`
(was failing before the change).

## Step 9 (Post-Implementation)

Single-file test fix on the current branch (no worktree/branch to merge).
Archive via `./.aitask-scripts/aitask_archive.sh 883`.

## Final Implementation Notes

- **Actual work done:** Added `"python_resolve.sh"` to the hardcoded lib-copy
  list in `tests/test_desync_state.py:49`. One-line change.
- **Deviations from plan:** None — the implemented change matches the task's
  suggested fix exactly.
- **Issues encountered:** None functionally. (Environment note: the session's
  tool-output channel was severely batching/delaying results during this task,
  which slowed verification but did not affect the change.)
- **Key decisions:** Minimal fix (add the single missing leaf lib) rather than
  refactoring the Python fixture to route through the bash
  `tests/lib/test_scaffold.sh::setup_fake_aitask_repo` scaffold. That scaffold
  is bash-only; a Python↔bash bridge to share the copy-list would be a larger
  change than warranted for a low-effort fix. The "route fixtures through a
  shared helper so the list cannot drift again" idea is recorded as a possible
  future refactor, not done here.
- **Upstream defects identified:** `tests/test_pr_contributor_metadata.sh:76` — the test's fixture lib-copy omits `cross_repo_reexec.sh` (sourced by `aitask_ls.sh:7`); running `bash tests/test_pr_contributor_metadata.sh` reproduces 2 failing subtests with a missing-source error. Same fixture-drift *class* as t883 but a different missing lib; surfaced while auditing other tests during t883 diagnosis. Out of scope for t883's one-line fix — candidate standalone follow-up.
  - Cleared (NOT defects): the other ~8 bash tests that copy `task_utils.sh` into a fake lib dir (`test_zip_old.sh`, `test_fold_validate.sh`, `test_create_silent_stdout.sh`, `test_parallel_child_create.sh`, `test_archive_no_overbroad_add.sh`, `test_task_push.sh`, `test_lock_force.sh`) all **pass** — they call `setup_fake_aitask_repo` in `tests/lib/test_scaffold.sh`, which already pre-copies `python_resolve.sh`.
- **Notes for sibling tasks:** N/A (no siblings).
