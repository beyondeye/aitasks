---
date: 2026-02-22
title: "v0.6.0: Code Explanations, Wrap Skill, and Auto-Refresh Board"
linkTitle: "v0.6.0"
description: "aitasks v0.6.0 brings code explanation tracking, retroactive task wrapping, smarter file selection, and an auto-refreshing board."
author: "aitasks team"
---

aitasks v0.6.0 is out, and it's a feature-packed release. Here are the highlights.

## Code Explanation Skill

Ever wanted to document how a piece of code evolved over time? The new `/aitask-explain` skill generates structured code explanations with evolution tracking. Point it at a file or module, and it produces a narrative that captures not just what the code does, but how it got there — complete with data extraction pipelines and run management for iterative analysis.

## Retroactive Task Wrapping

Already made changes but forgot to create a task first? The `/aitask-wrap` skill has you covered. It looks at your uncommitted work, figures out what you did, and retroactively creates a proper task with an implementation plan — so your project history stays clean even when you code first and organize later.

## Smarter File Selection

A new internal `user-file-select` capability makes it easier for other skills to help you find the right files. It combines keyword search, fuzzy name matching, and functionality-based search, and it's already integrated into both the explain and explore workflows.

## Board Auto-Refresh

The board TUI now refreshes itself periodically, with a new settings screen where you can dial in your preferred interval. No more manual refreshes to see what your teammates (or your other Claude sessions) are up to.

---

**Full changelog:** [v0.6.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.6.0)
