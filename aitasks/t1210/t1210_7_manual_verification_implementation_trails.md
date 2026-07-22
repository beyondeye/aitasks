---
priority: medium
effort: medium
depends: [t1210_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1210_2, 1210_3, 1210_4, 1210_5]
anchor: 1210
created_at: 2026-07-22 16:17
updated_at: 2026-07-22 16:17
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1210_3] Create a trail interactively via /aitask-trail on a real task: scope question offered, proposal rendered with full narrative (waves, rationale, observations), single confirmed write; `ait artifact ls <owner>` shows the art:trail-* handle
- [ ] [t1210_3] Refresh flow: archive one member task, run /aitask-trail --refresh <handle>; drift reasons named, diff-style summary shown, new version appears in `ait artifact versions <handle>`
- [ ] [t1210_2] Drift check is read-only: run the drift verb twice; trail artifact bytes unchanged; boardidx-only board move does NOT flip the trail to stale
- [ ] [t1210_4] By-Trail view: enter the view, select each of several trails, verify wave columns, classification/confidence badges, completion strike-through, and the stale banner after a member status change
- [ ] [t1210_4] Error states: temporarily rename the artifact blob/manifest; By-Trail view shows the fail-closed error card and offers versions fallback; restore afterwards
- [ ] [t1210_4] Launch seams: create/refresh actions from a task card, a By-Topic lane header, and the By-Trail view all open AgentCommandScreen with the expected /aitask-trail arguments
- [ ] [t1210_5] Move commands: `m` moves a focused entry to a chosen column; `M` moves a whole wave preserving wave order; ghost (archived/cross-repo) cards are excluded with a visible reason
- [ ] [t1210_5] Passive report bridge: after `M` into a column, run the board Work Report flow on that column; report contains exactly those tasks in board order
