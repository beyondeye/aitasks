---
date: 2026-06-12
title: "v0.24.0: See your proposal while you work, Your tmux sessions stop dying, and Smarter module decomposition"
linkTitle: "v0.24.0"
description: "v0.24.0 is a big one — 49 tasks landed, headlined by a ground-up tmux gateway, a much nicer brainstorm experience, and some quality-of-life wins for keyboard-driven workflows."
author: "aitasks team"
---


v0.24.0 is a big one — 49 tasks landed, headlined by a ground-up tmux gateway, a much nicer brainstorm experience, and some quality-of-life wins for keyboard-driven workflows.

## See your proposal while you work

The brainstorm TUI now shows the relevant proposal side-by-side as you configure your next step — in the explore wizard, in module-decompose, with a section minimap and adjustable split ratios. You can hit `Ctrl+Shift+L` to flip the preview into a syntax-highlighted, line-numbered source view. No more bouncing between screens to remember what you were building on.

## Your tmux sessions stop dying

If you've ever had a Wayland compositor restart take your agent sessions down with it, that's fixed. `ait` now runs its sessions on a dedicated, persistent tmux server placed in a systemd user slice, so they survive session teardowns and stay isolated from your everyday tmux. Under the hood this rides on a brand-new tmux gateway that centralizes every tmux call behind one chokepoint — more robust, more consistent, and guarded against regressions.

## Smarter module decomposition

module_decompose got two upgrades you'll feel immediately. There's a new "Review before apply" gate, so you can preview the proposed breakdown — and re-run it with steering notes — before anything lands. And a new "Agent-proposed" mode infers the module set straight from your plan, so you don't have to name every module up front.

## Find any shortcut, fast

Both the shortcut editor and the Settings Shortcuts tab now have a fuzzy filter box. Start typing and the keybinding you want surfaces instantly. App-scope rebinds also take effect on the live keymap right away now, instead of quietly needing a restart.

## A more capable minimonitor

The minimonitor learned two new tricks: `k` to kill the followed agent and `n` to launch its next sibling task, both right from the panel. The followed agent also gets its own dedicated card, separate from the general list, and the companion pane now holds its width when you resize the terminal.

---

---

**Full changelog:** [v0.24.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.24.0)
