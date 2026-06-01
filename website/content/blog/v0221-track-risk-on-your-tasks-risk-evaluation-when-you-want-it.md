---
date: 2026-06-01
title: "v0.22.1: Track risk on your tasks, Risk evaluation, and  when you want it"
linkTitle: "v0.22.1"
description: "A focused follow-up to v0.22.0's cross-repo release, this one is all about risk-awareness in your task workflow."
author: "aitasks team"
---


A focused follow-up to v0.22.0's cross-repo release, this one is all about risk-awareness in your task workflow.

## Track risk on your tasks

Tasks can now carry a `risk` level (high/medium/low) plus a list of `risk_mitigation_tasks`. Set them straight from the CLI with `ait update --risk high`, see risk at a glance in `ait ls`, and edit it right in the board TUI. It's a lightweight way to flag the work that needs extra care before it ships.

## Risk evaluation, when you want it

A new opt-in `risk_evaluation` profile key lets you fold a risk-evaluation step into planning. Flip it on per profile or from the settings TUI — it stays out of your way until you ask for it.

---

---

**Full changelog:** [v0.22.1 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.22.1)
