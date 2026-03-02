---
Task: t285_more_aitask_settings_bugs.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Context

Task t285: Fix two bugs in the `ait settings` TUI (`aiscripts/settings/settings_app.py`):

1. **Tab switching shortcuts (a/b/m/p) only work when the tab bar is focused.** When focus is on a widget inside a tab pane (e.g., a CycleField or ConfigRow), pressing a tab shortcut key momentarily switches to the new tab, then immediately reverts to the old tab. Root cause: `tabbed.active = new_tab_id` switches the visible pane, but focus remains on a widget in the old (now-hidden) pane. Textual's focus system detects the focused widget is hidden and switches the active tab back to show it.

2. **Board tab hint line is incomplete.** The Board tab has CycleField widgets (auto-refresh, sync-on-refresh) but the keyboard hint only shows `↑↓: navigate | a/b/m/p: switch tabs` — missing `◀▶: cycle options` and positioned awkwardly in the middle of the tab content (between the columns section and the user settings section).

Previous focus management fixes (t275) that MUST be preserved:
- VerticalScroll excluded from focusable widget list in `_nav_vertical()`
- Up-arrow at idx 0 returns focus to the tab bar
- Hint lines added to Board, Models, and Profiles tabs

## Plan

**File:** `aiscripts/settings/settings_app.py`

### Fix 1: Tab switching focus management

- [x] Add `_focus_first_in_tab()` helper method after `_nav_vertical()`
- [x] Update tab switching code in `on_key()` to call the helper via `call_after_refresh`

### Fix 2: Board tab hint line

- [x] Remove hint from middle of Board tab (between columns and user settings)
- [x] Add comprehensive hint at bottom of Board tab (after Save button) with `◀▶: cycle options`

## Verification

1. Run `./ait settings`
2. Navigate to a CycleField in the Agent Defaults tab using ↓ arrow
3. Press `b` to switch to Board tab — should switch and stay, with focus on first widget
4. Press `a` to go back to Agent Defaults — should work from any focus position
5. Check Board tab has hint line at the bottom with `◀▶: cycle options`
6. Verify up-arrow at top of tab still returns focus to tab bar (preserve t275 fix)

## Post-Review Changes

### Change Request 1 (2026-03-02)
- **Requested by user:** Move keyboard shortcut hints to be consistently at the bottom of ALL tabs, not just Board
- **Changes made:** Moved hint lines from top/middle to bottom in Agent Defaults, Models, and Profiles tabs. Added hints to early-return paths in Models and Profiles (no profiles, add new profile).
- **Files affected:** `aiscripts/settings/settings_app.py`

## Final Implementation Notes
- **Actual work done:** Fixed tab switching focus issue by adding `_focus_first_in_tab()` helper that focuses the first widget in the target tab after refresh, plus an immediate `Tabs.focus()` call to prevent Textual from reverting the tab switch. Moved all keyboard shortcut hint lines to be consistently at the bottom of every tab. Updated Board tab hint to include `◀▶: cycle options`.
- **Deviations from plan:** Original plan only moved the Board tab hint. User requested all tabs be consistent, so all four tabs were updated. Also needed a two-step focus approach: immediate focus on tab bar + deferred focus on tab content.
- **Issues encountered:** Initial fix with only `call_after_refresh` didn't work for the Models tab (no focusable widgets). Between setting `tabbed.active` and the deferred focus, Textual detected the focused widget was hidden and reverted the tab. Fixed by immediately focusing the tab bar before the deferred call.
- **Key decisions:** Two-step focus: (1) immediate `Tabs.focus()` to prevent revert, (2) `call_after_refresh` to refine focus to first content widget. For tabs with no focusable content (Models), focus stays on tab bar. Early return paths in Profiles and Models tabs also get hints for completeness.
