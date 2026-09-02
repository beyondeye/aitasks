---
date: 2026-09-02
title: "v0.34.0: Know whether your backlog is growing, Merges no longer race, and The board knows where a task actually is"
linkTitle: "v0.34.0"
description: "A big one — 81 tasks landed since v0.33.0. The headline: the framework got a lot better at not tripping over itself when several agents work the same repo at once, and `ait stats` learned to tell you whether your backlog is actually growing."
author: "aitasks team"
---


A big one — 81 tasks landed since v0.33.0. The headline: the framework got a lot better at not tripping over itself when several agents work the same repo at once, and `ait stats` learned to tell you whether your backlog is actually growing.

## Know whether your backlog is growing

`ait stats` and the stats TUI gained two new views. **Backlog Level** shows how many open tasks sat in each category, week by week, going back as far as you ask. **Backlog Net Flow** shows what arrived versus what closed in each of those weeks. Together they answer the question a completion count can't: are you keeping up? Both tables read chronologically with the current week last, so you can stack them, and `--csv-backlog` dumps the whole thing if you'd rather graph it elsewhere.

## Merges no longer race

If you run several agents in parallel, two of them finishing at the same moment used to mean two merges interleaving. There's now a session-anchored mutex in front of the merge step: one agent goes, the others queue and get told exactly what happened and what to do next. On top of that, every auto-commit in the framework — the claim, the fold mark, the sync sweep — was narrowed to commit only the paths it owns, skip anything a live lock is holding, and quarantine rather than publish work it can't attribute. Your neighbour's in-flight edits stay yours.

## The board knows where a task actually is

The board's In-Flight section gained a **Planned** lane for tasks whose plan is approved but whose implementation you've deliberately put off — a state that used to be invisible. Each in-flight item now shows the workflow phase it's reached, and task detail has a Gates section listing the active gates and how many have passed. When the board can't determine a phase, it says so instead of guessing.

## Trades, not just concerns

The shadow reviewer's concerns now carry an impact vector: what the change improves, what it worsens, and at what effort, over a fixed seven-dimension vocabulary. The picker renders that as a trade profile with magnitude colour-coded, plus a detail panel for whatever you're focused on — so you can see at a glance which concern buys you a lot and which one is mostly cost. You can also hit `e` to edit a concern's payload before it gets copied.

## Trails reach the board

`ait trail`'s By-Trail board view can now move work: `m` moves the focused task to a column, `M` moves the entire wave in wave order. Trail runs also end with a proper recap of what they wrote and where to look at it. And trails finally have real documentation — two new pages covering the workflow and the skill.

---

---

**Full changelog:** [v0.34.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.34.0)
