---
priority: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [aitasks, codexcli]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-16 10:16
updated_at: 2026-02-20 11:16
boardcol: next
boardidx: 30
---

add support for codexcli, by migrating claude code skills to codex cli. this can be a challenging tasks especially from the point of view of maintenance: I am not going to switch using codexcli any time soon, so there will not be proper testing for this feature, not in the beginning and not when new features will be added to aitasks. for documentation of codecli skill to understand how they differ from claudecode skills see https://developers.openai.com/codex/skills and also https://agentskills.io/specification. and see https://code.claude.com/docs/en/skills. I want to keep the claude code skills are the main source of truth and wrap them in codecli skill by referencing them and call them indirectly by telling codecli how to interpret specific claude code instructions (like AskUserQuestion tool). it can be that it would be better to implement this feature using codexcli directly so that it can direct access to the internal (not documented) information about its configured internal tools. so basically the idea is: create ./agents/skills/SKILLNAME wrappers for each of the claude code skills in the project. Need to update the ait setup script to ask if we want support in a project for codexcli (and in the future gemini cli) and if yes then copy to the project the skill wrappers for codecli. claudecode skills will be always be included by default as all other agents skills will always reference them. here is for reference the documentation of the request_user_input tool in codex cli that corresponds to AskUserQuestion in claude code         In your current session, it is not available because collaboration mode is Default (it only works in Plan

Here is instead the description of the AskUserQuestion tool in claude code:  AskUserQuestion Tool Specifications

This is a complex task so it is probably better to decompose it in child tasks

UPDATE TO TASK DEFINITION: only claudecode currently directly support invoking a skill as a custom slash command, so for the user facing skills in aitasks framework
that are invokable as custom slash commands, instead of writing wrapper skill to original claude code skills I need to writter wrapper custom commands for codecli. 
in codex you can reference a skill in a command with a text like this: use $MySkill to ...
