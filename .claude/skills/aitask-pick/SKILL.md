---
name: aitask-pick
description: Select the next AI task for implementation from the `aitasks/` directory.
---

## Workflow

### Step 0a: Select Execution Profile

Check for available execution profiles:

```bash
ls aitasks/metadata/profiles/*.yaml 2>/dev/null
```

**If no profiles found:** Skip this step (no profile active, all questions asked normally).

**If exactly one profile found:** Auto-load it and inform user: "Using execution profile: \<name\> (\<description\>)".

**If multiple profiles found:**

Read each profile's `name` and `description` fields. Use `AskUserQuestion`:
- Question: "Select an execution profile (pre-configured answers to reduce prompts):"
- Header: "Profile"
- Options:
  - Each profile: label = `name` field, description = `description` field
  - "No profile" (description: "Ask all questions interactively")

**If "No profile" selected:** Proceed with all questions asked normally (no active profile).

Store the selected profile in memory for use throughout remaining steps.

**Error handling:** If a profile file has invalid YAML, warn the user ("Profile '\<filename\>' has invalid format, skipping") and exclude it from the selection list.

### Step 0b: Check for Direct Task Selection (Optional Argument)

If this skill is invoked with a numeric argument:

**Format 1: Parent task (e.g., `/aitask-pick 16`):**
- Parse the argument as the task number
- Find the matching task file:
  ```bash
  ls aitasks/t<number>_*.md 2>/dev/null
  ```
- If found, check if it's a parent task (has children directory):
  ```bash
  ls aitasks/t<number>/ 2>/dev/null
  ```
  - If it has children → proceed to **Step 2d** (Child Task Selection)
  - If no children:
    - **Show task summary and confirm:**
      - Read the task file content
      - Generate a brief 1-2 sentence summary of the task description
      - **Profile check:** If the active profile has `skip_task_confirmation` set to `true`:
        - Display: "Profile '\<name\>': auto-confirming task selection"
        - Skip the AskUserQuestion below and proceed directly to **Step 3** (Task Status Checks)

        Otherwise, use `AskUserQuestion`:
        - Question: "Is this the correct task? Brief summary: <1-2 sentence summary of the task>"
        - Header: "Confirm task"
        - Options: "Yes, proceed" (description: "This is the correct task, continue with aitask-pick workflow") / "No, abort" (description: "Wrong task, cancel the selection")
      - If "Yes, proceed" → proceed to **Step 3** (Task Status Checks)
      - If "No, abort" → fall back to normal task selection (proceed to Step 1)

**Format 2: Child task (e.g., `/aitask-pick 16_2`):**
- Parse as child task ID (parent=16, child=2)
- Find the matching child task file:
  ```bash
  ls aitasks/t<parent>/t<parent>_<child>_*.md 2>/dev/null
  ```
- If found:
  - Set this as the selected task
  - Read the task file and parent task for context
  - **Gather archived sibling context:** Read archived sibling plan files from `aiplans/archived/p<parent>/` as the primary context source for completed siblings (these contain full implementation records). Only fall back to reading archived sibling task files from `aitasks/archived/t<parent>/` for siblings that have no corresponding archived plan.
  - Also read pending sibling task files from `aitasks/t<parent>/` and their plans from `aiplans/p<parent>/` if they exist.
  - **Show task summary and confirm:**
    - Generate a brief 1-2 sentence summary of the child task description, mentioning the parent task name for context
    - **Profile check:** If the active profile has `skip_task_confirmation` set to `true`:
      - Display: "Profile '\<name\>': auto-confirming task selection"
      - Skip the AskUserQuestion below and proceed directly to **Step 3** (Task Status Checks)

      Otherwise, use `AskUserQuestion`:
      - Question: "Is this the correct task? Brief summary: <1-2 sentence summary of the child task> (Parent: <parent task name>)"
      - Header: "Confirm task"
      - Options: "Yes, proceed" (description: "This is the correct task, continue with aitask-pick workflow") / "No, abort" (description: "Wrong task, cancel the selection")
    - If "Yes, proceed" → proceed to **Step 3** (Task Status Checks)
    - If "No, abort" → fall back to normal task selection (proceed to Step 1)

**If no file is found:**
- Display error message
- Fall back to normal task selection (proceed to Step 1)

If no argument is provided, proceed with Step 1 as normal.

### Step 0c: Sync with Remote (Best-effort)

Before listing tasks, do a best-effort pull to ensure the local task list is up to date (prevents picking a task that another PC already started):

```bash
git pull --ff-only --quiet 2>/dev/null || true
```

This is non-blocking — if it fails (e.g., no network, merge conflicts), continue silently.

### Step 1: Label Filtering (Optional)

Before retrieving tasks, ask the user if they want to filter by labels.

- Read available labels from `aitasks/metadata/labels.txt`
- Use `AskUserQuestion` with multiSelect:
  - Question: "Do you want to filter tasks by specific labels? (Select labels to include, or skip to show all)"
  - Header: "Labels"
  - Options: List each label from labels.txt, plus "Show all tasks (no filter)"
- If labels selected, pass them to the task listing command using `-l label1,label2`

### Step 2: List and Select Task

#### 2a: Get Top Tasks

Run the task selection script to get the top 15 prioritized **parent** tasks:

```bash
./aiscripts/aitask_ls.sh -v 15
```

If labels were selected in Step 1:
```bash
./aiscripts/aitask_ls.sh -v -l label1,label2 15
```

**Note:** This only shows parent-level tasks, not children. Parent tasks with pending children will show as "Has children" and can be selected to drill down into child tasks.

The output format with `-v` is:
```
t<number>_<name>.md [Status: <status>, Priority: <priority>, Effort: <effort>]
```

#### 2b: Generate Task Summaries

For each task returned by the script:

- Read the corresponding task file from `aitasks/<filename>`
- Check if it has children:
  ```bash
  ls aitasks/t<number>/ 2>/dev/null
  ```
- Generate a brief summary including child count if applicable
- Present each task in this format:

```
<filename> [Priority: <priority>, Effort: <effort>, Status: <status>]
<brief summary of task content>
Children: <N children pending> (or "None")
___________
```

#### 2c: Ask User to Select Task

**Note:** This sub-step is skipped if a task number was provided as an argument in Step 0b.

Since `AskUserQuestion` supports a maximum of 4 options, implement pagination to show all available tasks:

**Pagination loop:**

- Start with `current_offset = 0` and `page_size = 3` (3 tasks per page + 1 "Show more" slot).

- For the current page, take tasks from index `current_offset` to `current_offset + page_size - 1`.

- Build `AskUserQuestion` options:
  - For each task in the current page slice: option label = task filename, description = brief summary with metadata
  - If there are more tasks beyond this page: add a **"Show more tasks"** option (description: "Show next batch of tasks (N more available)")

- Present options via `AskUserQuestion`.

- Handle selection:
  - If user selects a task → proceed to Step 2d (if parent with children) or Step 3
  - If user selects "Show more tasks" → increment `current_offset` by `page_size`, loop back to building the page options
  - If this is the last page (no "Show more" needed), show up to 4 tasks instead of 3

#### 2d: Child Task Selection (For Parent Tasks with Children)

If the selected task is a parent task with children in `aitasks/t<N>/`:

- List all child tasks:
  ```bash
  ./aiscripts/aitask_ls.sh -v --children <parent_num> 99
  ```

- Read each child task file for summaries

- Use `AskUserQuestion`:
  - Question: "This is a parent task with child subtasks. Select which to work on:"
  - Options:
    - Each ready (unblocked) child task with brief summary
    - "Work on parent directly" (only if all children are complete)

- If child selected:
  - Set child as the working task
  - Include links to parent and pending sibling task files in the context
  - **Include archived sibling context:** Read archived sibling plan files from `aiplans/archived/p<parent>/` as primary reference for completed siblings (these contain full implementation records with post-implementation feedback). Only include archived sibling task files from `aitasks/archived/t<parent>/` for siblings without a corresponding archived plan.
  - Proceed to Step 3

### Step 3: Task Status Checks

After a task is selected and confirmed (from Step 0b or Step 2), perform these checks before proceeding to Step 4.

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

### Step 4: Assign Task to User

- **Read stored emails:**
  ```bash
  cat aitasks/metadata/emails.txt 2>/dev/null | sort -u
  ```

- **Profile check:** If the active profile has `default_email` set:
  - If value is `"first"`: Read `aitasks/metadata/emails.txt` and use the first email address. Display: "Profile '\<name\>': using email \<email\>". If emails.txt is empty or missing, fall through to the AskUserQuestion below.
  - If value is a literal email address: Use that email directly. Display: "Profile '\<name\>': using email \<email\>"
  - Skip the AskUserQuestion below

  Otherwise, **ask for email using `AskUserQuestion`:**
  - Question: "Enter your email to track who is working on this task (optional):"
  - Header: "Email"
  - Options:
    - List each stored email from emails.txt (if any exist)
    - "Enter new email" (description: "Add a new email address")
    - "Skip" (description: "Don't assign this task to anyone")

- **If "Enter new email" selected:**
  - Ask user to type their email via `AskUserQuestion` with free text (use the "Other" option)

- **If email provided (new or selected):**
  - Store new email to file:
    ```bash
    echo "user@example.com" >> aitasks/metadata/emails.txt
    sort -u aitasks/metadata/emails.txt -o aitasks/metadata/emails.txt
    ```

- **Update task status to "Implementing" and set assigned_to:**
  ```bash
  ./aiscripts/aitask_update.sh --batch <task_num> --status Implementing --assigned-to "<email>"
  ```
  Or if no email (user selected "Skip"):
  ```bash
  ./aiscripts/aitask_update.sh --batch <task_num> --status Implementing
  ```

- **Commit and push the status change:**
  ```bash
  git add aitasks/
  git commit -m "Start work on t<N>: set status to Implementing"
  git push
  ```

- **Store previous status for potential abort** (remember it was "Ready" before picking)

### Step 5: Environment and Branch Setup

- **Profile check:** If the active profile has `run_location` set:
  - Use the value directly (`"locally"` or `"remotely"`). Display: "Profile '\<name\>': running \<value\>"
  - Skip the AskUserQuestion below

  Otherwise, use `AskUserQuestion` to ask:
  - "Are you running Claude Code locally or remotely?"
  - Options: "Locally" / "Remotely"

- If running **locally**:

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

**If No or running remotely:**
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

**Profile check:** If the active profile has `plan_preference` set:
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

**For child tasks:** Include context links to related files (in priority order):
- Parent task file: `aitasks/t<parent>_<name>.md`
- Archived sibling plan files (primary reference for completed siblings): `aiplans/archived/p<parent>/p<parent>_*_*.md` — these contain the most up-to-date and detailed implementation records including post-implementation feedback
- Archived sibling task files (fallback, only for siblings without an archived plan): `aitasks/archived/t<parent>/t<parent>_*_*.md`
- Pending sibling task files: `aitasks/t<parent>/t<parent>_*_*.md`
- Pending sibling plan files: `aiplans/p<parent>/p<parent>_*_*.md`

While in plan mode:

- Ask the user clarifying questions about the task requirements
- Explore the codebase to understand the relevant architecture
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
    - After creation, ask which child to start with
    - Restart the pick process with `/aitask-pick <parent>_1`
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
If "Abort": Execute abort procedure (see Abort Handling section).

### Step 7: Implement

Follow the approved plan, working in the directory specified in the plan metadata.

Update the external plan file as you progress:
- Mark steps as completed
- Note any deviations or changes from the original plan
- Record issues encountered during implementation

**IMPORTANT:** Do NOT commit changes automatically after implementation. Proceed to Step 8 for user review and approval.

**Note:** When committing implementation changes (in Step 8), the commit message must include `(t<task_id>)`. See Step 8 for details.

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
  - **IMPORTANT — Commit message convention:** The commit message MUST include `(t<task_id>)` at the end (e.g., `Add channel settings screen (t16)` or `Fix login validation (t16_2)`). This tag is used by `aitask_issue_update.sh` to find commits associated with a task when posting to GitHub issues. Only source code implementation commits should include this tag — administrative commits (status changes, archival in Steps 4, 9, and Abort) must NOT include it.
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
  - Execute abort procedure (see Abort Handling section)

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

- **Verify build:**
  ```bash
  JAVA_HOME=/opt/android-studio/jbr ./gradlew assembleDebug
  ```

- **Clean up branch and worktree:**
  ```bash
  git worktree remove aiwork/<task_name>
  rm -rf aiwork/<task_name>
  git branch -d aitask/<task_name>
  ```

**For child tasks:**

- **Verify plan completeness before archival:**
  - Read the plan file from `aiplans/p<parent>/<child_plan>`
  - Verify it contains a "Final Implementation Notes" section with comprehensive details
  - If missing or incomplete, add/update it now — the archived plan will serve as the primary reference for subsequent sibling tasks
  - Ensure the notes include: actual work done, issues encountered and resolutions, and any information useful for sibling tasks

- **Update parent's children_to_implement:**
  ```bash
  ./aiscripts/aitask_update.sh --batch <parent_num> --remove-child t<parent>_<child>
  ```

- **Archive the child task file:**
  ```bash
  mkdir -p aitasks/archived/t<parent>
  sed -i 's/^status: .*/status: Done/' aitasks/t<parent>/<child_file>
  sed -i 's/^updated_at: .*/updated_at: '"$(date '+%Y-%m-%d %H:%M')"'/' aitasks/t<parent>/<child_file>
  sed -i '/^updated_at:/a completed_at: '"$(date '+%Y-%m-%d %H:%M')"'' aitasks/t<parent>/<child_file>
  mv aitasks/t<parent>/<child_file> aitasks/archived/t<parent>/
  ```

- **Archive the child plan file:**
  ```bash
  mkdir -p aiplans/archived/p<parent>
  mv aiplans/p<parent>/<child_plan> aiplans/archived/p<parent>/
  ```

- **Update/close associated issue (if linked):** Execute the **Issue Update Procedure** (see below) for the child task, reading the `issue` field from `aitasks/archived/t<parent>/<child_file>`.

- **Check if all children complete:**
  - Read parent task's children_to_implement
  - If empty:
    - Inform user: "All child tasks complete! Archiving parent task as well."
    - Remove the now-empty child directories:
      ```bash
      rmdir aitasks/t<parent>/ 2>/dev/null || true
      rmdir aiplans/p<parent>/ 2>/dev/null || true
      ```
    - **Archive the parent task file:**
      ```bash
      sed -i 's/^status: .*/status: Done/' aitasks/<parent_task_file>
      sed -i 's/^updated_at: .*/updated_at: '"$(date '+%Y-%m-%d %H:%M')"'/' aitasks/<parent_task_file>
      sed -i '/^updated_at:/a completed_at: '"$(date '+%Y-%m-%d %H:%M')"'' aitasks/<parent_task_file>
      mv aitasks/<parent_task_file> aitasks/archived/<parent_task_file>
      ```
    - **Archive the parent plan file (if it exists):**
      ```bash
      mv aiplans/<parent_plan_file> aiplans/archived/<parent_plan_file> 2>/dev/null || true
      ```
    - **Update/close parent's associated issue (if linked):** Execute the **Issue Update Procedure** (see below) for the parent task, reading the `issue` field from `aitasks/archived/<parent_task_file>`.

- **Commit archived files to git:**
  ```bash
  git add aitasks/archived/t<parent>/<child_file> aiplans/archived/p<parent>/<child_plan>
  git add -u aitasks/t<parent>/ aiplans/p<parent>/
  git add -u aitasks/ aiplans/
  # If parent was also archived (all children complete):
  git add aitasks/archived/<parent_task_file> 2>/dev/null || true
  git add aiplans/archived/<parent_plan_file> 2>/dev/null || true
  git commit -m "Archive completed t<parent>_<child> task and plan files"
  ```

**For parent tasks:**

- **Archive the task file:**
  ```bash
  sed -i 's/^status: .*/status: Done/' aitasks/<task_file>
  sed -i 's/^updated_at: .*/updated_at: '"$(date '+%Y-%m-%d %H:%M')"'/' aitasks/<task_file>
  sed -i '/^updated_at:/a completed_at: '"$(date '+%Y-%m-%d %H:%M')"'' aitasks/<task_file>
  mv aitasks/<task_file> aitasks/archived/<task_file>
  ```

- **Archive the plan file:**
  ```bash
  mv aiplans/<plan_file> aiplans/archived/<plan_file>
  ```

- **Update/close associated issue (if linked):** Execute the **Issue Update Procedure** (see below) for the task, reading the `issue` field from `aitasks/archived/<task_file>`.

- **Commit archived files to git:**
  ```bash
  git add aitasks/archived/<task_file> aiplans/archived/<plan_file>
  git add -u aitasks/ aiplans/
  git commit -m "Archive completed <task_id> task and plan files"
  ```

### Abort Handling

When abort is selected at any checkpoint, execute these steps:

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

- **Revert task status and clear assignment:**
  ```bash
  ./aiscripts/aitask_update.sh --batch <task_num> --status <selected_status> --assigned-to ""
  ```

- **Commit the revert:**
  ```bash
  git add aitasks/
  git commit -m "Abort t<N>: revert status to <status>"
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

---

## Notes

- This skill uses the project's `aitask_ls.sh` script for task prioritization
- Parent tasks with pending children show as "Has children" and are sorted normally by priority/effort
- The `--children` flag of `aitask_ls.sh` lists only children of a specific parent
- When working on a child task, always include links to parent and sibling task files for context, plus archived sibling plan files as primary reference for completed siblings
- **Archived sibling context priority:** When gathering context for a child task, prefer archived **plan files** (`aiplans/archived/p<parent>/`) over archived task files (`aitasks/archived/t<parent>/`). Plan files contain the full implementation record; task files are just initial proposals. Only use archived task files as fallback when no corresponding plan exists.
- Child tasks are archived to `aitasks/archived/t<parent>/` preserving the directory structure
- Child plans are archived to `aiplans/archived/p<parent>/` preserving the directory structure
- When invoked with a child task argument (e.g., `/aitask-pick 10_2`), the skill goes directly to that child task
- **IMPORTANT:** When modifying any task file, always update the `updated_at` field in frontmatter to the current date/time using format `YYYY-MM-DD HH:MM`
- **Child task naming:** Use format `t{parent}_{child}_description.md` where both parent and child identifiers are **numbers only**. Do not insert tasks "in-between" (e.g., no `t10_1b` between `t10_1` and `t10_2`). If you discover a missing implementation step, add it as the next available number and adjust dependencies accordingly
- When archiving a task with an `issue` field, the workflow offers to update/close the linked issue using `aitask_issue_update.sh`. The SKILL.md workflow is platform-agnostic; the script handles platform specifics (GitHub, GitLab, etc.). It auto-detects commits and includes "Final Implementation Notes" from the archived plan file.

### Execution Profiles

Profiles are YAML files stored in `aitasks/metadata/profiles/`. They pre-answer workflow questions to reduce interactive prompts. Two profiles ship by default:
- **default** — All questions asked normally (empty profile, serves as template)
- **fast** — Skip confirmations, use first stored email, work locally on current branch, reuse existing plans

#### Profile Schema Reference

| Key | Type | Required | Values | Step |
|-----|------|----------|--------|------|
| `name` | string | yes | Display name shown during profile selection | Step 0a |
| `description` | string | yes | Description shown below profile name during selection | Step 0a |
| `skip_task_confirmation` | bool | no | `true` = auto-confirm task; omit or `false` = ask | Step 0b |
| `default_email` | string | no | `"first"` = first from emails.txt; or a literal email address; omit = ask | Step 4 |
| `run_location` | string | no | `"locally"` or `"remotely"` | Step 5.1 |
| `create_worktree` | bool | no | `true` = create worktree; `false` = current branch | Step 5.2 |
| `base_branch` | string | no | Branch name (e.g., `"main"`) | Step 5.3 |
| `plan_preference` | string | no | `"use_current"`, `"verify"`, or `"create_new"` | Step 6.0 |
| `post_plan_action` | string | no | `"start_implementation"` = skip to impl; omit = ask | Step 6 checkpoint |

Only `name` and `description` are required. Omitting any other key means the corresponding question is asked interactively.

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
run_location: locally
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
