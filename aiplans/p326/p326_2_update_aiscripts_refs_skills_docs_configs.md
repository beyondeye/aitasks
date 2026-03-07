---
Task: t326_2_update_aiscripts_refs_skills_docs_configs.md
Parent Task: aitasks/t326_refactoring_of_installed_files.md
Sibling Tasks: aitasks/t326/t326_1_*.md, aitasks/t326/t326_3_*.md
Archived Sibling Plans: aiplans/archived/p326/p326_1_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t326_2 — Update aiscripts/ references in skills, docs, seeds, configs

## Overview

After t326_1 renamed the directory, this task updates all non-test, non-executable references from `aiscripts/` to `.aitask-scripts/`. The backward-compat symlink is still in place, so this is a safe find-and-replace operation.

## Steps

### 1. Claude Code Skills (~22 files)

Use find-and-replace in all `.claude/skills/**/SKILL.md` and supporting files:
- `./aiscripts/` → `./.aitask-scripts/`
- `aiscripts/` → `.aitask-scripts/` (in non-command contexts like directory descriptions)

Key files with high occurrence counts:
- `.claude/skills/aitask-pickrem/SKILL.md` (~23)
- `.claude/skills/task-workflow/SKILL.md` (~18)
- `.claude/skills/task-workflow/procedures.md` (~10)
- `.claude/skills/aitask-review/SKILL.md` (~10)
- `.claude/skills/aitask-pick/SKILL.md` (~10)
- `.claude/skills/aitask-pr-import/SKILL.md` (~9)
- `.claude/skills/aitask-fold/SKILL.md` (~9)

### 2. Root Documentation

- `CLAUDE.md`: Update architecture section, shellcheck commands, directory listing (~5 occurrences)
- `README.md`: Update any aiscripts/ references

### 3. Website Documentation (~12 files)

Search `website/content/docs/` for `aiscripts/` references. Key files:
- `website/content/docs/development/_index.md` (~9)
- `website/content/docs/workflows/code-review.md` (~6)
- `website/content/docs/skills/aitask-explain.md` (~7)
- `website/content/docs/workflows/explain.md` (~4)
- And others

### 4. Internal Documentation (aidocs/)

- `aidocs/sed_macos_issues.md` (~11 occurrences)
- `aidocs/gitremoteproviderintegration.md` (~4 occurrences)

### 5. Seed Templates (~56 occurrences)

- `seed/claude_settings.local.json`: ~28 entries of `Bash(./aiscripts/` → `Bash(./.aitask-scripts/`
- `seed/opencode_config.seed.json`: ~28 entries of same pattern

### 6. Other Tool Configs

- `.opencode/instructions.md`
- `.opencode/commands/` and `.opencode/skills/`
- `.codex/instructions.md`
- `.agents/skills/`

### 7. Commit
```bash
git add .claude/skills/ CLAUDE.md README.md website/ aidocs/ seed/ .opencode/ .codex/ .agents/
git commit -m "refactor: Update aiscripts/ refs in skills, docs, configs (t326_2)"
```

## Approach

For each category, use a systematic grep → edit cycle:
1. `grep -rl 'aiscripts/' <directory> --include='*.md' --include='*.json'`
2. For each file, replace `aiscripts/` with `.aitask-scripts/`
3. Verify the replacements look correct (not accidentally replacing inside words like `.aitask-scripts/` — but there's no word containing `aiscripts` as a substring, so this is safe)

## Verification
- `grep -r 'aiscripts/' --include='*.md' --include='*.json' --include='*.yaml' . | grep -v '.aitask-scripts' | grep -v tests/ | grep -v archived/ | grep -v CHANGELOG` → 0 matches
- Read a few key skill files to spot-check
- Website builds: `cd website && hugo build --gc --minify`

## Step 9 (Post-Implementation)
After verification, proceed to archival per the task-workflow.
