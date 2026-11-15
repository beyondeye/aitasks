---
priority: medium
effort: medium
depends: [t2278_2]
issue_type: feature
status: Ready
labels: [website, documentation, tui, screenshots]
gates: [risk_evaluated]
anchor: 2278
created_at: 2026-11-15 18:12
updated_at: 2026-11-15 18:12
---

## Context

Child 3 of t2278 (docs TUI screenshot generator). The full design is in the
parent plan `aiplans/p2278_docs_tui_screenshot_generator.md`. Child 2 delivered
the scene spec (`website/screenshots/scene.py`), the registry, backend A
(`website/screenshots/backends/textual_backend.py`) and `capture`.

This child adds partial screenshots (crop) and highlight / annotation overlays,
and delivers the three annotated scenes.

## Key Files to Modify

- `website/screenshots/svgpost.py` (new): works on cell rectangles only.
  - `crop(svg, rect)`: rewrite the `viewBox` to the rectangle and drop the
    window chrome (rounded rect, title, the three dots).
  - `overlay(svg, items)`: append `<rect>` (box or tint) and `<text>` (numbered
    callout, label) elements. Output stays vector.
- `website/screenshots/backends/textual_backend.py`: while the app is still
  mounted, resolve every `crop` and `overlays[].target` selector to a cell
  rectangle from `widget.region`, and pass the rectangles to `svgpost`. A
  selector that matches nothing, or more than one widget, is a capture failure.
- `website/screenshots/scene.py`: validate `crop` (`{selector}` or
  `{cells: [x, y, w, h]}`) and `overlays` (`type: box | tint`, `target`,
  optional `callout: <n>`, optional `label`).
- `website/screenshots/registry.py`: add the `monitor` adapter.
- `website/screenshots/scenes/`: `board_layout_annotated`,
  `board_card_annotated` (crop to one card plus callouts),
  `monitor_layout_annotated`.
- `tests/test_screenshots_svgpost.py` (new).

## Geometry (Rich 15.0.0, fixed)

`char_width = 12.2`, `line_height = 24.4`, `char_height = 20`. The content group
is translated to `(9, 41)`. A cell `(col, row)` is at
`x = 9 + col * 12.2`, `y = 41 + row * 24.4`. Full size: width
`ceil(cols * 12.2 + 16) + 2`, height `rows * 24.4 + 48 + 2`. Overlay elements
are appended after the content group so they draw on top, and must not be
inside its clip path.

## Reference Files for Patterns

- `tests/test_monitor_focus_switch.py:24-25, 36-165`: monitor refuses to mount
  without `$TMUX`. The test pops `TMUX` and `TMUX_PANE`, then after mount sets
  `app._monitor = _FakeMonitor(snapshots)`, `app._snapshots`,
  `app._focused_pane_id`, and calls `app._rebuild_pane_list()`. The monitor
  layout scene must show a pane with a shadow so the preview splits into the
  preview and shadow columns, as the page text describes.
- `tests/lib/monitor_status_scenarios.py`: deterministic `PaneSnapshot` frames.
- Page text the annotations must match: `website/content/docs/tuis/board/_index.md`
  (zones Header, Filter area, Board area, Footer; "Reading a Task Card") and
  `website/content/docs/tuis/monitor/_index.md` (header, session bar, pane
  list, preview / shadow columns, footer).

## Implementation Plan

See `aiplans/p2278/p2278_3_crop_and_overlays.md`.

## Verification Steps

- `bash tests/run_all_python_tests.sh --test-dir tests` passes. The svgpost
  tests assert the exact `viewBox` and overlay coordinates for a known cell
  rectangle, that a cropped SVG has no chrome elements, and that an unmatched
  selector fails the capture.
- A double capture of each annotated scene is byte-identical.
- Open the three staged SVGs: callout numbers sit on the zones the page text
  names, and the cropped card has no window chrome.
