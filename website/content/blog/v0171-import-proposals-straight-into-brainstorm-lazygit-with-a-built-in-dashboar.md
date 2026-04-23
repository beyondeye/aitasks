---
date: 2026-04-23
title: "v0.17.1: Import proposals straight into brainstorm, Lazygit with a built-in dashboard, and `ait setup` that tells you what's going on"
linkTitle: "v0.17.1"
description: "v0.17.1 is a small but focused release: you can now bring your own proposal into the brainstorm engine, lazygit gets a dashboard companion, and `ait setup` is noticeably more trustworthy."
author: "aitasks team"
---


v0.17.1 is a small but focused release: you can now bring your own proposal into the brainstorm engine, lazygit gets a dashboard companion, and `ait setup` is noticeably more trustworthy.

## Import proposals straight into brainstorm

If you already have a markdown spec for a feature, you no longer have to paste it into a blank brainstorm session by hand. `ait brainstorm init --proposal-file my_proposal.md` now hands the file to a new initializer agent that reformats it into the brainstorm node format — structured sections, dimension metadata, the whole shape — then auto-starts the crew runner so you can jump straight into the interactive flow.

## Lazygit with a built-in dashboard

Launch `git` from the TUI switcher and you'll get a minimonitor companion pane next to lazygit, just like the `create` and `explore` flows. The cleanup is smart about it: if you split off a shell or a codeagent into the same window, the companion sticks around when lazygit exits so your other work isn't interrupted. Close every pane and the window tears itself down cleanly.

## `ait setup` that tells you what's going on

`ait setup` in a fresh project is now a lot more honest. It installs `AGENTS.md` alongside `CLAUDE.md` and `GEMINI.md`, asks for a default tmux session name, and shows a visible three-line banner before committing framework files (with captured git errors so silent failures no longer hide). Config writes go through symlinks instead of replacing the inode, and every write is verified afterward — so if something didn't land, you get a warning pointing at the problem instead of an empty config field.

---

---

**Full changelog:** [v0.17.1 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.17.1)
