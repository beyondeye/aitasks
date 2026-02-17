---
priority: medium
effort: low
depends: []
issue_type: refactor
status: Done
labels: [aitasks, bash]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-17 10:48
updated_at: 2026-02-17 11:15
completed_at: 2026-02-17 11:15
---

## Context

This is child 1 of t144 (ait clear_old rewrite). The script `aitask_clear_old.sh` is being renamed to `aitask_zip_old.sh` for clarity. The command `clear-old` becomes `zip-old` in the dispatcher, and the skill `aitask-cleanold` becomes `aitask-zipold`.

This child task handles ONLY the rename — no logic changes. Child 2 (tar.gz fallback) and Child 3 (selection logic rewrite) depend on this completing first.

## Key Files to Modify

1. **`aiscripts/aitask_clear_old.sh`** — `git mv` to `aiscripts/aitask_zip_old.sh`, update comment on line 3
2. **`ait`** — Line 30: `clear-old` → `zip-old` in usage; Line 109: update dispatch to `aitask_zip_old.sh`
3. **`.claude/skills/aitask-cleanold/`** — `git mv` entire directory to `.claude/skills/aitask-zipold/`, update SKILL.md:
   - Frontmatter `name: aitask-cleanold` → `name: aitask-zipold`
   - All `./aiscripts/aitask_clear_old.sh` references → `./aiscripts/aitask_zip_old.sh`
4. **`docs/commands.md`** — Lines 14, 30, 339-367: rename `clear-old` → `zip-old` everywhere
5. **`docs/skills.md`** — Lines 14, 28, 233-253: rename `aitask-cleanold` → `aitask-zipold`
6. **`seed/claude_settings.local.json`** — Line 30: `aitask_clear_old.sh` → `aitask_zip_old.sh`
7. **`aitasks/metadata/claude_settings.seed.json`** — Line 30: same rename
8. **`tests/test_terminal_compat.sh`** — Line 232: `aitask_clear_old.sh` → `aitask_zip_old.sh`

## Reference Files for Patterns

- `ait` dispatcher (line 109): current dispatch pattern
- `.claude/skills/aitask-cleanold/SKILL.md`: current skill content

## Implementation Plan

1. `git mv aiscripts/aitask_clear_old.sh aiscripts/aitask_zip_old.sh`
2. Update comment in line 3 of renamed file
3. `git mv .claude/skills/aitask-cleanold .claude/skills/aitask-zipold`
4. Update SKILL.md content (name, references)
5. Edit `ait` dispatcher (lines 30, 109)
6. Edit `docs/commands.md` (lines 14, 30, 339-367)
7. Edit `docs/skills.md` (lines 14, 28, 233-253)
8. Edit `seed/claude_settings.local.json` (line 30)
9. Edit `aitasks/metadata/claude_settings.seed.json` (line 30)
10. Edit `tests/test_terminal_compat.sh` (line 232)

No backward compat alias needed.

## Verification Steps

- `bash -n aiscripts/aitask_zip_old.sh` (syntax check)
- `./ait zip-old --help` (confirm dispatch works)
- `./ait zip-old --dry-run` (confirm script runs)
- `bash tests/test_terminal_compat.sh` (syntax check for all scripts)
