---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [aitask_explore, ait_settings, tmux]
children_to_implement: [t480_1, t480_2]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-30 10:42
updated_at: 2026-03-30 12:25
---

I want to improve UX of running aitask-explore skill, that is one of the most important skills: currently you need to open a new shell start a code agent and type aitask-explore. instead we want to add 1) add a shortcut to explore in the TUI switcher that is integrated in most tui, that will launch a new codeagent with /aitask-explore command. for defining which codeagent to run, we need to add settings for it in the setttings TUI in the codeagent tab, update seed defaults for agent defaults. by the way when selected e(x)plore (keyboard shortcut) it will alway open a new windows, will not swith to existing explore window. this is complex task that should be split in child tasks
