---
Task: t572_word_wrap_in_file_view_in_codebrowser.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Word Wrap & Horizontal Scroll in Codebrowser File View (t572)

## Context

The codebrowser TUI's file detail pane currently truncates long lines with "…" and has no way to view the full content. There is no horizontal scrollbar and no word wrapping. The user wants a keyboard shortcut to toggle between these display modes.

## Current State

- `CodeViewer` extends `VerticalScroll` (vertical scroll only, `overflow-x: hidden`)
- Inside: a `Static` widget renders a Rich `Table` with 3 columns (line nums, code, annotations)
- Code column: `no_wrap=True`, `width=code_max_width` (fits available terminal width)
- Lines longer than available width are truncated with "…" at the end
- CSS: `#code_display { width: auto; overflow-x: hidden; }`

## Design: Three Display Modes

Cycle with `w` key: **Truncate → Wrap → Scroll → Truncate**

| Mode | Code column | Truncation | CodeViewer overflow-x | Description |
|------|------------|------------|----------------------|-------------|
| **Truncate** (default) | `no_wrap=True`, `width=code_max_width` | Yes, with "…" | `hidden` | Current behavior |
| **Wrap** | `no_wrap=False`, `width=code_max_width` | No | `hidden` | Lines wrap within available width |
| **Scroll** | `no_wrap=True`, `width=max_content_width` | No | `auto` | Horizontal scrollbar for wide content |

## Implementation Steps

### Step 1: Add state and mode cycling to `CodeViewer` (`code_viewer.py`)

**Add instance variable** in `__init__` (after line 72):
```python
self._wrap_mode: str = "truncate"  # "truncate" | "wrap" | "scroll"
self._max_line_width: int = 0     # cached max line width for scroll mode
```

**Add `cycle_wrap_mode()` method:**
```python
def cycle_wrap_mode(self) -> str:
    """Cycle through truncate → wrap → scroll and rebuild display."""
    modes = ["truncate", "wrap", "scroll"]
    idx = modes.index(self._wrap_mode)
    self._wrap_mode = modes[(idx + 1) % len(modes)]
    # Update horizontal overflow on the CodeViewer container
    if self._wrap_mode == "scroll":
        self.styles.overflow_x = "auto"
    else:
        self.styles.overflow_x = "hidden"
    if self._total_lines > 0:
        self._rebuild_display()
    return self._wrap_mode
```

**Cache max line width in `load_file()`** — after `self._highlighted_lines` is populated:
```python
self._max_line_width = max((len(l) for l in self._highlighted_lines), default=0)
```

### Step 2: Modify `_rebuild_display()` in `code_viewer.py`

In `_rebuild_display()`, change the table column setup and truncation logic based on `_wrap_mode`:

**Column setup (replacing current lines 263-265):**
```python
if self._wrap_mode == "scroll":
    # Use actual content width so table extends beyond viewport
    scroll_code_width = max(code_max_width, self._max_line_width + 2)
    table.add_column(style="dim", justify="right", width=LINE_NUM_WIDTH, no_wrap=True)
    table.add_column(no_wrap=True, width=scroll_code_width)
    table.add_column(width=ann_width, no_wrap=True, justify="left")
elif self._wrap_mode == "wrap":
    table.add_column(style="dim", justify="right", width=LINE_NUM_WIDTH, no_wrap=True)
    table.add_column(no_wrap=False, width=code_max_width)
    table.add_column(width=ann_width, no_wrap=True, justify="left")
else:  # truncate (current behavior)
    table.add_column(style="dim", justify="right", width=LINE_NUM_WIDTH, no_wrap=True)
    table.add_column(no_wrap=True, width=code_max_width)
    table.add_column(width=ann_width, no_wrap=True, justify="left")
```

**Truncation logic (around lines 299-303):** Only apply truncation in truncate mode:
```python
if self._wrap_mode == "truncate":
    effective_max = min(self.MAX_LINE_WIDTH, code_max_width)
    if len(line) > effective_max:
        line = line.copy()
        line.truncate(effective_max)
        line.append("…", style="dim")
```

### Step 3: Add keybinding in `codebrowser_app.py`

**Add binding** (after line 168):
```python
Binding("w", "toggle_wrap_mode", "Wrap mode"),
```

**Add action method:**
```python
def action_toggle_wrap_mode(self) -> None:
    """Cycle the code viewer's wrap mode."""
    code_viewer = self.query_one("#code_viewer", CodeViewer)
    new_mode = code_viewer.cycle_wrap_mode()
    self._update_info_bar()
    self.notify(f"Wrap mode: {new_mode}", timeout=2)
```

### Step 4: Show mode in info bar (`codebrowser_app.py`)

In `_update_info_bar()` (around line 498), add the wrap mode indicator when not in the default truncate mode:
```python
code_viewer = self.query_one("#code_viewer", CodeViewer)
# ... existing parts ...
if code_viewer._wrap_mode != "truncate":
    parts.append(f"mode: {code_viewer._wrap_mode}")
```

### Step 5: Reset mode on `_reset_state()`

In `_reset_state()` (code_viewer.py, line 77), do NOT reset `_wrap_mode` — the mode should persist across file loads. This is intentional: if the user sets wrap mode, it should stay when they switch files.

## Files Modified

| File | Changes |
|------|---------|
| `.aitask-scripts/codebrowser/code_viewer.py` | State variable, cache max width, `cycle_wrap_mode()`, `_rebuild_display()` mode logic |
| `.aitask-scripts/codebrowser/codebrowser_app.py` | Keybinding `w`, action method, info bar indicator |

## Verification

1. Open codebrowser: `./ait codebrowser`
2. Open a file with long lines (e.g., a minified JS/CSS file, or any file with lines >120 chars)
3. Verify default mode shows truncation with "…" (existing behavior preserved)
4. Press `w` → verify lines wrap within the pane width (no horizontal overflow)
5. Press `w` → verify horizontal scrollbar appears and scrolling works to see full long lines
6. Press `w` → back to truncate mode
7. Switch files while in wrap/scroll mode → verify mode persists
8. Test with a large file (>2000 lines) to verify viewport mode still works
9. Verify cursor movement (up/down) works correctly in all three modes
10. Check info bar shows "mode: wrap" or "mode: scroll" when not in truncate

## Step 9: Post-Implementation

Follow SKILL.md Step 9 for archival and cleanup.
