---
priority: high
effort: medium
depends: [t195_2, t195_1, t195_2]
issue_type: feature
status: Done
labels: [codebrowser]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-25 12:18
updated_at: 2026-02-25 16:53
completed_at: 2026-02-25 16:53
---

## Context

This is child task 3 of t195 (Python Code Browser TUI). It implements the code viewer widget that displays source code with syntax highlighting and line numbers in the right pane. When a user selects a file in the tree (t195_2), the code viewer loads and displays it.

The viewer uses Rich's `Syntax` class for syntax highlighting (powered by Pygments). The code is rendered as a Rich `Table` inside a single Textual `Static` widget within a `VerticalScroll` container — this single-widget approach ensures later additions (annotation gutter in t195_5, cursor in t195_6) stay vertically aligned.

## Key Files to Modify

- **`aiscripts/codebrowser/code_viewer.py`** (NEW): `CodeViewer(VerticalScroll)` widget with:
  - `load_file(file_path: Path)`: reads file content, detects lexer from file extension, builds and displays a Rich Table with 2 columns (line numbers + syntax-highlighted code)
  - Internal `Static` widget (id="code_display") that renders the Rich Table
  - Lexer detection: use `Syntax.guess_lexer(str(file_path))` or map common extensions
  - Line numbers: right-aligned, dim style
  - Code: syntax-highlighted using Rich `Syntax` or by tokenizing with Pygments and building `Rich.Text` objects per line
  - Empty state: show "Select a file to view" when no file loaded
- **`aiscripts/codebrowser/codebrowser_app.py`** (MODIFY):
  - Replace right pane placeholder with: `Static(id="file_info_bar")` + `CodeViewer(id="code_viewer")`
  - Wire `on_directory_tree_file_selected()`: call `self.query_one(CodeViewer).load_file(event.path)`
  - Update file info bar: show filename and line count
  - CSS for code viewer: monospace font, proper padding, dark background

## Reference Files for Patterns

- Rich `Syntax` class: `from rich.syntax import Syntax` — `Syntax(code, lexer, line_numbers=True, theme="monokai")` renders highlighted code
- Rich `Table` class: `from rich.table import Table` — for building the 2-column layout (line num + code)
- Rich `Text` class: `from rich.text import Text` — for styled per-line text
- `aiscripts/board/aitask_board.py` (lines 407-551): `TaskCard(Static)` — pattern for a custom widget rendering Rich content via `render()` or `update()`

## Implementation Plan

1. Create `code_viewer.py`:
   - Import: `VerticalScroll`, `Static` from Textual; `Syntax`, `Table`, `Text` from Rich
   - `CodeViewer(VerticalScroll)`:
     - `compose()`: yield `Static(id="code_display")`
     - `load_file(file_path: Path)`:
       a. Read file content with `file_path.read_text(errors="replace")`
       b. Detect lexer: `Syntax.guess_lexer(str(file_path), code=content)` or fallback to "text"
       c. Create `Syntax` object for tokenization (to get per-line highlighted Text)
       d. Build `Rich.Table(show_header=False, show_edge=False, pad_edge=False, box=None)`:
          - Column 1: line number (style="dim", justify="right", width=5, no_wrap=True)
          - Column 2: code line (no_wrap=True for initial version)
       e. For each line: `table.add_row(Text(str(i+1), style="dim"), highlighted_line_text)`
       f. `self.query_one("#code_display", Static).update(table)`
     - Store `self._file_path`, `self._lines`, `self._total_lines` for later use
   - Approach for per-line syntax highlighting:
     - Use `Syntax._get_syntax()` or create a `Syntax` object and extract tokens using `syntax.highlight(code)` which returns a `Text` object, then split by newlines
     - Alternative: use `Syntax` with `line_range` to render chunks, but single-render + split is simpler

2. Update `codebrowser_app.py`:
   - Import `CodeViewer` from `code_viewer`
   - In `compose()`, right pane becomes: `Static("No file selected", id="file_info_bar")` + `CodeViewer(id="code_viewer")`
   - Wire handler: `on_directory_tree_file_selected` → convert path, call `load_file()`
   - Update info bar with filename and line count
   - CSS: `#code_viewer { height: 1fr; }`, `#file_info_bar { height: 1; dock: top; background: $surface-lighten-1; padding: 0 1; }`, `#code_display { width: auto; }`

## Verification Steps

1. Run `./ait codebrowser`, select a Python file (.py) — should show syntax-highlighted code with line numbers
2. Select a shell script (.sh) — different highlighting
3. Select a markdown file (.md) — markdown highlighting
4. Select a YAML file (.yaml) — yaml highlighting
5. Scroll up/down through a long file — scrolling should work smoothly
6. File info bar should show the filename and total line count
7. Before selecting any file, right pane should show "Select a file to view" or similar
