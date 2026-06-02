---
priority: low
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: [bash_scripts, python]
created_at: 2026-06-02 12:48
updated_at: 2026-06-02 12:48
---

## Context

Follow-up filed by t884_7 (trailing retrospective of the task risk-evaluation
feature, t884). The parent plan (`aiplans/p884_add_task_risk_evaluation_in_planning.md`,
"Single-source-of-truth for the risk enum — decision") deliberately mirrored
`priority`'s existing duplication rather than introduce a shared constant inside
the feature task, and recorded a named follow-up to extract the enum properly.
Per `aidocs/planning_conventions.md` ("name the refactor, don't bury it").

## Goal

Extract the `high | medium | low` enum — shared by `priority` and the two risk
fields (`risk_code_health`, `risk_goal_achievement`) — into a single source of
truth, removing the cross-language duplication.

## Scope (larger than the parent plan's "~5 bash sites + board.py" estimate)

A t884_7 verify-mode scan found `high|medium|low` hardcoded across ~15 files:

- **Bash:** `aitask_create.sh`, `aitask_update.sh`, `aitask_ls.sh`,
  `aitask_archive.sh`, `aitask_issue_import.sh`, `aitask_pr_import.sh`,
  `aitask_verification_followup.sh`, `aitask_create_manual_verification.sh`.
- **Python:** `board/aitask_board.py`, `settings/settings_app.py`,
  `brainstorm/brainstorm_app.py`, `monitor/monitor_shared.py`,
  `monitor/monitor_app.py`, `monitor/minimonitor_app.py`,
  `monitor/desync_summary.py`, `agentcrew/agentcrew_dashboard.py`.

Not every match is a priority/risk enum (some are unrelated literals) — the
implementation must triage each site before substituting.

## Proposed approach

A single source consumable by both bash and Python. Options to weigh in planning:
- A bash sourced lib (e.g. a `lib/` constant array) mirrored by a Python
  constant, OR
- A metadata file (e.g. under `aitasks/metadata/`) read by both.

Follow CLAUDE.md shell conventions and the cross-language help-text duplication
guidance in `aidocs/code_conventions.md`. Validate with `shellcheck` and the
existing risk/update tests (`tests/test_update_risk.sh`).

## Reference

- `aiplans/p884_add_task_risk_evaluation_in_planning.md` (enum decision + rationale).
- t884 (parent feature task).
