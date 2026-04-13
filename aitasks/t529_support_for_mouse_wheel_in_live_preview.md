---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [aitask_monitor]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-13 10:11
updated_at: 2026-04-13 10:53
---

in ait monitor we have the bottom panel in the tui that is a preview of selected codeagent session. we cannot currently scroll up to see previus part of terminal history. this would be very helpful. whe should add support for vertical scrollbar (with option to hide show it) and support for mouse wheel for scrolling. Also the currently we have z shorcut to change the vertical size of the preview panel: there shold be setting for the zoom size with almost ALL vertical space taken by the "preview" panel (like except for 10 lines) also, changing the zoom factor should immediately trigger refresh of the preview panel content we should not wait for the next refresh cycle (3 seconds refresh cycle)
