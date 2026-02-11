# Plan: Fix parent task incorrectly set to Blocked when creating children (t45)

## Root Cause

When the aitask-pick skill decomposes a parent task into child tasks (Step 5.3), the AI agent changes the parent status to "Blocked". But `aitask_ls.sh` already computes "Blocked (by children)" dynamically at display time. The stored "Blocked" status means the task gets incorrectly filtered.

The real issue: Step 3.5 sets the parent to "Implementing" before planning begins. If during planning the task is decomposed into children, the parent should be **reverted back to "Ready"** — only the child being worked on should be set to "Implementing".

## Fix

### Step 1: Update SKILL.md — Add revert instruction to Step 5.3

**File:** `.claude/skills/aitask-pick/SKILL.md` (around line 245-250)

In the "If creating child tasks" section, add instructions to revert the parent status back to "Ready":

```markdown
- **If creating child tasks:**
  - Ask how many subtasks and get brief descriptions for each
  - Use `aitask_create.sh --batch --parent <N>` to create each child
  - **IMPORTANT:** Each child task file MUST include detailed context (see Child Task Documentation Requirements below)
  - **IMPORTANT:** Revert the parent task status back to "Ready" since only the child task being worked on should be "Implementing":
    ```bash
    ./aitask_update.sh --batch <parent_num> --status Ready --assigned-to ""
    ```
    The `aitask_ls.sh` script will automatically display the parent as "Blocked (by children)" because it has pending `children_to_implement`.
  - After creation, ask which child to start with
  - Restart the pick process with `/aitask-pick <parent>_1`
```

### Step 2: Fix t40's incorrect status

**File:** `aitasks/t40_time_balance_bugs.md`

Change `status: Blocked` to `status: Ready` (line 6), and clear `assigned_to` if present.

## Verification

1. Read the updated SKILL.md to confirm the new instruction is in place
2. Read t40 task file to confirm status is corrected to "Ready"
3. Run `./aitask_ls.sh -v 10` to confirm t40 shows as "Blocked (by children)" in the display (computed dynamically, not from stored status)
