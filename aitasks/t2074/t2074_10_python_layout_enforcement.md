---
priority: medium
effort: medium
depends: [t2074_7, t2074_9]
issue_type: refactor
status: Ready
labels: [python, board, syncer, data_integrity]
gates: [risk_evaluated]
anchor: 2074
created_at: 2026-10-20 12:33
updated_at: 2026-10-20 16:58
---

## Context

This task is part of t2074, rescoped to branch-mode layout hardening. **Legacy
mode stays supported.** It brings the board into line with the layout
enforcement table, and it is merged into t2074_9 as that child's **Step C**.
The binding contract is in `aiplans/p2074_branch_mode_layout_hardening.md`.

The bug: `board/board_task_manager.py:66` `_task_git_cmd` probes the
cwd-relative `./.aitask-data/.git` and otherwise falls back to `["git"]`. When
the board runs in branch mode from a cwd other than the repo root, it targets
the code repo. It also never re-validates during its long life.

## Scope (Step C)

**Repo-root resolution, validated fresh.** `_task_git_cmd` resolves from the
repo root, not the cwd. It **validates fresh on every call** through
`lib/data_layout.py` (from t2074_1) and never uses the cached `snapshot()`. A
worktree that was valid at startup can switch branches or break later, and the
same `git -C` prefix would then silently target the new branch.

**Two named operation classes**, following the enforcement table:
- **Git inspection of the data worktree (C1a only)**, via
  `require_repo_branch()`. This covers read-only status/dirty indicators, log,
  diff and show. These still run while C1b is `misdirected`, `dangling`,
  `mixed` or `unlinked`.
- **Mutations (C1a and C1b)**, via `require_branch_ready()`, checked
  immediately before each operation. This covers task-file edits,
  column/board-index moves, revert (`git checkout --`,
  `board_detail_screen.py:59,1970`), delete (`git rm -f`,
  `aitask_board.py:6629`) and any board-initiated commit.

`_task_git_cmd` takes an explicit class argument. A test enumerates every
caller and asserts its class.

Behaviour by state:
- In `legacy` or `uninitialized`, return `["git"]` explicitly, as today.
- A broken state raises with its recovery.
- Callers surface the error and never fall back to plain git.

**Board startup** applies the reader-class check and refuses, with the recovery
text, on a branch layout that is not ready. The sync gate at
`aitask_board.py:236` and `:2851` becomes an explicit refusal toast for broken
branch layouts. Legacy behaviour is unchanged.

**Not touched:** `desync_state`, `cross_repo_settings` and
`REASON_DEST_LEGACY_LAYOUT`.

## Tests

- From a non-root cwd, a valid layout resolves to the data worktree.
- A broken `board_fixture` is refused, and no git command runs against the
  code repo.
- The legacy board fixture still works.

**Same-process transitions.** Each transition gets its own test, and the
expected outcomes come from the enforcement table. Every test runs in one
process (`App.run_test` or the `board_task_manager` API). It starts from a valid
layout, where one inspection and one mutation both succeed, then applies the
transition:
- **(a) Branch switch** (`broken:wrong_branch`): inspection and every mutation
  refuse.
- **(b) `.aitask-data` deleted** (`broken:missing_storage`): inspection and
  every mutation refuse, with no plain-git fallback.
- **(c) `aitasks` repointed to another existing dir** (`branch`/`misdirected`):
  inspection succeeds; edit, revert and delete each refuse.

Every refusal must prove nothing changed:
- the content manifest is unchanged, including the redirected-to dir in (c);
- the HEAD, refs and index snapshots of both the data repo and the code repo
  are unchanged.

Planted control: a variant that reads the cached `snapshot()` must fail
case (a).

## Verification

Run `bash tests/run_all_python_tests.sh`. The last line must read
`PYTHON SUITE: PASSED`.
