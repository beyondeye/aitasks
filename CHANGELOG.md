# Changelog

## v0.2.0

### Features

- **Comprehensive README** (t85_10): Added full project documentation covering installation, command reference, Claude Code skills, platform support, and task file format.
- **Terminal compatibility detection** (t89): Added automatic detection of terminal capabilities on Windows/WSL with helpful upgrade suggestions for unsupported terminals.
- **Execution profiles** (t92): Added YAML-based execution profiles for task picking that pre-answer workflow prompts, with built-in "default" and "fast" presets.
- **Centralized task types** (t94): Added "refactor" issue type and moved all task type definitions into a single configuration file for easy customization.
- **Skills as source of truth** (t95): Release workflow now builds distributable skills from `.claude/skills/`, ensuring the repository is the single source of truth.
- **Default Claude Code permissions** (t96): New installations automatically configure Claude Code tool permissions, with interactive merge during `ait setup`.
- **Changelog generation** (t97): Added `aitask-changelog` skill to generate release notes from completed tasks and archived plans, with a shared task utilities library.
- **Board child collapse** (t101): The 'x' shortcut now works when a child card is focused in the task board, collapsing back to the parent task.

### Bug Fixes

- **Board create shortcut** (t93): Fixed the 'n' keyboard shortcut in the task board that failed to launch task creation due to an incorrect script path.
- **Missing documentation type** (t98): Added the "documentation" task type to seed and active task type definitions.

### Documentation

- **CRUD commands and skills** (t99_1): Documented `ait create`, `ait ls`, and `ait update` commands with interactive workflows and batch mode options.
- **Utility commands and skills** (t99_2): Documented `ait setup`, `ait board`, `ait stats`, and `ait clear-old` commands and related skills.
- **Integration commands and changelog skill** (t99_3): Documented `ait issue-import`, `ait issue-update`, `ait changelog` commands and the `/aitask-changelog` skill.
- **Pick skill documentation** (t99_4): Expanded `/aitask-pick` documentation with a full workflow overview and key capability descriptions.
- **Architecture documentation** (t99_5): Added architecture overview, directory layout, and library script reference to the Development section.
- **README consolidation** (t99_6): Merged all documentation snippets into a comprehensive README, growing from 314 to ~720 lines.
- **README corrections** (t103): Added table of contents, fixed section hierarchy, and updated release process documentation.
