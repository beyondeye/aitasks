---
Task: t257_performance_when_chaning_selection.md
Worktree: (none — working on current branch)
Branch: (none — working on current branch)
Base branch: main
---

# Plan: Codebrowser Performance When Changing Selection (t257)

## Context

When navigating files in the codebrowser with keyboard arrows, Shift+arrows for selection, or mouse dragging, the TUI feels sluggish. Scrollbar/mousewheel scrolling is fast because Textual handles it as a CSS offset change without content rebuild. But keyboard/mouse interactions trigger `_rebuild_display()` on **every event**, which creates a new Rich Table (up to 200 rows in viewport mode, up to 2000 without), rebuilds the annotation gutter, and calls `Static.update()` forcing a full repaint + layout pass.

## Root Cause

The `_rebuild_display()` method in `code_viewer.py` is called from:
- `move_cursor()` — every arrow key press
- `extend_selection()` — every Shift+arrow press
- `on_mouse_move()` — every mouse move during drag
- `_edge_scroll_tick()` — 20Hz timer during edge drag

Each call builds a new `Table`, recomputes the annotation gutter, and triggers `Static.update(table)` which runs Textual's full layout + repaint. At 30Hz key repeat, that's 30 full rebuilds/sec with no coalescing.

## Changes

All changes in **one file**: `aiscripts/codebrowser/code_viewer.py`

### 1. Throttle rebuilds to ~30fps

Add a time-based throttle so rapid input (held arrows, mouse drag) triggers at most ~30 rebuilds/sec. First event is immediate; subsequent events within 33ms are deferred. A trailing timer ensures the final state always renders.

**New state in `__init__`:**
```python
self._last_rebuild_time: float = 0.0
self._pending_rebuild_timer = None
```

**New methods:**
- `_request_rebuild()` — checks elapsed time; if >= 33ms, flushes immediately; otherwise schedules a deferred flush
- `_flush_rebuild()` — calls `_rebuild_display()` + `_scroll_cursor_visible()` + `post_message(CursorMoved(...))`
- `_cancel_pending_rebuild()` — stops any pending timer

**Modified methods** (replace 3-line `_rebuild_display()` + `_scroll_cursor_visible()` + `post_message()` with `_request_rebuild()`):
- `move_cursor()`
- `extend_selection()`
- `on_mouse_move()`
- `_edge_scroll_tick()`

**Guard against stale deferred rebuilds:**
- `on_mouse_up()` — add `_cancel_pending_rebuild()` before immediate rebuild
- `load_file()` — add `_cancel_pending_rebuild()` before immediate rebuild

**NOT throttled** (discrete actions that must render immediately):
- `load_file()`, `set_annotations()`, `toggle_annotations()`, `on_resize()`, `on_mouse_down()`, `on_mouse_up()`, `clear_selection()`, `on_mouse_scroll_up/down()`

### 2. Cache annotation gutter

The annotation gutter only changes when `set_annotations()` is called or the viewport window shifts. Cache it across rebuilds.

**New state in `__init__`:**
```python
self._annotation_version: int = 0
self._cached_gutter: list | None = None
self._cached_gutter_key: tuple | None = None
```

**Changes:**
- `set_annotations()` — bump `_annotation_version`, clear cache
- `_reset_state()` — invalidate cache
- `_rebuild_display()` — check cache key `(vp_start, vp_end, _annotation_version)` before calling `_build_annotation_gutter()`

### 3. Skip layout pass on same-viewport rebuilds

When cursor moves within the same viewport window (no shift), the table has the same row count. Use `Static.update(table, layout=False)` to skip Textual's layout calculation.

**New state in `__init__`:**
```python
self._last_rendered_viewport: tuple | None = None
```

**Changes in `_rebuild_display()`:**
```python
current_vp = (vp_start, vp_end)
needs_layout = self._last_rendered_viewport != current_vp
self._last_rendered_viewport = current_vp
self.query_one("#code_display", Static).update(table, layout=needs_layout)
```

Reset `_last_rendered_viewport` in `_reset_state()` and `on_resize()`.

## Risk Assessment: Mouse Selection Regressions

### What stays safe (not throttled)

`on_mouse_down()` and `on_mouse_up()` remain **immediate** — the user always sees instant feedback on click and release. The coordinate system logic (content-relative before `capture_mouse()`, viewport-relative after) is untouched.

### Where risk exists: `on_mouse_move()` during drag

Currently, each mouse move event triggers `_rebuild_display()` + `_scroll_cursor_visible()` synchronously. After throttling, the **internal state** (`_cursor_line`, `_selection_end`) is still updated immediately on every event, but the **visual update** may be deferred by up to 33ms.

**Risk 1 — Stale `scroll_y` in next mouse event:**
`on_mouse_move` computes `row = int(self.scroll_y) + event.y`. If a previous `_scroll_cursor_visible()` was deferred, `scroll_y` may be stale. However, `_scroll_cursor_visible()` only changes `scroll_y` when the cursor is near the edge of the visible area (within 2-line margin). For mid-viewport drag, it's always a no-op — **zero risk**. Near edges, the discrepancy is at most 1-2 lines for 33ms before the flush corrects it. **Low risk**, barely perceptible.

**Risk 2 — `_ensure_viewport_contains_cursor()` not called in `on_mouse_move`:**
Unlike `move_cursor()` and `extend_selection()`, the `on_mouse_move` handler does NOT call `_ensure_viewport_contains_cursor()`. This is unchanged from the current code. Edge scrolling handles viewport shifts via its own timer. **No new risk.**

**Risk 3 — Race between deferred rebuild and `on_mouse_up`:**
If the user releases the mouse while a deferred rebuild is pending, `on_mouse_up()` cancels the pending timer first (`_cancel_pending_rebuild()`), then does its own immediate rebuild. **No risk** — explicitly handled.

### Overall mouse risk: **LOW**

The internal selection state is always correct. Only the visual frame rate during fast drag is affected (capped at ~30fps instead of ~60fps). The final state on mouse release is always correct.

## Complexity Trade-off

### Current code: simple, direct

Every interaction follows one pattern: update state → `_rebuild_display()` → `_scroll_cursor_visible()` → `post_message()`. Easy to understand, easy to add new handlers.

### After changes: two patterns to understand

1. **Rapid-fire handlers** → update state → `_request_rebuild()` (may defer)
2. **Discrete actions** → `_rebuild_display()` directly (always immediate)

A developer adding a new interaction handler needs to decide which pattern to use. The rule is simple: "Is this called rapidly in a loop? Use `_request_rebuild()`. Is this a one-shot action? Use `_rebuild_display()` directly."

### Concrete additions

| What | Count | Lines |
|------|-------|-------|
| New state variables | 6 total | +6 lines in `__init__` |
| New methods | 3 (`_request_rebuild`, `_flush_rebuild`, `_cancel_pending_rebuild`) | +25 lines |
| Modified methods | 6 (simplified — each loses 2 lines, gains 1) | net -6 lines |
| Gutter cache logic | inline in `_rebuild_display` | +5 lines |
| Layout skip | inline in `_rebuild_display` | +4 lines |
| **Net** | | **+~30 lines** |

### Simplification option: drop Optimization 3 (layout skip)

The `layout=False` optimization saves ~2-3ms per rebuild when viewport hasn't shifted. It's a nice-to-have but adds 1 state variable and a conditional. Could be dropped to reduce cognitive load with only minor performance loss. The throttle + gutter cache provide the main wins.

## Expected Impact

| Scenario | Before | After |
|----------|--------|-------|
| Hold arrow key (30Hz repeat) | 30 full rebuilds/sec, each with gutter + layout | 30 rebuilds/sec, gutter cached, layout skipped |
| Mouse drag (~60Hz events) | Up to 60 rebuilds/sec | Capped at ~30, gutter cached |
| Edge scroll (20Hz timer) | 20 rebuilds/sec with full gutter | 20 rebuilds/sec, gutter cached |
| Scrollbar/wheel | Fast (unchanged) | Fast (unchanged) |

The biggest win comes from the throttle reducing mouse drag rebuilds by ~50% and from skipping the layout pass + gutter computation on cursor-only movements.

## Verification

1. `./ait codebrowser` — open a large file (>2000 lines)
2. Hold down-arrow for several seconds — should scroll smoothly
3. Hold Shift+down-arrow — selection should expand smoothly
4. Click + drag from top to bottom — smooth drag selection
5. Drag past visible area — edge scroll still works
6. Release mouse — final state renders correctly
7. Resize terminal — display adapts immediately
8. Toggle annotations (t key) — immediate update
9. Go-to-line (g key) — immediate jump

## Post-Implementation

Follow Step 9 (Post-Implementation) from the task workflow for archival.
