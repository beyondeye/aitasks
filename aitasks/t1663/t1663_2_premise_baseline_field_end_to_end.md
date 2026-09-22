---
priority: medium
effort: medium
depends: [t1663_1]
issue_type: feature
status: Ready
labels: [task-workflow]
gates: [risk_evaluated]
anchor: 1538
created_at: 2026-09-01 15:19
updated_at: 2026-09-01 15:19
---

Add the `premise_baseline:` frontmatter field end-to-end: writer flag, merge rule, extension-point sweep, contract test, and documentation surfaces.

## Context

Second child of t1663. Design in `aidocs/framework/task_premise_staleness.md`. The field is `premise_baseline: <sha> @ <YYYY-MM-DD HH:MM>` — same grammar as `verification_baseline:`, but a distinct field (the MV field stays issue-type-scoped). Update-path only, like `plan_approved_at` (no interactive create prompt; child 3 adds the creation-time seeding separately).

## Key files

- `.aitask-scripts/aitask_update.sh` — `--premise-baseline` batch flag (empty string clears), positional threading through `write_task_file` (model: `--verification-baseline` at :205/:391/:619/:812-817/:2120-2126/:2253), value validated not accepted.
- `.aitask-scripts/board/aitask_merge.py` — add `premise_baseline` to `_BASE_AWARE_FIELDS` with `deletion_aware=True`. This is the **third** user of `_normalize_opaque_scalar` (:150-166), whose comment says the third user promotes the helper — do that promotion, don't add a fourth copy. The rationale block at :189-207 (why presence-based merge resurrects a dismissed baseline; why updated_at-based merge lets unrelated edits win) applies verbatim.
- `aidocs/framework/aitasks_extension_points.md` — walk the 5-layer checklist ("Adding a new frontmatter field"); the `plan_approved_at` worked example is the closest shape (update-only, contract test pinning sites).
- Docs surfaces: `website/content/docs/development/task-format.md` field table, `seed/aitasks_agent_instructions.seed.md` + generated mirrors, CLAUDE.md task-format block, `.claude/skills/task-workflow/task-creation-batch.md` note that `active`-style framework fields are not caller-authored (premise_baseline IS caller-visible via update).

## Reference files for patterns

- `tests/test_plan_approved_marker_contract.sh` — the contract-test shape: pin each write/clear site by hit count AND pin where the clear must NOT appear.
- `board/aitask_board.py` `Task`/`serialize_frontmatter` path — confirm the field round-trips through the board's writer without being dropped (BOARD_KEYS/BOARD_LAYOUT_KEYS seam, `tests/test_board_persistence_seam.py`).

## Verification (this child owns the concurrent-merge cases; pinned outcomes)

- `aitask_update.sh --batch <id> --premise-baseline "<sha> @ <ts>"` writes; `--premise-baseline ""` clears; malformed value rejected.
- Merge tests in the `aitask_merge.py` suite: (a) baseline cleared on one side + present on the other → stays cleared (deletion-aware, no resurrection); (b) an unrelated `--status` edit with newer `updated_at` does not win a baseline it never touched; (c) divergent advances on both sides → surfaced as PARTIAL/conflict, never a silently guessed winner.
- Contract test: every write/clear site pinned; board round-trip preserves the field.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:10:13Z.53ce91263516a7128172fae8 from=t1794_9 from_verified=yes at=2026-09-22T06:10:13Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
