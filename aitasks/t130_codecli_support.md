---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [aitasks, codexcli]
children_to_implement: [t130_3]
implemented_with: claudecode/opus4_6
created_at: 2026-02-16 10:16
updated_at: 2026-03-05 09:12
boardcol: now
boardidx: 20
---

add support for codexcli codeagent by adding wrappers to existing claudecode skills to be recognized as custom commands  in codex cli.  https://developers.openai.com/codex/skills and also https://agentskills.io/specification. and see https://code.claude.com/docs/en/skills. I want to keep the claude code skills are the main source of truth and wrap them in codecli skill by referencing them and call them indirectly by telling codecli how to interpret specific claude code instructions (like AskUserQuestion tool). it can be that it would be better to implement this feature using codexcli directly so that it can direct access to the internal (not documented) information about its configured internal tools. so basically the idea is: create ./agents/skills/SKILLNAME wrappers for each of the claude code skills in the project. Need to update the ait setup script to ask if we want support in a project for codexcli (and in the future gemini cli) and if yes then copy to the project the skill wrappers for codecli. claudecode skills will be always be included by default as all other agents skills will always reference them. here is for reference the documentation of the request_user_input tool in codex cli that corresponds to AskUserQuestion in claude code         In your current session, it is not available because collaboration mode is Default (it only works in Plan

note that most existing claude code skill are used also as commands but not all, check which skill need wrappers as skills and which need wrappers as commands or both
make sure command/skills wrappers support passing the arguments the command/skill expect

this is an initial task for support, than only create wrappers to claude skills that are optionally installed in ait setup if codex is detectec (similar to claude
specifc file installations. also check if it is possible to create a seed file with perimission for codex similar to the one existing for claude code, that will be
installed with ait setup if codex detected.
