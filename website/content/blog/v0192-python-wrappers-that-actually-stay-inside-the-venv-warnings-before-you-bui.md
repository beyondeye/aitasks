---
date: 2026-04-29
title: "v0.19.2: Python wrappers that actually stay inside the venv, Warnings before you build on stale main, and Source-tree setup gets the starter tmux config too"
linkTitle: "v0.19.2"
description: "v0.19.2 is a reliability-focused release for the everyday setup and release workflows. It fixes a few sharp edges around Python environments, tmux setup, macOS docs, and stale task data during changelog generation."
author: "aitasks team"
---


v0.19.2 is a reliability-focused release for the everyday setup and release workflows. It fixes a few sharp edges around Python environments, tmux setup, macOS docs, and stale task data during changelog generation.

## Python wrappers that actually stay inside the venv

The framework Python launchers now use wrapper scripts instead of symlink chains. That keeps `ait board` and the other Python tools inside the aitasks virtual environment, so packages like Textual, PyYAML, and linkify-it are found reliably after setup.

## Warnings before you build on stale main

After you approve a task plan, aitasks can now check whether `origin/main` moved ahead while your local branch was stale. If the remote commits touch files your plan also targets, you get a stronger warning before implementation starts, which is a much nicer time to stop and re-sync than during final merge.

## Source-tree setup gets the starter tmux config too

If you run `ait setup` directly from a source checkout, the starter tmux configuration prompt now appears correctly. That means developers working from a clone get the same mouse and truecolor-friendly tmux defaults as users running from an installed framework tree.

## macOS terminal guidance is now explicit

There is a new macOS installation page that calls out Apple Terminal's tmux limitations and points users toward truecolor-capable terminal emulators. The main installation and terminal setup pages now link into that guidance, so macOS users see the caveat before wondering why colors or right-click behavior look wrong.

## Changelog generation handles stale task data better

The changelog gather step no longer falls over when a task archive is missing locally. It falls back gracefully, and it now warns when your local task-data branch appears behind the remote so you know to sync before trusting the release notes.

---

---

**Full changelog:** [v0.19.2 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.19.2)
