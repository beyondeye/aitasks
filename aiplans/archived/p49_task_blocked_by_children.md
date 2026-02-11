# Plan: Fix task-blocked-by-children sorting and improve task selection UI (t49)

## Problem

Two related issues in the aitask system:

1. **Sorting bug**: `aitask_ls.sh` treats parent tasks with `children_to_implement` as "blocked" (`blocked=1`), pushing them to the bottom of sorted results. With the `-v 10` limit in aitask-pick, they may be cut off entirely.
2. **Limited selection UI**: `AskUserQuestion` supports max 4 options, but aitask-pick tries to show all returned tasks as options — only showing 3-4 tasks with no way to see more.

## Fix 1: `aitask_ls.sh` — Separate "has children" from "blocked"

### 1a. Add `has_children` variable

- After line 165 (`children_to_implement_text=""`), add: `has_children=0`
- After line 316 (`children_to_implement_text=""`), add: `has_children=0`

### 1b. Modify `calculate_blocked_status()` (lines 290-298)

**Replace** the children-blocking logic:
```bash
# OLD (lines 290-298):
if [[ "$blocked" -eq 0 && -n "$children_to_implement_text" ]]; then
    blocked=1
    ...
fi
```

**With** informational-only tracking:
```bash
if [[ -n "$children_to_implement_text" ]]; then
    has_children=1
fi
```

This means `blocked` stays `0` for parent tasks with children (they sort normally by priority/effort).

### 1c. Update display logic (lines 377-383)

**Replace:**
```bash
if [ "$blocked" -eq 1 ]; then
    display_status="Blocked (by $d_text)"
else
    display_status="Ready"
fi
```

**With:**
```bash
if [ "$blocked" -eq 1 ]; then
    display_status="Blocked (by $d_text)"
elif [ "$has_children" -eq 1 ]; then
    display_status="Has children"
else
    display_status="Ready"
fi
```

## Fix 2: `.claude/skills/aitask-pick/SKILL.md` — Add pagination

### 2a. Increase fetch limit (line 60)

Change `./aitask_ls.sh -v 10` → `./aitask_ls.sh -v 15` (and same for label-filtered variant on line 65).

### 2b. Rewrite Step 2c (lines 94-98) with pagination

Replace the simple "present as multiple choice" instruction with a pagination loop:
- Show 3 tasks per page + "Show more tasks" as 4th option (if more tasks remain)
- If user selects "Show more", show next 3 tasks
- Loop until user picks a task or all tasks are shown

### 2c. Update references to "Blocked (by children)"

Three locations in SKILL.md:
- Line 68: Change to "Has children"
- Line 253: Change to "Has children"
- Line 527: Change to "Has children"

## Files to modify

1. `/home/ddt/Work/tubetime/aitask_ls.sh` — lines 165, 274-304, 316, 377-383
2. `/home/ddt/Work/tubetime/.claude/skills/aitask-pick/SKILL.md` — lines 60, 65, 68, 94-98, 253, 527

## Verification

```bash
# After Fix 1, run:
./aitask_ls.sh -v 15

# Expected: t29 and t42 appear sorted by priority/effort (not at bottom)
# Expected: Display shows "Has children" instead of "Blocked (by children)"
# Expected: Tasks truly blocked by depends still show "Blocked (by ...)"
```
