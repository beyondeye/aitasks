---
date: 2026-02-25
title: "v0.7.0: Run Tasks from Anywhere, Claude Code Web Support, and Full macOS Compatibility"
linkTitle: "v0.7.0"
description: "v0.7.0 is a big one — this release makes aitasks work everywhere: on macOS, on remote servers, and even in Claude Code Web."
author: "aitasks team"
---


v0.7.0 is a big one — this release makes aitasks work everywhere: on macOS, on remote servers, and even in Claude Code Web.

## Run Tasks from Anywhere

The new `/aitask-pickrem` skill lets you run task implementation on remote servers, CI pipelines, or SSH sessions — completely hands-free. No interactive prompts, no fzf, just autonomous execution. Pair it with the new `ait sync` command to keep your task files in sync across machines, and the auto-merge engine handles any YAML frontmatter conflicts automatically.

## Claude Code Web Support

You can now implement tasks directly in Claude Code Web with `/aitask-pickweb`. It stores task data locally to avoid branch conflicts, and when you're done, `/aitask-web-merge` brings everything back to main. The board TUI gained lock/unlock controls so you can reserve tasks before starting a Web session, preventing anyone else from grabbing them.

## Full macOS Compatibility

macOS is now fully supported. We fixed every GNU-specific `sed`, `date`, `grep`, and `mktemp` usage across all scripts and tests. A new `sed_inplace()` helper and portable date wrapper ensure everything works with macOS's BSD tools out of the box. `ait setup` now validates your tool versions too.

## Task Data Branch

Task and plan files can now live on a dedicated git branch, so your task metadata doesn't clutter feature branch diffs. The new `./ait git` command routes task file operations through this branch transparently. All scripts, the board TUI, and skills have been updated to use it.

## Smart Sync with Auto-Merge

The new `ait sync` command handles pulling and pushing task data, and when conflicts arise in YAML frontmatter, the auto-merge engine resolves them intelligently using field-specific rules. Press `S` in the board TUI to sync without leaving the interface.

---

---

**Full changelog:** [v0.7.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.7.0)
