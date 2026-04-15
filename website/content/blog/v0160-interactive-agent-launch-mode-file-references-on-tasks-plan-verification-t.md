---
date: 2026-04-15
title: "v0.16.0: Interactive agent launch mode, File references on tasks, and Plan verification tracking"
linkTitle: "v0.16.0"
description: "v0.16.0 is a big one — 46 tasks landed, headlined by interactive agents you can actually watch, a file-references system that ties tasks to specific lines of code, and smarter plan verification that stops duplicated work across agents."
author: "aitasks team"
---


v0.16.0 is a big one — 46 tasks landed, headlined by interactive agents you can actually watch, a file-references system that ties tasks to specific lines of code, and smarter plan verification that stops duplicated work across agents.

## Interactive agent launch mode

You can now run agentcrew agents in `interactive` mode instead of headless, which means they spawn inside a tmux window you can attach to and watch live. Flip the mode per-agent from the brainstorm wizard, from the Status tab with `e`, or via the new `ait crew setmode` CLI — each agent type ships with a sensible default that you can override in the Settings TUI.

## File references on tasks

Tasks can now carry a `file_references` list pointing at specific files and line ranges like `foo.py:10-20^30-40`. Open the codebrowser, select a block, press `n`, and a new task is created pre-seeded with that exact range. If the new task overlaps with an existing pending task's file refs, you'll get offered an auto-merge. The board's task-detail modal shows these refs as a clickable row that jumps straight back into the codebrowser at the right line.

## Plan verification tracking

Plans now record which agents have verified them against the current codebase. Combined with the new `plan_verification_required` and `plan_verification_stale_after_hours` profile keys, a pick can skip re-verification when another agent validated the plan recently — no more repeating the same work across agent runs.

## ANSI log viewer and task restart

A new `ait crew logview` TUI tails agent log files with ANSI color rendering, live search, and a raw-mode toggle. Press `L` from the brainstorm Status tab or monitor to open it for the focused agent. And when an agent goes off the rails, `R` on an idle pane in `ait monitor` now kills the window and restarts the task cleanly.

## Monitor preview that actually stays put

The monitor preview remembers where you scrolled on each pane, freezes with a `PAUSED` badge when you scroll up from the tail, and re-engages with `t`. Tmux refreshes run async now, so arrow keys don't get eaten by refresh ticks and the whole TUI stays responsive even with a lot of agents.

---

---

**Full changelog:** [v0.16.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.16.0)
