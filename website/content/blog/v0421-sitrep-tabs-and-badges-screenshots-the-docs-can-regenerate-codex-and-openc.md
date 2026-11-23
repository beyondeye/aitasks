---
date: 2026-11-23T12:32:28+02:00
title: "v0.42.1: Sitrep tabs and badges, Screenshots the docs can regenerate, and Codex and OpenCode panes look right"
linkTitle: "v0.42.1"
description: "v0.42.1 is a smaller release, mostly sitrep improvements, screenshot tooling and a few fixes you'll notice quickly."
author: "aitasks team"
---


v0.42.1 is a smaller release, mostly sitrep improvements, screenshot tooling and a few fixes you'll notice quickly.

## Sitrep tabs and badges

The sitrep TUI now splits its list into All, Triage, Tasks, Recovery and Watches tabs, each showing its count, so you can see what kind of work is waiting. Frozen agents in monitor and minimonitor now carry a badge. `drop ok` means you can drop the agent and nothing is lost; `unharvested` means sitrep hasn't read its output yet. You can also open sitrep from the TUI switcher with `Shift+S`.

## Screenshots the docs can regenerate

Every TUI screenshot on the website except the logos is now produced by driving the real TUI on a sample project. A new skill captures a batch of shots, shows you a preview and applies only the batch you approved. When a TUI changes, its screenshots can be regenerated instead of retaken by hand.

## Codex and OpenCode panes look right

Codex and OpenCode panes in monitored sessions sometimes showed black text and backgrounds because they read the wrong colours. They now read your real terminal's colours. Codex question prompts also accept small typos and differences in letter case or spacing. Answers that are ambiguous or hedged are still refused, with suggestions you can type instead.

## GPT-6.2 Sol and Astra

The new GPT-6.2 Sol and Astra models are registered for Codex, and Sol is now the default for shadow and discuss. The OpenCode model list is also refreshed.

---

---

**Full changelog:** [v0.42.1 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.42.1)
