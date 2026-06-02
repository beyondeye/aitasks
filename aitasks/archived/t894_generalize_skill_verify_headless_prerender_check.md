---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [task_workflow, task-planning]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-01 12:20
updated_at: 2026-06-02 22:38
completed_at: 2026-06-02 22:38
boardidx: 70
---

## Origin

Spawned from t888 during Step 8b review.

## Upstream defect

`.aitask-scripts/aitask_skill_verify.sh:151 — headless-prerender freshness check is hardcoded to aitask-pickrem only (TODO t777_29); no check covers the committed task-workflow-remote- closure, so source-vs-committed-prerender drift goes unnoticed. Generalize the freshness check (read a prerender marker from j2 frontmatter + headless flag from profile YAML) so this drift class fails loudly.`

Note: t777_29 is referenced in the `TODO(t777_29)` comment at `aitask_skill_verify.sh:152` but does not exist as a real task — this task supersedes that placeholder.

## Diagnostic context

t888 fixed stale `task-workflow-remote-` prerenders by rerendering them. The root cause of the drift going unnoticed: `aitask_skill_verify.sh` only verifies committed-remote-prerender freshness for `aitask-pickrem` (see its "Headless prerender check (pickrem only for now)" / `TODO(t777_29): generalize` at lines 151-155). A source edit to `.claude/skills/task-workflow/` (planning.md / SKILL.md) without a `aitask_skill_rerender.sh remote` left the committed `task-workflow-remote-` closure stale, and nothing failed. Any profile-aware skill with a committed headless/remote prerender has the same exposure.

## Suggested fix

Generalize the hardcoded `if [[ "$skill" == "aitask-pickrem" ]]` branch in `aitask_skill_verify.sh` to discover prerender-bearing skills declaratively: read a `prerender_for_headless` marker from the `.md.j2` frontmatter and the `headless: true` flag from the profile YAML, then verify committed-prerender freshness for every (skill, profile) pair that opts in — including the `task-workflow-remote-` closure. Remove the `TODO(t777_29)` comment once generalized.
