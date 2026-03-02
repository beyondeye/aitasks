---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [ait_settings]
assigned_to: dario-e@beyond-eye.com
implemented_with: claude/opus4_6
created_at: 2026-03-02 15:07
updated_at: 2026-03-02 16:05
---

in ait settings tui, the shortcuts for switching between tabs works only if the top line with tabs is currently selected, otherwise what happens is that the shortcut trigger swith to the new tab but immediately after we switch back to the old tab. I think has to do to focusmanagement fixes we did previously, so must be careful we do not undo previos work with this fix. also the "Board" tab is missing the hint line with available keyboard shortcuts (navigate/ switch tab keyboard hints)
