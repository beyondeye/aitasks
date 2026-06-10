---
Task: t960_codeviewer_render_regression_tests.md
Worktree: (none — working on current branch, profile 'fast')
Branch: main
Base branch: main
---

# Plan: Render-level regression tests for codebrowser's CodeViewer (t960)

## Context

The t959 refactor moved `CodeViewer`'s render loop onto the shared
`NumberedSourceView` base (`.aitask-scripts/lib/numbered_source_view.py`) and
unified `_highlighted_lines` → `_lines`. The base now owns the boxless Rich
`Table` skeleton, width calc, the number→row loop, and `on_resize`→rebuild;
`CodeViewer` layers on its divergences through override hooks (file-aware lexer,
annotation gutter as a 3rd column, viewport windowing with above/below
indicators, cursor/selection row styling, wrap/truncate toggle).

That core render path is currently covered **only** by
`tests/test_code_viewer_control_chars.py`, which exercises `_sanitize_control_chars`
and a standalone Rich render — it never drives `CodeViewer` itself. Two
medium code-health risks called out in the t959 risk evaluation are unguarded:

- the render loop now lives in shared code touched by both hosts; and
- the annotation gutter moved from inline-in-`_rebuild_display` to a
  `_prepare_build` precompute + per-row `_extra_cell(file_idx)` lookup that
  indexes off `file_idx - self._build_start` — an off-by-one there would
  mis-render the gutter, especially in viewport mode where `_build_start` is
  non-zero.

This task adds a Textual-pilot regression test that drives the live widget and
locks in the post-refactor render contract.

## Approach

Add one new test file, `tests/test_code_viewer_render.py`, mirroring the
harness style of `tests/test_brainstorm_proposal_preview.py` (a minimal
`App` host + `app.run_test(size=...)` pilot, `asyncio.run` per test). Drive a
real `CodeViewer` mounted in the host and assert against its public state and
the built `self._table`.

### Harness setup

- `sys.path` insert `.aitask-scripts/codebrowser` **and** `.aitask-scripts/lib`
  (code_viewer imports `numbered_source_view` from lib and `annotation_data`
  from codebrowser). `code_viewer.py` already self-inserts lib at import, but
  inserting both keeps the test explicit and matches the brainstorm test.
- `from code_viewer import CodeViewer, CURSOR_STYLE, SELECTION_STYLE` and
  `from annotation_data import AnnotationRange`.
- A `_HostApp(App)` whose `compose` yields a single `CodeViewer(id="viewer")`.
- `CodeViewer.load_file()` reads from disk, so write fixture files to a
  `tempfile.TemporaryDirectory()` per test (or a class-level temp dir). Use a
  `.py` extension so the lexer produces highlight spans.
- Files end **without** a trailing newline mismatch concern: assert against
  `content.splitlines()`, which agrees with the highlighter's split (the
  highlighter drops the empty trailing line after a final `\n`).

### Test cases (one per task bullet)

1. **One row per source line / `_total_lines`** — load a small multi-line `.py`
   file; assert `viewer._total_lines == len(content.splitlines())` and (no
   viewport) `viewer._table.row_count == viewer._total_lines`.

2. **3-column layout + highlight spans** — assert `len(viewer._table.columns) == 3`
   (line-number + content + annotation gutter, per `_has_extra_column()==True`)
   and `any(line.spans for line in viewer._lines)` for a Python source file.

3. **Annotation gutter indexing (non-viewport)** — `set_annotations([
   AnnotationRange(start_line=3, end_line=3, task_ids=["42"])])`; assert
   `viewer._extra_cell(2).plain == "t42"` (file line 3 = 0-indexed 2) and an
   un-annotated line `viewer._extra_cell(0).plain == ""`. This pins the
   `_prepare_build` gutter + `_extra_cell` lookup with `_build_start == 0`.

4. **Annotation gutter indexing (viewport / `_build_start` offset)** — load a
   2500-line file (> `_viewport_threshold` 2000 → `_viewport_mode` True);
   annotate the 2400th line (`AnnotationRange(start_line=2400, end_line=2400,
   task_ids=["77"])`); `move_cursor(2399)` to shift the viewport window over it
   (`_build_start` becomes non-zero, ~2230). Assert `viewer._extra_cell(2399).plain
   == "t77"` and the off-by-one neighbor `viewer._extra_cell(2398).plain == ""`.
   This is the core guard for `idx = file_idx - self._build_start`.

5. **Cursor / selection row styles** — `move_cursor(5)`; assert
   `viewer._row_style(5) is CURSOR_STYLE`. Then `extend_selection(1)` twice
   (selection 5..7, cursor at 7); assert `viewer._row_style(6) is SELECTION_STYLE`
   (mid-selection, not cursor) and `viewer._row_style(7) is CURSOR_STYLE` (cursor
   wins). `_sel_min/_sel_max` are populated by `_prepare_build` during the
   rebuild that `move_cursor`/`extend_selection` trigger.

6. **Wrap vs truncate toggle** — load a file containing one very long line
   (e.g. 200 chars, > the ~73 content width at size (80,24) and below
   `MAX_LINE_WIDTH` 500). In default truncate mode, the content cell
   (`viewer._table.columns[1]._cells[row]`) `.plain` ends with `"…"`. Call
   `viewer.cycle_wrap_mode()` → `"wrap"`; after rebuild the same cell `.plain`
   equals the full untruncated line and does **not** end with `"…"`.

7. **Viewport windowing indicators** — reuse a >2000-line file; assert
   `viewer._viewport_mode` is True. At `_viewport_start == 0`: a "lines below"
   indicator row is present, no "lines above" → `row_count == _viewport_size + 1`.
   After `move_cursor` into the middle, both indicators present →
   `row_count == _viewport_size + 2`; assert indicator cell text contains
   "lines above" / "lines below" (scan `columns[1]._cells`).

### Notes / gotchas

- All widget interaction must happen inside the `app.run_test()` context after
  an initial `await pilot.pause()` — `load_file`/`_rebuild_display` call
  `query_one(self._INNER_ID)`, `self.size`, and `self.app.size`, which require
  the widget mounted.
- Rich stores built cells on `Column._cells`; content column is index 1, gutter
  index 2. Indicator rows are added by `_pre_rows`/`_post_rows` so they shift
  `row_count` but not `_total_lines`.
- Pure additive change: one new test file. No production code is modified, so
  blast radius is nil. If a test surfaces an actual off-by-one or contract bug
  in `CodeViewer`/`NumberedSourceView`, record it under the plan's "Upstream
  defects identified" rather than silently patching production code under a
  test task (raise it for the Step 8b follow-up).

## Key files

- NEW: `tests/test_code_viewer_render.py`
- Read/reference (unchanged): `.aitask-scripts/codebrowser/code_viewer.py`,
  `.aitask-scripts/lib/numbered_source_view.py`,
  `.aitask-scripts/codebrowser/annotation_data.py`
- Harness reference: `tests/test_brainstorm_proposal_preview.py`,
  `tests/test_code_viewer_control_chars.py`

## Verification

- `python3 tests/test_code_viewer_render.py` → all tests PASS (the env has
  textual 8.2.7; the brainstorm pilot test already runs green under `python3`).
- Optionally run the existing `python3 tests/test_code_viewer_control_chars.py`
  to confirm no import regression from the shared `sys.path` setup.
- See **Step 9 (Post-Implementation)** of the task-workflow for archival/merge.

## Risk

### Code-health risk: low
- Tests assert against widget/Rich internals (`_table`, `Column._cells`,
  `_build_start`, `_extra_cell`, `_row_style`), coupling them to the current
  render structure · severity: low · → mitigation: none (acceptable — this is a
  render-contract regression test; that coupling is the point, and it is the
  cheapest way to pin the t959 refactor's behavior)

### Goal-achievement risk: low
- None identified. The six assertions map 1:1 to the task's bullets, the pilot
  harness is proven to run green under `python3` (textual 8.2.7), and no
  production code changes.
