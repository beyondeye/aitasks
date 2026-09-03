---
date: 2026-09-03
title: "v0.34.1: Park the agents you're not watching, A heads-up before two tasks collide, Sync stages every conflict you resolve, and  not just the first"
linkTitle: "v0.34.1"
description: "v0.34.1 is a consolidation release — one new workflow feature, one new monitor feature, and a stack of fixes to the things that quietly went wrong while several agents worked the same tree."
author: "aitasks team"
---


v0.34.1 is a consolidation release — one new workflow feature, one new monitor feature, and a stack of fixes to the things that quietly went wrong while several agents worked the same tree.

## Park the agents you're not watching

Running eight agents at once means six of them are idle at any moment, and they all take up the same amount of room in `ait monitor`. You can now park an agent: cycle its mark to parked and press `P` to fold every parked agent out of the list. The session bar tells you how many are hidden, and parked agents stop being captured, previewed or offered for concerns — so parking one actually costs you less, not just visually.

## A heads-up before two tasks collide

The task workflow can now warn you, before you start implementing, that the task you just picked overlaps with something another agent already has in flight. It's deliberately advisory — it never blocks a pick — and every shipped profile has it turned off for now, because the measurements say the evidence isn't good enough yet to be worth a prompt. Turn it on per profile with `parallel_admission` if you want to see it in action.

## Sync stages every conflict you resolve, not just the first

If `ait sync` handed you more than one conflict, it staged the first file you resolved and forgot the rest, leaving the rebase wedged. Now every file you resolve gets staged, and if a stage fails you hear about it instead of finding out later.

## The docs site can no longer ship a dead link

Hugo happily builds a page full of broken relative links and dead anchors. There's now a site-wide link checker running in CI, and it found 28 broken links across 11 pages on its first pass — all repaired. From here on, a dead link blocks the deploy.

## Clicking back into minimonitor does what you meant

Alt-tabbing back to a terminal running `ait minimonitor` used to re-select the first agent card, so your first click landed on whatever had moved under your cursor — and if a dialog was open, it lost focus entirely. The focus-in handler now leaves things alone when something is already focused.

---

---

**Full changelog:** [v0.34.1 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.34.1)
