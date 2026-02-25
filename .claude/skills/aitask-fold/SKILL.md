---
name: aitask-fold
description: Identify and merge related tasks into a single task, then optionally execute it.
---

## Workflow

### Step 0a: Select Execution Profile

Scan available execution profiles:

```bash
./aiscripts/aitask_scan_profiles.sh
```

Parse the output lines. Each valid profile appears as `PROFILE|<filename>|<name>|<description>`. Lines starting with `INVALID|<filename>` indicate profiles with bad YAML — warn the user ("Profile '\<filename\>' has invalid format, skipping").

**If output is `NO_PROFILES`:** Skip this step (no profile active, all questions asked normally).

**If exactly one `PROFILE` line:** Auto-load it and inform user: "Using execution profile: \<name\> (\<description\>)". Read the full profile: `cat aitasks/metadata/profiles/<filename>`

**If multiple `PROFILE` lines:** Use `AskUserQuestion`:
- Question: "Select an execution profile (pre-configured answers to reduce prompts):"
- Header: "Profile"
- Options:
  - Each profile: label = `name` field, description = `description` field
  - "No profile" (description: "Ask all questions interactively")

**If "No profile" selected:** Proceed with all questions asked normally (no active profile).

**After selection:** Read the chosen profile file: `cat aitasks/metadata/profiles/<filename>`. Store the profile in memory for use throughout remaining steps.

### Step 0b: Check for Explicit Task IDs (Optional Argument)

If this skill is invoked with arguments (e.g., `/aitask-fold 106,108,112` or `/aitask-fold 106 108 112`):

- **Parse task IDs:** Split the argument string by commas and/or spaces to extract individual task IDs. Each ID should be a number (e.g., `106`) — child task IDs (e.g., `106_2`) are not supported for folding.

- **Validate each task ID:**
  For each parsed ID:
  - Find the task file:
    ```bash
    ./aiscripts/aitask_query_files.sh task-file <id>
    ```
    Parse the output: `TASK_FILE:<path>` means found (use that path), `NOT_FOUND` means not found.
  - If not found: warn "t\<id\>: file not found — skipping" and exclude.
  - If found, read the task file's frontmatter and check eligibility:
    - **Status check:** Must be `Ready` or `Editing`. If not, warn "t\<id\>: status is \<status\> — skipping" and exclude.
    - **Children check:** Must not have children:
      ```bash
      ./aiscripts/aitask_query_files.sh has-children <id>
      ```
      Parse the output: `HAS_CHILDREN:<count>` means it has children — warn "t\<id\>: has children — skipping" and exclude. `NO_CHILDREN` means eligible.
    - **Child task check:** Must not be a child task itself (the filename must match `t<number>_*.md` with a single number, not `t<parent>_<child>_*.md`). If it's a child task, warn "t\<id\>: is a child task — skipping" and exclude.

- **Check remaining count:** If fewer than 2 valid tasks remain after filtering, inform user "Need at least 2 eligible tasks to fold. Only \<N\> valid task(s) found." and abort the workflow.

- If 2 or more valid tasks remain, skip to **Step 2** (Primary Task Selection) with the valid task set.

If no argument is provided, proceed with Step 1 as normal.

### Step 0c: Sync with Remote (Best-effort)

Do a best-effort sync to ensure the local state is up to date and clean up stale locks:

```bash
./aiscripts/aitask_pick_own.sh --sync
```

This is non-blocking — if it fails (e.g., no network, merge conflicts), it continues silently.

### Step 1: Interactive Task Discovery

This step is only executed when no task IDs were provided as arguments.

#### 1a: List Eligible Tasks

List all pending tasks:

```bash
./aiscripts/aitask_ls.sh -v --status all --all-levels 99 2>/dev/null
```

Filter the output to include only tasks that are eligible for folding:
- Status must be `Ready` or `Editing`
- Must not have children (status shows "Has children") — too complex to fold
- Must not be a child task — too complex to fold
- Exclude tasks with status `Implementing`, `Postponed`, `Done`, or `Folded`

If fewer than 2 eligible tasks exist, inform user "Need at least 2 eligible tasks to fold. Only \<N\> eligible task(s) found." and abort the workflow.

#### 1b: Identify Related Tasks

For each eligible task:
- Read the task file's title and first ~5 lines of body text
- Note the task's labels from frontmatter

**Identify related groups** by analyzing:
- **Shared labels:** Tasks that share one or more labels are likely related
- **Semantic similarity:** Tasks whose descriptions address the same topic, feature, or problem area

Present a summary of the eligible tasks and any detected relationships.

#### 1c: Select Tasks to Fold

Use `AskUserQuestion` with multiSelect to let the user choose which tasks to fold:
- Question: "Select tasks to fold together into a single task (minimum 2):"
- Header: "Fold tasks"
- Options: Each eligible task with the task filename as label and a brief description including labels and match reasons

**Pagination:** Since `AskUserQuestion` supports a maximum of 4 options, implement pagination if there are more than 3 eligible tasks:
- Start with `current_offset = 0` and `page_size = 3` (3 tasks per page + 1 "Show more" slot)
- For each page, show tasks from `current_offset` to `current_offset + page_size - 1`
- If more tasks exist beyond this page, add a "Show more tasks" option (description: "Show next batch of tasks (N more available)")
- On the last page, show up to 4 tasks
- Accumulate selections across pages

**After selection:** If fewer than 2 tasks were selected, inform user "Need at least 2 tasks to fold." and abort the workflow.

### Step 2: Primary Task Selection

Present the selected tasks and ask the user which should be the "primary" task. The primary task is the one that survives — all other tasks' content will be merged into it, and the other tasks will be deleted after the primary is implemented and archived.

Use `AskUserQuestion`:
- Question: "Which task should be the primary? (Other tasks' content will be merged into it, and they will be deleted after implementation)"
- Header: "Primary"
- Options: Each selected task with filename as label and a brief summary as description

**Pagination:** If more than 4 tasks are selected, paginate with the same pattern as Step 1c.

### Step 3: Merge Content

#### 3a: Read All Task Content

- Read the primary task file's full content (frontmatter + description body)
- Read each non-primary task file's full content

#### 3b: Build Merged Description

Construct the updated description for the primary task:

1. **Keep the primary task's original description unchanged** at the top
2. **Append merged content** from each non-primary task, under clearly labeled headers:
   ```markdown
   ## Merged from t<N>: <task_name>

   <full description body of the non-primary task>
   ```
3. **Append the Folded Tasks reference section** at the end:
   ```markdown
   ## Folded Tasks

   The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

   - **t<N>** (`<filename>`)
   - ...
   ```

#### 3c: Update Primary Task

Update the primary task's description:

```bash
./aiscripts/aitask_update.sh --batch <primary_num> --desc-file - <<'TASK_DESC'
<merged description>
TASK_DESC
```

#### 3d: Set folded_tasks Frontmatter

**Check if the primary task already has a `folded_tasks` field.** If it does, merge (append) the new non-primary task IDs to the existing list rather than replacing.

Set the folded_tasks frontmatter:

```bash
./aiscripts/aitask_update.sh --batch <primary_num> --folded-tasks "<comma-separated list of all folded task IDs>"
```

#### 3e: Update Folded Tasks Status

For each non-primary task ID that was folded, set its status to `Folded` and add the `folded_into` reference:

```bash
./aiscripts/aitask_update.sh --batch <folded_task_num> --status Folded --folded-into <primary_num>
```

#### 3f: Commit

```bash
./ait git add aitasks/
./ait git commit -m "ait: Fold tasks into t<primary_id>: merge t<id1>, t<id2>, ..."
```

### Step 4: Decision Point

**Profile check:** If the active profile has `explore_auto_continue` set to `true`:
- Display: "Profile '\<name\>': continuing to implementation"
- Skip the AskUserQuestion below and proceed directly to the handoff

**Default when `explore_auto_continue` is not defined:** `false` (always ask the user).

Otherwise, use `AskUserQuestion`:
- Question: "Tasks folded successfully into t\<primary_id\>. How would you like to proceed?"
- Header: "Proceed"
- Options:
  - "Continue to implementation" (description: "Start implementing the merged task now via the standard workflow")
  - "Save for later" (description: "Task saved — pick it up later with /aitask-pick <N>")

**If "Save for later":**
- Inform user: "Task t\<primary_id\>_\<name\>.md is ready. Run `/aitask-pick <primary_id>` when you want to implement it."
- End the workflow.

**If "Continue to implementation":**
- Proceed to the handoff below.

### Step 5: Hand Off to Shared Workflow

Set the following context variables from the primary task, then read and follow `.claude/skills/task-workflow/SKILL.md` starting from **Step 3: Task Status Checks**:

- **task_file**: Path to the primary task file (e.g., `aitasks/t106_fix_login_timeout.md`)
- **task_id**: The primary task number (e.g., `106`)
- **task_name**: The filename stem (e.g., `t106_fix_login_timeout`)
- **is_child**: `false` (fold creates standalone merged tasks)
- **parent_id**: null
- **parent_task_file**: null
- **active_profile**: The execution profile loaded in Step 0a (or null if no profile)
- **previous_status**: `Ready`
- **folded_tasks**: List of non-primary task IDs folded into this task (e.g., `[108, 112]`)

---

## Notes

- This skill merges existing tasks — unlike `/aitask-explore` which creates a new task and folds others into it, `/aitask-fold` selects one existing task as the "primary" and merges others into it
- Only standalone parent-level tasks without children and with status `Ready` or `Editing` are eligible for folding
- Child tasks cannot be folded — they are part of a parent task hierarchy and folding would break that structure
- When a task ID is invalid or ineligible, it is excluded with a warning rather than aborting the entire operation. The workflow only aborts if fewer than 2 valid tasks remain
- If the primary task already has a `folded_tasks` frontmatter field (e.g., from a previous fold operation), new IDs are appended to the existing list
- The `explore_auto_continue` profile key controls whether to ask the user about continuing to implementation (default: `false`, always ask). This is the same key used by `/aitask-explore`
- Post-implementation cleanup (deleting folded task files, releasing locks, updating linked issues) is handled by task-workflow Step 9 — no additional cleanup logic is needed in this skill
- The `folded_tasks` frontmatter field tracks which task IDs to clean up. Folded tasks are set to status `Folded` with a `folded_into` property pointing to the primary task. They are deleted after archival
- When handing off to task-workflow, the primary task has status `Ready` — task-workflow's Step 4 will set it to `Implementing`
