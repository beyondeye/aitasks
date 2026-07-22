---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [skills, opencode]
gates: [risk_evaluated]
anchor: 1150
created_at: 2026-07-15 18:32
updated_at: 2026-07-15 18:32
boardidx: 280
---

## Origin

Spawned from t1150 during Step 8b review.

## Upstream defect

- `.opencode/skills/task-workflow-remote-/cross-repo-child-assignment.md` — committed prerender is stale relative to its `.claude/skills/task-workflow/` source (t1117 edited `cross-repo-child-assignment.md` without rerendering); `aitask_skill_verify.sh` fails with 2 PRERENDER_FAIL (aitask-pickrem / aitask-pickweb, agent=opencode, profile=remote).

## Diagnostic context

While verifying t1150's aitask-explore `.md.j2` edit, `./.aitask-scripts/aitask_skill_verify.sh` reported:

```
PRERENDER_FAIL: aitask-pickrem agent=opencode profile=remote committed prerender stale or unrenderable (run aitask_skill_rerender.sh remote and commit):
committed prerender drift:
  .opencode/skills/task-workflow-remote-/cross-repo-child-assignment.md (stale)
PRERENDER_FAIL: aitask-pickweb agent=opencode profile=remote ... (same file)
```

Confirmed pre-existing: with t1150's edits stashed, the same 2 failures occur. `git log` shows the source was last touched by commit 49ee5e30f "bug: Support cross-repo child creation (t1117)", which did not regenerate the committed OpenCode remote prerender.

## Suggested fix

Run `./.aitask-scripts/aitask_skill_rerender.sh remote`, review the drift diff, and commit the regenerated `.opencode/skills/task-workflow-remote-/cross-repo-child-assignment.md`. Re-run `aitask_skill_verify.sh` to confirm green.
