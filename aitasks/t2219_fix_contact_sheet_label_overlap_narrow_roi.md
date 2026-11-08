---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [python, claudeskills]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1887
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-05 15:34
updated_at: 2026-11-08 10:43
---

## Origin

Spawned from t1893_4 during Step 8b review.

## Upstream defect

- `.aitask-scripts/screen_recording/video_prep.py:372 — sheet_layout()/contact_sheets() (bug and anim sheets) size cells from the image alone, so a narrow --roi gives cells narrower than their labels and labels overlap neighbouring tiles (e.g. anim --roi on a 40x800 strip, 30 per sheet: 45 px cells vs a 69 px "f013 0.483s" label). Layout-level probe only; not run end to end. The sheet-mode fix (core.label_safe_layout + measure_labels) could be reused.`

## Diagnostic context

- ImageMagick `montage` does not widen a cell for a label wider than the cell.
  The label overlaps the neighbouring tiles instead (probed on IM 7.1.2-35).
- `sheet_layout(n, w, h)` picks the cell from the image size and the
  `SHEET_MAX_EDGE` budget only. Probes:
  - `sheet_layout(30, 40, 800)` → `(30, 45, 906)`, i.e. 45 px cells;
  - `magick -pointsize 15 label:'f013 0.483s' -format %w info:` → 69 px.
- Typical full-screen inputs are unaffected (8 bug frames of 450×1000 → 338 px
  cells). Narrow `anim --roi` strips, or many tall frames per sheet, overflow.
- t1893_4 solved this for `sheet` mode:
  - `vp_core.label_safe_layout(n, W, H, need_w, max_edge, label_h)` widens
    cells to the measured label width and letterboxes the image;
  - `vp_core.chunk_sheets` splits into more sheets when a sheet cannot hold N
    tiles with readable labels;
  - `video_prep.measure_labels(texts)` gives the rendered widths in one
    `magick label:` call;
  - `tests/test_screen_recording_cli.py::dirty_borders` detects label pixels in
    the 8 px border between cells.

## Suggested fix

Route `contact_sheets()` through the same machinery:
- measure both label lines;
- use `label_safe_layout` / `chunk_sheets` (the per-sheet count becomes an
  upper bound, and the bug and anim summaries must then list the actual tile
  ranges per sheet);
- add a narrow-ROI anim test using `dirty_borders`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-08T08:43:02Z status=pass attempt=1 type=human
