---
title: "/aitask-create"
linkTitle: "/aitask-create"
weight: 40
description: "Create a new task file interactively via Claude Code"
---

Create a new task file with automatic numbering and proper metadata via Claude Code prompts.

**Usage:**
```
/aitask-create
```

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

## Step-by-Step

Claude Code guides you through task creation using `AskUserQuestion` prompts:

1. **Parent selection** — Choose standalone or child of existing task
2. **Task number** — Auto-determined from active, archived, and compressed tasks
3. **Metadata** — Priority, effort, dependencies (with sibling dependency prompt for child tasks)
4. **Task name** — Free text with auto-sanitization
5. **Definition** — Iterative content collection with file reference insertion via Glob search
6. **Create & commit** — Writes task file with YAML frontmatter and commits to git

This is the Claude Code-native alternative — metadata collection happens through Claude's UI rather than terminal fzf.

## Workflows

For workflow guides, see [Capturing Ideas](../../workflows/capturing-ideas/) and [Follow-Up Tasks](../../workflows/follow-up-tasks/).
