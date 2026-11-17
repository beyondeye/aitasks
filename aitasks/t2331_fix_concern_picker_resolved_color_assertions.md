---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tests, test_infrastructure]
gates: [risk_evaluated]
anchor: 2295
followup_kind: upstream_defect
created_at: 2026-11-17 22:59
updated_at: 2026-11-17 22:59
---

## Origin

Spawned from t2295 during Step 8b review.

## Upstream defect

Two pre-existing resolved-color assertions fail in `tests/test_concern_picker_modal.py`:

- `test_the_resolved_colours_are_pinned` (line 3694 at discovery).
- `test_the_ramp_survives_every_row_state_that_recolours_its_text` (line 3723 at discovery).

Both report expected `#ff0000` versus actual `#363636`. Diagnose whether the defect is in resolved styling or in the test expectations, and fix it while preserving meaningful color-ramp coverage.

## Diagnostic context

The same two failures occurred in the full Python suite before and after t2295's temporary-resource cleanup changes. The combined parallel and serial runs yielded 12,573 passed, 7 skipped, and these 2 failures. t2295 did not modify this test file. This establishes that the failures predate its changes; the underlying cause has not been diagnosed.

Local diagnostic logs from that run, if still available: `/tmp/t2295-evidence/python-before.log` and `/tmp/t2295-evidence/python-after.log`. The final implementation notes in t2295's archived plan also record the baseline findings.

## Acceptance criteria

- Reproduce and explain both failures, distinguishing incorrect expectations from an actual styling regression.
- Correct the responsible code or fixtures without weakening the intended resolved-color and row-state assertions.
- Run the relevant concern-picker tests and report the result.
