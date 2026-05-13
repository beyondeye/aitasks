---
date: 2026-05-13
title: "v0.20.3: Linux install pages unified, Curl-first install,  with native packages as the alternative, and A page on updating model lists"
linkTitle: "v0.20.3"
description: "v0.20.3 is mostly a documentation release — a big sweep across the website to make it easier to find what you need, install the framework the way you prefer, and discover features that have been there for a while but weren't obvious."
author: "aitasks team"
---


v0.20.3 is mostly a documentation release — a big sweep across the website to make it easier to find what you need, install the framework the way you prefer, and discover features that have been there for a while but weren't obvious.

## Linux install pages unified

The three separate install pages for Arch, Debian, and Fedora are gone. There's now a single **Linux** page with per-distro sections, and the Installation index has been reorganized into clear "Operating systems" and "Setup topics" groups. If you've ever bounced between three near-identical pages trying to find your distro, you'll like this.

## Curl-first install, with native packages as the alternative

The home page and installation pages now lead with the curl one-liner — the fastest path to getting `ait` on your machine. Native packages (Homebrew, AUR, .deb, .rpm) are still documented and recommended where they fit, but as the alternative path rather than the headline. Per-platform "Upgrade" sections now correctly point you to `ait upgrade latest` instead of suggesting (misleading) package-manager upgrades.

## A page on updating model lists

There's a new **Updating Model Lists** subpage under Installation that walks you through refreshing the supported-models list for OpenCode and the other agents, plus how to register a single known model. If you've been waiting for a way to keep your local model list current without spelunking through scripts, that's it.

## Maturity labels and mouse-support, everywhere

The sidebar maturity tag cloud now actually reflects reality: 37 doc pages got their maturity tag added or refreshed, with a new `stable` value introduced. And every TUI doc page now calls out **full mouse support** — click to select, scroll to navigate — as an alternative to keyboard. Both features have been in the framework for a while; now you can find them.

## Home page and About page polish

The home-page tour trimmed from five TUI tiles to the three most-used (Board, Code Browser, Monitor), and the About page got a refresh with a slimmer header, updated stats, and centered author/license blocks. Smaller touch-ups across Getting Started, the TUIs index, and the Overview page round out the docs sweep.

---

---

**Full changelog:** [v0.20.3 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.20.3)
