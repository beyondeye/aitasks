---
date: 2026-08-05
title: "v0.31.0: Mark cards and move them in bulk, The board got noticeably faster, and Every shortcut is visible again"
linkTitle: "v0.31.0"
description: "If you spend your day on the board, this one is for you. v0.31.0 makes the kanban board feel like a real tool for handling many tasks at once — and quietly fixes a whole class of \"it said it worked but it didn't\" failures underneath."
author: "aitasks team"
---


If you spend your day on the board, this one is for you. v0.31.0 makes the kanban board feel like a real tool for handling many tasks at once — and quietly fixes a whole class of "it said it worked but it didn't" failures underneath.

## Mark cards and move them in bulk

Hit `Space` on any card to mark it. The checkbox glyph is always visible, so you can see at a glance what's selected, and the selection sticks as you navigate around. Then press `m`, pick a destination column, and every marked task moves at once — with a review dialog first so you can back out.

## The board got noticeably faster

Three things landed together here. Moving a card now rewrites a single file instead of renumbering the whole column, moving a card between columns transplants the widget instead of rebuilding the board, and filtering only touches the columns that actually changed. On a big board, typing in the search box stays smooth and a two-column hop dirties nothing but the card you moved.

## Every shortcut is visible again

Board footers used to hide keys once they ran out of room, which meant half the operations were undiscoverable. The footer now wraps onto multiple rows, and you can cap how many with `footer_max_rows`.

## No more silent successes

A pile of fixes in this release share one theme: things that failed while reporting success. Task-data syncs, stale-lock cleanup, `ait lock list` on an empty branch, and the installer's upgrade step all now tell you what went wrong and what to do about it. Task and plan files are also written atomically, so a concurrent reader never catches a half-written file.

## Risk mitigations can stay in the plan

When planning surfaces a risk mitigation, you no longer have to spin it out as a follow-up task. You can inline it as a pre- or post-phase of the plan you're about to execute, decided one mitigation at a time — and the workflow will stop you from implementing if a blocking mitigation is still unfinished.

---

---

**Full changelog:** [v0.31.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.31.0)
