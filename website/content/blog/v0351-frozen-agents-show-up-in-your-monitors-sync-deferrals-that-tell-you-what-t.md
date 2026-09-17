---
date: 2026-09-17
title: "v0.35.1: Frozen agents show up in your monitors, Sync deferrals that tell you what to do, and Git safety: fewer silent surprises"
linkTitle: "v0.35.1"
description: "v0.35.1 finishes what v0.35.0 started with frozen agents, and makes syncing and restores a lot harder to break."
author: "aitasks team"
---


v0.35.1 finishes what v0.35.0 started with frozen agents, and makes syncing and restores a lot harder to break.

## Frozen agents show up in your monitors

Frozen agents now appear in monitor and minimonitor as their own rows, with counters and a shared filter. You can restore or drop them right there. Restore also got sturdier: it works after you close the agent's window, restart tmux, or have no session open for the project, and with several Codex agents in one repo, each one comes back to its own conversation.

## Sync deferrals that tell you what to do

When a sync is held back because another session has a file, `ait syncer` now names the file, the task holding it, and that agent's tmux pane. It also says whether that agent is waiting on a question, so you know where to go. And when a rebase is blocked on a diverged data branch, sync now tries a guarded merge that only goes ahead when it is clearly safe, instead of just giving up.

## Git safety: fewer silent surprises

We went through the git checks that could treat an error as "all clear" and made them stop instead. The worst one could quietly drop a commit during a pull. `ait create` no longer commits a task file with no id when claiming the id fails. The remaining plain `git commit` instructions on `main` now name their own files, so one session can't commit what another has staged.

## Shadow shortcodes

The shadow companion now gives each capability a short `>` code and lists them all when it greets you. `>t` gives you the current task in plain words, which helps when you've just joined an agent's work and want the gist.

## Your CHANGELOG.md is safe on upgrade

`ait upgrade` used to overwrite your project's own root `CHANGELOG.md` with the framework's. That's fixed: upgrades and fresh installs now leave your changelog alone.

---

---

**Full changelog:** [v0.35.1 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.35.1)
