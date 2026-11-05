---
Task: t1893_4_sheet_subcommand_any_image_folder.md
Parent Task: aitasks/t1893_screen_recording_skill_expansion.md
Sibling Tasks: aitasks/t1893/t1893_5_*.md … aitasks/t1893/t1893_14_*.md
Archived Sibling Plans: aiplans/archived/p1893/p1893_*_*.md
Base branch: main
Output branch: main
---

# Plan: `sheet` subcommand for any image folder (t1893_4)

## Context

Today contact sheets come only from a video, inside `bug`/`anim`. The user wants
to extract frames (`frames`, t1893_3), edit them by hand (crop, annotate,
delete), and feed the folder back as labelled sheets. Each label shows the time
read from the file name and the Δ to the previous image, so a deleted frame shows
up as a larger gap. This task adds
`aitask_screen_recording.sh sheet DIR [--per-sheet N] [--out DIR]`.

Notes acknowledged (advisory):
- t1893_1: docs layout. Reference tables go on the skill page; how-tos go in
  `workflows/screen-recordings/` subpages listed in both indexes.
- t1893_3: `parse_frame_name` is strict, and `TOKEN_TILE`/`image_tokens` live in
  `vp_core`.

**User decision (planning):** `sheet` also accepts a canonical name followed by a
suffix (for example `t00007040_annotated.png`). The strict parser stays the
default for t1893_5/6.

**Plan review (2026-11-05):** the user raised three concerns. All were verified
and are now addressed in the design below:
1. ordering and Δ were planned before dropping unreadable images;
2. narrow tiles overflow labels;
3. animated WebP renders one tile per frame;
4. (second round) sheet capacity: the row budget makes a large `--per-sheet`
   infeasible. Resolved with an explicit overflow rule (split into more sheets)
   and a fixture that forces the conflict;
5. (third round) tiny crops: an absolute 64 px floor was unreachable under the
   4× cap. The floor is now relative (`min(64, 4·L)`), k = 1 is proven
   feasible, and there are tiny-crop and property fixtures;
6. (fourth round) the overflow warning fires only on a feasibility reduction,
   not a remainder chunk (a 9-with-8 case is added). The CLI overflow fixture is
   sized from a measured capacity upper bound, with a premise guard.

## Facts probed (2026-11-05, ImageMagick 7.1.2-35 here)
- `montage -geometry WxH+4+4` fits each image into the W×H cell and keeps its
  aspect. It enlarges small images, centres them in the cell, and keeps cells
  uniform.
  - Probe: a 200×100 image with a 50×50 square in a 180×400 cell came out
    180×90, and the square stayed square.
- A label wider than its cell does **not** widen the cell; it overlaps the
  neighbours. So names must be truncated in the label.
- `-label` text interprets `%` escapes and a literal backslash-n (`\n` → newline),
  and a label starting with `@` reads a file. The fixes: escape `%`→`%%` and
  `\`→`\\`, and always start the label with `#k`.
- IM parses file names (`[0]` subimage specs, `fmt:` prefixes). Inputs are
  therefore staged under safe names.
- webp and jpeg read fine (`magick identify`).
- `sheet_layout(8, 200, 4000)` returns 8 columns with `tw=77`. The line
  `7.040 s +33 ms edited` measures 119 px at pointsize 15, so it would overlap
  its neighbours. Resizing the finished sheet cannot undo that overlap.
- `magick -pointsize 15 label:'A' label:'B' … -format '%w %h\n' info:` measures
  each label with the host's own default font, in one call and with no files
  written. Probe: 119/86/206 px for a time line, `no time in name` and a long
  name line.
- An animated WebP without `[0]` gives one montage tile per frame (user's probe),
  so `[0]` must also be used when rendering, not only when sizing.

## Design
- **Input:** the top level of DIR only, with no recursion. Files ending in
  `.png/.jpg/.jpeg/.webp` (any case) are images. Dotfiles, other files and
  subdirectories are counted as ignored, and the summary names up to 5 of them.
- **Readability first, then the plan.** Every candidate is identified
  (`magick identify -format "%w %h\n" <staged>`, one line per frame) **before**
  ordering. An image `magick` cannot read is left out, with a warning listing
  it, never silently. `plan_sheet` then runs on the **readable names only**, so
  order numbers, Δ and gaps all describe exactly the tiles that are rendered.
  Example: with 0/33/66 ms and a corrupt 33 ms file, the 66 ms tile shows +66 ms
  and its gap.
- **Animated images:** only the first frame is used, for sizing **and**
  rendering. Staged inputs are passed as `NNNN.<ext>[0]` to both identify and
  montage, so one file is one tile. The frame count comes from identify's line
  count, and a file with more than one frame gets a summary note ("animated:
  first frame of N used") plus a `frames_in_file` column in tiles.tsv.
- **Time from name:** `core.parse_frame_name(name, allow_suffix=True)`.
  - The time is the canonical form (`t\d{8,}`, `\d{2,}_\d+\.\d{3}s` or
    `f\d{3,}_\d+\.\d{3}s`), optionally followed by a suffix that starts with
    `_`, `-`, `.`, a space or `(`.
  - `FrameName` gains `suffix: str = ""`. The default keeps existing equality.
  - The strict default is unchanged; its tests keep rejecting
    `t00007040_edited.png`.
- **Order (pure, `vp_core.plan_sheet(names) -> SheetPlan`):**
  - Timed images first, by (ms, natural name order).
  - Then untimed ones, in natural (digit-aware) name order, each with an index
    label and **no time**.
  - `delta_ms` is the difference to the previous *timed* image (None for the
    first). Equal ms gives Δ 0.
  - `SheetPlan` also carries `forms` (the set of name forms), `untimed`, and
    `gaps`.
  - A gap is a Δ > 1.5 × the median positive Δ, when there are ≥ 3 timed images.
    It is labelled heuristic: a deleted frame, or the screen held still in a VFR
    recording.
- **Precision:** Δ comes from the rounded ms in the names (±1 ms), and the docs
  say so.
- **Provenance from `DIR/frames.tsv`** (when present): for an image with a row
  under its file name, its SHA-256 is compared. Column `frames_tsv` is `match`,
  `edited` (hash differs, and the label says `edited`) or empty (no row or no
  manifest). This is the same trust rule t1893_5 uses.
- **Mixed name forms** (for example `t…` and `NN_…s`): the summary warns that
  times are comparable only if the images come from the same recording.
- **Labels fit their cells.** Readable timestamps are part of the deliverable.
  - Line 2 (time, Δ, markers) is built first. Its rendered widths are measured
    in **one** batched `magick … label:… -format '%w %h\n' info:` call, with the
    same pointsize and the default font that montage uses.
  - `need_w` = the widest line 2 on that sheet + 6 px margin.
- **Layout (new pure `core.label_safe_layout(n, W, H, need_w, max_edge, label_h)`):**
  - Per sheet, the box is (max w, max h) of that chunk's first frames.
  - For each column count, `s` is chosen as in `sheet_layout`, and then
    `cell_w = max(need_w, round(W·s))`, with the constraint
    `cols·(cell_w + 8) ≤ max_edge` and `rows·(th + label_h + 8) ≤ max_edge`.
  - A cell wider than its image is fine: montage centres the image, which
    letterboxes it horizontally.
  - Scale is chosen as in `sheet_layout`, including its **4× enlargement cap**:
    `s = min(width bound, height bound, 4)`. Fitted dimensions are clamped to
    ≥ 1 px (`max(1, round(…))`), never rejected.
  - A layout is **feasible** only if:
    - the fitted long edge `s·L` (L = the box's long edge) is
      ≥ `floor_px = min(MIN_TILE_PX, 4·L)`, with `MIN_TILE_PX = 64`. A tiny
      original is exempt: a 10×10 crop needs only 40 px, which is what the 4×
      cap gives it;
    - `cols·(cell_w+8) ≤ max_edge`;
    - `rows·(th + label_h + 8) ≤ max_edge`.

    The function returns the feasible column count with the largest image scale,
    or **None when no column count is feasible**.
  - **Why k = 1 always works** (while `need_w + 8 ≤ max_edge`): with one tile,
    `s = min(4, (max_edge−8)/W, (max_edge−label_h−8)/H)`. So `s·L ≥ min(4L, 1552)`,
    which is ≥ `floor_px` for every source size, and the label space and sheet
    cap still hold (`cell_w = max(need_w, W·s) ≤ 1592`).
  - **Overflow rule — `--per-sheet N` is an upper bound, never a promise.** Tiles
    are kept, labels stay readable, and the sheet size cap holds; the number of
    sheets gives way. The pure `core.chunk_sheets(boxes, per_sheet, need_ws, …)`
    chunks greedily: for each chunk it starts at `k = min(N, remaining)` and
    lowers k until the chunk's layout is feasible.
    - `k = 1` is always feasible while `need_w + 8 ≤ max_edge` (shown above).
      Otherwise `PrepError`, which these short line-2 texts cannot reach. The
      loop therefore always terminates with every tile placed.
    - Example: n = 1000, need_w = 125, label_h = 40 allows at most
      12 cols × 14 rows (`64 + 48 = 112` px per row), so 168 tiles a sheet.
      `--per-sheet 1000` therefore writes several sheets.
    - Each chunk records `reduced = k < min(N, remaining)`, i.e. whether
      feasibility (not running out of images) shrank it. Only when some chunk
      has `reduced` does the summary warn:
      `Warning: --per-sheet N does not fit with readable labels (at most K tiles a sheet here); wrote M sheets`.
      A shorter last sheet (9 images with `--per-sheet 8` → 8 + 1) is ordinary
      exhaustion and gives no warning.
    - run.json records `per_sheet_requested`, `tiles_per_sheet` (a list) and
      `per_sheet_reduced` (bool).
    - Nothing is dropped, and no tile is shrunk below its `floor_px`.
  - `sheet_layout` stays unchanged for bug/anim.
  - `montage -geometry {cell_w}x{th}+4+4`.
  - `fit_scale = min(cell_w/w, th/h)` is recorded per tile.
- **Name line truncated to the measured width:**
  - full name lines are measured in one batched call;
  - a line wider than `cell_w − 6` is middle-truncated with `...` to
    `floor(len · (cell_w−6) / width)` characters;
  - the truncated lines are re-measured in one batch, and any still too wide
    shrink by one more character, for up to 3 rounds. After that the name is
    dropped to `#k` alone, which is always narrower than line 2;
  - the full name is always in tiles.tsv `file`.
- **Size cap:** sheets stay within `SHEET_MAX_EDGE` by construction (the layout
  constraints above). After each montage the size is read with `core.png_size`.
  An edge over `SHEET_MAX_EDGE` means montage did not lay out as modelled, and
  that is a **`PrepError`** (fail closed). The sheet is never shrunk afterwards,
  because shrinking would undo the readable-label guarantee.
- **Labels (ASCII only; the fonts are host-dependent):**
  - line 1: `#k <name>`, truncated to the measured cell width (above);
  - line 2:
    - `7.040 s +33 ms` for a timed image after the first;
    - `7.040 s first` for the first timed image;
    - `no time in name` for an untimed image;
    - ` edited` appended when the image's hash differs from `frames.tsv`.
  - `core.im_label(text)` escapes the text.
- **Staging:** symlinks `.stage/NNNN.<ext>` inside the out dir (copied if
  `os.symlink` fails), removed in `finally`. User paths never reach IM's
  file-name parser.
- **Outputs** in `make_out_dir(args.out, DIR, "sheet")` (default
  `$TMPDIR/video-prep/<dirname>-sheet`):
  - `sheet_NN.png`;
  - `tiles.tsv`, with columns
    `sheet tile row col order file t_ms delta_ms time_from frames_tsv img_w img_h frames_in_file cell_w fit_scale label`.
    Only rendered tiles are listed; unreadable files appear in summary.md and
    run.json `unreadable`.
    `time_from` is `name:frames|name:bug|name:anim|none`. The label is written
    with its newline shown as ` | `.
  - `summary.md`, with: header, warnings, `## Contact sheets` (tiles #a–#b per
    sheet and the token estimate), `## Gaps (heuristic)`, `## Tiles` table, and
    what the labels mean;
  - `run.json`.
  - stdout ends with `tokens: …` (one line) and then `SUMMARY: <path>`.
- **Errors:**
  - DIR is not a directory → exit 2;
  - `magick` missing → `PrepError` (exit 1), checked **before** anything is
    written; the message names ImageMagick 7. Install hints are t1893_13's job.
  - `--per-sheet < 1` → 1;
  - no images → 1;
  - every image unreadable → 1.

  None of these leaves a directory behind.

## Implementation steps

### 1. `vp_core.py`
- `FrameName.suffix` field. In `parse_frame_name(name, *, allow_suffix=False)`,
  when `allow_suffix` is set the stem regex gets `(?P<sfx>[-_ .(].*)?`.
- `natural_key(name)` sorts by digit runs.
- `SheetItem(name, ms, form, suffix, delta_ms, order)` and
  `plan_sheet(names) -> SheetPlan(items, untimed, forms, gaps, median_delta_ms)`.
- `im_label(text)` escapes `%` and `\`.
- `truncate_middle(text, n)`.
- `label_safe_layout(n, W, H, need_w, max_edge, label_h) -> (cols, cell_w, th) | None`
  and `chunk_sheets(...)`: pure, so they are unit-testable. `MIN_TILE_PX = 64`.

### 2. `video_prep.py`
- `cmd_sheet(args)`, in this order:
  1. validation;
  2. scan;
  3. out dir;
  4. stage;
  5. **identify every candidate (drop unreadable ones; record frame counts)**;
  6. **`plan_sheet(readable names)`**;
  7. frames.tsv check;
  8. per chunk: build labels → measure line 2 → `label_safe_layout` → truncate
     line 1 to the measured width → montage with `[0]` inputs (new
     `folder_sheets(...)`; `contact_sheets` and `sheet_layout` are untouched);
  9. size cap;
  10. tiles.tsv, summary.md, run.json;
  11. stdout.

  If every image is unreadable, the step-3 out dir is removed before the
  `PrepError` (exit 1), so no directory is left behind.
- `measure_labels(texts) -> list[(w, h)]`: one `magick` call with escaped
  `label:` arguments. It fails closed (`PrepError`) on a line-count mismatch.
- Parser: `sheet` with `dir`, `--per-sheet` (default 8, as in `bug`) and `--out`.
- `main()`: check that the video file exists only for modes that have `video`;
  for `sheet`, check that `dir` is a directory.
- Module docstring and the `aitask_screen_recording.sh` usage comment gain
  `sheet DIR`.

### 3. Tests
- **`tests/test_screen_recording_core.py`:**
  - `FrameNames.test_suffix_variant`. Accepts with `allow_suffix`:
    - `t00007040_edited.png` (suffix `_edited`);
    - `f013_0.483s (1).png`;
    - `04_5.500s-crop.JPG`;
    - `t00007040.v2.webp`.

    Rejects:
    - `t00007040x.png`;
    - `t0000704_e.png`;
    - `sheet_01.png`;
    - `IMG_20260101_120000.png`;
    - `t00007040[1].png`.

    The strict calls still reject the suffix names.
  - `SheetPlan` tests:
    - order and Δ, with a deleted frame giving a gap;
    - equal ms → Δ 0;
    - natural-order tie-break;
    - untimed after timed, with no ms;
    - all untimed;
    - mixed forms reported;
    - no gap reported with < 3 timed images.
  - `ImLabel`: escaping of `%` and `\`; truncation keeps the head and the tail.
  - `LabelSafeLayout`:
    - `(8, 200, 4000, need_w=125)` → `cell_w ≥ 125`, with
      `cols·(cell_w+8) ≤ 1600` and the height within 1600;
    - when the label needs no extra width, the result equals `sheet_layout`'s;
    - `need_w = 1600` → None;
    - `(1000, 360, 800, 125)` → None.
  - `ChunkSheets` (forces the budget conflict):
    - 1000 boxes of 360×800, `per_sheet = 1000`, `need_w = 125`;
    - chunks sum to 1000, in order with none dropped;
    - every chunk's layout is feasible;
    - every chunk is ≤ the computed capacity, and the reduction is reported;
    - `per_sheet = 4` with ordinary boxes → chunks of 4 (no false reduction);
    - **remainder is not a reduction:** 9 ordinary boxes with `per_sheet = 8` →
      chunks `[8, 1]`, every `reduced` False;
    - **tiny originals:** a single 10×10 box → one feasible chunk (s = 4,
      40×40, `cell_w = need_w`). A 1×2000 sliver and a 10×10 crop together →
      the loop terminates, and every box is placed with fitted dimensions
      ≥ 1 px;
    - a property check over a grid of box sizes (1…4000 px each side) and
      `need_w` ∈ {60, 125, 400}: `label_safe_layout(1, …)` is never None.
- **`tests/test_screen_recording_cli.py`, new `SheetMode`.** These need no
  ffmpeg. PNGs come from a small stdlib PNG writer in the test (`zlib`), and
  jpg/webp copies are made by `magick`. Sheet assertions are skipped without
  `magick`.
  - **Folder:** `t<ms>` PNGs every 33 ms, 360×800, with:
    - one frame deleted;
    - one cropped to 200×100 and carrying a black 50×50 square;
    - one `.jpg` and one `.webp`.

    Run with `--per-sheet 4`. Assert:
    - the sheet count;
    - the `tiles.tsv` order;
    - `delta_ms` values, and the larger Δ at the gap in both the label and
      `## Gaps`;
    - `fit_scale`;
    - every sheet ≤ 1600 px (via `core.png_size`);
    - the `tokens:` line;
    - `SUMMARY:` as the last line.
  - **Not stretched:** the sheet is converted to raw gray with `magick … gray:-`.
    The bbox of pixels < 10 (the square; background 30, white 255) is square
    within 1 px. A premise guard checks that the source square is square.
  - **Untimed:** `a.png`, `b10.png`, `b2.png` →
    - order a, b2, b10;
    - labels `no time in name`;
    - the summary warning;
    - exit 0.

    A mixed folder places untimed images after timed ones.
  - **frames.tsv provenance:**
    - one row whose hash matches → `match`;
    - one with a wrong hash → `edited`, also shown in the label.
  - **Hostile names:** `t00000100_<80 chars>.png`, `t00000200 50%.png`,
    `-x.png`, `t00000300[1].png` and `a\b.png` all run cleanly. Expected:
    - the tile count matches;
    - the long label is truncated (`...`), with the full name in the `file`
      column;
    - `[1]` comes out untimed.
  - **Unreadable middle file:** `t00000000.png`, a corrupt `t00000033.png`
    (random bytes) and `t00000066.png` → exit 0. Assert:
    - tiles.tsv has 2 rows, `order` 1 and 2;
    - the 66 ms row has `delta_ms` 66, and its label says `+66 ms`;
    - the summary lists `t00000033.png` as unreadable;
    - the sheet's tile count (from the layout: `cols·rows ≥ 2`, and the sheet
      width equals `cols·(cell_w+8)` for 2 tiles) agrees with tiles.tsv.
  - **Narrow tiles:** 8 tall 40×800 crops with long suffixed names, 1 sheet.
    Assert:
    - tiles.tsv `cell_w` ≥ the measured line-2 width (re-measured in the test);
    - no label overlaps a neighbour. In the raw gray sheet, every column within
      ±3 px of each cell boundary `k·(cell_w+8)` is background (≈30) over the
      whole sheet height: images and text never enter the 4 px borders unless a
      label overflows.
    - Premise guard: the same check on a deliberately over-long label rendered
      by the test with `sheet_layout`'s width finds text in a border column.
  - **Animated WebP:** a 2-frame WebP made with `magick` (premise guard:
    `identify` lists 2 frames) next to two PNGs → 3 tiles, not 4. The webp row
    has `frames_in_file` 2, and the summary carries the first-frame note.
  - **Capacity overflow (CLI), sized from a proven bound, not a guess** (a probe
    showed 200 tiles with 88 px labels fit one sheet). The test establishes the
    bound first:
    - `w_min` = the measured width (the test's own `magick label:` call) of the
      **narrowest** line 2 the fixture can produce (`0.000 s first`). Every real
      `need_w ≥ w_min + 6`.
    - For 20×20 images, `floor_px = min(64, 80) = 64`, so `rows ≤
      ⌊1600 / (64 + 40 + 8)⌋ = 14` and `cols ≤ ⌊1600 / (w_min + 6 + 8)⌋`.
    - `cap_upper = cols_max · 14`, and the fixture holds `cap_upper + 1` images
      with `--per-sheet cap_upper + 1`. A premise guard asserts
      `count > cap_upper`.

    Assert:
    - more than 1 sheet;
    - tiles.tsv has every image, in order with none missing;
    - the summary carries the `--per-sheet … does not fit` warning, and
      `per_sheet_reduced` is true;
    - run.json `tiles_per_sheet` sums to the count;
    - every sheet ≤ 1600 px;
    - the narrow-tile border check passes on every sheet.
  - **No false overflow warning (CLI):** 9 ordinary `t<ms>` images with
    `--per-sheet 8` → 2 sheets (8 + 1), no `does not fit` warning, and
    `per_sheet_reduced` false.
  - **Tiny crop (CLI):** a folder holding one 10×10 `t00000100.png` → exit 0,
    1 sheet, 1 tile. tiles.tsv `fit_scale` is 4, and `cell_w` ≥ the measured
    line-2 width. The sheet passes the border check and is ≤ 1600 px.
  - **No magick (always runs):** with `video_prep.have_magick` patched to False,
    `main(["sheet", dir, "--out", o])` returns 1, the stderr names ImageMagick,
    and `o` does not exist.
  - **Errors:**
    - a missing dir → 2;
    - an empty dir → 1;
    - `--per-sheet 0` → 1;
    - none of them leaves the out dir.
- **Mutation checks during verification** (scratch edits, reverted):
  - Δ from the index instead of ms → the Δ assertions go red;
  - untimed files assigned ms 0 → the untimed test goes red;
  - `-geometry …!` (stretch) → the square test goes red;
  - no truncation → the label-length assertion goes red;
  - `need_w` ignored (plain `sheet_layout`) → the narrow-tile border check goes
    red;
  - `plan_sheet` run before dropping unreadable files → the unreadable-middle
    Δ goes red;
  - `[0]` dropped from the montage inputs → the animated-WebP tile count goes
    red;
  - `chunk_sheets` returning one chunk of N → the capacity tests go red (core
    and CLI);
  - `reduced = len(chunk) < N` (the remainder counted) → the 9-with-8 no-warning
    tests go red;
  - no escape → the `%` label assertion goes red;
  - frames.tsv match forced → the provenance test goes red.

  For each mutant, confirm the targeted output actually changed.

### 4. Skill text: `.claude/skills/aitask-screen-recording/SKILL.md`
- A "Pick a mode" row: images you already have, for example frames edited by
  hand → `sheet`.
- A run example.
- A **Sheet mode** section:
  - label meaning (time, `+Δ`, `first`, `no time in name`, `edited`);
  - unreadable files are left out and listed, and Δ skips them;
  - animated images use their first frame;
  - the accepted names, including suffixes;
  - gaps are heuristic;
  - Δ is ±1 ms;
  - `magick` is required.
- The Tests list gains sheet.

The `.agents`/`.opencode` wrappers are thin pointers and need no change. No new
`.sh` helper, so no whitelist changes.

### 5. Website docs
- `website/content/docs/skills/aitask-screen-recording.md`:
  - the Step-by-Step intro sentence and a Modes row;
  - a `### sheet` options table (`DIR`, `--per-sheet 8`, `--out`);
  - the `sheet` output layout and a `### tiles.tsv` column table;
  - warning rows: untimed names, mixed forms, unreadable or ignored files,
    animated first frame, the `--per-sheet … does not fit` split, the
    "magick not found" error, the no-images error;
  - the Requirements bullet: `magick` is required for `sheet`;
  - the Workflows list.
- New `website/content/docs/workflows/screen-recordings/hand-edited-images.md`,
  "Prepare Images by Hand, Then Feed Them to the Agent":
  - extract with `frames --range` (or `--at`);
  - edit in any tool, keeping the timestamp at the start of the name (a suffix
    is fine);
  - delete frames you do not need;
  - run `sheet DIR`;
  - the agent reads `summary.md`, then the sheets;
  - what labels and gaps mean;
  - that edited images lose `frames.tsv` geometry, and that renaming loses the
    manifest match.

  List it in the section `_index.md` ("Choose a mode" row and Walkthroughs;
  replace the "More use cases" placeholder sentence only if it then reads
  stale) and in `workflows/_index.md`, with relref.
- `exact-frames.md`: change "Keep the file name unchanged…" to the current rule
  (the timestamp must stay at the start of the name; `sheet` accepts a suffix;
  `frames.tsv` matches by unchanged name and hash). Link the new walkthrough.
- Run `cd website && python3 check_links.py --build && hugo build --gc --minify`.

### 6. Step 9 (Post-Implementation)
Commit the code, tests and docs as `feature: Add the sheet subcommand for any
image folder (t1893_4)`. Commit the plan via `./ait git`, then archive per
Step 9. The final notes for siblings cover: `allow_suffix`, `plan_sheet`,
`im_label` and staging (IM file-name parsing), and the frames.tsv hash check.

## Verification
- `python3 tests/test_screen_recording_core.py`
- `python3 tests/test_screen_recording_cli.py`
- `bash tests/run_all_python_tests.sh --test-dir tests`; read the last line only.
- The mutation checks above.
- `sheet --help` checked against every documented flag.
- `./.aitask-scripts/aitask_skill_verify.sh`.
- The website link check and hugo build.
- Manual: a real `frames --range` run, two frames deleted and one cropped, then
  `sheet` on the folder, and a look at the sheet image.

## Risk

### Code-health risk: low
- `main()`'s input check changes for every mode (video vs dir). The existing
  `test_bad_inputs_fail_cleanly` pins the video behaviour · severity: low ·
  → mitigation: none
- `FrameName` gains a defaulted field, and `parse_frame_name` gains a keyword.
  The strict behaviour is unchanged and pinned by the existing garbage tests ·
  severity: low · → mitigation: none

### Goal-achievement risk: low
- Label width depends on the host's default font. It is measured with that font
  through `label:`, which assumes montage renders labels with the same default
  font and pointsize. The narrow-tile pixel test checks that assumption against
  real montage output · severity: low · → mitigation: none
- The same overlap can occur in bug/anim `contact_sheets` with very narrow
  tiles. That is out of scope here and is recorded in the final notes as an
  upstream observation if it reproduces · severity: low · → mitigation: none

## Post-Review Changes

### Change Request 1 (2026-11-05)
- **Requested by user:** three review findings. Each was confirmed before fixing.
  1. `tiles.tsv` passed every value through the control-character translation,
     the `file` column included. `t00000000_a\nb.png` was recorded as
     `t00000000_a?b.png`, a file that does not exist, and could collide with a
     real one.
  2. `make_out_dir` named the default output after `Path(dir).stem`, so
     `edited.v2` defaulted to `edited-sheet`.
  3. `chunk_sheets` restarted at `min(N, remaining)` and rescanned each rejected
     prefix. 10000 boxes with `--per-sheet 10000` took about 50 s.
- **Changes made:**
  1. The `file` column is the exact name. Tabs, newlines and quotes get
     standard csv quoting, and the file is written with UTF-8
     `surrogateescape`, so non-UTF-8 bytes stay byte-exact. Labels and the
     Markdown table are still display-sanitized. `summary.md` is written with
     `errors="replace"`, because otherwise an undecodable name would crash the
     run.
  2. `make_out_dir(..., name=)`. `sheet` passes the folder's full
     `resolve().name` (`"folder"` if that is empty). Video naming is unchanged.
  3. `chunk_sheets` takes per-tile label widths (a list, or one int):
     - each sheet tries at most `sheet_capacity_bound()` tiles, which is
       `⌊max/(need_w+8)⌋ · ⌊max/(1+label_h+8)⌋` and holds for any box size;
     - running prefix maxima are kept in arrays, so a rejected count costs one
       layout call.

     The CLI passes the widths, no longer a rescanning lambda.
  - Docs: the `tiles.tsv` `file` row states the exact-name and quoting rule.
- **Verification:**
  - New tests:
    - `test_tiles_tsv_keeps_exact_file_names`: `\n`, `?`, tab, quotes and a
      non-UTF-8 byte all round-trip to `os.listdir`, with no collision;
    - `test_default_output_keeps_a_dotted_folder_name`;
    - core `test_matches_the_plain_algorithm`: 60 random cases, equal to the
      plain algorithm;
    - `test_capacity_bound_holds`;
    - `test_a_huge_request_is_fast`: 10000 tiles in under 5 s.
  - Mutants. Red:
    - sanitized `file` column;
    - stem-based name;
    - wrong bound width.

    Bound removed alone and rescan alone each stay green, because each
    optimisation covers for the other. Both removed together (the original
    code): 45.75 s, red. All mutants were reverted with checksums.
  - Core 93 OK; CLI 67 OK; `check_links.py --build` PASSED.

## Final Implementation Notes
- **Actual work done:**
  - `aitask_screen_recording.sh sheet DIR [--per-sheet N] [--out DIR]` (`cmd_sheet`
    in `video_prep.py`). It reads the top level of a folder of png/jpg/jpeg/webp
    images and writes `sheet_NN.png`, `tiles.tsv`, `summary.md` and `run.json`,
    plus a `tokens:` line before `SUMMARY:`.
  - Pipeline:
    1. stage the inputs under safe symlink names in a temp dir;
    2. fully decode each one with `magick <f> -format "%w %h\n" info:`; this
       gives one line per frame, and failures are recorded as unreadable;
    3. `plan_sheet` on the readable names only;
    4. compare against `frames.tsv` hashes;
    5. measure line 2 of every label in one batched `label:` call;
    6. `chunk_sheets` → `label_safe_layout` per sheet;
    7. measure name lines and middle-truncate them to the cell;
    8. montage with `[0]` inputs;
    9. fail closed if a sheet comes out over 1600 px.
  - `vp_core` additions:
    - `parse_frame_name(..., allow_suffix=True)` and `FrameName.suffix`;
    - `natural_key`;
    - `SheetItem` / `SheetPlan` / `plan_sheet`, and `GAP_FACTOR = 1.5`;
    - `im_label`, `truncate_middle`;
    - `MIN_TILE_PX = 64` and `MAX_ENLARGE = 4`;
    - `label_safe_layout`, `sheet_capacity_bound`, `chunk_sheets`.
  - `make_out_dir(..., name=)`, and `main()` validates `dir` for `sheet`.
  - Docs:
    - skill page: usage, Modes row, `### sheet`, the sheet layout,
      `### tiles.tsv`, nine warning rows, Requirements and Workflows;
    - new walkthrough `workflows/screen-recordings/hand-edited-images.md`,
      listed in both indexes;
    - `exact-frames.md`: the edit-name rule now allows a suffix, and links the
      walkthrough;
    - `SKILL.md`: a Sheet mode section, a mode row and a run example.
- **Deviations from plan:**
  - Plan review: four rounds, all incorporated before implementation:
    - readable-first ordering;
    - labels measured to fit their cells;
    - `[0]` for animated images;
    - `--per-sheet` as an upper bound with a split;
    - a relative tile floor;
    - the overflow warning only on a real reduction.
  - Code review (Change Request 1):
    - the `file` column keeps exact names;
    - the default output keeps a dotted folder name;
    - `chunk_sheets` uses a capacity bound and prefix maxima (10000 tiles:
      50 s → well under 5 s).
  - `frames.tsv` is not reported as "ignored", because sheet reads it.
  - Staging uses a system temp dir, not `<out>/.stage`, so a run whose images
    are all unreadable leaves no output directory.
  - The `im_label` escape mutant is caught by the core `ImLabel` test, not by a
    CLI assertion; the CLI cannot see rendered text.
- **Issues encountered:**
  - montage labels wider than their cell overlap the neighbours and never
    widen the cell. That is why labels are measured with IM's own `label:` and
    checked by a border-pixel test with a premise control.
  - Each of the two `chunk_sheets` optimisations alone keeps 10000 tiles fast,
    so the timing test only catches removing both (45.75 s).
- **Key decisions:**
  - Suffixed names are accepted only through `allow_suffix=True` (a user
    decision); the strict parser is unchanged for t1893_5/6.
  - Δ comes from the rounded name ms (±1 ms).
  - Gaps are labelled heuristic.
  - A tile's fit scale is montage's fit both ways (it may enlarge), recorded per
    tile.
  - An oversized sheet is a `PrepError`, never shrunk.
  - ASCII-only labels (host fonts vary).
- **Upstream defects identified:**
  - `.aitask-scripts/screen_recording/video_prep.py:372 — sheet_layout()/contact_sheets() (bug and anim sheets) size cells from the image alone, so a narrow --roi gives cells narrower than their labels and labels overlap neighbouring tiles (e.g. anim --roi on a 40x800 strip, 30 per sheet: 45 px cells vs a 69 px "f013 0.483s" label). Layout-level probe only; not run end to end. The sheet-mode fix (core.label_safe_layout + measure_labels) could be reused.`
- **Notes for sibling tasks:**
  - **t1893_5 (pick) / t1893_6 (folder input):**
    - `parse_frame_name` is still strict by default. `allow_suffix=True` is the
      edited-name variant.
    - `plan_sheet` orders a folder the way sheet does.
    - `frames.tsv` trust is a hash match by file name: `sha256_file` vs the
      `sha256` column.
  - **ImageMagick hygiene:**
    - stage user files under safe names, because IM parses `[..]`, `fmt:` and
      `%` in file names;
    - escape label text with `core.im_label` (`%` → `%%`, `\` → `\\`);
    - never start a label with `@`;
    - pass `<file>[0]` for animated inputs;
    - `measure_labels` gives rendered widths with the host font.
  - **Machine-readable files** keep exact names (csv quoting, UTF-8
    `surrogateescape`). Only display text is sanitized.
  - **t1893_13 (dependency hints):** sheet's "magick missing" error is raised
    before anything is written, from `cmd_sheet`; add the install hint there.
  - **Test fixtures:**
    - `write_png` (stdlib gray PNG writer), `square_png`, `sheet_gray`,
      `label_width`, `dirty_borders` (overlap detector) in
      `tests/test_screen_recording_cli.py`;
    - `SheetMode` needs only `magick`, not ffmpeg.
