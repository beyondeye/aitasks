---
priority: low
effort: medium
depends: [t1076_2]
issue_type: feature
status: Ready
labels: [task_attachments]
gates: [risk_evaluated]
anchor: 1065
created_at: 2026-07-06 18:30
updated_at: 2026-07-06 18:30
boardidx: 141312
---

**Design spec:** `aidocs/unified_artifact_design.md` §9 (lifecycle).

## Context

t1076_2 shipped a fail-closed guard in `ait attach decref-deleted`
(`.aitask-scripts/aitask_attach.sh::_attach_decref_deleted_txn`): a board
hard-delete of a task that still lists `artifacts:` entries ABORTS (die) unless
every handle is also listed by a `--protect-task` revived survivor. That guard
prevents silently stranding manifests, but pushes the work onto the user
("remove artifacts first"). This task replaces the guard with real handling.

## Key work

1. **Manifest lifecycle on hard-delete** — a decref-deleted analog for
   artifacts: when a doomed task is the last referrer of a handle, delete the
   manifest (and sweep orphan blobs with the same guards as
   `ait artifact rm`: keep blobs owned by the attachment meta ledger or
   referenced by any remaining manifest); when a `--protect-task` revived
   survivor lists the handle, ownership transfers (frontmatter already lists it
   — nothing to move; just don't delete the manifest). Then relax/remove the
   t1076_2 guard.
2. **Orphaned-manifest reaper** — a manifest no task file (active, archived, or
   Folded) references is unreachable via `ait artifact rm <task> <handle>`
   (rm is task-scoped). Reachable states: fold-then-archive (folded file deleted
   at archival after the primary rm'd its entry), historical bugs. Add a reap
   verb (e.g. `ait artifact gc` or an `rm --orphaned <handle>` escape hatch)
   that lists/removes such manifests, with the same blob-sweep guards.

## Reference files

- `.aitask-scripts/aitask_artifact.sh` — `_artifact_rm_txn` (the guards to
  reuse), `_artifact_handle_referenced_elsewhere` (the reference scan).
- `.aitask-scripts/aitask_attach.sh` — `cmd_decref_deleted` /
  `_attach_decref_deleted_txn` (the guard to replace; the rebind pattern).
- `.aitask-scripts/board/aitask_board.py` — `_decref_doomed_attachments`
  (fail-closed board call site).
- `tests/test_artifact_cli.sh` — decref-deleted guard cases to update.

## Verification

- Hard-delete of an artifact-bearing task cleans its manifests (or transfers to
  revived survivors) without user pre-work; blobs shared with attachments or
  other manifests survive (negative controls).
- The reaper finds and removes an orphaned manifest; a referenced manifest is
  never reaped (negative control).

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:10:30Z.7b56f36dbeada99c51ebfba6 from=t1794_9 from_verified=yes at=2026-09-22T06:10:30Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
>
> | t1794 split the board mono-file `.aitask-scripts/board/aitask_board.py`
> | (children t1794_1..8 landed; the last extraction is commit 387d8cb20). Any
> | `aitask_board.py:NN` anchor in your body or plan is STALE: aitask_board.py is
> | now ~6.8k lines (was ~13.7k) and most classes moved. Re-derive by symbol
> | (grep the class/function name), not by line number.
> | 
> | Where symbols live now (.aitask-scripts/board/):
> | - aitask_board.py: KanbanApp (incl. action_* handlers, _do_archive,
> |   action_work_report, sync), Kanban/InFlight/Topic columns, board-only modals
> |   (delete/archive/rename/commit/settings/cross-repo/gate choice), key map,
> |   command palette provider
> | - board_task_manager.py: TaskManager (paths injected as required kw-only
> |   tasks_dir / metadata_file / gates_registry_file; no module-global reads)
> | - board_task_model.py: Task, MoveResult, MergeResult
> | - board_workflow_phase.py: workflow-phase / in-flight derivation
> | - board_widgets.py: TaskCard, ColumnHeader, PickerItem, badge/marker helpers,
> |   LoadingOverlay
> | - board_detail_screen.py: TaskDetailScreen + its field widgets and pickers
> | - board_column_dialogs.py: ColumnEdit/Select/Manage/MultiSelect screens,
> |   ColorSwatch, column confirm dialogs
> | - board_trail_view.py: pure trail rendering - trail cards/columns, trail
> |   modals (TrailDetailScreen, TrailSelectScreen, summary), TRAIL_CSS
> | - board_trail_screen.py: TrailScreenMixin (all By-Trail actions),
> |   TRAIL_BINDINGS, TrailHost protocol, TRAIL_ACTION_CAPABILITIES
> | - trails_app.py: the new stand-alone `ait trails` TUI, hosting the same mixin
> | 
> | Rules a change to these files must keep (full text: contracts C1-C3 in
> | aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md; note that the
> | line ranges in that plan's "Target file map" are PRE-split mono-file anchors,
> | not current ones):
> | 1. Flat imports between board/*.py (`import board_x`), never `board.`-qualified.
> | 2. No board/*.py other than aitask_board.py reads TASKS_DIR / METADATA_FILE /
> |    etc. at import time - moved code receives paths by parameter.
> | 3. No board/*.py imports aitask_board.
> | All three are test-enforced (tests/test_board_package_contract.py,
> | tests/test_board_fixture_harness.py). Test patch targets follow the symbol:
> | patch board_task_manager.X (etc.), not aitask_board.X, for moved code.
> | 
> | Advisory, not an instruction: tree-relative claims above are as of the base
> | SHA this note records.
