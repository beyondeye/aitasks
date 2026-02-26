---
priority: high
effort: high
depends: [t259_1, t259_4]
issue_type: feature
status: Ready
labels: [aitask_review, ui]
created_at: 2026-02-26 18:43
updated_at: 2026-02-26 18:46
---

## Context

This is the main TUI application for browsing batch review findings (t259). It provides a two-panel layout with a virtual file tree on the left and a detail view on the right, plus a Python manager class (ReviewRunManager) mirroring the ExplainManager pattern.

Depends on: t259_1 (data model), t259_4 (run management scripts inform cleanup logic)

## Key Files to Modify

- aiscripts/reviewbrowser/reviewbrowser_app.py (new) — main Textual App
- aiscripts/reviewbrowser/findings_tree.py (new) — virtual Tree widget
- aiscripts/reviewbrowser/review_run_manager.py (new) — Python manager class
- aiscripts/aitask_reviewbrowser.sh (new) — launcher script
- ait — add reviewbrowser command
- .gitignore — add aiscripts/reviewbrowser/__pycache__/

## Reference Files for Patterns

- aiscripts/codebrowser/codebrowser_app.py — two-panel Textual App layout, event routing, info bar
- aiscripts/codebrowser/file_tree.py — DirectoryTree widget (our tree is virtual, not filesystem-based)
- aiscripts/codebrowser/explain_manager.py — ExplainManager pattern: load/cache/cleanup/lazy-load
- aiscripts/aitask_codebrowser.sh — launcher script pattern (venv detection, package check)

## Implementation Plan

### Step 1: Create ReviewRunManager

aiscripts/reviewbrowser/review_run_manager.py:
- list_runs() -> list of run dirs with metadata
- load_run(run_dir) -> ReviewRunManifest (from findings_data.py)
- find_latest_run(dir_key) -> Path or None
- load_file_findings(run_dir, rel_path) -> FileFindings (lazy, cached)
- aggregate_directory(run_dir, dir_path) -> dict
- cleanup_stale_runs() -> int (keep newest per key, called on init)
- LRU cache for per-file findings (OrderedDict, max 100)

### Step 2: Create findings_tree.py

Virtual Tree widget (Textual Tree, not DirectoryTree):
- Build tree from list of reviewed file paths
- Nodes: files show "filename (N findings)" with severity color coding
  - Red for files with high-severity findings
  - Yellow for medium
  - Dim for low-only
- Directory nodes: "dirname/ (N total)"
- Post TreeNodeSelected message when user clicks

### Step 3: Create reviewbrowser_app.py

Main App class:
- Two-panel horizontal layout: tree (35 chars) | detail view (1fr)
- Info bar at top with current selection info
- Load ReviewRunManager on mount
- Run selection dialog if multiple runs exist
- Handle TreeNodeSelected to update right panel (placeholder for t259_6)
- Keybindings: q quit, tab toggle focus, r refresh

### Step 4: Create launcher script

aiscripts/aitask_reviewbrowser.sh following aitask_codebrowser.sh pattern:
- Venv detection, package check (textual, pyyaml)
- Terminal capability warning
- Optional --run-dir argument to open specific run
- exec python reviewbrowser_app.py

### Step 5: Dispatcher integration

Add to ait: reviewbrowser) shift; exec SCRIPTS_DIR/aitask_reviewbrowser.sh
Add aiscripts/reviewbrowser/__pycache__/ to .gitignore

## Verification Steps

- Run ait reviewbrowser with sample aireviews/ data (create test fixtures)
- Verify tree displays with correct file counts and severity colors
- Verify run selection when multiple runs exist
- Test keyboard navigation (tab, up/down, enter)
