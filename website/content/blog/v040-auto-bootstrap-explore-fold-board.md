---
date: 2026-02-17
title: "v0.4.0: Auto-Bootstrap, Explore Skill, and Task Folding"
linkTitle: "v0.4.0"
description: "aitasks v0.4.0 brings auto-bootstrap setup, interactive codebase exploration, task folding, and board customization."
author: "aitasks team"
---

v0.4.0 is a big one. It makes getting started easier, adds new ways to investigate your codebase, and gives you more control over how you organize tasks.

## Auto-Bootstrap for New Projects

Setting up aitasks used to require downloading the installer manually. Now just run `ait setup` in any directory and it bootstraps everything automatically — the framework files, the task directory structure, all of it. One command, done.

## Interactive Codebase Exploration

The new `/aitask-explore` skill is for when you have a vague idea and need to figure out the right approach. Point it at a problem area, and it guides you through an interactive investigation of your code — asking follow-up questions, exploring related files, and eventually creating a well-scoped task from what you discover. It even checks for existing tasks that might overlap with your idea and offers to fold them together.

## Task Folding

Speaking of folding — the `/aitask-fold` skill lets you merge related tasks into a single one. If you've accumulated a few tasks that are really about the same thing, fold them together instead of juggling duplicates. The folded tasks get marked with a `Folded` status and a pointer to the primary task, so you can always trace back to the originals.

## Board Column Customization

The board TUI now lets you add, edit, and delete columns via a command palette (Ctrl+P) or by clicking column headers. Pick from 8 colors to make your board visually distinct. It's your board — set it up however makes sense for your workflow.

---

**Full changelog:** [v0.4.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.4.0)
