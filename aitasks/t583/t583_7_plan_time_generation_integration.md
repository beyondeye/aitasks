---
priority: medium
effort: medium
depends: [t583_2, t583_6]
issue_type: feature
status: Ready
labels: [framework, skill, task_workflow, verification]
created_at: 2026-04-19 08:29
updated_at: 2026-04-19 08:29
---

## Context

Seventh child of t583. This is the **planning-flow integration** that the user specifically asked about during plan review: how to make `/aitask-pick` and `/aitask-explore` proactively offer to create manual-verification tasks (aggregate sibling for parent tasks, follow-up for single-task plans) during the planning phase.

Depends on t583_2 (`verifies:` field plumbing) and t583_6 (`manual_verification` issue type registered). Uses a new seeder helper that wraps `aitask_create.sh` with the correct defaults.

## Key Files to Modify

- `.aitask-scripts/aitask_create_manual_verification.sh` — **new seeder helper**.
- `.claude/skills/task-workflow/planning.md` — add two new sub-procedures (aggregate-sibling branch; single-task follow-up branch).
- `.claude/skills/aitask-explore/SKILL.md` — add the single-task follow-up question in the create-task phase.
- Whitelist updates (5 touchpoints) for the new helper.

## Reference Files for Patterns

- `.aitask-scripts/aitask_create.sh --batch` — backend.
- `.aitask-scripts/aitask_verification_parse.sh seed` (from t583_1) — for injecting the `## Verification Checklist` H2.
- `.claude/skills/task-workflow/planning.md` existing Complexity Assessment section (~line 140-180) — where the new sub-procedures slot in.
- `.claude/skills/aitask-explore/SKILL.md` — the create-task phase.

## Implementation Plan

### 1. `aitask_create_manual_verification.sh`

Usage:
```
aitask_create_manual_verification.sh \
  --name <task_name> \
  --verifies <csv_of_ids> \
  [--parent <parent_num>] [--related <task_id>] \
  --items <items_file>
```

Behavior:
- One of `--parent` or `--related` must be set. `--parent` = aggregate-sibling mode (creates a child of that parent). `--related` = follow-up mode (creates a standalone task that references the source).
- Delegates creation:
  ```
  aitask_create.sh --batch \
    --type manual_verification \
    --priority medium --effort medium \
    --labels verification,manual \
    --name <name> \
    [--parent <parent_num>] \
    --verifies <csv> \
    --desc-file <tmp_desc> \
    --commit
  ```
  The description template includes a `## Verification Checklist` H2 (empty) plus a preamble explaining how to run the module.
- After creation, read the new task's ID from `aitask_create.sh` output, then run:
  `./.aitask-scripts/aitask_verification_parse.sh seed <new_file> --items <items_file>`
  to populate the checklist.
- Output: `MANUAL_VERIFICATION_CREATED:<task_id>:<path>`.

If `--related` is used and `aitask_create.sh` does not yet support that flag (it doesn't — see t583_3 which faced the same gap), fall back to using `--deps <related_id>` semantically and append a note in the description body (`**Related to:** t<related_id>`).

### 2. `planning.md` edits

**Edit 1: After child-task creation loop, before the checkpoint (~line 170):**

Insert a new `### Manual Verification Sibling (post-child-creation)` section:
```markdown
### Manual Verification Sibling (post-child-creation)

After creating the child tasks, use `AskUserQuestion`:
- Question: "Do any of these children produce behavior that needs manual verification (TUI flows, live agent launches, on-disk artifact inspection, multi-screen navigation)?"
- Header: "Manual verify"
- Options:
  - "No, not needed"
  - "Yes, add aggregate sibling covering all children (Recommended for TUI/UX-heavy work)"
  - "Yes, but let me choose which children it verifies"

**If "Yes, all children" or "Yes, let me choose":**
- If "let me choose", use a multiSelect `AskUserQuestion` with one option per child to narrow the `verifies:` list.
- Generate a `<tmp_checklist>` file: one bullet per child's plan "Verification" section entry if present, else a single stub `TODO: define verification for t<child_id>`.
- Run:
  ```bash
  ./.aitask-scripts/aitask_create_manual_verification.sh \
    --parent <parent_num> \
    --name manual_verification_<parent_slug> \
    --verifies <selected_child_ids_csv> \
    --items <tmp_checklist>
  ```
- The new sibling becomes the last child of the parent (e.g., t<parent>_<last+1>).
```

**Edit 2: After `ExitPlanMode` for single-task plans (at the end of §6.1):**

Insert `### Manual Verification Follow-up (post-ExitPlanMode, single-task path)`:
```markdown
If the Complexity Assessment returned "No, implement as single task", use `AskUserQuestion`:
- Question: "Does this task need a manual verification follow-up (for behavior that only a human can validate)?"
- Header: "Manual verify"
- Options:
  - "No"
  - "Yes, create follow-up task (picked after this task archives)"

**If "Yes":**
- Extract the plan's `## Verification` section bullets (if any) into `<tmp_checklist>`; else a stub.
- Run:
  ```bash
  ./.aitask-scripts/aitask_create_manual_verification.sh \
    --related <this_task_id> \
    --name manual_verification_<this_task_slug>_followup \
    --verifies <this_task_id> \
    --items <tmp_checklist>
  ```
- This creates a standalone (not child) manual-verification task that can be picked after the current task is archived.
```

### 3. `aitask-explore/SKILL.md` edit

In the final "Create task" phase, after the task draft is ready but before the batch-create step, add the same single-task follow-up question from Edit 2 above. Explore-created tasks typically have no plan yet, so the checklist seed is a single stub item — the user fills it in later when picking the follow-up.

### 4. Whitelist updates

Five entries for `aitask_create_manual_verification.sh` across runtime + seed configs (Claude, Gemini, OpenCode). Codex: skip.

## Verification Steps

- **Aggregate-sibling path:** `/aitask-pick` a parent task; create 2 children in plan mode; answer "Yes, aggregate sibling" at the new prompt; confirm a new sibling is created with `issue_type: manual_verification`, `verifies: [child1, child2]`, `## Verification Checklist` containing stubs.
- **Single-task follow-up path:** plan a single-task change; at the new prompt, answer "Yes, create follow-up"; confirm a standalone task is created with `verifies: [this_task]`.
- **Explore path:** `/aitask-explore` to create a new task; at the new prompt, answer "Yes"; confirm follow-up task is created.
- **Opt-out:** in all three paths, answering "No" should complete the usual flow without creating any extra task.

## Step 9 reminder

Commit: `feature: Add plan-time manual-verification task generation (t583_7)`.
