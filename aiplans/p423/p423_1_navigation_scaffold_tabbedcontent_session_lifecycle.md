---
Task: t423_1_navigation_scaffold_tabbedcontent_session_lifecycle.md
Parent Task: aitasks/t423_design_and_finalize_brainstorm_tui.md
Worktree: (none - working on current branch)
Branch: (current)
Base branch: main
---

## Context

Replace the placeholder brainstorm TUI scaffold with a real navigation framework. The current `brainstorm_app.py` (156 LOC) has 5 placeholder screens using push_screen. This task replaces it with a tab-based architecture using Textual's `TabbedContent` (5 tabs: Dashboard, DAG, Compare, Actions, Status) and adds session lifecycle handling on launch.

## Implementation

1. Replace BrainstormApp with TabbedContent (5 tabs with placeholder Labels)
2. Add numeric key bindings (1-5) for tab switching
3. Create NodeDetailModal(ModalScreen) skeleton (empty compose, Esc to close)
4. In on_mount(): check session_exists(task_num)
   - No session: show init ModalScreen with confirm button, run `ait brainstorm init` via @work(thread=True), reload
   - Existing session: load_session(), populate self.task_num, self.session_path, self.session_data
   - Completed/archived: set self.read_only = True
5. Establish full CSS structure for the app
6. Ensure q quits, Esc closes modals

### Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` -- Replace entire scaffold with TabbedContent layout + session lifecycle

### Reference Files for Patterns
- `.aitask-scripts/board/aitask_board.py` -- ModalScreen pattern, @work threading, CSS structure
- `.aitask-scripts/brainstorm/brainstorm_session.py` -- `session_exists()`, `load_session()`, `crew_worktree()`

### Manual Verification
1. `./ait brainstorm 999` -- init screen appears, confirm creates session, tabs load
2. `./ait brainstorm <existing>` -- loads directly into tabbed view
3. Press 1-5 -- each tab activates (placeholder content is fine)
4. Press q -- app exits cleanly

## Post-Implementation

Follow Step 9 of the task workflow (testing, verification, commit).
