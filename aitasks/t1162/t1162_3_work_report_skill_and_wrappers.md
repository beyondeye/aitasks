---
priority: medium
effort: medium
depends: [t1162_2]
issue_type: feature
status: Implementing
labels: [skills, reporting]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1162
created_at: 2026-07-22 10:45
updated_at: 2026-07-23 14:56
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
6b. Throughput + projection (PINNED — AC amendment from planning, REVISED by t1162_1): observed throughput is a default part of the report; a completion-date projection is **opt-in and must be explicitly requested**. Render `VELOCITY:` rows **generically** (per bucket: `<bucket_label>`, `<avg_per_unit>`, `<observed_units>`) — the estimator is selectable via `--velocity-model`, so do NOT hardcode weekday semantics; quote `<observed_units>` so the reader can judge confidence. Only when the user asks for a forecast, re-invoke the gatherer with `--project` and read `PROJECTION:<remaining_total>|<projected_date>|<days_ahead>|<basis_completions>|<caveat>`; report it as-is — do NOT recompute it and do NOT do date arithmetic in-prompt. `remaining_total` 0 → say the selection is effectively complete and omit the projection. Compare `<projected_date>` against the chosen horizon ("≈ N days at the recent pace — roughly fits / exceeds this week") and **always surface `<caveat>`**: the figure counts tasks, so it ignores task size, blockers and capacity — an extrapolation of past throughput, never a commitment or a delivery estimate. Quote `<basis_completions>`. `PROJECTION:<n>|none|insufficient_data|…` → state "insufficient completion history for a projection" and omit — never fabricate a rate.
7. Present in-session for review/editing (iterate). Do NOT write a report file.
8. Satisfaction Feedback Procedure (`.claude/skills/task-workflow/satisfaction-feedback.md`) with `skill_name: work-report`.

## Verification

- `tests/test_work_report_skill_contract.sh`: asserts the canonical SKILL.md contains the load-bearing markers — the fail-closed `ERROR:`/`NO_TASKS` hard-stop section, the "never drafts from a partial or silently-corrected selection" sentence, the `--list-columns` discovery requirement, the no-report-file rule, the "insufficient completion history" fallback — and that all 3 wrapper files point at the canonical path. Dropping any marker fails the test.
- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- Skill listed by the audit: `./.aitask-scripts/aitask_audit_wrappers.sh` (wrapper coverage for the new skill).
