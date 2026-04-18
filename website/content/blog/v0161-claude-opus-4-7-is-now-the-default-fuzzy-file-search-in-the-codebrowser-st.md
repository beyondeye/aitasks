---
date: 2026-04-18
title: "v0.16.1: Claude Opus 4.7 is now the default, Fuzzy file search in the codebrowser, and Structured brainstorming"
linkTitle: "v0.16.1"
description: "v0.16.1 ships with Claude Opus 4.7 as the new default and a pile of codebrowser TUI upgrades. Structured brainstorming lands too — you can now zoom brainstorm operations in on individual sections of a plan."
author: "aitasks team"
---


v0.16.1 ships with Claude Opus 4.7 as the new default and a pile of codebrowser TUI upgrades. Structured brainstorming lands too — you can now zoom brainstorm operations in on individual sections of a plan.

## Claude Opus 4.7 is now the default

Opus 4.7 is registered in two variants — standard and 1M context — and the 1M variant is the new default for pick, explore, and all brainstorm ops. If you want the standard variant or need to swap models later, the new `aitask-add-model` skill registers models and promotes them to defaults with a single command, including dry-run diffs so you can see exactly what it will change.

## Fuzzy file search in the codebrowser

The codebrowser gets a proper fuzzy file search box — just start typing part of a filename and it scores matches with a recursive multi-alignment algorithm borrowed from toad. No more hunting through the file tree.

## Structured brainstorming

Brainstorm plans and proposals now carry structured section markers, and the brainstorm TUI wizard has a new step that lets you pick which sections to explore, compare, detail, or patch. You can refine one part of a design without re-running the whole agent over the entire document.

## Codebrowser polish

Lots of small-but-nice codebrowser improvements: `c` copies the current file path, `w` toggles word wrap, `R` refreshes the file tree against the current tracked-file set, and the `n` shortcut (create task from selection) now works even with no file selected. Launching `ait create` from the board, codebrowser, or TUI switcher also spawns a minimonitor companion pane next to the new window automatically.

## Killable brainstorm sessions

The brainstorm TUI finally grows a "Delete" operation with a double-confirmation modal. Stale sessions are no longer permanent.

---

---

**Full changelog:** [v0.16.1 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.16.1)
