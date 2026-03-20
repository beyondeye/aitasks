---
Task: t423_9_bottom_up_flow_diffviewer_patcher_architecture.md
Parent Task: aitasks/t423_design_and_finalize_brainstorm_tui.md
Worktree: (none - working on current branch)
Branch: (current)
Base branch: main
---

## Context

Integrate the diff viewer with the brainstorm TUI's bottom-up flow. When a user edits a plan via the diff viewer, compute a structured diff and feed it to the Patcher agent for impact analysis. If the patcher detects architectural impact, trigger the Explorer agent for architecture reconciliation.

Depends on: t423_1 (scaffold), t423_6 (actions wizard), t423_8 (diff viewer params)

## Implementation

1. Add "Edit Plan" to Actions wizard operation list
2. When selected: get current node's plan_file + parent nodes' plan files
3. Launch diff viewer: `python diffviewer_app.py --main <plan> --other <parent_plans> --result-file <tmp> --diff-output <tmp_diff>`
4. Use self.app.suspend() to yield terminal to diff viewer
5. On return: read result file (modified paths) and diff output (JSON hunks)
6. Use diff_engine to compute structured diff between original and modified
7. Format as patch request and register_patcher() via @work
8. Parse patcher output: NO_IMPACT -- update plan, IMPACT_FLAG -- register_explorer()

### Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` -- Add "Edit Plan" action
- `.aitask-scripts/brainstorm/brainstorm_crew.py` -- Patcher/Explorer registration with diff context

### Reference Files for Patterns
- `.aitask-scripts/diffviewer/diff_engine.py` -- `compute_multi_diff()`, `DiffHunk`, `PairwiseDiff`
- `.aitask-scripts/brainstorm/brainstorm_crew.py` -- `register_patcher()`, `register_explorer()`

### Manual Verification
1. Select "Edit Plan" -- diff viewer launches
2. Merge changes, save -- diff viewer exits
3. TUI resumes -- Patcher agent registered
4. Check crew worktree for patcher agent files

## Post-Implementation

Follow Step 9 of the task workflow (testing, verification, commit).
