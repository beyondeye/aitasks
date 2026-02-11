# Implementation Plan: Add "Implementing" Status to aitask System

## Task Reference
- Task file: `aitasks/t36_add_in_the_works_status.md`
- Working on: main branch (no separate worktree)

## Overview

Add multi-user support to the aitask system by:
1. Adding "Implementing" status to track work-in-progress tasks
2. Adding `assigned_to` email field to track who is working
3. Creating email storage file (`aitasks/metadata/emails.txt`)
4. Modifying aitask-pick skill with assignment workflow and abort options

## Files to Modify

| File | Purpose |
|------|---------|
| `aitask_update.sh` | Add "Implementing" status + assigned_to field support |
| `aitask_create.sh` | Add "Implementing" status + assigned_to field support |
| `aitask_ls.sh` | Add "Implementing" to status filter options |
| `.claude/skills/aitask-pick/SKILL.md` | Assignment workflow + abort handling |
| `aitasks/metadata/emails.txt` | New file for email storage |

---

## Phase 1: Modify `aitask_update.sh`

### 1.1 Add batch variables (around line 35-38)
```bash
BATCH_ASSIGNED_TO=""
BATCH_ASSIGNED_TO_SET=false
```

### 1.2 Add current value variable (around line 49)
```bash
CURRENT_ASSIGNED_TO=""
```

### 1.3 Update help text (line 87)
Change: `Status: Ready, Editing, Postponed, Done`
To: `Status: Ready, Editing, Implementing, Postponed, Done`

### 1.4 Add help text for assigned_to (around line 99)
Add new line:
```
  --assigned-to, -a EMAIL  Email of assigned person (use "" to clear)
```

### 1.5 Update `parse_args()` (around line 146-181)
Add case:
```bash
--assigned-to|-a) BATCH_ASSIGNED_TO="$2"; BATCH_ASSIGNED_TO_SET=true; shift 2 ;;
```

### 1.6 Update `parse_yaml_frontmatter()` to read assigned_to
Add to case statement (around line 221-302):
```bash
assigned_to) CURRENT_ASSIGNED_TO="$value" ;;
```

### 1.7 Update `write_task_file()` function
Add assigned_to parameter and write to YAML (after labels line):
```bash
local assigned_to="${11:-}"
# In echo block:
if [[ -n "$assigned_to" ]]; then
    echo "assigned_to: $assigned_to"
fi
```

### 1.8 Update `interactive_update_status()` (line 648)
Change: `echo -e "Ready\nEditing\nPostponed\nDone"`
To: `echo -e "Ready\nEditing\nImplementing\nPostponed\nDone"`

### 1.9 Update batch status validation (lines 1060-1061)
Change: `Ready|Editing|Postponed|Done`
To: `Ready|Editing|Implementing|Postponed|Done`

### 1.10 Add batch mode assigned_to processing (around line 1082-1088)
```bash
local new_assigned_to="$CURRENT_ASSIGNED_TO"
if [[ "$BATCH_ASSIGNED_TO_SET" == true ]]; then
    new_assigned_to="$BATCH_ASSIGNED_TO"
fi
```

### 1.11 Update all `write_task_file()` calls to pass assigned_to parameter

---

## Phase 2: Modify `aitask_create.sh`

### 2.1 Add batch variable (around line 33)
```bash
BATCH_ASSIGNED_TO=""
```

### 2.2 Update help text (line 65)
Change: `Status: Ready, Editing, Postponed`
To: `Status: Ready, Editing, Implementing, Postponed`

### 2.3 Add help line for assigned_to (around line 67)
```
  --assigned-to, -a EMAIL  Email of person assigned to task (optional)
```

### 2.4 Update argument parsing (around line 96-117)
Add case:
```bash
--assigned-to|-a) BATCH_ASSIGNED_TO="$2"; shift 2 ;;
```

### 2.5 Update `select_status()` (lines 364-366)
Change: `echo -e "Ready\nEditing\nPostponed"`
To: `echo -e "Ready\nEditing\nImplementing\nPostponed"`

### 2.6 Add email helper functions (after line 368)
```bash
EMAILS_FILE="aitasks/metadata/emails.txt"

ensure_emails_file() {
    local dir
    dir=$(dirname "$EMAILS_FILE")
    mkdir -p "$dir"
    touch "$EMAILS_FILE"
}

add_email_to_file() {
    local email="$1"
    ensure_emails_file
    if [[ -n "$email" ]] && ! grep -qFx "$email" "$EMAILS_FILE" 2>/dev/null; then
        echo "$email" >> "$EMAILS_FILE"
        sort -u "$EMAILS_FILE" -o "$EMAILS_FILE"
    fi
}
```

### 2.7 Update batch status validation (lines 787-788)
Change: `Ready|Editing|Postponed`
To: `Ready|Editing|Implementing|Postponed`

### 2.8 Update `create_task_file()` function
Add assigned_to parameter and write to YAML if provided.

---

## Phase 3: Modify `aitask_ls.sh`

### 3.1 Update help text (lines 22-23)
Change: `Values: Ready, Editing, Postponed, Done, all`
To: `Values: Ready, Editing, Implementing, Postponed, Done, all`

### 3.2 Add assigned_to parsing variable (around line 160)
```bash
assigned_to_text=""
```

### 3.3 Update `parse_yaml_frontmatter()` case statement
Add:
```bash
assigned_to)
    assigned_to_text="$value"
    ;;
```

### 3.4 Update `parse_task_metadata()` reset (around line 310)
Add: `assigned_to_text=""`

### 3.5 Optionally update verbose output to show assigned_to (around line 382)
```bash
local assigned_info=""
if [[ -n "$assigned_to_text" ]]; then
    assigned_info=", Assigned: $assigned_to_text"
fi
# Include in display string
```

---

## Phase 4: Create emails.txt

Create new file: `aitasks/metadata/emails.txt` (empty initially)

---

## Phase 5: Modify `.claude/skills/aitask-pick/SKILL.md`

### 5.1 Add new Step 3.5: Assign Task (insert after Step 3b, before Step 4)

```markdown
### Step 3.5: Assign Task to User

After task selection, before determining execution environment:

1. **Read stored emails:**
   ```bash
   cat aitasks/metadata/emails.txt 2>/dev/null | sort -u
   ```

2. **Ask for email using `AskUserQuestion`:**
   - Question: "Enter your email to track who is working on this task (optional):"
   - Header: "Email"
   - Options:
     - List each stored email from emails.txt
     - "Enter new email" (description: "Add a new email address")
     - "Skip" (description: "Don't assign this task to anyone")

3. **If "Enter new email" selected:**
   - Ask user to type their email via `AskUserQuestion` with free text option

4. **If email provided (new or selected):**
   - Store new email:
     ```bash
     echo "user@example.com" >> aitasks/metadata/emails.txt
     sort -u aitasks/metadata/emails.txt -o aitasks/metadata/emails.txt
     ```

5. **Update task status to "Implementing" and set assigned_to:**
   ```bash
   ./aitask_update.sh --batch <task_num> --status Implementing --assigned-to "<email>"
   ```
   Or if no email:
   ```bash
   ./aitask_update.sh --batch <task_num> --status Implementing
   ```

6. **Commit the status change:**
   ```bash
   git add aitasks/
   git commit -m "Start work on t<N>: set status to Implementing"
   ```

7. **Store previous status for potential abort** (was likely "Ready")
```

### 5.2 Add Abort Checkpoint after Step 5 (Branch Setup)

```markdown
**Abort Option (after Step 5):**
Use `AskUserQuestion`:
- Question: "Branch setup complete. Continue to planning?"
- Header: "Continue"
- Options:
  - "Yes, start planning"
  - "Abort task" (description: "Stop and revert task to previous status")

**If "Abort" selected:** Execute abort procedure (see Abort Handling section)
```

### 5.3 Add Abort Checkpoint after Step 6 (Plan Mode Exit)

```markdown
**Abort Option (after ExitPlanMode):**
Use `AskUserQuestion`:
- Question: "Plan created. How would you like to proceed?"
- Header: "Proceed"
- Options:
  - "Approve and implement"
  - "Revise plan" (description: "Re-enter plan mode")
  - "Abort task" (description: "Stop and revert task status")
```

### 5.4 Add Abort Checkpoint after Step 7 (Plan File Written)

```markdown
**Abort Option (after Step 7):**
Use `AskUserQuestion`:
- Question: "Ready to start implementation?"
- Header: "Implement"
- Options:
  - "Yes, start implementation"
  - "Abort task" (description: "Stop, ask about keeping plan file")
```

### 5.5 Add new section: Abort Handling (after Step 9)

```markdown
### Abort Handling

When abort is selected at any checkpoint:

1. **Ask about plan file (if created):**
   Use `AskUserQuestion`:
   - Question: "A plan file was created. What should happen to it?"
   - Header: "Plan file"
   - Options:
     - "Keep for future reference"
     - "Delete the plan file"

   If "Delete": `rm aiplans/<plan_file> 2>/dev/null || true`

2. **Ask for revert status:**
   Use `AskUserQuestion`:
   - Question: "What status should the task be set to?"
   - Header: "Status"
   - Options:
     - "Ready" (description: "Task available for others to pick up")
     - "Editing" (description: "Task needs modifications before ready")

3. **Revert task status and clear assignment:**
   ```bash
   ./aitask_update.sh --batch <task_num> --status <selected_status> --assigned-to ""
   ```

4. **Commit the revert:**
   ```bash
   git add aitasks/
   git commit -m "Abort t<N>: revert status to <status>"
   ```

5. **Cleanup worktree/branch if created:**
   ```bash
   git worktree remove aiwork/<task_name> --force 2>/dev/null || true
   rm -rf aiwork/<task_name> 2>/dev/null || true
   git branch -d aitask/<task_name> 2>/dev/null || true
   ```

6. **Inform user:**
   "Task t<N> has been reverted to '<status>' and is available for others."
```

---

## Implementation Order

1. Create `aitasks/metadata/emails.txt` (empty file)
2. Modify `aitask_ls.sh` - Add "Implementing" status (low risk, read-only)
3. Modify `aitask_update.sh` - Add "Implementing" + assigned_to (core functionality)
4. Modify `aitask_create.sh` - Add "Implementing" + assigned_to + email helpers
5. Modify `.claude/skills/aitask-pick/SKILL.md` - Workflow changes

---

## Verification

### Test Commands:

1. **Status update works:**
   ```bash
   ./aitask_update.sh --batch 36 --status Implementing --assigned-to "test@example.com"
   head -15 aitasks/t36_add_in_the_works_status.md  # Verify fields
   ```

2. **Status revert works:**
   ```bash
   ./aitask_update.sh --batch 36 --status Ready --assigned-to ""
   ```

3. **List filtering works:**
   ```bash
   ./aitask_ls.sh -v -s Implementing 10
   ./aitask_ls.sh -v -s all 10
   ```

4. **Email storage works:**
   ```bash
   cat aitasks/metadata/emails.txt
   ```

5. **Full workflow test:**
   - Run `/aitask-pick` on a test task
   - Verify email prompt appears
   - Verify task status changes to "Implementing"
   - Verify commit is created
   - Test abort at a checkpoint
   - Verify status reverts and cleanup works
