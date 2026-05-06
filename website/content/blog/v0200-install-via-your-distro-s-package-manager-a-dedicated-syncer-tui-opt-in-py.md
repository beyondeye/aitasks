---
date: 2026-05-06
title: "v0.20.0: Install via your distro's package manager, A dedicated syncer TUI, and Opt-in PyPy fast-path"
linkTitle: "v0.20.0"
description: "v0.20.0 is a big one — a brand new sync TUI, package-manager installs across four ecosystems, an opt-in PyPy fast-path that makes the long-running TUIs noticeably snappier, and a wave of polish across brainstorm."
author: "aitasks team"
---


v0.20.0 is a big one — a brand new sync TUI, package-manager installs across four ecosystems, an opt-in PyPy fast-path that makes the long-running TUIs noticeably snappier, and a wave of polish across brainstorm.

## Install via your distro's package manager

Aitasks now ships as proper packages on Homebrew, the AUR, Debian/Ubuntu (`.deb`), and Fedora/RHEL (`.rpm`). Each tag triggers a CI workflow that builds, tests, and publishes the appropriate format, so `brew install aitasks`, `yay -S aitasks`, `apt install ./aitasks_*.deb`, and `dnf install ./aitasks-*.rpm` all just work. The `ait` shim itself was extracted to a single canonical file so every package consumes the same binary.

## A dedicated syncer TUI

Run `ait syncer` and you get a live two-row view of your `main` and `aitask-data` branches: ahead/behind counts, recent commits, and the changed paths. One-key actions sync `aitask-data`, pull `main`, and push `main`; if anything fails, an in-TUI escape hatch lets you dispatch a code agent to resolve the conflict. The syncer is wired into the TUI switcher (`y`), surfaces a desync line in monitor/minimonitor, and can auto-launch via `ait ide` if you opt in.

## Opt-in PyPy fast-path

Run `ait setup --with-pypy` once and six long-running TUIs — board, codebrowser, settings, stats, brainstorm, and syncer — auto-route through PyPy 3.11. Startup and refresh are dramatically faster, with no behavior change for non-PyPy users. The `AIT_USE_PYPY` env var lets you override per invocation. Monitor and minimonitor stay on CPython for now (their bottleneck is fork+exec, not Python execution), and the stats TUI stays on CPython because of its `plotext` dependency.

## Fork-free monitor hot path

`ait monitor` and `ait minimonitor` now talk to tmux through a persistent `tmux -C` control client instead of forking a subprocess on every refresh. On a 5-pane benchmark, that's a ~10× speedup and 100% fork elimination. The control channel is supervised: when it fails, the monitor falls back to subprocess and reconnects with bounded backoff, with a status badge in the session bar showing the current state.

## Smarter agent picker and live usage stats

The agent/model picker dialog learned new tricks: cycle through Top, All, and per-agent modes with Shift+Left/Right; rank "Top by recent" using a rolling window so old high-score incumbents stop dominating; and a brand-new "Top by usage" mode shows what you actually use. Powering this is a new live usage hook that records every task completion independently of satisfaction feedback, with a `prev_month` bucket so recent-window views have data immediately on month rollover.

---

---

**Full changelog:** [v0.20.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.20.0)
