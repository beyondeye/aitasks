---
date: 2026-08-18
title: "v0.33.0: Your shadow reviewer works with Codex and OpenCode now, Turn a review concern straight into a task, and Trails got lighter and easier to read"
linkTitle: "v0.33.0"
description: "v0.33.0 is the release where the shadow reviewer stops being a Claude-only feature and trails stop being expensive to keep around."
author: "aitasks team"
---


v0.33.0 is the release where the shadow reviewer stops being a Claude-only feature and trails stop being expensive to keep around.

## Your shadow reviewer works with Codex and OpenCode now

The auto-recheck review loop used to arm only for Claude panes. It now arms for Codex and OpenCode too — the framework knows what each agent's composer looks like when it's genuinely ready for input, and each CLI's native permission dialog was measured live so a dialog is never mistaken for review output. The monitors picked up the same knowledge, so an agent sitting on a question gets flagged whichever CLI it's running.

## Turn a review concern straight into a task

The concern picker already let you forward a concern or reject it for good. Now there's a third option: press `t` and the concern becomes its own aitask when you confirm. Good ideas that aren't for right now stop evaporating when you close the picker.

## Trails got lighter and easier to read

`ait trail` now defaults to lite depth — the full evidence-backed document is still there behind `--deep`, but the everyday path is fast. The board's By-Trail view gained a summary pane telling you where the trail stands (`v` expands it full-screen), trails can carry a one-paragraph overview of what they're for, and the detail view now opens on the entry you focused with only the waves, drift and evidence that actually bear on it.

## The docs gate knows what you changed

The `docs_updated` gate used to hand you everything dirty in the tree and let you sort it out. It now attributes the change surface to your task specifically — commit tags, plan scope, and a baseline captured when you claimed the task — and asks you directly about anything it can't place.

## The worktree is cut when you actually need it

Task worktrees used to be created up front, at branch resolution. Now the names get resolved in Step 5 but the fork waits until after you've approved the plan and the drift check has run. Abandon a task at plan time and there's nothing left behind to clean up.

---

---

**Full changelog:** [v0.33.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.33.0)
