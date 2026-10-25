---
date: 2026-10-25T06:14:59+02:00
title: "v0.40.0: Your artifact store stays off your fetches, The syncer asks an agent for help, and Git that never takes your work by surprise"
linkTitle: "v0.40.0"
description: "v0.40.0 keeps your clones lean, gets the syncer to ask for help instead of giving up, and closes a long list of ways git and agent state could quietly go wrong."
author: "aitasks team"
---


v0.40.0 keeps your clones lean, gets the syncer to ask for help instead of giving up, and closes a long list of ways git and agent state could quietly go wrong.

## Your artifact store stays off your fetches

If you keep artifacts on a git branch, every clone used to pull that whole store down with every routine fetch. Now `git fetch`, `ait sync`, `ait setup` and data init leave it alone, so you only download what you actually use. If the exclusion can't be confirmed, `ait sync` holds off rather than fetching the store anyway. Saving the Artifacts tab in `ait settings` re-applies it in the background, so the UI never freezes.

## The syncer asks an agent for help

Pressing `u` in `ait syncer` on your main branch now works even with uncommitted changes, as a safe fast-forward. When it can't finish on its own, because your branch has diverged, the push was rejected, or submodules are involved, you get an "Automatic update needs assistance" dialog. One click launches an agent that already knows the repository, branch, upstream and what went wrong.

## Git that never takes your work by surprise

`ait setup` and `install.sh` now refuse to commit when they can't tell which files you'd already changed, and tell you exactly which paths to commit yourself. Crew commits never commit into, finish or push a half-done merge or rebase. And a tag that happens to share a branch's name no longer turns `main` into `heads/main` and breaks merges, sync and pushes.

## Agents you start by hand come back as themselves

The session hook now records which CLI a hand-started agent is running. Restoring a frozen agent with an unknown or different CLI is refused, so you never get the wrong one, and `ait frozenagent` tells you how to re-pick instead. Codex agents typed at a shell prompt keep their session when frozen, and Codex capture now works on macOS too.

## A clearer picture in trails and minimonitor

The trail entry detail now opens with the task's header, archived tasks included, and `o` shows its description. The trails banner tells you when the trail was generated. In `ait minimonitor`, each workflow phase gets its own symbol and colour, so you can see at a glance where every agent is.

---

---

**Full changelog:** [v0.40.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.40.0)
