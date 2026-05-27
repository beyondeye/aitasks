---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [manual_verification]
created_at: 2026-05-27 11:18
updated_at: 2026-05-27 11:18
---

I recently run the t787 manual verification task using codex as code agent. manual verification is designed basically to work with claude code that has support for AskUserQuestion also outside plan mode. what happened surprised me: codex created a "plan" for manual verification that the it executed "automatically" exercising the tui and sending commanding in the tmux session running ait brainstorm in a custom tmux session for the test, creatign fake data when needed, etc. this was actually very useful. I am not sure if all code agent can be capable to do what codex 5.5 did, but it is a possiblity, that is, we should have an option for "manual verification" tasks to optionally create a plan to do the "manual" verification of at least what is possible to automate, actually in automode. perhaps not all manual verification points will be run this way but this should be an option even when running manual verification in the "proper" way with claude code. ask me questions if you need clarifications
