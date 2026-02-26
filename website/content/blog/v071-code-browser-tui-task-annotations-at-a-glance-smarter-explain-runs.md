---
date: 2026-02-26
title: "v0.7.1: Code Browser TUI, Task Annotations at a Glance, and Smarter Explain Runs"
linkTitle: "v0.7.1"
description: "v0.7.1 introduces the code browser — a brand new TUI for exploring your codebase with full task traceability — along with a batch of board improvements and developer experience fixes."
author: "aitasks team"
---


v0.7.1 introduces the code browser — a brand new TUI for exploring your codebase with full task traceability — along with a batch of board improvements and developer experience fixes.

## Code Browser TUI

The headline feature of this release is a full code browser you can launch with `ait codebrowser`. It gives you a file tree on the left and a syntax-highlighted code viewer on the right, complete with task annotation gutters that show exactly which tasks modified each line. Navigate with keyboard or mouse, select code ranges, and jump straight into the explain skill for deeper analysis.

## Task Annotations at a Glance

Every line of code now carries its history. The code browser's gutter column shows color-coded task IDs so you can instantly see who changed what and why. Click any annotated line and a detail pane shows the full task description and implementation plan — no context switching needed.

## Smarter Explain Runs

Explain runs are now automatically named after their source directory and old runs get cleaned up automatically. No more manually tracking or pruning stale explain data — just run the explain pipeline and the system handles the rest.

## Board Quality-of-Life

The board gets column collapse/expand for less clutter, optimized lock refreshes for snappier interactions, and a smarter unlock flow that resets task status and assignment in one step.

## Multi-Platform Repository Support

Review guide imports and the new repo fetch library now work seamlessly across GitHub, GitLab, and Bitbucket with automatic platform detection — no manual configuration needed.

---

---

**Full changelog:** [v0.7.1 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.7.1)
