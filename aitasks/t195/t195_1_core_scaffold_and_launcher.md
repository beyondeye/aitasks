---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [codebrowser]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-25 12:18
updated_at: 2026-02-25 12:25
---

## Context

This is the first child task of t195 (Python Code Browser TUI). It creates the minimal runnable application skeleton that all subsequent child tasks build upon. The codebrowser is a new TUI tool — separate from the existing board TUI — for browsing project source code with task-origin annotations.

The existing board TUI (`aiscripts/board/aitask_board.py`) and its launcher (`aiscripts/aitask_board.sh`) provide the exact patterns to follow.

## Key Files to Modify

- **`aiscripts/aitask_codebrowser.sh`** (NEW): Launcher shell script modeled on `aiscripts/aitask_board.sh`. Checks for venv at `$HOME/.aitask/venv/bin/python`, falls back to system python3, verifies required packages (textual, pyyaml), warns on incapable terminals via `ait_warn_if_incapable_terminal`, then `exec`s the Python entry point.
- **`aiscripts/codebrowser/codebrowser_app.py`** (NEW): Main `CodeBrowserApp(App)` class with:
  - CSS class variable for two-pane horizontal layout (left pane ~30 cols for file tree, right pane flex for code viewer)
  - `compose()` yielding: `Header(show_clock=True)`, `Horizontal` container with two `Container` placeholders (left/right panes), `Footer`
  - Bindings: `q` to quit, `tab` to toggle focus between panes
  - `TITLE = "aitasks codebrowser"`
  - `__main__` entry point: `CodeBrowserApp().run()`
- **`aiscripts/codebrowser/annotation_data.py`** (NEW): Dataclasses used across all codebrowser modules:
  - `AnnotationRange(start_line: int, end_line: int, task_ids: list[str], commit_hashes: list[str], commit_messages: list[str])`
  - `FileExplainData(file_path: str, annotations: list[AnnotationRange], commit_timeline: list[dict], generated_at: str)`
  - `ExplainRunInfo(run_dir: str, directory_key: str, timestamp: str, file_count: int)`
- **`ait`** (MODIFY): Add `codebrowser` command routing — add to help text near `board` and to case statement: `codebrowser) shift; exec "$SCRIPTS_DIR/aitask_codebrowser.sh" "$@" ;;`
- **`.gitignore`** (MODIFY): Add `aiexplain/` entry (the existing `aiexplains/` entry is separate)

## Reference Files for Patterns

- `aiscripts/aitask_board.sh` (lines 1-42): Exact pattern for launcher script — venv detection, package check, terminal warning, exec
- `aiscripts/board/aitask_board.py` (lines 1989-2160): CSS class variable pattern, compose() structure, binding definitions
- `aiscripts/board/aitask_board.py` (lines 2893-2895): `__main__` entry point pattern
- `ait` (lines 108-115): Command dispatch case statement pattern

## Implementation Plan

1. Create `aiscripts/codebrowser/` directory
2. Write `annotation_data.py` with the three dataclasses using `@dataclass`
3. Write `codebrowser_app.py`:
   - Import Textual: App, ComposeResult, Header, Footer, Horizontal, Container, Static, Binding
   - Define CSS for two-pane layout with proper widths, borders, background colors matching board theme (`$surface`, `$primary`, `$accent`)
   - Left pane placeholder: `Container` with id="file_tree_pane", shows `Static("File tree will appear here")`
   - Right pane placeholder: `Container` with id="code_pane", shows `Static("Select a file to view")`
   - Bindings for q (quit) and tab (toggle_focus)
   - `__main__` block
4. Write `aitask_codebrowser.sh`:
   - `#!/usr/bin/env bash` + `set -euo pipefail`
   - Source `terminal_compat.sh`
   - Venv/system python detection
   - Package check: textual, pyyaml (not linkify-it-py — codebrowser doesn't need it)
   - Terminal capability warning
   - `exec "$PYTHON" "$SCRIPT_DIR/codebrowser/codebrowser_app.py" "$@"`
5. Add `codebrowser` to `ait` dispatcher (help text + case statement)
6. Add `aiexplain/` to `.gitignore`

## Verification Steps

1. Run `./ait codebrowser` — app should launch showing two-pane layout with placeholder text
2. Press `q` — app should exit cleanly
3. Press `tab` — focus should visually toggle between left and right panes
4. Run `./ait --help` or `./ait` — should show `codebrowser` in command list
