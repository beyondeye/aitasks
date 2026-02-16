---
Task: t141_loosing_execution_profile_when_moving_to_task_implementation.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Context

When `aitask-explore` hands off to `task-workflow` for implementation, the execution profile (e.g., "fast") is lost. The `active_profile` is purely a conceptual "context variable" in the LLM's memory — there is no durable storage. After a long exploration session (many rounds of exploration, task creation, folded-task selection), the LLM forgets the profile settings by the time it reaches the task-workflow steps that check them. This causes all questions to be asked interactively, defeating the purpose of the profile.

The root cause is that the handoff instructions passively reference "the profile loaded in Step 0a" instead of actively forcing a re-read of the profile YAML file.

## Plan

### Single change: task-workflow entry point (Step 3)

**File:** `.claude/skills/task-workflow/SKILL.md` (between lines 27-29)

Insert a **Profile Refresh** step at the start of Step 3, before "Check 1":

```markdown
**Profile Refresh:** If `active_profile` was provided and is non-null, re-read the profile YAML file from `aitasks/metadata/profiles/` to ensure all settings are fresh in context. Display: "Refreshing profile: <name>". If the profile file cannot be read (missing or invalid), warn: "Warning: Could not refresh profile '<name>', proceeding without profile" and set `active_profile` to null.

If `active_profile` is null (either because no profile was selected by the calling skill, or because the profile name was lost during a long conversation), re-run the profile selection logic from Step 0a of the calling skill: check for available profiles in `aitasks/metadata/profiles/*.yaml`, and if profiles exist, ask the user to select one using `AskUserQuestion` (same format as Step 0a in aitask-pick/aitask-explore). If the user selects "No profile", proceed without one.
```

This is placed in task-workflow (the receiver side) because all calling skills (aitask-explore, aitask-pick) converge here. One change covers all callers. The re-read refreshes all settings; the null fallback recovers from total profile loss.

## Verification

- Run `/aitask-explore` with "fast" profile, go through a multi-round exploration, create a task, choose "Continue to implementation" — verify the profile settings are respected (no interactive questions for email, worktree, plan preference, etc.)
- Run `/aitask-pick` with "fast" profile — verify it still works as before (regression check)

## Final Implementation Notes

- **Actual work done:** (1) Added a "Profile Refresh" step (Step 3b) in task-workflow that re-reads the profile YAML file to refresh settings in context, and falls back to re-asking the user if the profile was completely lost. (2) Added explicit "Verify plan" path instructions in step 6.1 so the LLM knows to read/validate the existing plan when entering from the verify path.
- **Deviations from plan:** User moved Profile Refresh from top of Step 3 to a separate Step 3b (after task status checks — no profile needed for archival). Also added the verify-mode clarification in 6.1 which wasn't in the original plan.
- **Issues encountered:** None.
- **Key decisions:** (1) Single change in task-workflow rather than modifying all callers. (2) Used inline conditional in 6.1 rather than a separate verification step or a stateful flag, to avoid duplication.

## Post-Implementation (Step 9)

Archive t141 task and plan files after commit.
