---
priority: medium
effort: medium
depends: [t1725_4]
issue_type: feature
status: Ready
labels: [ui, syncer, board, robustness]
gates: [risk_evaluated]
anchor: 1599
created_at: 2026-09-07 16:40
updated_at: 2026-09-07 16:40
---

## Context

Parent t1725, finding 1 (TUI side) / acceptance criterion 1: with one file held by a
live-locked task on this host, `ait syncer`'s deferral must show task id, path,
holder host / pid / pane, and the clearing action. Depends on **t1725_4** (which
completes the wire record: `pane`, `pane_state`) and, through it, on t1725_3
(`DeferredFile`, `SyncResult.deferred_files`, `--commit-for-task`, `--expect-path`,
`--require-waiting`, the `commit_scope_changed` / `holder_not_waiting` skips).

Today the syncer's `STATUS_DEFERRED` branch (`syncer_app.py:2264-2273`) renders
`deferred_reason (deferred_detail)` as a toast and deliberately bypasses
`_capture_failure` (a deferral is not a failure — do **not** change that). The
board (`aitask_board.py:12315-12325`) does the same.

**Design rule (mitigation `wire_fields_cover_screen`):** the screen renders the
parsed snapshot **only** — it never probes panes, reads locks or git. The record's
`pane_state` gates the *offer* of commit-on-behalf; the sweep's `--require-waiting`
re-probe gates the *commit*; `--expect-path` pins the *scope*. The user chose a
per-task override (the sweep's commit unit is the owning task's group, t1599_3),
surfaced per row.

## Key files

- `.aitask-scripts/lib/sync_action_runner.py` — `SyncConflictScreen` (the pattern:
  self-contained `DEFAULT_CSS`, `ModalScreen`, `dismiss(...)`), `run_sync_batch` /
  `sync_batch_command` (gain `extra_args`), `DeferredFile`
- `.aitask-scripts/syncer/syncer_app.py` — `_sync_data_worker`, `_on_data_sync_done`
  (~2214-2275), `_on_conflict_resolved`
- `.aitask-scripts/board/aitask_board.py` — `action_sync_remote` (~12267),
  `_run_sync` (~12280, `show_notification` / `show_overlay`), `_show_conflict_dialog`
- `tests/test_sync_action_runner.py` (module import pattern),
  `tests/test_syncer_rows.py` (untouched), `aidocs/framework/testing_conventions.md`
  (`App.run_test` + `@work` workers must be awaited), `aidocs/framework/tui_conventions.md`

## Implementation plan

1. `sync_action_runner.py`: `SyncDeferredScreen(ModalScreen)`, shared like
   `SyncConflictScreen`. Title `Sync deferred: <reason> — <N> file(s)`; one row per
   `DeferredFile`: `t<task>  <path>  <holder text>  <state>  <action>`. Holder text:
   `you · pid <pid> · pane <pane> · <pane_state>` for `self`; `<email> on <host> ·
   pid <pid>` for `other`; `<host> (unverified)` for `remote`; `identity unverified`
   for `unverified` — every value from the parsed record. Wide content scrolls
   inside the modal.
2. Buttons: **Commit t<id> on my behalf** — offered **only** for a `self` task whose
   parsed `pane_state` is `waiting_<kind>`; a `self` task whose record says `active`
   or `""` renders the row with the note "session is active — commit on its behalf is
   offered only while it waits on a prompt" and **no** button. Pressing it opens a
   **scope confirmation** listing the task id and **every path in that task's
   group** (all records sharing the `task`, tree state per path) plus the CLI's
   live-session warning; confirming runs
   `run_sync_batch(extra_args=["--commit-for-task", id, *["--expect-path", enc(p)
   for each listed path], "--require-waiting"])` (paths percent-encoded with the
   parser's inverse of `_pct_decode`) and re-dispatches the result through the same
   handler; a `commit_scope_changed` / `holder_not_waiting` outcome arrives as a new
   `STATUS_DEFERRED` and re-opens the screen with the fresh records. **Dismiss**.
3. `syncer_app.py` `_on_data_sync_done` `STATUS_DEFERRED`: keep the toast; push the
   screen when `deferred_files` is non-empty; the retry runs in the same
   `syncer-action` worker group.
4. `aitask_board.py` `_run_sync`: push the screen (via `call_from_thread`) only for
   the explicit `s` action (`show_overlay=True`); the `sync_on_refresh` background
   path stays toast-only.
5. No keybinding changes beyond the modal's own `escape`; nothing to add to
   `KNOWN_TUIS` or footers.

### Post-phase (risk mitigation `wire_fields_cover_screen`)

6. [wire_fields_cover_screen] A test builds `SyncDeferredScreen` from `DeferredFile`s
   produced **only** by `parse_sync_output` on literal `DEFERRED_FILE:` lines and
   asserts every rendered cell maps to a dataclass field (no TUI-side lookups of
   locks, files or git — patch `subprocess.run` / the tmux gateway to raise). If a
   needed field is missing, extend t1725_3's record and parser in the same commit and
   note it for t1725_6's field list.

## Verification

`tests/test_sync_deferred_screen.py` (`App.run_test`; await workers before the
block exits):
- rows render task / path / holder / email / host / pid / pane / state / action from
  parsed records;
- the commit button appears only for `self` rows whose `pane_state` is `waiting_*`;
  an `active` or `""` `self` row has no button (active holder cannot be silently
  committed — both states on the wire); an `other` / `remote` / `unverified` row has
  none;
- the scope confirmation lists exactly the paths of every record sharing that task,
  and the mocked `run_sync_batch` receives `--commit-for-task <id> --expect-path
  <each listed path, encoded> --require-waiting` (displayed scope == passed scope,
  pinned by comparing the two lists; the flag pinned present);
- a mocked retry result carrying `holder_not_waiting` / `commit_scope_changed`
  re-opens the screen with the new records;
- a record with `pane=""`, `pane_state=""` renders pid / host / action without
  raising and offers no button (the TUI half of t1725_4's
  `pane_unresolvable_degrades_to_pid`);
- the board's background-refresh sync does not push a screen; the explicit `s` does.
Run: `bash tests/run_all_python_tests.sh --test-dir tests` (last line is the verdict);
`tests/test_syncer_rows.py` untouched. Manual: `ait syncer` → `s` on an
`aitask-data` row while a live pane of yours holds a modified task file.
