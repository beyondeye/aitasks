---
date: 2026-06-15
title: "v0.25.0: Task gates that actually drive the workflow, Your phone can now talk to your workspace, and Meet the shadow companion"
linkTitle: "v0.25.0"
description: "v0.25.0 is a big one — it lands a whole task-gating system, opens the door to the mobile companion app, and introduces an advisory \"shadow\" agent that watches over your coding agents."
author: "aitasks team"
---


v0.25.0 is a big one — it lands a whole task-gating system, opens the door to the mobile companion app, and introduces an advisory "shadow" agent that watches over your coding agents.

## Task gates that actually drive the workflow

Tasks can now carry named approval checkpoints — gates like *plan approved*, *build verified*, and *merge approved* — recorded in a durable ledger. Once you turn on `record_gates`, those gates aren't just notes: they decide when dependent tasks unblock, hold a task back from archival until everything's green, and let you pick up an in-flight task right where you left off instead of starting over. It's the connective tissue that makes the workflow resumable and dependency-aware.

## Your phone can now talk to your workspace

The new applink WebSocket listener brings up a paired, TLS-secured connection that the mobile companion app connects to over your LAN. Pairing is QR-bootstrapped, and a dedicated Devices screen lets you see what's connected and revoke any device with a keystroke.

## Meet the shadow companion

`/aitask-shadow` is a new advisory sidekick. It reads the terminal output of an agent you're following and — on demand — explains what's happening, helps you answer a prompt it's stuck on, or critically challenges its plan before you commit to it. Launch one straight from the minimonitor with the `e` key, in its own pane next to the agent it's shadowing. It's read-only and advisory by design: it never touches your work, it just makes you a better-informed driver.

## Smoother upgrades

Upgrading no longer clobbers your local model configuration. New seed models are merged in alongside whatever you've customized, so your own entries survive and the new ones simply get appended.

---

---

**Full changelog:** [v0.25.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.25.0)
