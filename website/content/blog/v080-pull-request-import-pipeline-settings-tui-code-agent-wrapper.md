---
date: 2026-03-03
title: "v0.8.0: Pull Request Import Pipeline, Settings TUI, and Code Agent Wrapper"
linkTitle: "v0.8.0"
description: "v0.8.0 is a big one — three major features that change how you work with aitasks day-to-day, plus a ton of polish across the board."
author: "aitasks team"
---


v0.8.0 is a big one — three major features that change how you work with aitasks day-to-day, plus a ton of polish across the board.

## Pull Request Import Pipeline

You can now import pull requests directly as aitasks. Run `ait primport` and point it at a PR from GitHub, GitLab, or Bitbucket — it creates a structured task with the PR metadata, contributor info, and a ready-to-go implementation plan. When you're done and archive the task, the original PR gets closed automatically. Contributor attribution flows through to your commits too, so the original author gets credit.

## Settings TUI

No more hand-editing JSON config files. The new `ait settings` command opens a full terminal UI where you can manage profiles, board settings, model configurations, and more — all in one place. It supports layered configuration (project vs. user), export/import, and even shows verification scores for AI models so you know which ones have been tested.

## Code Agent Wrapper

aitasks now works with any AI code agent, not just Claude Code. The new `ait codeagent` command is a universal entry point that routes to whichever agent you've configured — Claude Code, Gemini CLI, Codex CLI, or others. The board and settings TUIs use it automatically, and the new `implemented_with` frontmatter field tracks which agent built each task.

## Board View Modes

The board now has All/Git/Implementing view filters so you can quickly focus on what matters — tasks with uncommitted changes, tasks currently being worked on, or everything at once. The search placeholder even updates to tell you what you're filtering by.

## Refresh Models Skill

Keeping model configs up to date used to be manual. The new `/aitask-refresh-code-models` skill researches the latest AI code agent models via the web and updates your configuration files automatically.

---

---

**Full changelog:** [v0.8.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.8.0)
