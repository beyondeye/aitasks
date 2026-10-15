---
date: 2026-10-16
title: "v0.38.0: The test map takes shape, Trails that cross projects, and Prune a brainstorm down to what matters"
linkTitle: "v0.38.0"
description: "v0.38.0 turns the test-map engine into something you can actually run, lets trails reach across projects, and stops a whole family of git operations from touching work that isn't theirs."
author: "aitasks team"
---


v0.38.0 turns the test-map engine into something you can actually run, lets trails reach across projects, and stops a whole family of git operations from touching work that isn't theirs.

## The test map takes shape

`ait testmap` now has real verbs. `scan` and `check` keep the `aitestmap/` registry in step with your tests, `annotate` and `verify` manage `testmap:` covers lines in bash, Python, Go and Kotlin files, and `run` executes test units through the runners you declare, with per-unit timeouts and full process cleanup. The engine also works out what each test depends on, and `annotate --suggest` uses that to propose missing covers lines. A long series of Kotlin and Gradle fixes means the scanners no longer get tripped up by strings, backticks or multi-dollar literals. When a file can't be read safely, the engine now widens test selection instead of quietly hiding dependencies.

## Trails that cross projects

Trail cards now show when a member is blocked by a task in another registered project, with that task's live status. Press `L` in `ait trails` or the board's By-Trail view to list linked trails in other projects and jump straight to one. Its tmux session is started for you if needed. You can also open a specific trail at startup with `ait trails --trail <handle>`.

## Prune a brainstorm down to what matters

In `ait brainstorm`, press `A` → **Prune Dimensions** on a node to create a child that keeps only the dimensions you choose, either the top N of a ranked list or a hand-picked set. No agent runs, the source node stays as it was, and the new node becomes the subgraph's HEAD.

## Git that keeps its hands off your work

Sync, task pulls and crew pulls now ignore git's auto-stash settings, so they no longer stash and re-apply files other sessions are holding. `ait setup` and `ait upgrade` commit only their own changes and leave your uncommitted edits alone. Crew branches are now actually pushed to `origin`, and the crew runner finally sees stop requests sent from another machine. One thing to do: if you use the shared-directory (`dir`) artifact store, run `ait artifact init-store dir` once, because the store now refuses to write anywhere that isn't marked.

## Dialogs and monitors that behave

The agent launch dialog now scrolls on short terminals, so Run and Cancel are always reachable. It also shows the window-name field when you create a new session or pick a blank window. Window names and titles with square brackets show exactly as written instead of crashing the monitor. Elapsed-time badges are compact (`IDLE 5h`, not `IDLE 18734s`).

---

---

**Full changelog:** [v0.38.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.38.0)
