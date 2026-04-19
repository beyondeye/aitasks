---
Task: t583_7_plan_time_generation_integration.md
Parent Task: aitasks/t583_manual_verification_module_for_task_workflow.md
Sibling Tasks: aitasks/t583/t583_1_*.md .. t583_9_*.md
Archived Sibling Plans: aiplans/archived/p583/p583_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t583_7 — Plan-time Generation Integration

## Context

The integration side the user asked about during plan review: make `/aitask-pick` (during child-task creation AND single-task ExitPlanMode) and `/aitask-explore` proactively offer to create manual-verification tasks.

Depends on t583_2 (`verifies:` field) and t583_6 (`issue_type: manual_verification` registered).

## Files to create/modify

**New:**
- `.aitask-scripts/aitask_create_manual_verification.sh` (seeder helper)

**Modify:**
- `.claude/skills/task-workflow/planning.md` (two new sub-procedures)
- `.claude/skills/aitask-explore/SKILL.md` (create-task phase)
- 5 whitelist touchpoints for the new helper (Codex: skip)

## Seeder helper spec

```
aitask_create_manual_verification.sh \
  --name <task_name> \
  --verifies <csv_of_ids> \
  [--parent <parent_num>] [--related <task_id>] \
  --items <items_file>
```

- `--parent` → aggregate-sibling mode (child of parent).
- `--related` → follow-up mode (standalone; uses `--deps <related>` under the hood since `aitask_create.sh` lacks `--related`).
- Calls `aitask_create.sh --batch --type manual_verification --priority medium --effort medium --labels verification,manual [--parent ...] --verifies ... --desc-file <tmp> --commit`.
- Runs `aitask_verification_parse.sh seed <new_file> --items <items_file>` to populate the checklist.
- Outputs `MANUAL_VERIFICATION_CREATED:<task_id>:<path>`.

## `planning.md` edits

**Edit 1 — after child-task creation loop, before checkpoint (~line 170):**
Insert `### Manual Verification Sibling (post-child-creation)`:
- `AskUserQuestion` with options: No / Yes aggregate all / Yes let me choose.
- On "let me choose" → multiSelect over children.
- Shell out to seeder with `--parent <parent_num>`.
- New sibling becomes next-numbered child.

**Edit 2 — after `ExitPlanMode` on single-task path (end of §6.1):**
Insert `### Manual Verification Follow-up`:
- `AskUserQuestion`: No / Yes create follow-up.
- On Yes → seeder with `--related <this_task_id> --verifies <this_task_id>`.

## `aitask-explore/SKILL.md` edit

In the final create-task phase, add the single-task follow-up question (Edit 2 variant). Seed is a stub item.

## Whitelist

All 5 touchpoints for `aitask_create_manual_verification.sh`. Codex: skip.

## Verification

- Aggregate path: parent with 2 children → prompt appears → "Yes aggregate all" → new sibling with correct `verifies:` and checklist stubs.
- Single-task path: single-task plan → prompt appears → "Yes" → standalone task with `verifies:[this]`.
- Explore path: new task creation → prompt → "Yes" → follow-up task.
- Opt-out: all paths answer "No" → no extra task created.

## Final Implementation Notes

_To be filled in during implementation._
