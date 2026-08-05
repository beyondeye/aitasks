---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [framework, task_workflow]
gates: [risk_evaluated]
anchor: 1419
created_at: 2026-08-05 12:11
updated_at: 2026-08-05 12:11
---

## Origin

Spawned from t1419 during Step 8b review.

## Upstream defect

- .claude/skills/task-workflow/related-task-discovery.md:68 — AskUserQuestion header "Related tasks" (13 chars) exceeds the documented 12-char header cap
- .claude/skills/task-workflow/planning.md:273 — AskUserQuestion header "Manual verify" (13 chars) exceeds the documented 12-char header cap

## Diagnostic context

While pinning the new recovery-prompt headers in `risk-mitigation-followup.md` to the AskUserQuestion header contract ("Very short label displayed as a chip/tag (max 12 chars)"), a repo scan of `.claude/skills/task-workflow/*.md` found these two pre-existing headers over the cap. The schema enforces the cap via description only (no `maxLength`), so the prompts work today — but they violate the documented contract and any future hard enforcement would break them. t1419 added Test 7 in `tests/test_skill_render_task_workflow.sh` asserting the ≤12 cap for `risk-mitigation-followup.md` only, deliberately excluding these two pre-existing cases.

## Suggested fix

Rename both headers to ≤12-char labels (e.g. "Related" / "Man. verify" or "Verify"), regenerate the affected task-workflow goldens in the same commit, and widen Test 7's header-cap scan from `risk-mitigation-followup.md` to all canonical `.claude/skills/task-workflow/*.md` files.
