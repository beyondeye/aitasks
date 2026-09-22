---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [skills, ui, reporting, documentation]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1162_6]
created_at: 2026-07-19 12:22
updated_at: 2026-07-24 11:50
boardidx: 132096
---

## Context

`aitask-changelog` summarizes work that landed since the previous release. A complementary forward-looking workflow is needed for reporting what will be worked on today or this week to managers. Task membership must come from selected `ait board` columns, and each column's top-to-bottom `boardidx` order represents priority.

## Goal

Add a manager-facing `/aitask-work-report` skill and a contextual `w` action in the board TUI. The workflow must let users choose columns and include or exclude individual tasks before launching an agent, then produce an editable Markdown draft without writing a report file.

## Requirements

### Deterministic report input

- Add an internal gatherer that reads board configuration and active parent tasks, validates requested columns and task IDs, and returns structured data grouped in left-to-right board-column order.
- Preserve ascending `boardidx` order within every column. Include the dynamic Unsorted column when it exists.
- Support `/aitask-work-report --columns <comma-separated-column-ids>` with optional `--tasks <comma-separated-task-ids>`; normalize optional `t` prefixes and reject tasks outside the selected columns.
- Without explicit arguments, interactively select columns and review the ordered task list for inclusion/exclusion. With explicit task IDs, validate them and skip duplicate membership prompts.
- Treat the gatherer as an internal skill helper; do not add a new public `ait` CLI command.

### Manager-facing skill

- Add the canonical profile-agnostic skill and supported-agent wrappers following the repository's skill-authoring conventions.
- Ask for a report horizon on every run: Today, This week, or a custom label. The period labels the report but does not silently change task membership.
- Read each selected task's description, metadata, active plan when present, dependencies, and relevant child-task context.
- Draft first-person, manager-friendly Markdown containing a short focus summary, column-grouped ordered priorities with outcome and current status, task IDs for traceability, and a final blockers/manager-asks section.
- Include exactly the selected tasks. Do not invent dates, estimates, progress, commitments, dependencies, or blockers, and avoid implementation-level file/symbol detail.
- Present the draft for review/editing in the agent session only; do not automatically write a dated or repository report file.
- Use the shared satisfaction-feedback procedure with `skill_name: work-report`.

### Board workflow

- Register a customizable, footer-visible `w` binding named Work Report.
- Enable it only in persistent kanban views when a focused card or collapsed-column placeholder identifies a column; hide it in In-Flight/By-Topic views and when no reportable column is focused.
- First show a column multi-select with the focused column checked by default.
- Then show a task multi-select grouped by the chosen columns, with every underlying parent task checked by default. Use full column contents regardless of current search or board filters.
- Follow the existing SelectionList interaction: Space toggles, Enter confirms, Escape cancels. Preserve board ordering after exclusions.
- Do not launch when no columns or no tasks remain selected; show a clear notification instead.
- Launch the shared agent-command dialog with explicit `--columns` and `--tasks` arguments so the agent receives the exact board-reviewed selection.

### Agent dispatch and documentation

- Register `work-report` as a configurable read-only code-agent operation for Claude Code, Codex, and OpenCode, defaulting to the same lightweight model class used by `explain`.
- Treat the Codex operation as read-only analysis so it launches in default mode rather than forced Plan Mode.
- Add a skill reference page, a dedicated work-reporting workflow page, board shortcut/how-to documentation, and skills/workflows index entries.

## Verification

- Test gather ordering, multi-column grouping, selected subsets, optional `t` prefixes, invalid/moved/missing tasks, dynamic Unsorted behavior, duplicates, and empty selections.
- Add board Pilot/unit coverage for focused-column defaults, collapsed placeholders, full-column behavior under filters/search, selection cancellation, empty selection, footer visibility, shortcut registration, stable ordering, and exact launch arguments.
- Add dispatch dry-run tests for each supported agent and the Codex read-only policy.
- Run skill/wrapper verification and packaging/install coverage, plus documentation link/build checks.
- Manually smoke-test focusing a board column, pressing `w`, changing both selections, launching an agent, choosing a period, and confirming that the report contains exactly the selected tasks in board order.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:10:43Z.b6b5f522f19d7aed30c1ad56 from=t1794_9 from_verified=yes at=2026-09-22T06:10:43Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
> | Your plan aiplans/p1162_add_manager_facing_work_report_skill_and_board_flow.md cites stale anchors: aitask_board.py:4619, aitask_board.py:539-541 - re-verify it against the current modules before implementing.
