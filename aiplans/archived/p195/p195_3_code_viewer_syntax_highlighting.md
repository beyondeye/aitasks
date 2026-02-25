---
Task: t195_3_code_viewer_syntax_highlighting.md
Parent Task: aitasks/t195_python_codebrowser.md
Sibling Tasks: aitasks/t195/t195_1_*.md, aitasks/t195/t195_2_*.md, aitasks/t195/t195_4_*.md
Branch: main
Base branch: main
---

# Plan: t195_3 — Code Viewer with Syntax Highlighting

## Steps

### 1. Create `aiscripts/codebrowser/code_viewer.py`
- `CodeViewer(VerticalScroll)`:
  - `compose()`: yield `Static(id="code_display")`
  - `load_file(file_path: Path)`:
    1. Read file: `file_path.read_text(errors="replace")`
    2. Detect lexer: `Syntax.guess_lexer(str(file_path), code=content)` or fallback "text"
    3. Create `Syntax` object → call `syntax.highlight(content)` to get Rich `Text`
    4. Split by newlines to get per-line `Text` objects
    5. Build `Rich.Table(show_header=False, show_edge=False, box=None, pad_edge=False)`:
       - Column 1: line number (style="dim", justify="right", width=5, no_wrap=True)
       - Column 2: code line (no_wrap=True)
    6. `self.query_one("#code_display", Static).update(table)`
  - Store: `self._file_path`, `self._lines: list[str]`, `self._total_lines: int`
  - Empty state: default content "Select a file to view"

### 2. Update `codebrowser_app.py`
- Import `CodeViewer`
- Right pane: `Static("No file selected", id="file_info_bar")` + `CodeViewer(id="code_viewer")`
- Wire `on_directory_tree_file_selected()`: call `self.query_one(CodeViewer).load_file(event.path)`
- Update info bar: filename + line count
- CSS:
  - `#file_info_bar { height: 1; dock: top; background: $surface-lighten-1; padding: 0 1; }`
  - `#code_viewer { height: 1fr; }`
  - `#code_display { width: auto; }`

### 3. Per-line syntax approach
Option A (preferred): Use Rich `Syntax.highlight()` which returns a `Text` object, then split by `\n`.
Option B (fallback): Use Pygments tokenizer directly to build `Text` per line.

Start with Option A; fall back to B if splitting loses style information.

## Verification
- Select .py → Python highlighting
- Select .sh → Bash highlighting
- Select .md → Markdown highlighting
- Line numbers correct and right-aligned
- Scrolling works for long files

## Final Implementation Notes
- **Actual work done:** All steps implemented as planned. Created `code_viewer.py` with `CodeViewer(VerticalScroll)` widget using `Syntax.highlight()` + `Text.split('\n')` + Rich `Table` pipeline. Updated `codebrowser_app.py` with imports, file info bar, wired file selection handler, updated CSS and focus toggle.
- **Deviations from plan:** Option A (Syntax.highlight + split) worked perfectly — no need for fallback Option B. Added `_rebuild_display()` as a separate method (not in original plan step list but mentioned in verification notes) for clean separation and future extensibility by t195_5/t195_6/t195_9. Also stored `_highlighted_lines` as instance variable for reuse.
- **Issues encountered:** None. Smoke test confirmed `Syntax.highlight()` returns `Text`, `Text.split('\n')` preserves style spans with correct offsets, and `Syntax.guess_lexer()` detects languages from file extensions.
- **Key decisions:** Used per-line Table approach (not direct `Syntax` pass to `Static.update()` or `TextArea`) because downstream tasks need per-line access for annotation gutter, cursor highlighting, and viewport windowing. Removed `padding: 1` from `#code_pane` CSS to avoid awkward spacing with docked info bar.
- **Notes for sibling tasks:** `CodeViewer._rebuild_display()` is the method to extend for adding columns (t195_5 annotation gutter) or per-row styling (t195_6 cursor). `_highlighted_lines` is stored as an instance list and can be accessed without re-highlighting. Direct imports used (not relative) — same pattern as `file_tree.py`. The `scroll_home(animate=False)` call in `_rebuild_display()` resets scroll position when loading a new file.
