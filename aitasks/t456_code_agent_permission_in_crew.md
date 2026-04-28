---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [agentcrew, brainstorming]
assigned_to: ''
created_at: 2026-03-24 22:16
updated_at: 2026-03-26 09:27
boardidx: 140
boardcol: unordered
---

I am trying to run a brainstorm in ait brainstorm (see /home/ddt/Work/aitasks/.aitask-crews/crew-brainstorm-427/) when running explorer001 (/home/ddt/Work/aitasks/.aitask-crews/crew-brainstorm-427/explorer_001_log.txt) I noticed that the explored got stuck bacause of missing permissions. and finally the runner mark the task as stale (error). how can i set the correct permissions for each agent in the crew, and (second problem) how to set the permission in away that is compatible with all codeagent: this require some additions to ait codeagent to support passing various types of permissions in agent ndependent way, and set the proper permission for the current agent types that are used in a brainstorm session. also we should have a mechanism to easily change the permission when missing permissions are detected in agent logs, and also a better way to start/stop agents in an agentcrew by the runner and by a tui that integrate the runner like the ait brainstorm tui. this is complex task that should be split in child tasks. ask me questions if you need clarifications
