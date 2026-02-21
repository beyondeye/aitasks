---
priority: medium
effort: high
depends: ['130']
issue_type: feature
status: Ready
labels: [geminicli]
created_at: 2026-02-16 10:31
updated_at: 2026-02-16 10:31
boardcol: next
boardidx: 50
---

I want to add support for geminicli in aitasks framework, please refer to task 130, for details of possible issues, and suggested architecture. the idea is to keep the current .claude/skills are the source of truth for skills and only write wrappers to support other ai cli tools, specificaly for gemini cli (see https://geminicli.com/docs/cli/skills) agent skills will be in the .gemini/skills of current project. during ait setup there should be a qustions if to install aitasks for gemini cli and yes should copy ./gemini/skills wrappers to current repo (and commit them so their are part of the repo) gemini cli skills will be only wrappers around the original claude code skills. it could perhaps best to implement this task using geminicli itself so that it will have the most up-to-date info of features and available tools to match what we use in the claude code skills. specifically the internall tool geminicli uses to ask user questions is the ask_user tool, for reference of the AskUserQuestion used in claudecode see task t130. here is an excerpt on to use the tool according the geminicli description of it

✦ The ask_user tool allows me to ask you one or more questions to gather preferences, clarify requirements,

as i said the task it write wrappers for all existing claude code skills and update ait setup to ask user if he want gemini cli support in the current repo and if yes install the geminicli skill wrappers.

this is a complex tasks so it will be probably better to split it into multiple child tasks

IMPORTANT TASK UPDATE: in geminicli skills cannot be invoked as custom commands like in claude code, to instead of writing wrapper gemini skills for aitask claudecode skills
need instead to write geminicli wrapper custom commands
