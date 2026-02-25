# Step 6: Create Implementation Plan

Detailed planning workflow for the task-workflow skill. Read this file when
Step 5 (Environment and Branch Setup) is complete and you are ready to plan.

## Table of Contents

- [6.0: Check for Existing Plan](#60-check-for-existing-plan)
- [6.1: Planning](#61-planning)
- [Child Task Documentation Requirements](#child-task-documentation-requirements)
- [Save Plan to External File](#save-plan-to-external-file)
- [Checkpoint](#checkpoint-after-plan-is-saved)

---

## 6.0: Check for Existing Plan

Check if a plan file already exists at the expected path:
- For parent tasks: `aiplans/p<taskid>_<name>.md`
- For child tasks: `aiplans/p<parent>/p<parent>_<child>_<name>.md`

```bash
./aiscripts/aitask_query_files.sh plan-file <taskid>
```
Parse the output: `PLAN_FILE:<path>` means found, `NOT_FOUND` means not found.

**If a plan file exists**, read it.

**Profile check:** If the active profile has `plan_preference` set (or `plan_preference_child` for child tasks — `plan_preference_child` takes priority when the current task is a child task):
- If `"use_current"`: Skip to the **Checkpoint** at the end of Step 6. Display: "Profile '\<name\>': using existing plan"
- If `"verify"`: Enter verification mode (step 6.1). Display: "Profile '\<name\>': verifying existing plan"
- If `"create_new"`: Proceed with step 6.1 as normal. Display: "Profile '\<name\>': creating plan from scratch"
- Skip the AskUserQuestion below

Otherwise, use `AskUserQuestion`:
- Question: "An existing implementation plan was found at `<plan_path>`. How would you like to proceed?"
- Header: "Plan"
- Options:
  - "Use current plan" (description: "Skip planning and proceed with the existing plan as-is")
  - "Verify plan" (description: "Check if code has changed, verify the plan is still sound or if there are better alternatives")
  - "Create plan from scratch" (description: "Discard existing plan and start fresh")

**If "Use current plan":** Skip to the **Checkpoint** at the end of Step 6.
**If "Verify plan":** Enter plan mode (step 6.1), but start by reading the existing plan and verifying it against the current codebase. Update the plan if needed.
**If "Create plan from scratch":** Proceed with step 6.1 as normal, ignoring the existing plan.

**If no plan file exists**, proceed with step 6.1 as normal.

## 6.1: Planning

Use the `EnterPlanMode` tool to enter Claude Code's plan mode.

**If entering from the "Verify plan" path in 6.0:** Start by reading the existing plan file. Then explore the current codebase to check if the plan's assumptions, file paths, and approach are still valid. Focus on identifying what changed since the plan was written. Update the plan if needed, or confirm it is still sound and exit plan mode.

**For child tasks:** Include context links to related files (in priority order):
- Parent task file: `aitasks/t<parent>_<name>.md`
- Archived sibling plan files (primary reference for completed siblings): `aiplans/archived/p<parent>/p<parent>_*_*.md` — these contain the most up-to-date and detailed implementation records including post-implementation feedback
- Archived sibling task files (fallback, only for siblings without an archived plan): `aitasks/archived/t<parent>/t<parent>_*_*.md`
- Pending sibling task files: `aitasks/t<parent>/t<parent>_*_*.md`
- Pending sibling plan files: `aiplans/p<parent>/p<parent>_*_*.md`

While in plan mode:

- Ask the user clarifying questions about the task requirements
- Explore the codebase to understand the relevant architecture
- **Folded Tasks Note:** If the task has a `folded_tasks` frontmatter field, the task description already contains all relevant content from the folded tasks (their content was incorporated at creation time by aitask-explore). There is no need to read the original folded task files during planning — they exist only as references for post-implementation cleanup (deletion in Step 9).
- **Complexity Assessment:**
  - After initial exploration, assess implementation complexity
  - If the complexity appears HIGH for a parent task, use `AskUserQuestion`:
    - Question: "This task appears complex. Would you like to break it into child subtasks?"
    - Options: "Yes, create child tasks" / "No, implement as single task"
  - **If creating child tasks:**
    - Ask how many subtasks and get brief descriptions for each
    - Use `aitask_create.sh --batch --parent <N>` to create each child
    - **IMPORTANT:** Each child task file MUST include detailed context (see Child Task Documentation Requirements below)
    - **IMPORTANT:** Revert the parent task status back to "Ready" since only the child task being worked on should be "Implementing":
      ```bash
      ./aiscripts/aitask_update.sh --batch <parent_num> --status Ready --assigned-to ""
      ```
      The `aitask_ls.sh` script will automatically display the parent as "Has children" because it has pending `children_to_implement`. Do NOT manually set the parent status to "Blocked".
    - **Write implementation plans for ALL child tasks** before proceeding:
      - For each child task created, write a plan file to `aiplans/p<parent>/p<parent>_<child>_<name>.md`
      - Use the child plan file naming and metadata header conventions from the **Save Plan to External File** section below
      - Each plan should leverage the codebase exploration already done during the parent planning phase
      - Plans do not need to go through `EnterPlanMode`/`ExitPlanMode` — write them directly as files since the overall parent plan was already approved
      - Commit all child task files and plan files together:
        ```bash
        mkdir -p aiplans/p<parent>
        ./ait git add aitasks/t<parent>/ aiplans/p<parent>/
        ./ait git commit -m "ait: Create t<parent> child tasks and plans"
        ```
    - **Child task checkpoint (ALWAYS interactive — ignores `post_plan_action` profile setting):**
      Use `AskUserQuestion`:
      - Question: "Created <N> child tasks with implementation plans. How would you like to proceed?"
      - Header: "Children"
      - Options:
        - "Start first child" (description: "Continue to pick and implement the first child task")
        - "Stop here" (description: "All child tasks and plans are written — end this session and pick children later in fresh contexts")
      - **If "Start first child":** Restart the pick process with `/aitask-pick <parent>_1`
      - **If "Stop here":** End the workflow. Display: "Child tasks and plans written to `aiplans/p<parent>/`. Pick individual children later with `/aitask-pick <parent>_<N>`."
- Create a detailed implementation plan
- Include a reference to **Step 9 (Post-Implementation)** in the plan for the cleanup, archival, and merge steps
- Use `ExitPlanMode` when ready for user approval

## Child Task Documentation Requirements

When creating child tasks, each task file MUST include detailed context that enables independent execution in a fresh Claude Code context. The assumption is that child tasks will NOT be executed in the current context, so ALL information currently available should be stored in the child task definition.

**Required sections for each child task:**

1. **Context Section**
   - Why this task is needed
   - How it fits into the parent task's goal
   - Relevant background from the exploration phase that led to this specific child task

2. **Key Files to Modify**
   - Full paths to files that need changes
   - Brief description of what changes are needed in each file

3. **Reference Files for Patterns**
   - Existing files that demonstrate similar patterns to follow
   - Specific line numbers or function names when helpful

4. **Implementation Plan**
   - Step-by-step instructions
   - Code snippets where helpful
   - Dependencies between steps

5. **Verification Steps**
   - How to build/compile
   - How to test the changes
   - Expected outcomes

## Save Plan to External File

Immediately after the user approves the plan via `ExitPlanMode`, save it to an external file.

**File naming convention:**

For parent tasks:
- Location: `aiplans/`
- Filename: Replace `t` prefix with `p`
- Example: `t16_implement_auth.md` → `aiplans/p16_implement_auth.md`

For child tasks:
- Location: `aiplans/p<parent>/`
- Filename: Replace `t` prefix with `p`
- Example: `t16_2_add_login.md` → `aiplans/p16/p16_2_add_login.md`

**Required metadata header for parent tasks:**
```markdown
---
Task: t16_implement_auth.md
Worktree: aiwork/t16_implement_auth
Branch: aitask/t16_implement_auth
Base branch: main
---
```

**Required metadata header for child tasks:**
```markdown
---
Task: t16_2_add_login.md
Parent Task: aitasks/t16_implement_auth.md
Sibling Tasks: aitasks/t16/t16_1_*.md, aitasks/t16/t16_3_*.md
Archived Sibling Plans: aiplans/archived/p16/p16_*_*.md
Worktree: aiwork/t16_2_add_login
Branch: aitask/t16_2_add_login
Base branch: main
---
```

## Checkpoint (after plan is saved)

**Override for verified child task plans:** If this is a child task AND the plan was verified (entered via the "Verify plan" path in 6.0), the checkpoint is ALWAYS interactive — ignore the `post_plan_action` profile setting. The user must confirm the verified plan before implementation proceeds. This ensures the user sees and approves the plan even when using fast profiles.

**Profile check:** If the active profile has `post_plan_action` set to `"start_implementation"` (and the override above does NOT apply):
- Display: "Profile '\<name\>': proceeding to implementation"
- Skip the AskUserQuestion below and proceed directly to Step 7

Otherwise, use `AskUserQuestion`:
- Question: "Plan saved to `<plan_path>`. How would you like to proceed?"
- Header: "Proceed"
- Options:
  - "Start implementation" (description: "Begin implementing the approved plan")
  - "Revise plan" (description: "Re-enter plan mode to make changes")
  - "Abort task" (description: "Stop and revert task status")

If "Revise plan": Return to the beginning of Step 6.
If "Abort": Execute the **Task Abort Procedure** (see `procedures.md`).
