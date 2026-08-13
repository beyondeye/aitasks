---
date: 2026-08-13
title: "v0.32.0: Board columns you can actually manage, Grouped cards, and Reject a concern and it stays rejected"
linkTitle: "v0.32.0"
description: "v0.32.0 is a big one for anyone who lives in the board and the monitors. Columns became something you actually manage, cards learned to group themselves, and the shadow reviewer finally stops repeating objections you've already dismissed."
author: "aitasks team"
---


v0.32.0 is a big one for anyone who lives in the board and the monitors. Columns became something you actually manage, cards learned to group themselves, and the shadow reviewer finally stops repeating objections you've already dismissed.

## Board columns you can actually manage

Press `e` on the board and you get a real Columns dialog — add, rename, recolour, reorder with `Shift+Up`/`Shift+Down`, and merge one column into another in a single move. Column creation also came to minimonitor: when a task prompt pops up, you can send it to an existing column or spin up a brand-new one right there, without ever opening the board.

## Grouped cards

Tasks now carry a `boardgroup` field, and the board renders each group under its own header. Arrow keys step over groups as single units, `x` collapses one, and collapsed state sticks across restarts — it even survives you renaming, merging or deleting the column underneath. Filter the board and each group header tells you how many of its hidden cards matched.

## Reject a concern and it stays rejected

The shadow reviewer's concern picker used to be forward-or-nothing. Now every concern has three states — forward, reject, or leave it — and rejections are remembered per task. Every review producer reads that store before it emits, so the objection you dismissed in round one doesn't come back in round four. There's a viewer for what you've rejected, in case you change your mind.

## The shadow re-reviews on its own

When the followed agent revises its plan, the shadow can now notice and re-run its review by itself. It waits for actual evidence that something changed, debounces across a few ticks, and sits out a cooldown, so it won't fire on a half-drawn screen or a spinner. Each review block is stamped with its round number, so you always know whether you're looking at fresh feedback or last round's.

## You can see what phase an agent is in

Agent cards in both monitors now show the workflow phase of whatever they're following — and whether it's sitting there waiting on you. In minimonitor that shares a single row with gate status, shedding detail gracefully as the pane narrows. The shadow reads the same signal to pick its own default mode instead of asking you first.

## Follow-up tasks say why they exist

Auto-spawned tasks now carry a `followup_kind` — risk mitigation, QA, review finding, docs gap, and so on — set automatically wherever the framework creates a task. Board cards show it as a coloured glyph, group headers roll it up, and `ait ls` will filter on it with `--followup-kind` (or `--no-followup-kind` for genuine new work only).

---

---

**Full changelog:** [v0.32.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.32.0)
