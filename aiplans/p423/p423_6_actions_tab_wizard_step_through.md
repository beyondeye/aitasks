---
Task: t423_6_actions_tab_wizard_step_through.md
Parent Task: aitasks/t423_design_and_finalize_brainstorm_tui.md
Worktree: (none - working on current branch)
Branch: (current)
Base branch: main
---

## Context

Implement the Actions tab (Tab 4) as a wizard step-through for launching brainstorm operations and managing session lifecycle. Two groups: design ops (explore, compare, hybridize, detail, patch) and session ops (pause, resume, finalize, archive).

## Implementation

1. Step 1: operation list with focusable rows (two groups: Design ops, Session ops) + recent ops history from br_groups.yaml
2. Step 2: operation-specific configuration form
   - Explore: base node selector, mandate TextArea, parallel explorer count (CycleField)
   - Compare: multi-node checkboxes, dimension checkboxes
   - Hybridize: multi-node checkboxes, merge rules TextArea
   - Detail: single node selector
   - Patch: single node selector, patch request TextArea
   - Session ops (pause/resume/finalize/archive): confirmation only
3. Step 3: summary display + Launch/Confirm button
4. Step indicator at top (Step 1 of 3, Step 2 of 3, etc.)
5. Design ops call register_* from brainstorm_crew.py via @work(thread=True)
6. Session ops call save_session/finalize_session/archive_session
7. Disable session ops based on current session state

### Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` -- Replace Actions tab placeholder with wizard

### Reference Files for Patterns
- `.aitask-scripts/brainstorm/brainstorm_crew.py` -- `register_explorer()`, `register_comparator()`, `register_synthesizer()`, `register_detailer()`, `register_patcher()`
- `.aitask-scripts/brainstorm/brainstorm_session.py` -- `save_session()`, `finalize_session()`, `archive_session()`
- `.aitask-scripts/board/aitask_board.py` -- CycleField for option cycling, Button handlers

### Manual Verification
1. Step 1 shows operation list with two groups
2. Select Explore -- Step 2 shows mandate TextArea, explorer count
3. Fill in, advance to Step 3 -- summary + Launch
4. Launch -- agent files created in crew worktree
5. Select Pause -- confirm -- session status changes
6. Esc returns to previous step

## Final Implementation Notes

- **Actual work done:** Replaced Actions tab placeholder in `brainstorm_app.py` with a full 3-step wizard. Added `OperationRow` (focusable row with click handler), `CycleField` (minimal left/right cycle widget), and 22 new methods on BrainstormApp for wizard lifecycle, config forms, validation, launch, and agent registration. Added imports for `save_session`, `finalize_session`, `archive_session`, `GROUPS_FILE` from session module; all `register_*` functions from crew module; `read_yaml` from agentcrew_utils; `TextArea` from Textual. Total: +605/-12 lines in a single file.
- **Deviations from plan:** All dynamically created wizard widgets use CSS classes instead of IDs to avoid Textual `DuplicateIds` errors — `remove_children()` is async and doesn't immediately clear ID registry, so mounting widgets with the same IDs during step transitions crashes. Button event handlers use `@on(Button.Pressed, ".class_selector")` pattern instead of `#id_selector`. Config collection queries by widget type (`container.query_one(TextArea)`) and CSS class (`container.query("Checkbox.chk_node")`) instead of by ID.
- **Issues encountered:** 1) Textual's `DuplicateIds` crash on step transitions — fixed by switching all dynamic widget IDs to CSS classes. 2) OperationRow focus lost after click — VerticalScroll parent was stealing focus; fixed by adding explicit `on_click` handler with `self.focus()`. 3) Keyboard navigation didn't work initially because dynamically mounted widgets need a render frame before they can receive focus — fixed by calling `call_after_refresh(self._focus_first_operation)` after mounting step 1.
- **Key decisions:** Kept all changes in a single file (brainstorm_app.py) matching sibling task pattern. Created inline CycleField (~25 LOC) rather than importing from board module to avoid heavy cross-dependencies. Used `@work(thread=True)` for design ops (matching `_run_init` pattern) with `call_from_thread` for UI updates. Session ops executed synchronously (they're just YAML writes). Used `_selected_node` tracking via `on_descendant_focus` for single-node selection in explore/detail/patch forms.
- **Notes for sibling tasks:** `OperationRow` is reusable for any focusable list row with disable support (wider than NodeRow which lacks disable). The `CycleField` widget is available but minimal — for more complex needs, consider extracting the board's CycleField to a shared module. CSS class IDs used: `.actions_step_indicator`, `.actions_section_title`, `.actions_summary`, `.actions_buttons`, `.btn_actions_next`, `.btn_actions_launch`, `.btn_actions_back`, `.chk_node`, `.chk_dim`. The wizard state variables `_wizard_step`, `_wizard_op`, `_wizard_config` control the flow. `_next_group_name(op)` reads `br_groups.yaml` to generate sequential names like `explore_001`. For `register_detailer`, `codebase_paths` defaults to `["."]` — future tasks may want to make this configurable.
