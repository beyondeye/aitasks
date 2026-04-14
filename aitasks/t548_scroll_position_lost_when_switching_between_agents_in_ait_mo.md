---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask_monitor]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-14 15:57
updated_at: 2026-04-14 17:22
---

in ait monitor we have recently introudude the feature of allowing to scroll the agent terminal preview pane vertically. the desired behavior is that when we switch between vieweed agents pnae the current vertical scroll position for each agent is remembered. this bug was supposed to be fixed (in the past there was a SINGLE scroll position remembered, shared between all agents, that was clearly a bug) not the bug is different: when we switch agent with top down arrow, the scroll position is reset completely (to tail) this happen immediately when switch to a new agent
