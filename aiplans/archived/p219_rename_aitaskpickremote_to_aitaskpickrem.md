---
Task: t219_rename_aitaskpickremote_to_aitaskpickrem.md
---

## Context

The `aitask-pick-remote` skill name is verbose. Renaming to `aitask-pickrem` for brevity while maintaining all functionality.

## Plan

### 1. Rename the skill directory

```bash
mv .claude/skills/aitask-pick-remote .claude/skills/aitask-pickrem
```

### 2. Update SKILL.md frontmatter and base directory

In `.claude/skills/aitask-pickrem/SKILL.md`:
- Line 2: `name: aitask-pick-remote` → `name: aitask-pickrem`
- Line 6: Update base directory path from `aitask-pick-remote` → `aitask-pickrem`

### 3. Update references in task-workflow/SKILL.md

In `.claude/skills/task-workflow/SKILL.md`:
- Line 115: `aitask-pick-remote` → `aitask-pickrem`
- Line 622: `aitask-pick-remote` → `aitask-pickrem`

## Files Modified

- `.claude/skills/aitask-pick-remote/` → `.claude/skills/aitask-pickrem/` (directory rename)
- `.claude/skills/aitask-pickrem/SKILL.md` (name + base directory)
- `.claude/skills/task-workflow/SKILL.md` (2 references)

## Verification

1. `ls .claude/skills/aitask-pickrem/SKILL.md` — file exists at new path
2. `ls .claude/skills/aitask-pick-remote/ 2>/dev/null` — old path gone
3. `grep -r "aitask-pick-remote" .claude/skills/` — no remaining references

## Final Implementation Notes
- **Actual work done:** Renamed directory, updated SKILL.md name field, updated 2 references in task-workflow/SKILL.md. Also removed the machine-specific "Base directory for this skill" line from SKILL.md as it was unique to this skill and unnecessary.
- **Deviations from plan:** Removed the base directory line (not in original plan) per user feedback — no other skill uses it and it contained a hardcoded machine path.
- **Issues encountered:** None.
- **Key decisions:** Removed base directory line rather than just updating it, since it was machine-specific and not used by any other skill.
