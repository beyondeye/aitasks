---
priority: medium
effort: medium
depends: [1365]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1365]
created_at: 2026-08-02 22:58
updated_at: 2026-08-02 22:58
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1365

## Verification Checklist

- [ ] With ait board running, create a trail for a task in another shell, then press s in By-Trail and confirm the new trail is listed without restarting the board
- [ ] Activate a newly created trail and confirm its member cards render as real task cards (not grey ghost cards) — the members were created after the board started
- [ ] Leave By-Trail (z to another base filter) and re-enter it after cancelling the selector with Esc; confirm the selector re-scans rather than serving the previous list
- [ ] While a task file is being rewritten (e.g. run ait artifact new against a task in a loop), press s and confirm the board warns "Trail scan skipped N unreadable active task file(s)" and does NOT claim "No implementation trails found"
- [ ] Confirm the board does not exit when a task file in aitasks/ contains malformed YAML frontmatter while s is pressed
- [ ] Check the By-Trail footer and the reference docs agree on what s does (r Refresh / R Agent Refresh / d Freshness / s Select Trail / S Sync)
