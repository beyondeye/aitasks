# Task Selection Procedure

Handles task selection for the aitask-qa skill — both direct (argument-based) and
interactive (recent archived + active tasks). Referenced from Step 1 of the main
SKILL.md workflow.

**Input:**
- Optional task ID argument (e.g., `42`, `16_2`)
- `active_profile` — loaded execution profile (or null)

**Output:**
- `task_file` — path to selected task file
- `task_id` — extracted task identifier (e.g., `42` or `16_2`)
- `is_child` — true if task ID contains `_`
- `parent_id` — parent number if child task, null otherwise
- `is_archived` — true if path starts with `aitasks/archived/`

---

## 1a: Direct Task Selection (if argument provided)

**Format 1: Parent or standalone task (e.g., `/aitask-qa 42`):**
- Try active first:
  ```bash
  ./.aitask-scripts/aitask_query_files.sh resolve <number>
  ```
  Parse the output: if first line is `TASK_FILE:<path>`, use that path.
- If `NOT_FOUND`, try archived:
  ```bash
  ./.aitask-scripts/aitask_query_files.sh archived-task <number>
  ```
  Parse the output: `ARCHIVED_TASK:<path>` means found, `NOT_FOUND` means not found.
- If still not found: display error and fall through to interactive selection (1b).

**Format 2: Child task (e.g., `/aitask-qa 16_2`):**
- Parse as parent=16, child=2
- Try active first:
  ```bash
  ./.aitask-scripts/aitask_query_files.sh child-file <parent> <child>
  ```
- If `NOT_FOUND`, try archived:
  ```bash
  ./.aitask-scripts/aitask_query_files.sh archived-task <parent>_<child>
  ```
- If still not found: display error and fall through to interactive selection (1b).

**Confirm selection:**
- Read the task file and generate a 1-2 sentence summary
- **Profile check:** If `skip_task_confirmation` is `true`:
  - Display: "Profile '<name>': auto-confirming task selection"
  - Skip confirmation and proceed

  Otherwise, use `AskUserQuestion`:
  - Question: "Run QA analysis on this task? Summary: <brief summary>"
  - Header: "Confirm task"
  - Options: "Yes, proceed" / "No, select different task"
- If "No": fall through to interactive selection (1b)
- If "Yes": proceed

**Determine task context:**
- Set `is_child` based on whether the task ID contains `_` (e.g., `16_2`)
- Set `parent_id` if child task
- Set `is_archived` based on whether the path starts with `aitasks/archived/`
- Set `task_id` from the filename (e.g., `42` or `16_2`)

## 1b: Interactive Task Selection (no argument or fallback)

List candidate tasks from two sources:

**Source 1 — Recently archived tasks:**
```bash
./.aitask-scripts/aitask_query_files.sh recent-archived 15
```
Parse `RECENT_ARCHIVED:<path>|<completed_at>|<issue_type>|<task_name>` lines.

**Source 2 — Active tasks with status Done or Implementing:**
```bash
./.aitask-scripts/aitask_ls.sh -v -s Done 15
./.aitask-scripts/aitask_ls.sh -v -s Implementing 15
```

Merge both lists (archived first, then active), deduplicate by task number.

**Read each task file** and generate brief summaries.

**Paginated selection** (same pattern as aitask-pick Step 2c):
- `page_size = 3` (3 tasks per page + 1 "Show more" slot)
- For each task: label = filename, description = `[<status/completed_at>] <brief summary>`
- If more tasks available: add "Show more tasks" option
- Last page: show up to 4 tasks

**Determine task context** (same as 1a).
