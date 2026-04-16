---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitask_monitor]
created_at: 2026-04-16 12:45
updated_at: 2026-04-16 12:45
---

in ait monitor tui we have two panes: agent list and agent window preview. with up/down arrow we can select an agent in the list and its preview is shown in the bottom panel. there seems to be a bug. please look at the current tmux open windows in aitasks session, I currently havhen agent-pick 575 is selected it first show the correct preview , but when the 3s refresh hit (and there is at least one active agent), the preview "CONTENT" switch batch to the one of the first agent in the list, but the selection in the agent list did not change it is sitll pointing to agent-pick 575. can yuo help me trouble shoot this issue?
