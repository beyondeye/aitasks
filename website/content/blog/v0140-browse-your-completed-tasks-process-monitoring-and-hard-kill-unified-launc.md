---
date: 2026-03-29
title: "v0.14.0: Browse Your Completed Tasks, Process Monitoring and Hard Kill, and Unified Launch Dialog with tmux Support"
linkTitle: "v0.14.0"
description: "v0.14.0 is a big one — headlined by a full history browser, process monitoring, and a unified tmux-aware launch dialog across all TUIs."
author: "aitasks team"
---


v0.14.0 is a big one — headlined by a full history browser, process monitoring, and a unified tmux-aware launch dialog across all TUIs.

## Browse Your Completed Tasks

The codebrowser now has a history screen (press `h`) that lets you browse every archived task. Search and filter by labels, read the full task details and implementation plans, navigate to sibling tasks, and jump straight to the source files that were changed. It's the fastest way to understand why code looks the way it does.

## Process Monitoring and Hard Kill

Both the AgentCrew dashboard and brainstorm TUI now show running agent processes with resource stats. If an agent is stuck, you can pause, kill, or hard-kill it right from the UI — no more hunting for PIDs in a terminal.

## Unified Launch Dialog with tmux Support

Every agent launch action — pick, create, explain, QA — now goes through a shared dialog with Direct and tmux tabs. Configure your preferred tmux session and split settings once in the new Tmux settings tab, and every launch respects them.

## QA Agent from History

Added `qa` as a first-class codeagent operation. Press `a` in the history screen to launch a QA agent for any completed task, or press `H` in the codebrowser to jump directly from an annotated line to its task history.

## Archives Are Now Zstandard

The entire archive system has been migrated from tar.gz to tar.zst. Compression and decompression are noticeably faster, and all existing tar.gz archives are still readable. Run `ait migrate-archives` to convert your repo.

---

---

**Full changelog:** [v0.14.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.14.0)
