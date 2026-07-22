---
priority: medium
effort: medium
depends: [1204]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1204]
created_at: 2026-07-22 11:32
updated_at: 2026-07-22 11:32
boardidx: 110
boardcol: tests
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1204

## Verification Checklist

- [ ] Open the chatlink wizard, reach "Who may open a bug report", press "Fetch from Discord" against a working bot; confirm rows appear and a member + a role can be selected
- [ ] Break connectivity (or revoke the token) and press "Fetch from Discord" again; confirm the rows and selections are RETAINED, both pickers show a warning-coloured border plus the "! previous fetch - may be out of date" border title, and the status names the earlier fetch
- [ ] Press Back then forward again; confirm the warning borders, border titles and the EARLIER-fetch notice all re-render (never a blank status line over stale rows)
- [ ] Restore connectivity and press "Fetch from Discord"; confirm the warning borders and titles clear and the normal "fetched N member(s) and M role(s)" line returns
- [ ] Partial failure: remove only the bot's role-read permission, then Fetch; confirm ONLY the role picker is marked stale while the member picker refreshes clean
- [ ] First fetch while offline; confirm the pickers never appear, the connection error plus "enter ids manually above" is shown, Next still advances, and Back-then-forward does not resurrect an empty picker with a blank status
- [ ] Confirm the warning border is visually distinguishable from the normal border in your real terminal + theme (the automated test asserts the resolved colour and the SVG export, not a live terminal render)
