---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [workflow, skills]
gates: [risk_evaluated]
anchor: 1536
followup_kind: upstream_defect
created_at: 2026-08-18 11:59
updated_at: 2026-08-18 11:59
---

## Origin

Spawned from t1558 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_skill_rerender.sh` — the orphaned-dir skip keys on
  `<skill>/SKILL.md.j2`, so a closure whose authoring template is a Jinja-inline
  `SKILL.md` (`task-workflow`, `user-file-select`) is never re-rendered directly
  and is refreshed only incidentally via an entry-point skill's dependency walk.
  A project with no entry-point skill rendered for that profile would silently
  keep stale rendered variants.

## Diagnostic context

t1558 edited `.claude/skills/task-workflow/SKILL.md` (the authoring template —
Jinja is inline in the `.md`; there is no `SKILL.md.j2` for this skill) and then
ran the documented regeneration:

```bash
for p in default fast remote; do ./.aitask-scripts/aitask_skill_rerender.sh "$p"; done
```

Every run logged, for every agent tree:

```
Skipping orphaned rendered dir (no template at .claude/skills/task-workflow/SKILL.md.j2): .claude/skills/task-workflow-remote-
Skipping orphaned rendered dir (no template at .claude/skills/user-file-select/SKILL.md.j2): .claude/skills/user-file-select-remote-
```

The tracked `task-workflow-remote-` variants *were* refreshed in the end — but
only as a side effect of the **entry-point** skills (`aitask-pick`,
`aitask-pickrem`, `aitask-explore`, …) being re-rendered, because
task-workflow sits in their dependency closure. The direct pass over the
`task-workflow-<profile>-` dirs never fires.

Two problems follow:

1. **The message reads as a failure and is not one.** Anyone auditing a
   rerender of this closure sees "orphaned rendered dir" against a skill that
   is very much alive, and has no way to tell whether the refresh actually
   happened.
2. **The incidental refresh is not guaranteed.** It holds only because some
   entry-point skill is rendered for that profile and lists task-workflow in
   its closure. A profile (or a downstream project) with no such entry point
   would leave the rendered variants stale with no diagnostic beyond the
   misleading skip line.

## Suggested fix

Make the template probe accept either authoring form — `<skill>/SKILL.md.j2`
**or** a Jinja-bearing `<skill>/SKILL.md` — before declaring a rendered dir
orphaned; and reserve the "orphaned" wording for a rendered dir with neither.
The skip loop lives around `.aitask-scripts/aitask_skill_rerender.sh:60`.
