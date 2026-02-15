---
priority: medium
effort: medium
depends: [129_1]
issue_type: feature
status: Ready
labels: [claudeskills]
created_at: 2026-02-15 17:15
updated_at: 2026-02-15 17:15
---

## Context
This task creates the review modes infrastructure for the `/aitask-review` skill. Review modes are configurable markdown files with YAML frontmatter that define code review instructions. They are stored in `aitasks/metadata/reviewmodes/` and seed templates are provided in `seed/reviewmodes/` for installation via `ait setup`.

This is part of the dynamic task skill initiative (t129). The review modes system provides the foundation that the `/aitask-review` skill (t129_4) will consume.

## Key Files to Create/Modify

1. **Create** `seed/reviewmodes/` directory with 9 template review mode files
2. **Create** `aitasks/metadata/reviewmodes/` directory (populated during `ait setup`)
3. **Modify** `aiscripts/aitask_setup.sh` — add review mode selection/installation step

## Reference Files for Patterns

- `seed/profiles/` — existing seed template pattern (profiles copied to metadata during setup)
- `seed/task_types.txt` — another seed file pattern
- `aiscripts/aitask_setup.sh` — the setup script to modify (add a new step after existing ones)
- `aitasks/metadata/profiles/*.yaml` — YAML frontmatter pattern for metadata files

## Implementation Plan

### Step 1: Define the review mode file format

Each review mode is a markdown file with YAML frontmatter:
```yaml
---
name: Code Conventions
description: Check naming, formatting, and pattern consistency
environment: [python]  # optional; list of environments this mode targets
---

## Review Instructions

### Naming Conventions
- Check that function/method names use snake_case
...
```

Frontmatter fields:
- `name` (required): Display name shown during mode selection
- `description` (required): Short description of what this mode reviews
- `environment` (optional): List of environments/languages (e.g., `[python]`, `[android, kotlin]`). When omitted, the mode is universal

### Step 2: Create seed review mode templates in `seed/reviewmodes/`

Create 9 files:

1. `code_conventions.md` — Universal: naming patterns, formatting consistency, code organization
2. `code_duplication.md` — Universal: DRY violations, copy-paste code, repeated patterns
3. `refactoring.md` — Universal: complex functions, tight coupling, long methods, god classes
4. `security.md` — Universal: input validation, injection risks, secrets exposure, OWASP top 10
5. `performance.md` — Universal: unnecessary allocations, N+1 patterns, missing caching, blocking I/O
6. `error_handling.md` — Universal: missing error checks, poor error messages, unhandled edge cases
7. `python_best_practices.md` — [python]: type hints, f-strings, context managers, pathlib, dataclasses
8. `android_best_practices.md` — [android, kotlin]: lifecycle awareness, coroutines, compose patterns, memory leaks
9. `shell_scripting.md` — [bash, shell]: variable quoting, error handling (set -e), portability, shellcheck patterns

Each file should have detailed, actionable review instructions that Claude can follow during automated review. Include specific things to look for, patterns that indicate problems, and what the fix should look like.

### Step 3: Add review mode installation to `ait setup`

Add a new function to `aiscripts/aitask_setup.sh` (after existing setup steps):

1. Check if `seed/reviewmodes/` directory exists
2. List all seed review mode files
3. Extract name and description from each file's YAML frontmatter
4. Present to user via fzf multi-select: "Select review modes to install (Tab to select, Enter to confirm):"
   - Include an "Install all" option at the top
5. Create `aitasks/metadata/reviewmodes/` directory if it doesn't exist
6. Copy selected files, skipping any that already exist (preserve user customizations)
7. Report how many were installed

### Step 4: Ensure setup is idempotent

- Skip files that already exist in target directory
- Don't remove files from target that aren't in seed (user may have custom modes)
- Show "Skipping existing: <filename>" for each skipped file

## Verification Steps

1. Verify all 9 seed files have valid YAML frontmatter with required name and description fields
2. Verify environment field format is correct (list in square brackets)
3. Run the setup function and verify review modes are copied to `aitasks/metadata/reviewmodes/`
4. Run setup again and verify existing files are NOT overwritten
5. Verify the metadata/reviewmodes/ directory only contains .md files
