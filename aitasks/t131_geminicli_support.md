---
priority: medium
effort: high
depends: ['130']
issue_type: feature
status: Ready
labels: [geminicli]
created_at: 2026-02-16 10:31
updated_at: 2026-02-16 10:31
boardcol: now
boardidx: 20
---

I want to add support for geminicli in aitasks framework, please refer to task 130, for details of possible issues,
 the task it write wrappers for all existing claude code skills and update ait setup to ask user if he want gemini cli support in the current repo and if yes install the geminicli wrappers.
note that most existing claude code skill are used also as commands but not all, check which skill need wrappers as skills and which need wrappers as commands or both
make sure command/skills wrappers support passing the arguments the command/skill expect

IMPORTANT TASK UPDATE: in geminicli skills cannot be invoked as custom commands like in claude code, to instead of writing wrapper gemini skills for aitask claudecode skills
need instead to write geminicli wrapper custom commands

note: the current note about geminicli plan mode in conductor docs: need to check if this is also relevant for aitasks framework: https://github.com/gemini-cli-extensions/conductor/commit/3bc0f18413b8bfb71b1d8000fcdae21c0874896a

add support for codexcli codeagent by adding wrappers to existing claudecode skills to be recognized as custom commands  in codex cli.  https://developers.openai.com/codex/skills and also https://agentskills.io/specification. and see https://code.claude.com/docs/en/skills. I want to keep the claude code skills are the main source of truth and wrap them in codecli skill by referencing them and call them indirectly by telling codecli how to interpret specific claude code instructions (like AskUserQuestion tool). it can be that it would be better to implement this feature using codexcli directly so that it can direct access to the internal (not documented) information about its configured internal tools. so basically the idea is: create ./agents/skills/SKILLNAME wrappers for each of the claude code skills in the project. Need to update the ait setup script to ask if we want support in a project for codexcli (and in the future gemini cli) and if yes then copy to the project the skill wrappers for codecli. claudecode skills will be always be included by default as all other agents skills will always reference them. here is for reference the documentation of the request_user_input tool in codex cli that corresponds to AskUserQuestion in claude code         In your current session, it is not available because collaboration mode is Default (it only works in Plan
