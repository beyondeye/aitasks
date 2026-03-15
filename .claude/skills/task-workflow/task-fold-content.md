# Task Fold Content Procedure

This shared procedure builds a structured merged description by incorporating
folded task content into a primary task's description. It is referenced by
aitask-fold (Step 3), aitask-explore (Step 3), aitask-pr-import (Step 5),
and aitask-contribution-review (Step 6).

## Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `primary_description` | The primary task's current description body (everything after frontmatter) | Task description text |
| `folded_task_files` | List of file paths for tasks being folded in | `["aitasks/t12_fix_login.md", "aitasks/t15_auth_timeout.md"]` |

## Procedure

### Step 1: Read Folded Task Content

For each file path in `folded_task_files`:
- Read the full file (frontmatter + description body)
- Extract the task number and name from the filename (e.g., `t12` and `fix_login` from `t12_fix_login.md`)
- Extract the description body (everything after the frontmatter `---` closing delimiter)

### Step 2: Build Merged Description

Construct the merged description with this structure:

1. **Primary description unchanged at the top** — preserve the original `primary_description` exactly as-is

2. **Append each folded task's content** under clearly labeled headers:
   ```markdown
   ## Merged from t<N>: <task_name>

   <full description body of the folded task>
   ```

   Where `<task_name>` is the human-readable name extracted from the filename (underscores replaced with spaces, e.g., `fix_login` → `fix login`).

3. **Append the Folded Tasks reference section** at the end:
   ```markdown
   ## Folded Tasks

   The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

   - **t<N>** (`<filename>`)
   - ...
   ```

### Step 3: Return

Return the complete merged description text.

## Usage by Callers

**"Merge into existing" callers** (aitask-fold, contribution-review): The primary task already exists. After calling this procedure, update the primary task's description:
```bash
./.aitask-scripts/aitask_update.sh --batch <primary_num> --desc-file - <<'TASK_DESC'
<merged description>
TASK_DESC
```

**"Incorporate during creation" callers** (aitask-explore, aitask-pr-import): The primary task is being created. Use the returned merged description as the `TASK_DESC` content for `aitask_create.sh --desc-file -`.
