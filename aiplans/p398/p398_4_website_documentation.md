---
Task: t398_4_website_documentation.md
Parent Task: aitasks/t398_aitask_revert.md
Sibling Tasks: aitasks/t398/t398_1_revert_analyze_script.md, aitasks/t398/t398_2_revert_skill.md, aitasks/t398/t398_3_post_revert_integration.md
Archived Sibling Plans: aiplans/archived/p398/p398_1_revert_analyze_script.md, aiplans/archived/p398/p398_2_revert_skill.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t398_4 — Website Documentation

## Overview

Create two website pages: a skill reference page for `/aitask-revert` and a "Revert Changes with AI" workflow guide.

## Steps

### Step 1: Create skill reference page

Create `website/content/docs/skills/aitask-revert.md`:

```yaml
---
title: "/aitask-revert"
linkTitle: "/aitask-revert"
weight: 35
description: "Revert changes associated with completed tasks — fully or partially"
---
```

Sections:
- Opening paragraph explaining what the skill does and when to use it
- **Usage**: `/aitask-revert` and `/aitask-revert <task_id>`
- **Task Discovery**: three methods (direct ID, browse recent, file drill-down)
- **Revert Types**: complete vs partial with descriptions
- **Post-Revert Options**: delete / keep archived / move back to Ready
- **Flow Summary**: brief step-by-step
- **Related**: link to workflow page

Follow pattern from `website/content/docs/skills/aitask-fold.md`.

### Step 2: Create workflow guide page

Create `website/content/docs/workflows/revert-changes.md`:

```yaml
---
title: "Revert Changes with AI"
linkTitle: "Revert Changes"
weight: 90
description: "Reverting features or changes that are no longer needed"
---
```

Sections:
- **When to Use**: feature bloat, experiments, partial cleanup
- **How It Works**: overview of the flow
- **Complete Revert Walkthrough**: step-by-step example
- **Partial Revert Walkthrough**: step-by-step example
- **Post-Revert Management**: three disposition options explained
- **vs Git Revert**: higher-level approach (creates aitask, handles metadata, supports partial)
- **Tips**: when to use complete vs partial, parent tasks with children

Follow pattern from `website/content/docs/workflows/follow-up-tasks.md`.

### Step 3: Update skills index

**File:** `website/content/docs/skills/_index.md`

Add `/aitask-revert` row to the "Task Management" table after `/aitask-fold`.

### Step 4: Verify build

```bash
cd website && hugo build --gc --minify
```

Check that pages render correctly, links work, and are in correct position in nav.

## Step 9 Reference
After implementation, follow task-workflow Step 9 for archival.
