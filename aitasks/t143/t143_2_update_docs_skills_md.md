---
priority: medium
effort: low
depends: [t143_1]
issue_type: documentation
status: Ready
labels: [claudeskills, aitask_fold]
created_at: 2026-02-17 10:02
updated_at: 2026-02-17 10:02
---

## Context

This is child task 2 of t143 (aitask fold skill). After the SKILL.md is created in t143_1, this task adds documentation for the `/aitask-fold` skill to `docs/skills.md`.

The `docs/skills.md` file (line 153) already contains a forward reference to `/aitask-fold` in the `/aitask-explore` section: "To fold tasks outside of the explore workflow, use [`/aitask-fold`](#aitask-fold) — a dedicated skill for identifying and merging related tasks."

However, no actual section exists yet. This task adds the missing documentation.

## Key Files to Modify

- **`docs/skills.md`** — Add `/aitask-fold` to three locations: Table of Contents, Skill Overview table, and a new full section

## Reference Files for Patterns

- **`docs/skills.md`** — The file itself contains patterns for all other skills. Follow the same format as the `/aitask-explore` section (lines 117-154) for structure and level of detail.
- **`.claude/skills/aitask-fold/SKILL.md`** — Read this (created by t143_1) to understand the full workflow for accurate documentation.

## Implementation Plan

### 1. Add to Table of Contents (after line 10)

Add this line after the `/aitask-explore` entry:
```markdown
- [/aitask-fold](#aitask-fold)
```

### 2. Add to Skill Overview table (after the `/aitask-explore` row, around line 24)

Add this row:
```markdown
| `/aitask-fold` | Identify and merge related tasks into a single task |
```

### 3. Add full section (between `/aitask-explore` closing `---` at line 155 and `/aitask-create` heading at line 157)

Add a new section following the same format as other skills:

```markdown
## /aitask-fold

Identify and merge related tasks into a single task, then optionally execute it. This skill provides the same folding capability as `/aitask-explore` but as a standalone workflow — no codebase exploration required.

**Usage:**
```
/aitask-fold                    # Interactive: discover and fold related tasks
/aitask-fold 106,108,112        # Explicit: fold specific tasks by ID
```

**Workflow overview:**
1. Profile selection
2. Task discovery (interactive or from arguments)
3. Primary task selection
4. Content merging
5. Optional handoff to implementation

**Key capabilities:**
- Interactive mode with AI-powered related task discovery
- Explicit mode with task IDs for quick folding
- Graceful handling of ineligible tasks (warns and continues)
- Same folded_tasks mechanism as /aitask-explore
- Optional continuation to implementation via task-workflow

**Profile key:** `explore_auto_continue` — reuses the same key as /aitask-explore for the post-fold decision point.
```

## Verification Steps

1. Verify TOC link `#aitask-fold` matches the section heading
2. Verify the overview table row aligns with column formatting
3. Verify the section is placed between `/aitask-explore` and `/aitask-create`
4. Verify the existing forward reference on line 153 correctly links to the new section
