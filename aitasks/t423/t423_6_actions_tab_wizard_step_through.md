---
priority: medium
effort: high
depends: [t423_5]
issue_type: feature
status: Ready
labels: [brainstorming, tui]
created_at: 2026-03-20 12:40
updated_at: 2026-03-20 12:40
---

## Context
Implement the Actions tab (Tab 4) as a wizard step-through for launching brainstorm operations and managing session lifecycle. Two groups: design ops (explore, compare, hybridize, detail, patch) and session ops (pause, resume, finalize, archive).

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` — Replace Actions tab placeholder with wizard

## Reference Files for Patterns
- `.aitask-scripts/brainstorm/brainstorm_crew.py` — `register_explorer()`, `register_comparator()`, `register_synthesizer()`, `register_detailer()`, `register_patcher()`
- `.aitask-scripts/brainstorm/brainstorm_session.py` — `save_session()`, `finalize_session()`, `archive_session()`
- `.aitask-scripts/board/aitask_board.py` — CycleField for option cycling, Button handlers

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

## Manual Verification
1. Step 1 shows operation list with two groups
2. Select Explore → Step 2 shows mandate TextArea, explorer count
3. Fill in, advance to Step 3 → summary + Launch
4. Launch → agent files created in crew worktree
5. Select Pause → confirm → session status changes
6. Esc returns to previous step
