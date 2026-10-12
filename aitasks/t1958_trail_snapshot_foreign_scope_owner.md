---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [trails, cross_repo]
gates: [risk_evaluated]
anchor: 1957
created_at: 2026-10-12 21:32
updated_at: 2026-10-12 21:32
---

## Problem

`/aitask-trail proj#42` (a cross-repo task scope) writes the trail onto the
wrong task.

`.aitask-scripts/lib/trail_gather.py` `cmd_snapshot` (~lines 1118-1124) sets the
owner to `--owner` if given, else the **single scope id even when it lives in
another repo**, and prints `OWNER:proj#42` (~1137). The skill's write step then
strips that to the bare id and runs `aitask_artifact.sh create 42 …`. That
attaches the trail to **local** t42 (an unrelated task), or fails when no local
t42 exists.

A trail is an artifact owned by a **local** task, so a foreign owner can never
be valid.

## Candidate fixes (choose in planning)

1. Make `cmd_snapshot` reject a foreign owner (a new error code) and require a
   local `--owner` whenever the single scope id is cross-repo.
2. Have the `/aitask-trail` skill (`.claude/skills/aitask-trail/SKILL.md.j2`)
   ask the user for a local owner task when the scope id is cross-repo, and pass
   it as `--owner`.

Either way, the skill must never strip a `proj#` prefix into a bare local id.
If the skill changes, regenerate its goldens and suggest ports to the other
agents' skill trees.

## Origin

Found while exploring t1957 (cross-repo trail blockers and linked trails),
where it was kept out of scope.
