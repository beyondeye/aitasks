---
priority: medium
effort: medium
depends: [1777]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [1777]
assigned_to: dario-e@beyond-eye.com
anchor: 1705
followup_kind: manual_verification
created_at: 2026-09-16 12:44
updated_at: 2026-09-16 12:48
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1777

## Verification Checklist

- [ ] Freeze an agent, then press k in monitor on the frozen card: the dialog body must read "Its captured output is deleted along with the record, and the stand-in pane is closed. This cannot be undone. A verified restore or re-pick deletes it too — copy it first." and the affirmative button must be a red "Drop".
- [ ] Repeat in minimonitor at its normal narrow companion width: the dialog text must be unclipped and BOTH buttons fully on screen and clickable. Measured to need 18 rows at 40 columns — note the pane height you tested at.
- [ ] In the frozenagent viewer (the stand-in pane), press k: the message must read "Drop the frozen record and its capture? This cannot be undone." and the button must say "Drop", matching the footer's "k Drop".
- [ ] Verify the corrected claim end-to-end: freeze an agent, press y to copy the transcript, then R to restore. Once the resumed agent verifies itself the capture must be GONE — confirming the dialog was right to stop advising restore/re-pick as a way to keep it.
- [ ] Run `bash tests/run_all_python_tests.sh` from an external terminal (not inside tmux, with no live `-L ait` session). t1777 ran 316 of 320 modules (7656 tests, OK); the four live-TUI carve-out modules were not run because $TMUX was set and test_board_header_row_live.py takes .git/index.lock on this repo.
