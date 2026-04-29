---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [codexcli, aitask_pick]
assigned_to: dario-e@beyond-eye.com
implemented_with: codex/gpt5_5
created_at: 2026-04-29 09:04
updated_at: 2026-04-29 14:50
---

currently codexcli support askuserquestion only when in plan mode (please recheck current online documentation to confirm). but currently, in agentcommanddialog called from ait board for spawning aitask-pick codeagent, or when spawned from other tuis, codex is spawned in "normal" model (not plan mode). we should updates spawning code (ait_codeagent script?) and commands used to spawn codeagent in tuis so that when a invoked skill require interactiveity the codeagent is spawned with a prompt that put it in plan model (for codexcli). ask me questions if you need clarifications
