---
priority: low
effort: medium
depends: [t417_11]
issue_type: feature
status: Implementing
labels: [tui, brainstorming]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-19 17:16
updated_at: 2026-03-20 10:29
---

Implement the unified diff mode in DiffViewerScreen. Currently the 'u' keybinding toggles _unified_mode but both code paths in _load_current_view call the same load_multi_diff — it's a no-op. The unified mode should show all comparisons simultaneously on one screen instead of requiring n/p navigation between them. Each comparison's diff lines should be annotated with the plan gutter letter (A, B, C...) so the user can see which plan each change comes from. Reference the PLAN_COLORS in diff_display.py for the color scheme.
