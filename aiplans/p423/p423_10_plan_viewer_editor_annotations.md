---
Task: t423_10_plan_viewer_editor_annotations.md
Parent Task: aitasks/t423_design_and_finalize_brainstorm_tui.md
Worktree: (none - working on current branch)
Branch: (current)
Base branch: main
---

## Context

Implement an in-TUI plan viewer/editor with annotation support. Users can view a node's plan, navigate to specific sections, and add annotations describing what to change. Annotations are accumulated and then formatted as a structured patch request for the Patcher agent.

Depends on: t423_1 (scaffold), t423_4 (node detail modal)

## Implementation

1. Create PlanEditorScreen accessible from Node Detail Plan tab or Actions wizard
2. Show plan text in scrollable view with line numbers (Static/TextArea)
3. Annotation mode: press `a` to annotate current section
   - Input overlay at current position
   - User types instruction
   - Save as {section_range: (start, end), instruction: "..."}
4. Colored markers in margin for active annotations
5. `r` key: review screen listing all annotations
6. Submit: format annotations as patch request (section text + instruction per annotation)
7. Register patcher agent via register_patcher()
8. Handle output: NO_IMPACT -- plan updated, IMPACT_FLAG -- Explorer triggered

### Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` -- Add PlanEditorScreen and annotation logic

### Reference Files for Patterns
- `.aitask-scripts/diffviewer/diff_display.py` -- Custom scrollable widget with line tracking
- `.aitask-scripts/brainstorm/brainstorm_crew.py` -- `register_patcher()` for submitting patch requests
- `.aitask-scripts/diffviewer/md_parser.py` -- `parse_sections()` for section-based navigation

### Manual Verification
1. Open Plan tab -- press Edit key -- annotation mode
2. Navigate to section -- `a` -- input overlay
3. Type instruction -- annotation saved, marker visible
4. Add 2-3 annotations -- `r` shows review
5. Submit -- patcher agent registered

## Post-Implementation

Follow Step 9 of the task workflow (testing, verification, commit).
