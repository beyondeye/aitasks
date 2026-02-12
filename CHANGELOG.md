# Changelog

## v0.2.0

### Features

- **Comprehensive README** (t85_10): Added full project documentation covering installation, command reference, Claude Code skill integration, platform support, and task file format
- **Terminal compatibility detection** (t89): Added automatic detection of terminal capabilities on Windows/WSL with helpful upgrade suggestions for unsupported terminals
- **Execution profiles** (t92): Added YAML-based execution profiles for aitask-pick that pre-answer workflow prompts, with built-in "default" and "fast" presets
- **Centralized task types** (t94): Added "refactor" issue type and centralized all task type definitions into a single configuration file
- **Skills as source of truth** (t95): Changed release workflow to build distributable skills from the authoritative `.claude/skills/` directory
- **Default Claude Code permissions** (t96): Added seed permissions file so new installations automatically get the correct Claude Code tool permissions
- **Changelog generation** (t97): Added `aitask-changelog` skill to automatically generate release notes from completed tasks and archived plans, with integration into the release workflow. Extracted common task/plan resolution functions into a shared utilities library

### Bug Fixes

- **Board create shortcut** (t93): Fixed the 'n' keyboard shortcut in the task board that failed to launch task creation due to an incorrect script path
