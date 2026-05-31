---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [task_workflow, task-planning]
created_at: 2026-05-31 19:05
updated_at: 2026-05-31 19:05
---

## Origin

Spawned from t885 during Step 8b review.

## Upstream defect

`.claude/skills/task-workflow-remote-/planning.md:136 — committed task-workflow-remote- prerenders (planning.md + SKILL.md, across claude/codex/opencode) are stale vs source: missing the cross-repo dispatch (planning.md) and cross-repo child-assignment (SKILL.md) paragraphs that a prior cross-repo task added to source without rerendering the committed remote prerenders. aitask_skill_verify.sh enforces headless-prerender freshness only for aitask-pickrem (TODO t777_29 to generalize), so the drift was not caught. Fix: ./.aitask-scripts/aitask_skill_rerender.sh remote, then commit the refreshed task-workflow-remote- files.`

The 6 affected committed files:
- `.claude/skills/task-workflow-remote-/planning.md`, `.claude/skills/task-workflow-remote-/SKILL.md`
- `.agents/skills/task-workflow-remote-codex-/planning.md`, `.agents/skills/task-workflow-remote-codex-/SKILL.md`
- `.opencode/skills/task-workflow-remote-/planning.md`, `.opencode/skills/task-workflow-remote-/SKILL.md`

## Diagnostic context

While implementing t885 (a `.claude/skills/task-workflow/planning.md` source edit), regenerating the committed remote prerenders via `aitask_skill_rerender.sh remote` produced diffs that included not just t885's "Revise plan" change but also pre-existing cross-repo paragraphs absent from the committed copies. The source files (`.claude/skills/task-workflow/planning.md` §6.1 "Cross-repo dispatch check"; `.claude/skills/task-workflow/SKILL.md` Step 7 "Cross-repo child assignment") carry these paragraphs; the committed `task-workflow-remote-` copies do not. t885 deliberately restored the 6 remote files to HEAD to keep its commit scoped, leaving this drift for this task.

Root cause: `aitask_skill_verify.sh` only verifies committed-remote-prerender freshness for `aitask-pickrem` (see its "Headless prerender check (pickrem only for now)" / `TODO(t777_29): generalize`). No check covers the committed `task-workflow-remote-` closure, so a source edit without a rerender goes unnoticed.

## Suggested fix

1. Run `./.aitask-scripts/aitask_skill_rerender.sh remote` and commit the refreshed `task-workflow-remote-` files (all 3 agent trees).
2. Consider generalizing `aitask_skill_verify.sh`'s headless-prerender freshness check beyond `aitask-pickrem` (the existing `TODO(t777_29)`) so future source-vs-committed-prerender drift fails loudly. Track separately if larger than this task.
