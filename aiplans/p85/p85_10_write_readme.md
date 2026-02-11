---
Task: t85_10_write_readme.md
Parent Task: aitasks/t85_universal_install.md
Sibling Tasks: aitasks/t85/t85_11_*.md
Archived Sibling Plans: aiplans/archived/p85/p85_*_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: t85_10 - Write README.md

## Context

The `beyondeye/aitasks` repo has an empty `README.md`. This task writes a comprehensive README with installation instructions, command reference, Claude Code integration, and platform support information.

## File to Modify

- `~/Work/aitasks/README.md` (exists, currently empty)

## Implementation

Write README.md with these sections, based on the task spec but corrected against the actual codebase:

### Corrections from task spec

- Task spec lists `ait import` but the actual dispatcher uses **`ait issue-import`** (mapping to `aitask_issue_import.sh`)
- Task spec lists 10 commands; actual dispatcher has **9 subcommands** + help/version
- Current version is **0.1.2** (not 0.1.0)

### Sections to write

1. **Header** - Title, tagline, short description
2. **Quick Install** - curl one-liner, --force upgrade variant
3. **What Gets Installed** - Per-project files + global dependencies
4. **Command Reference** - Table of 9 `ait` subcommands with usage examples
5. **Claude Code Integration** - 5 skills: aitask-pick, aitask-create, aitask-create2, aitask-stats, aitask-cleanold
6. **Platform Support** - Matrix table (Arch, Ubuntu/Debian, Fedora/RHEL, macOS, WSL)
7. **Task File Format** - Example YAML frontmatter + status workflow
8. **Known Issues** - macOS `date -d`, macOS bash 3.2
9. **Development / Contributing** - Brief section on modifying scripts, testing, release process

## Verification

1. README.md renders valid markdown
2. Install URL `https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh` is correct
3. All 9 subcommands documented match the `ait` dispatcher
4. Platform support matrix matches `aitask_setup.sh` detection logic

## Final Implementation Notes
- **Actual work done:** Created comprehensive README.md (145 lines) at `~/Work/aitasks/README.md`. Covers all 9 sections: header/tagline, quick install, what gets installed, command reference (9 subcommands with usage examples), Claude Code integration (5 skills), platform support matrix, task file format with status workflow, known issues, and development/release process.
- **Deviations from plan:** None significant. Used `issue-import` (not `import`) as documented in the plan corrections. Added a License section placeholder at the bottom.
- **Issues encountered:** None.
- **Key decisions:** Used `issue-import` throughout to match the actual `ait` dispatcher. Listed platform support with specific sub-distros (Pop!_OS, Linux Mint, etc.) matching `aitask_setup.sh` detection logic. Included parent-child task hierarchy explanation in the Task File Format section.
- **Notes for sibling tasks:** The README documents the current command set (9 subcommands). If t85_11 (aitask update) adds new `ait` subcommands or changes behavior, the README command reference table should be updated accordingly.

## Post-Implementation (Step 9)

Archive child task and plan, update parent's `children_to_implement`.
