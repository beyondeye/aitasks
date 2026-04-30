---
priority: medium
effort: medium
depends: [t713_2]
issue_type: refactor
status: Ready
labels: [tui, scripts, refactor]
created_at: 2026-04-30 10:27
updated_at: 2026-04-30 10:27
---

## Context

Parent **t713** ships a new `ait syncer` TUI that needs sync/pull/push actions
(t713_3). The board TUI (`aitask_board.py`) already has a working
implementation of the same actions: it shells out to
`.aitask-scripts/aitask_sync.sh --batch`, parses the structured output,
shows a conflict-resolution modal, and offers an interactive `./ait sync`
fallback.

If t713_3 lands as currently planned, the parsing/dispatch glue (~80 lines:
worker, status branching, conflict modal, interactive fallback) is duplicated
verbatim into `syncer_app.py`. Per CLAUDE.md ("Refactor duplicates before
adding to them") and t713_1's own precedent (extracting `desync_state` as
the second-caller refactor of `aitask_changelog.sh:check_data_desync`), the
glue must be extracted to a shared helper **before t713_3 adds the second
caller**.

This task is the second-caller-extraction sibling. It must land between
t713_2 (TUI shell) and t713_3 (sync actions); t713_3 will be updated to
depend on it.

## Backend (already shared — no changes here)

`.aitask-scripts/aitask_sync.sh --batch` is the authoritative push/pull/rebase
implementation. Both board and syncer call it. This task does NOT touch it.

## Code to extract (currently inside `aitask_board.py`)

| Piece | Current location |
|---|---|
| `_run_sync()` worker (subprocess + timeout + status-line parse) | `board/aitask_board.py:4097-4146` |
| Status branching (`CONFLICT:` / `NO_NETWORK` / `NO_REMOTE` / `NOTHING` / `AUTOMERGED` / `PUSHED` / `PULLED` / `SYNCED` / `ERROR:`) | same |
| `_show_conflict_dialog()` flow | `board/aitask_board.py:4148-4156` |
| `_run_interactive_sync()` (terminal-or-suspend fallback) | `board/aitask_board.py:4158-4168` |
| `SyncConflictScreen` modal | `board/aitask_board.py:2943-2975` |

## Key Files to Modify

- `.aitask-scripts/board/sync_action_runner.py` (new): shared module hosting
  the runner + status enum + conflict screen, designed to be imported by any
  Textual app.
- `.aitask-scripts/board/aitask_board.py`: replace the inline implementations
  with calls into the new module. `BoardApp.action_sync_remote` should reduce
  to a 2-3 line dispatch.
- (Optional) `.aitask-scripts/lib/`: if `board/` is the wrong home for shared
  TUI code in this repo, move to `lib/` instead. Decide during implementation
  by checking precedent (see Reference Files).

## Reference Files for Patterns

- `.aitask-scripts/lib/desync_state.py`: precedent for the second-caller
  extraction pattern (also from t713 family, archived as t713_1).
- `.aitask-scripts/lib/agent_launch_utils.py`: an existing example of a
  shared TUI helper module in `lib/`.
- `.aitask-scripts/board/aitask_board.py` `BoardApp.action_sync_remote` /
  `_run_sync` / `_show_conflict_dialog` / `_run_interactive_sync`: the code
  to extract.
- `.aitask-scripts/aitask_sync.sh` (top-of-file comment): the authoritative
  list of `--batch` status strings the parser must handle.
- `.aitask-scripts/board/aitask_board.py` `LoadingOverlay` (~2977-2987):
  loading-modal pattern to keep accessible to callers.

## Implementation Plan

1. **Decide module location.** Compare `lib/` (e.g., `desync_state.py`,
   `agent_launch_utils.py`) vs `board/` for TUI-flavored shared code; pick
   the one that matches existing precedent. Note any cross-module imports
   (`tui_switcher.py` lives in `lib/`).
2. **Create `sync_action_runner.py`** with:
   - A `SyncStatus` enum (or string-constants module) covering every
     `aitask_sync.sh --batch` status: `SYNCED`, `PUSHED`, `PULLED`, `NOTHING`,
     `AUTOMERGED`, `CONFLICT`, `NO_NETWORK`, `NO_REMOTE`, `ERROR`, plus a
     synthetic `TIMEOUT` / `NOT_FOUND`.
   - A `parse_sync_output(stdout: str) -> SyncResult` pure function (no
     Textual imports). Easy to unit-test.
   - A `run_sync_batch()` worker helper that subclassers call from a
     `@work(thread=True, exclusive=True)` method, returning a `SyncResult`.
   - A `SyncConflictScreen` modal (moved verbatim from `aitask_board.py`),
     parameterized only by the conflicted-files list.
   - A `run_interactive_sync(app)` coroutine that mirrors the existing
     terminal-or-suspend fallback.
3. **Refactor `aitask_board.py`** to import and use the module:
   - `BoardApp.action_sync_remote()` → call the shared runner.
   - Status notification mapping (e.g., "Auto-merged conflicts") can stay
     in the app since the wording is board-specific, but the parsing must
     come from the shared module.
   - `SyncConflictScreen` import path updated everywhere it's referenced.
4. **Add focused tests** for `parse_sync_output()` covering every status
   string. (Tests for the modal/worker remain manual since Textual snapshot
   tests are not the project convention.)
5. **Verify board still works end-to-end** in tmux: `./ait board`, trigger
   sync, simulate a conflict (e.g., dirty `.aitask-data` worktree against a
   remote ahead by one commit) and confirm the dialog and interactive
   fallback both fire.

## Out of scope

- Adding the syncer caller (that is **t713_3** — it will land after this
  task and consume the shared module).
- Changing `aitask_sync.sh` itself.
- Any UX changes to the board's sync flow beyond the import-path swap.

## Verification Steps

- `python3 -m py_compile .aitask-scripts/board/sync_action_runner.py` (or
  the chosen path).
- `python3 -m py_compile .aitask-scripts/board/aitask_board.py`.
- New unit test: `python3 tests/test_sync_action_runner.py` covering every
  status string parses correctly.
- Manual: `./ait board` in tmux still:
  - shows the same sync notifications (PUSHED / PULLED / NOTHING / etc.)
  - opens `SyncConflictScreen` on `CONFLICT:` and resolves via interactive
    fallback.
- Diff confirms ~80 lines removed from `aitask_board.py` (no behavior
  drift; pure extraction).

## Notes for sibling tasks

After this task lands, **t713_3** must be updated to:
- Depend on t713_8 (this task) instead of t713_2.
- Import the shared runner instead of re-implementing parsing/dialog/fallback.
- Limit its own scope to: action handlers in `syncer_app.py`, agent escape
  hatch (which is genuinely new), and the `main` ref pull/push (also new —
  `aitask_sync.sh` only handles `aitask-data`).
