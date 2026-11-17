---
date: 2026-11-17T23:08:25+02:00
title: "v0.42.0: Pick up the work a crash left behind, Answer Codex questions when you're ready, and Keep model statistics out of task-data traffic"
linkTitle: "v0.42.0"
description: "v0.42.0 helps you recover interrupted agent work, keeps Codex workflow questions available until you answer, and separates model statistics from task-data updates. It also adds tools for capturing documentation screenshots from real TUIs."
author: "aitasks team"
---


v0.42.0 helps you recover interrupted agent work, keeps Codex workflow questions available until you answer, and separates model statistics from task-data updates. It also adds tools for capturing documentation screenshots from real TUIs.

## Pick up the work a crash left behind

Sitrep now collects crashed and orphaned work into recovery items, with evidence about the task, its plan and its remaining changes. You can inspect what happened, ask the sitrep agent about crashed work with `w`, and pick a crashed or orphaned task to continue. Uncertain locks stay visible with guidance to check their owner before releasing them.

## Answer Codex questions when you're ready

You can enable a dedicated question server during setup to answer Codex workflow questions in forms, or at the ordinary prompt if a form times out. Unanswered questions survive restarts, and approvals stay tied to the content or revision you reviewed. Setup explains the choice, remembers it, and gives you flags to enable or remove the server.

## Keep model statistics out of task-data traffic

Usage counts and satisfaction ratings now update their own shared store, so recording a run no longer needs to synchronize your task files. Setup and upgrades move older counters across with resumable checks. Your rankings, model picker and settings use the shared counters, and shown scores follow your recorded ratings when available.

## Capture the screen you want to explain

The new documentation capture tools launch real TUIs with sample data in an isolated tmux session, then save a recipe you can replay later. You can crop a card, add labels and callouts, or capture a whole window with several panes. SVG output and PNG previews let you inspect the result, with initial scenes for the board and monitor family included.

---

---

**Full changelog:** [v0.42.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.42.0)
