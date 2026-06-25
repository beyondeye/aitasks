---
date: 2026-06-25
title: "v0.26.1: Spin Up an Agent,  No Task Required, and Upgrades That Survive GitHub Rate Limits"
linkTitle: "v0.26.1"
description: "A small but handy maintenance release that smooths out two rough edges."
author: "aitasks team"
---


A small but handy maintenance release that smooths out two rough edges.

## Spin Up an Agent, No Task Required

Sometimes you just want a code agent in front of you without ceremony. Hit `e` in the TUI switcher and you get a fresh agent window with nothing attached — pick the agent and model right there and start hacking. Perfect for quick experiments and one-off questions.

## Upgrades That Survive GitHub Rate Limits

If GitHub's API throttled you, `ait upgrade` used to give up with a confusing "No releases found." Now it quietly falls back to git tags and tells you the truth about where you stand, so checking for updates keeps working even when the API doesn't.

---

---

**Full changelog:** [v0.26.1 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.26.1)
