---
priority: high
effort: high
depends: [t326_1]
issue_type: refactor
status: Done
labels: [install_scripts]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-07 22:41
updated_at: 2026-03-07 23:29
completed_at: 2026-03-07 23:29
---

Update all references from aiscripts/ to .aitask-scripts/ in skills, documentation, seed templates, and tool configs.

## Context
After t326_1 renames the directory and updates core executable code, this task handles all remaining non-test references. The backward-compat symlink (aiscripts -> .aitask-scripts) is still in place, so nothing is broken — this task just updates the canonical references.

## Key Files to Modify

### Claude Code Skills (~22 files, ~154 occurrences)
All `./aiscripts/` → `./.aitask-scripts/` in:
- `.claude/skills/aitask-pick/SKILL.md`
- `.claude/skills/aitask-pickrem/SKILL.md`
- `.claude/skills/aitask-pickweb/SKILL.md`
- `.claude/skills/aitask-explore/SKILL.md`
- `.claude/skills/aitask-create/SKILL.md`
- `.claude/skills/aitask-create2/SKILL.md`
- `.claude/skills/aitask-fold/SKILL.md`
- `.claude/skills/aitask-review/SKILL.md`
- `.claude/skills/aitask-pr-import/SKILL.md`
- `.claude/skills/aitask-stats/SKILL.md`
- `.claude/skills/aitask-changelog/SKILL.md`
- `.claude/skills/aitask-explain/SKILL.md`
- `.claude/skills/aitask-wrap/SKILL.md`
- `.claude/skills/aitask-web-merge/SKILL.md`
- `.claude/skills/aitask-refresh-code-models/SKILL.md`
- `.claude/skills/aitask-reviewguide-classify/SKILL.md`
- `.claude/skills/aitask-reviewguide-merge/SKILL.md`
- `.claude/skills/aitask-reviewguide-import/SKILL.md`
- `.claude/skills/ait-git/SKILL.md`
- `.claude/skills/user-file-select/SKILL.md`
- `.claude/skills/task-workflow/SKILL.md`
- `.claude/skills/task-workflow/procedures.md`
- `.claude/skills/task-workflow/planning.md`
- `.claude/skills/task-workflow/profiles.md`

### Root Documentation (~3 files)
- `CLAUDE.md`: architecture docs (~5 occurrences), shellcheck commands, directory listing
- `README.md`: any aiscripts/ references
- `CHANGELOG.md`: if any references exist (may leave historical entries as-is)

### Website Documentation (~12 files, ~39 occurrences)
- `website/content/docs/development/_index.md`
- `website/content/docs/workflows/code-review.md`
- `website/content/docs/development/review-guide-format.md`
- `website/content/docs/workflows/releases.md`
- `website/content/docs/workflows/explain.md`
- `website/content/docs/commands/explain.md`
- `website/content/docs/skills/aitask-explain.md`
- `website/content/docs/installation/_index.md`
- And others found via grep

### Internal Docs (~2 files)
- `aidocs/sed_macos_issues.md` (~11 occurrences)
- `aidocs/gitremoteproviderintegration.md` (~4 occurrences)

### Seed Templates (~56 occurrences)
- `seed/claude_settings.local.json`: ~28 Bash command patterns
- `seed/opencode_config.seed.json`: ~28 Bash command patterns

### Other Tool Configs
- `.opencode/instructions.md`, `.opencode/commands/`, `.opencode/skills/`
- `.codex/instructions.md`
- `.agents/skills/`

## Implementation Steps
1. Use grep to find all files with aiscripts/ references (excluding tests/ and .aitask-scripts/)
2. For each file, replace `aiscripts/` with `.aitask-scripts/` and `./aiscripts/` with `./.aitask-scripts/`
3. Be careful with CHANGELOG.md — historical entries may be left as-is
4. Verify no broken skill references by checking a few key skill commands
5. Commit changes

## Verification Steps
- `grep -r 'aiscripts/' --include='*.md' --include='*.json' --include='*.yaml' . | grep -v '.aitask-scripts' | grep -v tests/ | grep -v archived/ | grep -v CHANGELOG` returns 0
- Read a few skill files to verify paths look correct
- Website builds: `cd website && hugo build --gc --minify`
