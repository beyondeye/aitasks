---
date: 2026-06-24
title: "v0.26.0: Gate orchestration,  end to end, Your terminals,  on your phone, and Project groups"
linkTitle: "v0.26.0"
description: "v0.26.0 is a big one — it lands a full gate-driven verification system, brings the mobile companion's live-terminal data plane online, and adds project groups plus a bunch of brainstorm TUI polish."
author: "aitasks team"
---


v0.26.0 is a big one — it lands a full gate-driven verification system, brings the mobile companion's live-terminal data plane online, and adds project groups plus a bunch of brainstorm TUI polish.

## Gate orchestration, end to end

Tasks now run their declared verification gates through a real orchestrator that handles retries, parallelism, and even detects when a gate is stuck. You can resume an interrupted task right where it left off with `aitask-resume`, `aitask-pick` surfaces in-flight tasks as resume candidates, and both the board (a new In-Flight view) and the monitor (a compact pass/pending/failed summary) show you gate progress at a glance.

## Your terminals, on your phone

The mobile companion's data plane is here. Applink streams live terminal output to the companion app as compact binary frames — full keyframes, row-level deltas for small changes, and an append fast path that sends only new lines for scrolling logs. A new headless bridge mode (`ait monitor --headless-for-applink`) runs the whole thing without a terminal UI, and a built-in firewall doctor diagnoses and offers to fix LAN issues so pairing just works.

## Project groups

You can now organize your projects into named groups with `ait projects group`. The TUI switcher and stats view gained group-aware navigation so you can cycle by group as well as by session, and there's a dedicated Project Groups tab in settings to assign, rename, and sync them.

## A calmer, sharper brainstorm TUI

The brainstorm TUI got a major layout pass: the list and graph views merged into one Browse tab, operations moved into a unified dialog and a Node Hub overlay, compare became an on-demand overlay, and session and running actions each got their own home. You can now restart or retry a whole operation group from the Running tab, and marked nodes show a clean ☑/☐ checkbox everywhere.

## Hardened mobile security

Applink got a thorough security pass — a TLS 1.2+ floor, per-IP connection and rate caps, input validation on every command verb, secure on-disk permissions, and audit logging — so the convenience of phone access doesn't come at the cost of safety.

---

---

**Full changelog:** [v0.26.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.26.0)
