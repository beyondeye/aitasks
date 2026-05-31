---
date: 2026-05-31
title: "v0.22.0: Tasks that span multiple repos, Make every shortcut your own, and Manual verification that runs itself"
linkTitle: "v0.22.0"
description: "v0.22.0 is a big one — cross-repo dependencies, fully customizable keyboard shortcuts, autonomous manual verification, and Opus 4.8 as the new default."
author: "aitasks team"
---


v0.22.0 is a big one — cross-repo dependencies, fully customizable keyboard shortcuts, autonomous manual verification, and Opus 4.8 as the new default.

## Tasks that span multiple repos

You can now wire up dependencies *between* aitasks projects, not just within one. A task in your frontend repo can declare it's blocked by a task in your backend repo using the new `xdeps` fields, and the board, planner, and blocking logic all understand it. Projects are referenced by a logical name you register once — no fragile `../` paths — so cross-repo planning, task creation, and context lookups just work.

## Make every shortcut your own

The TUIs now have a full customizable-shortcuts layer. Don't like a keybinding? Open the in-TUI shortcut editor, remap it, and your override sticks across every TUI. There's also a dedicated Shortcuts tab in the settings TUI for managing them all in one place.

## Manual verification that runs itself

Manual-verification tasks no longer always need you in the loop. Turn on autonomous mode and the agent can run the checks for you — either improvising the verification on the spot or following a pre-built plan you approve. It's configurable per profile, so you decide how hands-off each workflow should be.

## Opus 4.8 is the new default

Claude Opus 4.8 is now registered and promoted to the default model, so new sessions pick it up automatically.

---

---

**Full changelog:** [v0.22.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.22.0)
