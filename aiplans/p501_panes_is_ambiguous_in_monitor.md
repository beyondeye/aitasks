---
Task: t501_panes_is_ambiguous_in_monitor.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Plan

Disambiguate "pane" terminology in the monitor TUI. The word "pane" was used for
both tmux panes (the monitored processes) and UI panels (the two navigable areas).

### Changes

- Rename `PreviewPane` class → `PreviewPanel` (class + all references)
- Change session bar hint: `Tab: switch pane` → `Tab: switch panel`
- Update module docstring to use "panels" for UI areas
- Update comment: `Preview pane size presets` → `Preview panel size presets`
- Keep all tmux pane references unchanged (`PaneCard`, `#pane-list`, `Zone.PANE_LIST`, notifications)

## Final Implementation Notes
- **Actual work done:** Renamed UI panel concept from "pane" to "panel" in monitor_app.py. 14 lines changed across class definition, CSS selectors, widget queries, user-visible hint, docstring, and comment.
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** Kept all tmux pane references intact since "pane" is the correct tmux term. Only renamed references to the TUI's own UI panels.
