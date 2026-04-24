---
date: 2026-04-24
title: "v0.18.0: Your monitor and minimonitor now see every project at once, The TUI switcher teleports across sessions, and `ait install` is now `ait upgrade`"
linkTitle: "v0.18.0"
description: "v0.18.0 is the multi-session release. If you keep two or three aitasks projects open in separate tmux sessions, every TUI now sees them all at once instead of pretending only the current session exists."
author: "aitasks team"
---


v0.18.0 is the multi-session release. If you keep two or three aitasks projects open in separate tmux sessions, every TUI now sees them all at once instead of pretending only the current session exists.

## Your monitor and minimonitor now see every project at once

Both `ait monitor` and `ait minimonitor` now aggregate code-agent panes across every tmux session rooted in an aitasks project. No more switching sessions just to check whether the other project's agent finished — it's all one list, grouped by session under divider rows. Tap `M` in either TUI to flip back to single-session view if you want it.

## The TUI switcher teleports across sessions

The `j` switcher overlay now lists every aitasks session that's running, not just the one you're attached to. Use `←` / `→` to cycle between them, and pressing `Enter` on a TUI row (or hitting any shortcut key) will teleport tmux to that session automatically. Cross-project navigation without leaving the keyboard.

## `ait install` is now `ait upgrade`

Framework updates are now invoked with `ait upgrade` — the name `install` was lying about what it did once your project was already set up. `ait install` still works but prints a deprecation notice. While renaming, we also fixed a packaging bug that was silently omitting shared skills (`task-workflow`, `ait-git`, `user-file-select`) from release tarballs — a long-standing quiet regression now sealed up.

## Per-project tmux launch memory

The agent launch dialog used to remember the last-used tmux session and window globally — so opening project A after using project B gave you project B's session name pre-filled. Now the memory is per-project, and the dialog respects any `default_tmux_window` the caller passes in.

## `gpt-5.5` for codex and opencode

`gpt-5.5` is selectable for the codex agent directly and for the opencode agent via the OpenAI and OpenCode providers.

---

---

**Full changelog:** [v0.18.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.18.0)
