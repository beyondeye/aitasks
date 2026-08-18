---
priority: medium
effort: medium
depends: [1557]
issue_type: manual_verification
status: Done
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
updated_at: 2026-08-18 09:48
completed_at: 2026-08-18 09:48
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1557

## Verification Checklist

- [x] In a real tmux pane at a SHORT height (<=9 rows), trigger Claude's tool-permission dialog and confirm `ait monitor` still flags the pane as awaiting input with kind `claude_proceed` (the regime where the truncated option list lifts the real header into the 6-line detection window) — PASS 2026-08-18 09:47 auto: live claude 2.1.234 in tmux 120x9, real Bash permission dialog; ait monitor header '1 awaiting', row 'PROMPT 38s'; production classify_content reports kind=claude_proceed (question at window index -5)
- [x] At a normal height (>=11 rows), press Tab to amend option 1, type `Do you want to proceed?` into it, and confirm the followed-pane review loop does NOT fire an auto-recheck round while typing — PASS 2026-08-18 09:47 auto: same live dialog resized to 120x14; Tab + typed 'Do you want to proceed?' into option 1; kind stayed claude_help_bar and classify_followed_change returned selection_only on every typing tick (neg control with the pre-t1557 substring pattern: kind flips to claude_proceed and verdict=work)
- [x] With that text still typed into option 1, move the option cursor between rows and confirm the reported kind / dialog badge stays put instead of flipping — PASS 2026-08-18 09:47 auto: cursor moved 1->2->3->2 with the text still typed; kind stayed claude_help_bar, verdicts selection_only, ait monitor badge stayed PROMPT
- [x] TODO: verify .aitask-scripts/monitor/prompt_patterns.py end-to-end in tmux — PASS 2026-08-18 09:47 auto: prompt_patterns.py exercised end-to-end against a live pane at both geometries (claude_proceed at 9 rows, claude_help_bar at 14) via monitor capture args + classify_content; tests/test_prompt_detection.py 22/22
- [x] TODO: verify .aitask-scripts/monitor/review_loop.py end-to-end in tmux — PASS 2026-08-18 09:47 auto: review_loop.classify_followed_change driven over 6 live captured frames (geometry + history_size as minimonitor passes them); tests/test_review_loop.py 145/145
