---
Task: t2219_fix_contact_sheet_label_overlap_narrow_roi.md
Base branch: main
Output branch: main
---

# t2219 — Contact-sheet labels overlap neighbouring tiles on narrow cells (bug / anim)

## Context

`contact_sheets()` (`.aitask-scripts/screen_recording/video_prep.py:396`), used by
`bug` and `anim`, sizes each cell from the image alone via `sheet_layout()`.
ImageMagick `montage` never widens a cell for a wider label, so a narrow
`anim --roi` strip (40x800, 30 a sheet → 45 px cells vs a 69 px `f013 0.483s`
label) or many tall frames a sheet draws labels over the neighbouring tiles.
`sheet` mode already solved this (t1893_4) with `measure_labels()`,
`vp_core.label_safe_layout()` and `vp_core.chunk_sheets()`. This task routes
`contact_sheets()` through that same machinery and makes the bug and anim
summaries list the frames each sheet actually holds. The per-sheet count then
becomes an upper bound.

Probe (current code, read-only): typical inputs keep their exact layout. 30 of
360x800 → (8 cols, 158, 352) both ways; 8 of 450x1000 → (4, 338, 752) both ways;
30 of 800x360 / 800x800 / 200x800 are unchanged. Only the narrow and overfull
cases change: 30 of 40x800 goes from 30 cols x 45 px to 15 cols x 75 px, and
40 of 450x1000 goes from 152 px to 200 px cells when the labels need 200 px. No
consumer assumes `per_sheet` arithmetic except the bug summary itself
(`video_prep.py:1291-1294`). `vp_pick` reads `run.json["mode"]` and `frames/`
only. Only the Claude tree has the skill doc: the `.agents`/`.opencode` copies
are thin wrappers, so nothing needs porting.

## Implementation

### 1. `video_prep.py` — shared label-safe sheet drawing

- **Move up** `SHEET_POINTSIZE`, `SHEET_LABEL_H`, `SHEET_LABEL_MARGIN` and
  `measure_labels()` from the "sheet mode" section (`:1832-1855`) to sit just
  above `contact_sheets()`, because they are now shared. This is a pure move.
  Reword the `SHEET_LABEL_H` comment to "two label lines at SHEET_POINTSIZE".
- **New helper** `checked_sheet_size(path) -> (w, h)`. It contains the PNG-size
  check from `cmd_sheet` (`:2003-2007`): `core.png_size`, then `PrepError` when
  the size is None or over `SHEET_MAX_EDGE`, with the same message. `cmd_sheet`
  calls it instead of the inline block, so there is one copy.
- **Remove `sheet_layout()`**: it is dead after the rewrite.
- **Rewrite `contact_sheets(items, out_dir, per_sheet, w, h, prefix="sheet")`**.
  It returns `(path, start, count, reduced, cols, cell_w)` per sheet, where
  `start` indexes `items`:
  ```python
  labels = [label.replace("%", "pct") for _, label in items]   # drawn text, unchanged
  split = [lab.split("\n") for lab in labels]
  flat = [ln for ls in split for ln in ls if ln]
  widths = iter(w for w, _ in measure_labels(flat))
  need = []
  for ls in split:                       # widest line of each label, + margin
      need.append(max([next(widths) for ln in ls if ln] or [0]) + SHEET_LABEL_MARGIN)
  try:
      chunks = core.chunk_sheets([(w, h)] * len(items), per_sheet, need,
                                 SHEET_MAX_EDGE, SHEET_LABEL_H)
  except ValueError as exc:
      raise PrepError(str(exc)) from exc
  for n, (start, count, reduced, (cols, cell_w, th, _)) in enumerate(chunks, 1):
      montage ... "-pointsize", str(SHEET_POINTSIZE),
              per item: "-label", core.im_label(label), str(path)
              "-tile", f"{cols}x", "-geometry", f"{cell_w}x{th}+4+4", out
      checked_sheet_size(out)
      sheets.append((out, start, count, reduced, cols, cell_w))
  ```
  Measured text = drawn text: `measure_labels` applies `core.im_label` itself,
  and the montage label goes through `core.im_label` too. The labels contain no
  backslashes, so what is drawn does not change. Keep the early `return []`
  when there are no items or no `magick`. Update the docstring: at most
  `per_sheet` a sheet, fewer where labels would not fit; an image narrower
  than its cell is letterboxed.

### 2. `bug` (`_cmd_bug`)

- `token_estimate([s[0] for s in sheets])`.
- Summary "Contact sheets": for each sheet,
  `- <path>: frames #<rows[start][0]>-#<rows[start+count-1][0]>`. These are the
  actual ranges, no longer `s_i * per_sheet` arithmetic. When any sheet is
  `reduced`, add `- note: --per-sheet N does not fit with readable labels (at
  most M frames a sheet here)`, the same wording as the sheet mode's warning.
- `run.json`: `"sheets"` stays the list of paths, because `vp_pick` and the
  tests read it. Add `"sheet_tiles": [{"sheet", "first", "last", "count",
  "cols", "cell_w"}]` (first/last = the `#k` numbers) and
  `"per_sheet_reduced": bool`.

### 3. `anim` (`_cmd_anim` + `_write_anim_summary`)

- `made = contact_sheets(items, seg_dir, args.per_sheet, vw, vh)`;
  `res["sheets"]` = the relative paths, as before. Set
  `res["sheet_tiles"] = [{"sheet": rel, "first": idx[start],
  "last": idx[start+count-1], "count", "cols", "cell_w"}]`, where `items[k]` ↔
  `idx[k]`. Set `res["sheets_reduced"]`.
- Segment summary, after the `- files:` line: `- sheets: s01/sheet_01.png
  f000-f014, s01/sheet_02.png f015-f029` (frame ids formatted `f{i:03d}`, as in
  the labels and file names), plus the same `--per-sheet` note when reduced.
- `run.json` extra (`:~1552`): `"sheet_tiles"` aggregated over the segments.

### 4. Tests

- `tests/test_screen_recording_cli.py`:
  - **New e2e test** (ffmpeg + magick): `anim` on a synth card video with a
    narrow `--roi` strip that the card crosses (e.g. 40x800 through the card's
    path). At implementation time, probe which synth mode and x actually gives
    a segment. Assertions:
    - `run["sheet_tiles"]` is non-empty;
    - the counts add up to the segment's saved view frames, contiguously;
    - some sheet has `cols > 1`;
    - `dirty_borders(sheet, cell_w, cols) == []` for every sheet;
    - the summary carries the `- sheets: … f…-f…` line.
    **Premise control:** montage three of the run's own frames with
    anim-style labels at the old image-only geometry (`<vw>x<vh>+4+4`). It must
    give `dirty_borders != []`, which proves the check can see an overflow on
    exactly these frames.
  - **New unit test** of `contact_sheets()` (magick only; `import video_prep`)
    that forces a reduction. Use many small tall PNGs with bug-style two-line
    labels and a `per_sheet` too large to keep the `MIN_TILE_PX` floor.
    Assertions: more than one sheet; some sheet is `reduced`; each `count` is at
    most `per_sheet`; starts are contiguous and the counts add up to n; every
    sheet is ≤ `SHEET_MAX_EDGE`; `dirty_borders` is empty everywhere.
  - **New bug-mode integration case with real layout-driven reduction**
    (ffmpeg + magick). A real reduction needs more frames than one sheet can
    hold with readable labels. Probed one-sheet capacity: 126–224 tall tiles
    (226 landscape), set by the 64 px `MIN_TILE_PX` floor and the label widths,
    whatever the frame size. So the run needs about 250 key frames on one
    requested sheet:
    - A short synth video with continuous motion, run with `--interval` near
      one frame, `--max-frames` ≈ 300, `--per-sheet` ≈ 400 and a small
      `--view-size` (e.g. 100) so that extraction and montage stay cheap.
    - At implementation time, probe the exact flags and confirm that the run
      really yields more picks than the capacity.
    - Fallback if the video route cannot produce that many picks cheaply:
      `bug DIR` on a generated folder of distinct timed PNGs (an
      `ImageFolderInput`-style fixture).
    Assertions:
    - `run["per_sheet_reduced"]` is true, and there are at least 2
      `sheet_tiles`, each with `count` < `--per-sheet`;
    - for **every** sheet, the summary has the line
      `- <sheet>: frames #<first>-#<last>` equal to its `sheet_tiles` entry
      (parsed from the summary, compared one-to-one in order);
    - the ranges partition `#1…#N` contiguously, where N = the timeline row
      count = the number of images in `frames/` (the frames actually saved);
    - each sheet PNG's width equals `min(count, cols) * (cell_w + 8)` (the tile
      count actually drawn per row), and `dirty_borders` is empty;
    - the summary carries the reduction note:
      `--per-sheet <N> does not fit with readable labels (at most <max count>
      frames a sheet here)`.
    **Pre-fix control** (temporary, during implementation, not committed): run
    the new test against the old range arithmetic and record that it fails.
    This proves the range assertions bind.
  - The narrow-`--roi` anim test also runs with a small `--per-sheet` (e.g.
    7). That makes the strip span several sheets, so the anim `- sheets:` line
    is checked range by range against `sheet_tiles`, not only on a single
    sheet.
  - Add to an existing `BugMode` test: `run["sheet_tiles"]` covers every
    timeline row, and the summary line reads `frames #1-#…`.
- `tests/test_screen_recording_core.py:667`
  `test_matches_sheet_layout_when_labels_need_no_room`: `sheet_layout` is gone,
  so pin the values it gave (probed): (8,360,800)→(4,338,752),
  (30,200,120)→(5,312,187), (4,1080,2400)→(4,392,871). Rename the test to say
  what it pins: unchanged layouts for labels that need no room. Reword the
  `MAX_ENLARGE` comment in `vp_core.py:225` ("the enlargement cap
  sheet_layout uses too" → "the enlargement cap of every sheet layout").

### 5. Docs — `.claude/skills/aitask-screen-recording/SKILL.md`

- "Read the results" item 2 (Contact sheets): add "Every label fits its cell,
  so a sheet may hold fewer than `--per-sheet` frames; the summary lists the
  frames on each sheet."
- Test-coverage list (~`:400`): add a bullet: bug/anim sheets whose labels fit
  narrow `--roi` cells, and the `--per-sheet` reduction.

## Verification

- `python3 tests/test_screen_recording_core.py` and
  `python3 tests/test_screen_recording_cli.py`: all pass. Read each file's own
  final verdict.
- The original repro, by hand: `anim` with `--roi` on a 40x800 strip at the
  default 30 a sheet. Expect 75 px cells (15 cols) and clean borders.
  `dirty_borders` against the old 45 px layout confirms that the overlap is
  gone.
- `bug` on a standard synth video: the summary ranges and the sheet sizes are
  identical to before (the 8 x 450x1000 layout is unchanged).

## Step 9 (Post-Implementation)

Commit the code changes (`bug: … (t2219)`) and the plan separately, then archive
via the workflow's Step 9.

## Risk

### Code-health risk: low
- `contact_sheets()` can now raise `PrepError` (the sheet-size check, or a label
  wider than a whole sheet) where it never did, so it could fail a whole bug or
  anim run · severity: low · → mitigation: none needed. The bounds come from
  the same `label_safe_layout` model that sheet mode already enforces and
  tests; a 1600 px label cannot come from these generated labels; the new unit
  test exercises the bounds.
- Layout change for existing inputs · severity: low · → mitigation: none
  needed. Probed as identical for typical full-screen inputs, and pinned in the
  core test.

- The reduction integration case extracts about 250 frames, so it is a slower
  test · severity: low · → mitigation: none needed. It uses a small
  `--view-size` and one short video, and the cost is measured during
  implementation.

### Goal-achievement risk: low
- Bug summary ranges after a layout-driven reduction were untested in the
  first draft of this plan · severity: medium · → mitigation: addressed in
  Step 4: a real-reduction bug integration case with a pre-fix control.
- The narrow-strip e2e test needs a synth video whose motion stays detectable
  inside a 40 px strip · severity: low · → mitigation: none needed. Step 4
  probes the synth mode and x position first, and the unit test covers the
  layout independently of segment detection.

## Final Implementation Notes

- **Actual work done:** all five plan steps landed as written:
  - `contact_sheets()` measures every label line, lays out with
    `core.chunk_sheets`, and returns `(path, start, count, reduced, cols,
    cell_w)`;
  - new helpers `checked_sheet_size()` (shared with `cmd_sheet`),
    `sheet_tiles()` and `per_sheet_note()`;
  - `sheet_layout()` removed;
  - bug and anim list each sheet's real frame range in the summary, plus the
    reduction note, and write `sheet_tiles` to `run.json` (bug also writes
    `per_sheet_reduced`);
  - one skill-doc sentence and one test-coverage bullet.
- **Deviations from plan:** the bug reduction integration test runs
  in-process with `SHEET_MAX_EDGE` patched to 500, not as a CLI run with
  about 250 frames.
  - Bisected on ffmpeg n9.0.2: the CLI cannot reach a layout-driven
    reduction in bug mode. Extraction works at 100 picks and fails at 120
    (see the upstream defect), while a 1600 px sheet only reduces past about
    126–224 tall tiles.
  - The image-folder fallback uses the same extraction, so it does not help
    either.
  - The test runs the shipped bug pipeline (`vp.main`) with the smaller edge
    and gets a real 20 / 17 split. It checks every summary range against
    `sheet_tiles` one to one, the contiguous partition of `#1…#N` = the
    timeline rows = `frames/*.png`, the sheet PNG widths, `dirty_borders`,
    and the note.
  - The real 1600 px reduction is covered by the direct `ContactSheets` unit
    test (260 tiles).
- **Issues encountered:**
  - A 2 s clip gives 37 picks, not 40. The premise now asserts that every pick
    is requested on one sheet, instead of an exact count.
  - `main` advanced mid-task: t2229 `111838f20` made a comment-only change
    to `video_prep.py`, unrelated to this task.
- **Key decisions:**
  - `run.json["sheets"]` keeps its list-of-paths shape for `vp_pick` and the
    tests; `sheet_tiles` is added beside it.
  - Pre-fix control (not committed): the new bug test ran against a scratch
    copy of `video_prep.py` with the old `s_i * per_sheet` arithmetic, and
    failed: the summary listed `#1-#37` and `#41-#37` where the sheets hold
    `#1-#20` and `#21-#37`.
  - The anim strip test carries its own premise control: the old image-only
    geometry on the same frames gives dirty borders.
  - Verification:
    - `python3 tests/test_screen_recording_core.py`: 123 OK.
    - `python3 tests/test_screen_recording_cli.py`: 107 OK.
    - Original repro by hand: anim `--roi 160,0,40,800` gives 11 cols of
      75 px cells (45 px before) with labels inside their cells.
- **Upstream defects identified:**
  - `.aitask-scripts/screen_recording/video_prep.py:244 — extract_views()
    builds one select expression with an eq(pts,…) term per wanted frame;
    ffmpeg (n9.0.2) fails with "Cannot allocate memory" somewhere between 100
    and 120 terms, so `bug --max-frames` above ~110 (and any extraction that
    large) aborts the run.`

## Post-Review Changes

### Change Request 1 (2026-11-08 11:30)
- **Requested by user:** the narrow-ROI anim test used `--per-sheet 7`. For
  seven 40x800 frames the old image-only layout already gives 77 px cells, so
  the 69 px caption fits and the test proved nothing about the overlap. Its
  control forced 40x800 cells, not the layout the old code would choose.
  Keep the multi-sheet range coverage, and also exercise the default
  `--per-sheet` (30) case, with a premise showing that the old computed layout
  overlaps for the actual saved frame count.
- **Changes made:**
  - Split the test in two, sharing a `strip_run()` helper:
    - `test_narrow_roi_sheet_labels_stay_inside_their_cells` runs at the
      default `--per-sheet`. All saved frames (22) sit on one sheet with clean
      borders. Its premise recomputes the pre-t2219 image-only layout
      (`pre_t2219_layout`, a copy of the removed `sheet_layout`) for the
      actual saved count: 22 cols of 64 px. It draws the real frames with
      their real first label line (from the file names) and asserts dirty
      borders. Verified by hand: all 21 borders are dirty under the old
      layout, none under the new one.
    - `test_narrow_roi_sheets_list_the_frames_they_hold` keeps the
      `--per-sheet 7` multi-sheet range check.
  - Re-ran: CLI 108 OK, core 123 OK.
- **Files affected:** `tests/test_screen_recording_cli.py`
