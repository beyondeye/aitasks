---
date: 2026-04-21
title: "v0.17.0: Manual verification workflow, Stats TUI, and Shared section viewer across TUIs"
linkTitle: "v0.17.0"
description: "v0.17.0 is a workflow-and-UX release: a brand-new manual-verification loop, a full interactive stats TUI, section-aware navigation across three TUIs, and a ground-up rewrite of the website and landing page."
author: "aitasks team"
---


v0.17.0 is a workflow-and-UX release: a brand-new manual-verification loop, a full interactive stats TUI, section-aware navigation across three TUIs, and a ground-up rewrite of the website and landing page.

## Manual verification workflow

Some things you just can't test with a bash assertion — you have to load the TUI, click through it, and see whether the row reorders. v0.17.0 gives those checks a proper home: mark a task with `issue_type: manual_verification`, list the items to verify, and `/aitask-pick` walks you through a Pass / Fail / Skip / Defer loop for each one. Failures become linked bug-fix follow-ups automatically, deferred items carry over into a fresh task on archival, and the archival gate makes sure you can't forget half-finished verification runs.

## Stats TUI

`ait stats --plot` is gone. In its place, `ait stats-tui` (or just `t` from the TUI switcher) gives you twelve live stats panes across Overview, Labels, Agents, and Velocity categories — counters, charts, heatmaps, and ranked tables of your most-run operations. An inline layout picker lets you swap between presets or build your own, and layout choices persist to your user-level config without ever touching the shared project config.

## Shared section viewer across TUIs

The structured section markers that shipped in v0.16.1 for brainstorming are now a first-class navigation tool everywhere. Open a plan in the codebrowser, the Brainstorm node-detail modal, or the board's task-detail screen, and you get a minimap of sections you can click to jump to — or press `V` to pop the whole thing fullscreen with keyboard navigation. Long plans stop being a scroll-wall.

## Docs and website overhaul

The landing page, the overview, the README, and a new 12-page Concepts section have all been rewritten around a single framing: aitasks is an agentic IDE that lives in your terminal. On top of that, a systemic consistency sweep caught drift in the TUIs, Skills, Workflows, Concepts, and Commands sections, and every docs page now carries `maturity` and `depth` badges so you can see at a glance whether a feature is experimental or stable and whether a page is main-concept, intermediate, or advanced.

---

---

**Full changelog:** [v0.17.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.17.0)
