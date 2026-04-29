---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [aitask_board, agent_chooser]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-29 22:22
updated_at: 2026-04-29 22:43
---

in aitasks tuis like ait board, we have the command dialog where we show the command being run we can change the (A)agent to use for the command from the default value defined in settings for that action

we want to change a few things in the dialog: instead of having a button use last, change it to (u)se previous (not default) that is we don't store last model use if it was default. also when we actually select the (a)agent button to choose the codeagent to use, don't list browse all model option together with top rated model, and add instead a keyboard shortcut, to switch from top models to all models list. the shortcut cannot be one of the lettes from a-z because we have the edit active where we type the model name to select. so perhaps use left right arrows to change the list from where we search models with the following possible list 1) top models 2) all models 3) all codex models 4) all opencode models 5) all claude models 6) all gemini models. ask me question if you need clarifications
