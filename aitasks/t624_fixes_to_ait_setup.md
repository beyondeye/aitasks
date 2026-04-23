---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [installation, install_scripts]
created_at: 2026-04-23 11:31
updated_at: 2026-04-23 11:31
---

There are several issues with ait setup that install framework files in a new project directory:  1)the current installed CLAUDE.md, GEMINI.md are seed files created a long a ago. since then CLAUDE.md in aitasks project has evolved quite a bit. obviously not all the content of CLAUDE.md in the aitasks project is relevant for a generic project that use the aitasks framework, need to check what is relevant and update the seed CLAUDE.md 2) there is no AGENTS.md installed (or symlinked from CLAUDE.md, only GEMINI.md). AGENTS.md is used for example by codex. perhaps install it? 3)framework files installed are not commiitted to git (at least not when no git repo initially found and it is created from scratch) we should ask the user in the ait setup interactively, if he wants the framework files git added and committed 4) in ait setup we should ask the user wich tmux session name to use as default (used by ait ide, see also ait settings, tmux tab) it should show as dfault "aitasks" but the user should be able to change 5) currently no default is set for git_tui to use in tmux (see ait settings tmux tab) if lazygit is installed, it should be set as the default. ask me questions if you need clarifications
