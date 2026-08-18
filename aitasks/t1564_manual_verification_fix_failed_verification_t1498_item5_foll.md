---
priority: medium
effort: medium
depends: [1499]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1499]
anchor: 1159
followup_kind: manual_verification
created_at: 2026-08-18 10:00
updated_at: 2026-08-18 10:00
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1499

## Verification Checklist

- [ ] [shadow] With a real shadow companion running (`e`), let its feedback go stale and confirm the red `⚠ shadow feedback is stale — …` banner appears IN THE MINIMONITOR PANE (the exact item that failed t1498 #5), and that it clears when the shadow re-reads.
- [ ] [loop] Arm the auto-recheck loop with `L` and confirm the $warning loop banner (`⟳ recheck #N sent — waiting for shadow`) is visible and updates per tick, and is visually distinct from the $error stale banner.
- [ ] [session bar] Confirm the session bar on row 0 shows live agent counts plus `awaiting` / `idle` / done / desync, and that `rc:retry` / `rc:fb` appear when the tmux control channel degrades.
- [ ] [short mode] With a standing stale banner, shrink the tmux window below ~20 rows: the key hints must compact to two lines while the agent list and the followed-agent panel stay on screen. Grow it back and confirm the full 10-line hints return.
- [ ] [own panel] Confirm the followed-agent panel still renders its identity line, the ★ mark glyph and the advisory phase, now one row lower than before.
- [ ] [not-in-tmux] Run `ait minimonitor` outside tmux and confirm the red `Not inside tmux` message is actually visible (it was written to a dead widget before t1499).
