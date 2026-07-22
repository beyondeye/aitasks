---
priority: medium
effort: medium
depends: [t1162_2]
issue_type: feature
status: Ready
labels: [skills, reporting]
gates: [risk_evaluated]
anchor: 1162
created_at: 2026-07-22 10:45
updated_at: 2026-07-22 10:45
---

## Context

Third child of t1162. Adds the canonical `/aitask-work-report` skill (plain static skill — no `.j2`, no goldens, like `aitask-changelog`/`aitask-explain`), its cross-agent wrappers, and a contract guard test. Consumes the t1162_1 gatherer (`aitask_work_report_gather.sh`) and the t1162_2 operation registration. Parent plan: `aiplans/p1162_add_manager_facing_work_report_skill_and_board_flow.md` (t1162_3 section).

## Key Files to Create

- `.claude/skills/aitask-work-report/SKILL.md` — canonical skill (workflow below).
- Wrappers (copy `aitask-changelog` wrapper shapes): `.agents/skills/aitask-work-report/SKILL.md`, `.opencode/skills/aitask-work-report/SKILL.md`, `.opencode/commands/aitask-work-report.md`.
- `tests/test_work_report_skill_contract.sh` — contract guard test.

## Skill workflow (PINNED contracts)

1. Parse args: `--columns <csv>`, `--tasks <csv>` optional.
2. No args → interactive: column discovery ONLY via `./.aitask-scripts/aitask_work_report_gather.sh --list-columns` (emits `unordered` first when Unsorted has tasks — the dynamic column is always offered); AskUserQuestion multiSelect for columns; then run the gatherer with chosen columns and present the ordered task list for exclusions (multiSelect, paginate past the 4-option limit). With explicit `--tasks` → validate via gatherer and SKIP membership prompts (board already reviewed the selection).
3. Fail-closed gatherer parsing (PINNED): after ANY gatherer run, one or more `ERROR:` lines or `NO_TASKS` → the skill MUST stop before drafting — present every error verbatim and offer via AskUserQuestion: re-select interactively / abort. It never drafts from a partial or silently-corrected selection — the report must contain exactly the validated selected tasks.
4. Horizon question on EVERY run: Today / This week / custom label (via Other free text). Labels the report only — never changes membership.
5. Per selected task: read task file (description, metadata, depends), active plan (`aitask_query_files.sh plan-file <id>`). Child-context rules (PINNED): parent = single manager-level line; pending children inform outcome phrasing and progress ("3 of 5 subtasks complete", pending vs archived via `aitask_query_files.sh archived-children <id>`); done/archived children counted, never listed individually; folded tasks are merged content, never separate items; child plans NOT mined for implementation-level file/symbol detail.
6. Draft first-person manager-friendly Markdown: short focus summary → column-grouped ordered priorities (outcome + current status + t<id> for traceability) → throughput-based completion projection → blockers/manager-asks. Exactly the selected tasks; no invented dates/estimates/progress/commitments; no implementation-level file/symbol detail.
6b. Completion projection (PINNED — explicit AC amendment from planning): data-derived projections from `VELOCITY:` lines are in scope, labeled as projections from historical throughput, never commitments. Work items = Σ `remaining_items` (0-sum → say selection is effectively complete, omit projection); throughput = `avg_per_day` (prefer 30-day window; mention 7-day when notably divergent); projected days ≈ items ÷ rate, compared against the chosen horizon. Velocity 0 → state "insufficient completion history for a projection" and omit — never fabricate a rate.
7. Present in-session for review/editing (iterate). Do NOT write a report file.
8. Satisfaction Feedback Procedure (`.claude/skills/task-workflow/satisfaction-feedback.md`) with `skill_name: work-report`.

## Verification

- `tests/test_work_report_skill_contract.sh`: asserts the canonical SKILL.md contains the load-bearing markers — the fail-closed `ERROR:`/`NO_TASKS` hard-stop section, the "never drafts from a partial or silently-corrected selection" sentence, the `--list-columns` discovery requirement, the no-report-file rule, the "insufficient completion history" fallback — and that all 3 wrapper files point at the canonical path. Dropping any marker fails the test.
- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- Skill listed by the audit: `./.aitask-scripts/aitask_audit_wrappers.sh` (wrapper coverage for the new skill).
