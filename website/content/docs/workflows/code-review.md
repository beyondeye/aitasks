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

## Walkthrough: Reviewing a Shell Script Module

You've just finished adding several new helper scripts to `aiscripts/`. Before moving on, you want to check them against shell scripting best practices.

**1. Launch the skill**

```
/aitask-review
```

Select "Specific paths" when prompted and enter `aiscripts/` as the target.

**2. Select review guides**

The auto-detection system analyzes the target files, finds `.sh` extensions and bash shebangs, and ranks shell-related guides first. You're presented with a multi-select list:

- Shell Scripting (score: 7) — top match
- Error Handling (universal)
- Code Conventions (universal)
- Security (universal)
- ...

Select "Shell Scripting" and "Error Handling" — two guides keeps the review focused.

**3. Review findings**

Claude reads each guide's review instructions and systematically examines the scripts. Findings are presented grouped by guide and severity:

```
Shell Scripting (3 findings)
  High: aiscripts/aitask_sync.sh:42 — Unquoted variable in rm command risks glob expansion
  Medium: aiscripts/aitask_sync.sh:15 — Missing set -euo pipefail
  Low: aiscripts/aitask_helper.sh:88 — Hardcoded /tmp path instead of mktemp

Error Handling (1 finding)
  Medium: aiscripts/aitask_sync.sh:67 — Broad trap on EXIT masks specific error handling
```

**4. Select and create a task**

You select the high and both medium findings (skip the low cosmetic one). Choose "Single task" — a task is created with the three findings in its description, priority set to `high` (from the highest severity finding).

Select "Continue to implementation" to hand off to the standard [`/aitask-pick`](../../skills/aitask-pick/) workflow, which handles planning, implementation, review, and archival.

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

## Tips

- **Keep reviews focused** — Select one or two guides per session rather than running all guides at once. Focused reviews produce actionable findings; broad reviews produce noise
- **Review after implementing** — Use "Recent changes" to review your own work before moving on. This catches issues while context is fresh
- **Build project-specific guides** — Use [`/aitask-reviewguide-import`](../../skills/aitask-reviewguide-import/) to turn your team's coding standards or style guides into review guides. Project-specific conventions are where automated review adds the most value
- **Pre-configure frequent combinations** — Set the `review_default_modes` profile key (comma-separated guide names) to auto-select your go-to guides, skipping the selection prompt
