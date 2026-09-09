---
date: 2026-09-09
title: "v0.35.0: Freeze an agent and come back to it, Send a note to a task, and Let the backlog rank itself"
linkTitle: "v0.35.0"
description: "v0.35.0 is a big one. You can now park a running agent and pick it back up later, tell a task something it needs to know while nobody is working on it, and let the framework rank your backlog for you."
author: "aitasks team"
---


v0.35.0 is a big one. You can now park a running agent and pick it back up later, tell a task something it needs to know while nobody is working on it, and let the framework rank your backlog for you.

## Freeze an agent and come back to it

Sometimes you need a pane back but you do not want to throw away what an agent was doing. `ait frozen` freezes a running code agent in place, leaving a stand-in that holds its slot, and later you restore it into a live pane — or repick its task fresh if the world moved on. There is a viewer TUI for browsing everything you have frozen, reading its captured output, and bringing it back.

## Send a note to a task

New `/aitask-note` skill: when you learn something a task depends on — a stale assumption in its body, a wider blast radius than it thinks, a decision that changes its approach — you can send it there durably, even when nobody is working on it. The note shows up as unread when someone picks the task, and if an agent is holding the task live on your machine right now, it gets delivered straight to them.

## Let the backlog rank itself

`/aitask-backlog-roadmap` looks at your background work, weighs it against what is already in flight, and produces a conflict-aware implementation trail as a durable artifact you can refresh later. It is an advisory estimate of what is actually worth picking up next, not a decree.

## Concurrent sessions stop stepping on each other

If you run several agents against one tree, this release is mostly about that. Board operations, settings saves, cross-repo config pushes and dozens of commit sites throughout the framework now name their own paths instead of committing whatever happened to be staged. A wedged task-data worktree refuses writes rather than corrupting them, a conflicted rebase aborts cleanly, and `ait create` no longer burns a task id when its commit fails.

## macOS actually passes now

The macOS-only test failures are fixed, along with a BSD `mktemp` defect that turned up across 32 call sites, and the BSD-vs-GNU splits in `stat`, `readlink` and `mkdir -p` are documented for the next person who hits one.

---

---

**Full changelog:** [v0.35.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.35.0)
