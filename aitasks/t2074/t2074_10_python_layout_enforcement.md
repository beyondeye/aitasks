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
updated_at: 2026-10-20 12:34
---

## Context

This child is part of t2074, which removes legacy repository mode. It brings the
Python consumers into line with the shell enforcement from t2074_9. The binding
contract is sections C0 and C1 of
`aiplans/p2074_remove_legacy_repository_mode_support.md`. Python must read the
layout state through `.aitask-scripts/lib/data_layout.py` (from t2074_1), which
calls the shell classifier once per process. It must never re-implement the
checks.

This child depends on t2074_7 (Python fixtures converted) and t2074_9 (shell
enforcement landed).

## Current state

- `board/board_task_manager.py:66` `_task_git_cmd` returns `["git"]` whenever
  `./.aitask-data/.git` is missing. In branch mode that also fires from a
  non-root cwd, which silently targets the wrong repo. It is re-exported by
  `aitask_board.py:176` and used at `aitask_board.py:6629` (`git rm -f`) and
  `board_detail_screen.py:59,1970` (`git checkout --`).
- `board/aitask_board.py:236` and `:2851` only run `sync_on_refresh` when
  `DATA_WORKTREE.exists()`, so legacy repos never sync.
- `lib/desync_state.py:150-159,246` reports `missing_worktree` for the
  `aitask-data` ref, and `syncer/syncer_app.py:700-705` consumes it.
- `lib/cross_repo_settings.py:84,488-489,545-552` uses
  `REASON_DEST_LEGACY_LAYOUT`, consumed by `syncer_app.py:77,245`. It refuses a
  destination repo whose `MODE:` is not `branch`. Keep it: the destination may
  be an older, unconverted install.
- `lib/parallel_admission_collect.py:68-80` falls back to code-branch-only
  classification when the data ref is missing. This is low priority: add a
  reason, or record why the fallback is content-only and safe.

## Implementation

1. `_task_git_cmd` resolves the data worktree through `lib/data_layout.py`,
   starting from the repo root rather than the cwd. It raises a clear error
   naming the state, the reason and the recovery when C1a is not `branch`.
   Every caller surfaces that error, for example as a toast, and never runs
   plain `git`.
2. The board checks C0 (reader class: C1a and C1b) at startup. On a non-ready
   layout it shows an explicit refusal with the recovery text. The
   existence-gated sync becomes an explicit refusal toast.
3. Reword `desync_state.py` `missing_worktree` and its `syncer_app.py` row as a
   broken or unconverted layout, with the recovery.
4. `REASON_DEST_LEGACY_LAYOUT` stays a refusal. Reword it to "destination not
   converted — run `ait setup` there". Read
   `aidocs/framework/tui_conventions.md:476` for the documented refusal row; the
   doc text itself is updated in t2074_12.

## Tests

- Update `tests/test_desync_state.py`, `tests/test_syncer_rows.py`,
  `tests/test_cross_repo_push_commit.py` (keep
  `test_legacy_layout_target_is_refused`) and
  `tests/test_cross_repo_settings.py`.
- New: a board test on a broken-layout fixture built with `board_fixture`.
  Assert the refusal and that no git command ran against the code repo.
- New: `_task_git_cmd` from a non-root cwd in a valid layout resolves to the
  data worktree.

## Verification

Run `bash tests/run_all_python_tests.sh`. The last line must read
`PYTHON SUITE: PASSED`.
