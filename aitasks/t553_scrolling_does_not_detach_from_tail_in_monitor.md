---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitask_monitor]
created_at: 2026-04-14 23:30
updated_at: 2026-04-15 09:42
boardidx: 30
---

we have recently implemented task 541 that was supposed to fix several issue with preserving the vertical scrolling state of the agent preview pane in ait monitor tui, when switching between previews of diffrent agents, and also make sure that when the preview pane is scrolled up it becomes "detached" from the tail of the codeagent output, if we scroll up to view previous output of the codeagent, then the scroll position will not be affected by the codeagent adding more output in the meanwhile (the tail the output). this detaching from tail is bug that has not been fixed, need to investigate further.
