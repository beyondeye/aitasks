---
priority: low
effort: low
depends: [t398_2]
issue_type: documentation
status: Done
labels: [aitask_revert]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-16 10:39
updated_at: 2026-03-17 12:24
completed_at: 2026-03-17 12:24
---

Create website documentation for the aitask-revert feature: skill reference page and workflow guide.

## Context
This is child 4 of t398 (aitask-revert). Depends on t398_2 (needs the skill to be implemented to document accurately). Can be done in parallel with t398_3.

## Key Files to Create
- `website/content/docs/skills/aitask-revert.md` — Skill reference page
- `website/content/docs/workflows/revert-changes.md` — "Revert Changes with AI" workflow guide

## Reference Files for Patterns
- `website/content/docs/skills/aitask-fold.md` — Skill page template (frontmatter, structure)
- `website/content/docs/skills/aitask-explore.md` — Another skill page example
- `website/content/docs/workflows/follow-up-tasks.md` — Workflow page template
- `website/content/docs/workflows/task-consolidation.md` — Another workflow example

## Implementation Plan

### 1. Skill Reference Page (`aitask-revert.md`)

Frontmatter:
```yaml
---
title: "/aitask-revert"
linkTitle: "/aitask-revert"
weight: 35
description: "Revert changes associated with completed tasks — fully or partially"
---
```

Sections:
- Opening paragraph: what the skill does, when to use it
- **Usage**: `/aitask-revert` (interactive) and `/aitask-revert <task_id>` (direct)
- **Task Discovery**: three methods (direct ID, recent tasks, file drill-down)
- **Revert Types**: complete vs partial, with brief descriptions
- **Post-Revert Options**: delete / keep archived / move back to Ready
- **How It Works**: brief flow summary
- **Related**: links to workflow page, aitask-explain, user-file-select

### 2. Workflow Guide Page (`revert-changes.md`)

Frontmatter:
```yaml
---
title: "Revert Changes with AI"
linkTitle: "Revert Changes"
weight: 90
description: "Reverting features or changes that are no longer needed"
---
```

Sections:
- **When to Use**: feature bloat, experimental features that didn't pan out, partial reverts of large changes, cleanup after prototyping
- **How It Works**: overview of the skill flow (discovery → analysis → selection → task creation → implementation)
- **Complete Revert Walkthrough**: step-by-step example of reverting all changes from a task
- **Partial Revert Walkthrough**: step-by-step example of selecting areas to keep/revert
- **Post-Revert Task Management**: explanation of the three disposition options and when each is appropriate
- **Relationship to Git Revert**: explain that this is higher-level than `git revert` — it creates an aitask with a plan, handles task metadata, supports partial reverts, and manages archived task state
- **Tips**: when to use complete vs partial, reverting parent tasks with children

### 3. Update index pages if needed
- Check if `website/content/docs/skills/_index.md` needs updating (Hugo auto-discovers, probably not needed)
- Same for `website/content/docs/workflows/_index.md`

## Verification Steps
- `cd website && hugo build --gc --minify` succeeds without errors
- Skill page renders correctly (check local dev server with `./serve.sh`)
- Workflow page renders correctly
- All internal links work (skill page links to workflow, workflow links to skill)
- Frontmatter weights place pages in logical order among existing pages
