---
date: 2026-09-25
title: "v0.36.0: Discuss your brainstorm proposals, Frozen agents come back when you start `ait ide`, and Notes that cross repositories"
linkTitle: "v0.36.0"
description: "v0.36.0 is a big one: you can talk through brainstorm designs with an agent, frozen agents come back when you start `ait ide`, and notes can now reach tasks in other repos."
author: "aitasks team"
---


v0.36.0 is a big one: you can talk through brainstorm designs with an agent, frozen agents come back when you start `ait ide`, and notes can now reach tasks in other repos.

## Discuss your brainstorm proposals

The brainstorm TUI has a new **Discuss** operation. Pick any node, or mark a few, and an advisory-only agent opens beside you. It can compare proposals in simple words or in depth, explain one plainly, answer your questions, and check a design for structural flaws before you commit to it. It never edits anything.

## Frozen agents come back when you start `ait ide`

If you froze agents and then closed their windows or restarted your machine, `ait ide` now notices when it starts. It lists what's missing and lets you recreate the viewers, restore the agents, re-pick the tasks, or skip. Restores are also more faithful now: each agent comes back on the model it was running, the new window gets its minimonitor, and an agent can no longer lose track of its task.

## Notes that cross repositories

`ait note --project <name>` sends a durable note to a task in another registered repository, and that repository writes and commits the note itself. If you work across several aitasks projects, you can now pass context to the task that needs it, whichever repo it lives in.

## A heads-up when the session hook is missing

If an upgrade left the Claude Code session hook uninstalled, you'll now be told. Freeze and restore depend on that hook. Run `ait setup --hooks-only` to install just the hook without redoing the full setup.

## New models and a stand-alone trails view

Claude Opus 5.5 is now the default Claude Code model. Codex GPT-6 Sol and Luna are registered, and Sol now runs shadow and discuss agents. Implementation trails also have their own TUI: run `ait trails` to open them without the board.

---

---

**Full changelog:** [v0.36.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.36.0)
