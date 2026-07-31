---
title: "/aitask-docs-gap"
linkTitle: "/aitask-docs-gap"
weight: 61
description: "Find website docs gaps for a release and create one documentation task"
maturity: [experimental]
depth: [intermediate]
---

Analyze all tasks landed since the last release and determine which shipped changes are missing documentation on the project website, then create a single `documentation` task capturing all the gaps. Complementary to [`/aitask-changelog`](../aitask-changelog/) (release summary) and to the `docs_updated` gate (per-task doc enforcement): this skill is the retroactive batch check for releases where the gate was not active per-task.

**Usage:**
```
/aitask-docs-gap [from_tag]
```

- `from_tag` (optional) — analyze tasks landed since this tag instead of the latest release tag.

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

## Step-by-Step

1. **Sync with remote** — Best-effort fetch and behind-check so tasks merged only on the remote are not silently missed
2. **Gather release scope** — Runs `ait changelog --gather` to collect all tasks since the last release tag, with their issue types, plan files, commits, and implementation notes
3. **Resolve the doc-update spec** — Reads the project's configured doc-update guide (the `doc_update.guide` setting), which maps change kinds to documentation areas
4. **Derive changed files** — Lists each task's changed files from its commits, ignoring task/plan data paths
5. **Classify each task** — Marks every task as documented (its mapped doc page was updated in the release window or already covers the change), a gap (doc-relevant surface shipped without docs), or not doc-relevant (no doc obligation per the guide)
6. **Confirm findings** — Presents the per-gap findings for approval; you can create the task, narrow it to a subset of gaps, or end with a report only. If no gaps exist, reports "docs are complete for this release" and creates nothing
7. **Create the documentation task** — Creates exactly one `documentation` task whose description contains one delimited `## Gap:` section per confirmed gap (target doc pages, what shipped, what to write, source pointers)

## Key Features

- Analysis-only: never edits documentation itself — writing the docs is the created task's job
- Reuses the changelog gather step and the configured doc-update guide; no parallel gathering logic or hardcoded doc-area map
- Creates exactly one task, never child tasks — the per-gap sections are designed so the task can be split into siblings at pick time via normal decomposition
- Handles releases with no task-tagged commits and fully documented releases gracefully

## Workflows

For a full workflow guide covering the release pipeline, see [Releases](../../workflows/releases/).
