# OpenCode Plan Mode Prerequisites

These prerequisites apply to all OpenCode skills that use a multi-step
workflow with planning phases. Check them BEFORE reading or executing the
source Claude Code skill.

## Plan Mode Handling

OpenCode has no `EnterPlanMode`/`ExitPlanMode` toggle. Instead:

1. When the skill enters plan mode, announce "Entering planning phase" and
   use only read-only tools (`read`, `grep`, `glob`, `bash` with read-only commands)
2. Create a **detailed, step-by-step implementation plan** and present it
   to the user for approval before implementing. The plan should include:
   - Specific file paths that will be modified or created
   - Detailed implementation steps with exact description of changes needed
     in each file (function signatures, config keys, section locations)
   - Code snippets for non-trivial changes
   - Verification steps (how to test/validate the changes)
   - Dependencies between steps (ordering constraints)

   Do NOT present a high-level overview. The plan
   should be detailed enough that a developer could implement it without
   further clarification.
3. When the skill exits plan mode, announce "Planning complete" and proceed

## Checkpoints

At each checkpoint where the skill uses `AskUserQuestion`, use the `ask`
tool to present the same options and wait for the user's choice.

## Abort Handling

Follow the abort procedure exactly as documented if the user selects abort
at any checkpoint.

## Locking Caveat

OpenCode's plan mode restricts the agent to read-only tools. However, the
task-workflow's Step 4 (Assign Task) calls `aitask_pick_own.sh` which
performs write operations (lock acquisition, status updates, git commits).
These calls MUST still be executed even during plan mode — they are
prerequisites for the workflow, not part of the implementation.

**Recommendation:** Use OpenCode in regular mode (not plan mode) for
interactive skills like aitask-pick, aitask-explore, aitask-review, and
aitask-fold. These skills have their own internal planning phases that
handle plan/implement transitions correctly.
