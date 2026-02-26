---
priority: medium
effort: high
depends: [t259_5]
issue_type: feature
status: Ready
labels: [aitask_review, ui]
created_at: 2026-02-26 18:44
updated_at: 2026-02-26 18:44
---

## Context

This task implements the right-panel findings viewer widget for the reviewbrowser TUI (t259). It displays findings detail when a file is selected, directory aggregate summaries, and the run summary at root level. Includes severity/guide filtering and source code preview.

Depends on: t259_1 (data model), t259_5 (app shell and tree must exist)

## Key Files to Modify

- aiscripts/reviewbrowser/findings_viewer.py (new) — right-panel widget

## Reference Files for Patterns

- aiscripts/codebrowser/code_viewer.py — Rich table rendering, viewport, styling patterns
- aiscripts/board/aitask_board.py — Rich Text styling, color-coded severity patterns

## Implementation Plan

### Step 1: File-level view

When a file is selected in the tree:
- Show file path and review timestamp
- List findings grouped by review guide
- Within each guide group, sort by severity (high -> medium -> low)
- Each finding: severity badge (colored), line number, description, code_snippet, suggested_fix
- Use Rich Table with styled rows

### Step 2: Directory-level view

When a directory is selected:
- Aggregate summary from ReviewRunManager.aggregate_directory()
- Show: total findings, breakdown by severity (counts + bars), breakdown by guide (counts)
- List files sorted by highest severity first, then by finding count
- Each file shows: filename, finding count, highest severity

### Step 3: Root-level view

When root is selected:
- Full run summary from manifest
- Source root, review guides used, session count/status
- Overall severity/guide breakdown

### Step 4: Severity/guide filtering

- f key: cycle severity filter (all -> high only -> medium+ -> all)
- g key: toggle guide filter (show picker if multiple guides)
- Visual indicator of active filters in info bar

### Step 5: Source code preview

When a finding is highlighted/focused:
- Read relevant lines from source_root + file path
- Show context: 3 lines before and after the finding line
- Syntax highlight if possible (Rich Syntax)
- Handle missing source files gracefully (external repos may not be accessible)

### Step 6: Refresh from disk

- r key: reload findings from YAML files
- Useful when batch driver is still running and producing new findings

## Verification Steps

- Test with sample findings data showing file, directory, and root views
- Test severity filtering toggles
- Test source code preview with accessible and inaccessible files
