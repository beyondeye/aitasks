---
date: 2026-03-15
title: "v0.11.0: Contribution Pipeline, Satisfaction Feedback & Verified Scores, and Explain Context"
linkTitle: "v0.11.0"
description: "v0.11.0 is a big one — it introduces a complete contribution management pipeline, a satisfaction feedback system that tracks how well each AI model performs, and a bunch of board and settings TUI improvements."
author: "aitasks team"
---


v0.11.0 is a big one — it introduces a complete contribution management pipeline, a satisfaction feedback system that tracks how well each AI model performs, and a bunch of board and settings TUI improvements.

## Contribution Pipeline

You can now receive external contributions as GitHub/GitLab/Bitbucket issues and have them automatically checked for overlap with your existing tasks. CI/CD templates handle the automation, and a new contribution review skill walks you through analyzing, merging, and importing contributions. You can even merge multiple related issues into a single task or update an existing task with new contribution content.

## Satisfaction Feedback & Verified Scores

Every task completion can now optionally ask you to rate how well the AI did. These ratings feed into per-model verified scores tracked across time windows — all-time, monthly, and weekly. The settings TUI shows you which models perform best for which operations, and `ait stats` now includes verified model rankings with bar chart visualizations. Over time, this helps you pick the right model for the job.

## Explain Context

The explain feature now gathers historical task context automatically. When you ask for an explanation of a file, it pulls in relevant past tasks and plans to give you richer context about why the code looks the way it does.

## Board TUI Polish

The board got several quality-of-life improvements: a pick command dialog that works cleanly in tmux/terminal multiplexers, keyboard shortcuts on all task detail buttons, and better integration with the pick workflow.

---

---

**Full changelog:** [v0.11.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.11.0)
