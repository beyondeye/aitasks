---
date: 2026-05-10
title: "v0.20.2: A redesigned home page, Native installs for every platform, and Code browser History screen no longer crashes"
linkTitle: "v0.20.2"
description: "A polish-focused release. The website got a visual makeover, install instructions now match how you actually want to install software, and a couple of nasty bugs got squashed."
author: "aitasks team"
---


A polish-focused release. The website got a visual makeover, install instructions now match how you actually want to install software, and a couple of nasty bugs got squashed.

## A redesigned home page

The website home page now leads with a split hero — clear pitch on the left, a screenshot of the Board on the right — and gets straight to the point. Below that, a new "Take the tour" mosaic shows off the suite of TUIs (Board, Code Browser, Monitor, Settings, Stats) at a glance, with each tile linking through to the relevant docs. The top feature cards are clickable too, so you can jump straight into the part of the framework that interests you.

## Native installs for every platform

If you're on macOS, you can `brew install beyondeye/aitasks/aitasks`. On Arch, grab it from the AUR. On Debian/Ubuntu, install the `.deb`; on Fedora/Rocky/Alma, install the `.rpm`. The curl-based installer is still there as a fallback (and remains the recommended path on Ubuntu 20.04 / Debian 11 where Python is older), but it's no longer the only option. Each platform has its own install page now, and there's a maintainer-facing reference doc tracking what's stable, what's in progress, and what's next on the packaging roadmap.

## Code browser History screen no longer crashes

If you opened the Code Browser History screen from a cold start, it would crash with a `NoMatches` error before showing anything. Now it doesn't — the screen waits for its panes to mount before trying to populate them.

---

---

**Full changelog:** [v0.20.2 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.20.2)
