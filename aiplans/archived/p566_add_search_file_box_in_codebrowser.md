---
Task: t566_add_search_file_box_in_codebrowser.md
Base branch: main
plan_verified: []
---

# Implementation Plan: t566 — Add Search File Box in Codebrowser

## Context

The codebrowser TUI currently requires drilling down the file tree widget to select files. This is slow for large projects. The task adds an always-visible fuzzy search box at the top of the code pane, integrated into Tab cycling, so users can quickly find and open files by typing partial filenames. Inspired by [toad's file picker](https://github.com/batrachianai/toad) — specifically its `PathFuzzySearch` algorithm and `OptionList`-based results.

## Key Files

- **New**: `.aitask-scripts/codebrowser/file_search.py` — PathFuzzySearch + FileSearchWidget
- **Modify**: `.aitask-scripts/codebrowser/codebrowser_app.py` — Layout, Tab cycling, event handling
- **Reference (toad)**: `_path_match.py` — PathFuzzySearch algorithm (recursive multi-match with scoring)
- **Reference (toad)**: `widgets/path_search.py` — PathSearch widget using Input + OptionList
- **Reference (local)**: `.aitask-scripts/codebrowser/file_tree.py` — ProjectFileTree._tracked_files

## Design

### Fuzzy Matching: Adapted from toad's PathFuzzySearch

Toad's algorithm (from `_path_match.py` / `fuzzy.py`) finds **all** possible character alignments and picks the highest-scoring one. Scoring heuristics:
- **First-letter bonus**: matches at position 0 or after `/` separators score higher
- **Consecutive group bonus**: fewer gaps between matched characters = higher score (normalized quadratic boost)
- **Filename boost**: 2x multiplier when the first matched character is in the filename portion (after last `/`)

We adapt this directly rather than using simple substring matching. The algorithm is self-contained (~80 LOC) with no external dependencies. For our scale (hundreds to low thousands of git-tracked files), no trigram index is needed — direct matching is fast enough.

### Widget Layout

```
#code_pane (Container)
├── #file_info_bar (Static, dock: top, height: 1)       [existing]
├── FileSearchWidget (Container, height: auto)            [NEW]
│   ├── Input (height: 1, placeholder "Search files...")
│   └── OptionList (max-height: 12, hidden when empty)
└── #code_viewer (CodeViewer, height: 1fr)                [existing]
```

Following toad's pattern: Input for query + `OptionList` (Textual built-in) for results. OptionList handles highlighting, scrolling, and selection natively. Results are `Option` items with highlighted match positions shown via Rich markup (underline on matched chars, dim path, bold filename).

### Tab Cycling (updated)

```
recent_files → file_tree → file_search_input → code_viewer → detail (if visible) → recent_files
```

### Keyboard Behavior

When Input has focus:
- **Type** → fuzzy filter files, show results in OptionList
- **Down/Up** → navigate OptionList (handled by bindings on the widget, like toad)
- **Enter** → open highlighted file, clear input, hide results, focus code_viewer
- **Escape** → clear input, hide results
- **Tab** → normal pane cycling (next = code_viewer)

## Implementation Steps

### Step 1: Create `file_search.py`

New file at `.aitask-scripts/codebrowser/file_search.py` with two components:

#### 1a. PathFuzzySearch class (~80 LOC)

Adapted from toad's `_path_match.py`. Self-contained fuzzy matcher:

```python
class PathFuzzySearch:
    """Fuzzy file path matcher adapted from toad."""

    def __init__(self, case_sensitive=False):
        self.case_sensitive = case_sensitive

    def match(self, query: str, candidate: str) -> tuple[float, list[int]]:
        """Return (score, matched_positions) or (0.0, []) for no match."""
        # Find all possible character alignments, pick highest scoring
        ...

    def score(self, candidate: str, positions: list[int]) -> float:
        """Score based on first-letter matches, consecutive groups, filename bonus."""
        # First letters: position 0 and positions after '/'
        first_letters = {0} | {m.start() + 1 for m in re.finditer(r"/", candidate)}
        offset_count = len(positions)
        score = offset_count + len(first_letters.intersection(positions))
        # Consecutive group bonus
        groups = 1
        for i in range(1, len(positions)):
            if positions[i] != positions[i-1] + 1:
                groups += 1
        normalized = (offset_count - (groups - 1)) / offset_count
        score *= 1 + (normalized * normalized)
        # Filename boost: 2x if first match is in filename
        if positions[0] > candidate.rfind("/"):
            score *= 2
        return score

    def _match(self, query, candidate):
        """Recursive generator of (score, positions) for all alignments."""
        # Build letter_positions for each query char
        # Recursively enumerate valid offset combinations
        # Yield (score, offsets) for each
        ...
```

#### 1b. FileSearchWidget class (~120 LOC)

```python
class FileSearchWidget(Container):
    """Fuzzy file search: Input + OptionList results."""

    class FileOpened(Message):
        def __init__(self, path: str): ...

    DEFAULT_CSS = """
    FileSearchWidget { height: auto; }
    FileSearchWidget Input {
        height: 1;
        border: none;
        background: $surface-lighten-1;
        &:focus { border: none; background: $surface-lighten-2; }
    }
    FileSearchWidget OptionList {
        max-height: 12;
        display: none;
        background: $surface;
        border-bottom: solid $primary;
    }
    FileSearchWidget OptionList.visible { display: block; }
    """

    BINDINGS = [
        Binding("up", "cursor_up", "Up", priority=True),
        Binding("down", "cursor_down", "Down", priority=True),
        Binding("enter", "submit", "Open file", priority=True, show=False),
        Binding("escape", "dismiss_search", "Clear", priority=True, show=False),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._all_files: list[str] = []
        self._fuzzy = PathFuzzySearch()

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search files...", id="file_search_input")
        yield OptionList(id="file_search_results")

    def set_files(self, files: list[str]) -> None:
        self._all_files = sorted(files)

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.strip()
        option_list = self.query_one(OptionList)
        if not query:
            option_list.clear_options()
            option_list.add_class("hidden")  # maps to display:none via .-hidden
            option_list.remove_class("visible")
            return
        # Score all files
        scored = []
        for f in self._all_files:
            score, positions = self._fuzzy.match(query, f)
            if score > 0:
                scored.append((score, positions, f))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:30]
        # Build OptionList items with highlighted matches
        option_list.clear_options()
        for score, positions, path in top:
            option_list.add_option(Option(self._highlight(path, positions), id=path))
        if top:
            option_list.highlighted = 0
            option_list.remove_class("hidden")
            option_list.add_class("visible")
        else:
            option_list.add_class("hidden")
            option_list.remove_class("visible")

    def _highlight(self, path: str, positions: list[int]) -> Text:
        """Build Rich Text with matched chars underlined, filename bold."""
        # Use Rich Text object
        # Dim the directory portion, normal the filename
        # Underline matched positions
        ...

    def action_cursor_up(self) -> None:
        self.query_one(OptionList).action_cursor_up()

    def action_cursor_down(self) -> None:
        self.query_one(OptionList).action_cursor_down()

    def action_submit(self) -> None:
        ol = self.query_one(OptionList)
        if ol.highlighted is not None:
            option = ol.get_option_at_index(ol.highlighted)
            self.post_message(self.FileOpened(option.id))
            self._clear_search()

    def action_dismiss_search(self) -> None:
        self._clear_search()

    def _clear_search(self) -> None:
        self.query_one(Input).value = ""
        ol = self.query_one(OptionList)
        ol.clear_options()
        ol.add_class("hidden")
        ol.remove_class("visible")
```

### Step 2: Integrate into `codebrowser_app.py`

**Imports** (add near other codebrowser imports):
```python
from file_search import FileSearchWidget
```

**`compose()` method** (~line 420) — add FileSearchWidget inside #code_pane:
```python
with Container(id="code_pane"):
    yield Static("No file selected", id="file_info_bar")
    yield FileSearchWidget(id="file_search")
    yield CodeViewer(id="code_viewer")
```

**`on_mount()` method** (~line 392) — populate file list after project root is set:
```python
# At end of on_mount, after existing code:
try:
    tree = self.query_one("#file_tree", ProjectFileTree)
    search = self.query_one("#file_search", FileSearchWidget)
    search.set_files(sorted(tree._tracked_files))
except Exception:
    pass
```

### Step 3: Handle file selection from search

Add event handler in `CodeBrowserApp`:
```python
def on_file_search_widget_file_opened(self, event: FileSearchWidget.FileOpened) -> None:
    self._open_file_by_path(event.path)
    try:
        self.query_one("#code_viewer").focus()
    except Exception:
        pass
```

### Step 4: Update Tab cycling

In `action_toggle_focus()` (~line 815), insert the search input into the cycle between file_tree and code_viewer. Two changes needed:

**Change 1**: When file_tree has focus, go to search input instead of code_viewer:
```python
if file_tree is not None and file_tree.has_focus_within:
    try:
        search_input = screen.query_one("#file_search_input", Input)
        search_input.focus()
    except Exception:
        code_viewer.focus()
    return
```

**Change 2**: Add new check for search input focus → code_viewer (before the existing code_viewer check):
```python
# Search input → code_viewer
try:
    search_input = screen.query_one("#file_search_input", Input)
    if search_input.has_focus:
        code_viewer.focus()
        return
except Exception:
    pass
```

### Step 5: Verify and test

1. Run codebrowser: `python .aitask-scripts/codebrowser/codebrowser_app.py`
2. Verify search box appears at top of code pane (1-line Input)
3. Type a filename fragment → OptionList results appear below
4. Fuzzy matching works (e.g., "cba" matches "codebrowser_app.py", "ftrpy" matches "file_tree.py")
5. Matched characters underlined in results
6. Up/Down arrows navigate results
7. Enter opens file in code viewer and clears search
8. Escape clears search and hides results
9. Tab cycles through: recent → tree → search → code → detail → recent
10. Empty search hides the results list (only Input visible, 1 line)

## Post-Review Changes

### Change Request 1 (2026-04-16 10:20)
- **Requested by user:** Search input border should be more visible with color change on focus
- **Changes made:** Updated Input CSS from `border: none` to `border: tall $surface-lighten-2` with `border: tall $accent` on focus
- **Files affected:** `.aitask-scripts/codebrowser/file_search.py`

### Change Request 2 (2026-04-16 10:22)
- **Requested by user:** Move search box above the file info bar (to the very top of code pane)
- **Changes made:** Swapped compose order: FileSearchWidget before file_info_bar. Removed `dock: top` from #file_info_bar CSS so it flows naturally.
- **Files affected:** `.aitask-scripts/codebrowser/codebrowser_app.py`

### Change Request 3 (2026-04-16 10:24)
- **Requested by user:** Make file_info_bar text more visible (bold/accented)
- **Changes made:** Added `text-style: bold; color: $text;` to #file_info_bar CSS
- **Files affected:** `.aitask-scripts/codebrowser/codebrowser_app.py`

## Final Implementation Notes
- **Actual work done:** Implemented as a single task (no child tasks needed). Created `file_search.py` with PathFuzzySearch (adapted from toad) + FileSearchWidget (Input + OptionList). Modified `codebrowser_app.py` for layout, tab cycling, escape handling, and event wiring.
- **Deviations from plan:** (1) Search box moved above file_info_bar instead of below it. (2) Removed `dock: top` from file_info_bar CSS. (3) Added visible border to search input. (4) Made file_info_bar text bold. (5) App-level escape handler intercepts Escape for search clearing (priority binding issue).
- **Issues encountered:** App-level `action_handle_escape_key` with `priority=True` intercepted Escape before the widget's binding could fire. Solved by adding search-active check at the top of the app escape handler.
- **Key decisions:** Used toad's full PathFuzzySearch algorithm (recursive multi-alignment with scoring) rather than simple substring matching. Used Textual's built-in OptionList for results instead of custom Static widgets.

## Step 9 (Post-Implementation)

After implementation is reviewed and committed, proceed with task archival, lock release, and push per the standard workflow.
