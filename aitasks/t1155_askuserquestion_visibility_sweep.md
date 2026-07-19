---
priority: medium
effort: medium
depends: []
issue_type: chore
status: Ready
labels: [skills, aitask_explore]
gates: [risk_evaluated]
anchor: 1150
created_at: 2026-07-15 18:37
updated_at: 2026-07-15 18:37
boardidx: 90
---

## Origin

Risk-mitigation ("after") follow-up for t1150, created at Step 8d after implementation landed.

## Risk addressed

- Mitigation relies on future sessions' instruction-following to embed summaries in the question text; the widget payload is structurally rendered, but a model could still under-fill it · severity: medium
- Same invisible-prose hazard exists at other summary-before-question sites outside t1150's scope (e.g. `risk-mitigation-followup.md` Part 1's "plain-text numbered list before the prompt", `manual-verification-followup.md` candidate list, review/qa finding summaries) · severity: medium

## Goal

Audit ALL skill/procedure surfaces for "plain-text summary before AskUserQuestion" sites and apply the AskUserQuestion visibility rule (added to `aidocs/framework/skill_authoring_conventions.md` by t1150): any content the user needs to answer the question must be inside the widget payload (question text / option labels / descriptions), with preceding prose kept only as best-effort duplication.

Surfaces to sweep:
- `.claude/skills/*/SKILL.md.j2` and static `SKILL.md` skills
- `.claude/skills/task-workflow/*.md` procedures — known offenders: `risk-mitigation-followup.md` Part 1 step 2 ("Present the proposed mitigations to the user as a plain-text numbered list ... before the prompt"), `manual-verification-followup.md` step 4 ("Display the assembled candidate bullets ... as plain text before the prompt"), review/qa finding summaries
- Regenerate affected goldens (`tests/golden/skills/`, `tests/golden/procs/`) in the same commit and run the `tests/test_skill_render_*.sh` suites + `aitask_skill_verify.sh`

Background: under Claude Code + Fable 5, assistant prose emitted in the same turn as an AskUserQuestion call is routed to a non-rendered narration channel and is invisible (t1150; upstream: anthropics/claude-code#77849). First hardened site: `aitask-explore` Step 2/Step 3.
