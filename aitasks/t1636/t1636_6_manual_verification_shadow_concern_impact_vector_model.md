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
updated_at: 2026-09-01 09:15
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1636_1] `python -m pytest tests/test_concern_dimensions.py tests/test_concern_parser.py` — the parser suite must stay green untouched (this child adds no parser code).
- [ ] [t1636_1] `bash tests/run_all_python_tests.sh --test-dir tests`; read only the last line (`PYTHON SUITE: PASSED|FAILED`).
- [ ] [t1636_1] `./.aitask-scripts/aitask_skill_verify.sh` passes.
- [ ] [t1636_2] `python -m pytest tests/test_concern_parser.py tests/test_concern_body_display_contract.py tests/test_concern_dimensions.py`
- [ ] [t1636_2] Step 1's class observed passing **before** step 3's first edit (record the run in the Final Implementation Notes).
- [ ] [t1636_2] `bash tests/run_all_python_tests.sh --test-dir tests`; read only the last line.
- [ ] [t1636_3] `python -m pytest tests/test_concern_parser.py tests/test_shadow_disposition_surfaces.py`
- [ ] [t1636_3] `./.aitask-scripts/aitask_skill_verify.sh` passes.
- [ ] [t1636_3] `bash tests/run_all_python_tests.sh --test-dir tests`; read only the last line.
- [ ] [t1636_4] `python -m pytest tests/test_concern_picker_modal.py tests/test_minimonitor_shadow_pick.py tests/test_concern_body_display_contract.py`
- [ ] [t1636_4] `ConcernHelpLineBudgetTests` green untouched.
- [ ] [t1636_4] `bash tests/run_all_python_tests.sh --test-dir tests`; read only the last line.
- [ ] [t1636_4] Live: real minimonitor companion pane at ~28 and 24 columns (render-level assertion).
