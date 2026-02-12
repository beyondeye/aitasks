---
priority: medium
effort: low
depends: []
issue_type: documentation
status: Implementing
labels: [aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-12 10:56
updated_at: 2026-02-12 12:42
---

## Context
This is child task 5 of t99 (Update Scripts and Skills Docs). The parent task updates README.md documentation for all aitask scripts and skills. Each child writes a documentation snippet file; a final consolidation task (t99_6) merges them into README.md.

## Goal
Document the architecture overview and library scripts for the Development section of the README.

## Output
Write documentation to `aitasks/t99/docs/05_development.md`. This snippet file will contain new subsections to be inserted into the README's "## Development" section, before the existing "### Modifying scripts" subsection.

## Content to Write

### Architecture Overview
Document the framework's architecture:
- `ait` dispatcher script: routes `ait <subcommand>` to `aiscripts/aitask_<subcommand>.sh`
- Script directory: `aiscripts/` contains all framework scripts
- Library directory: `aiscripts/lib/` contains shared utilities sourced by main scripts
- Skill directory: `.claude/skills/aitask-*` contains Claude Code skill definitions (SKILL.md files)
- Data directories: `aitasks/` (task files), `aiplans/` (plan files), `aitasks/archived/`, `aiplans/archived/`
- Metadata: `aitasks/metadata/` (labels.txt, task_types.txt, emails.txt, profiles/)

### Library Scripts

#### lib/task_utils.sh (`aiscripts/lib/task_utils.sh`)
- Read the full source code
- Document exported functions:
  - `resolve_task_file(task_id)` — Find task file in active or archived directories
  - `resolve_plan_file(task_id)` — Find corresponding plan file (t→p prefix conversion)
  - `extract_issue_url(file_path)` — Extract issue URL from YAML frontmatter
  - `extract_final_implementation_notes(plan_path)` — Extract "Final Implementation Notes" section from plan file
- Document default directory variables: AITASKS_DIR, AIPLANS_DIR, etc.
- Note: double-source guard pattern

#### lib/terminal_compat.sh (`aiscripts/lib/terminal_compat.sh`)
- Read the full source code
- Document exported functions:
  - `die(message)` — Exit with red error message
  - `info(message)` — Blue informational message
  - `success(message)` — Green success message
  - `warn(message)` — Yellow warning message
  - `ait_check_terminal_capable()` — Detect modern terminal support (checks COLORTERM, WT_SESSION, TERM_PROGRAM, TERM, tmux/screen)
  - `ait_is_wsl()` — Detect Windows Subsystem for Linux
  - `ait_warn_if_incapable_terminal()` — Print helpful warnings for legacy terminals
- Document: AIT_SKIP_TERMINAL_CHECK env var, color variables

## Reference Files
- `aiscripts/lib/task_utils.sh` — Library source
- `aiscripts/lib/terminal_compat.sh` — Library source
- `ait` — Dispatcher script (project root)
- Current README.md lines 287-309 — Existing Development section

## Documentation Format
Use `### Architecture` and `### Library Scripts` as main headings, with `#### lib/<filename>` for each library file. Keep technical but accessible — target audience is developers who want to modify or extend the framework.

## Verification
- Architecture overview covers all directories and the dispatcher pattern
- Both library files documented with all exported functions
- Consistent with existing Development section style
