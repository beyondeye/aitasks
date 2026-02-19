---
title: "Code Review Workflow"
linkTitle: "Code Review"
weight: 70
description: "Systematic code review using review guides, separate from implementation"
---

The aitasks review system separates code quality review from implementation. The philosophy: first build something that works, then review it for quality improvements. This separation of concerns makes more efficient use of the LLM context — implementation and review are distinct cognitive tasks that benefit from dedicated focus.

## The Review Cycle

After completing an implementation task with [`/aitask-pick`](../../skills/aitask-pick/), run a targeted review:

1. **Run [`/aitask-review`](../../skills/aitask-review/)** — Select the files or commits to review, and choose which review guides to apply. The skill auto-detects the most relevant guides based on the languages and frameworks in your code
2. **Review findings** — Examine the results grouped by guide and severity. Select which findings to act on
3. **Create tasks** — Turn selected findings into tasks (single task, grouped by guide, or one per finding)
4. **Implement fixes** — Run [`/aitask-pick`](../../skills/aitask-pick/) on the review task to fix the issues

This cycle can be repeated with different review guides to cover multiple quality dimensions (security, performance, style, etc.).

## Managing Review Guides

Review guides live in `aireviewguides/` organized by environment (`general/`, `python/`, `shell/`, etc.). Each guide is a markdown file with metadata and actionable review instructions. Guides can be excluded from auto-detection by adding patterns to `aireviewguides/.reviewguidesignore` (uses gitignore syntax). Three companion skills manage the guide library:

**Typical guide management workflow:**

1. **Import** — Use [`/aitask-reviewguide-import`](../../skills/aitask-reviewguide-import/) to bring in external coding standards, style guides, or best practices from URLs, local files, or GitHub repositories. The skill transforms narrative content into actionable review checklists
2. **Classify** — Use [`/aitask-reviewguide-classify`](../../skills/aitask-reviewguide-classify/) to assign metadata (type, labels, environment) to new or unclassified guides. This metadata powers the auto-detection when running reviews
3. **Merge** — Use [`/aitask-reviewguide-merge`](../../skills/aitask-reviewguide-merge/) to consolidate overlapping guides. When classify finds similar guides, merge resolves the overlap by combining content or deduplicating shared checks

## When to Review

- **After implementing a feature** — Review the implementation for quality, security, and adherence to project conventions
- **After a batch of changes** — Select recent commits and review them collectively
- **Periodic codebase audits** — Review specific directories or modules against relevant guides
- **Onboarding new standards** — Import a new coding standard as a review guide, then review existing code against it to create tasks for bringing the codebase into compliance
