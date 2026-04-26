---
date: 2026-04-26
title: "v0.18.1: Triage manual-verification checklists in batches, Filter the board by issue type, and `ait upgrade` actually upgrades branch-mode setups now"
linkTitle: "v0.18.1"
description: "v0.18.1 is a polish-and-fix release. The headline changes are a faster manual-verification flow, a new issue-type filter in the board, and a fix for branch-mode upgrades that were silently leaving framework files uncommitted."
author: "aitasks team"
---


v0.18.1 is a polish-and-fix release. The headline changes are a faster manual-verification flow, a new issue-type filter in the board, and a fix for branch-mode upgrades that were silently leaving framework files uncommitted.

## Triage manual-verification checklists in batches

Manual-verification tasks used to walk you through items one at a time. Now the skill re-renders the whole numbered checklist with state markers on every turn, and you can answer in batch through the Other field — `1 pass, 3 defer, 5 skip not applicable` lands four state changes in a single response. The single-item Pass/Fail/Skip/Defer prompt is still there for the items that actually need careful thought.

## Filter the board by issue type

The board TUI gains a new `t` view mode. Hit `t` and you get a multi-select dialog of every issue type — `feature`, `bug`, `refactor`, and the rest — pick the ones you care about, and the board narrows to those. Picks persist per project, and a summary line under the view selector tells you what's active. Pressing `t` again reopens the picker if you want to adjust.

## `ait upgrade` actually upgrades branch-mode setups now

If your project uses a separate `aitask-data` branch (the default for new setups), `ait upgrade` was silently skipping the commit of framework files — so your `.aitask-scripts/` and `.claude/` would update on disk but never make it into git. v0.18.1 fixes the symlink-handling bug at the root and adds a dedicated commit pass for the data branch's `aitasks/metadata/` and `aireviewguides/`.

## Setup tells you when there's no remote

Running `ait setup` on a repo without an `origin` remote used to silently configure branch-tracked features that quietly won't sync anywhere. Now setup pauses, explains exactly which features need a remote to work, and waits for you to acknowledge before continuing. Bonus: lock operations now distinguish "the lock branch doesn't exist on origin" from "I can't reach origin right now," so transient network blips no longer look like missing infrastructure.

---

---

**Full changelog:** [v0.18.1 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.18.1)
