# Plan: t41 - Delete empty child directories on completion

## Task
Update the aitask-pick skill to clean up empty child task and plan directories after all child tasks have been archived.

## Problem
When child tasks are archived (moved from `aitasks/t<parent>/` to `aitasks/archived/t<parent>/`), the source directories `aitasks/t<parent>/` and `aiplans/p<parent>/` can become empty but are never deleted. This leaves stale empty directories in the project.

## File to Modify
- `/home/ddt/Work/tubetime/.claude/skills/aitask-pick/SKILL.md` (lines ~435-444)

## Changes

### 1. Update Step 8.9 (child task flow) to include directory cleanup

After checking if all children are complete and finding the list is empty, add instructions to remove the now-empty directories:

**Current Step 8.9** (line 435-437):
```
8.9. **Check if all children complete:**
   - Read parent task's children_to_implement
   - If empty, inform user: "All child tasks complete! Parent task can now be completed."
```

**Updated Step 8.9:**
```
8.9. **Check if all children complete:**
   - Read parent task's children_to_implement
   - If empty:
     - Inform user: "All child tasks complete! Parent task can now be completed."
     - Remove the now-empty child directories:
       ```bash
       rmdir aitasks/t<parent>/ 2>/dev/null || true
       rmdir aiplans/p<parent>/ 2>/dev/null || true
       ```
```

### 2. Update Step 8.10 git commands to stage deleted directories

**Current Step 8.10** (line 439-444):
```
8.10. **Commit archived files to git:**
    ```bash
    git add aitasks/archived/t<parent>/<child_file> aiplans/archived/p<parent>/<child_plan>
    git add -u aitasks/t<parent>/ aiplans/p<parent>/
    git commit -m "Archive completed t<parent>_<child> task and plan files"
    ```
```

**Updated Step 8.10:**
```
8.10. **Commit archived files to git:**
    ```bash
    git add aitasks/archived/t<parent>/<child_file> aiplans/archived/p<parent>/<child_plan>
    git add -u aitasks/t<parent>/ aiplans/p<parent>/
    git add -u aitasks/ aiplans/
    git commit -m "Archive completed t<parent>_<child> task and plan files"
    ```
```

The extra `git add -u aitasks/ aiplans/` ensures that if the directories were removed (last child), git picks up the deletion.

## Verification
- Read the modified SKILL.md to verify the changes are correct
- Check that the `rmdir` commands use `2>/dev/null || true` to avoid errors when directories are not empty (still have remaining children)
