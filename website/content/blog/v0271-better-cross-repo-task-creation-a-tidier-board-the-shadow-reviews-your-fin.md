---
date: 2026-07-05
title: "v0.27.1: Better cross-repo task creation, A tidier board, and The shadow reviews your finished work"
linkTitle: "v0.27.1"
description: "A small follow-up release that smooths out cross-repo work and sharpens the shadow companion."
author: "aitasks team"
---


A small follow-up release that smooths out cross-repo work and sharpens the shadow companion.

## Better cross-repo task creation

If you work across linked projects, you can now create a child task directly in another repo by pointing `ait create` at both a project and a parent. Project-routed creation also hands back an absolute path to the new task, so downstream tooling always knows exactly where it landed.

## A tidier board

The task board now hides footer actions that don't apply to whatever you've got selected. No more staring at a Commit or Brainstorm button that would just no-op — you only see the moves you can actually make right now.

## The shadow reviews your finished work

The shadow companion already helped interrogate plans before you started; now it can turn the same critical eye on a completed implementation. It reads the task, the plan, and the real diff against your final notes, then pushes back on what it finds — a second opinion right when you're wrapping up.

---

---

**Full changelog:** [v0.27.1 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.27.1)
