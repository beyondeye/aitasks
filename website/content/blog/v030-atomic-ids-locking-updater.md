---
date: 2026-02-13
title: "v0.3.0: Atomic Task IDs, Task Locking, and Framework Updater"
linkTitle: "v0.3.0"
description: "aitasks v0.3.0 introduces atomic task IDs, concurrent task locking, and a built-in framework updater."
author: "aitasks team"
---

aitasks v0.3.0 is all about making multi-device and multi-developer workflows rock-solid.

## Atomic Task IDs

Task IDs used to be assigned locally, which meant two people creating tasks at the same time could end up with the same ID. Not anymore. IDs now come from a shared atomic counter on a separate git branch, so every task gets a unique number no matter how many PCs are creating tasks against the same repo. Tasks start as local drafts and get their final ID when you commit.

## Concurrent Task Locking

Here's a scenario that used to be annoying: you pick a task on your laptop, and your coworker picks the same task on their desktop. With the new lock mechanism, that can't happen. When you pick a task, it acquires a lock using compare-and-swap semantics on a dedicated `aitask-locks` git branch. If someone else already grabbed it, you'll know immediately.

## Framework Updater

Keeping aitasks up to date just got easier. The new `ait install` command updates the framework to the latest (or a specific) version. It also runs a daily background check and quietly notifies you when a newer release is available — no nagging, just a heads-up next time you run a command.

---

**Full changelog:** [v0.3.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.3.0)
