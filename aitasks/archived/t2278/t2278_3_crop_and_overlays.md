---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: [t2278_2]
issue_type: feature
status: Done
labels: [website, documentation, tui, screenshots]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2278
implemented_with: claudecode/opus5_5
created_at: 2026-11-15 18:12
updated_at: 2026-11-16 15:31
completed_at: 2026-11-16 15:31
---

## Context

Child 3 of t2278 (docs TUI screenshot generator). Read the parent plan
`aiplans/p2278_docs_tui_screenshot_generator.md` first; the design was revised
on 2026-11-15 to an agent driving the real TUI in an isolated tmux session.
Child 2 delivered the sample project, the session primitives
(`website/screenshots/session.py`), the SVG export, recipes and the batch
manifest. Read child 2's archived plan for the primitives and schemas as
implemented.

This child adds partial screenshots (crop) and highlight / annotation
overlays, and delivers two annotated scenes.

There are no widget selectors in this design: the TUI runs in a real pane, so
crops and overlays are **cell rectangles**. The agent finds them on the
screen with the `find` verb and by reading `screen` output.

## Key Files to Modify

- `website/screenshots/svgpost.py` (new): works on cell rectangles only.
  - `crop(svg, rect)`: rewrite the `viewBox` to the rectangle and drop the
    window chrome (rounded rect, title, the three dots).
  - `overlay(svg, items)`: append `<rect>` (box or tint) and `<text>` (numbered
    callout, label) elements. Output stays vector.
- `website/screenshots/session.py` / `cli.py`: `find` gains what the two
  scenes need (for example `--box` to return the rectangle of the bordered
  box around a text). `shot` takes `--crop x,y,w,h` and `--overlay` items and
  journals them, so `recipe save` records them.
- `website/screenshots/recipe.py`: validate `crop: {cells: [x, y, w, h]}` and
  `overlays` (`type: box | tint`, `target: {cells: [...]}`, optional
  `callout: <n>`, optional `label`). Optionally a target may be
  `{text: "...", box: true}`, resolved at replay time with `find`, so a recipe
  survives a layout shift; decide this from what the two scenes need.
- `website/screenshots/scenes/`: `board_layout_annotated`,
  `board_card_annotated` (crop to one card plus callouts), recorded through
  the tool.
- `tests/test_screenshots_svgpost.py` (new).

## Geometry (Rich 15.0.0, fixed)

`char_width = 12.2`, `line_height = 24.4`, `char_height = 20`. The content group
is translated to `(9, 41)`. A cell `(col, row)` is at
`x = 9 + col * 12.2`, `y = 41 + row * 24.4`. Full size: width
`ceil(cols * 12.2 + 16) + 2`, height `rows * 24.4 + 48 + 2`. Overlay elements
are appended after the content group so they draw on top, and must not be
inside its clip path.

## Reference Files for Patterns

- Page text the annotations must match:
  `website/content/docs/tuis/board/_index.md` (zones Header, Filter area,
  Board area, Footer; "Reading a Task Card").
- `rich/_export_format.py`: the SVG template whose fixed structure `crop`
  relies on.
- `website/screenshots/svg_export.py` (child 2): how the SVG is produced.

## Implementation Plan

See `aiplans/p2278/p2278_3_crop_and_overlays.md`.

## Verification Steps

- `bash tests/run_all_python_tests.sh --test-dir tests` passes. The svgpost
  tests assert the exact `viewBox` and overlay coordinates for a known cell
  rectangle, and that a cropped SVG has no chrome elements.
- `website/screenshots.sh replay --scene board_layout_annotated --scene
  board_card_annotated` passes in fresh sessions.
- Open the two staged images: callout numbers sit on the zones the page text
  names, and the cropped card has no window chrome.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-16T10:37:11Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-16T13:04:05Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-16T13:31:13Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:e0aedcf3fa3b03be

> **✅ gate:risk_evaluated** run=2026-11-16T13:31:13Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2278_3/risk_evaluated_2026-11-16T13:31:13Z-risk_evaluated-a1.log`
