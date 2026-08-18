---
priority: medium
effort: medium
depends: [1557]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1557]
assigned_to: dario-e@beyond-eye.com
anchor: 1159
followup_kind: manual_verification
created_at: 2026-08-18 09:05
updated_at: 2026-08-18 09:11
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1557

## Verification Checklist

- [ ] In a real tmux pane at a SHORT height (<=9 rows), trigger Claude's tool-permission dialog and confirm `ait monitor` still flags the pane as awaiting input with kind `claude_proceed` (the regime where the truncated option list lifts the real header into the 6-line detection window)
- [ ] At a normal height (>=11 rows), press Tab to amend option 1, type `Do you want to proceed?` into it, and confirm the followed-pane review loop does NOT fire an auto-recheck round while typing
- [ ] With that text still typed into option 1, move the option cursor between rows and confirm the reported kind / dialog badge stays put instead of flipping
- [ ] TODO: verify .aitask-scripts/monitor/prompt_patterns.py end-to-end in tmux
- [ ] TODO: verify .aitask-scripts/monitor/review_loop.py end-to-end in tmux
