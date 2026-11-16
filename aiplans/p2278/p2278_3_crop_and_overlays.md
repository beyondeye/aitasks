---
Task: t2278_3_crop_and_overlays.md
Parent Task: aitasks/t2278_docs_tui_screenshot_generator.md
Sibling Tasks: aitasks/t2278/t2278_1_*.md, aitasks/t2278/t2278_2_*.md, aitasks/t2278/t2278_4_*.md, aitasks/t2278/t2278_5_*.md, aitasks/t2278/t2278_6_*.md, aitasks/t2278/t2278_7_*.md, aitasks/t2278/t2278_8_*.md
Archived Sibling Plans: aiplans/archived/p2278/p2278_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2278_3: crop and overlays

Design source: `aiplans/p2278_docs_tui_screenshot_generator.md` (revised
2026-11-15: real TUI in tmux, recipes recorded from captures). Read child 2's
archived plan for the primitives, the recipe schema and the manifest.

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
     widths are constants in `svgpost.py`. Overlay coordinates are in the full
     image's pixel space, so a crop applied afterwards still lines up.
   - Order is always overlay, then crop.

2. **Finding rectangles on a live screen.** Extend `find` with what the scenes
   need: the cell of a text, and `--box`, the rectangle of the box-drawing
   border that encloses it. Wide glyphs count as two cells (use
   `rich.cells.cell_len`, the same measure the exporter uses). A text that
   occurs zero times or more than once is an error naming the count.

3. **`shot --crop` / `--overlay`, journal and recipe.** `shot` applies
   `svgpost` after the export. The crop and overlays are journaled with the
   shot, `recipe save` records them, and `recipe.py` validates them (callout
   numbers unique within a scene; rectangles inside the pane).

4. **Scenes, through the discovery workflow.** For each of
   `board_layout_annotated` and `board_card_annotated`: read the page section,
   drive the real board on the sample project, find the rectangles, shot with
   overlays, look at the PNG, then walk it cleanly and `recipe save`. Numbers
   must match the page's own numbered list.

5. **Tests, `tests/test_screenshots_svgpost.py`.** Exact `viewBox` for a known
   rectangle; chrome elements absent after a crop; exact overlay element
   coordinates; overlay-then-crop keeps alignment; an SVG without the expected
   structure raises; `find --box` on a canned screen text (no tmux needed)
   returns the expected rectangle, including a row with a wide glyph before
   the box.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests`.
- `website/screenshots.sh replay --scene board_layout_annotated --scene board_card_annotated`,
  then view the two images in a browser at page width and zoomed.

## Notes for sibling tasks

Record: the rectangle contract (child 4 passes pane rectangles, child 7 maps
them to pixels); the overlay style values; whether text-anchored targets were
added; any page whose text needs numbering to match the callouts.

Post-implementation: Step 9 of the task workflow.
