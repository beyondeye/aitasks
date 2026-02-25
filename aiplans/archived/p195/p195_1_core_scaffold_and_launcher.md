---
Task: t195_1_core_scaffold_and_launcher.md
Parent Task: aitasks/t195_python_codebrowser.md
Sibling Tasks: aitasks/t195/t195_2_*.md through t195_11_*.md
Branch: main
Base branch: main
---

# Plan: t195_1 — Core Scaffold and Launcher

## Steps

### 1. Create directory structure
```bash
mkdir -p aiscripts/codebrowser
```

### 2. Create `aiscripts/codebrowser/annotation_data.py`
Define three dataclasses:
- `AnnotationRange`: start_line, end_line, task_ids (list[str]), commit_hashes (list[str]), commit_messages (list[str])
- `FileExplainData`: file_path (str), annotations (list[AnnotationRange]), commit_timeline (list[dict]), generated_at (str)
- `ExplainRunInfo`: run_dir (str), directory_key (str), timestamp (str), file_count (int)

### 3. Create `aiscripts/codebrowser/codebrowser_app.py`
- Import: App, ComposeResult, Header, Footer, Horizontal, Container, Static, Binding from textual
- CSS class variable: two-pane layout
  - `#file_tree_pane`: width 35, border-right, dock left
  - `#code_pane`: width 1fr
  - Colors matching board theme: `$surface`, `$primary`, `$accent`
- `compose()`: Header + Horizontal(Container left + Container right) + Footer
- Placeholder content in both panes
- Bindings: q=quit, tab=toggle_focus
- `__main__` entry point

### 4. Create `aiscripts/aitask_codebrowser.sh`
Follow `aiscripts/aitask_board.sh` pattern:
- `#!/usr/bin/env bash` + `set -euo pipefail`
- Source `terminal_compat.sh`
- Venv detection: `$HOME/.aitask/venv/bin/python`
- System python fallback
- Package check: textual, pyyaml (not linkify-it-py)
- Terminal capability warning
- `exec "$PYTHON" "$SCRIPT_DIR/codebrowser/codebrowser_app.py" "$@"`

### 5. Add to `ait` dispatcher
- Help text: `codebrowser    Launch the code browser TUI`
- Case: `codebrowser) shift; exec "$SCRIPTS_DIR/aitask_codebrowser.sh" "$@" ;;`

### 6. Add `aiscripts/codebrowser/__pycache__/` to `.gitignore`
No separate `aiexplain/` directory — codebrowser uses `aiexplains/` (already gitignored, managed by `aitask_explain_runs`).

## Verification
- `./ait codebrowser` launches, shows two panes, exits on `q`
- `./ait` shows codebrowser in help
- Tab toggles focus between panes

## Final Implementation Notes
- **Actual work done:** All 6 steps implemented as planned. Created `aiscripts/codebrowser/` with `__init__.py`, `annotation_data.py`, `codebrowser_app.py`; created `aiscripts/aitask_codebrowser.sh` launcher; added `codebrowser` command to `ait` dispatcher; added `__pycache__` to `.gitignore`.
- **Deviations from plan:** Step 6 changed from adding `aiexplain/` to `.gitignore` to adding only `aiscripts/codebrowser/__pycache__/`. Per user feedback, codebrowser will use the existing `aiexplains/` directory (already gitignored and managed by `aitask_explain_runs`) instead of a separate `aiexplain/` directory.
- **Issues encountered:** None. All verification steps passed — TUI launches with two-pane layout, shows placeholder text, footer displays quit binding.
- **Key decisions:** Used `$surface` and `$primary` theme variables for consistent styling with the board TUI. Left pane width set to 35 columns with thick primary-colored border separator.
- **Notes for sibling tasks:** The `codebrowser_app.py` is the main file to extend. Subsequent tasks should add widgets inside the `#file_tree_pane` and `#code_pane` containers. The `toggle_focus` action will need updating once real focusable widgets replace the Static placeholders. `annotation_data.py` dataclasses are ready for use by t195_4 (explain data generation) and t195_5 (task annotation overlay). Explain data should be stored under `aiexplains/` not a separate directory.
