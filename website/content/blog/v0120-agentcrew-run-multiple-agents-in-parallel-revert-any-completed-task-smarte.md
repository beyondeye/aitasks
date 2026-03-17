---
date: 2026-03-17
title: "v0.12.0: AgentCrew: Run Multiple Agents in Parallel, Revert Any Completed Task, and Smarter Contribution Management"
linkTitle: "v0.12.0"
description: "v0.12.0 brings multi-agent orchestration and the ability to undo any task you've ever completed. Two big additions that change how you work with aitasks."
author: "aitasks team"
---


v0.12.0 brings multi-agent orchestration and the ability to undo any task you've ever completed. Two big additions that change how you work with aitasks.

## AgentCrew: Run Multiple Agents in Parallel

You can now decompose a large task into subtasks and have multiple AI agents work on them simultaneously — each in its own git worktree. `ait crew init` sets up the session, `ait crew addwork` assigns subtasks with dependencies, and `ait crew runner` handles the rest: launching agents in the right order, monitoring heartbeats, and managing concurrency. There's even a full TUI dashboard (`ait crew dashboard`) so you can watch everything happen in real time.

## Revert Any Completed Task

Made a change three weeks ago that turned out to be a bad idea? `/aitask-revert` analyzes the commits, files, and code areas touched by any task, then lets you choose a complete or partial revert. For parent tasks with children, you can even pick which child tasks to keep and which to undo. The skill creates a fully-documented revert task with all the context an agent needs to safely roll back the changes.

## Smarter Contribution Management

The contribution workflow got several quality-of-life improvements: `list-issues` and `check-imported` subcommands let you query what's pending and what's already been pulled in, several crash-causing pipefail bugs are fixed, and the website now properly lists all three contribution skills in one place.

## Board TUI: Delete and Archive Obsolete Tasks

The board now has a unified Delete/Archive flow for child tasks that have become obsolete. It checks dependencies, warns you about tasks that depend on the one you're removing, and marks archived tasks as "superseded" so you know why they were shelved.

---

---

**Full changelog:** [v0.12.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.12.0)
