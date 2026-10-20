---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [framework, git, data_integrity, bash_scripts]
gates: [risk_evaluated]
anchor: 2074
created_at: 2026-10-20 12:31
updated_at: 2026-10-20 17:01
---

## Context

This is the first child of t2074 (rescoped: **branch-mode layout hardening**;
legacy mode stays supported and unchanged). It provides the classifiers that
t2074_3 (setup repair) and t2074_9 (enforcement) build on. The binding contract
is **C1a, C1b and the no-marker precedence table** in
`aiplans/p2074_branch_mode_layout_hardening.md`. Read it first.

**Additive only.** No existing caller changes behaviour in this child.

## Deliverables

1. **C1a `ait_data_repo_state`** in `.aitask-scripts/lib/data_symlinks.sh`
   (sourced by `task_utils.sh:26`). It prints `<state>[:<reason>]` and
   **always returns 0, never dies**, including under `set -euo pipefail`,
   inside `$( )` and inside `local x="$( )"`.

   **Resolution order:**
   1. The cwd is inside the data worktree (T13c).
   2. A local marker: `./.aitask-data`, then `<toplevel>/.aitask-data`. A
      separate-git-dir primary resolves here without calling
      `ait_main_worktree_root`.
   3. The main checkout's marker, only if local resolution fails (T13d). If
      that lookup returns 2: fall through when `ait_linked_worktree_roots`
      proves the checkout is not linked, otherwise return
      `indeterminate:topology`.
   4. Otherwise, the no-marker table. Outside a work tree: `not_a_repo`.

   **Validation, first failure wins:**
   1. `broken:stale_marker`: a stale gitdir, an empty `.git`, a pruned admin
      dir, or `.aitask-data` without `.git`.
   2. `broken:foreign_repo`: the canonical common-dir differs.
   3. `broken:wrong_branch`. A detached HEAD during an in-progress operation
      is valid but wedged when the operation's own record names `aitask-data`:
      `rebase-merge/head-name`, `rebase-apply/head-name`, or `BISECT_START`.
      Any other detached HEAD, or any other branch, is `wrong_branch`.

   **No-marker precedence.** Each of `aitasks`/`aiplans` is a `data_link`
   (raw target equal to the `ait_data_link_target` literal), a `real_dir`, an
   `other_link` or `absent`. Rows are checked in order:
   1. Either path is a `data_link` → `broken:missing_storage`. This includes a
      real `aitasks/` alongside a dangling `aiplans` link.
   2. Otherwise, any `real_dir` → `legacy`. A stale registration or a leftover
      ref is ignored.
   3. Otherwise, a registered or prunable worktree record at
      `<root>/.aitask-data` → `broken:missing_storage`.
   4. Otherwise, unchanged from today: `legacy` if `aitasks` resolves to a
      dir, else `uninitialized`.

   A leftover `aitask-data` ref is never evidence.
2. **C1b `ait_data_paths_state`.** This applies in branch mode only, and
   compares canonical `$PWD/$TASK_DIR` and `$PWD/$PLAN_DIR` with
   `<data>/aitasks` and `<data>/aiplans`. States: `ready`, `unlinked`,
   `misdirected` (which includes a `TASK_DIR` override outside `<data>`),
   `dangling` and `mixed`. In legacy mode it reports `legacy`.
3. Checks run filesystem-first (gitdir file, `commondir`, `HEAD`,
   `BISECT_START`, `readlink`), with a git fallback. Results are cached per
   process. A code comment must say that this is valid **only** because shell
   commands are short-lived, and that long-running loops must re-validate
   before each mutation.
4. **CLI `.aitask-scripts/aitask_data_layout.sh`** prints `REPO:<state>` and
   `PATHS:<state>`. Follow `aidocs/framework/aitasks_extension_points.md` for
   the helper whitelists.
5. **`.aitask-scripts/lib/data_layout.py`** never re-implements the checks. It
   exposes:
   - `snapshot()`, which is cached and for **display only**;
   - `require_repo_branch()` and `require_branch_ready()`, which are **fresh on
     every call**. They run the CLI and raise on a refusing state. Long-lived
     processes must call them before each git operation and each write.
6. **`git-health` state reporting** (`task_git_health`, `task_utils.sh:513`).
   This is behind the shared-file gate: if `task_utils.sh` still carries
   uncommitted t2064 hunks, skip it and hand it to t2074_9 with
   `./ait note 2074_9 --from 2074_1`.

## Tests

`tests/test_data_layout_classifier.sh` and `tests/test_data_layout.py`.

**One fixture per state and reason:**
- **`stale_marker`:** a stale gitdir, an empty `.git`, a pruned admin dir, and
  `.aitask-data` without `.git`.
- **`foreign_repo`:** an unrelated repo, a clone, and another repo's worktree.
- **`wrong_branch`:** `checkout <sha>`, and a bisect started from another
  branch.
- **Links:** dangling, misdirected (to an existing other dir), missing in a
  linked worktree, and a `TASK_DIR` override.
- **`mixed`.**
- **`missing_storage`**, one fixture per row: links dangle after `.aitask-data`
  is deleted (row 1); a real `aitasks/` plus a dangling `aiplans` link (row 1,
  refused, not legacy); a prunable record with neither path (row 3); an
  `other_link` with no marker (row 4, unchanged).

**Positive cases:**
- mid-rebase, and mid-bisect with `BISECT_START`=`aitask-data`: `branch`
- T13c: `branch` / `ready`
- T13d: `branch` / `unlinked`
- a `--link-worktree`'d worktree: `branch` / `ready`
- a separate-git-dir primary: `branch`, with no main-root call
- its unresolved linked checkout: `indeterminate:topology`, returned rather
  than dying
- a nested repo or submodule: its own state

**Legacy controls, all of which stay `legacy`:**
- a legacy repo root, and a subdirectory of it
- a legacy repo with a leftover `aitask-data` ref
- a legacy repo with a stale `.aitask-data` record plus a real `aitasks/`

**Also:**
- never-dies checks under errexit, for every fixture;
- a filesystem-vs-git differential;
- Python/shell parity;
- a test that `require_*()` re-evaluates after a branch switch in the same
  process.

## Verification

- The new tests pass.
- `bash tests/test_task_git.sh` and `bash tests/test_init_data.sh` stay green.
- `shellcheck` is clean.
