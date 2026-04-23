---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitask_monitor]
created_at: 2026-04-23 12:33
updated_at: 2026-04-23 12:33
---

in ait monitor tui, we have two panes: the agent list and the agent window preview. the agent window preview is supposed to refresh every x secods (3 seconds) by default. I have found out that that something this auto refresh feature stop working, and the preview content is refreshed only when we switch between selected agents in the agent list pane, or when we switch focus from agent list to the preview pane. what is interesting is that agent list status is updated crrectly every 3 seconds. only the preview content is not. then after interacting in the live preview (typing) is suddengly get unstacked, I am not sure what is actually happening. I need to trouble shoot and fi this bug
