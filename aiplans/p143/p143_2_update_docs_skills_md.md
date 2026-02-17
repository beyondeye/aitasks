---
Task: t143_2_update_docs_skills_md.md
Parent Task: aitasks/t143_aitask_fold_skill.md
Sibling Tasks: (none pending)
Archived Sibling Plans: aiplans/archived/p143/p143_1_create_aitask_fold_skill.md
---

# Plan: t143_2 — Add /aitask-fold documentation to docs/skills.md

## Context

Child task 2 of t143. The `/aitask-fold` SKILL.md was created in t143_1. Now we need to add user-facing documentation for the skill to `docs/skills.md`. A forward reference already exists on line 153 (`[/aitask-fold](#aitask-fold)`) but the actual section is missing.

## File to Modify

- **`docs/skills.md`** — Three insertions at specific locations

## Implementation

### 1. Add to Table of Contents (after line 10)

Insert after the `/aitask-explore` entry:
```markdown
- [/aitask-fold](#aitask-fold)
```

### 2. Add to Skill Overview table (after `/aitask-explore` row, line 24)

Insert row:
```markdown
| `/aitask-fold` | Identify and merge related tasks into a single task |
```

### 3. Add full section (between `/aitask-explore` closing `---` and `## /aitask-create`)

Insert a new section following the same format as `/aitask-explore`. Content derived from the SKILL.md created in t143_1.

## Verification

1. TOC link `#aitask-fold` matches the section heading `## /aitask-fold`
2. Overview table row aligns with existing column formatting
3. Section is placed between `/aitask-explore` and `/aitask-create`
4. Existing forward reference on line 153 correctly links to the new section

## Step 9 Reference

Post-implementation: archive child task + plan, update parent's children_to_implement, check if parent is complete.
