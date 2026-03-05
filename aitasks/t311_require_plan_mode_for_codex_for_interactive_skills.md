---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [codexcli, aitask_pick]
created_at: 2026-03-05 10:18
updated_at: 2026-03-05 10:18
---

codexcli does not support AskUserQuestion analog when not in plan mode. when not in plan mode and we run aitask-pick, it simply skips all user questions, and also skip plan review before execution. this is very problematic. so we must require, for all skills that are interactive, to be started in codex plan mode and if we are not in plan mode we need to notify the user to swith to plan mode and restart the skill (update the codex cli skill wrapper for aitask-pick) we should also review other skills that are interactive (probably most of them) and this rquirement. since this will become a common part for most of the codexcli wrapper skills we should define this instruction in a common markdown file

also another issue with codex in aitask-pick, is that after implementation, codex does not show the askuser question to finalize the task, so we need to add explicit call to code "please finalize this task" or "run post-implementation steps". need to update task 130_3 with this important note
