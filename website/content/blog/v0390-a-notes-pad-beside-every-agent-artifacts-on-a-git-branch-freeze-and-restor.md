---
date: 2026-10-21T12:51:53+03:00
title: "v0.39.0: A notes pad beside every agent, Artifacts on a git branch, and Freeze and restore you can trust"
linkTitle: "v0.39.0"
description: "v0.39.0 gives every task a notes pad, adds a git-branch home for your artifacts, and makes freezing and restoring agents much harder to get wrong."
author: "aitasks team"
---


v0.39.0 gives every task a notes pad, adds a git-branch home for your artifacts, and makes freezing and restoring agents much harder to get wrong.

## A notes pad beside every agent

Press `o` in `ait minimonitor` to open a scratchpad pane bound to the agent you're following. It's a small notes editor tied to that task. It autosaves shortly after you stop typing, saves when you quit or close the pane, and closes when its agent does. Notes stay out of git and are cleaned up automatically when the task is archived. You can also open one directly with `ait scratchpad`.

## Artifacts on a git branch

`ait artifact` has a new `gitbranch` backend that keeps artifact blobs on a dedicated branch of your repository and shares them through `origin`. You don't need a shared drive or an extra service. Pick it as the default in the new **Artifacts** tab of `ait settings` (`k`). If you ever rename the branch, `ait artifact gitbranch-migrate` moves the store over and can resume if it's interrupted.

## Freeze and restore you can trust

A long run of fixes makes frozen agents behave. `ait ide` now brings back frozen agents from every registered project, each with its minimonitor. Restored agents can be frozen again. Kills and restarts re-check whether an agent got frozen while a dialog was open, so its capture is never lost. Restoring and re-picking now happen only in `ait frozenagent`, where re-pick is now on `P`. Codex restores are confirmed from the session they open, so they finish quickly without sending a prompt.

## Git that can't hang

Crew fetches and pushes, crew branch deletion, `ait sync`, the remote drift check and release lookups now all have a timeout and can't stop on a password or SSH prompt. `./ait git pull` and `./ait git push` now handle the git options you pass in front of them correctly, abort their own stopped merges, and report a broken remote config instead of quietly acting as if there were no remote.

## The test map keeps growing

`ait testmap` gains variant axes for tests that run once per platform or flavor, areas and kinds for scoping tests, provenance tracking for machine-written annotations, and a cost ledger. With the ledger, `ait testmap costs` reports how long your tests take and suggests a gate timeout.

---

---

**Full changelog:** [v0.39.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.39.0)
