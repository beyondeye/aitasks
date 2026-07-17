---
priority: medium
effort: medium
depends: [t1157_9]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1157_1, 1157_2, 1157_3, 1157_4, 1157_5, 1157_6, 1157_7, 1157_8, 1157_9]
anchor: 1157
created_at: 2026-07-17 16:57
updated_at: 2026-07-17 16:57
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1157_1] Legacy singleton configuration migrates explicitly; two registered projects/workflows across guilds validate with one bot token and no duplicate channel trigger.
- [ ] [t1157_2] A paused thread retains proposal/checkpoint state; Resume and Restart create a new attempt against latest committed HEAD, while an expired seven-day session rejects controls.
- [ ] [t1157_3] Two Discord workflow channels route to their configured projects without cross-talk; an unknown or foreign interaction has no side effect.
- [ ] [t1157_4] Bug intake visibly reports budget/deadline/default, can ask more than three useful questions, and never creates a task without an explicit initiator approval.
- [ ] [t1157_5] An explore-channel message opens a thread, selects an intent, shows findings with Continue/Redirect/Pause controls, and explicitly creates only an approved task.
- [ ] [t1157_6] File selection, related-task folding, and cross-project explore routing behave safely with stale selections rejected before mutation.
- [ ] [t1157_7] Chatlink TUI presents project/workflow/attempt health and configuration migration without controlling live sessions.
- [ ] [t1157_8] Published documentation accurately describes setup, budgets, proposal approval, revision, resume, restart, expiry, and safety boundaries.
- [ ] [t1157_9] Seeded soak and restart tests pass; perform a live two-workflow Discord run with approval, revision, resume/restart, routed task creation, and TUI observation.
