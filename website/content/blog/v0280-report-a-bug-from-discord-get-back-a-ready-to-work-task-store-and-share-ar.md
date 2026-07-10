---
date: 2026-07-10
title: "v0.28.0: Report a bug from Discord,  get back a ready-to-work task, Store and share artifacts with your team, Slack, and  not just Discord"
linkTitle: "v0.28.0"
description: "v0.28.0 is a big one — a whole new way to file bugs from chat, team-wide artifact sharing, Slack support, and zero-config remote access for the mobile companion."
author: "aitasks team"
---


v0.28.0 is a big one — a whole new way to file bugs from chat, team-wide artifact sharing, Slack support, and zero-config remote access for the mobile companion.

## Report a bug from Discord, get back a ready-to-work task

Drop a bug report in Discord and a sandboxed agent takes it from there: it explores your codebase, asks you clarifying questions right in the thread, and files a structured task when it has what it needs. The agent runs in an isolated Docker container, and you watch the whole thing from the new `ait chatlink` status screen.

## Store and share artifacts with your team

The new `ait artifact` CLI gives you first-class artifacts with stable handles, full version history, and pluggable storage backends. Point it at a shared directory and your whole team resolves the same handles — no more passing build outputs around by hand.

## Slack, not just Discord

Chat-driven workflows now run on Slack too, via a new Socket Mode adapter. Everything you could do from Discord now works from your Slack workspace.

## Reach your workspace from anywhere

`ait applink --auto-tunnel` spins up a Cloudflare Quick Tunnel for you automatically, so your phone can reach the workspace from outside the LAN with zero manual tunnel wrangling. And if you're on a mesh VPN or an unusual network, the new `--advertise-*` flags let you tell the pairing QR exactly what endpoint to hand out.

---

---

**Full changelog:** [v0.28.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.28.0)
