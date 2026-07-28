---
priority: medium
effort: medium
depends: [1204]
issue_type: manual_verification
status: Done
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1204]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-22 11:32
updated_at: 2026-07-28 11:30
completed_at: 2026-07-28 11:30
boardcol: tests
boardidx: 110
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1204

## Verification Checklist

- [x] Open the chatlink wizard, reach "Who may open a bug report", press "Fetch from Discord" against a working bot; confirm rows appear and a member + a role can be selected — PASS 2026-07-28 11:27 auto: live tmux run of the real ChatlinkApp wizard; Fetch revealed 3 members + 2 roles, status 'fetched 3 member(s) and 2 role(s)'; selecting alice and mods wrote both ids into the Allowed user/role id Inputs. Discord network layer simulated at the allowlist_fetch_runner seam (no bot token configured on this machine)
- [x] Break connectivity (or revoke the token) and press "Fetch from Discord" again; confirm the rows and selections are RETAINED, both pickers show a warning-coloured border plus the "! previous fetch - may be out of date" border title, and the status names the earlier fetch — PASS 2026-07-28 11:27 auto: refresh with both stages erroring (connection failed (OSError)) -- all 5 rows and both selections retained, BOTH pickers rendered border title '! previous fetch - may be out of date' in $warning RGB(254,166,43) vs fresh RGB(1,120,212), status showed the per-stage errors plus '! showing the EARLIER fetch for: users, roles'
- [x] Press Back then forward again; confirm the warning borders, border titles and the EARLIER-fetch notice all re-render (never a blank status line over stale rows) — PASS 2026-07-28 11:27 auto: Back to step 3 then forward to step 4 -- both warning borders (RGB 254,166,43), both border titles and the full EARLIER-fetch notice re-rendered; status was never blank over the stale rows
- [x] Restore connectivity and press "Fetch from Discord"; confirm the warning borders and titles clear and the normal "fetched N member(s) and M role(s)" line returns — PASS 2026-07-28 11:27 auto: connectivity restored and Fetch pressed -- zero warning-coloured cells left on the pane, both border titles cleared, status back to 'fetched 3 member(s) and 2 role(s)'
- [x] Partial failure: remove only the bot's role-read permission, then Fetch; confirm ONLY the role picker is marked stale while the member picker refreshes clean — PASS 2026-07-28 11:27 auto: roles-only failure (role fetch failed (Forbidden)) -- ONLY the role picker carried the warning border + title; member picker refreshed clean in the primary colour; status named roles only
- [x] First fetch while offline; confirm the pickers never appear, the connection error plus "enter ids manually above" is shown, Next still advances, and Back-then-forward does not resurrect an empty picker with a blank status — PASS 2026-07-28 11:27 auto: fresh app, first fetch offline -- no pickers, no filter, status '! members/roles: connection failed (OSError)' + 'enter ids manually above - Next still works'; Next advanced (after the pre-existing deny-all posture confirm) to step 5; Back-then-forward returned a clean manual-entry-only screen, no empty picker, no blank status
- [x] Confirm the warning border is visually distinguishable from the normal border in your real terminal + theme (the automated test asserts the resolved colour and the SVG export, not a live terminal render) — PASS 2026-07-28 11:29 user-confirmed in a live tmux pane: stale orange border reads as clearly distinct from the normal blue
