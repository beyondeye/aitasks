---
Task: t2278_3_crop_and_overlays.md
Parent Task: aitasks/t2278_docs_tui_screenshot_generator.md
Sibling Tasks: aitasks/t2278/t2278_1_*.md, aitasks/t2278/t2278_2_*.md, aitasks/t2278/t2278_4_*.md, aitasks/t2278/t2278_5_*.md, aitasks/t2278/t2278_6_*.md, aitasks/t2278/t2278_7_*.md, aitasks/t2278/t2278_8_*.md
Archived Sibling Plans: aiplans/archived/p2278/p2278_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2278_3 — crop and overlays

Design source: `aiplans/p2278_docs_tui_screenshot_generator.md`. Read child 2's
archived plan for the adapter interface and the pinned look.

## Steps

1. **`svgpost.py`, pure functions on SVG text and cell rectangles.**
   - Constants: `CHAR_W = 12.2`, `LINE_H = 24.4`, `ORIGIN = (9, 41)`.
   - `cell_rect_to_px(rect) -> (x, y, w, h)`.
   - `crop(svg, rect)`: set `viewBox` to the pixel rectangle; remove the chrome
     (the rounded background rect, the title text, the three circles) and keep
     the content group and its clip path. Find them by their fixed structure in
     Rich's template (`rich/_export_format.py`), and fail loudly if the
     structure is not found rather than emitting a half-cropped file.
   - `overlay(svg, items)`: append one `<g class="shot-overlay">` after the
     content group. `box` → stroked `<rect>`; `tint` → semi-transparent filled
     `<rect>`; `callout: n` → a filled circle with the number at the rect's
     top-left corner; `label` → text beside the callout. Colours and stroke
     widths come from `registry.LOOK`. Overlay coordinates are in the full
     image's pixel space, so a crop applied afterwards still lines up.
   - Order is always overlay, then crop.

2. **Region resolution in backend A.** After settle and before export, for each
   `crop.selector` and `overlays[].target.selector`, `app.screen.query(selector)`
   must match exactly one widget; take `widget.region` (x, y, width, height in
   cells, screen coordinates). Zero or several matches raise a capture error
   naming the selector. `{cells: [...]}` targets pass through. Return the
   rectangles in `CaptureResult.regions`; `cli capture` calls `svgpost`.

3. **`scene.py` validation** for `crop` and `overlays` (see the task file).
   Callout numbers within a scene must be unique.

4. **`monitor` adapter.** Pop `TMUX` / `TMUX_PANE` for the duration, build
   `MonitorApp` with `rename_window=False, mark_pane=False`, and after mount
   inject fake snapshots the way `tests/test_monitor_focus_switch.py:148-165`
   does. Use deterministic snapshots (see `tests/lib/monitor_status_scenarios.py`),
   including one agent with a shadow so the preview splits into two columns.
   Restore the environment on exit.

5. **Scenes.** `board_layout_annotated` (four callouts: header, filter area,
   board area, footer), `board_card_annotated` (crop to one card; callouts for
   the card parts the page's "Reading a Task Card" section names),
   `monitor_layout_annotated` (header, session bar, pane list, preview column,
   shadow column, footer). The callout numbers must match the numbered lists in
   the page text; if the page has no numbering, note it for child 5, which
   edits those pages.

6. **Tests, `tests/test_screenshots_svgpost.py`.** Exact `viewBox` for a known
   rect; exact overlay `x` / `y` / `width` / `height`; cropped output has no
   chrome elements and is still well-formed XML (`xml.etree`); overlay-then-crop
   keeps overlays aligned; an unmatched selector and a multi-match selector both
   fail the capture; a monitor adapter capture contains expected text; double
   capture is byte-identical.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests`.
- `website/screenshots.sh capture --scene board_layout_annotated --scene board_card_annotated --scene monitor_layout_annotated`,
  then view the three SVGs in a browser at page width and zoomed.

## Notes for sibling tasks

Record: the `regions` contract (child 4 fills it with pane rectangles, child 7
maps it to pixels); the overlay style values; any page whose text needs
numbering to match the callouts.

Post-implementation: Step 9 of the task workflow.
