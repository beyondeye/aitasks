---
Task: t2306_fix_screen_recording_and_questions_test_failures.md
Base branch: main
Output branch: main
---

# t2306 — Fix the screen-recording and questions test failures

## Context

t1912_2's full Python run had 8 deterministic failures that are unrelated to that
task. I diagnosed both groups on this machine. Each has one root cause.

### A. `test_screen_recording_cli.py` (6 tests): ImageMagick's default font draws nothing

- `magick -pointsize 15 label:abc -format %w info:` prints **1** for any text.
  A debug trace shows `Font none`. ImageMagick's default font (Helvetica) maps,
  through `/etc/ImageMagick-7/type-ghostscript.xml`, to
  `/usr/share/fonts/gsfonts/*.pfb`. Those files are not installed here: there is
  no gsfonts/ghostscript package. With an explicit font file
  (`-font /usr/share/fonts/liberation/LiberationSans-Regular.ttf`) the same label
  measures 26 px.
- This is a **real product defect**, not only a test-environment issue.
  `video_prep.py` measures (`measure_labels`) and draws (`contact_sheets`,
  `cmd_sheet` montage) every label with the default font. On such a machine the
  contact sheets come out with **blank labels**, and the label-fit layout
  collapses to its minimum cell width. Every assertion in the task maps to this:
  - `1485 ≤ 400`: `w_min` = 1
  - `64 < 64`: cells stay at the floor
  - `1 > 1`: a single column
  - no `...`: nothing is ever too wide to truncate
  - `dirty_borders == []`: the premise sheets draw no text either
- **Fix, part 1 (font):** resolve the label font once, and use the same font
  everywhere a label is measured or drawn. Keep ImageMagick's default font when
  it draws text, so machines where it works today behave exactly as before. When
  it draws nothing, fall back to fontconfig's sans-serif file. If neither draws
  text, fail with an error that names the cause. Silently blank labels are never
  acceptable.
- **Fix, part 2 (label band height):** the font alone is not enough. A review
  caught this, and I confirmed it. The layout reserves a fixed
  `SHEET_LABEL_H = 40` px per row for the two label lines, but the real band
  montage draws depends on the font's vertical metrics:
  - Liberation Sans (fontconfig's sans-serif here): **44 px**
  - Noto Sans: **52 px**

  With the font fallback alone, the dense 260-frame `ContactSheets` fixture
  comes out `(1590, 1652)` and `checked_sheet_size` raises. I reproduced that as
  a control in a scratch copy. So the band is **measured**: one tiny montage with
  a two-line label in the sheet font. Labels are never more than two lines,
  because `_CONTROL` turns newlines in names into `?`. The measured band is fed
  to `chunk_sheets(..., label_h)`, which already takes it as a parameter, and it
  is floored at the existing 40. Machines whose default font fits 40 keep today's
  layout exactly.
- **Prototype evidence.** The full fix (font + measured band + test helpers) was
  applied in a scratch copy of `.aitask-scripts/screen_recording/` + the test
  module:
  - Liberation fallback: all **120** screen-recording tests pass, the 6 named
    ones included.
  - Fallback forced to Noto: all 36 sheet-layout tests pass
    (`ContactSheets`/`SheetMode`/`BugMode`/`AnimMode`).
  - Control (band left at 40): the 1652 px failure is back.

### B. `test_aitask_questions.py` (2 StoreTests): `ps` truncated to 80 columns under pytest

- The fixture's `_runs_below` reads `ps -o args= -g <pid>` and looks for the
  server-script name in the first two words. Under pytest the child's line comes
  back cut at 80 columns (`…/python /tmp/tmpXXXX/bin/aita`), so the marker never
  matches and `_client` fails with "stand-in (…) never started its child".
- Verified cause: pytest imports `readline`. GNU readline then exports
  `COLUMNS=80` into the C-level environment. That change is invisible to
  `os.environ`, but child processes inherit it. procps `ps` honours `COLUMNS`.
  - Repro: `python -c "import readline; …"` truncates.
  - Without readline: full width.
  - With `-ww`: full width in both cases.
  - Under the unittest backend (no readline) the tests pass. That is why they
    looked deterministic only under the pytest runner.
- **Fix:** `ps -ww`, the documented "unlimited width" flag. It is the same on
  procps and BSD ps. This is a test-fixture defect. The code under test
  (`owner.py`) reads `/proc/<pid>/cmdline` on Linux and is unaffected.

## Implementation

### 1. `.aitask-scripts/screen_recording/video_prep.py`: one label font

Put this next to `SHEET_POINTSIZE` (around line 446). Add `import functools` if
it is missing.

```python
SHEET_FONT_PROBE = "0.000 s first"   # a real second label line

def _label_px(font_args: tuple[str, ...]) -> int:
    """Width magick draws SHEET_FONT_PROBE in at SHEET_POINTSIZE with font_args;
    0 when it cannot draw it at all."""
    try:
        out, _ = run(["magick", "-pointsize", str(SHEET_POINTSIZE), *font_args,
                      f"label:{SHEET_FONT_PROBE}", "-format", "%w", "info:"])
        return int(out.strip())
    except (PrepError, ValueError):
        return 0

def _fontconfig_sans() -> list[str]:
    """fontconfig's sans-serif font file (absolute, existing), or []."""
    if not shutil.which("fc-match"):
        return []
    try:
        out, _ = run(["fc-match", "-f", "%{file}", "sans-serif"])
    except PrepError:
        return []
    p = Path(out.strip())
    return [str(p)] if p.is_absolute() and p.is_file() else []

@functools.lru_cache(maxsize=None)
def sheet_font_args() -> tuple[str, ...]:
    """The -font arguments every sheet label is measured and drawn with: () while
    ImageMagick's default font draws text, else fontconfig's sans-serif file. The
    default can resolve to font files that are not installed (type.xml naming
    gsfonts that are absent), and then it draws every label 1 px wide: blank."""
    if _label_px(()) > SHEET_POINTSIZE:      # 13 glyphs never fit in one em
        return ()
    for path in _fontconfig_sans():
        if _label_px(("-font", path)) > SHEET_POINTSIZE:
            return ("-font", path)
    raise PrepError(
        "ImageMagick draws no text with its default font (its font configuration "
        "names font files that are not installed), and fontconfig offers no "
        "sans-serif font it can draw with, so the sheet labels would be blank. "
        "Install a sans-serif font, or the fonts ImageMagick's type.xml names "
        "(e.g. gsfonts / urw-base35)")
```

Measure the label band next to it:

```python
@functools.lru_cache(maxsize=None)
def sheet_label_h() -> int:
    """Height montage gives a two-line label below a tile, in the sheet font
    (labels are at most two lines: _CONTROL turns newlines into '?'). Floored at
    SHEET_LABEL_H, so a font that fits it keeps the layout it always had; a
    taller one (Liberation Sans 44 px, Noto Sans 52 px at 15 pt) gets its rows
    sized to what is drawn, and the sheet stays within SHEET_MAX_EDGE."""
    with tempfile.TemporaryDirectory(prefix="vp-label-h-") as d:
        tile, out = Path(d) / "t.png", Path(d) / "m.png"
        run(["magick", "-size", "8x8", "xc:black", str(tile)])
        run(["magick", "montage", "-background", "#1e1e1e", "-fill", "#f2f2f2",
             "-pointsize", str(SHEET_POINTSIZE), *sheet_font_args(),
             "-label", f"{SHEET_FONT_PROBE}\n{SHEET_FONT_PROBE}", str(tile),
             "-tile", "1x", "-geometry", "8x8+4+4", str(out)])
        with open(out, "rb") as fh:
            size = core.png_size(fh.read(24))
    if size is None:
        raise PrepError("could not measure the sheet label height")
    return max(SHEET_LABEL_H, size[1] - 8 - 8)   # minus the tile and its +4+4 border
```

Replace `SHEET_LABEL_H` with `sheet_label_h()` in the two `chunk_sheets(...)`
calls, in `contact_sheets` (line ~500) and `cmd_sheet` (line ~2142). The
`SHEET_LABEL_H` comment becomes "floor for the measured label band
(`sheet_label_h`)".

Then add `*sheet_font_args()` right after `"-pointsize", str(SHEET_POINTSIZE)` at
all three call sites:
- `measure_labels` (line ~457)
- `contact_sheets` montage (line ~506)
- `cmd_sheet` montage (line ~2154)

`_fit_names` goes through `measure_labels`, so it inherits the font. Update the
`measure_labels` docstring from "the default font" to "the sheet font
(`sheet_font_args`)".

### 2. `tests/test_screen_recording_cli.py`: test helpers use the same font

- Add a helper `font_args()` that returns
  `list(video_prep.sheet_font_args())`. Import `video_prep` lazily, the way the
  module's existing in-test `import video_prep` does.
- Pass `*font_args()` after `-pointsize 15` at the four helper and premise call
  sites:
  - `label_width()` (line ~1467)
  - the pre-t2219 overflow premise montage (line ~172)
  - the narrow-tiles premise montage (line ~1700)
  - the `w_min` measurement in `test_too_many_per_sheet_is_split_with_a_warning`
    (line ~1727)

  Without this, the premises measure a font that production no longer draws in.
- In that same `w_min` premise, replace the hard-coded `(64 + 40 + 8)` row pitch
  with `(64 + video_prep.sheet_label_h() + 8)`. Leave `pre_t2219_layout`'s
  `label_h=40` default unchanged: it models the old code on purpose.
- Add a `SheetFont` test class. Each test calls `video_prep.sheet_font_args.cache_clear()`
  in setUp and tearDown, and patches `video_prep._label_px` and
  `video_prep._fontconfig_sans`:
  1. The default font is kept when it draws text: `_label_px(()) → 90` gives `()`,
     and fontconfig is never consulted.
  2. fontconfig's font is used when the default draws nothing: `() → 1` and
     `("-font", "/f.ttf") → 90` give `("-font", "/f.ttf")`.
  3. A fontconfig font that also draws nothing is skipped, and the result is a
     `PrepError` whose message names the cause ("draws no text").
  4. No fc-match: `_fontconfig_sans → []` with a blank default gives `PrepError`.
  5. A real-environment symptom guard, `@skipUnless(HAVE_MAGICK)`:
     `video_prep.measure_labels([SHEET_FONT_PROBE])[0][0] > 3 * SHEET_POINTSIZE`.
     The sheet labels have real width on whatever machine runs the suite. This
     test fails before the fix on this box, because the width is 1.
  6. A real-environment band guard, `@skipUnless(HAVE_MAGICK)`. Montage two
     rows of 8×8 tiles with two-line `SHEET_FONT_PROBE` labels in the sheet font
     (`-tile 1x -geometry 8x8+4+4`). The image height must be at most
     `2 * (8 + 8 + sheet_label_h())`, and `sheet_label_h() >= SHEET_LABEL_H`.
     That proves the modelled row pitch covers what montage draws. Test 6 is the
     direct check; the dense 260-frame `ContactSheets` test remains the
     end-to-end check.
  7. A mocked check that `sheet_label_h()` never goes below `SHEET_LABEL_H`:
     patch `run` so the measured montage is shorter than 40.

### 3. `tests/test_aitask_questions.py`: `_runs_below` reads full-width `ps`

- Line ~526: `["ps", "-ww", "-o", "args=", "-g", str(pid)]`.
- Add a comment saying why: under pytest, readline has exported `COLUMNS=80`,
  procps `ps` honours it and cuts each line, and `-ww` lifts the limit.

### 4. Docs: `website/content/docs/skills/aitask-screen-recording.md`

- Line ~147: replace "measured with the font ImageMagick uses on your machine"
  with "measured with the font the labels are drawn in: ImageMagick's default
  font, or fontconfig's sans-serif font when the default draws no text (its font
  files not installed)". Add that each row leaves room for the two label lines
  as that font draws them. Keep the prose current-state only.
- Add a troubleshooting-table row for bug / anim / sheet, next to the existing
  ImageMagick rows (lines ~373 / ~419). The row names the new error, gives the
  cause (no font ImageMagick can draw text with) and the fix (install a
  sans-serif font, or gsfonts).
- Run `python3 check_links.py --build` in `website/`.

## Verification

1. `~/.aitask/venv/bin/python -m pytest -p no:randomly -q tests/test_screen_recording_cli.py tests/test_aitask_questions.py`
   passes with 0 failed, including the 8 named tests and the new `SheetFont` tests.
2. The same two modules run under the unittest backend (`python3 tests/test_screen_recording_cli.py`,
   `python3 tests/test_aitask_questions.py`) also pass.
3. Pre-fix controls:
   - `SheetFont` test 5 and the 6 screen-recording tests fail on the old
     `video_prep.py`. That is already observed: width 1, and the 6 failures above.
   - Font-only (band left at 40): `ContactSheets` raises at 1590×1652. Already
     observed in the prototype. Re-run it once against the real file by
     temporarily returning `SHEET_LABEL_H` from `sheet_label_h`, then restore it.
   - The questions fix is checked by the observed truncation at 80 columns, then
     full width with `-ww`.
3b. Second font: re-run `ContactSheets SheetMode BugMode AnimMode` with
   `_fontconfig_sans` forced to `/usr/share/fonts/noto/NotoSans-Regular.ttf`
   (52 px band) through a temporary local edit, then restore it. The prototype
   already passed 36/36 this way.
4. Manual: build a sheet from a small folder of images with
   `./.aitask-scripts/aitask_screen_recording.sh sheet <dir>`. Then view
   `sheet_01.png` and confirm the labels are visible.
5. Full suite: `set -o pipefail; bash tests/run_all_python_tests.sh 2>&1 | tail -3`.
   The last line should read `PYTHON SUITE: PASSED`.
6. `python3 website/check_links.py --build` (from `website/`) is clean.

## Step 9 (Post-Implementation)

Current-branch mode, so there is no merge. Commit the code as
`bug: … (t2306)` with named paths, and the plan with `./.aitask-scripts/aitask_task_commit.sh`.
Then the Step 9 archival per task-workflow.

Not in scope, for Final Implementation Notes and the Step 8b offer: the
non-procfs fallbacks `owner._argv` (`.aitask-scripts/aitask_questions/owner.py:38`)
and `monitor_core.py:502` call `ps -o args=` without `-ww`. If they run in a
process that imported readline, they get the same 80-column cut. Both run only
without `/proc` (macOS), and BSD ps width handling under `COLUMNS` was not measured.

## Risk

### Code-health risk: low
- Production now spends one extra `magick` call per process to probe the label font (cached via `lru_cache`). On machines where the default font works, the output is byte-identical, because the font args stay `()`. · severity: low · → mitigation: none (SheetFont test 1 pins the unchanged path)
- A fontconfig fallback font has different metrics from the default, in both width and height. Width measurement and drawing share one `sheet_font_args()`, and the row band is measured in that same font (`sheet_label_h`, floored at 40), so the layout stays self-consistent and within 1600 px. · severity: low · → mitigation: none (SheetFont tests 6 and 7, the dense ContactSheets test, and Verification 3b with a second font)
- Production now spends one more small `magick` montage per process to measure the band (cached). · severity: low · → mitigation: none

### Goal-achievement risk: low
- Other environment-dependent assertions could have been hidden behind the blank-font failure and surface once labels render. · severity: low · → mitigation: none (Verification 1, 2 and 5 run both modules and the whole suite)

## Post-Review Changes

### Change Request 1 (2026-11-15 22:45)
- **Requested by user:** `_label_px` turned every `PrepError` into width 0, so a
  magick failure that has nothing to do with fonts (reproduced: a policy.xml
  denying the LABEL coder) was reported as "install fonts", and the error claimed
  missing font files without evidence. Keep the underlying error, and do not
  assert the cause.
- **Changes made:**
  - `_label_px` now raises `PrepError` carrying magick's own message.
  - `sheet_font_args` re-raises a failure of the default probe unchanged, and
    tries no other font, because none could draw either.
  - A failing fallback candidate is recorded as `<path>: <error>` and named in
    the final error, which now gives the measured default width and states the
    usual cause as likely rather than certain.
  - New tests:
    - a mocked default-probe failure (the same exception surfaces, and
      fontconfig is never consulted)
    - a mocked failing candidate (named in the message)
    - an end-to-end `sheet` run under a real `MAGICK_CONFIGURE_PATH` policy
      denying LABEL (stderr carries "not authorized", not the font advice)
  - Docs troubleshooting row updated to match.
- **Files affected:** `.aitask-scripts/screen_recording/video_prep.py`,
  `tests/test_screen_recording_cli.py`,
  `website/content/docs/skills/aitask-screen-recording.md`

### Change Request 2 (2026-11-15 23:20)
- **Requested by user:** after CR1, a `PrepError` from the default probe escaped
  before fontconfig was consulted. Not every default-probe error means no font
  can draw. Reproduced: a `type.xml` mapping the default font to an unreadable
  file made `sheet` fail with "unable to read font", while LiberationSans
  measured 79 px under the same configuration. That removed recovery the first
  version had. Keep the default error, try the fallback, and surface the kept
  diagnostics if nothing works; add a regression.
- **Changes made:**
  - `sheet_font_args` now keeps the default probe's error and still tries
    fontconfig. With no candidate to try, the default error is raised unchanged.
    When candidates were tried and all failed, the message names the default's
    error and each candidate's (`ImageMagick could not draw a sample label with
    its default font (…), and fontconfig's sans-serif font did not help either: …`),
    with no font-install advice.
  - The "draws no text … install a sans-serif font" message is used only when
    the default probe measured a blank width.
  - Tests:
    - mocked: an unreadable default font falls back
    - mocked: a lone default failure is re-raised as it is
    - mocked: default and fallback both failing report both messages and no
      font advice
    - end-to-end: `sheet` under a `MAGICK_CONFIGURE_PATH` `type.xml` that maps
      Helvetica/Arial to a non-font file succeeds, with label-sized cells
      (cell_w > 64)

    The policy e2e test now shares a `sheet_under_config` helper. Docs row
    covers both message forms.
- **Files affected:** `.aitask-scripts/screen_recording/video_prep.py`,
  `tests/test_screen_recording_cli.py`,
  `website/content/docs/skills/aitask-screen-recording.md`

## Final Implementation Notes
- **Actual work done:**
  - `video_prep.py` resolves one label font (`sheet_font_args`): ImageMagick's
    default font while it draws text, else fontconfig's sans-serif file, else an
    error that carries the kept diagnostics.
  - It measures the two-line label band in that font (`sheet_label_h`, floored
    at `SHEET_LABEL_H`) and uses both at every measure, draw and layout site:
    `measure_labels`, the two montages, and the two `chunk_sheets` calls.
  - The test helpers and premises in `test_screen_recording_cli.py` use the same
    font and band. A new `SheetFont` class adds 13 tests: 4 end-to-end or real
    environment, the rest mocked.
  - `test_aitask_questions.py` `_runs_below` uses `ps -ww`.
  - The docs layout paragraph and the troubleshooting row are updated.
- **Deviations from plan:**
  - The label-band measurement was added during plan review: the font alone
    overflowed the dense sheet to 1590×1652.
  - The error handling was reworked twice in Step 8 review (Change Requests 1
    and 2): magick failures are kept rather than turned into width 0, and a
    default-probe failure still tries the fallback.
- **Issues encountered:**
  - Root cause 1: on this machine ImageMagick's default font, Helvetica, maps
    through `type-ghostscript.xml` to gsfonts files that are not installed.
    Every label then renders 1 px wide.
  - Root cause 2: pytest imports readline, and GNU readline exports `COLUMNS=80`
    into the C environment (`os.environ` does not show it). procps `ps` honours
    it and truncates `args`. Under the unittest backend the tests passed.
  - The full suite had 1 unrelated failure:
    `test_metadata_writer_inventory::NewWriterTripwire` flags
    `.aitask-scripts/lib/sitrep_crash.py`, an untracked file from another
    session. It was already present when this task started.
- **Key decisions:**
  - Keep the default font when it draws, and keep the 40 px band floor, so
    machines where the default works are byte-identical.
  - Font-install advice appears only when the default measured blank; magick's
    own errors are passed through.
  - Labels are at most 2 lines (`_CONTROL` maps newlines to `?`), so a two-line
    probe bounds the band.
- **Verification:**
  - Both modules pass under pytest and unittest (133 and 41).
  - Control with the band left at 40: the dense ContactSheets test and the
    band test fail at 1590×1652.
  - Noto Sans forced as the fallback (52 px band): 43/43 sheet tests pass.
  - A manual `sheet` run shows readable labels.
  - `check_links.py --build` passes.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_questions/owner.py:38 — non-procfs fallback reads `ps -o args=` without `-ww`; in a process that imported readline (COLUMNS=80 exported) argv is cut at 80 columns (macOS-only path; BSD ps COLUMNS handling not measured)`
  - `.aitask-scripts/monitor/monitor_core.py:502 — same `ps -p <pid> -o args=` without `-ww` in the non-procfs companion-keyword check; keywords past column 80 can be missed`
