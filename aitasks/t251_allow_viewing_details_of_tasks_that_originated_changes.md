---
priority: medium
effort: medium
depends: ['256']
issue_type: feature
status: Ready
labels: [codebrowser]
created_at: 2026-02-26 08:28
updated_at: 2026-02-26 12:00
boardidx: 30
boardcol: unordered
---

in codebrowser currently is possible to see for each code line with task originated it, but althoguh the info is available (and extracted in aiexplains directory) it is not possible to see this information. need to add command shortcut that open a an additional pane (or close it) where we can see the text of the plan that originated the change. the content of this pane should update automatically when line selection is updated, when the user finalize selection (stop holding shift and finish the selection action flow (or stop holidng the left mouse button and finish the selection flow with the mouse). this pane with the plan text should be support markdown rendering (like with task description box in task detail in ait board. thhis pane should be 30 characters line width with option to expandit/ to half screen and back with context aware keyobard shortcuts

## Responsive layout integration notes (from t256)

Task t256 introduced a responsive layout system for the codebrowser. The new detail pane must integrate with this system:

- **Width distribution priority:** The code column should get space first (up to at least 80 characters). Only after the code column has 80+ characters should additional screen width be allocated to the new detail/plans pane. The annotation label column stays at a fixed width (12 chars, or 10 on narrow terminals).
- **Responsive tree width:** The file tree already adapts (35/28/22 chars at breakpoints 120/80). The detail pane sizing must account for the tree width at the current breakpoint.
- **Dynamic column calculation:** The width logic lives in `code_viewer.py:_rebuild_display()` — it computes `code_max_width = max(20, available - LINE_NUM_WIDTH - ann_width - 2)`. When adding the detail pane, extend this calculation to allocate remaining width after code gets its 80-char minimum.
- **Toggle behavior:** The detail pane toggle should reclaim its width for the code column when hidden (same pattern as annotation column toggle reclaims 12 chars).
- **on_resize handler:** Both `CodeViewer.on_resize()` and `CodeBrowserApp.on_resize()` trigger layout recalculation — the detail pane must respond to resize events and recalculate its width.
