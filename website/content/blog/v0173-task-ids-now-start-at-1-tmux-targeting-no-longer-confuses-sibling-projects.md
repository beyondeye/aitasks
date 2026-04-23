---
date: 2026-04-23
title: "v0.17.3: Task IDs now start at 1, Tmux targeting no longer confuses sibling projects, and `ait setup` adds `__pycache__/` to `.gitignore`"
linkTitle: "v0.17.3"
description: "v0.17.3 is a small bug-fix release — three quality-of-life fixes aimed at people running the framework across multiple projects or starting fresh ones."
author: "aitasks team"
---


v0.17.3 is a small bug-fix release — three quality-of-life fixes aimed at people running the framework across multiple projects or starting fresh ones.

## Task IDs now start at 1

New projects used to begin at t10 because of a buffer that made room for future renumbering. The buffer is gone: `--peek` returns 1, the first `ait claim` returns 1, and fresh projects finally look the way most people expect them to.

## Tmux targeting no longer confuses sibling projects

If you had two aitasks sessions with overlapping name prefixes (e.g. `myproject` and `myproject-old`), a handful of tmux calls could silently target the wrong one because tmux falls back to prefix matching. Every session-denominated tmux command now goes through a helper that forces exact-match targeting, so cross-project bleed-through is no longer possible.

## `ait setup` adds `__pycache__/` to `.gitignore`

Python cache directories used to show up in `git status` after your first board or TUI run. `ait setup` now appends a `__pycache__/` rule to your project's `.gitignore` (or creates the file if missing) and folds it into the same approval-gated framework commit as the rest of the scaffolding.

---

---

**Full changelog:** [v0.17.3 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.17.3)
