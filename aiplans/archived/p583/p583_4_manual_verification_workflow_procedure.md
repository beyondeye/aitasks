---
Task: t583_4_manual_verification_workflow_procedure.md
Parent Task: aitasks/t583_manual_verification_module_for_task_workflow.md
Sibling Tasks: aitasks/t583/t583_7_plan_time_generation_integration.md, aitasks/t583/t583_8_documentation_website_and_skill.md, aitasks/t583/t583_9_meta_dogfood_aggregate_verification.md
Archived Sibling Plans: aiplans/archived/p583/p583_1_verification_parser_python_helper.md, aiplans/archived/p583/p583_2_verifies_frontmatter_field_three_layer.md, aiplans/archived/p583/p583_3_verification_followup_helper_script.md, aiplans/archived/p583/p583_5_archival_gate_and_carryover.md, aiplans/archived/p583/p583_6_issue_type_manual_verification_and_unit_tests.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-19 16:20
---

# Plan: t583_4 — Manual-Verification Workflow Procedure (verified)

## Context

Siblings t583_1 (parser), t583_3 (follow-up helper), t583_5 (archival gate + carry-over), and t583_6 (issue_type registration + unit tests) are already archived. All the infrastructure this task depends on exists on `main` — verified against the actual scripts. This task writes the **procedure file** that `/aitask-pick` dispatches to when a picked task has `issue_type: manual_verification`, plus the SKILL.md routing edit that calls it.

Per `feedback_agent_specific_procedures`: the procedure lives in its own file with conditional referencing from `SKILL.md`, not inlined.

## Verified dependencies

- `.aitask-scripts/aitask_verification_parse.sh` — subcommands `parse`, `summary`, `set <idx> pass|fail|skip|defer [--note …]`, `seed --items`, `terminal_only`. Confirmed.
- `.aitask-scripts/aitask_verification_followup.sh` — `--from <id> --item <idx> [--origin <feature_id>]`. Emits `FOLLOWUP_CREATED:<new_id>:<path>` on success, `ORIGIN_AMBIGUOUS:<csv>` (exit 2) when ambiguous, `ERROR:<msg>` (exit 1) on failure. **Already calls `aitask_verification_parse.sh set … fail` internally** — no follow-up `set` call needed from the procedure.
- `.aitask-scripts/aitask_archive.sh --with-deferred-carryover <task_id>` — present, creates carry-over task with remaining deferred items.
- `aitasks/metadata/task_types.txt` includes `manual_verification`.
- `.claude/skills/task-workflow/manual-verification.md` does **not** exist yet.

## Files to create/modify

**New:** `.claude/skills/task-workflow/manual-verification.md`

**Modify:** `.claude/skills/task-workflow/SKILL.md`
- Step 3 — add **Check 3** after Check 2.
- Procedures registry at the bottom (~L477–493) — add alphabetical entry between `lock-release.md` and `model-self-detection.md`.

## `manual-verification.md` structure

Mirror the input/structure conventions of `satisfaction-feedback.md` (typed input table, clear sections).

1. **Input** block — `task_file`, `task_id`, `task_name`, `active_profile` (from SKILL.md handoff).

2. **Pre-loop check:**
   - Run `aitask_verification_parse.sh summary <task_file>`; parse `TOTAL:N`.
   - If `TOTAL:0`: `AskUserQuestion` "Task has no `## Verification Checklist` items — seed from plan's `## Verification` section, or abort?" Options: "Seed from plan" / "Abort".
     - Seed: locate the plan (prefer `aiplans/p<parent>/p<parent>_<child>_*.md`, fall back to archived `aiplans/archived/p<parent>/…`); extract the bullet list under `## Verification`; write to a tmp file; call `aitask_verification_parse.sh seed <task_file> --items <tmp>`; re-run `summary`.
     - Abort: execute the **Task Abort Procedure** and end.

3. **Main loop** — for each `pending` or `defer` item (enumerate via `aitask_verification_parse.sh parse <task_file>`, which emits `ITEM:<idx>:<state>:<line>:<text>`):
   - Render the item text to the user as context.
   - `AskUserQuestion` header "Verify", options: **Pass** / **Fail** / **Skip (with reason)** / **Defer**.
   - **Pass** → `aitask_verification_parse.sh set <task_file> <idx> pass`.
   - **Fail** → `aitask_verification_followup.sh --from <task_id> --item <idx>`.
     - On `ORIGIN_AMBIGUOUS:<csv>`: `AskUserQuestion` listing one option per candidate task from the csv; re-invoke with `--origin <chosen>`.
     - On `FOLLOWUP_CREATED:<new_id>:<path>`: announce "Created follow-up bug task t<new_id>". No extra `set` call (helper already marked the item as fail).
     - On `ERROR:<msg>`: show the error and re-prompt the same item.
   - **Skip** → `AskUserQuestion` for free-text reason (use "Other"); then `set <task_file> <idx> skip --note "<reason>"`.
   - **Defer** → `set <task_file> <idx> defer`.

4. **Post-loop checkpoint:**
   - Re-run `summary`.
   - If `DEFER > 0`: `AskUserQuestion` "Some items were deferred. Archive with carry-over, or stop without archiving?"
     - "Archive with carry-over" → set an internal flag so Step 9 calls `aitask_archive.sh --with-deferred-carryover <task_id>` instead of the default archive.
     - "Stop without archiving" → end the workflow (task stays Implementing; lock remains; user can re-pick later).
   - Else (all terminal) → proceed to normal Step 9 archival.

5. **Commit verification state** before handing off to Step 9:
   ```
   ./ait git add aitasks/
   ./ait git commit -m "ait: Record verification state for t<task_id>"
   ```

6. **Hand-off** — return to SKILL.md Step 9 (Post-Implementation). The procedure replaces Steps 6–8; Steps 4 (ownership) and 5 (worktree) still run before dispatch.

## `SKILL.md` Step 3 edit

Insert after Check 2, before the "If neither check triggers…" sentence:

```markdown
**Check 3 - Manual-verification task:**
- Read the task file's frontmatter `issue_type` field
- If `issue_type` is `manual_verification`:
  - Execute the **Manual Verification Procedure** (see `manual-verification.md`)
  - Skip Steps 6-8; proceed to Step 9 after the procedure returns
  - Steps 4 (ownership) and 5 (worktree) still run before dispatch
```

Keep the existing "If neither check triggers, proceed to Step 4 as normal." sentence — it still applies when Check 3 also doesn't trigger.

## Procedures registry edit

Add alphabetically between `lock-release.md` and `model-self-detection.md`:

```markdown
- **Manual Verification Procedure** (`manual-verification.md`) — Interactive checklist runner for `issue_type: manual_verification` tasks. Referenced from Step 3 (Check 3).
```

## Out of scope

- Gemini/Codex/OpenCode mirror — flagged as follow-up per CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS". Claude Code is the source of truth.
- `aitask-qa` integration — this module is live human checks only.
- `verifies:` frontmatter enumeration beyond what `aitask_verification_followup.sh` already handles via `ORIGIN_AMBIGUOUS`.
- Website docs page and skill-docs mention — t583_8 covers these.

## Verification (for this task itself)

Mostly tested end-to-end in t583_9 (meta-dogfood). For this task, at minimum:
- Read the new `manual-verification.md` against `planning.md`/`satisfaction-feedback.md` conventions (format, input block, AskUserQuestion phrasing).
- Read the updated `SKILL.md` Step 3 to confirm Check 3 sits cleanly after Check 2 and the registry entry is alphabetical.
- Dry-run walkthrough against a hypothetical manual-verification task: confirm each branch (Pass / Fail / Skip / Defer) maps to the right script call.

## Commit

Per CLAUDE.md: `documentation: Add manual-verification workflow procedure (t583_4)` (procedure file + SKILL.md edit are both documentation-adjacent).

## Step 9 reminder

Post-implementation: user review → commit → archive via `aitask_archive.sh 583_4` → push.

## Final Implementation Notes

- **Actual work done:**
  - Created `.claude/skills/task-workflow/manual-verification.md` — the 5-section procedure (Pre-loop check, Main loop, Post-loop checkpoint, Commit, Hand-off) mirroring the input-block + stepwise-script-invocation conventions of `satisfaction-feedback.md` and `task-abort.md`.
  - Inserted **Check 3** into `SKILL.md` Step 3 after Check 2, with the explicit caveat that Steps 4 (ownership) and 5 (worktree) still run before dispatch (unlike Check 1/Check 2 which skip Step 4).
  - Rewrote the trailing "These checks should NOT set status to Implementing" note to clarify it applies only to Check 1/Check 2 — Check 3 does run Step 4 normally.
  - Added the "Manual Verification Procedure" entry to the Procedures registry (near the other Step-3-related entries — the registry is ordered by workflow step, not alphabetically, despite what the verification agent reported).
- **Deviations from plan:** None substantive. The plan was verified in full before implementation (verify-path) and no gaps surfaced. Minor wording: the Check 3 block uses "Skip Steps 6-8" (not 4-8) to make the Steps-4-and-5-still-run caveat unambiguous.
- **Issues encountered:** None. All dependencies (`aitask_verification_parse.sh`, `aitask_verification_followup.sh`, `aitask_archive.sh --with-deferred-carryover`, `manual_verification` task type) were already in place on `main` from t583_1/3/5/6.
- **Key decisions:**
  - "Stop without archiving" keeps the task `Implementing` with the lock held, rather than reverting to `Ready`. Rationale: only the original picker should be able to resume an in-flight verification; reverting would let another user start over and lose the deferred-item annotations.
  - The procedure commits its own "Record verification state" commit before Step 9, separate from the archival commit. This keeps the state record durable even if the user chooses "Stop without archiving" later in the loop (the deferred state is already on disk and committed).
  - Seeding from the plan's `## Verification` H2 is offered as a fallback when the task has `TOTAL:0` checklist items, rather than forcing the user to re-edit the task file by hand.
- **Notes for sibling tasks:**
  - **t583_7 (plan-time generation):** Should emit a `## Verification Checklist` block directly in new manual-verification tasks — this procedure's seed fallback exists for retrofitting older tasks, not as the primary path.
  - **t583_8 (website/skill docs):** The user-facing docs should describe the full branch set (Pass / Fail / Skip / Defer) and the two post-loop outcomes (archive vs archive-with-carry-over vs stop). The skill docs for `/aitask-pick` also need a short "Manual-verification tasks" section pointing at this procedure.
  - **t583_9 (meta-dogfood):** Use this procedure to verify the whole module end-to-end. The test task should include one item of each terminal fate to exercise all four branches.
  - **Mirror follow-ups:** Per CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS", this task touched the Claude Code source of truth only. Separate follow-up tasks should port `manual-verification.md` and the SKILL.md edit to `.gemini/skills/task-workflow/`, `.agents/skills/task-workflow/`, and `.opencode/skills/task-workflow/`.
