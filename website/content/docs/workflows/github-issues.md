---
title: "GitHub Issue Development Workflow"
linkTitle: "GitHub Issues"
weight: 30
description: "Round-trip workflow between GitHub issues and aitasks"
---

The framework fully supports GitHub issue-based development through the [`ait issue-import`](../../commands/issue-integration/#ait-issue-import) and [`ait issue-update`](../../commands/issue-integration/#ait-issue-update) commands, creating a seamless round-trip between GitHub and your local task management.

## The Full Cycle

1. **Import** — Run [`ait issue-import`](../../commands/issue-integration/#ait-issue-import) to fetch open GitHub issues and create task files. In interactive mode, you can browse issues with fzf, preview their content, and select which ones to import. GitHub labels are mapped to aitask labels, and the issue type is auto-detected from labels (bug, chore, documentation, feature, performance, refactor, style, test). A link to the original issue is stored in the task's `issue` metadata field

2. **Implement** — Pick the imported task with [`/aitask-pick`](../../skills/aitask-pick/) and go through the normal implementation workflow (planning, coding, review)

3. **Close** — During post-implementation, the [`/aitask-pick`](../../skills/aitask-pick/) workflow detects the linked `issue` field and offers to update the GitHub issue. Choose from: close with implementation notes, comment only, close silently, or skip. The [`ait issue-update`](../../commands/issue-integration/#ait-issue-update) command automatically extracts implementation notes from the archived plan file and detects associated commits by searching git log for the `(t<task_id>)` pattern in commit messages

## Batch Import

```bash
ait issue-import --batch --all --skip-duplicates    # Import all open issues
ait issue-import --batch --range 10-20 --parent 5   # Import as children of task 5
```
