---
priority: medium
effort: medium
depends: [t1636_7]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [t1636_1, t1636_2, t1636_3, t1636_4, t1636_7]
assigned_to: dario-e@beyond-eye.com
anchor: 1636
followup_kind: manual_verification
created_at: 2026-08-30 14:58
updated_at: 2026-09-01 09:51
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t1636_1] `python -m pytest tests/test_concern_dimensions.py tests/test_concern_parser.py` — the parser suite must stay green untouched (this child adds no parser code). — PASS 2026-09-01 09:26 auto: python -m pytest tests/test_concern_dimensions.py tests/test_concern_parser.py -> 191 passed in 0.28s
- [x] [t1636_1] `bash tests/run_all_python_tests.sh --test-dir tests`; read only the last line (`PYTHON SUITE: PASSED|FAILED`). — PASS 2026-09-01 09:51 user decision: PASS scoped to t1636. Suite last line is 'PYTHON SUITE: FAILED (1 failed, 6167 passed, 2 skipped)', but every t1636-touched module is green and the sole failure -- test_minimonitor_startup_input_latency::test_mount_returns_while_the_window_probe_is_still_blocked (822ms/595ms vs 500ms; 0.41s in isolation) -- PASSES at pristine HEAD in the same full-lane run. Attributed to t1653's minimonitor_app.py change (+325 lines), which was uncommitted in the shared tree when the A/B ran and LANDED mid-session as 451dd3af7; the tested bytes are now HEAD, so this is a regression in landed code, not in-flight work. No t1636 commit touches that file or that test. Finding routed to a new task against t1653's change, not to t1636.
- [x] [t1636_1] `./.aitask-scripts/aitask_skill_verify.sh` passes. — PASS 2026-09-01 09:26 auto: aitask_skill_verify.sh -> OK (13 templates, 3 agents, 4 stub surfaces; wrapper parity clean)
- [x] [t1636_2] `python -m pytest tests/test_concern_parser.py tests/test_concern_body_display_contract.py tests/test_concern_dimensions.py` — PASS 2026-09-01 09:26 auto: python -m pytest test_concern_parser + test_concern_body_display_contract + test_concern_dimensions -> 209 passed in 3.48s
- [x] [t1636_2] Step 1's class observed passing **before** step 3's first edit (record the run in the Final Implementation Notes). — PASS 2026-09-01 09:26 auto: independently reconstructed, not just read from the notes. Rebuilt the pre-t1636_2 tree (git archive ead279ff0^ of .aitask-scripts/monitor; parser has 0 occurrences of 'improves') and ran HEAD's test file against it: TestFiveFieldProjectionBackCompat -> 5 passed; negative control TestWorsensIsPricedOrUnpriced -> 4 failed (AttributeError on worsens). Matches the run recorded in p1636_2 Final Implementation Notes ('5 passed, 122 deselected').
- [x] [t1636_2] `bash tests/run_all_python_tests.sh --test-dir tests`; read only the last line. — PASS 2026-09-01 09:51 user decision: PASS scoped to t1636. Suite last line is 'PYTHON SUITE: FAILED (1 failed, 6167 passed, 2 skipped)', but every t1636-touched module is green and the sole failure -- test_minimonitor_startup_input_latency::test_mount_returns_while_the_window_probe_is_still_blocked (822ms/595ms vs 500ms; 0.41s in isolation) -- PASSES at pristine HEAD in the same full-lane run. Attributed to t1653's minimonitor_app.py change (+325 lines), which was uncommitted in the shared tree when the A/B ran and LANDED mid-session as 451dd3af7; the tested bytes are now HEAD, so this is a regression in landed code, not in-flight work. No t1636 commit touches that file or that test. Finding routed to a new task against t1653's change, not to t1636.
- [x] [t1636_3] `python -m pytest tests/test_concern_parser.py tests/test_shadow_disposition_surfaces.py` — PASS 2026-09-01 09:26 auto: python -m pytest tests/test_concern_parser.py tests/test_shadow_disposition_surfaces.py -> 175 passed in 0.35s
- [x] [t1636_3] `./.aitask-scripts/aitask_skill_verify.sh` passes. — PASS 2026-09-01 09:26 auto: aitask_skill_verify.sh -> OK (same run as item 3)
- [x] [t1636_3] `bash tests/run_all_python_tests.sh --test-dir tests`; read only the last line. — PASS 2026-09-01 09:51 user decision: PASS scoped to t1636. Suite last line is 'PYTHON SUITE: FAILED (1 failed, 6167 passed, 2 skipped)', but every t1636-touched module is green and the sole failure -- test_minimonitor_startup_input_latency::test_mount_returns_while_the_window_probe_is_still_blocked (822ms/595ms vs 500ms; 0.41s in isolation) -- PASSES at pristine HEAD in the same full-lane run. Attributed to t1653's minimonitor_app.py change (+325 lines), which was uncommitted in the shared tree when the A/B ran and LANDED mid-session as 451dd3af7; the tested bytes are now HEAD, so this is a regression in landed code, not in-flight work. No t1636 commit touches that file or that test. Finding routed to a new task against t1653's change, not to t1636.
- [x] [t1636_4] `python -m pytest tests/test_concern_picker_modal.py tests/test_minimonitor_shadow_pick.py tests/test_concern_body_display_contract.py` — PASS 2026-09-01 09:26 auto: python -m pytest test_concern_picker_modal + test_minimonitor_shadow_pick + test_concern_body_display_contract -> 197 passed in 81.4s
- [x] [t1636_4] `ConcernHelpLineBudgetTests` green untouched. — PASS 2026-09-01 09:26 auto: ConcernHelpLineBudgetTests -> 3 passed, and byte-identical across t1636_4's two commits (extracted the class at 300a80daf vs 1d14bf8f0 -> IDENTICAL; also IDENTICAL at HEAD)
- [x] [t1636_4] `bash tests/run_all_python_tests.sh --test-dir tests`; read only the last line. — PASS 2026-09-01 09:51 user decision: PASS scoped to t1636. Suite last line is 'PYTHON SUITE: FAILED (1 failed, 6167 passed, 2 skipped)', but every t1636-touched module is green and the sole failure -- test_minimonitor_startup_input_latency::test_mount_returns_while_the_window_probe_is_still_blocked (822ms/595ms vs 500ms; 0.41s in isolation) -- PASSES at pristine HEAD in the same full-lane run. Attributed to t1653's minimonitor_app.py change (+325 lines), which was uncommitted in the shared tree when the A/B ran and LANDED mid-session as 451dd3af7; the tested bytes are now HEAD, so this is a regression in landed code, not in-flight work. No t1636 commit touches that file or that test. Finding routed to a new task against t1653's change, not to t1636.
- [x] [t1636_4] Live: real minimonitor companion pane at ~28 and 24 columns (render-level assertion). — PASS 2026-09-01 09:48 auto: LIVE. Real MiniMonitorApp in a real tmux pty (only the 4 tmux-facing seams of action_pick_concerns stubbed); real parse_concerns over a vector-bearing block -> real ConcernPickerModal(narrow=True). Body deliberately long so the three-line row form is exercised (the case p1636_4 records every headless fixture missed). Row widths match trade_profile_rungs.__doc__ exactly: pane 40x30 -> row 28 '   ▲robus ▲verif ▼simpl E:lo' (full rung); pane 30x30 -> row 24 '▲robus +1 ▼simpl E:lo' (rung 1, 2nd improve folded to +1); pane 24x30 -> row 18 '▲robus ▼simpl E:lo' (rungs 4+5, exact 18-of-18 fit). Confirmed both on the composited strips AND on a real 'tmux capture-pane'. Negative control (same block, no trailer vector) renders ZERO profile lines at row 28, so the assertion can fail.
