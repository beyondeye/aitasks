---
Task: t357_1_fix_opencode_planning_detail.md
Parent Task: aitasks/t357_planning_phase_in_codex_opencode.md
Sibling Tasks: aitasks/t357/t357_2_document_opencode_plan_mode_caveats.md
Archived Sibling Plans: (none yet)
Worktree: (none — working on current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Fix OpenCode Planning Detail

## Context

OpenCode's plan mode produces shallow, high-level plans instead of the detailed step-by-step implementation plans needed for the task-workflow. The root cause is that `opencode_planmode_prereqs.md` gives vague instructions ("Present your plan to the user") without specifying the required level of detail. Additionally, `planning.md` (the source of truth for all CLIs) has only a brief "Create a detailed implementation plan" bullet without defining what "detailed" means.

A secondary issue is that OpenCode's plan mode restricts the agent to read-only tools, which can cause task locking (write operation) to be skipped.

## Implementation Steps

### Step 1: Enhance `.opencode/skills/opencode_planmode_prereqs.md`

**1a. Replace item 2 in "Plan Mode Handling"**

Current (line 13-14):
```
2. Present your plan to the user and ask for approval before implementing
```

Replace with:
```
2. Create a **detailed, step-by-step implementation plan** and present it
   to the user for approval before implementing. The plan MUST include:
   - Specific file paths that will be modified or created
   - Exact description of changes needed in each file (function signatures,
     config keys, section locations)
   - Code snippets for non-trivial changes
   - Verification steps (how to test/validate the changes)
   - Dependencies between steps (ordering constraints)

   Do NOT present a high-level overview or bullet-point summary. The plan
   should be detailed enough that a developer could implement it without
   further clarification.
```

**1b. Add new "Locking Caveat" section after "Abort Handling"**

Add:
```markdown
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
```

### Step 2: Clarify "detailed" in `.claude/skills/task-workflow/planning.md`

**Line 106** currently reads:
```
- Create a detailed implementation plan
```

Replace with:
```
- Create a detailed, step-by-step implementation plan. "Detailed" means:
  specific file paths, exact changes needed in each file, code snippets
  for non-trivial modifications, and verification steps. Do not produce
  a high-level overview — the plan should be implementable without further
  clarification.
```

### Step 3: Commit

```
bug: Enhance OpenCode planning detail requirements and add locking caveat (t357_1)
```

## Key Files
- `.opencode/skills/opencode_planmode_prereqs.md` — Primary fix
- `.claude/skills/task-workflow/planning.md` — Source of truth clarification (line 106)

## Verification
- Read both files after editing to confirm changes
- No shell scripts modified, so shellcheck N/A

## Post-Implementation
- Step 9: Archive task, push
