---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Implementing
labels: [aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-12 10:56
updated_at: 2026-02-12 11:36
---

## Context
This is child task 2 of t99 (Update Scripts and Skills Docs). The parent task updates README.md documentation for all aitask scripts and skills. Each child writes a documentation snippet file; a final consolidation task (t99_6) merges them into README.md.

## Goal
Document the utility commands (board, stats, clear-old, setup) and utility-related skills (/aitask-stats, /aitask-cleanold).

## Output
Write documentation to `aitasks/t99/docs/02_utility_commands.md`. This snippet file will contain markdown sections ready to be inserted into README.md by the consolidation task.

## Scripts to Review and Document

### ait board (`aiscripts/aitask_board.sh`)
- Read the full source code (small script, ~37 lines)
- Document: Python TUI launcher (Textual-based), venv detection at `~/.aitask/venv/bin/python`, fallback to system python3, required packages (textual, pyyaml, linkify-it-py), terminal capability check, argument forwarding
- No interactive mode per se — it launches the TUI board application

### ait stats (`aiscripts/aitask_stats.sh`)
- Read the full source code
- Document all options: -d/--days N, -w/--week-start DAY, -v/--verbose, --csv [FILE]
- Document the 7 statistic types: summary (7/30/all-time), daily breakdown, day-of-week averages, label weekly trends, task type weekly trends, label+issue type trends, label day-of-week distribution
- Document CSV export format: date, day_of_week, week_offset, task_id, labels, issue_type, task_type
- No interactive mode

### ait clear-old (`aiscripts/aitask_clear_old.sh`)
- Read the full source code
- Document options: --dry-run/-n, --no-commit, --verbose/-v
- Document archive behavior: scans aitasks/archived/ and aiplans/archived/, keeps most recent parent file uncompressed (for task numbering), archives older files to old.tar.gz, handles child subdirectories, auto git commit
- No interactive mode

### ait setup (`aiscripts/aitask_setup.sh`)
- Read the full source code
- Document: OS detection (macOS, Arch, Debian, Fedora, WSL), per-platform package installation, Python venv creation at ~/.aitask/venv/, global shim at ~/.local/bin/ait, Claude Code permissions merge from seed file, version check
- This has a guided interactive flow — document what the user is asked/shown at each step

## Skills to Review and Document

### /aitask-stats (`.claude/skills/aitask-stats/SKILL.md`)
- Read the skill file
- This skill is MISSING from the README — write new documentation
- Document what the skill adds beyond the bare `ait stats` command

### /aitask-cleanold (`.claude/skills/aitask-cleanold/SKILL.md`)
- Read the skill file
- Verify the existing README documentation (lines 159-174) is still accurate
- Write updated docs if needed

## Documentation Format
Follow the snippet format from the plan: `### ait <command>` headings for commands, `### /aitask-<name>` headings for skills. Include options tables, key features, usage examples.

## Verification
- Snippet file contains sections for all 4 commands and 2 skills
- All options are documented with descriptions
- Format is consistent and ready for README insertion
