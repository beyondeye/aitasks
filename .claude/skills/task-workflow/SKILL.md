---
name: task-workflow
description: Shared implementation workflow for task-based skills. Handles status checks, assignment, environment setup, planning, implementation, review, and archival.
user-invocable: false
---

## Context Requirements

This skill is invoked by other skills (e.g., aitask-pick, aitask-explore, aitask-review) after they have selected a task. The calling skill MUST establish the following context before handing off:

| Variable | Type | Description |
|----------|------|-------------|
| `task_file` | string | Path to selected task file (e.g., `aitasks/t16_implement_auth.md` or `aitasks/t10/t10_2_add_login.md`) |
| `task_id` | string | Task identifier (e.g., `16` or `16_2`) |
| `task_name` | string | Filename stem for branches/worktrees (e.g., `t16_implement_auth` or `t16_2_add_login`) |
| `is_child` | boolean | Whether this is a child task |
| `parent_id` | string/null | Parent task number if child (e.g., `16`), null otherwise |
| `parent_task_file` | string/null | Path to parent task file if child (e.g., `aitasks/t16_implement_auth.md`), null otherwise |
| `active_profile` | object/null | Loaded execution profile from calling skill (or null if no profile) |
| `previous_status` | string | Task status before workflow began (for abort revert, e.g., `Ready`) |
| `folded_tasks` | array/null | List of task IDs folded into this task (e.g., `[106, 129_5]`), or null/empty if none. Set by aitask-explore when existing tasks are folded into a new task. |

## Workflow

### Step 3: Task Status Checks

After a task is selected and confirmed, perform these checks before proceeding to Step 4.

**Check 1 - Done but unarchived task:**
- Read the task file's frontmatter `status` field
- If status is `Done`:
  - Check if a plan file exists:
    ```bash
    ls aiplans/p<taskid>_*.md 2>/dev/null
    ```
  - Use `AskUserQuestion`:
    - Question: "This task has status 'Done' but hasn't been archived yet. Would you like to archive it now?"
    - Header: "Archive"
    - Options:
      - "Yes, archive it" (description: "Proceed to archive the task and plan file if found")
      - "No, skip" (description: "Leave the task as-is and end the workflow")
  - If "Yes, archive it" → skip Steps 4-8, proceed directly to **Step 9** (Post-Implementation) for parent task archival
  - If "No, skip" → end the workflow

**Check 2 - Orphaned parent task (empty children_to_implement):**
- Check if the task file's frontmatter contains `children_to_implement: []` (empty list)
- If empty, check for archived children:
  ```bash
  ls aitasks/archived/t<number>/ 2>/dev/null
  ```
- If archived children exist, this is an orphaned parent task:
  - Use `AskUserQuestion`:
    - Question: "This parent task has all children completed and archived, but the parent itself was not archived. Would you like to archive it now?"
    - Header: "Archive"
    - Options:
      - "Yes, archive it" (description: "Proceed to archive the parent task and plan file if found")
      - "No, skip" (description: "Leave the task as-is and end the workflow")
  - If "Yes, archive it" → skip Steps 4-8, proceed directly to **Step 9** (Post-Implementation) for parent task archival
  - If "No, skip" → end the workflow

**Note:** These checks should NOT set the task status to "Implementing" — the task is already done. Skip Step 4 (Assign Task) entirely when archiving via this step.

If neither check triggers, proceed to Step 4 as normal.

### Step 3b: refresh execution profile
If `active_profile` was provided and is non-null, re-read the profile YAML file from `aitasks/metadata/profiles/` to ensure all settings are fresh in context. Display: "Refreshing profile: \<name\>". If the profile file cannot be read (missing or invalid), warn: "Warning: Could not refresh profile '\<name\>', proceeding without profile" and set `active_profile` to null.

If `active_profile` is null (either because no profile was selected by the calling skill, or because the profile name was lost during a long conversation), re-run the profile selection logic: check for available profiles in `aitasks/metadata/profiles/*.yaml`, and if profiles exist, ask the user to select one using `AskUserQuestion` (same format as Step 0a in aitask-pick/aitask-explore). If the user selects "No profile", proceed without one. If no profile files exist, skip this step.

### Step 4: Assign Task to User

- **Email resolution (priority order):**

  1. **Check task metadata:** Read the `assigned_to` field from the task file's frontmatter.
  2. **Check userconfig:** Read `aitasks/metadata/userconfig.yaml` and extract the `email:` field (if file exists).
  3. **Mismatch check:** If both `assigned_to` and userconfig email are non-empty and DIFFERENT, use `AskUserQuestion`:
     - Question: "Task is assigned to \<assigned_to\> but your userconfig email is \<userconfig_email\>. Which email to use?"
     - Header: "Email"
     - Options:
       - "Keep \<assigned_to\>" (description: "Continue with the existing assignment")
       - "Use \<userconfig_email\>" (description: "Override with your local email")
     - Use the selected email and proceed to the **Claim task ownership** step below.
  4. **If `assigned_to` is non-empty** (and matches userconfig, or userconfig is empty): use `assigned_to`. Display: "Using email from task metadata: \<email\>". Skip to **Claim task ownership**.
  5. **Profile check:** If the active profile has `default_email` set:
     - If value is `"userconfig"`: Use the userconfig email (from step 2). If userconfig is empty/missing, fall back to reading `aitasks/metadata/emails.txt` (first email). Display: "Profile '\<name\>': using email \<email\> (from userconfig)". If both are empty, fall through to the AskUserQuestion below.
     - If value is `"first"`: Read `aitasks/metadata/emails.txt` and use the first email address. Display: "Profile '\<name\>': using email \<email\>". If emails.txt is empty or missing, fall through to the AskUserQuestion below.
     - If value is a literal email address: Use that email directly. Display: "Profile '\<name\>': using email \<email\>"
     - Skip the AskUserQuestion below

  6. **Otherwise, ask for email using `AskUserQuestion`:**
     - Read stored emails: `cat aitasks/metadata/emails.txt 2>/dev/null | sort -u`
     - Question: "Enter your email to track who is working on this task (optional):"
     - Header: "Email"
     - Options:
       - List each stored email from emails.txt (if any exist)
       - "Enter new email" (description: "Add a new email address")
       - "Skip" (description: "Don't assign this task to anyone")

  - **If "Enter new email" selected:**
    - Ask user to type their email via `AskUserQuestion` with free text (use the "Other" option)

- **Userconfig sync check:** After email is resolved, if the final email differs from the userconfig email (or userconfig doesn't exist):
  - Use `AskUserQuestion`:
    - Question: "The selected email (\<email\>) differs from your userconfig (\<userconfig_email\>). Update userconfig.yaml?"
    - Header: "Userconfig"
    - Options:
      - "Yes, update userconfig" (description: "Save this email to userconfig.yaml for future use")
      - "No, keep current userconfig" (description: "Use this email for now but don't change userconfig")
  - If "Yes": Write `email: <email>` to `aitasks/metadata/userconfig.yaml` (create file if needed with comment header `# Local user configuration (gitignored, not shared)`)
  - If "No": Proceed without updating
  - **Skip this check** if: the final email matches userconfig, or email was resolved from userconfig itself, or no email was selected ("Skip")

- **Claim task ownership (lock, update status, commit, push):**

  If email was provided (new or selected):
  ```bash
  ./aiscripts/aitask_own.sh <task_num> --email "<email>"
  ```
  If no email (user selected "Skip"):
  ```bash
  ./aiscripts/aitask_own.sh <task_num>
  ```

  **Parse the script output:**
  - `OWNED:<task_id>` — Success. Proceed to Step 5.
  - `FORCE_UNLOCKED:<previous_owner>` + `OWNED:<task_id>` — Force-unlock succeeded. Inform user: "Force-unlocked stale lock held by \<previous_owner\>." Proceed to Step 5.
  - `LOCK_FAILED:<owner>` — Task is locked by another user/PC. Run `aitask_lock.sh --check <task_num>` to get lock details (locked_by, locked_at, hostname). Use `AskUserQuestion`:
    - Question: "Task t\<N\> is locked by \<owner\> (since \<locked_at\>, hostname: \<hostname\>). Force unlock?"
    - Header: "Lock"
    - Options:
      - "Force unlock and claim" (description: "Override the stale lock and claim this task")
      - "Pick a different task" (description: "Leave the lock intact and select another task")
    - If "Force unlock and claim": Re-run ownership with `--force`:
      ```bash
      ./aiscripts/aitask_own.sh <task_num> --force --email "<email>"
      ```
      Parse the output again. If `FORCE_UNLOCKED` + `OWNED`: proceed. Otherwise: abort.
    - If "Pick a different task": Return to the calling skill's task selection. Do NOT proceed.
  - `LOCK_ERROR:<message>` — Lock system error (fetch failure, race exhaustion, etc.). Display the error and suggest running `./aiscripts/aitask_lock_diag.sh` for troubleshooting. Use `AskUserQuestion`:
    - Question: "Lock system error: \<message\>. How to proceed?"
    - Header: "Lock error"
    - Options:
      - "Retry" (description: "Try acquiring the lock again")
      - "Continue without lock" (description: "Proceed without locking (risky if multiple users)")
      - "Abort" (description: "Stop the workflow")
    - If "Retry": Re-run `aitask_own.sh` (same command). Parse output again.
    - If "Continue without lock": Skip lock acquisition, proceed to Step 5 (task status will be updated but no lock held).
    - If "Abort": End the workflow.
  - `LOCK_INFRA_MISSING` — Lock infrastructure not initialized. Inform user to run `ait setup` and abort.

  **Note:** The script handles email storage, lock acquisition, task metadata update (`status` → Implementing, `assigned_to`), and git add/commit/push internally. If the script fails entirely (non-zero exit without structured output), display the error and abort.

- **Store previous status for potential abort** (remember the `previous_status` from context)

### Step 5: Environment and Branch Setup

> **Note:** For fully autonomous remote workflows (Claude Code Web), use the `aitask-pickrem` skill instead — it skips all environment setup and always works on the current branch.

- **Profile check:** If the active profile has `create_worktree` set:
  - If `true`: Create worktree. Display: "Profile '\<name\>': creating worktree"
  - If `false`: Work on current branch. Display: "Profile '\<name\>': working on current branch"
  - Skip the AskUserQuestion below

  Otherwise, use `AskUserQuestion` to ask:
  - "Do you want to create a separate branch and worktree for this task?"
  - Options: "No, work on current branch" (default, first option) / "Yes, create worktree (recommended for complex features or when working in parallel on multiple features)"

**If Yes:**

- Extract `<task_name>` from the filename
  - For parent: `t16_implement_channel_settings` from `t16_implement_channel_settings.md`
  - For child: `t16_2_add_login` from `t16_2_add_login.md`

- **Profile check:** If the active profile has `base_branch` set:
  - Use the specified branch name. Display: "Profile '\<name\>': using base branch \<branch\>"
  - Skip the AskUserQuestion below

  Otherwise, ask which branch to base the new branch on using `AskUserQuestion`:
  - "Which branch should the new task branch be based on?"
  - Options: "main (Recommended)" / "Other branch"
  - If "Other branch", ask user to specify the branch name

- Create worktree directory:
  ```bash
  mkdir -p aiwork
  ```

- Create both the branch and worktree in a single command:
  ```bash
  git worktree add -b aitask/<task_name> aiwork/<task_name> <base-branch>
  ```
  Where `<base-branch>` is `main` or the user-specified branch.

- Work in the `aiwork/<task_name>/` directory for implementation

**If No:**
- Work directly on the current branch in the current directory

### Step 6: Create Implementation Plan

#### 6.0: Check for Existing Plan

Check if a plan file already exists at the expected path:
- For parent tasks: `aiplans/p<taskid>_<name>.md`
- For child tasks: `aiplans/p<parent>/p<parent>_<child>_<name>.md`

```bash
ls aiplans/p<taskid>_*.md 2>/dev/null
```

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

#### 6.1: Planning

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

#### Child Task Documentation Requirements

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

#### Save Plan to External File

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

**Checkpoint (after plan is saved):**

**Profile check:** If the active profile has `post_plan_action` set to `"start_implementation"`:
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
If "Abort": Execute the **Task Abort Procedure** (see below).

### Step 7: Implement

Follow the approved plan, working in the directory specified in the plan metadata.

Update the external plan file as you progress:
- Mark steps as completed
- Note any deviations or changes from the original plan
- Record issues encountered during implementation

**IMPORTANT:** Do NOT commit changes automatically after implementation. Proceed to Step 8 for user review and approval.

**Note:** When committing implementation changes (in Step 8), the commit message must follow the `<issue_type>: <description> (t<task_id>)` format. See Step 8 for details.

### Step 8: User Review and Approval

After implementation is complete, the user MUST be given the opportunity to review and test changes before any commits are made.

- **Show change summary:**
  ```bash
  git status
  git diff --stat
  ```

- **Ask for user approval using `AskUserQuestion`:**
  - Question: "Implementation complete. Please review and test the changes. When ready, select an option:"
  - Header: "Review"
  - Options:
    - "Commit changes" (description: "Changes reviewed and tested, ready to commit")
    - "Need more changes" (description: "Adjustments needed before committing")
    - "Abort task" (description: "Discard changes and revert task status")

- **If "Commit changes":**
  - **Consolidate the plan file** before committing:
    - Read the current plan file from `aiplans/`
    - Review `git diff --stat` against the plan to identify any changes not yet documented
    - Add or update a "Final Implementation Notes" section at the end of the plan:
      ```markdown
      ## Final Implementation Notes
      - **Actual work done:** <summary of what was actually implemented vs what was originally planned>
      - **Deviations from plan:** <any changes from the original approach and why>
      - **Issues encountered:** <problems found during implementation and how they were resolved>
      - **Key decisions:** <technical decisions made during implementation>
      - **Notes for sibling tasks:** <patterns established, gotchas discovered, shared code created, or other information useful for subsequent child tasks> (include this section if this is a child task)
      ```
    - **IMPORTANT for child tasks:** The plan file will be archived and serve as the primary reference for subsequent sibling tasks. Ensure the Final Implementation Notes are comprehensive enough that a fresh context can understand what was done and learn from the experience.
    - The plan file should now serve as a complete record of: the original plan, any post-review change requests (from the "Need more changes" loop), and final implementation notes
  - Stage and commit all implementation changes (including the updated plan file)
  - **IMPORTANT — Commit message convention:** The commit message MUST use the format `<issue_type>: <description> (t<task_id>)`, where `<issue_type>` is the value from the task's `issue_type` frontmatter field (one of: `bug`, `chore`, `documentation`, `feature`, `performance`, `refactor`, `style`, `test`). Examples: `feature: Add channel settings screen (t16)`, `bug: Fix login validation (t16_2)`, `refactor: Simplify auth module (t42)`. The `(t<task_id>)` suffix is used by `aitask_issue_update.sh` to find commits associated with a task when posting to GitHub issues. Only source code implementation commits should use this format — administrative commits (status changes, archival in Steps 4, 9, and Task Abort Procedure) use the `ait:` prefix instead and must NOT include the `(t<task_id>)` tag.
  - Proceed to Step 9

- **If "Need more changes":**
  - Ask user what needs to change
  - Make the requested changes
  - **Update the plan file** to log what was changed:
    - Append a "Post-Review Changes" section (if not already present) to the plan file in `aiplans/`
    - Add a numbered change request entry with timestamp:
      ```markdown
      ## Post-Review Changes

      ### Change Request 1 (YYYY-MM-DD HH:MM)
      - **Requested by user:** <summary of what the user asked for>
      - **Changes made:** <summary of what was actually implemented>
      - **Files affected:** <list of modified files>
      ```
    - Increment the change request number for each review iteration
  - Return to the beginning of Step 8

- **If "Abort":**
  - Execute the **Task Abort Procedure** (see below)

### Step 9: Post-Implementation

Execute the post-implementation cleanup steps.

**If a separate branch was created:**

**IMPORTANT:** Use `AskUserQuestion` to ask: "Proceed with merge of code changes to main branch?" with options "Yes, proceed with merge" / "No, not yet". Do NOT proceed until the user approves.

- **Check for uncommitted changes:**
  ```bash
  git status --porcelain
  ```

- **Merge branch into main:**
  ```bash
  git checkout main
  git merge aitask/<task_name>
  ```

- **Handle merge conflicts:** Ask user for guidance if needed.

- **Verify build (if configured):**
  - Read `aitasks/metadata/project_config.yaml` and check the `verify_build` field
  - **If `verify_build` is absent, null, or empty (or file doesn't exist):** Display "No verify_build configured — skipping build verification." and skip this step.
  - **If `verify_build` is a single command string:** Run it.
  - **If `verify_build` is a list of commands:** Run each sequentially (stop on first failure).
  - **If the build fails:**
    1. Analyze the error output and compare against the changes introduced by this task (`git diff` against the base)
    2. **If the failure is caused by this task's changes:** Go back to the implementation to fix the build errors. After fixing, re-run the build command(s). Repeat until the build passes.
    3. **If the failure is NOT related to this task's changes** (pre-existing issue, environment problem, etc.): Log the build failure details in the plan file's "Final Implementation Notes" section under a "Build verification" entry and proceed with the workflow. Do not attempt to fix pre-existing issues.

- **Clean up branch and worktree:**
  ```bash
  git worktree remove aiwork/<task_name>
  rm -rf aiwork/<task_name>
  git branch -d aitask/<task_name>
  ```

**For child tasks — verify plan completeness before archival:**

- Read the plan file from `aiplans/p<parent>/<child_plan>`
- Verify it contains a "Final Implementation Notes" section with comprehensive details
- If missing or incomplete, add/update it now — the archived plan will serve as the primary reference for subsequent sibling tasks
- Ensure the notes include: actual work done, issues encountered and resolutions, and any information useful for sibling tasks

**Run the archive script:**

All archival operations (metadata updates, file moves, lock releases, folded task cleanup, git staging, and commit) are handled by a single script call:

For parent tasks:
```bash
./aiscripts/aitask_archive.sh <task_num>
```

For child tasks:
```bash
./aiscripts/aitask_archive.sh <parent>_<child>
```

The script automatically handles:
- Updating task metadata (status → Done, updated_at, completed_at)
- Creating archive directories and moving task/plan files
- For child tasks: removing child from parent's children_to_implement
- For child tasks: archiving parent too if all children are complete
- Releasing task locks (and parent locks if parent was also archived)
- For parent tasks: deleting folded tasks (if any, where status is not Implementing/Done)
- Git staging and committing all changes

**Parse the script output and handle interactive follow-ups:**

The script outputs structured lines. Parse each line and handle accordingly:

- `ISSUE:<task_num>:<issue_url>` — Execute the **Issue Update Procedure** (see below) for the task
- `PARENT_ISSUE:<task_num>:<issue_url>` — Execute the **Issue Update Procedure** for the parent task
- `FOLDED_ISSUE:<folded_task_num>:<issue_url>` — The folded task's file has been deleted, so the standard Issue Update Procedure cannot be used (it requires the task file). Instead, handle inline:
  - Use `AskUserQuestion`:
    - Question: "Folded task t<folded_task_num> had a linked issue: <issue_url>. Update/close it?"
    - Header: "Issue"
    - Options:
      - "Close with notes" (description: "Post implementation notes from primary task and close")
      - "Comment only" (description: "Post implementation notes but leave open")
      - "Close silently" (description: "Close without posting a comment")
      - "Skip" (description: "Don't touch the issue")
  - If "Close with notes":
    ```bash
    ./aiscripts/aitask_issue_update.sh --issue-url "<issue_url>" --close <task_id>
    ```
  - If "Comment only":
    ```bash
    ./aiscripts/aitask_issue_update.sh --issue-url "<issue_url>" <task_id>
    ```
  - If "Close silently":
    ```bash
    ./aiscripts/aitask_issue_update.sh --issue-url "<issue_url>" --close --no-comment <task_id>
    ```
  - If "Skip": do nothing
  - Note: Uses the primary `task_id` (not `folded_task_num`) so the comment references the primary task's commits and plan file
- `FOLDED_WARNING:<task_num>:<status>` — Warn the user: "Folded task t<N> has status '<status>' — skipping automatic deletion. Please handle it manually."
- `PARENT_ARCHIVED:<path>` — Inform user: "All child tasks complete! Parent task also archived."
- `COMMITTED:<hash>` — Archival commit was created

**Push after archival:**

```bash
./ait git push
```

### Task Abort Procedure

This procedure is referenced from Step 6 (plan checkpoint) and Step 8 (user review) wherever the user selects "Abort task". It handles lock release, status revert, email clearing, and worktree cleanup.

When abort is selected at any checkpoint after Step 4, execute these steps:

- **Ask about plan file (if one was created):**
  Use `AskUserQuestion`:
  - Question: "A plan file was created. What should happen to it?"
  - Header: "Plan file"
  - Options:
    - "Keep for future reference" (description: "Plan file remains in aiplans/")
    - "Delete the plan file" (description: "Remove the plan file")

  If "Delete":
  ```bash
  rm aiplans/<plan_file> 2>/dev/null || true
  ```

- **Ask for revert status:**
  Use `AskUserQuestion`:
  - Question: "What status should the task be set to?"
  - Header: "Status"
  - Options:
    - "Ready" (description: "Task available for others to pick up")
    - "Editing" (description: "Task needs modifications before ready")

- **Release task lock:** Execute the **Lock Release Procedure** (see below) for the task.

- **Revert task status and clear assignment:**
  ```bash
  ./aiscripts/aitask_update.sh --batch <task_num> --status <selected_status> --assigned-to ""
  ```

- **Commit the revert:**
  ```bash
  ./ait git add aitasks/
  ./ait git commit -m "ait: Abort t<N>: revert status to <status>"
  ```

- **Cleanup worktree/branch if created:**
  If a worktree was created in Step 5:
  ```bash
  git worktree remove aiwork/<task_name> --force 2>/dev/null || true
  rm -rf aiwork/<task_name> 2>/dev/null || true
  git branch -d aitask/<task_name> 2>/dev/null || true
  ```

- **Inform user:**
  "Task t<N> has been reverted to '<status>' and is available for others."

### Issue Update Procedure

This procedure is referenced from Step 9 wherever a task is being archived. It handles updating/closing a linked issue via `aitask_issue_update.sh` (platform-agnostic — the script handles GitHub, GitLab, etc.).

- Read the `issue` field from the task file's frontmatter (path specified by the caller)
- If the `issue` field is present and non-empty:
  - Use `AskUserQuestion`:
    - Question: "Task has a linked issue: <issue_url>. Update/close it?"
    - Header: "Issue"
    - Options:
      - "Close with notes" (description: "Post implementation notes + commits as comment and close")
      - "Comment only" (description: "Post implementation notes but leave open")
      - "Close silently" (description: "Close without posting a comment")
      - "Skip" (description: "Don't touch the issue")
  - If "Close with notes":
    ```bash
    ./aiscripts/aitask_issue_update.sh --close <task_num>
    ```
  - If "Comment only":
    ```bash
    ./aiscripts/aitask_issue_update.sh <task_num>
    ```
  - If "Close silently":
    ```bash
    ./aiscripts/aitask_issue_update.sh --close --no-comment <task_num>
    ```
  - If "Skip": do nothing
- If no `issue` field: skip silently

### Lock Release Procedure

This procedure is referenced from the Task Abort Procedure wherever a task lock may need to be released. (Step 9 archival lock releases are handled automatically by `aitask_archive.sh`.)

**When to execute:** After Step 4 has been reached (i.e., a lock may have been acquired). This applies to:
- Task Abort Procedure (task aborted after Step 4)
- Note: Step 9 lock releases are handled by `aitask_archive.sh` and do NOT need this procedure

**Procedure:**

- Release the task lock (best-effort, idempotent):
  ```bash
  ./aiscripts/aitask_lock.sh --unlock <task_num> 2>/dev/null || true
  ```
  This is safe to call even if no lock was acquired (e.g., lock branch not initialized, or lock acquisition was skipped due to infrastructure issues). It succeeds silently in all these cases.

- **For child tasks where the parent is also being archived** (all children complete): also release the parent lock:
  ```bash
  ./aiscripts/aitask_lock.sh --unlock <parent_task_num> 2>/dev/null || true
  ```

---

## Notes

- When working on a child task, always include links to parent and sibling task files for context, plus archived sibling plan files as primary reference for completed siblings
- **Archived sibling context priority:** When gathering context for a child task, prefer archived **plan files** (`aiplans/archived/p<parent>/`) over archived task files (`aitasks/archived/t<parent>/`). Plan files contain the full implementation record; task files are just initial proposals. Only use archived task files as fallback when no corresponding plan exists.
- Child tasks are archived to `aitasks/archived/t<parent>/` preserving the directory structure
- Child plans are archived to `aiplans/archived/p<parent>/` preserving the directory structure
- **IMPORTANT:** When modifying any task file, always update the `updated_at` field in frontmatter to the current date/time using format `YYYY-MM-DD HH:MM`
- **Child task naming:** Use format `t{parent}_{child}_description.md` where both parent and child identifiers are **numbers only**. Do not insert tasks "in-between" (e.g., no `t10_1b` between `t10_1` and `t10_2`). If you discover a missing implementation step, add it as the next available number and adjust dependencies accordingly
- When archiving a task with an `issue` field, the workflow offers to update/close the linked issue using `aitask_issue_update.sh`. The SKILL.md workflow is platform-agnostic; the script handles platform specifics (GitHub, GitLab, etc.). It auto-detects commits and includes "Final Implementation Notes" from the archived plan file.
- **Folded tasks:** When a task has a `folded_tasks` frontmatter field (set by aitask-explore or aitask-fold), the listed tasks are deleted during Step 9 archival. Folded tasks have status `Folded` with a `folded_into` property pointing to the primary task. They are deleted (not archived) because their full content was incorporated into the primary task's description at creation/fold time.
- **Note:** Since aitask-explore creates standalone parent tasks only, the child task archival path does not need to handle `folded_tasks`.

### Project Configuration

Project-level settings are stored in `aitasks/metadata/project_config.yaml` (git-tracked, shared across team). This is separate from execution profiles (workflow behavior) and `userconfig.yaml` (per-user, gitignored).

| Key | Type | Default | Description | Used in |
|-----|------|---------|-------------|---------|
| `verify_build` | string or list | (none — skip) | Shell command(s) to verify the build after implementation | Step 9 |

If the file does not exist or a field is absent, the corresponding feature is skipped.

### Execution Profiles

Profiles are YAML files stored in `aitasks/metadata/profiles/`. They pre-answer workflow questions to reduce interactive prompts. Two profiles ship by default:
- **default** — All questions asked normally (empty profile, serves as template)
- **fast** — Skip confirmations, use userconfig email, work locally on current branch, reuse existing plans

#### Profile Schema Reference

| Key | Type | Required | Values | Step |
|-----|------|----------|--------|------|
| `name` | string | yes | Display name shown during profile selection | Step 0a |
| `description` | string | yes | Description shown below profile name during selection | Step 0a |
| `skip_task_confirmation` | bool | no | `true` = auto-confirm task; omit or `false` = ask | Step 0b |
| `default_email` | string | no | `"userconfig"` = from userconfig.yaml (falls back to first from emails.txt); `"first"` = first from emails.txt; or a literal email address; omit = ask. Note: `assigned_to` from task metadata always takes priority regardless of this setting (see Step 4 email resolution). | Step 4 |
| `create_worktree` | bool | no | `true` = create worktree; `false` = current branch | Step 5 |
| `base_branch` | string | no | Branch name (e.g., `"main"`) | Step 5 |
| `plan_preference` | string | no | `"use_current"`, `"verify"`, or `"create_new"` | Step 6.0 |
| `plan_preference_child` | string | no | Same values as `plan_preference`; overrides `plan_preference` for child tasks. Defaults to `plan_preference` if omitted | Step 6.0 |
| `post_plan_action` | string | no | `"start_implementation"` = skip to impl; omit = ask | Step 6 checkpoint |

Only `name` and `description` are required. Omitting any other key means the corresponding question is asked interactively.

> **Remote-specific profile fields** (e.g., `done_task_action`, `review_action`, `issue_action`) are documented in the `aitask-pickrem` skill. They are only recognized by that skill and ignored by this workflow.

#### Customizing Execution Profiles

**To create a custom profile:**
1. Copy an existing profile: `cp aitasks/metadata/profiles/fast.yaml aitasks/metadata/profiles/my-profile.yaml`
2. Edit `name` and `description` (both required — `description` is shown during profile selection)
3. Add, remove, or change setting keys as needed
4. Any key you omit will cause that question to be asked interactively

**Example — worktree-based workflow:**
```yaml
name: worktree
description: Like fast but creates a worktree on main for each task
skip_task_confirmation: true
default_email: first
create_worktree: true
base_branch: main
plan_preference: use_current
post_plan_action: start_implementation
```

**Notes:**
- Profiles are partial — only include keys you want to pre-configure
- The `description` field is shown next to the profile name when selecting a profile
- Profiles are preserved during `install.sh --force` upgrades (existing files are not overwritten)
- Plan approval (ExitPlanMode) is always mandatory and cannot be skipped by profiles
