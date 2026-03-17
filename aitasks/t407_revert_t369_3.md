---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: []
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-17 10:52
updated_at: 2026-03-17 10:53
---

## Revert: Partially revert t369 (aitask_explain_for_aitask_pick) — by child task

### Original Task Summary
Integrate aiexplains historical context data into the aitask-pick planning workflow, enabling code agents to automatically access architectural context from historical task plans.

### Children to REVERT
- t369_3 (update_planning_skill_and_profile_schema): 1 commit
  Areas: .claude/skills/aitask-pick/, .claude/skills/task-workflow/
  Commits:
  - `b53c1bd2210c` (2026-03-15): feature: Add gather_explain_context profile key and planning instructions (t369_3) — .claude/skills/aitask-pick/SKILL.md (+16/-0), .claude/skills/task-workflow/planning.md (+10/-0), .claude/skills/task-workflow/profiles.md (+1/-0)

### Children to KEEP (do NOT modify)
- t369_1 (create_explain_format_context_py): 1 commit
  Areas: .aitask-scripts/, tests/
- t369_2 (create_explain_context_sh): 1 commit
  Areas: .aitask-scripts/, tests/

### Parent-level commits
- None

### Revert Instructions
1. Revert ALL changes from child t369_3 (commit b53c1bd2210c)
2. Preserve ALL changes from children t369_1 and t369_2
3. The single commit (b53c1bd2210c) only touches files in .claude/skills/ — no overlap with kept children, so git revert should work cleanly
4. Run verification/tests after reverting

### Implementation Transparency Requirements
During the planning/implementation phase for this revert task, the implementing agent MUST:
1. **Before making any changes**, produce a detailed summary for user review:
   - For each child being reverted: exactly which lines/functions/features will be removed or changed back
   - For each child being kept: confirm no unintended side effects from reverting the other children
   - Motivation: why each child is safe to revert independently of the kept children
2. **Cross-child dependency analysis**: Check for imports, function calls, shared state, or config that crosses the boundary between reverted and kept children. List each dependency and how it will be resolved.
3. **Impact on other project code**: Identify code OUTSIDE the original task's scope that now depends on the changes being reverted. List potential breakages and mitigation steps.
4. **Present this summary to the user for approval BEFORE executing any revert changes.**

### Post-Revert Task Management
- **Disposition:** Move back to Ready
- **Original task file:** `aitasks/t369_aitask_explain_for_aitask_pick.md` (active)
- **Original plan file:** `aiplans/p369_aitask_explain_for_aitask_pick.md` (active)

**Disposition: Move back to Ready**
1. Task is already active — no move needed
2. Plan is already active — no move needed
3. Update task status: `bash .aitask-scripts/aitask_update.sh --batch 369 --status Ready --assigned-to ""`
4. Add Revert Notes section to the task file:
   ```
   ## Revert Notes
   - **Reverted by:** t<revert_task_id>
   - **Date:** 2026-03-17
   - **Type:** Partial
   - **Areas reverted:** .claude/skills/aitask-pick/, .claude/skills/task-workflow/
   - **Areas kept:** .aitask-scripts/, tests/
   ```
5. Commit: `./ait git add aitasks/t369_aitask_explain_for_aitask_pick.md && ./ait git commit -m "ait: Add revert notes to t369"`

### Per-Child Disposition
For child t369_3 that was reverted, update the archived child task file with Revert Notes:

**Fully reverted child t369_3:**
Add to the archived child task file (`aitasks/archived/t369/t369_3_update_planning_skill_and_profile_schema.md`):
   ## Revert Notes
   - **Reverted by:** t<revert_task_id>
   - **Date:** 2026-03-17
   - **Type:** Complete (all changes from this child were reverted)
   - **Areas reverted:** .claude/skills/aitask-pick/, .claude/skills/task-workflow/

Children t369_1 and t369_2 were NOT reverted — no annotation needed.

Commit all child annotations: `./ait git add aitasks/archived/t369/t369_3_update_planning_skill_and_profile_schema.md && ./ait git commit -m "ait: Add revert notes to t369 children"`
