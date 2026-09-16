---
priority: medium
effort: medium
depends: [1777]
issue_type: manual_verification
status: Done
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1777]
assigned_to: dario-e@beyond-eye.com
anchor: 1705
followup_kind: manual_verification
created_at: 2026-09-16 12:44
updated_at: 2026-09-16 23:31
completed_at: 2026-09-16 23:31
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1777

## Verification Checklist

- [x] Freeze an agent, then press k in monitor on the frozen card: the dialog body must read "Its captured output is deleted along with the record, and the stand-in pane is closed. This cannot be undone. A verified restore or re-pick deletes it too — copy it first." and the affirmative button must be a red "Drop". — PASS 2026-09-16 17:17 auto: headless MonitorApp.run_test(120x40) with a frozen snapshot focused; pilot.press('k') opened FreezeConfirmDialog; rendered body sentence byte-equal to the expected copy, #btn-confirm label 'Drop' variant 'error' (red), -destructive class set
- [x] Repeat in minimonitor at its normal narrow companion width: the dialog text must be unclipped and BOTH buttons fully on screen and clickable. Measured to need 18 rows at 40 columns — note the pane height you tested at. — PASS 2026-09-16 17:17 auto: headless MiniMonitorApp.run_test at 40x18: dialog y=0..18, body Static natural height 8 == allotted 8 (unclipped), Drop right=19 and Cancel right=30 both inside 40 cols, bottom=16 <= 18; centre-clicks landed and dismissed True/False. Same at 40x20. At 40x17 and 40x16 the dialog is 19 rows and overflows -- minimum fitting pane height is 18 rows, matching t1777's measurement
- [x] In the frozenagent viewer (the stand-in pane), press k: the message must read "Drop the frozen record and its capture? This cannot be undone." and the button must say "Drop", matching the footer's "k Drop". — PASS 2026-09-16 17:17 auto: headless FrozenAgentApp.run_test(80x24) on a temp store with one frozen record and a fake tmux; pilot.press('k') opened ConfirmDialog; #fa-confirm-text renders 'Drop the frozen record and its capture? This cannot be undone.', #fa-confirm-yes label 'Drop' variant 'error'; the stock Footer's FooterKey widgets include ('k', 'Drop'); Escape cancelled with zero run-shell calls
- [x] Verify the corrected claim end-to-end: freeze an agent, press y to copy the transcript, then R to restore. Once the resumed agent verifies itself the capture must be GONE — confirming the dialog was right to stop advising restore/re-pick as a way to keep it. — PASS 2026-09-16 23:31 manual: user ran freeze -> y copy -> R restore; capture gone after the verified restore
- [x] Run `bash tests/run_all_python_tests.sh` from an external terminal (not inside tmux, with no live `-L ait` session). t1777 ran 316 of 320 modules (7656 tests, OK); the four live-TUI carve-out modules were not run because $TMUX was set and test_board_header_row_live.py takes .git/index.lock on this repo. — PASS 2026-09-16 17:58 auto: bash tests/run_all_python_tests.sh run from this plain-terminal session (TMUX unset, no -L ait server): 'Ran 7667 tests in 1012.7s', 'OK (skipped=10)', 'PYTHON SUITE: PASSED (runner=unittest, exit=0)', EXIT=0 read from the process's own status, not a pipeline. pytest tier not installed so the run was serial; all four live-TUI carve-out modules ran and passed
