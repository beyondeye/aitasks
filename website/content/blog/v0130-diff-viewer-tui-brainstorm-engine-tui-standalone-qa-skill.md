---
date: 2026-03-23
title: "v0.13.0: Diff Viewer TUI, Brainstorm Engine & TUI, and Standalone QA Skill"
linkTitle: "v0.13.0"
description: "v0.13.0 is a big one — the diff viewer is fully operational, brainstorming has its own TUI, and there's a dedicated QA skill so you stop forgetting to write tests."
author: "aitasks team"
---


v0.13.0 is a big one — the diff viewer is fully operational, brainstorming has its own TUI, and there's a dedicated QA skill so you stop forgetting to write tests.

## Diff Viewer TUI

You can now visually compare implementation plans side-by-side (or interleaved) with `ait diffviewer`. It supports classical line-by-line diffs and structural section-aware diffs, word-level highlighting so you can spot exactly what changed within a line, markdown syntax coloring, and a unified mode for comparing multiple plans at once. There's even a merge screen where you can cherry-pick individual hunks from one plan into another.

## Brainstorm Engine & TUI

The brainstorm system is taking shape. You can initialize a brainstorm session for any task, and it creates a DAG of exploration nodes — each produced by a specialized agent (explorer, comparator, synthesizer, detailer, patcher). The TUI gives you a dashboard with node details, an ASCII art DAG graph, a dimension comparison matrix, and a wizard for launching new brainstorm operations. Still a work in progress, but the foundation is solid.

## Standalone QA Skill

`/aitask-qa` replaces the old embedded test-followup step with something much more capable. It analyzes your changes, identifies test coverage gaps, optionally runs your test suite, and produces a health score. Three tiers — quick, standard, and exhaustive — let you choose how deep to go. It can even create follow-up tasks for missing test coverage automatically.

## Default Execution Profiles

Tired of picking the same profile every time you run `/aitask-pick`? You can now set default profiles per skill in your project config, and override them with `--profile` on any command. The settings TUI has a nice per-skill picker for it too.

## Numbered Archives

The archive system got a major overhaul under the hood. Instead of one giant `old.tar.gz` that grows forever, tasks are now stored in numbered per-range archives. Lookups are O(1) instead of scanning the entire archive, and parallel archiving is safe. The migration is transparent — old archives still work.

---

---

**Full changelog:** [v0.13.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.13.0)
