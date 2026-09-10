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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1725_3** id=2026-09-09T19:24:18Z.40417ea1ebd824f46c4374c4 from=t1725_3 from_verified=yes at=2026-09-09T19:24:18Z base=9cb61927c8910812c2c6a3fa852663cf7ad9bd8e base_branch=main dirty=no host=omg16
>
> | t1725_3 landed. Two things change what you can build, and one is a contract
> | narrowing you cannot work around from your side.
> | 
> | 1. `--expect-path` is a ONE-TASK contract, not a global set.
> | 
> |    As first implemented it was a single global list compared against every task
> |    group in turn, which meant `--commit-for-task 10,20` with one confirmed path
> |    per task made task 10 see task 20's path as "missing" and vice versa: both
> |    groups refused as `commit_scope_changed`, zero commits, and the combined form
> |    silently did nothing while appearing to work. Measured, not theorised.
> | 
> |    Rather than grow a per-id expectation syntax, the ambiguous combination is
> |    now REFUSED up front (`die`), as are `--expect-path` and `--require-waiting`
> |    without `--commit-for-task`. So: a screen that lets a user confirm files
> |    across two different tasks must issue TWO sync runs, one per task. If that is
> |    wrong for your design, say so and the per-id syntax can be added -- the
> |    refusal was chosen as the fail-closed option, not as a final answer.
> | 
> | 2. `sync_batch_command` still builds a hard-coded two-element argv.
> | 
> |    `lib/sync_action_runner.py` `sync_batch_command()` returns
> |    `[script, "--batch"]` with no `extra_args` parameter, deliberately left alone
> |    -- threading the new flags from a TUI is yours. `run_sync_batch` passes
> |    whatever it returns straight to `subprocess.run`.
> | 
> | What you should NOT have to do:
> | 
> | - Re-derive anything. Every field the deferral screen renders is already on the
> |   wire. Each `DEFERRED_FILE:` line is
> |   `<sub_reason>|<task>|<path>|<tree_state>|<holder>|<email>|<host>|<pid>|<pane>|<pane_state>|<action>`
> |   and parses into `SyncResult.deferred_files: list[DeferredFile]`. If a field
> |   your screen needs is missing, extend the record in aitask_sync.sh rather than
> |   re-reading locks or the dirty set in the TUI -- that re-derivation is the
> |   thing this child exists to remove.
> | - `holder` is `self|other|remote|unverified|none` and is what should gate
> |   whether you OFFER commit-on-behalf at all. `self` is deliberately hard to
> |   reach (same verified host AND same email); `unverified` is what an unreadable
> |   lock branch now reports, and it must never be treated as `none`.
> | - `action` is a ready-to-show prescriptive line, already per-class.
> | 
> | Two cautions:
> | 
> | - `pane` and `pane_state` are emitted EMPTY by t1725_3. t1725_4 fills them.
> |   Design for empty, because a run on a box where the probe cannot resolve the
> |   pane will keep emitting empty even after t1725_4 lands.
> | - Textual fields are percent-decoded by the parser but may contain lone
> |   surrogates: a git path may hold bytes that are not valid UTF-8, so
> |   `run_sync_batch` decodes with `errors="surrogateescape"`. Writing such a value
> |   to a strict-UTF-8 stream RAISES. Rendering one safely is explicitly your
> |   task's problem, and `DeferredFile`'s docstring says so.
> | 
> | Advisory only, and dated -- verify against the tree rather than trusting the
> | line numbers implied above.

> **✉ note:t1725_4** id=2026-09-10T12:47:57Z.874c20ae98042c6aca95b9a3 from=t1725_4 from_verified=yes at=2026-09-10T12:47:57Z base=2f023c5949cddc06c78d11777a11edd8c2abfbbd base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1725_4 (its code landed in 76a113510). A claim about that tree, not an instruction.
> | 
> | The `pane_state` column your commit-on-behalf offer keys on (`waiting_<kind>` → show the button) is derived from SCREEN TEXT only: `lib/pane_state_probe.py` captures the holder pane through the tmux gateway and classifies it with `monitor_core._classify_one`, scoped by `agent_keys.agent_key_from_pane`. When the pane's agent does not resolve (a shell, a wrapper — anything that is not claude/codex/opencode at rung 1 or as a single child at rung 2), matching runs over the whole unscoped pattern list, so a pane that merely displays copied AskUserQuestion text reads `waiting_claude_askuserquestion`.
> | 
> | What still holds: the sweep's `--require-waiting` re-probes at commit time (it never trusts the snapshot your screen rendered), the offer is for `self` rows only, and the 5a.3 re-check and publication guard still apply. The exposure is bounded, but `waiting_*` is not proof that an agent is waiting.
> | 
> | Tracked as t1787 (durable agent provenance for the gate, e.g. a launch-time pane marker; depends on t1725_4). Possibly relevant to your plan: whether the modal should say "the pane shows a prompt" rather than asserting the agent is waiting, and whether t1787's outcome should change when the button appears.
> | 
> | For your tests: `tests/lib/sync_fixture.sh` now pins AITASKS_TMUX_SOCKET to a socket nothing serves, at file scope. To get pane resolution, call `require_isolated_tmux` first and pass SYNC_FIXTURE_TMUX_SOCKET=<your -L name> per sweep; `tests/test_sync_holder_pane_live.sh` is a working template (redraw-from-file pane, bottom-aligned screen, UTF-8 locale).

> **✉ note:t1731** id=2026-09-10T18:09:21Z.36b54b32c39447d12459e8f2 from=t1731 from_verified=yes at=2026-09-10T18:09:21Z base=e2f12c49990459143f2e387db431b5222fc66ef7 base_branch=main dirty=no host=omg16
>
> | t1731 landed (commit e2f12c499) a new batch status your deferral screen will meet. Advisory; tree-relative claims below are dated by that commit.
> | 
> | NEW STATUS `MERGED`. `aitask_sync.sh --batch` now prints the bare token `MERGED` when a DIVERGED aitask-data branch whose rebase was blocked by protected dirty files was converged by a guarded merge commit and pushed. The protected files — the ones this screen lists — are left dirty and uncommitted. It is a SUCCESS status, not a deferral:
> | - `STATUS_MERGED = "MERGED"` in lib/sync_action_runner.py, accepted like SYNCED;
> | - syncer_app.py and aitask_board.py notify it at information severity ("Sync: Merged — protected files left uncommitted"), with no failure capture;
> | - it never carries `DEFERRED_FILE:` records.
> | So a screen keyed on DEFERRED must not open on MERGED, and after a MERGED run there is nothing "blocking sync" to show even though the held files are still dirty.
> | 
> | WHY A MERGE DECLINED. When a diverged run still defers, stderr now carries exactly one extra line:
> |   sync: Guarded merge not possible (<slug>): <detail>
> | The slug is a closed set: not_diverged, unknown_state, rev_unresolved, multiple_merge_bases, sides_overlap, merge_conflict, protected_written, ignored_written, ff_refused. It is stderr prose only — deliberately NOT on the wire. If the screen should show why the merge declined, that belongs on the wire (e.g. a field on the status line or a record), not in a parser of stderr.
> | 
> | Unchanged: `DEFERRED:protected_dirty`, the `DEFERRED_FILE:` record format, and the --commit-for-task / --expect-path / --require-waiting flags.
