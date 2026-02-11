---
Task: t26_support_for_parent_child_tasks.md
Worktree: aiwork/t26_support_for_parent_child_tasks
Branch: aitask/t26_support_for_parent_child_tasks
Base branch: main
---

# Implementation Plan: Parent/Child Task Support (Task t26)

## Overview

This is a large feature requiring 7 sequential implementations. Given the complexity, I recommend implementing this task using the parent/child system itself - creating 7 child tasks for each component.

## Architecture Summary

### New Metadata Fields

**Parent Tasks:**
```yaml
children_to_implement: [t1_1, t1_2, t1_3]  # Only incomplete children
```

**Child Tasks:**
- Child task ID in filename: `t1_1_name.md`, `t1_2_name.md`
- Child depends on previous sibling (user choice during creation)
- Stored in subdirectory: `aitasks/t1/`

### Directory Structure

```
aitasks/
  t1_parent_task.md           # Parent task
  t1/                         # Child directory
    t1_1_first_child.md
    t1_2_second_child.md
  metadata/labels.txt
  archived/
    t5_old_parent.md
    t5/                       # Archived children preserve structure
      t5_1_child.md
    old.tar.gz                # Contains subdirectory structure

aiplans/
  p1_parent_task.md
  p1/                         # Child plans (nested)
    p1_1_first_child.md
  archived/
    old.tar.gz
```

---

## Implementation Components (7 child tasks)

### 1. `aitasks_create.sh` - [COMPLETED]
**File:** `/home/ddt/Work/tubetime/aitasks_create.sh`

**New CLI options:**
- `--parent, -P TASK_NUM` - Create as child of specified parent
- `--no-sibling-dep` - Skip default sibling dependency

**New functions:**
- `get_next_child_number()` - Find next child number for parent
- `select_parent_task()` - Interactive fzf selection
- `update_parent_children_to_implement()` - Add child to parent metadata
- `create_child_task_file()` - Create file in `aitasks/t<N>/`

**Interactive flow change:** Add parent selection after metadata collection

---

### 2. `aitask-create` skill - [COMPLETED]
**File:** `.claude/skills/aitask-create/SKILL.md`

**Changes:**
- Add Step 2c: Parent task selection with `AskUserQuestion`
- Ask about sibling dependency per task
- Update Step 5 to create files in child directories
- Call `aitasks_update.sh --add-child` to update parent

---

### 3. `aitasks_update.sh` - [COMPLETED]
**File:** `/home/ddt/Work/tubetime/aitasks_update.sh`

**New CLI options:**
- `--add-child CHILD_ID`
- `--remove-child CHILD_ID`
- `--children CHILDREN` (replace all)

**Key changes:**
- Parse `children_to_implement` from YAML
- `resolve_task_file()` handles child task IDs (e.g., `1_2` → `aitasks/t1/t1_2_*.md`)
- `handle_child_task_completion()` - When child status → Done, update parent's list
- Validation: Cannot complete parent with incomplete children

---

### 4. `aitasks_ls.sh` - [COMPLETED]
**File:** `/home/ddt/Work/tubetime/aitasks_ls.sh`

**New CLI options:**
- `--children, -c PARENT` - List only children of parent
- `--all-levels` - Show all tasks including children
- `--tree` - Hierarchical view

**Key changes:**
- Scan subdirectories `aitasks/t*/` for child tasks
- `is_task_uncompleted()` handles child IDs
- Parent auto-blocked if `children_to_implement` is non-empty
- Tree output format with indentation

---

### 5. `aitask-pick` skill - [COMPLETED]
**File:** `.claude/skills/aitask-pick/SKILL.md`

**Major changes:**
1. **Step 0:** Handle child task selection (`/aitask-pick 1_2`)
2. **New Step 3b:** Secondary selection for parent's children
3. **Step 6:** Complexity assessment - suggest breaking into child tasks
4. **Step 7:** Plan files for children go to `aiplans/p<N>/`
5. **Step 9:** Archive children to `aitasks/archived/t<N>/`

**Context injection:** Include links to parent/sibling task files (paths only, not inline content)

---

### 6. `aitask_clear_old.sh` - [COMPLETED]
**File:** `/home/ddt/Work/tubetime/aitask_clear_old.sh`

**Changes:**
- `archive_files()` preserves subdirectory structure
- `get_files_to_archive()` scans child directories
- `find_files_to_keep()` keeps most recent per subdirectory
- tar.gz includes `t<N>/` directories

---

### 7. `aitask-cleanold` skill - [COMPLETED]
**File:** `.claude/skills/aitask-cleanold/SKILL.md`

**Changes:** Documentation update for new archive structure

---

## Edge Cases Handled

1. **Converting task to parent:** First child creation adds `children_to_implement`
2. **Empty parent:** Only tasks with `children_to_implement` entries are parents
3. **Orphaned children:** Detection and recovery options
4. **Circular deps:** Child cannot depend on parent; parent cannot depend on children
5. **Parent completion:** Blocked until `children_to_implement` is empty

---

## Verification Plan

After each component:

1. **aitasks_create.sh:**
   ```bash
   # Create parent then child
   ./aitasks_create.sh --batch --name "test_parent" --priority high --effort high
   ./aitasks_create.sh --batch --parent 27 --name "test_child" --priority medium --effort low
   # Verify: aitasks/t27/ exists, t27_1_test_child.md created
   ```

2. **aitasks_update.sh:**
   ```bash
   ./aitasks_update.sh --batch 27 --add-child t27_2
   ./aitasks_update.sh --batch 27_1 --status Done
   # Verify: parent children_to_implement updated
   ```

3. **aitasks_ls.sh:**
   ```bash
   ./aitasks_ls.sh --children 27
   ./aitasks_ls.sh --tree
   # Verify: children listed, tree shows hierarchy
   ```

4. **aitask-pick skill:** Manual test - pick parent task and verify child selection

5. **aitask_clear_old.sh:**
   ```bash
   ./aitask_clear_old.sh --dry-run
   # Verify: subdirectory structure shown in archive plan
   ```

---

## Recommended Approach

Given this task has 7 components and high complexity, I recommend:

1. Create t26 as a parent task
2. Create 7 child tasks (t26_1 through t26_7) for each component
3. Implement each child sequentially

This will serve as both implementation AND validation of the parent/child system (starting from component 1 which enables the rest).

---

## Working Directory

- Worktree: `aiwork/t26_support_for_parent_child_tasks`
- Branch: `aitask/t26_support_for_parent_child_tasks`
- Base: `main`

---
COMPLETED: 2026-02-01 23:51
