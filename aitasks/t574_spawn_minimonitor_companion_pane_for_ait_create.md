---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [aitask-create, bash_scripts, tmux, aitask_monitormini]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-16 11:58
updated_at: 2026-04-16 12:25
---

currently wehn we spawn ait create inside tmux, it is usually get spawned in a new window with no minimonitor companion tui like insteas is done for aitask pick that spawn a codeagent with a companion minimontor. I want to add the same feature (with smart spawning of minimonitor) for ait create. the mottivation: we usually spend significant time writing task description, and we don't what is happening we our codeagent, what is their status. the spawning should be smart: don't spawn a companion minimonitor to ait create if ait create is spawned in a window where minimononitor or full monitor already exists, also don't spawn companion minimonitor if ait create is spwaned in the same window as existing other aitasks tui. automatic despwan smart mechanism, similar to what is used for codeagent minimonitor companion. ask me questions if you need clarifications
