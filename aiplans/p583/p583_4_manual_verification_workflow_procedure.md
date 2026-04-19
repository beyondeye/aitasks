---
Task: t583_4_manual_verification_workflow_procedure.md
Parent Task: aitasks/t583_manual_verification_module_for_task_workflow.md
Sibling Tasks: aitasks/t583/t583_1_*.md .. t583_9_*.md
Archived Sibling Plans: aiplans/archived/p583/p583_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t583_4 — Manual-Verification Workflow Procedure

## Context

Core procedure file that `/aitask-pick` dispatches to when `issue_type: manual_verification`. Depends on t583_1 (parser) and t583_3 (follow-up helper).

Per `feedback_agent_specific_procedures`, the procedure lives in its own file, referenced conditionally from `SKILL.md` — not inlined.

## Files to create/modify

**New:**
- `.claude/skills/task-workflow/manual-verification.md`

**Modify:**
- `.claude/skills/task-workflow/SKILL.md` — Step 3, insert Check 3 after Check 2.

## `manual-verification.md` structure

1. **Input context:** `task_file`, `task_id`, `task_name`, `active_profile` from SKILL.md handoff.
2. **Pre-loop check:** `aitask_verification_parse.sh summary`. If `TOTAL:0`, offer to seed from plan's `## Verification` H2 or abort.
3. **Main loop** (for each pending/defer item):
   - Render item text; `AskUserQuestion` with options Pass / Fail / Skip (with reason) / Defer.
   - Pass → `aitask_verification_parse.sh set <i> pass`.
   - Fail → `aitask_verification_followup.sh --from <id> --item <i>`; handle `ORIGIN_AMBIGUOUS` by asking user to pick.
   - Skip → reason prompt; `set <i> skip --note "<reason>"`.
   - Defer → `set <i> defer`.
4. **Post-loop checkpoint:** if any defer, offer "Archive with carry-over" (calls `aitask_archive.sh --with-deferred-carryover`) vs "Stop without archiving".
5. **Commit state:** `./ait git commit -m "ait: Record verification state for t<id>"`.
6. **Hand off to Step 9.**

## `SKILL.md` Step 3 edit

After existing Check 2, add:

```markdown
**Check 3 - Manual-verification task:**
- Read the task file's frontmatter `issue_type` field
- If `issue_type` is `manual_verification`:
  - Execute the **Manual Verification Procedure** (see `manual-verification.md`)
  - Skip Steps 6-8; proceed to Step 9 after the procedure returns
```

Steps 4 (ownership) and 5 (worktree) still run before the dispatch.

## Reference precedent

- `planning.md`, `task-abort.md`, `satisfaction-feedback.md` — procedure file conventions.
- `SKILL.md` Check 1/Check 2 — pattern for conditional routing in Step 3.

## Verification

- Pick a test manual-verification task with 4 items (one per terminal target); exercise each branch.
- Confirm state persists across re-picks.
- Confirm carry-over prompt appears when Defer chosen; direct archival when all terminal.
- End-to-end validation in t583_9 (meta-dogfood).

## Final Implementation Notes

_To be filled in during implementation._
