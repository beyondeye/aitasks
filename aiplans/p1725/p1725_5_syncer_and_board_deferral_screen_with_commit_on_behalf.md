---
Task: t1725_5_syncer_and_board_deferral_screen_with_commit_on_behalf.md
Parent Task: aitasks/t1725_sync_deferrals_actionable_and_safe_to_continue.md
Sibling Tasks: aitasks/t1725/t1725_1_*.md, aitasks/t1725/t1725_2_*.md, aitasks/t1725/t1725_3_*.md, aitasks/t1725/t1725_4_*.md, aitasks/t1725/t1725_6_*.md
Archived Sibling Plans: aiplans/archived/p1725/p1725_*_*.md
Base branch: main
Output branch: main
---

# t1725_5 — syncer + board deferral screen with commit-on-behalf

Parent plan: `aiplans/p1725_sync_deferrals_actionable_and_safe_to_continue.md`,
section "Child 5". Finding 1 (TUI) / AC1. Depends on t1725_4 (complete wire record).
Read `aidocs/framework/tui_conventions.md` and
`aidocs/framework/testing_conventions.md` (`App.run_test` + `@work`) first.

## Design rule

The screen renders the parsed `DeferredFile` snapshot **only** — no pane probing,
no lock or git reads. `pane_state` gates the *offer*; the sweep's `--require-waiting`
gates the *commit*; `--expect-path` pins the *scope*. Override is per task (the
sweep's commit unit), surfaced per row. `_capture_failure` stays bypassed for a
deferral.

## Files

`.aitask-scripts/lib/sync_action_runner.py` (`SyncConflictScreen` as the pattern;
`run_sync_batch` / `sync_batch_command` gain `extra_args`),
`.aitask-scripts/syncer/syncer_app.py` (`_on_data_sync_done` ~2214-2275),
`.aitask-scripts/board/aitask_board.py` (`action_sync_remote` ~12267, `_run_sync`
~12280), new `tests/test_sync_deferred_screen.py`.

## Steps

1. `SyncDeferredScreen(ModalScreen)` in `sync_action_runner.py`: title `Sync
   deferred: <reason> — <N> file(s)`; one row per record: `t<task>  <path>  <holder
   text>  <state>  <action>`; holder text per class (`you · pid · pane · <pane_state>`
   / `<email> on <host> · pid` / `<host> (unverified)` / `identity unverified`);
   wide content scrolls inside the modal.
2. Button **Commit t<id> on my behalf** only for a `self` task whose `pane_state`
   is `waiting_<kind>`; otherwise the row note "session is active — commit on its
   behalf is offered only while it waits on a prompt" and no button. The button
   opens a scope confirmation listing the task id + every path of the records
   sharing that task (tree state per path) + the live-session warning; confirm →
   `run_sync_batch(extra_args=["--commit-for-task", id, *["--expect-path", enc(p)
   …], "--require-waiting"])`, result re-dispatched through the same handler
   (a `commit_scope_changed` / `holder_not_waiting` outcome re-opens the screen with
   fresh records). **Dismiss**.
3. `syncer_app.py` `STATUS_DEFERRED`: keep the toast; push the screen when
   `deferred_files` is non-empty; retry in the `syncer-action` worker group.
4. `aitask_board.py` `_run_sync`: push the screen (`call_from_thread`) only when
   `show_overlay=True` (explicit `s`); background `sync_on_refresh` stays toast-only.

### Post-phase (risk mitigations)

5. [wire_fields_cover_screen] Build the screen from records produced only by
   `parse_sync_output` on literal `DEFERRED_FILE:` lines with `subprocess.run` and
   the tmux gateway patched to raise; assert every rendered cell maps to a dataclass
   field. A missing field → extend t1725_3's record + parser in the same commit and
   flag it for t1725_6.

## Verification

`tests/test_sync_deferred_screen.py`: rows render every field from parsed records;
button only for `self` + `waiting_*` (none for `active` / `""` / other classes);
scope confirmation lists exactly the task's paths and the mocked `run_sync_batch`
receives `--commit-for-task <id> --expect-path <each, encoded> --require-waiting`
(displayed == passed); a mocked `holder_not_waiting` / `commit_scope_changed` retry
re-opens the screen; `pane=""` / `pane_state=""` renders and offers no button;
board background sync pushes no screen, explicit `s` does.
Run `bash tests/run_all_python_tests.sh --test-dir tests`; `tests/test_syncer_rows.py`
untouched. Manual: `ait syncer` → `s` on an `aitask-data` row while a live pane of
yours holds a modified task file.

## Step 9

Standard post-implementation; parent t1725 archives after the last child.
