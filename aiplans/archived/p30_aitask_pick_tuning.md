---
Task: t30_aitask_pick_tuning.md
Branch: main (working directly)
---

# Implementation Plan: t30_aitask_pick_tuning

## Summary

Six improvements to the aitask-pick skill:

1. **Child task detail requirements** - Standardize what information must be included when creating child tasks
2. **Completion tracking** - Use `completed_at` metadata field instead of appended text
3. **Updated_at field handling** - Make explicit that `updated_at` must be updated when tasks change
4. **Child task naming** - Clarify naming convention: numbers only, no in-between insertions (no t10_1b)
5. **Label filtering** - Ask user to filter by labels before task selection
6. **Task limit increase** - Show top 10 instead of top 5

## Files to Modify

1. `.claude/skills/aitask-pick/SKILL.md` - Main skill definition
2. `aitasks_ls.sh` - Add label filtering support (optional `-l, --labels` flag)

## Implementation Steps

### Step 1: Update SKILL.md - Child Task Detail Requirements

Add a new section after Step 6 (Create Implementation Plan) that specifies required content for child tasks:

```markdown
#### Child Task Documentation Requirements

When creating child tasks, each task file MUST include detailed context that enables independent execution in a fresh Claude Code context. Include:

1. **Context Section**
   - Why this task is needed
   - How it fits into the parent task's goal
   - Relevant background from the exploration phase

2. **Key Files to Modify**
   - Full paths to files that need changes
   - Brief description of what changes are needed in each

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
```

Location: After line 164 in SKILL.md

### Step 2: Update SKILL.md - Completion Tracking (completed_at field)

Replace the current completion tracking approach in Step 9.

**Current (lines 277-279, 297-299):**
```bash
echo -e "\n---\nCOMPLETED: $(date '+%Y-%m-%d %H:%M')" >> aitasks/t<parent>/<child_file>
```

**New approach:**
```bash
# Add completed_at to frontmatter (using sed to insert after updated_at line)
sed -i '/^updated_at:/a completed_at: '"$(date '+%Y-%m-%d %H:%M')"'' aitasks/t<parent>/<child_file>
# Update updated_at timestamp
sed -i 's/^updated_at: .*/updated_at: '"$(date '+%Y-%m-%d %H:%M')"'/' aitasks/t<parent>/<child_file>
```

Remove the `echo -e "\n---\nCOMPLETED:..."` lines from:
- Line 278 (child task archiving)
- Line 285 (child plan archiving)
- Line 298 (parent task archiving)
- Line 304 (parent plan archiving)

### Step 3: Update SKILL.md - Updated_at Field Handling

Add a note in the Notes section at the end:

```markdown
- **IMPORTANT:** When modifying any task file, always update the `updated_at` field in frontmatter to the current date/time using format `YYYY-MM-DD HH:MM`
```

### Step 4: Update SKILL.md - Child Task Naming Convention

Add to the Notes section:

```markdown
- **Child task naming:** Use format `t{parent}_{child}_description.md` where both parent and child identifiers are **numbers only**. Do not insert tasks "in-between" (e.g., no `t10_1b` between `t10_1` and `t10_2`). If you discover a missing step, add it as the next available number and adjust dependencies.
```

### Step 5: Update SKILL.md - Label Filtering (Step 0.5)

Insert new step between Step 0 and Step 1:

```markdown
### Step 0.5: Label Filtering (Optional)

Before retrieving tasks, ask the user if they want to filter by labels.

1. Read available labels from `aitasks/metadata/labels.txt`
2. Use `AskUserQuestion` with multiSelect:
   - Question: "Do you want to filter tasks by specific labels? (Select labels to include, or skip to show all)"
   - Header: "Labels"
   - Options: List each label from labels.txt, plus "Show all tasks (no filter)"
3. If labels selected, pass them to the task listing command
```

### Step 6: Update SKILL.md - Task Limit Increase

Change Step 1 from:
```bash
./aitasks_ls.sh -v 5
```
to:
```bash
./aitasks_ls.sh -v 10
```

Also update line 44 text from "top 5" to "top 10".

### Step 7: Update aitasks_ls.sh - Add Label Filtering

Add new option `-l, --labels` to filter by labels.

**Help text addition (around line 26):**
```bash
  -l, --labels LABELS  Filter by labels (comma-separated). Only show tasks with at least one matching label.
```

**Argument parsing (around line 76):**
```bash
        -l|--labels)
            LABELS_FILTER="$2"
            shift 2
            ;;
```

**Initialize variable (around line 63):**
```bash
LABELS_FILTER=""
```

**Filter logic in process_task_file() (around line 344, after status filter):**
```bash
    # Apply labels filter
    if [[ -n "$LABELS_FILTER" ]]; then
        local match_found=false
        IFS=',' read -ra FILTER_LABELS <<< "$LABELS_FILTER"
        IFS=',' read -ra TASK_LABELS <<< "$labels_text"
        for filter_label in "${FILTER_LABELS[@]}"; do
            for task_label in "${TASK_LABELS[@]}"; do
                if [[ "$filter_label" == "$task_label" ]]; then
                    match_found=true
                    break 2
                fi
            done
        done
        if [[ "$match_found" == false ]]; then
            return
        fi
    fi
```

## Complete Changes Summary

| File | Change |
|------|--------|
| SKILL.md line 44 | "top 5" → "top 10" |
| SKILL.md line 47 | `./aitasks_ls.sh -v 5` → `./aitasks_ls.sh -v 10` |
| SKILL.md after line 40 | Insert Step 0.5 for label filtering |
| SKILL.md after line 164 | Insert child task documentation requirements |
| SKILL.md lines 277-279, 297-299 | Replace completion text with completed_at frontmatter |
| SKILL.md lines 285, 304 | Remove COMPLETED text for plan files |
| SKILL.md Notes section | Add updated_at and naming convention notes |
| aitasks_ls.sh | Add `-l, --labels` option |

## Implementation Progress

- [x] Step 1: Child Task Detail Requirements - Added section in SKILL.md (lines 186-213)
- [x] Step 2: Completion Tracking - Updated to use `completed_at` metadata field
- [x] Step 3: Updated_at Field Handling - Added note in Notes section
- [x] Step 4: Child Task Naming Convention - Added note in Notes section
- [x] Step 5: Label Filtering - Added Step 0.5 in SKILL.md
- [x] Step 6: Task Limit Increase - Changed from 5 to 10 in SKILL.md
- [x] Step 7: Label Filtering in Script - Added `-l, --labels` option to aitasks_ls.sh

## Verification

1. Test label filtering:
   ```bash
   ./aitasks_ls.sh -v -l claudeskills 10
   ```
   Should only show tasks with `claudeskills` label.

2. Test top 10 limit:
   ```bash
   ./aitasks_ls.sh -v 10
   ```
   Should show up to 10 tasks.

3. Test completion tracking manually:
   ```bash
   # Simulate adding completed_at
   sed -i '/^updated_at:/a completed_at: 2026-02-02 15:30' test_task.md
   ```

4. Review SKILL.md manually to ensure:
   - Child task documentation requirements are clear
   - Naming convention is explicit
   - updated_at reminder is present
