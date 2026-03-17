---
Task: t412_defer_profile_selection_in_explore.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

The `/aitask-explore` skill loads the execution profile at Step 0a before the user even starts exploring. No profile key is used until Step 4 (`explore_auto_continue`), meaning the profile selection prompt unnecessarily delays the first substantive user interaction ("What would you like to explore?").

## Plan

### File: `.claude/skills/aitask-explore/SKILL.md`

**1. Remove Step 0a (profile selection)**

Delete the entire `### Step 0a: Select Execution Profile` section (lines 8-10).

**2. Renumber Step 0c to Step 0**

Rename `### Step 0c: Sync with Remote (Best-effort)` to `### Step 0: Sync with Remote (Best-effort)`. Keep content unchanged — sync doesn't depend on the profile.

**3. Insert new Step 3b: Select Execution Profile**

After Step 3 (Task Creation) and before Step 4 (Decision Point), insert a new section:

```markdown
### Step 3b: Select Execution Profile

Execute the **Execution Profile Selection Procedure** (see `.claude/skills/task-workflow/execution-profile-selection.md`).

Store the loaded profile as `active_profile` and `active_profile_filename` for use in Step 4 and the Step 5 handoff.

If no profiles exist (output is `NO_PROFILES`), set both to null — Step 4 will use the default behavior (always ask the user).
```

**4. Update Step 4 reference**

Step 4 already references `active profile` generically — no text changes needed there.

**5. Update Step 5 handoff**

The handoff variable list already includes `active_profile` and `active_profile_filename` with descriptions referencing "Step 0a". Update the descriptions:
- Change `active_profile` description from "The execution profile loaded in Step 0a (or null if no profile)" to "The execution profile loaded in Step 3b (or null if no profile)"
- Change `active_profile_filename` description similarly

**6. Update Notes section**

The Notes section doesn't reference Step 0a. No changes needed.

## Verification

1. Read the updated SKILL.md top-to-bottom and confirm:
   - No references to Step 0a remain
   - Step 0 (sync) is the first step
   - Profile selection appears between Step 3 and Step 4
   - Step 5 handoff variables reference Step 3b
2. Verify the abort path: if user selects "Abort" in Step 2, the workflow ends before Step 3b — no profile is ever loaded (correct)
3. Verify profile is available for Step 4 (`explore_auto_continue` check) and Step 5 handoff

## Final Implementation Notes
- **Actual work done:** Exactly as planned — removed Step 0a, renumbered Step 0c to Step 0, inserted Step 3b, updated Step 5 handoff references, and updated the shared execution-profile-selection.md procedure file
- **Deviations from plan:** Also updated `.claude/skills/task-workflow/execution-profile-selection.md` to reflect that aitask-explore now calls the procedure from Step 3b instead of Step 0a
- **Issues encountered:** None
- **Key decisions:** Kept the procedure reference update minimal — just moved aitask-explore to a separate line noting the deferred timing
