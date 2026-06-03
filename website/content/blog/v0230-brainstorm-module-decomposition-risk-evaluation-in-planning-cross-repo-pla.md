---
date: 2026-06-03
title: "v0.23.0: Brainstorm module decomposition, Risk evaluation in planning, Cross-repo planning, and  straight from explore"
linkTitle: "v0.23.0"
description: "v0.23.0 is a big one — two major new capabilities land, plus a pile of macOS/portability fixes and UI polish."
author: "aitasks team"
---


v0.23.0 is a big one — two major new capabilities land, plus a pile of macOS/portability fixes and UI polish.

## Brainstorm module decomposition

You can now split a brainstorm design into independent module subgraphs and work each one on its own track. Decompose a design into modules, merge or sync them as first-class brainstorm operations, and watch each module's status update live. When a module is ready to build, "Fast-track this module" extracts it into a linked aitask in a single pass.

## Risk evaluation in planning

Planning now sizes up risk along two separate axes — how risky the change is to code health, and how likely it is to actually hit its goal. It records both on the task, proposes mitigation follow-ups (before or after the main work), and automatically re-verifies a plan when one of those mitigations lands.

## Cross-repo planning, straight from explore

`aitask-explore` now notices when your description spans more than one repo and offers to create a cross-repo paired task — no manual wiring, the cross-repo planning flow is inherited automatically.

## A friendlier brainstorm node picker

The node action dialog now shows every operation available on a node, complete with relevance hints, and cascade delete previews exactly which nodes would go with it before you confirm.

## Smoother on macOS

Several BSD/macOS portability crashes in `ait setup` are fixed, the board now validates its Python dependencies at install time (and falls back gracefully when the fast path can't load), and the board no longer auto-refreshes by default — set an interval only if you want it.

---

---

**Full changelog:** [v0.23.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.23.0)
