---
Task: t2278_3_crop_and_overlays.md
Parent Task: aitasks/t2278_docs_tui_screenshot_generator.md
Sibling Tasks: aitasks/t2278/t2278_1_*.md, aitasks/t2278/t2278_2_*.md, aitasks/t2278/t2278_4_*.md, aitasks/t2278/t2278_5_*.md, aitasks/t2278/t2278_6_*.md, aitasks/t2278/t2278_7_*.md, aitasks/t2278/t2278_8_*.md
Archived Sibling Plans: aiplans/archived/p2278/p2278_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-16 12:36
---

# Plan: t2278_3: crop and overlays

## Context

Child 2 shipped the agent-driven capture tool (`website/screenshots/`):
isolated tmux session, real TUI, `shot` → Rich SVG, journal, `recipe save` /
`replay`, batch manifest. `recipe.py` already accepts `crop` / `overlays` but
passes them through unvalidated, and nothing applies them. This child makes
them real: crop an export to a cell rectangle, draw boxes / tints / numbered
callouts / labels on top, record them in recipes, replay them, and deliver the
two annotated board scenes whose markers sit in
`website/content/docs/tuis/board/_index.md`.

Verified against the code (2026-11-16): Rich is 15.0.0 in the framework venv;
template and geometry as the task states (content group
`translate(9, 41)`, cell 12.2 × 24.4; Rich places a row's background at
`row*24.4 + 1.5` inside the group). Two facts the original plan missed:

- The chrome `<rect>` (`fill=#292929`, `stroke=rgba(255,255,255,0.35)`, `rx=8`)
  is also the **default background**. Cells without an explicit background show
  it, so `crop` must replace it with a plain background rect, not just delete it.
- A crop that only rewrites the `viewBox` shows whatever lies beside the
  rectangle. The card scene needs a blank label gutter, so `crop` also clips the
  content group to the rectangle.

**User decision (planning):** the card image points at its fields with
**labels in a right-hand gutter**, using the page's own bold field names
(the page's card field list is a bullet list, not numbered). No page edit. The
layout image uses numbered callouts 1-4, matching the page's numbered list.

**Decision: no text-anchored targets.** Neither scene needs them. Instead a
target may carry `holds: <text>`: the text must lie inside the rectangle on the
exported frame, or the capture fails. That makes a layout shift a replay
failure (repair loop), not a silently misplaced annotation.

## Post-review changes to the plan (2026-11-16)

Two review findings, both verified against the code and folded into step 1,
step 3 and step 6:
1. `svg_export._VIEWBOX_RE` accepts only `viewBox="0 0 W H"`, so every cropped
   preview would fail, and `preview_png` swallows the error with exit 0 →
   `viewbox()` parses any origin; a requested preview that is not produced
   fails the verb.
2. A callout centred on a corner reaches `CALLOUT_R` (12) + stroke past it,
   more than `CROP_PAD` (8), so an interior crop would cut it → the crop
   `viewBox` includes the overlay extent; overlay targets must lie inside the
   crop.
3. The live `replay --png` assertion had no renderer guard, so with the strict
   `--png` it would fail on a tmux machine without Chromium / `rsvg-convert` →
   SVG checks stay unconditional; "preview produced" is its own method with the
   `shutil.which` renderer guard; "preview missing" is tested unconditionally
   by patching the renderer lookup.

## Steps

1. **`website/screenshots/svgpost.py` (new, pure functions on SVG text).**
   - Constants: `CHAR_W = 12.2`, `LINE_H = 24.4`, `ORIGIN = (9, 41)`,
     `ROW_OFFSET = 1.5` (Rich's background offset), `CROP_PAD = 8` px,
     `BOX_INSET = 2` px (adjacent zone boxes stay distinct), `ACCENT`
     (amber, e.g. `#ffc24b`), `STROKE_W = 3`, `TINT_OPACITY = 0.18`,
     `CALLOUT_R = 12`, `LABEL_FONT_PX = 16`, `LEADER_PX = 24`.
   - `cell_rect_to_px((c, r, w, h)) -> (x, y, w, h)`:
     `x = 9 + c*12.2`, `y = 41 + 1.5 + r*24.4`, `w*12.2`, `h*24.4`, rounded to
     2 decimals (one formatting helper used for every emitted number).
   - `_structure(svg)`: locates, each exactly once, the `viewBox`, the chrome
     rect, the title `<text class="…-title">`, the `translate(26,22)` circles
     group, and the content group (`<g transform="translate(9, 41)"
     clip-path="url(#<uid>-clip-terminal)">` up to its closing `</g>`, found by
     walking past the matrix group; no other `<g` may be nested). Any miss or
     duplicate raises `SvgPostError` naming what was not found — never a
     half-processed file.
   - `overlay(svg, items) -> svg`: one `<g class="shot-overlay">` inserted
     right after the content group's closing tag (outside its clip path).
     Per item, coordinates in full-image px:
     - `box` → `<rect>` stroked `ACCENT`, `fill="none"`, inset `BOX_INSET`;
     - `tint` → `<rect>` filled `ACCENT` at `TINT_OPACITY`, no stroke;
     - `anchor` → nothing over the rectangle (callout / label only);
     - `callout: n` → filled circle at the rect's top-left corner (centre
       clamped to stay inside the image) with the number, bold, dark text;
     - `label` → a leader line from the rect's right edge (`LEADER_PX` long,
       at the rect's vertical middle) and the text after it; text is
       XML-escaped.
   - `overlay_extent(items) -> (x0, y0, x1, y1)`: the px bounding box of every
     element `overlay` draws (box/tint rects incl. half the stroke, callout
     circles incl. stroke, leader lines, label text estimated as
     `len(label) * LABEL_FONT_PX * 0.61` wide — the label font is Fira Code,
     the same 0.61 aspect Rich uses — and `LABEL_FONT_PX` high). Computed from
     the same geometry helpers `overlay` uses, so the two cannot disagree.
   - `crop(svg, rect_cells, gutter=0, extent=None) -> svg`: the content area is
     the rectangle plus `CROP_PAD` on each side; the `viewBox` is the union of
     that area plus `gutter*CHAR_W` on the right **and** `extent` (when given)
     plus `CROP_PAD`, so no annotation is ever cut off (a callout centred on a
     corner reaches `CALLOUT_R` + stroke past it, more than `CROP_PAD`). Chrome
     rect, title and circles removed; a plain background rect (the chrome's own
     fill) covering the whole viewBox put where the chrome was; the content
     group wrapped in `<g clip-path="url(#<uid>-clip-crop)">` whose clipPath
     (added to `<defs>`) is the padded rectangle only — never widened by the
     gutter or the extent, so a neighbouring column never shows. Applying
     `crop` to an already-cropped SVG raises (no chrome found).
   - `postprocess(svg, crop=None, overlays=())`: the only entry point the CLI
     uses; always overlay first, then crop with
     `extent=overlay_extent(overlays)` (overlay coordinates are full-image px,
     so they line up either way, and the order is fixed in one place). In an
     uncropped image the callout centre stays clamped inside the image.

   **PNG previews of cropped SVGs (`website/screenshots/svg_export.py`).**
   `render_png` reads the size with `_VIEWBOX_RE = viewBox="0 0 W H"`, so a
   cropped SVG (non-zero origin) raises `ExportError("no viewBox …")` — checked
   in the code. Replace it with `viewbox(svg) -> (x, y, w, h)` accepting any
   four numbers (signed, decimal), and size the browser window from `w, h`.
   And `shot --png` / `replay --png` must not report success without a
   preview: `preview_png` returns whether it produced one, and a requested
   preview that could not be produced makes the verb exit 1 with
   `FAILED:png|<reason>` (the staged SVG stays, the message says so;
   `PNG_UNAVAILABLE:` remains the line for a missing renderer and is also
   exit 1 when `--png` was asked).

2. **Rectangles on the screen (`website/screenshots/session.py`).** Pure
   functions on plain screen rows, so they are testable without tmux and run on
   the exact frame that gets exported:
   - `cell_grid(line)`: a list indexed by cell column (a wide glyph fills two
     cells; zero-width characters join the previous cell), using
     `rich.cells.cell_len`, the exporter's measure.
   - `find_in_rows(rows, text)`; `find()` becomes a wrapper over it (same
     output as today).
   - `box_around(rows, text) -> (c, r, w, h)`: the text must occur exactly
     once (else `SessionError` naming the count); from its first cell scan left
     for the nearest vertical box-drawing glyph, follow that column up to a
     top-left corner and down to a bottom-left corner, follow the top row right
     to the top-right corner, and check the bottom-right corner; returns the
     rectangle including the border. Innermost box wins. No closed box is an
     error.
   - `rect_holds(rows, rect, text) -> bool`: `text` occurs with every cell
     inside `rect`.
   - CLI: `find <id> --text T --box` prints `BOX:c,r,w,h` (exit 1 with the
     reason otherwise).

3. **Schema and validation (`website/screenshots/recipe.py`).**
   ```yaml
   crop: {cells: [c, r, w, h], gutter: 34, holds: t12 add checkout page}
   overlays:
     - {type: box, target: {cells: [0, 0, 126, 1], holds: aitasks board}, callout: 1}
     - {type: anchor, target: {cells: [2, 7, 36, 1]}, label: Info line}
   ```
   - `validate_crop(value, size)` / `validate_overlays(value, size)`, shared
     by the loader and by `shot` (so a shot can only journal what a recipe
     accepts). Rules: unknown keys are errors; `cells` four ints, `w, h ≥ 1`,
     inside the pane; `gutter` int 0-200 (crop only); `holds` one-line text;
     `type` in `box | tint | anchor`; `callout` int 1-99, unique in the scene;
     `label` one-line text; an `anchor` needs a callout or a label; when a
     `crop` is given, every overlay target lies inside the crop rectangle (an
     annotation on cropped-away content is an error, not an invisible mark).
   - Normalised values (tuples) are stored on `Recipe`; `dump` writes them back
     in the schema form; `from_session` copies them from the scene's last
     `shot` journal entry. Module docstring documents the schema.

4. **`shot` / `replay` apply them (`website/screenshots/cli.py`).**
   - `shot --crop SPEC --overlay SPEC…` (repeatable). `SPEC` is YAML flow
     (parsed with `yaml.safe_load`, the recipe form); `--crop` also accepts
     `c,r,w,h`. Validated with step 3's functions before anything is captured.
   - `export(sess, title, scene, expect, crop, overlays)`: on the settled frame
     it already checks `expect` on, it also checks every `holds`, then
     `ansi_to_svg` → `svgpost.postprocess`. A `holds` miss is
     `FAILED:<scene>|overlay|…` on replay (stages nothing, keeps the session as
     for other failures) and `FAILED:overlay|…` on `shot`.
   - The `shot` journal entry records `crop` / `overlays` in schema form;
     `replay_one` passes `rec.crop` / `rec.overlays`. `recipe save`'s
     fresh-replay gate therefore covers them.
   - Docstring verb table updated.

5. **Scenes, through the discovery workflow** (126x44, dataset `base`, as the
   existing recipe). For each: read the page section, drive the real board,
   `screen` / `find --box`, shot with `--png`, look at the PNG, adjust, then
   walk cleanly in a fresh session and `recipe save`.
   - `board_layout_annotated` (`aitasks_board_layout_annotated.svg`): full
     image, four `box` overlays with callouts 1 Header, 2 Filter area, 3 Board
     area, 4 Footer, each with a `holds` text from that zone.
   - `board_card_annotated` (`aitasks_board_card_annotated.svg`): crop to the
     t12 card (`find --box`) with a gutter; `anchor` + `label` per visible
     field row, labels in the page's words: "Mark / Task number and title",
     "Info line", "Status line", "Children count". The leader must not cover
     text (check the PNG; adjust `LEADER_PX` / start point if it does).
   - Check `python3 website/check_screenshots.py`: both scenes now have a spec
     and no ownership problem. Markers stay unresolved (child 5 applies them).

6. **Tests.**
   - `tests/test_screenshots_svgpost.py` (new, no tmux): build SVGs with
     `svg_export.ansi_to_svg` from canned captures.
     - `cell_rect_to_px` exact values; crop of a known rectangle gives the exact
       `viewBox` (with and without gutter); after crop there is no chrome rect,
       no title, no circle; the background rect has the chrome's fill; the
       crop clipPath exists and wraps the content group; `svg_plain_text`
       still reads the content.
     - Overlay elements have exact coordinates (box with inset, tint opacity,
       callout circle centre and number, label leader and text, escaping of
       `<` / `&`); the overlay group sits after the content group, outside its
       clip path; overlay-then-crop keeps the overlay coordinates identical.
     - **Annotation extents:** a crop of an interior rectangle whose target
       has a numbered callout at the crop's top-left corner yields a `viewBox`
       that contains the whole circle (centre − `CALLOUT_R` − stroke ≥ viewBox
       origin), while the crop clipPath stays the padded rectangle; a label
       longer than the gutter widens the `viewBox` to its estimated end.
       Control: the same crop without the overlays has the plain padded
       `viewBox`.
     - **Previews:** `viewbox()` parses a cropped `viewBox` (non-zero and
       negative origin, decimals); `render_png` of a cropped SVG writes a PNG
       of the `viewBox` size (skipped only when no renderer is installed —
       the skip probe is `shutil.which`, never the code under test).
     - An SVG missing a structural element (circles group removed; content
       group duplicated; a non-Rich SVG) raises; cropping twice raises.
     - `box_around` on canned rows: the expected rectangle, including a row
       with a wide glyph before the box and a nested box (innermost wins);
       zero and two occurrences raise naming the count; an unclosed box
       raises. `rect_holds` true and false cases.
   - `tests/test_screenshots_recipe.py`: valid crop / overlays round-trip
     through `write` / `load`; each rejection rule (unknown key, out-of-pane
     rect, bad gutter, duplicate callout, bad type, bare anchor) raises
     `RecipeError`; `from_session` copies crop / overlays from the shot entry.
   - `tests/test_screenshots_session_live.py` (already serial): the two
     shipped recipes replay and their staged SVGs carry the overlay group (and
     the card one the cropped `viewBox`) — these SVG checks run without
     `--png` and stay unconditional whenever tmux is available. Preview
     checks are separate test methods:
     - *Preview produced* — its own method, guarded by the same
       `shutil.which`-based renderer probe as the standalone `render_png`
       test (skip when none of the browsers nor `rsvg-convert` is on `PATH`):
       `replay --png` of the card recipe prints a `PNG:` line whose file
       exists (the cropped preview is really produced, not only exit 0).
     - *Preview missing* — unconditional on any tmux machine: `cli.main` runs
       in-process, so the test patches `svg_export.shutil.which` to find no
       renderer; `replay --png` then exits 1 with `PNG_UNAVAILABLE:`, and the
       SVG is still staged in the batch.
     And a copy of the layout recipe whose
     `holds` names a text outside its rectangle fails with
     `FAILED:<scene>|overlay|…` and stages nothing (control: the unmodified
     copy passes in the same test); `find --box` on the live board returns the
     t12 card rectangle.
   - Mutants on an isolated copy (not the shared tree): drop the background
     rect in `crop`, drop the crop clip, skip the `holds` check, place the
     overlay group inside the content group, ignore `extent` in `crop`,
     restore the `0 0`-only viewBox regex, swallow a failed preview with exit
     0. Each must fail a test.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests`; read the last line.
- `website/screenshots.sh replay --scene board_layout_annotated --scene board_card_annotated --png`
  passes in fresh sessions and prints a `PNG:` line for each scene (open those
  files: they are the cropped and uncropped previews); then
  `website/screenshots.sh session list` is empty.
- Open both staged images in a browser at page width and zoomed: callout
  numbers 1-4 sit on the zones the page names; the cropped card has no window
  chrome, no neighbouring column, and the labels sit in the gutter. Show them
  to the user.
- `python3 website/check_screenshots.py`.
- `shellcheck website/screenshots.sh` (unchanged, sanity).

## Notes for sibling tasks (fill in at the end)

Record: the rectangle contract (cells `[c, r, w, h]` in pane coordinates,
inclusive of borders; child 4 passes window-wide rectangles, child 7 maps
them to pixels); overlay style constants; that text-anchored targets were not
added and `holds` was; that no page needed renumbering (card uses labels).

Post-implementation: Step 9 of the task workflow.

## Risk

### Code-health risk: low
- `crop` depends on the exact structure of Rich 15.0.0's SVG template; a Rich
  upgrade could change it · severity: low · → mitigation: none needed;
  `_structure` fails loudly on any mismatch and step 6 tests a missing element
- `--png` becoming strict changes the exit status of `shot` / `replay` on a
  machine without a renderer · severity: low · → mitigation: none needed;
  only when `--png` was explicitly asked, and the message names the cause
- Changing `export()` / `replay_one` signatures touches the code path the
  existing recipe uses · severity: low · → mitigation: none needed; crop and
  overlays default to none, and the existing live tests (shipped recipe replay)
  stay in the suite

### Goal-achievement risk: medium
- Cell rectangles can drift when the layout changes and annotations would point
  at the wrong zone · severity: medium · → mitigation: none needed; every
  target in the two scenes carries `holds`, which turns drift into a replay
  failure (step 4, tested in step 6)
- Callouts / leaders may cover text the image is meant to show, or look poor
  at page width · severity: medium · → mitigation: none needed; step 5 looks
  at the PNG of every shot and the user reviews both images
- Emoji whose terminal width differs between tmux and Rich could shift the
  computed columns on a row · severity: low · → mitigation: none needed;
  `box_around` scans vertically on the border column, and `holds` /
  the PNG check catch a misplaced rectangle

No separate mitigation is proposed: each risk is covered by a step of this
plan.

## Implementation log

- **Steps 1-6 done (2026-11-16).** Deviations found by looking at the first
  PNG previews of the real board (step 5), applied before any recipe was saved:
  - **Callout placement.** A callout on the rectangle's top-left corner covered
    the content it numbered (the header's `⭘`, the `T` of "Task filter") and
    was too small at page width. Callouts now sit **outside** the rectangle,
    left of it, at its vertical middle (`CALLOUT_R` 17, `CALLOUT_FONT_PX` 22),
    and the image grows to take them in: `svgpost.grow` widens an uncropped
    `viewBox` (the added margin is transparent, so callouts sit beside the
    window on the page); a crop already took the extent in. The "clamp inside
    the image" rule of the plan is gone with it.
  - **Crop clip.** Clipping to the rectangle *plus* `CROP_PAD` showed slivers
    of the column header and the column border around the card. The clip is
    now exactly the rectangle; `CROP_PAD` is plain background in the
    `viewBox` only.
- **Bug caught by a test:** `cell_grid` measured `🏷` and its VS16 one
  character at a time (1 + 0 cells) while Rich, and so `find_in_rows`,
  measures the pair as 2. Zero-width characters now join the previous
  character and the cluster is measured as a whole.
- Recipe files write cell rectangles in flow style (`cells: [2, 6, 38, 6]`).
  The two new recipes were re-dumped once through `recipe.dump` after that
  change, with a check that each loads back equal to the recipe that was
  saved; then replayed from the shipped files.

## Post-Review Changes

### Change Request 1 (2026-11-16 12:30)
- **Requested by user:** four review findings, each reproduced before fixing:
  (1) label extents used `len(label) * LABEL_CHAR_W` while the renderer draws
  real glyph widths, so a CJK or emoji label overflowed the `viewBox`
  (measured 380.3 vs 288.6); (2) `cell_grid` joined zero-width characters to
  the previous code point only, so `👩‍💻` measured 4 cells instead of Rich's 2
  and `box_around` failed beside it; (3) `box_around` gave up on the nearest
  vertical glyph, so an inner box beside the text hid the enclosing box;
  (4) `box_around` never checked the right edge or the bottom edge between
  the corners, so open boxes were accepted.
- **Changes made:** (1) `svgpost.label_width(label)` = Rich cell width ×
  `LABEL_CHAR_W`, and every label is drawn with that width as `textLength`
  (`lengthAdjust="spacingAndGlyphs"`), so the renderer fits it to exactly the
  width the extent assumes; (2) `cell_grid` builds cells from
  `rich.cells.split_graphemes` spans; (3) every vertical glyph left of the
  text is tried as a left border, nearest first, until one closes into a box
  holding the whole text; (4) `_closed_box` checks all four border runs and
  corners. Tests: a rendered-bound check in headless Chromium (`getBBox` of
  each label, one label per image so a longer one cannot mask an overflow,
  for CJK, emoji and ASCII) plus a `label_width` unit check; the ZWJ box; an
  inner box beside the text; negatives for gaps in the right, bottom and top
  edges and a box too narrow for the text, with a closed-box control. Six
  mutants (no `textLength`; width by `len()`; per-code-point grid; first
  vertical only; no bottom-edge check; no right-edge check) and the original
  defect (`len()` without `textLength`) were all killed on an isolated copy.
- **Files affected:** `website/screenshots/svgpost.py`,
  `website/screenshots/session.py`, `tests/test_screenshots_svgpost.py`.

## Final Implementation Notes
- **Actual work done:**
  - `website/screenshots/svgpost.py` (new): `cell_rect_to_px`, `overlay`
    (box / tint / anchor; numbered callouts; labels with a leader),
    `overlay_extent`, `label_width`, `crop` (exact-rectangle clip, plain
    background, `CROP_PAD`, `gutter`, grows to the overlay extent), `grow`
    (uncropped images widen to take in callouts), `postprocess` (the only
    entry point: overlay, then crop or grow), `viewbox`.
  - `session.py`: `cell_grid` (Rich grapheme spans), `find_in_rows`,
    `box_around` (innermost closed box, all four edges checked),
    `rect_holds`; `find` wraps `find_in_rows`.
  - `recipe.py`: `validate_crop` / `validate_overlays` (shared by the loader
    and `shot`), normalised values on `Recipe`, `from_session` copies them from
    the shot, cell rectangles dumped in flow style; schema in the docstring.
  - `cli.py`: `shot --crop/--overlay`, `find --box` (`BOX:c,r,w,h`), `export`
    checks `holds` on the exported frame (`FAILED:<scene>|overlay|…` on
    replay, `FAILED:overlay|…` on shot), strict `--png` (exit 1 without a
    preview).
  - `svg_export.py`: `render_png` sizes the window from any `viewBox` origin.
  - Scenes `board_layout_annotated` and `board_card_annotated`, recorded
    through the tool and replayed.
  - Tests: `tests/test_screenshots_svgpost.py` (27, new),
    `test_screenshots_recipe.py` (+5), `test_screenshots_session_live.py`
    (+5 in `AnnotatedSceneTests`).
- **Deviations from plan:** callouts sit left of their rectangle (outside),
  not on its top-left corner, and the image grows to take them in; the crop
  clip is the exact rectangle, the pad is background only (both from the
  first PNG previews, see the implementation log); labels are drawn with
  `textLength` (review finding 1).
- **Issues encountered:** `cell_grid` disagreed with Rich on VS16 and ZWJ
  sequences (fixed with `split_graphemes`); see "Post-Review Changes" for the
  four review findings. Headless Chromium aborts (SIGABRT) when `TMPDIR` is a
  very long path, so preview tests fail under such a `TMPDIR`; with the
  default one they pass. The first full-suite run failed in its parallel lane
  with output lost to a `| tail`; the two runs after it passed in full
  (12411 + 39, then 12415 + 39).
- **Key decisions:** no text-anchored targets; `holds` instead, so a layout
  shift fails a replay rather than misplacing an annotation. The card uses
  labels in a gutter in the page's own words (user decision), so no page was
  renumbered. Overlay targets must lie inside the crop.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - **Rectangle contract:** `[column, row, width, height]` in pane cells,
    border cells included, `(0, 0)` = the pane's top-left. `find --box --text
    T` returns the innermost closed box around a unique text. Child 4
    (multi-pane) should pass window-wide cell rectangles in the same form;
    child 7 maps the same cells to pixels with its window size ÷ cols×rows.
  - **Schema:** `crop: {cells, gutter?, holds?}`; `overlays: [{type: box |
    tint | anchor, target: {cells, holds?}, callout?: 1-99 unique, label?}]`.
    Every target carries a `holds` text in the shipped scenes; do the same.
  - **Style constants** (`svgpost.py`): `ACCENT #ffc24b`, `INK #1e1e1e`,
    `STROKE_W 3`, `BOX_INSET 2`, `TINT_OPACITY 0.18`, `CALLOUT_R 17`,
    `CALLOUT_FONT_PX 22`, `LABEL_FONT_PX 16`, `LEADER_PX 24`, `CROP_PAD 8`.
  - **Uncropped images with callouts are wider than the window** (transparent
    left margin): the page shows the callouts beside the window.
  - **Box finding needs four drawn edges:** a border with a title in its top
    run (`╭─ Title ─╮`) is not a closed box; use `screen` and give cells.
  - Preview checks: `shot`/`replay --png` now fail when no PNG is produced;
    child 5's skill should treat `PNG_UNAVAILABLE:` as "look at the SVG".
