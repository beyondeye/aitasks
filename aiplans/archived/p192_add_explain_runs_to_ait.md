---
Task: t192_add_explain_runs_to_ait.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

The `aitask_explain_runs.sh` script exists at `aiscripts/aitask_explain_runs.sh` and manages `aiexplains/` run directories (list, delete, interactive cleanup via fzf). However, it is not registered in the `ait` dispatcher and has no website documentation.

## Plan

### 1. Register `explain-runs` in the `ait` dispatcher

**File:** `ait`

- Add to `show_usage()` help text (after `changelog`, before `zip-old`)
- Add to dispatch case statement (after `changelog`)

### 2. Update the command reference table

**File:** `website/content/docs/commands/_index.md`

- Add row to the table linking to the new explain page
- Add usage examples in the examples block

### 3. Create command documentation page

**New file:** `website/content/docs/commands/explain.md` (weight 35)

Contents: frontmatter, description of `ait explain-runs`, interactive mode, batch mode flags, options table, run directory structure description, safety notes, cross-reference to `/aitask-explain` skill.

## Verification

1. `./ait explain-runs --help` — should show the script's help
2. `./ait explain-runs --list` — should work
3. `./ait help` — should show `explain-runs` in usage
4. `shellcheck ait` — should pass
5. `cd website && hugo build --gc --minify` — should build without errors

## Final Implementation Notes
- **Actual work done:** All three planned steps implemented exactly as planned — dispatcher registration, command reference update, and new documentation page.
- **Deviations from plan:** None.
- **Issues encountered:** None. All verification steps passed (help, list, shellcheck, hugo build).
- **Key decisions:** Used command name `explain-runs` (kebab-case, matching `issue-import`/`zip-old` convention). Placed in dispatcher help text between `changelog` and `zip-old` (utility grouping). New docs page at weight 35 between board-stats (30) and issue-integration (40).
