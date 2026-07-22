---
Task: t1162_3_work_report_skill_and_wrappers.md
Parent Task: aitasks/t1162_add_manager_facing_work_report_skill_and_board_flow.md
Sibling Tasks: aitasks/t1162/t1162_1_work_report_gatherer_helper.md, aitasks/t1162/t1162_2_work_report_codeagent_operation.md, aitasks/t1162/t1162_4_board_w_work_report_flow.md, aitasks/t1162/t1162_5_work_report_documentation.md
Archived Sibling Plans: aiplans/archived/p1162/p1162_*_*.md
Worktree: aiwork/t1162_3_work_report_skill_and_wrappers
Branch: aitask/t1162_3_work_report_skill_and_wrappers
Base branch: main
---

# Plan: t1162_3 — `/aitask-work-report` skill + agent wrappers + contract guard

## Context

The canonical manager-facing skill. Plain static skill (NO `.j2`, NO goldens,
NO profile stub — same shape as `aitask-changelog` / `aitask-explain`).
Consumes the t1162_1 gatherer (read its archived plan
`aiplans/archived/p1162/p1162_1_*.md` for the final output contract — the
authoritative field order is whatever landed there) and the t1162_2 operation.
Parent design: `aiplans/p1162_add_manager_facing_work_report_skill_and_board_flow.md`
(t1162_3 section). Read `aidocs/framework/skill_authoring_conventions.md`
before authoring.

## Files

1. `.claude/skills/aitask-work-report/SKILL.md` (new, canonical).
2. `.agents/skills/aitask-work-report/SKILL.md` (new, Codex thin wrapper —
   copy `.agents/skills/aitask-changelog/SKILL.md` shape: Source-of-Truth
   pointer + `codex_tool_mapping.md` note).
3. `.opencode/skills/aitask-work-report/SKILL.md` (new — copy
   `.opencode/skills/aitask-changelog/SKILL.md` shape).
4. `.opencode/commands/aitask-work-report.md` (new — copy
   `.opencode/commands/aitask-changelog.md` shape: description frontmatter,
   `@.opencode/skills/opencode_tool_mapping.md`, `Arguments: $ARGUMENTS`,
   `@.claude/skills/aitask-work-report/SKILL.md`).
5. `tests/test_work_report_skill_contract.sh` (new).

## SKILL.md workflow (write these steps; contract sentences marked ⚠ must
appear verbatim-recognizable — the guard test greps for them)

Frontmatter: `name: aitask-work-report`, description = "Draft a
manager-facing work report from selected board columns" (align with the
task's wording).

1. **Parse arguments:** `--columns <csv>`, `--tasks <csv>` (both optional;
   `--tasks` requires `--columns`).
2. **Selection:**
   - No `--columns` → interactive path. ⚠ Column discovery MUST use
     `./.aitask-scripts/aitask_work_report_gather.sh --list-columns` as the
     only discovery source (it emits `unordered` first when the Unsorted
     column currently has tasks). Present columns via `AskUserQuestion`
     `multiSelect: true` (paginate: max 4 options per question — 3 + "Show
     more" as in aitask-pick Step 2c). Then run the gatherer with the chosen
     columns and present the ordered task list for inclusion/exclusion
     (multiSelect, paginated; all tasks pre-announced as included, user
     unchecks to exclude).
   - With `--columns` (+ optional `--tasks`) → run the gatherer once with the
     exact args and SKIP membership prompts (the board already reviewed the
     selection).
3. ⚠ **Fail-closed validation (NON-NEGOTIABLE):** after ANY gatherer run, if
   the output contains one or more `ERROR:` lines or is `NO_TASKS`, STOP —
   do not draft. Present every error line verbatim, then `AskUserQuestion`:
   "Re-select interactively" / "Abort". ⚠ Include the sentence: the skill
   "never drafts from a partial or silently-corrected selection" — the report
   must contain exactly the validated selected tasks.
4. **Horizon (every run):** `AskUserQuestion` — "Today" / "This week" /
   custom label via Other free text. The period labels the report only; ⚠ it
   never changes task membership.
5. **Context gathering per selected task:** read the task file (description,
   frontmatter metadata, `depends`); active plan via
   `./.aitask-scripts/aitask_query_files.sh plan-file <id>`; for parents with
   children: pending list from `children_to_implement`, archived children via
   `./.aitask-scripts/aitask_query_files.sh archived-children <id>`.
   Child-context rules (PINNED): one manager-level line per parent; progress
   phrased as "N of M subtasks complete"; done/archived children counted,
   never listed individually; folded tasks are merged content — never
   separate items; do NOT mine child plans for file/symbol detail.
6. **Draft the report** (first-person, manager-friendly Markdown):
   - Short focus summary (2-3 sentences).
   - Column-grouped priorities in gatherer order: per task — outcome
     (what will be delivered, benefit-level), current status, `t<id>`.
   - **Completion projection** (data-derived; AC amendment approved during
     planning): work items = Σ `remaining_items` from `TASK:` lines. Sum 0 →
     say the selection is effectively complete and omit the projection.
     Otherwise: rate = 30-day `avg_per_day` (mention the 7-day figure when it
     diverges notably); projected ≈ items ÷ rate days, compared against the
     horizon ("≈ N days at the recent pace of X tasks/day — roughly fits /
     exceeds this week"). Label as a projection from historical throughput,
     never a commitment. ⚠ If velocity is 0: state "insufficient completion
     history for a projection" and omit the section — never fabricate a rate.
   - Blockers / manager-asks section (only real blockers from `depends` /
     task content — nothing invented).
   - Include exactly the selected tasks; no invented dates, estimates,
     progress, commitments, dependencies, or blockers; no
     implementation-level file/symbol detail.
7. **Present in-session** for review/editing; iterate on feedback. ⚠ Do NOT
   write a report file (no dated file, no repository file) — the draft lives
   in the session only.
8. **Satisfaction feedback:** execute the Satisfaction Feedback Procedure
   (`.claude/skills/task-workflow/satisfaction-feedback.md`) with
   `skill_name` = `"work-report"`.

## Contract guard test (`tests/test_work_report_skill_contract.sh`)

Scaffold per `tests/lib/asserts.sh`. Assert (grep -F over the canonical
SKILL.md):
- the `--list-columns` discovery requirement,
- the fail-closed `ERROR:`/`NO_TASKS` hard-stop wording,
- "never drafts from a partial or silently-corrected selection",
- the no-report-file rule,
- "insufficient completion history for a projection",
- `skill_name` = `"work-report"`.
Plus: each of the 3 wrapper files exists and contains the canonical path
`.claude/skills/aitask-work-report/SKILL.md`.

Note (wrapped-prose caveat, per project feedback memory): choose marker
strings that cannot be line-wrapped apart (short distinctive phrases), and
run each grep against the actual file before committing the test.

## Verification

- `bash tests/test_work_report_skill_contract.sh` — all PASS.
- `./.aitask-scripts/aitask_skill_verify.sh` — passes (static skill: verifies
  nothing broke in stub surfaces).
- `./.aitask-scripts/aitask_audit_wrappers.sh` — the new skill's helper
  references are whitelisted (t1162_2 added the entries; re-run to confirm
  discovery now that the skill references the helper).
- Dry-run sanity: `./.aitask-scripts/aitask_codeagent.sh --dry-run invoke
  work-report --columns now --tasks 1` shows the slash command.

## Step 9 reference

Post-implementation: merge/cleanup + archival per task-workflow Step 9.
