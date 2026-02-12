# Changelog

## v0.2.0

### Features

- **Write README** (t85_10): Added comprehensive README covering installation, command reference, Claude Code skill integration, platform support, and task file format documentation.
- **Detect capable terminal on Windows** (t89): Added terminal capability detection for Windows/WSL environments with automatic warnings for unsupported terminals and a shared library that deduplicates color/helper code across scripts.
- **Execution profiles for aitask-pick** (t92): Added YAML-based execution profiles that allow customizing task workflow steps, with built-in `default` and `fast` profiles.
- **Add refactor task type** (t94): Added `refactor` as a new task type and centralized all task type definitions into a single `task_types.txt` file.
- **Skills from .claude/skills as source of truth** (t95): Changed the release workflow to build skills from `.claude/skills/` instead of the top-level `skills/` directory.
- **Default Claude Code permissions** (t96): Added seed permission settings for Claude Code that are interactively merged during `ait setup`.

### Bug Fixes

- **Fix board task creation path** (t93): Fixed incorrect script path reference when creating tasks from the board's `n` shortcut.
