---
name: aitask-fold
description: Identify and merge related tasks into a single task, then optionally execute it.
---

## Workflow

### Step 0 (pre-parse): Extract `--profile` argument

If the skill arguments contain `--profile <name>`:
- Extract the `<name>` value (the word following `--profile`)
- Store it as `profile_override`
- Remove `--profile <name>` from the argument string before passing to Step 0b
- If `--profile` appears but no name follows, warn: "Missing profile name after --profile" and set `profile_override` to null

If no `--profile` in arguments, set `profile_override` to null.

Example: `/aitask-fold --profile fast 106,108` or `/aitask-fold 106,108 --profile fast`

### Step 0a: Select Execution Profile

Execute the **Execution Profile Selection Procedure** (see `.claude/skills/task-workflow/execution-profile-selection.md`) with:
- `skill_name`: `"fold"`
- `profile_override`: the value parsed from `--profile` argument (or null)

### Step 0b: Check for Explicit Task IDs (Optional Argument)

If this skill is invoked with arguments (e.g., `/aitask-fold 106,108,112` or `/aitask-fold 106 108 112`):

- **Parse task IDs:** Split the argument string by commas and/or spaces to extract individual task IDs. Each ID can be either a parent task number (e.g., `106`) or a child task ID in the `<parent>_<child>` format (e.g., `106_2`).

- **Validate task IDs:** Run the fold validator and parse its structured output:
  ```bash
  ./.aitask-scripts/aitask_fold_validate.sh <id1> <id2> ...
  ```
  For each output line:
  - `VALID:<id>:<path>` — keep this task in the valid set.
  - `INVALID:<id>:<reason>` — warn "t\<id\>: \<reason\> — skipping" and exclude. `<reason>` values: `not_found`, `status_<status>`, `has_children`, `is_self`.

- **Check remaining count:** If fewer than 2 valid tasks remain after filtering, inform user "Need at least 2 eligible tasks to fold. Only \<N\> valid task(s) found." and abort the workflow.

- If 2 or more valid tasks remain, skip to **Step 2** (Primary Task Selection) with the valid task set.

If no argument is provided, proceed with Step 1 as normal.

### Step 0c: Sync with Remote (Best-effort)

Do a best-effort sync to ensure the local state is up to date and clean up stale locks:

```bash
./.aitask-scripts/aitask_pick_own.sh --sync
```

This is non-blocking — if it fails (e.g., no network, merge conflicts), it continues silently.

### Step 1: Interactive Task Discovery

This step is only executed when no task IDs were provided as arguments.

Execute the **Related Task Discovery Procedure** (see `.claude/skills/task-workflow/related-task-discovery.md`) with:
- **Matching context:** (not used — fold uses "all" mode)
- **Purpose text:** "fold together into a single task (minimum 2)"
- **Min eligible:** 2
- **Selection mode:** all

If the procedure returns fewer than 2 task IDs, inform user "Need at least 2 tasks to fold." and abort the workflow.

Store the selected task IDs for Step 2 (Primary Task Selection).

### Step 2: Primary Task Selection

Present the selected tasks and ask the user which should be the "primary" task. The primary task is the one that survives — all other tasks' content will be merged into it, and the other tasks will be deleted after the primary is implemented and archived.

Use `AskUserQuestion`:
- Question: "Which task should be the primary? (Other tasks' content will be merged into it, and they will be deleted after implementation)"
- Header: "Primary"
- Options: Each selected task with filename as label and a brief summary as description

**Pagination:** If more than 4 tasks are selected, paginate with the same pattern as Step 1c.

### Step 3: Merge Content and Mark Folded Tasks

Merge the folded task content into the primary and update frontmatter in two script calls:

```bash
./.aitask-scripts/aitask_fold_content.sh <primary_file> <folded_file1> <folded_file2> ... \
  | ./.aitask-scripts/aitask_update.sh --batch <primary_num> --desc-file -

./.aitask-scripts/aitask_fold_mark.sh --commit-mode fresh <primary_num> <folded_id1> <folded_id2> ...
```

Parse the `aitask_fold_mark.sh` output for a `COMMITTED:<hash>` line confirming the fold was committed.

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
- **active_profile_filename**: The `<filename>` value from the scanner output for the selected profile (e.g., `fast.yaml` or `local/fast.yaml`), or null if no profile
- **previous_status**: `Ready`
- **folded_tasks**: List of non-primary task IDs folded into this task (e.g., `[108, 112]`)
- **skill_name**: `"fold"`

---

## Notes

- This skill merges existing tasks — unlike `/aitask-explore` which creates a new task and folds others into it, `/aitask-fold` selects one existing task as the "primary" and merges others into it
- Tasks with status `Ready` or `Editing` and without children are eligible for folding — both standalone parent tasks and child tasks
- When a child task is folded, it is automatically removed from its original parent's `children_to_implement` list via the Task Fold Marking Procedure. The child's content is merged into the primary task (which can be any other task — a standalone parent, the same original parent via a sibling, or an unrelated task)
- When a task ID is invalid or ineligible, it is excluded with a warning rather than aborting the entire operation. The workflow only aborts if fewer than 2 valid tasks remain
- If the primary task already has a `folded_tasks` frontmatter field (e.g., from a previous fold operation), new IDs are appended to the existing list
- The `explore_auto_continue` profile key controls whether to ask the user about continuing to implementation (default: `false`, always ask). This is the same key used by `/aitask-explore`
- Post-implementation cleanup (deleting folded task files, releasing locks, updating linked issues) is handled by task-workflow Step 9 — no additional cleanup logic is needed in this skill
- The `folded_tasks` frontmatter field tracks which task IDs to clean up. Folded tasks are set to status `Folded` with a `folded_into` property pointing to the primary task. They are deleted after archival
- When handing off to task-workflow, the primary task has status `Ready` — task-workflow's Step 4 will set it to `Implementing`
