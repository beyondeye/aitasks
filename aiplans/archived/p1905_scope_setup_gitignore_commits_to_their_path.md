---
Task: t1905_scope_setup_gitignore_commits_to_their_path.md
Branch: main
Base branch: main
Output branch: main
---

# Plan: t1905 — scope setup's .gitignore commits to their path

## Finding: already fixed upstream by t1959

The defect this task records (the `setup_*_gitignore` helpers in
`.aitask-scripts/aitask_setup.sh` committing with a bare `git commit -m`, which
sweeps the whole index) was fixed by **t1959** in commit `c6fbbaf85`
("bug: Keep setup's .gitignore helper commits path-scoped and off pre-setup
changes"), one week after this task was spawned from t1852_5.

Verified against the tree at `e2116c90a`:

- Every `.gitignore` helper commits through one shared function,
  `_ait_commit_gitignore_rule()` (`aitask_setup.sh`), which runs
  `git add -- .gitignore && git commit -m "$msg" -- .gitignore` — the exact
  `-- .gitignore` pathspec this task suggested — and additionally refuses to
  commit over a `.gitignore` that was already dirty before setup started.
- Its seven call sites are exactly the seven helpers: `setup_draft_directory`,
  `setup_python_cache_gitignore`, `setup_gate_logs_gitignore`,
  `setup_testmap_gitignore`, `setup_worktree_dirs_gitignore`,
  `setup_shadow_store_gitignore`, `setup_scratchpad_gitignore`. No `.gitignore`
  helper commits any other way.
- The regression case the task asked for exists as **Test 27b** in
  `tests/test_setup_git.sh`, run for all seven helpers: pre-stage
  `foreign.txt`, run the helper, assert exactly one new commit, that it names
  only `.gitignore`, and that `foreign.txt` is still staged.
- `bash tests/test_setup_git.sh` → `Results: 164 passed, 0 failed`.

The remaining bare `git commit -m` calls in `aitask_setup.sh` are out of this
task's scope and are already scoped by other means: line ~1550 commits through a
private `GIT_INDEX_FILE`, and the data-branch initial commit (~1874/1876) runs in
the `.aitask-data` worktree that `setup_data_branch` itself has just created.
(The other data-branch and framework commits use `-- "${changed_files[@]}"`,
t1963.)

## Implementation

No code change. Close the task as done, crediting t1959.

## Verification

- `bash tests/test_setup_git.sh` — all pass (Test 27b covers the defect for all
  seven helpers).

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** None in code. Verified the defect was already fixed by t1959 (`c6fbbaf85`): all seven `.gitignore` helpers commit through `_ait_commit_gitignore_rule()` with a `-- .gitignore` pathspec, and `tests/test_setup_git.sh` Test 27b is the requested pre-staged-foreign-file regression for every helper. `bash tests/test_setup_git.sh` → 164 passed, 0 failed.
- **Deviations from plan:** None.
- **Issues encountered:** None. The task was spawned (from t1852_5, 2026-10-06) one week before t1959 landed the same fix independently.
- **Key decisions:** User chose to archive as done rather than abort, crediting t1959.
- **Upstream defects identified:** None
