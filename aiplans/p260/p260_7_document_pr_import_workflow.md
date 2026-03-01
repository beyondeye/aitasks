---
Task: t260_7_document_pr_import_workflow.md
Parent Task: aitasks/t260_taskfrompullrequest.md
Sibling Tasks: aitasks/t260/t260_1_*.md through t260_6_*.md
Archived Sibling Plans: aiplans/archived/p260/p260_1_*.md through p260_6_*.md
Worktree: (none — current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Document PR Import Workflow (t260_7)

## Overview

Add comprehensive documentation for the PR import feature: bash command reference pages, skill reference page, workflow guide, and index updates.

## Steps

### 1. Create `website/content/docs/commands/pr-integration.md`

Hugo frontmatter:
```yaml
---
title: "PR Integration"
linkTitle: "PR Integration"
weight: 42
description: "Import pull requests as tasks and close/decline PRs after implementation"
---
```

Content sections:
- `## ait pr-import` — Description, interactive mode steps, batch mode examples, options table, key features
- `---` separator
- `## ait pr-close` — Description, platform behavior (GitHub close, GitLab close, Bitbucket decline), options table, comment format example

Follow `website/content/docs/commands/issue-integration.md` format exactly.

### 2. Create `website/content/docs/skills/aitask-pr-review.md`

Hugo frontmatter:
```yaml
---
title: "/aitask-pr-review"
linkTitle: "/aitask-pr-review"
weight: 22
description: "Analyze a pull request and create an aitask with implementation plan"
---
```

Content: opening paragraph, usage block, Note about project root, step-by-step flow (6 steps), key capabilities, profile info, link to workflow guide.

Follow `website/content/docs/skills/aitask-explore.md` format.

### 3. Create `website/content/docs/workflows/pr-workflow.md`

Hugo frontmatter:
```yaml
---
title: "PR Import Workflow"
linkTitle: "PR Import"
weight: 35
description: "End-to-end guide for importing pull requests as aitasks"
---
```

Content sections:
- **Motivation** — Why import PRs as tasks, use cases, benefits
- **Overview flow** — ASCII diagram showing the pipeline
- **Step-by-step guide** — Import → Review → Implement → Archive
- **New metadata fields** — Reference for `pull_request:`, `contributor:`, `contributor_email:`
- **Contributor attribution** — Co-authored-by explanation, email formats
- **Platform examples** — GitHub, GitLab, Bitbucket

### 4. Update `website/content/docs/commands/_index.md`

Add "PR Integration" category to command table with links to `pr-integration/`.

### 5. Update `website/content/docs/skills/_index.md`

Add `/aitask-pr-review` row to skill table.

## Verification

1. `cd website && hugo build --gc --minify` — no build errors
2. `cd website && ./serve.sh` — check all pages render
3. Verify sidebar navigation shows new entries
4. Verify all cross-links work
5. Compare command docs against actual CLI flags

## Step 9 Reference

Post-implementation: archive child task via `./aiscripts/aitask_archive.sh 260_7`
