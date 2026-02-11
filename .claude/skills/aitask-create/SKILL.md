---
name: aitask-create
description: Create a new AI task file with automatic numbering and proper metadata.
---

## Workflow

### Step 1: Check for Parent Task Selection (Optional)

First, list existing active tasks to see if the user wants to create a child task:

```bash
./aiscripts/aitask_ls.sh -v -s all 99
```

Use `AskUserQuestion`:
- Question: "Should this be a child task of an existing task?"
- Options:
  - "No, create standalone task (Recommended)" (description: "Create a new top-level task")
  - List each active task as an option with format "t<N> - <name>" (description: "Create as child of this task")

**If parent task selected:**
- Store the parent task number
- Get the next child number by scanning the parent's subdirectory:
  ```bash
  ls aitasks/t<parent>/t<parent>_*_*.md 2>/dev/null | grep -oE "t<parent>_[0-9]+" | sed "s/t<parent>_//" | sort -n | tail -1
  ```
  Add 1 to get the next child number (or 1 if no children exist).
- Display: "Next child task will be: t<parent>_<child>"

**If standalone task:**
- Proceed with regular task number determination (Step 2)

### Step 2: Determine Next Task Number (Standalone Tasks Only)

Scan active, archived, and compressed task files to find the highest existing task number, then add 1.

**2a. Get task numbers from active tasks:**
```bash
ls aitasks/t*_*.md 2>/dev/null | grep -oE 't[0-9]+' | sed 's/t//' | sort -n
```

**2b. Get task numbers from archived tasks:**
```bash
ls aitasks/archived/t*_*.md 2>/dev/null | grep -oE 't[0-9]+' | sed 's/t//' | sort -n
```

**2c. Get task numbers from compressed archive (if exists):**
```bash
tar -tzf aitasks/archived/old.tar.gz 2>/dev/null | grep -oE 't[0-9]+' | sed 's/t//' | sort -n
```

**2d. Find the maximum and calculate next number:**
Combine all numbers from steps 2a-2c, find the maximum, and add 1.

Display to user: "Next task number will be: t<number>"

### Step 3: Get Task Metadata from User

Use the `AskUserQuestion` tool to gather task metadata:

**3a. Priority:**
- Question: "What is the priority of this task?"
- Options:
  - "High" (description: "Critical or time-sensitive task")
  - "Medium" (description: "Normal priority task")
  - "Low" (description: "Nice-to-have, can wait")

**3b. Effort:**
- Question: "What is the estimated effort for this task?"
- Options:
  - "Low" (description: "Quick task, less than a few hours")
  - "Medium" (description: "Moderate effort, up to a day")
  - "High" (description: "Significant effort, multiple days")

**3c. Dependencies:**
First, list existing active tasks (and siblings if creating a child):
```bash
./aiscripts/aitask_ls.sh -v 99
```

For child tasks, also list siblings:
```bash
ls aitasks/t<parent>/t<parent>_*_*.md 2>/dev/null
```

Then use `AskUserQuestion`:
- Question: "Does this task depend on any existing tasks? Select all that apply, or choose 'None' for no dependencies."
- Options: List siblings first (if child task), then parent-level tasks, plus "None" option
- multiSelect: true (allow multiple selections)

**3d. Sibling Dependency (Child Tasks Only):**
If creating a child task (t<parent>_<N> where N > 1):

Use `AskUserQuestion`:
- Question: "Should this task depend on the previous sibling (t<parent>_<N-1>)?"
- Options:
  - "Yes (Recommended)" (description: "Sequential dependency on previous sibling")
  - "No" (description: "This task can run in parallel with siblings")

If "Yes", add t<parent>_<N-1> to the dependencies.

**Validation:** Only accept task numbers that correspond to existing active tasks.

### Step 4: Get Task Name

Use `AskUserQuestion`:
- Question: "Enter a short name for this task (will be used in filename):"
- Input type: Free text (use "Other" option)

**Sanitize the name:**
1. Convert to lowercase
2. Replace spaces with underscores
3. Replace multiple consecutive underscores with single underscore
4. Remove special characters (keep only a-z, 0-9, and underscores)
5. Trim leading/trailing underscores
6. Truncate to maximum 50 characters

**Final filename:**
- For standalone: `t<number>_<sanitized_name>.md`
- For child task: `t<parent>_<child>_<sanitized_name>.md` in `aitasks/t<parent>/`

Display to user: "Task file will be created as: <filepath>"

### Step 5: Get Task Definition (Iterative)

Collect the task definition iteratively, asking after each chunk if the user wants to add more or insert file references.

**5a. Initial prompt:**
Use `AskUserQuestion`:
- Question: "Enter the task definition (first part). What should be done?"
- Input type: Free text (use "Other" option)

**5b. Continue loop:**
After receiving input, use `AskUserQuestion`:
- Question: "What would you like to do next?"
- Options:
  - "Add more text" (description: "Continue entering task definition")
  - "Insert file reference" (description: "Search for a file and insert its path")
  - "Done" (description: "Finish and create the task file")

**5c. If "Add more text":**
Use `AskUserQuestion`:
- Question: "Enter additional content for the task definition:"
- Input type: Free text (use "Other" option)

Then repeat step 5b.

**5d. If "Insert file reference":**

**5d-i. Get search pattern:**
Use `AskUserQuestion`:
- Question: "Enter partial filename to search for (e.g., 'auth', 'Main', 'screen'):"
- Input type: Free text (use "Other" option)

**5d-ii. Search for matching files:**
Use the `Glob` tool to find matching files:
```
Pattern: **/*<user_input>*
```

This searches recursively for any file containing the search term.

**5d-iii. Present results:**
If matches found (limit to first 10-15 results):
- Use `AskUserQuestion` to present matching files as options
- Question: "Select a file to insert:"
- Options: List each matching file path, plus "Search again" and "Cancel" options

If no matches found:
- Inform user: "No files found matching '<pattern>'"
- Ask if they want to try a different search term or cancel

**5d-iv. Insert selected file:**
- Append the selected file path to the current task description
- Display: "Added: <file_path>"
- Return to step 5b (continue loop)

**5e. If "Done":**
Concatenate all collected text chunks and file references with newline separators and proceed to Step 6.

### Step 6: Create Task File

**For standalone tasks:**
Create the task file at `aitasks/t<number>_<name>.md`

**For child tasks:**
1. Create the parent subdirectory if needed:
   ```bash
   mkdir -p aitasks/t<parent>
   ```
2. Create the task file at `aitasks/t<parent>/t<parent>_<child>_<name>.md`

**File format (YAML front matter):**
```yaml
---
priority: <priority>
effort: <effort>
depends: [<dependencies>]
issue_type: feature
status: Ready
labels: []
created_at: <YYYY-MM-DD HH:MM>
updated_at: <YYYY-MM-DD HH:MM>
---

<task definition content>
```

Where:
- `<priority>` = `high`, `medium`, or `low`
- `<effort>` = `low`, `medium`, or `high`
- `<dependencies>` = comma-separated task IDs (e.g., `1, 3` for regular tasks, `t1_2` for sibling dependencies)

### Step 7: Update Parent Task (Child Tasks Only)

If creating a child task, update the parent's `children_to_implement` list:

```bash
./aiscripts/aitask_update.sh --batch <parent> --add-child t<parent>_<child>
```

If `aitask_update.sh` doesn't support `--add-child` yet, manually update the parent file by adding or updating the `children_to_implement` field in the YAML front matter.

### Step 8: Commit to Git

Stage and commit the new task file:

```bash
git add <task_file_path>
# For child tasks, also add the parent file if it was modified
git add aitasks/t<parent>_*.md 2>/dev/null || true
git commit -m "Add <task_id>: <task_name_humanized>"
```

Where:
- `<task_id>` is `task t<N>` for standalone or `child task t<parent>_<child>` for children
- `<task_name_humanized>` is the task name with underscores replaced by spaces

### Step 9: Confirm Completion

Display a summary to the user:
- Task ID: t<number> (or t<parent>_<child>)
- Parent: t<parent> (if child task)
- Filename: `<filepath>`
- Priority: <priority>
- Effort: <effort>
- Dependencies: <list or "None">
- Git commit: <commit hash>

Optionally ask if the user wants to immediately start working on this task using `/aitask-pick <task_id>`.

## Edge Cases

### Task Number Already Exists
Before writing the file, verify the task number hasn't been used:
```bash
ls aitasks/t<number>_*.md aitasks/archived/t<number>_*.md 2>/dev/null
```
For child tasks:
```bash
ls aitasks/t<parent>/t<parent>_<child>_*.md 2>/dev/null
```
If a file exists, increment the number and try again.

### Empty Task Definition
If the user provides no content, prompt them that a task definition is required before proceeding.

### Invalid Dependency Numbers
If the user enters a dependency number that doesn't correspond to an existing active task, warn them and ask to re-enter.

### Name Sanitization Results in Empty String
If sanitization removes all characters, use "unnamed_task" as the default name.

### Parent Task Doesn't Exist
If creating a child task and the parent doesn't exist, show an error and ask to select a different parent.

## Notes

- Use the YAML front matter format for metadata
- Dependencies should only reference active (non-archived) tasks
- For child tasks, sibling dependencies use the format `t<parent>_<sibling>` (e.g., `t1_2`)
- The task file is committed immediately to ensure it's tracked in version control
- Child tasks are stored in `aitasks/t<parent>/` subdirectory
