---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask_monitor]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-13 12:11
updated_at: 2026-04-13 12:24
---

I have just noticed that in ait monitor when we have multple agents and we scroll with the vertical scrollbar or the mouse wheel the current shown position in the codeagent preview panel, the position is not independent for each agent: if we scroll to some position for one agent then swich to another, scroll again, then switch back, the scroll position is not preserved. if we don't scroll between agent switch the position is preserved. it look like there is a single variable for keeping track of scroll position for all agent previews, instead of one per agent. can you help me fix this issue?
