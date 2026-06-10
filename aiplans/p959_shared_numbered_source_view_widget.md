---
Task: t959_shared_numbered_source_view_widget.md
Worktree: (none — working on current branch, profile 'fast')
Branch: main
Base branch: main
---

# t959 — Shared `NumberedSourceView` base widget

## Context

t954 added `_NumberedProposal` to `.aitask-scripts/brainstorm/brainstorm_app.py`
(brainstorm Actions-tab numbered proposal preview): a boxless Rich `Table` with
a right-justified `no_wrap` line-number column + a wrapping content column (one
source line per row, so numbers survive reflow), markdown-highlighted via
`Syntax(...).highlight(...).split("\n")`. This re-implements the same idiom that
already lives in `.aitask-scripts/codebrowser/code_viewer.py` (`CodeViewer`).

The decision (with the user) is to extract the **full coherent base widget**
(~40-60 lines: highlight + per-line split + cache, width calc, boxless table
skeleton, the number→row loop, `Static.update`, `on_resize`→rebuild) into
`.aitask-scripts/lib/` and sit both TUIs on it. `lib/` is already on `sys.path`
for both codebrowser (PyPy — `codebrowser_app.py:30`) and brainstorm (CPython —
`brainstorm_app.py:14`), so a single module imports cleanly in both.

## Design: hook-based base, both widgets as thin adopters

New file **`.aitask-scripts/lib/numbered_source_view.py`** — `NumberedSourceView(VerticalScroll)`.
Depends only on `textual` + `rich` + stdlib (no brainstorm/codebrowser imports),
so it is import-safe under PyPy and CPython.

The base owns the shared idiom and exposes clean override points for the 5
divergences the task enumerated. **Base defaults exactly match `_NumberedProposal`'s
current behavior**, so the brainstorm side becomes a near-empty subclass.

### Base attributes & methods

```python
from __future__ import annotations
import time
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text


class NumberedSourceView(VerticalScroll):
    LINE_NUM_WIDTH = 5
    _INNER_ID = "numbered_source_inner"     # overridable per host

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._text = ""
        self._lines: list[Text] = []        # cached highlighted per-line Text
        self._table = None                  # last built Table (one row/source line)
        self._build_start = 0               # render-range start of last build

    def compose(self) -> ComposeResult:
        yield Static(self._placeholder(), id=self._INNER_ID)

    def _inner_static(self) -> Static:
        return self.query_one(f"#{self._INNER_ID}", Static)

    # ---- hooks (override points; defaults == _NumberedProposal behavior) ----
    def _placeholder(self) -> str: return ""
    def _select_lexer(self, code: str) -> str: return "markdown"
    def _wrap(self) -> bool: return True
    def _render_range(self) -> tuple[int, int]: return 0, len(self._lines)
    def _has_extra_column(self) -> bool: return False
    def _extra_column_width(self) -> int: return 0
    def _extra_cell(self, file_idx: int) -> Text: return Text("")
    def _row_style(self, file_idx: int): return None
    def _truncate_line(self, line: Text, code_max_width: int) -> Text: return line
    def _prepare_build(self, start: int, end: int) -> None: pass
    def _pre_rows(self, table: Table, start: int, end: int) -> None: pass
    def _post_rows(self, table: Table, start: int, end: int) -> None: pass
    def _rebuild_log_detail(self) -> str: return f"{len(self._lines)} lines"

    # ---- core ----
    def _highlight(self, text: str) -> list[Text]:
        lexer = self._select_lexer(text)
        return Syntax(text, lexer, theme="monokai").highlight(text).split("\n")

    def set_text(self, text: str) -> None:
        self._text = text or ""
        self._lines = self._highlight(self._text)
        self._rebuild_display()

    def _content_width(self) -> int:
        available = self.size.width if self.size.width > 0 else 120
        extra = self._extra_column_width() if self._has_extra_column() else 0
        return max(20, available - self.LINE_NUM_WIDTH - extra - 2)

    def _rebuild_display(self) -> None:
        t0 = time.perf_counter()
        start, end = self._render_range()
        self._build_start = start
        self._prepare_build(start, end)
        code_w = self._content_width()
        table = Table(show_header=False, show_edge=False, box=None, pad_edge=False)
        table.add_column(style="dim", justify="right",
                         width=self.LINE_NUM_WIDTH, no_wrap=True)
        table.add_column(no_wrap=not self._wrap(), width=code_w)
        if self._has_extra_column():
            table.add_column(width=self._extra_column_width(),
                             no_wrap=True, justify="left")
        self._pre_rows(table, start, end)
        for file_idx in range(start, end):
            line = self._lines[file_idx]
            if not self._wrap():
                line = self._truncate_line(line, code_w)
            cells = [Text(str(file_idx + 1), style="dim"), line]
            if self._has_extra_column():
                cells.append(self._extra_cell(file_idx))
            table.add_row(*cells, style=self._row_style(file_idx))
        self._post_rows(table, start, end)
        self._table = table
        self._inner_static().update(table)
        elapsed = time.perf_counter() - t0
        if elapsed > 0.05:
            self.log(f"_rebuild_display: {elapsed*1000:.1f}ms ({self._rebuild_log_detail()})")

    def on_resize(self, event) -> None:
        if self._lines:
            self._rebuild_display()
```

This maps the 5 required extension hooks: (1) lexer → `_select_lexer`;
(2) per-row styling → `_row_style`; (3) optional extra column →
`_has_extra_column`/`_extra_column_width`/`_extra_cell`; (4) render-range +
indicators → `_render_range` + `_pre_rows`/`_post_rows` (+ `_prepare_build`);
(5) wrap-vs-truncate → `_wrap` + `_truncate_line`.

## Changes

### 1. NEW `.aitask-scripts/lib/numbered_source_view.py`
The base above. Module docstring noting it is the shared base for codebrowser
`CodeViewer` and brainstorm `_NumberedProposal`, PyPy+CPython safe.

### 2. `.aitask-scripts/brainstorm/brainstorm_app.py` — `_NumberedProposal`
Collapse to a thin subclass. Base defaults already give: markdown lexer,
always-wrap, full render range, no extra column, no per-row style, `_table`
cache, `set_text`/`on_resize`/`_rebuild_display`. So the class keeps **only** its
`DEFAULT_CSS`, its docstring, and `_INNER_ID = "preview_numbered_inner"`:

```python
from numbered_source_view import NumberedSourceView   # add near lib imports (line ~14 block)

class _NumberedProposal(NumberedSourceView):
    """<existing docstring, trimmed to note it now subclasses NumberedSourceView>"""
    DEFAULT_CSS = """ _NumberedProposal { height: 1fr; width: 1fr; padding: 0 1; } """
    _INNER_ID = "preview_numbered_inner"
```

Delete the now-inherited `LINE_NUM_WIDTH`, `__init__`, `compose`, `set_text`,
`on_resize`, `_rebuild`. Preserved invariants (covered by
`test_brainstorm_proposal_preview.py`): instances expose `_text`, `_lines`
(highlighted, with style spans), `_table` (row_count == source lines); the widget
mounts only a `Static` (no `TextArea`/`CycleField`/`RadioSet`) so the
`_actions_collect_config` single-match collector contract holds. `_INNER_ID`
keeps the inner `Static` id `preview_numbered_inner`.

### 3. `.aitask-scripts/codebrowser/code_viewer.py` — `CodeViewer`
Refactor onto the base while keeping **all** current behavior (viewport,
annotations, cursor/selection, truncate/wrap, control-char sanitize, binary/empty
messages, `CursorMoved`, mouse/edge-scroll).

- **Imports (top of file):** add lib to `sys.path` (mirror `section_viewer.py`'s
  parent-path guard) so importing `code_viewer` standalone resolves the base —
  the control-chars test only puts `codebrowser/` on the path:
  ```python
  import sys
  from pathlib import Path
  _LIB = Path(__file__).resolve().parent.parent / "lib"
  if str(_LIB) not in sys.path:
      sys.path.insert(0, str(_LIB))
  from numbered_source_view import NumberedSourceView
  ```
  `class CodeViewer(NumberedSourceView):` (was `VerticalScroll`). Keep its
  `BINDINGS`, `MAX_LINE_WIDTH`, `CursorMoved`, `ANNOTATION_COLORS`,
  `CURSOR_STYLE`, `SELECTION_STYLE`.

- **Attribute unification — `_highlighted_lines` → inherited `_lines`:** the base
  uses `self._lines` for highlighted `Text`; `CodeViewer` currently uses
  `self._lines` for raw `splitlines()` (read only to compute `_total_lines`) and
  `self._highlighted_lines` for highlighted `Text`. Replace every
  `self._highlighted_lines` with `self._lines`, and drop the raw-splitlines
  assignment. `_total_lines` stays a `CodeViewer` attribute, set to
  `len(self._lines)` after highlight (equal to the old `splitlines()` count — the
  existing render already indexes `_highlighted_lines` up to `_total_lines`, so
  they are already equal or the current code would IndexError).

- **`__init__`:** call `super().__init__(*args, **kwargs)`; drop the
  `self._lines`/`self._highlighted_lines` inits (base sets `_lines`); keep
  `_total_lines`, `_file_path`, viewport/selection/cursor/wrap/mouse attrs.
  `_wrap_mode` stays.

- **`compose`/Static id:** delete `CodeViewer.compose`; set
  `_INNER_ID = "code_display"` and override `_placeholder()` →
  `"Select a file to view"`. Base `compose` then yields
  `Static("Select a file to view", id="code_display")` — identical, so the
  `#code_display` CSS selector in `codebrowser_app.py:317` still matches.

- **`_show_message` / `show_binary_info`:** replace
  `self.query_one("#code_display", Static)` with `self._inner_static()`; set
  `self._lines = []` (drop `_highlighted_lines`).

- **`load_file`:** keep read/binary/empty/sanitize/`expandtabs` logic. Replace the
  highlight block with the base helper:
  ```python
  self._reset_state()
  self._lines = self._highlight(content)         # uses CodeViewer._select_lexer
  self._total_lines = len(self._lines)
  self._viewport_mode = self._total_lines > self._viewport_threshold
  self._rebuild_display()
  self.scroll_home(animate=False)
  ```

- **Replace `CodeViewer._rebuild_display` with hook overrides** (the base loop now
  builds the table):
  - `_select_lexer(self, code)` → `Syntax.guess_lexer(str(self._file_path), code=code)`
  - `_wrap(self)` → `self._wrap_mode == "wrap"`
  - `_render_range(self)` → viewport bounds: `(vp_start, vp_end)` in viewport mode
    else `(0, self._total_lines)`
  - `_has_extra_column(self)` → `True` (CodeViewer always has the 3rd/annotation
    column, width 0 when hidden — matches current 3-column table)
  - `_extra_column_width(self)` →
    `self._annotation_col_width() if (self._show_annotations and self._annotations) else 0`
  - `_prepare_build(self, start, end)` → compute & stash for the row loop:
    `self._gutter = self._build_annotation_gutter(start, end)` when annotations
    shown else `[Text("")] * (end - start)`; and
    `self._sel_min, self._sel_max = self._selection_bounds()`
  - `_extra_cell(self, file_idx)` →
    `self._gutter[file_idx - self._build_start]` (guard index bounds → `Text("")`)
  - `_row_style(self, file_idx)` → `CURSOR_STYLE` if `file_idx == self._cursor_line`
    elif selection bounds contain it → `SELECTION_STYLE` else `None`
  - `_truncate_line(self, line, code_w)` → existing truncate (copy/truncate/`…`)
    bounded by `min(self.MAX_LINE_WIDTH, code_w)`
  - `_pre_rows(self, table, start, end)` → "··· N lines above ···" indicator row
    (3 cells) when `_viewport_mode and start > 0`
  - `_post_rows(self, table, start, end)` → "··· N lines below ···" indicator row
    (3 cells) when `_viewport_mode and end < self._total_lines`
  - `_rebuild_log_detail(self)` → `f"{self._total_lines} lines, viewport={self._viewport_mode}"`
  Everything else in `CodeViewer` (gutter builder, `_annotation_col_width`,
  `cycle_wrap_mode`, viewport math, cursor/selection actions, mouse/edge-scroll)
  is unchanged and keeps calling `self._rebuild_display()` (now the inherited one).

- **`_build_annotation_gutter`** is unchanged but currently defaults
  `vp_end = len(self._highlighted_lines)` → change to `len(self._lines)`.

No changes needed in `codebrowser_app.py` (constructs `CodeViewer(id="code_viewer")`,
CSS targets `#code_viewer`/`#code_display` — both preserved) or
`test_brainstorm_proposal_preview.py` (imports `_NumberedProposal`, accesses
`_text`/`_lines`/`_table` — all preserved).

## Risk

### Code-health risk: medium
- `CodeViewer` is load-bearing and PyPy-routed; moving its render loop into a base
  and unifying `_highlighted_lines`→`_lines` touches the core render path ·
  severity: medium · → mitigation: codeviewer_render_regression_tests
- The annotation-gutter precompute moves from inline-in-`_rebuild_display` to a
  `_prepare_build` hook + per-row `_extra_cell` lookup; an off-by-one in the
  `file_idx - _build_start` index would mis-render the gutter · severity: medium
  · → mitigation: codeviewer_render_regression_tests

### Goal-achievement risk: low
- Goal (shared base + adopt in both, 5 enumerated hooks) is precise; base defaults
  reproduce `_NumberedProposal` exactly and the divergence points are known ·
  severity: low · → mitigation: None needed

### Planned mitigations
- timing: after | name: codeviewer_render_regression_tests | type: test | priority: medium | effort: medium | addresses: code-health (render path moved into base + gutter precompute off-by-one) | desc: Render-level regression test for CodeViewer (viewport above/below indicators, annotation-gutter cell content, cursor/selection row styles, wrap-vs-truncate) — the codebrowser side has only the control-chars test today

## Verification
- `python tests/test_brainstorm_proposal_preview.py` — all 19 green (one-row-per-
  source-line, reflow-survival, syntax-highlight, focus-ring numbered-mode).
- `python tests/test_code_viewer_control_chars.py` — all 7 green (the only
  codebrowser test; also confirms `code_viewer` imports standalone with only
  `codebrowser/` on `sys.path`, i.e. the lib-path guard works).
- `python -c "import sys; sys.path.insert(0,'.aitask-scripts/lib'); import numbered_source_view"` — base imports clean.
- `shellcheck` n/a (no shell changes).
- Manual: `ait codebrowser` — highlighted code with line numbers, annotation
  gutter, viewport indicators on a 2000+ line file, cursor move, multi-line
  shift-select, `w` wrap toggle all behave as before. `ait brainstorm` Actions tab
  → Ctrl+Shift+L numbered view unchanged (numbers track source lines across
  reflow; markdown highlighting; toggle/focus-ring).

Follow Step 9 (Post-Implementation) of the task-workflow for archival.
