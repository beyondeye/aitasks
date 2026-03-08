---
date: 2026-03-08
title: "v0.9.0: Gemini CLI and OpenCode Are First-Class Citizens, Model Discovery and Status Tracking, and Directory Rename: aiscripts to .aitask-scripts"
linkTitle: "v0.9.0"
description: "v0.9.0 is a big one — full Gemini CLI and OpenCode support, a cleaner directory layout, and several workflow fixes that make multi-agent development smoother."
author: "aitasks team"
---


v0.9.0 is a big one — full Gemini CLI and OpenCode support, a cleaner directory layout, and several workflow fixes that make multi-agent development smoother.

## Gemini CLI and OpenCode Are First-Class Citizens

Both Gemini CLI and OpenCode now have complete skill and command wrapper sets, matching what Claude Code and Codex CLI already had. Run `ait setup` in any project and the framework automatically detects which agents you have installed, configuring each one with the right skills, permissions, and instructions. Gemini CLI commands also moved to TOML format with automatic permission policy merging, so setup is truly hands-off.

## Model Discovery and Status Tracking

The new `ait opencode-models` command scans your OpenCode installation to discover available models and catalog them with provider-prefixed identifiers. Models can now carry an active/unavailable status — unavailable ones are dimmed in the settings TUI and excluded from the model picker, so you never accidentally select a model that's gone offline.

## Directory Rename: aiscripts to .aitask-scripts

The framework's internal scripts directory has been renamed from `aiscripts/` to `.aitask-scripts/`, keeping implementation details hidden as a dotfile. All documentation, skills, tests, and configs have been updated to match. If you have custom scripts referencing the old path, they'll need a quick update.

## Workflow Fixes

Parent tasks no longer get stuck in a locked state after creating child tasks. Child task planning checkpoints work correctly now, and agent attribution properly records which code agent did the work instead of defaulting to "claude". Small fixes, but they add up to a noticeably smoother experience when working with task hierarchies.

---

---

**Full changelog:** [v0.9.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.9.0)
