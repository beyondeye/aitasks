---
Task: t479_enhance_tui_switcher_dialog.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

The TUI Switcher overlay (`.aitask-scripts/lib/tui_switcher.py`) currently has three limitations:
1. Arrow navigation stops at list edges instead of wrapping
2. Only shows 6 hardcoded TUIs — no visibility into other tmux windows (agent panes, shells, etc.)
3. No keyboard shortcuts for quick-jumping to specific TUIs

## Plan

### 1. Arrow Key Wrap-Around

Create a `_WrappingListView(ListView)` subclass that overrides cursor movement to wrap at edges, skipping disabled items.

Replace `ListView` with `_WrappingListView` in `compose()`.

### 2. Show All Tmux Windows Grouped by Type

- Replicate `tmux_monitor.py`'s classification inline (AGENT_PREFIXES, TUI_NAMES)
- Add `_GroupHeader(ListItem)` for non-selectable section headers
- Add `_WindowListItem(ListItem)` for non-TUI windows
- Revise `on_mount()` to discover all windows and group them: TUIs, Agents, Other
- Extend `_switch_to()` and selection handlers to support non-TUI windows
- Increase dialog max-height to accommodate more items

### 3. Keyboard Shortcuts for Specific TUIs

- Add `b`, `c`, `s`, `r` bindings to `TuiSwitcherOverlay`
- Add `action_shortcut_*()` methods that directly switch/launch target TUI
- Update hint text

### Files to Modify

- `.aitask-scripts/lib/tui_switcher.py` — all three changes (single file)

### Verification

1. Open switcher from any TUI (`j`), test arrow wrapping at top/bottom
2. Verify TUI/Agent/Other grouping with running windows
3. Test `b`/`c`/`s`/`r` shortcuts
4. Test switching to non-TUI windows
