---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
archived_reason: superseded
labels: [agentcrew, whitelists, ait_brainstorm]
created_at: 2026-04-26 12:55
updated_at: 2026-04-27 17:21
completed_at: 2026-04-27 17:21
boardidx: 200
---

I am now running agent-initializer_bootstrap for brainstorm 635, I noticed that ait crew shell command where not properly whitelisted for code agent execution. need to add them to whiltelists for all codeagents in seed whitelist, ask me questions if you need clarifications
Another issue is that the initialize-proces is reported as DEAD in the ait brainstorm statu stab: this is probably related to the fact that the initializer skill/prompt has not proper keep alive status updates: need to investigate this. the process was reported "dead" after 1minute but the agent is actually running, perhaps this was different process? I don't think so. need to investiage
