---
date: 2026-10-11
title: "v0.37.0: Several trails at once in `ait trails`, Keep your default models current, and Let an agent untangle a sync conflict"
linkTitle: "v0.37.0"
description: "v0.37.0 brings tabs to `ait trails`, a nudge when your default models get replaced by newer ones, and an agent that can resolve task-data sync conflicts for you."
author: "aitasks team"
---


v0.37.0 brings tabs to `ait trails`, a nudge when your default models get replaced by newer ones, and an agent that can resolve task-data sync conflicts for you.

## Several trails at once in `ait trails`

`ait trails` now keeps several trails open as tabs. Switch with `[` / `]` or `1`–`9`, and close one with `ctrl+w`. Background tabs refresh on their own and show a marker when they change. You can also press `p` on a trail member to pick it, using the same dialog as the board. If an agent for that task is already running, its window is focused instead.

## Keep your default models current

When a newer model replaces one of your configured defaults, `ait upgrade` now offers to switch. You can run the same check any time with `ait codeagent check-superseded`. The Settings TUI marks these defaults too, and you switch with `o`. Lineages are recorded for Claude, Codex and OpenCode, and Claude Haiku 5.5 is registered as the successor to Haiku 4.5.

## Let an agent untangle a sync conflict

When syncing task data hits a conflict, the syncer and the board now offer to launch a code agent to resolve it. The agent works in a separate worktree, and other sessions' work is preserved. "Run in terminal" in the syncer now works as well.

## Sharper shadow agents

Ask a shadow agent `>pd` and it lists the plan's main design decisions, but only those with a real trade-off. Shadow concerns from Codex and OpenCode now reach the monitor reliably, including bullet-style markers, stripped brackets and text wrapped in the middle of a word. Every Codex pane now runs inline, so its scrollback is kept.

## Clearer endings and safer upgrades

Every task-workflow run now ends with a clear Complete or Stopped banner. Upgrades also remove script files the framework no longer ships, so stale leftovers can no longer load in place of the framework's own modules.

---

---

**Full changelog:** [v0.37.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.37.0)
