---
Task: t275_more_bug_fixes_in_ait_settings.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# Plan: Fix Settings TUI Navigation Bugs (t275)

## Context

The `ait settings` TUI has two navigation bugs related to arrow key focus management:

1. **Can't return to tab row with up arrow** — Once focus moves from the tab bar to the content area, pressing up at the top of the content doesn't return focus to the tab bar.
2. **Agents defaults tab: invisible focus on down arrow from tabs** — Pressing down from the tab bar focuses the `VerticalScroll` container (which has `can_focus=True` by default) instead of the first `ConfigRow` widget. Since VerticalScroll has no visual focus indicator, the user sees no selection.

## Root Cause

Both bugs are in `_nav_vertical()` at `settings_app.py:706-728`:

**Bug 1:** When `direction == "up"` and `idx == 0`, nothing happens — the method doesn't move focus back to the tab bar because it only considers widgets inside the `TabPane`.

**Bug 2:** The focusable widget query `[w for w in pane.query("*") if w.can_focus and w.display]` picks up the `VerticalScroll` container itself (inherited `can_focus=True` from `ScrollableContainer`), so `focusable[0]` is the container, not the first `ConfigRow`.

## Changes

**File: `aiscripts/settings/settings_app.py`**

### Fix 1: Filter out container widgets from focusable list (line 714)

Change the focusable query to exclude `VerticalScroll` containers:

```python
# Before:
focusable = [w for w in pane.query("*") if w.can_focus and w.display]

# After:
focusable = [
    w for w in pane.query("*")
    if w.can_focus and w.display and not isinstance(w, VerticalScroll)
]
```

This fixes Bug 2 for all tabs (Agent Defaults, Board, Models, Profiles) since they all use `VerticalScroll` containers.

### Fix 2: Navigate back to tab bar when pressing up at first widget (lines 718-728)

Add logic to move focus to the active tab when pressing "up" at idx == 0:

```python
if focused in focusable:
    idx = focusable.index(focused)
    if direction == "up" and idx > 0:
        focusable[idx - 1].focus()
    elif direction == "up" and idx == 0:
        # Return focus to the tab bar
        try:
            active_tab = tabbed.query_one(f"#--content-tab-{active_pane_id}")
            active_tab.focus()
        except Exception:
            pass
    elif direction == "down" and idx < len(focusable) - 1:
        focusable[idx + 1].focus()
```

This also needs a Textual `Tab` import to type-check if needed, but since we're querying by ID, no new import is needed.

## Final Implementation Notes
- **Actual work done:** Both navigation bugs fixed in `_nav_vertical()`. Also added keyboard hint labels (`↑↓: navigate | a/b/m/p: switch tabs`) to Board, Models, and Profiles tabs (previously only in Agent Defaults tab).
- **Deviations from plan:** Fix 2 went through three iterations: (1) hardcoded Tab ID `#--content-tab-{pane_id}` — wrong format, (2) `Tabs.active_tab.focus()` — `ContentTab` has `can_focus=False`, (3) `tabbed.query_one("Tabs").focus()` — focuses the `ContentTabs` widget itself which has `can_focus=True`. The third approach works correctly.
- **Issues encountered:** Textual's `TabbedContent` uses internal `ContentTab` subclass with `can_focus=False`, and `ContentTabs` subclass of `Tabs` with `can_focus=True`. Focusing the `Tabs` container puts keyboard control back on the tab bar.
- **Key decisions:** Used `isinstance(w, VerticalScroll)` filter rather than a whitelist of allowed widget types — simpler and handles future widget additions automatically.
- **Additional fix:** Keyboard hints were only shown in Agent Defaults tab — added to all four tabs for consistent UX.
