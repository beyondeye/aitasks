---
name: aitask-revert
description: Revert changes associated with completed tasks — fully or partially
user-invocable: true
---

## Arguments

- No argument: show task discovery options (Step 1)
- Numeric argument (e.g., `/aitask-revert 42` or `/aitask-revert t42`): skip discovery, go directly to task analysis (Step 2). Both `42` and `t42` are accepted — strip the leading `t` if present.

## Workflow

### Step 0: Select Execution Profile

Scan available execution profiles:

```bash
./.aitask-scripts/aitask_scan_profiles.sh
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

**After selection:** Read the chosen profile file: `cat aitasks/metadata/profiles/<filename>`. Store the profile in memory for use throughout remaining steps. Store the `<filename>` value as `active_profile_filename`.

### Step 1: Task Discovery

**If a task argument was provided** (e.g., `/aitask-revert 42` or `/aitask-revert t42`):
- Parse the argument as the task ID. If the argument starts with `t` or `T`, strip the prefix (e.g., `t42` → `42`)
- Validate the task exists:
  ```bash
  ./.aitask-scripts/aitask_query_files.sh resolve <number>
  ```
  Parse the output: if first line is `NOT_FOUND`, display error and fall through to the discovery options below. If first line is `TASK_FILE:<path>`, use that path. Also check `aitasks/archived/` for archived tasks:
  ```bash
  ./.aitask-scripts/aitask_query_files.sh archived-task <number>
  ```
  Parse: `ARCHIVED_TASK:<path>` means found in archive, `NOT_FOUND` means not found.
- If found (active or archived): skip to **Step 2** with the resolved task file path
- If not found: display "Task t\<N\> not found in active or archived tasks." and fall through to discovery options

**Otherwise (no argument):** Present discovery options via `AskUserQuestion`:
- Question: "How would you like to find the task to revert?"
- Header: "Discovery"
- Options:
  - "Browse recent tasks" (description: "List recently implemented tasks from git history")
  - "Search by files" (description: "Select files, then discover which tasks changed them")
  - "Enter task ID" (description: "Type a specific task number directly")

#### Path A: Browse Recent Tasks

Run the analysis script:
```bash
./.aitask-scripts/aitask_revert_analyze.sh --recent-tasks --limit 20
```

Parse the output. Each line has format: `TASK|<id>|<title>|<date>|<commit_count>`

**Pagination loop** (3 tasks per page + "Show more"):
- Start with `current_offset = 0` and `page_size = 3`
- For the current page, take tasks from index `current_offset` to `current_offset + page_size - 1`
- Build `AskUserQuestion` options:
  - For each task in the current page: label = `t<id>: <title>`, description = `<date>, <commit_count> commits`
  - If more tasks beyond this page: add "Show more tasks" (description: "Show next batch (<N> more available)")
- If this is the last page (no "Show more" needed), show up to 4 tasks
- Handle selection:
  - If user selects a task → extract task ID, proceed to **Step 2**
  - If user selects "Show more tasks" → increment `current_offset` by `page_size`, loop back

#### Path B: Search by Files

Read and follow `.claude/skills/user-file-select/SKILL.md` to get file paths. The skill returns a newline-separated list of selected file paths.

After file selection, map files to task IDs:
```bash
./.aitask-scripts/aitask_explain_extract_raw_data.sh --gather <path1> [path2...] --max-commits 50
```

Parse the `RUN_DIR: <path>` line to get the run directory. Read `<run_dir>/reference.yaml` and extract unique task IDs from the commit data (each commit's message contains a `(tN)` or `(tN_M)` tag).

Clean up the run directory:
```bash
./.aitask-scripts/aitask_explain_extract_raw_data.sh --cleanup <run_dir>
```

If no task IDs found: inform user "No tasks found associated with the selected files." and loop back to discovery options.

If task IDs found, present them via paginated `AskUserQuestion` (same pagination pattern as Path A):
- For each task ID: resolve the task file (active or archived), generate a brief summary
- label = `t<id>: <brief summary>`, description = relevant file associations

User selects a task → proceed to **Step 2**.

#### Path C: Enter Task ID

Use `AskUserQuestion`:
- Question: "Enter the task number to revert:"
- Header: "Task ID"
- Options: use "Other" for free text input

Parse the entered number. Validate the task exists (same resolution as direct argument above). If found → proceed to **Step 2**. If not found → inform user and loop back to discovery options.

### Step 2: Task Analysis & Confirmation

Read the task file (may be in `aitasks/` or `aitasks/archived/`). Extract a brief summary of the task description.

Run analysis commands:
```bash
./.aitask-scripts/aitask_revert_analyze.sh --task-commits <id>
./.aitask-scripts/aitask_revert_analyze.sh --task-areas <id>
```

Parse the output:
- `COMMIT|<hash>|<date>|<message>|<insertions>|<deletions>|<task_id>` — each commit
- `AREA|<dir>|<file_count>|<insertions>|<deletions>|<file_list>` — each area

For parent tasks with children: the script automatically includes child task commits. Group commits by `<task_id>` to show per-child breakdown.

**Display summary to user:**
```
## Task t<id>: <task name>
<brief summary>

### Commits (<N> total)
- <hash> (<date>): <message> [+<ins>/-<del>]
- ...

### Areas Affected
- <dir>/ — <file_count> files, +<ins>/-<del>
  Files: <file_list>
- ...

### Per-Child Breakdown (if parent with children)
- t<id>_1: <N> commits
- t<id>_2: <N> commits
```

Use `AskUserQuestion`:
- Question: "Confirm this is the task to revert?"
- Header: "Confirm"
- Options:
  - "Yes, proceed with revert" (description: "Continue to revert type selection")
  - "Select different task" (description: "Go back to task discovery")
  - "Cancel" (description: "Abort the revert workflow")

- "Yes, proceed" → proceed to **Step 3**
- "Select different task" → go back to **Step 1** (discovery options)
- "Cancel" → end the workflow

### Step 3: Revert Type Selection

Use `AskUserQuestion`:
- Question: "What type of revert do you want?"
- Header: "Revert type"
- Options:
  - "Complete revert" (description: "Revert all changes from this task")
  - "Partial revert" (description: "Select which areas/components to revert and which to keep")

- "Complete revert" → proceed to **Step 3a**
- "Partial revert" → proceed to **Step 3b**

### Step 3a: Complete Revert Path

Ask post-revert disposition via `AskUserQuestion`:
- Question: "After reverting, what should happen to the original task?"
- Header: "Disposition"
- Options:
  - "Delete task and plan" (description: "Remove task and plan files entirely from the archive")
  - "Keep archived" (description: "Keep archived with revert notes added to the task file")
  - "Move back to Ready" (description: "Un-archive and set to Ready with revert notes, for potential re-implementation")

Store the selected disposition. Proceed to **Step 4**.

### Step 3b: Partial Revert Path

Present areas from the `--task-areas` output (collected in Step 2). Use `AskUserQuestion` with `multiSelect: true`:
- Question: "Select the areas to REVERT (unselected areas will be kept):"
- Header: "Areas"
- Options: each area as a selectable option
  - label = `<dir>/` , description = `<file_count> files, +<ins>/-<del>: <truncated file list>`

The user can also type free text via "Other" for more granular specification (e.g., specific files within an area).

**After selection, collect per-area commit mapping:**

For each area selected for revert, identify which commits touch files in that area. Iterate commit hashes from the Step 2 analysis. For each commit, get its file list:
```bash
git diff-tree --no-commit-id -r --name-only <hash>
```
Match files against each area's file list to build the per-area commit mapping.

**Show confirmation summary:**

```
## Revert Summary

### Will REVERT:
- <dir1>/ — <files>, touched by commits: <hash1>, <hash2>
- <dir2>/ — <files>, touched by commits: <hash3>

### Will KEEP:
- <dir3>/ — <files>
- <dir4>/ — <files>
```

Use `AskUserQuestion`:
- Question: "Confirm the revert selection?"
- Header: "Confirm"
- Options:
  - "Confirm selection" (description: "Proceed with this revert/keep split")
  - "Adjust selection" (description: "Go back and change which areas to revert")
  - "Cancel" (description: "Abort the revert workflow")

- "Confirm" → ask disposition (same `AskUserQuestion` as Step 3a), then proceed to **Step 4**
- "Adjust" → loop back to the area selection `AskUserQuestion` above
- "Cancel" → end the workflow

### Step 4: Create Revert Task

Build a self-contained task description using the data collected. The description must include ALL information needed for a future planning agent to execute the revert without re-running analysis scripts.

**For complete reverts, build the description from this template:**

```markdown
## Revert: Fully revert t<id> (<original task name>)

### Original Task Summary
<1-2 sentence summary of what the task implemented>

### Commits to Revert (newest first)
- `<hash>` (<date>): <commit message>
  Files: <file1> (+N/-M), <file2> (+N/-M)
[one entry per commit from --task-commits, with file details from --task-files]

### Areas Affected
- `<dir>/` — <file_count> files, +<ins>/-<del>: <file_list>
[one entry per area from --task-areas]

### Revert Instructions
1. Analyze each commit and determine revert approach (git revert, manual edits, or hybrid)
2. Handle conflicts with changes made after the original commits
3. Run verification/tests after reverting

### Implementation Transparency Requirements
During the planning/implementation phase for this revert task, the implementing agent MUST:
1. **Before making any changes**, produce a clear summary for user review:
   - For each file that will be modified: what changes will be reverted, what the file will look like after
   - For each file that will be deleted: confirmation it was added entirely by the original task
   - Motivation for each revert action (why it is safe to revert)
2. **Impact analysis**: Identify code in OTHER parts of the project that depends on or references the changes being reverted. List potential breakages and how they will be addressed.
3. **Present this summary to the user for approval BEFORE executing any revert changes.**

### Post-Revert Task Management
- **Disposition:** <delete task and plan | keep archived with revert notes | move back to Ready>
<specific instructions per disposition choice:>
- Delete: Remove task file, plan file, and archived versions entirely
- Keep archived: Add a "## Reverted" section to the archived task file noting the revert task ID and date
- Move back to Ready: Un-archive task file to aitasks/, set status to Ready, clear assigned_to, add notes about what was reverted
```

**For partial reverts, build the description from this template:**

```markdown
## Revert: Partially revert t<id> (<original task name>)

### Original Task Summary
<1-2 sentence summary>

### Areas to REVERT
- `<dir>/` — Files: <file1>, <file2>, ...
  Commits touching this area:
  - `<hash>` (<date>): <message> — <file1> (+N/-M), <file2> (+N/-M)
[per area selected for revert, with cross-referenced commit-to-file mapping]

### Areas to KEEP (do NOT modify)
- `<dir>/` — Files: <file1>, <file2>, ...
[areas the user chose NOT to revert]

### Revert Instructions
1. Only revert changes in the "Areas to REVERT" section
2. Preserve ALL changes in "Areas to KEEP"
3. When a commit touches BOTH reverted and kept areas, manually revert only the relevant hunks (do NOT use git revert for mixed commits)
4. Run verification/tests after reverting

### Implementation Transparency Requirements
During the planning/implementation phase for this revert task, the implementing agent MUST:
1. **Before making any changes**, produce a detailed summary for user review:
   - For each area being reverted: exactly which lines/functions/features will be removed or changed back
   - For each area being kept: confirm no unintended side effects from reverting the other areas
   - Motivation: why each area is safe to revert independently of the kept areas
2. **Cross-area dependency analysis**: Check for imports, function calls, shared state, or config that crosses the boundary between reverted and kept areas. List each dependency and how it will be resolved.
3. **Impact on other project code**: Identify code OUTSIDE the original task's scope that now depends on the changes being reverted (e.g., other tasks built on top of this one, config references, documentation). List potential breakages and mitigation steps.
4. **Present this summary to the user for approval BEFORE executing any revert changes.**

### Post-Revert Task Management
- **Disposition:** <chosen disposition>
<specific instructions per disposition choice (same as complete revert)>
- If moving back to Ready: add notes to original task about which areas were reverted vs kept, referencing this revert task ID
```

**Also fetch file-level details for the description:**
```bash
./.aitask-scripts/aitask_revert_analyze.sh --task-files <id>
```
Parse the `FILE|<path>|<insertions>|<deletions>` output to populate per-commit file stats in the templates above.

**Create the task:**
```bash
./.aitask-scripts/aitask_create.sh --batch --commit --name "revert_t<id>" --type refactor --desc-file - <<'TASK_DESC'
<built description from template above>
TASK_DESC
```

Read back the created task file to confirm the assigned task ID:
```bash
git log -1 --name-only --pretty=format:'' | grep '^aitasks/t'
```

### Step 5: Decision Point

**Profile check:** If the active profile has `explore_auto_continue` set to `true`:
- Display: "Profile '\<name\>': continuing to implementation"
- Skip the AskUserQuestion below and proceed directly to the handoff

**Default when `explore_auto_continue` is not defined:** `false` (always ask the user).

Otherwise, use `AskUserQuestion`:
- Question: "Revert task created successfully. How would you like to proceed?"
- Header: "Proceed"
- Options:
  - "Continue to implementation" (description: "Start implementing the revert now via the standard workflow")
  - "Save for later" (description: "Task saved — pick it up later with /aitask-pick <N>")

**If "Save for later":**
- Inform user: "Revert task t\<N\>_revert_t\<original_id\>.md is ready. Run `/aitask-pick <N>` when you want to implement it."
- Execute the **Satisfaction Feedback Procedure** (see `.claude/skills/task-workflow/satisfaction-feedback.md`) with `skill_name` = `"revert"`.
- End the workflow.

**If "Continue to implementation":**
- Proceed to Step 6.

### Step 6: Hand Off to Shared Workflow

Set the following context variables from the created revert task, then read and follow `.claude/skills/task-workflow/SKILL.md` starting from **Step 3: Task Status Checks**:

- **task_file**: Path to the created revert task file (e.g., `aitasks/t420_revert_t106.md`)
- **task_id**: The revert task number (e.g., `420`)
- **task_name**: The filename stem (e.g., `t420_revert_t106`)
- **is_child**: `false` (revert creates standalone tasks)
- **parent_id**: null
- **parent_task_file**: null
- **active_profile**: The execution profile loaded in Step 0 (or null if no profile)
- **active_profile_filename**: The `<filename>` value from the scanner output (e.g., `fast.yaml`), or null if no profile
- **previous_status**: `Ready`
- **folded_tasks**: empty list
- **skill_name**: `"revert"`

---

## Notes

- This skill creates standalone (parent-level) revert tasks, not children
- The analysis backend script is `.aitask-scripts/aitask_revert_analyze.sh` (implemented in t398_1)
- For parent tasks with children, `--task-commits` automatically discovers and includes child task commits
- The revert task description is designed to be self-contained — when picked later, the planning agent has all commit hashes, file lists, area breakdowns, and disposition instructions without re-running analysis
- **Implementation Transparency Requirements** in the task description instruct the implementing agent to present a clear pre-revert summary (what will change, impact analysis, cross-area dependencies) and get user approval before executing any changes
- The `explore_auto_continue` profile key controls the "Continue to implementation" decision point (same as aitask-explore, default: `false`)
- When handing off to task-workflow, the revert task has status `Ready` — task-workflow Step 4 will set it to `Implementing`
- For the full Execution Profiles schema and customization guide, see `.claude/skills/task-workflow/SKILL.md`
