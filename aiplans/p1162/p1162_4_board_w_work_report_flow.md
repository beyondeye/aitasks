---
Task: t1162_4_board_w_work_report_flow.md
Parent Task: aitasks/t1162_add_manager_facing_work_report_skill_and_board_flow.md
Sibling Tasks: aitasks/t1162/t1162_1_work_report_gatherer_helper.md, aitasks/t1162/t1162_2_work_report_codeagent_operation.md, aitasks/t1162/t1162_3_work_report_skill_and_wrappers.md, aitasks/t1162/t1162_5_work_report_documentation.md
Archived Sibling Plans: aiplans/archived/p1162/p1162_*_*.md
Worktree: aiwork/t1162_4_board_w_work_report_flow
Branch: aitask/t1162_4_board_w_work_report_flow
Base branch: main
---

# Plan: t1162_4 — Board `w` Work Report flow + Pilot tests

## Context

Adds the contextual, footer-visible `w` (Work Report) action to the board
TUI: column multi-select → task multi-select → shared agent-command dialog
launching `/aitask-work-report` with the exact board-reviewed selection.
Requires the t1162_2 `work-report` operation (command resolution) and pins
membership equivalence against the t1162_1 gatherer. Parent design:
`aiplans/p1162_add_manager_facing_work_report_skill_and_board_flow.md`
(t1162_4 section). Read `aidocs/framework/tui_conventions.md` before editing
the board.

## Anchors (verified during parent planning; re-verify line drift)

All in `.aitask-scripts/board/aitask_board.py` unless noted:
- `KanbanApp.BINDINGS` ~4589-4641; `w` currently unbound.
- Model binding `Binding("p", "pick_task", "Pick")` :4619; handler
  `action_pick_task` :5640-5680; gating in `check_action` :4655-4766
  (`return False` hides from footer; derived views:
  `self.base_filter in ("inflight", "bytopic")`).
- `_focused_card()` :5318-5321; `_get_focused_col_id()` :5391-5399 (falls
  back to a focused `CollapsedColumnPlaceholder` :1074-1088 — `w` must work
  from a collapsed column too).
- Columns: `TaskManager.columns` / `column_order` :502-503;
  `get_column_tasks(col_id)` :668-671 (filters `board_col`, sorts
  `board_idx`; ignores search/filters — the required full-column source);
  dynamic Unsorted id `"unordered"`, non-editable, pickers prepend at index 0
  (:6339, :6364).
- Multi-select modal model: `IssueTypeFilterScreen` :3090-3143
  (`SelectionList[str]`, Space toggles natively, Enter confirms via
  `on_key`, Escape → `action_cancel` dismisses None). `check_action` already
  passes nav keys through when a `SelectionList` is focused (:4695-4697).
- Launch: `AgentCommandScreen` (`lib/agent_command_screen.py:363-399`),
  `resolve_dry_run_command` / `resolve_agent_string`
  (`lib/agent_launch_utils.py:199/:232`); result callback pattern
  :5668-5678 (`run` → terminal; `TmuxLaunchConfig` → `launch_in_tmux` +
  `maybe_spawn_minimonitor`).
- ShortcutsMixin auto-registers new `BINDINGS` under scope "board" — no
  extra wiring for customizability.

## Implementation steps

1. **Binding:** add `Binding("w", "work_report", "Work Report")` to
   `KanbanApp.BINDINGS` (near `p`).
2. **Gating in `check_action`:** for `action == "work_report"`: return
   `False` when `self.base_filter in ("inflight", "bytopic")`; return `False`
   when `self._get_focused_col_id()` is None (no focused card or collapsed
   placeholder identifying a column). Otherwise `True`.
3. **`WorkReportColumnSelectScreen`** (new `ModalScreen`, model
   `IssueTypeFilterScreen`): options = for each col in
   (`["unordered"] if unordered has tasks else []`) + `column_order`:
   `Selection(title, value=col_id, initial_state=(col_id == focused_col))`.
   Space toggles, Enter confirms (dismiss list of selected col_ids in the
   presented order), Escape cancels (dismiss None). Confirm with empty
   selection → `self.notify("No columns selected")` in the caller, no launch.
4. **`WorkReportTaskSelectScreen`** (new `ModalScreen`): for each chosen
   column in board order, a small header (column title) then one `Selection`
   per task from `manager.get_column_tasks(col_id)` — label
   `t<id> <name>`, value task id, `initial_state=True` (ALL checked).
   (SelectionList has no native section headers — either use disabled
   separator options or prefix labels with the column id; keep board order.)
   Enter confirms → dismiss ordered list of (col_id, task_id) preserving
   the DISPLAYED order restricted to still-selected ids; Escape cancels.
5. **`action_work_report`:** orchestrate: focused col → push column screen →
   on result push task screen → on result compose
   `cols_csv = ",".join(chosen_cols_in_board_order)` and
   `tasks_csv = ",".join(selected_task_ids_in_displayed_grouped_order)`
   (THE reviewed sequence — the gatherer's `task_order_changed` check
   defends exactly this order; never re-sort). Empty tasks →
   `self.notify("No tasks selected")`, no launch. Then:
   `full_cmd = resolve_dry_run_command(Path("."), "work-report", "--columns", cols_csv, "--tasks", tasks_csv)`,
   `agent_string = resolve_agent_string(Path("."), "work-report")`,
   `AgentCommandScreen(f"Work Report", full_cmd, f"/aitask-work-report --columns {cols_csv} --tasks {tasks_csv}", default_window_name="agent-work-report", operation="work-report", operation_args=["--columns", cols_csv, "--tasks", tasks_csv], default_agent_string=agent_string, skill_name="work-report")`
   with the `action_pick_task`-style result callback.

## Tests

Python tests under `tests/` (unittest + asyncio Pilot, models:
`tests/test_board_footer_visibility.py`, `tests/test_board_view_filter.py`,
`tests/test_agent_command_dialog_default_session.py`):

1. **Footer visibility:** `w` absent in inflight and bytopic views; absent
   with no focused column; present with a focused card in a persistent kanban
   view; present with a focused collapsed placeholder.
2. **Shortcut registration:** `bash tests/test_shortcuts_registry_coverage.sh`
   passes (new binding registered under scope "board").
3. **Defaults:** column screen opens with focused column checked (and
   `unordered` offered only when it has tasks); task screen opens with all
   tasks checked.
4. **Full-column under filter/search:** apply a search/filter that hides a
   task, open the flow → the hidden task still appears in the task screen.
5. **Cancellation:** Escape at column screen → no task screen, no launch;
   Escape at task screen → no launch.
6. **Empty selections:** deselect-all at either screen → notify, no launch.
7. **Ordering + exact args:** with a known fixture, confirm the composed
   `--columns`/`--tasks` csvs match the displayed grouped order after
   exclusions (spy on `resolve_dry_run_command`/screen-push args rather than
   exit codes — construction-spy pattern).
8. **Round-trip equivalence (membership oracle):** shared fixture tree with
   Unsorted tasks, `boardidx` ties, archived tasks, a parent with children, a
   task missing `boardcol`, and a phantom layout stub (frontmatter with ONLY
   `boardcol`/`boardidx`). Compute the args the board flow would launch, run
   `.aitask-scripts/aitask_work_report_gather.sh` with them, and assert the
   gatherer's `TASK:` membership AND order equal the board's
   `get_column_tasks` per column. Any divergence (incl. tie-break rule chosen
   in t1162_1) fails here — reconcile by fixing the gatherer to match the
   board, not vice versa.

## Verification

- All new Python tests pass; `bash tests/test_shortcuts_registry_coverage.sh`.
- Existing board tests still green (`tests/test_board_*.py`).
- Manual smoke (also covered by the aggregate manual-verification sibling):
  `ait board` → focus column → `w` → adjust selections → launch dialog shows
  the exact command.

## Step 9 reference

Post-implementation: merge/cleanup + archival per task-workflow Step 9.
