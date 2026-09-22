---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [task_metadata, bash_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
anchor: 1468
followup_kind: upstream_defect
created_at: 2026-08-13 23:29
updated_at: 2026-08-14 16:21
---

## Origin

Spawned from t1468_6 during Step 8b review.

## Upstream defect

`.aitask-scripts/lib/task_yaml.py:151` — `parse_frontmatter` normalizes task-id
lists for `depends` / `children_to_implement` / `folded_tasks` but **not** for
`verifies`, while `aitask_update.sh`'s serializer **does** canonicalize
`verifies` on write. The asymmetry means any read-modify-write silently
rewrites `verifies: ['635_11']` to `verifies: [t635_11]`.

## Diagnostic context

Surfaced by the t1468_6 `followup_kind` backfill, which drove
`aitask_update.sh --batch --followup-kind` over 167 tasks. Its delta assertion
compared each file before/after and flagged 19 files whose `verifies` field had
changed although the backfill never touched it:

- `t1015` `['635_11']` -> `['t635_11']`
- `t1243_15` `['1243_3', ...]` -> `['t1243_3', ...]` (11 ids)
- plus 17 more, all aggregate manual-verification tasks.

No data is lost — the two forms denote the same task ids, and the `t`-prefixed
form is the canonical one the writer emits. The problem is that a *reader*
comparing the two forms sees a spurious diff, and any tool that round-trips a
task file produces an unrelated change in its output. The backfill had to widen
its own delta check to tolerate this (`_norm_scalar` in
`.aitask-scripts/lib/followup_backfill_classify.py`), which is a workaround for
the asymmetry rather than a fix.

## Suggested fix

Add `verifies` (and audit `risk_mitigation_tasks` for the same issue) to the
normalization tuple at `task_yaml.py:151`, so read and write agree on the
canonical form. Check `tests/test_aitask_merge.py` and the board fixtures for
assertions that pin the un-normalized shape before changing it.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:10:40Z.dedf0973bbb405f42f81b06e from=t1794_9 from_verified=yes at=2026-09-22T06:10:40Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
> | 
> | Your plan aiplans/p1516_task_yaml_verifies_normalization_asymmetry.md cites stale anchors: aitask_board.py:3117-3122, aitask_board.py:4318 - re-verify it against the current modules before implementing.
