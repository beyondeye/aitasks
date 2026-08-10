---
priority: medium
effort: medium
depends: [1474]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1474]
created_at: 2026-08-10 18:42
updated_at: 2026-08-10 18:42
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1474

## Verification Checklist

- [ ] In a scratch directory Claude Code has never trusted, launch the agent inside the framework's tmux session and confirm `ait monitor` renders PROMPT (not IDLE) for that pane while the workspace-trust dialog is on screen.
- [ ] Confirm the reported awaiting_input_kind for that pane is `claude_trust_folder` (read it from an `ait applink` pane_status frame, or instrument monitor_core).
- [ ] Confirm the same detection for the settings-trust variant whose cancel label is "No, exit Claude Code" — that regex arm was dead until a late fix and has never been observed live.
- [ ] Confirm the cancel-label variant "No, continue without these permissions" is also flagged.
- [ ] Confirm the option lines land inside the 6-line detection window at a narrow pane width, where the wrapped question consumes more rows.
- [ ] Confirm a pane whose only change between refresh ticks is an OSC 8 hyperlink target still reaches IDLE in a live monitor session (folded in from the Step 8c discovery for t1474).
- [ ] Confirm no false PROMPT appears when a pane merely displays t1474's plan or tests/test_prompt_detection.py — the documented known limit is a verbatim option block only.
