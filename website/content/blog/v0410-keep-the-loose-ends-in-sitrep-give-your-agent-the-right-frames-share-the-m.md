---
date: 2026-11-10T18:50:00+02:00
title: "v0.41.0: Keep the loose ends in sitrep, Give your agent the right frames, and Share the monitoring work"
linkTitle: "v0.41.0"
description: "This release gives you a sitrep window for keeping track of finished agents and pending work, expands the recording-analysis tools, and lets your monitors share status collection. It also checks whether a task's assumptions still hold and follows a published release back to the issues it resolves."
author: "aitasks team"
---


This release gives you a sitrep window for keeping track of finished agents and pending work, expands the recording-analysis tools, and lets your monitors share status collection. It also checks whether a task's assumptions still hold and follows a published release back to the issues it resolves.

## Keep the loose ends in sitrep

`ait sitrep` brings pending work, questions, push reminders and trail watches into one window, with a TUI, a Claude Code agent and a minimonitor. You can collect an agent's wrap-up before closing it, inspect the source behind an item, ask the sitrep agent about it, or jump straight to its board or trail card. The local store keeps backups, and captures that need a closer look stay available for review.

## Give your agent the right frames

Recording analysis can now flag freezes, black screens and silence, extract frames at exact times, and work from a folder of still images. You can build contact sheets or open a visual picker to select frames, add notes and mark a region before copying the selection into your agent conversation. Reports call out gaps and uncertain timing so you can see what the recording actually supports.

## Share the monitoring work

Monitor, minimonitor and applink now share a status service for each tmux server and framework version, with reconnects and a local fallback. Minimonitor also keeps unchanged cards mounted to reduce refresh work, and gives you project jumps, phase filters and collapsible key hints. After an update, `ait monitor --restart-server` lets connected clients pick up a fresh service for the installed version.

## Revisit a task's assumptions before starting

Tasks created with file references or verification targets now remember the code revision they started from. When you pick one through the shared workflow, an advisory check shows relevant changes or evidence it could not verify, so you can proceed, replan, postpone or choose another task. A baseline advances only to the revision you reviewed, so changes that arrive while you're deciding remain visible next time.

## Tell issue reporters when the fix ships

The release command now waits for the release and its required assets to be published, then runs `ait release-notify` to add release comments to resolved linked issues. Posting runs on the project's designated machine, and retries check for an existing notification before commenting again. If publication cannot be confirmed, you get a retry command.

---

---

**Full changelog:** [v0.41.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.41.0)
