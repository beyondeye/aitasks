---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [agentcrew, brainstorming]
children_to_implement: [t462_1, t462_2, t462_3]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-25 09:54
updated_at: 2026-03-25 11:42
---

currently in agencreew tui and brainstorm tui, that integrates with agentcrew runner. we don't see current porcesses that are running agents that were triggered by the runner. this make no sense. the runner already keep track of the processes for the agents it spawned. we should have tab in the tui that show the current running processes with information like when it was started, running time, actual cpu time (or similar stat) associated codeagent name in the crew) and actions when one of the processes in the list: send kill command, send pause command, send resume command, hard kill. the hard kill command should also take care to update the code agent status file. this is a complex tasks that should be decomposed in child tasks
