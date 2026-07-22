---
priority: medium
effort: high
depends: [t1162_3]
issue_type: feature
status: Ready
labels: [ui, reporting]
gates: [risk_evaluated]
anchor: 1162
created_at: 2026-07-22 10:46
updated_at: 2026-07-22 10:46
---

## Context

Fourth child of t1162. Adds the contextual `w` (Work Report) action to the board TUI: column multi-select → task multi-select → shared agent-command dialog launching `/aitask-work-report` with the exact board-reviewed selection. Parent plan: `aiplans/p1162_add_manager_facing_work_report_skill_and_board_flow.md` (t1162_4 section). Requires t1162_2 (`work-report` operation) for command resolution.

## Key Files to Modify

- `.aitask-scripts/board/aitask_board.py`:
  - `Binding("w", "work_report", "Work Report")` in `KanbanApp.BINDINGS` (~4589-4641; `w` is currently unbound). ShortcutsMixin auto-registers it for user customization (scope "board") — no extra wiring.
  - `check_action` (~4655-4766): hide (`return False`) when `self.base_filter in ("inflight", "bytopic")` or `_get_focused_col_id()` (~5391-5399; handles focused TaskCard AND CollapsedColumnPlaceholder ~1074-1088) yields no column.
  - `action_work_report` (model `action_pick_task` ~5640-5680):
    1. Column multi-select — new ModalScreen modeled on `IssueTypeFilterScreen` (~3090-3143): `SelectionList`, Space toggles, Enter confirms, Escape cancels; options = `column_order` columns with `unordered` prepended when non-empty; focused column initially checked.
    2. Task multi-select — second modal, grouped by chosen columns in board order, one Selection per underlying parent task, ALL initially checked; contents from `manager.get_column_tasks(col_id)` (full column — ignores search/board filters). Board ordering preserved after exclusions.
    3. Empty column or task selection → `self.notify(...)`, no launch. Escape at either modal cancels cleanly.
    4. Launch: `resolve_dry_run_command(Path("."), "work-report", "--columns", cols_csv, "--tasks", tasks_csv)` → `AgentCommandScreen(..., operation="work-report", operation_args=["--columns", cols_csv, "--tasks", tasks_csv], skill_name="work-report")`, prompt `"/aitask-work-report --columns ... --tasks ..."`; result callback mirrors `action_pick_task` (~5668-5678: run / TmuxLaunchConfig + maybe_spawn_minimonitor). `--tasks` csv MUST be composed in exactly the displayed grouped order (the reviewed sequence the gatherer's `task_order_changed` check defends).

## Verification

- Pilot/unit tests (models: `tests/test_board_footer_visibility.py`, `test_board_view_filter.py`, `test_agent_command_dialog_*.py`): footer visibility per view + focus state (hidden in inflight/bytopic and with no focused column; visible with focused card and with collapsed placeholder), defaults (focused column checked; all tasks checked), full-column behavior under active search/filter, cancellation at each modal, empty selections notify without launch, stable ordering, exact launch arguments, shortcut registration (`bash tests/test_shortcuts_registry_coverage.sh`).
- Round-trip equivalence test (membership-contract oracle): shared fixture tree (Unsorted tasks, boardidx ties, archived tasks, parent with children, missing boardcol, phantom layout stub with boardcol/boardidx-only frontmatter) — assert the exact `--columns`/`--tasks` args the board flow would launch, fed through `aitask_work_report_gather.sh`, reproduce the same membership AND order the board modal displayed (`TaskManager.get_column_tasks` per column). Pins the two implementations against drift (archived/child/phantom exclusion, default boardcol, status filtering, tie-breaks, Unsorted).
