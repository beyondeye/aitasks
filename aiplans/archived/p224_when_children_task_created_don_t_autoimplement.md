---
Task: t224_when_children_task_created_don_t_autoimplement.md
---

# Plan: t224 — Don't auto-implement when child tasks are created

## Context

When a parent task is broken into child tasks during planning (Step 6.1 of task-workflow/SKILL.md), the workflow currently creates child task files and immediately restarts with `/aitask-pick <parent>_1`. With the "fast" profile, this auto-confirms and jumps straight to implementation. This is problematic because:

1. The context is already full from parent planning
2. Plans for children 2, 3, etc. are never written until each is individually picked
3. Subsequent children have no plan files when they are eventually picked

## Changes

### Change 1: Write all child plans before proceeding (task-workflow/SKILL.md, lines 223-224)

**File:** `.claude/skills/task-workflow/SKILL.md`

**Replace lines 223-224:**
```
    - After creation, ask which child to start with
    - Restart the pick process with `/aitask-pick <parent>_1`
```

**With:**
```
    - **Write implementation plans for ALL child tasks** before proceeding:
      - For each child task created, write a plan file to `aiplans/p<parent>/p<parent>_<child>_<name>.md`
      - Use the child plan file naming and metadata header conventions from the **Save Plan to External File** section below
      - Each plan should leverage the codebase exploration already done during the parent planning phase
      - Plans do not need to go through `EnterPlanMode`/`ExitPlanMode` — write them directly as files since the overall parent plan was already approved
      - Commit all child task files and plan files together:
        ```bash
        mkdir -p aiplans/p<parent>
        git add aitasks/t<parent>/ aiplans/p<parent>/
        git commit -m "ait: Create t<parent> child tasks and plans"
        ```
    - **Child task checkpoint (ALWAYS interactive — ignores `post_plan_action` profile setting):**
      Use `AskUserQuestion`:
      - Question: "Created <N> child tasks with implementation plans. How would you like to proceed?"
      - Header: "Children"
      - Options:
        - "Start first child" (description: "Continue to pick and implement the first child task")
        - "Stop here" (description: "All child tasks and plans are written — end this session and pick children later in fresh contexts")
      - **If "Start first child":** Restart the pick process with `/aitask-pick <parent>_1`
      - **If "Stop here":** End the workflow. Display: "Child tasks and plans written to `aiplans/p<parent>/`. Pick individual children later with `/aitask-pick <parent>_<N>`."
```

### Change 2: Add `plan_preference_child` profile setting (task-workflow/SKILL.md, Step 6.0)

**File:** `.claude/skills/task-workflow/SKILL.md`

At Step 6.0 (line 171), the profile check for `plan_preference` should also check `plan_preference_child` when the current task is a child task.

**Replace lines 171-175:**
```
**Profile check:** If the active profile has `plan_preference` set:
- If `"use_current"`: Skip to the **Checkpoint** at the end of Step 6. Display: "Profile '\<name\>': using existing plan"
- If `"verify"`: Enter verification mode (step 6.1). Display: "Profile '\<name\>': verifying existing plan"
- If `"create_new"`: Proceed with step 6.1 as normal. Display: "Profile '\<name\>': creating plan from scratch"
- Skip the AskUserQuestion below
```

**With:**
```
**Profile check:** If the active profile has `plan_preference` set (or `plan_preference_child` for child tasks — `plan_preference_child` takes priority when the current task is a child task):
- If `"use_current"`: Skip to the **Checkpoint** at the end of Step 6. Display: "Profile '\<name\>': using existing plan"
- If `"verify"`: Enter verification mode (step 6.1). Display: "Profile '\<name\>': verifying existing plan"
- If `"create_new"`: Proceed with step 6.1 as normal. Display: "Profile '\<name\>': creating plan from scratch"
- Skip the AskUserQuestion below
```

### Change 3: Add `plan_preference_child` to Profile Schema Reference table (task-workflow/SKILL.md, line 617)

**File:** `.claude/skills/task-workflow/SKILL.md`

**After the `plan_preference` row (line 617), add:**
```
| `plan_preference_child` | string | no | Same values as `plan_preference`; overrides `plan_preference` for child tasks. Defaults to `plan_preference` if omitted | Step 6.0 |
```

### Change 4: Update fast.yaml profile

**File:** `aitasks/metadata/profiles/fast.yaml`

**Add line:**
```yaml
plan_preference_child: verify
```

This means the fast profile will auto-accept parent plans (`plan_preference: use_current`) but will verify pre-written child plans (`plan_preference_child: verify`), giving the user a chance to review/modify them.

## Summary of files to modify

| File | What changes |
|------|-------------|
| `.claude/skills/task-workflow/SKILL.md` | Lines 171-175 (plan_preference child override), lines 223-224 (write all child plans + checkpoint), line 617 (schema table) |
| `aitasks/metadata/profiles/fast.yaml` | Add `plan_preference_child: verify` |

## Verification

1. Read the modified SKILL.md and verify instructions are clear
2. Verify `plan_preference_child` is documented in schema table and referenced in Step 6.0
3. Verify fast.yaml has the new setting
4. Grep for any other references to the old "After creation, ask which child" text

## Final Implementation Notes
- **Actual work done:** All 4 changes implemented as planned — no deviations
- **Deviations from plan:** None. The `plan_preference_child` feature was added during planning after user feedback (not in the initial plan draft)
- **Issues encountered:** None
- **Key decisions:** The `plan_preference_child` setting defaults to `plan_preference` when omitted (not to any hardcoded value), keeping the profile system flexible
