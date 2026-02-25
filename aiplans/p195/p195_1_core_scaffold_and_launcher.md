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

### 6. Add `aiexplain/` to `.gitignore`

## Verification
- `./ait codebrowser` launches, shows two panes, exits on `q`
- `./ait` shows codebrowser in help
- Tab toggles focus between panes
