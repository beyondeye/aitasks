---
priority: medium
effort: low
depends: []
issue_type: refactor
status: Implementing
labels: [claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-17 15:00
updated_at: 2026-03-17 15:03
---

## Context

The `/aitask-explore` skill currently selects the execution profile at Step 0a — before the user even answers "What would you like to explore?" However, no profile key is used during the exploration phase (Steps 1-2). The first profile key used is `explore_auto_continue` at Step 4 (decision point after task creation).

This delays the user reaching the first substantive question by one unnecessary prompt.

## Change

Move execution profile selection from Step 0a to just before Step 4 (after task creation, before the decision point). Specifically:

1. **Remove Step 0a** (profile selection) from the beginning of the workflow
2. **Keep Step 0c** (sync) at the top — it's non-blocking and doesn't depend on the profile
3. **Insert profile selection** between Step 3 (task creation) and Step 4 (decision point)
   - Use the same Execution Profile Selection Procedure
   - Store the profile for the Step 5 handoff to task-workflow
4. **Update Step 5** handoff to pass the newly-loaded profile as `active_profile` and `active_profile_filename`
5. **Handle the abort path:** If user aborts in Step 2, no profile is ever loaded (which is correct — it was never needed)

## Key constraint

- task-workflow Step 3b already has a profile refresh mechanism, so even if the profile is loaded late, it integrates cleanly with the downstream workflow
- The sync step (Step 0c) does NOT depend on the profile and should remain at the top

## Affected files

- `.claude/skills/aitask-explore/SKILL.md`

## Verification

1. Read the updated SKILL.md and verify no step references the profile before the new insertion point
2. Verify the handoff variables in Step 5 still include `active_profile` and `active_profile_filename`
3. Verify abort path (Step 2 "Abort") works without profile being loaded
