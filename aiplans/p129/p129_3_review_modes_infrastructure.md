---
Task: t129_3_review_modes_infrastructure.md
Parent Task: aitasks/t129_dynamic_task_skill.md
Sibling Tasks: aitasks/t129/t129_4_*.md, aitasks/t129/t129_5_*.md, aitasks/t129/t129_6_*.md
Archived Sibling Plans: aiplans/archived/p129/p129_1_extract_shared_workflow.md, aiplans/archived/p129/p129_2_create_aitask_explore_skill.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

# Plan: Review Modes Infrastructure (t129_3)

## Context

This task creates the review modes system for the future `/aitask-review` skill (t129_4). Review modes are markdown files with YAML frontmatter that define code review instructions. They are stored as seed templates in `seed/reviewmodes/` and installed to `aitasks/metadata/reviewmodes/` via `install.sh` and `ait setup`.

## Files to Create

### 9 seed review mode files in `seed/reviewmodes/`

Each file follows this format:
```yaml
---
name: Display Name
description: Short description
environment: [lang1]  # optional; omit for universal
---

## Review Instructions
### Section
- Actionable check items...
```

Files (60-120 lines each):
1. `code_conventions.md` — Universal: naming, code organization, formatting consistency, comment hygiene
2. `code_duplication.md` — Universal: exact/near duplicates, structural duplication, magic numbers, extraction opportunities
3. `refactoring.md` — Universal: function complexity, class/module size, coupling, code smells
4. `security.md` — Universal: input validation, injection risks, secrets exposure, auth checks, weak crypto
5. `performance.md` — Universal: unnecessary allocations, N+1 queries, missing caching, algorithmic complexity
6. `error_handling.md` — Universal: missing error checks, poor messages, broad catch blocks, edge cases, resource leaks
7. `python_best_practices.md` — `[python]`: type hints, modern idioms, context managers, pythonic patterns
8. `android_best_practices.md` — `[android, kotlin]`: lifecycle awareness, coroutines, Compose patterns, memory/performance
9. `shell_scripting.md` — `[bash, shell]`: variable quoting, error handling, portability, shellcheck patterns

## Files to Modify

### 1. `install.sh` — Add `install_seed_reviewmodes()`

- [x] Insert function after `install_seed_task_types()` (line 227)
- [x] Add call in `main()` after line 369, before `install_seed_claude_settings`

### 2. `aiscripts/aitask_setup.sh` — Add `setup_review_modes()`

- [x] Insert function after `install_claude_settings()` (line 644)
- [x] Add call in `main()` after `install_claude_settings`, before `check_latest_version`

## Implementation Steps

- [x] Step 1: Create `seed/reviewmodes/` directory and all 9 seed files
- [x] Step 2: Add `install_seed_reviewmodes()` to `install.sh`
- [x] Step 3: Add `setup_review_modes()` to `aiscripts/aitask_setup.sh`
- [x] Step 4: Test by running `ait setup`

## Verification

1. All 9 seed files have valid YAML frontmatter with `name` and `description`
2. `environment` field format correct for language-specific modes
3. `ait setup` shows fzf multi-select with names/descriptions
4. Selected modes copied to `aitasks/metadata/reviewmodes/`
5. Re-running setup skips existing files

## Final Implementation Notes
- **Actual work done:** Created 9 seed review mode files in `seed/reviewmodes/` with detailed, actionable review instructions. Added `install_seed_reviewmodes()` to `install.sh` (+26 lines) following the exact `install_seed_profiles()` pattern. Added `setup_review_modes()` to `aiscripts/aitask_setup.sh` (+156 lines) with fzf multi-select, YAML frontmatter extraction, idempotency, and non-interactive fallback.
- **Deviations from plan:** None — implementation matched the plan exactly.
- **Issues encountered:** The `((installed++))` arithmetic syntax returns exit code 1 when incrementing from 0 (since 0 is falsy), which causes `set -e` to terminate the script. Fixed by using `installed=$((installed + 1))` instead. This is a common bash pitfall.
- **Key decisions:** (1) YAML frontmatter extraction uses a simple while-read loop matching `^name:` and `^description:` — no external YAML parser needed. (2) fzf display includes `[installed]` markers for already-installed modes. (3) Non-interactive mode installs all modes silently, matching the pattern from other setup functions.
- **Notes for sibling tasks:** The review modes are now at `aitasks/metadata/reviewmodes/*.md`. The t129_4 (`aitask-review`) skill should read files from this directory, extract frontmatter for mode selection, and use the markdown body as review instructions for Claude. The frontmatter format is: `name` (string), `description` (string), `environment` (optional list). Universal modes have no `environment` field.
