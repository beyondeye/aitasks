---
date: 2026-03-03
title: "v0.8.1: Works Without a Remote, and Smarter Update Checks"
linkTitle: "v0.8.1"
description: "A small but important patch release fixing usability issues when working without a git remote and cleaning up the auto-update experience."
author: "aitasks team"
---


A small but important patch release fixing usability issues when working without a git remote and cleaning up the auto-update experience.

## Works Without a Remote

You can now use `ait create` and task locking in repositories that don't have a remote configured yet. The task ID counter runs locally and seamlessly upgrades to the remote-based atomic counter the moment you add a remote — no manual steps needed.

## Smarter Update Checks

The auto-update notification no longer suggests "upgrading" to an older version. Version comparisons now use proper semver ordering instead of string comparison, so you'll only see update prompts when there's actually a newer release available.

---

---

**Full changelog:** [v0.8.1 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.8.1)
