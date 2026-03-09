---
title: "/aitask-create"
linkTitle: "/aitask-create"
weight: 40
description: "Create a new task file interactively via code agent prompts"
---

Create a new task file with automatic numbering and proper metadata via interactive code agent prompts.

**Usage:**
```
/aitask-create
```

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

## Step-by-Step

The skill guides you through task creation using interactive prompts:

1. **Parent selection** — Choose standalone or child of existing task
2. **Task number** — Auto-determined from active, archived, and compressed tasks
3. **Metadata** — Priority, effort, dependencies (with sibling dependency prompt for child tasks)
4. **Task name** — Free text with auto-sanitization
5. **Definition** — Iterative content collection with file reference insertion via Glob search
6. **Create & commit** — Writes task file with YAML frontmatter and commits to git

## Batch Mode

For non-interactive task creation (e.g., scripting or automation), use the underlying script directly with `--batch`:

```bash
./.aitask-scripts/aitask_create.sh --batch --name "task_name" --desc "description" --commit
```

Run `./.aitask-scripts/aitask_create.sh --help` for the full list of flags.

## Workflows

For workflow guides, see [Capturing Ideas](../../workflows/capturing-ideas/) and [Follow-Up Tasks](../../workflows/follow-up-tasks/).
