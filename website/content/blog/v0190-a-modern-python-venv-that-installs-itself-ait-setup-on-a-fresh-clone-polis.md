---
date: 2026-04-28
title: "v0.19.0: A modern Python venv that installs itself, `ait setup` on a fresh clone,  polished end-to-end, Brainstorm: fewer crashes, and  more visibility"
linkTitle: "v0.19.0"
description: "v0.19.0 is mostly an infrastructure release — the Python venv story, `ait setup` on a fresh clone, and brainstorm stability all got a lot of attention. There's also a new audit-wrappers skill that closes a recurring drift class."
author: "aitasks team"
---


v0.19.0 is mostly an infrastructure release — the Python venv story, `ait setup` on a fresh clone, and brainstorm stability all got a lot of attention. There's also a new audit-wrappers skill that closes a recurring drift class.

## A modern Python venv that installs itself

`ait setup` now requires Python ≥3.11 and will auto-install a modern interpreter for you when the system Python is too old — Homebrew on macOS, uv-managed builds on Linux. Once installed, all aitasks scripts resolve through a single helper (`lib/python_resolve.sh`) and a scoped `~/.aitask/bin` symlink, so the framework picks up the right interpreter without ever touching your shell rc files. If you've been getting "Python too old" failures on Debian or older macOS, this just works now.

## `ait setup` on a fresh clone, polished end-to-end

A whole cluster of paper-cuts in the `ait setup` flow are gone. The task-ID counter now scans the data branch on a fresh clone, so you no longer get duplicate IDs like `t1` colliding with existing tasks. `.gitignore` edits are auto-committed instead of being left dirty in your working tree, and the trailing-slash entries (`aitasks/`, `aiplans/`) that didn't actually match the data-branch symlinks are migrated to the bare form (`aitasks`, `aiplans`) so `git status` stays clean. There's also a new opt-in starter `~/.tmux.conf` for first-time tmux users, and the docs now explain the post-clone setup step explicitly.

## Brainstorm: fewer crashes, more visibility

The brainstorm TUI got a stack of fixes. Agents launched into tmux now record the actual agent PID so the Status tab stops claiming "PID dead" for a running agent. Initializer/explorer/synthesizer outputs missing `created_at` are auto-filled instead of crashing with a parse error. The agent-command screen no longer crashes on Textual ≥8.0 when you open the session/window selector, and the section minimap inside the node-detail modal is crash-free with the section jump landing on the correct row. As a bonus, each running agent now shows a 10-character progress bar in the Status tab.

## Cross-PC lock warnings

If you `ait pick` a task that's already locked by *you* on a different machine, the workflow now prompts you instead of silently re-claiming. This was the most common way to lose half-committed work when bouncing between a laptop and a workstation — now you see a "this is locked on `<other-host>`" warning and can choose whether to take it over or pick a different task.

## New skill: aitask-audit-wrappers

Adding a new skill or helper script used to mean hand-editing four parallel wrapper trees (claude/gemini/codex/opencode) and five permission-touchpoint files. The new `aitask-audit-wrappers` skill audits and ports both layers automatically — wrapper drift across agent trees and helper-script whitelist gaps across runtime/seed configs are now a one-command fix.

---

---

**Full changelog:** [v0.19.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.19.0)
