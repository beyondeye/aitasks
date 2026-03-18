---
Task: t417_1_test_data_and_project_scaffolding.md
Parent Task: aitasks/t417_diff_viewer_tui_for_brainstorming.md
Sibling Tasks: aitasks/t417/t417_2_*.md through t417_7_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Test Data and Project Scaffolding (t417_1)

## 1. Create Directory Structure

```bash
mkdir -p .aitask-scripts/diffviewer/test_plans
```

## 2. Create `__init__.py`

Create `.aitask-scripts/diffviewer/__init__.py` — empty file.

## 3. Create Launcher Script

Create `.aitask-scripts/aitask_diffviewer.sh` copying the pattern from `aitask_codebrowser.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

VENV_PYTHON="$HOME/.aitask/venv/bin/python"

if [[ -x "$VENV_PYTHON" ]]; then
    PYTHON="$VENV_PYTHON"
else
    PYTHON="${PYTHON:-python3}"
    if ! command -v "$PYTHON" &>/dev/null; then
        echo "Error: Python not found. Run 'ait setup' to install dependencies." >&2
        exit 1
    fi
    missing=()
    $PYTHON -c "import textual" 2>/dev/null || missing+=(textual)
    $PYTHON -c "import yaml" 2>/dev/null   || missing+=(pyyaml)
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "Missing Python packages: ${missing[*]}" >&2
        echo "Run 'ait setup' to install all dependencies." >&2
        echo "Or install manually: pip install ${missing[*]}" >&2
        exit 1
    fi
fi

ait_warn_if_incapable_terminal

exec "$PYTHON" "$SCRIPT_DIR/diffviewer/diffviewer_app.py" "$@"
```

## 4. Create Placeholder App

Create `.aitask-scripts/diffviewer/diffviewer_app.py` as a minimal stub:

```python
#!/usr/bin/env python3
"""Diff Viewer TUI for comparing implementation plans."""
from __future__ import annotations

import sys

def main():
    print("ait diffviewer - placeholder (t417_1)")
    print("Full implementation coming in child tasks t417_2 through t417_7.")
    sys.exit(0)

if __name__ == "__main__":
    main()
```

## 5. Create 5 Test Plan Files

All plans in `.aitask-scripts/diffviewer/test_plans/`. Each has YAML frontmatter and varied markdown structure.

Design criteria for test data:
- **Shared content at different positions** — needed for structural diff testing
- **Different heading hierarchies** — exercises section parsing
- **Mix of bullet lists, numbered lists, code blocks** — realistic plan content
- **One plan is a content subset of another** (delta ⊂ gamma) — tests subset detection
- **One plan is a superset** (epsilon ⊃ alpha ∪ gamma) — tests comprehensive diffing
- **Rephrased versions of same ideas** — tests content similarity matching

### plan_alpha.md
- Topic: "Implement User Authentication"
- Structure: Context, Step 1 (Setup), Step 2 (Implementation), Step 3 (Testing), Verification
- Features: Numbered step headings, code snippets in Python, bullet list of verification items

### plan_beta.md
- Topic: "Implement User Authentication" (same topic, different approach)
- Structure: File-based sections (File: auth/handler.py, File: auth/middleware.py, File: tests/test_auth.py)
- Features: 2 paragraphs verbatim from alpha (at different positions), same code snippet as alpha, different heading structure

### plan_gamma.md
- Topic: "Implement User Authentication" (architecture-first approach)
- Structure: Architecture Overview, Component Design, Implementation, Verification
- Features: Shares Verification section with alpha, bullet lists instead of numbered, unique "Component Design" section

### plan_delta.md
- Topic: "Implement User Authentication" (minimal plan)
- Structure: Context, Implementation (only 2 sections)
- Features: Content is strict subset of gamma (2 paragraphs copied), very short

### plan_epsilon.md
- Topic: "Implement User Authentication" (comprehensive plan)
- Structure: All sections from alpha + gamma, plus Risk Assessment, Performance Considerations
- Features: `###` subsections, rephrased versions of shared content, longest plan

## 6. Register in `ait` Dispatcher

Add `diffviewer` command to `./ait`:
- Add usage line in `show_usage()` under TUI section
- Add case branch: `diffviewer) shift; exec "$SCRIPTS_DIR/aitask_diffviewer.sh" "$@" ;;`

## 7. Verification

- `shellcheck .aitask-scripts/aitask_diffviewer.sh` — passes
- `bash .aitask-scripts/aitask_diffviewer.sh` — runs without error (prints placeholder message)
- `./ait diffviewer` — works via dispatcher
- Python can import: `python3 -c "import sys; sys.path.insert(0, '.aitask-scripts'); import diffviewer"`
- Each test plan has valid YAML frontmatter (test with task_yaml.parse_frontmatter or manual check)

## Final Implementation Notes

- **Actual work done:** Created directory structure, launcher script, placeholder app, 5 test plans, and registered `ait diffviewer` in the dispatcher. All items from the plan implemented as specified.
- **Deviations from plan:** Added dispatcher registration (step 6) which was missing from the original plan — discovered during verification.
- **Issues encountered:** shellcheck SC1091 info about not following sourced files — same as existing `aitask_codebrowser.sh`, not a real issue.
- **Key decisions:** Test plans use plan-file frontmatter format (Task/Worktree/Branch/Base branch) rather than task-style frontmatter, matching real plan files in `aiplans/`.
- **Notes for sibling tasks:** The launcher script at `.aitask-scripts/aitask_diffviewer.sh` follows the exact `aitask_codebrowser.sh` pattern. The placeholder app at `.aitask-scripts/diffviewer/diffviewer_app.py` needs to be replaced with the actual Textual TUI in t417_2+. Test plans are in `.aitask-scripts/diffviewer/test_plans/` and have deliberately overlapping content at different positions for testing structural diff detection. The `ait diffviewer` command is registered in the dispatcher.

## Post-Implementation

Step 9 of the task-workflow: archive task, push changes.
