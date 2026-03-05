---
date: 2026-03-05
title: "v0.8.2: Codex CLI Support, Unified Install Pipeline, and macOS Compatibility"
linkTitle: "v0.8.2"
description: "v0.8.2 brings Codex CLI into the aitasks family — if you use OpenAI's Codex CLI, your aitask skills now work there too."
author: "aitasks team"
---


v0.8.2 brings Codex CLI into the aitasks family — if you use OpenAI's Codex CLI, your aitask skills now work there too.

## Codex CLI Support

All 17 aitask skills now have Codex CLI wrappers. Run them with `$skill-name` syntax just like you would in Claude Code. A shared tool mapping file handles the translation between Claude Code and Codex CLI conventions, so skills behave consistently across both agents.

## Unified Install Pipeline

Running `ait setup` now automatically detects which AI code agents you have installed and configures each one. Codex CLI gets its skills, config, and instructions assembled from a layered seed system. A new marker-based system (`>>>aitasks`/`<<<aitasks`) makes instruction injection idempotent — your existing config files stay clean, and aitasks content is neatly delimited and replaceable.

## macOS Compatibility

A sweep of all 33 bash tests on macOS caught and fixed a real symlink path bug in `ait setup` plus several stale test assertions. If you ran into issues with `ait setup` in macOS temp directories, this release fixes it.

---

---

**Full changelog:** [v0.8.2 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.8.2)
