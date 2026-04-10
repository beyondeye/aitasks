---
Task: t514_order_of_tui_in_switcher.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

The TUI switcher dialog (shared across all main TUIs) lists TUIs in a suboptimal order. The most commonly used TUIs should appear first.

## Changes

**File: `.aitask-scripts/lib/tui_switcher.py`**

### 1. Reorder `KNOWN_TUIS` (lines 59-65)

Current order: board, codebrowser, settings, monitor, diffviewer

New order:
```python
KNOWN_TUIS = [
    ("board", "Task Board", "ait board"),
    ("monitor", "tmux Monitor", "ait monitor"),
    ("codebrowser", "Code Browser", "ait codebrowser"),
    ("settings", "Settings", "ait settings"),
    ("diffviewer", "Diff Viewer", "ait diffviewer"),
]
```

### 2. Insert git TUI at position 2 instead of appending (line 75)

Change `tuis.append(...)` to `tuis.insert(2, ...)` so git appears after monitor (index 2), giving the final order: board, monitor, git, codebrowser, settings, diffviewer.

## Verification

- Launch `ait board` (or any TUI) and open the switcher dialog to confirm the new order.

## Final Implementation Notes
- **Actual work done:** Reordered `KNOWN_TUIS` list and changed git TUI insertion from `append` to `insert(2, ...)` — exactly as planned
- **Deviations from plan:** None
- **Issues encountered:** None
- **Key decisions:** Kept diffviewer at the end of the list since it wasn't mentioned in the desired order
