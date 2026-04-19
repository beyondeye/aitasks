---
priority: medium
effort: medium
depends: [t583_1, t583_3]
issue_type: documentation
status: Implementing
labels: [framework, skill, task_workflow, verification]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-19 08:29
updated_at: 2026-04-19 16:08
---

## Context

Fourth child of t583. This is the **core workflow procedure** — the procedure file that `/aitask-pick` dispatches to when a picked task has `issue_type: manual_verification`. Depends on t583_1 (parser) and t583_3 (follow-up helper); uses them to drive the interactive loop.

Per CLAUDE.md's `feedback_agent_specific_procedures` guideline, the procedure lives in its own file (`.claude/skills/task-workflow/manual-verification.md`) with conditional referencing from `SKILL.md`, not inlined.

## Key Files to Modify

- `.claude/skills/task-workflow/manual-verification.md` — **new file**, the procedure.
- `.claude/skills/task-workflow/SKILL.md` — add "Check 3 — Manual-verification task" to Step 3, before proceeding to Step 4.

## Reference Files for Patterns

- `.claude/skills/task-workflow/planning.md` — Textual style/format for procedure files (section headings, `AskUserQuestion` invocations).
- `.claude/skills/task-workflow/task-abort.md` — another shared procedure invoked from SKILL.md with conditional referencing.
- `.claude/skills/task-workflow/satisfaction-feedback.md` — another example of a procedure with internal state and multiple `AskUserQuestion` prompts.
- `.claude/skills/task-workflow/SKILL.md` Step 3 (existing Check 1 and Check 2) — the pattern we extend.

## Implementation Plan

### `manual-verification.md` contents

1. **Input context** (from SKILL.md handoff): `task_file`, `task_id`, `task_name`, `active_profile`.

2. **Pre-loop check:**
   - `summary = $(./.aitask-scripts/aitask_verification_parse.sh summary <task_file>)`.
   - Parse `TOTAL:N`. If `TOTAL:0`, warn: "Task has no `## Verification Checklist` items." Use `AskUserQuestion` with options: "Seed from plan's Verification section" / "Abort". If "Seed", search the archived or pending plan for a `## Verification` H2, extract its bullet list, and call `aitask_verification_parse.sh seed <task_file> --items <tmp>`. Re-summary.

3. **Main loop** — for each `pending` or `defer` item (use `parse` subcommand to enumerate):
   - Render the item text to the user as context.
   - `AskUserQuestion` with header "Verify":
     - Options: "Pass" / "Fail" / "Skip (with reason)" / "Defer"
   - **Pass:** `aitask_verification_parse.sh set <file> <index> pass`
   - **Fail:** call `aitask_verification_followup.sh --from <task_id> --item <index>`.
     - If output is `ORIGIN_AMBIGUOUS:<csv>`, show an `AskUserQuestion` with one option per verified task; re-invoke the helper with `--origin <chosen>`.
     - Parse `FOLLOWUP_CREATED:<new_id>:<path>`; announce "Created follow-up bug task t<new_id>".
     - Helper already updated the item state; no extra `set` call needed.
   - **Skip:** `AskUserQuestion` for reason (free-text "Other" option); `set <file> <index> skip --note "<reason>"`.
   - **Defer:** `set <file> <index> defer`.

4. **Post-loop checkpoint:**
   - Re-summary.
   - If `DEFER > 0`: `AskUserQuestion` — "Some items were deferred. Archive with carry-over (creates a new manual-verification task with only the deferred items), or stop without archiving?"
     - "Archive with carry-over" → proceed to Step 9 with `aitask_archive.sh --with-deferred-carryover <task_id>`.
     - "Stop without archiving" → end workflow; user can re-pick later.
   - Else (all terminal): proceed to Step 9 standard archival.

5. **Commit verification state** (once, before archival):
   ```
   ./ait git add aitasks/  # task file
   ./ait git commit -m "ait: Record verification state for t<task_id>"
   ```

6. **Hand-off** to Step 9 (Post-Implementation) in SKILL.md — archival + push.

### `SKILL.md` Step 3 edit

After Check 2 (orphaned parent), add Check 3:

```markdown
**Check 3 - Manual-verification task:**
- Read the task file's frontmatter `issue_type` field
- If `issue_type` is `manual_verification`:
  - Execute the **Manual Verification Procedure** (see `manual-verification.md`)
  - When the procedure returns, skip Steps 6-8 entirely; proceed to Step 9 (Post-Implementation) for archival
  - The procedure handles its own ownership-guard (Step 4 already ran) and checklist state persistence
```

Steps 4 (ownership) and 5 (worktree) still run before dispatching to the procedure — verification is work that should be owned and locked.

## Verification Steps

- Create a test manual-verification task with 4 items (one of each terminal state target).
- Run `/aitask-pick <id>`; confirm Step 3 routes to manual-verification.md.
- Exercise each branch: Pass, Fail (→ follow-up), Skip (→ reason prompt), Defer.
- Post-loop: verify carry-over prompt appears when Defer is chosen; verify direct archival when all terminal.
- Inspect the task file to confirm state annotations are correct.

## Step 9 reminder

Commit: `documentation: Add manual-verification workflow procedure (t583_4)` (procedure file is documentation-adjacent; SKILL.md edit is also doc).
