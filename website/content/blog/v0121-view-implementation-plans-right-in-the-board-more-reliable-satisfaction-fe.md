---
date: 2026-03-18
title: "v0.12.1: View Implementation Plans Right in the Board, and More Reliable Satisfaction Feedback"
linkTitle: "v0.12.1"
description: "A smaller release this time with two quality-of-life improvements — one for the board UI and one under the hood for agent reliability."
author: "aitasks team"
---


A smaller release this time with two quality-of-life improvements — one for the board UI and one under the hood for agent reliability.

## View Implementation Plans Right in the Board

You can now toggle between viewing a task and its implementation plan directly in the TUI board detail screen. Hit `v` to switch views — the border turns orange so you always know which file you're looking at. Editing is context-aware too, so pressing edit while viewing a plan opens the plan file, not the task.

## More Reliable Satisfaction Feedback

The satisfaction feedback procedure that agents follow after completing tasks has been simplified from a 3-file chain down to a single script call with `--agent` and `--cli-id` flags. This means agents are far less likely to get lost or hallucinate script names when wrapping up tasks in long conversations.

---

---

**Full changelog:** [v0.12.1 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.12.1)
