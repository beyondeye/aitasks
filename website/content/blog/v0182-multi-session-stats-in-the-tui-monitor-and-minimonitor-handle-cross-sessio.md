---
date: 2026-04-26
title: "v0.18.2: Multi-session stats in the TUI, Monitor and minimonitor handle cross-session agents correctly, and Agent crews that recover instead of erroring out"
linkTitle: "v0.18.2"
description: "v0.18.2 is mostly a polish release for multi-session — stats picks up every session you've got, and the monitor finally stops mixing up which project a foreign-session agent belongs to. Agent crews and brainstorm sessions also got a lot more forgiving when something flakes."
author: "aitasks team"
---


v0.18.2 is mostly a polish release for multi-session — stats picks up every session you've got, and the monitor finally stops mixing up which project a foreign-session agent belongs to. Agent crews and brainstorm sessions also got a lot more forgiving when something flakes.

## Multi-session stats in the TUI

The `ait stats` TUI now picks up every aitasks session on your machine. A new Session panel on the left lets you cycle between them with `←` / `→` or click to jump to one. There's also a new `sessions` preset with a grouped bar chart comparing today / 7-day / 30-day activity across all of them — useful for getting a single read on where your time has been going.

## Monitor and minimonitor handle cross-session agents correctly

Previously the monitor and minimonitor TUIs would resolve task data, log paths, and "next sibling" picks against the local project even when the focused agent was running in a different aitasks session. They now route everything through the foreign session's project root, so logs open the right file and pick-next launches land in the right repo.

## Agent crews that recover instead of erroring out

Agent crews now have a new MissedHeartbeat state for transient stalls. If an agent skips a heartbeat, it goes to MissedHeartbeat first instead of straight to Error, and it'll quietly recover back to Running if the heartbeat resumes within the grace window. Errored agents can also be moved to Completed without a force override, so cleaning up after a flaky run no longer means digging into status files.

## Brainstorm sessions that heal themselves

If the initializer apply fails partway through (em-dashes in YAML were a recurring culprit), the brainstorm TUI now shows a banner instead of getting stuck, retries automatically every 30 seconds and on each reopen, and exposes `ctrl+r` for an immediate manual retry. Behind the scenes the YAML loader auto-quotes problematic scalars, and a new `ait brainstorm apply-initializer <id>` CLI gives you a clean way to recover any session that's still stuck from before this release.

---

---

**Full changelog:** [v0.18.2 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.18.2)
