---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask_monitor]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-14 12:02
updated_at: 2026-04-14 12:04
---

in ait monitor tui we have two panes 1) agent list 2) agent terminal preview. when the agent list pane is focused, the user can use the up/down arrow to switch currently focused agent in the list and correspondigly the content of the preview pane. there is an autorefresh loop for checking the status of agents (running/idle) and updating the agent preview content. the problem I want to solve is the agent list becoming irresponsive to user up/down keyboard command to switch focused agent each time we hit the every-3s refresh. my idea would be (need to check if it make sense) is: when the user hit the up/down arrow, then immediately refresh only the (new) selected agent and delay the next refresh to start in 3s from the last up/down arrow command sent by user. even better, if the user has just interacted with up/down arrow then temporarily change the refresh interval from 3s (or whatever is configured) to double that. please check pros/cons of this possible improvement to current refresh mechanism, and check for alternative solutions. I will review and decide
