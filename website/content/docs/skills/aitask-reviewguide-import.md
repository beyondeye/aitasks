---
title: "/aitask-reviewguide-import"
linkTitle: "/aitask-reviewguide-import"
weight: 100
description: "Import external content as a review guide with proper metadata"
---

Import external content — a local file, a URL, or a GitHub repository directory — and transform it into a structured review guide with proper metadata. This skill converts coding standards, best practices documents, and style guides into actionable review checklists.

**Usage:**
```
/aitask-reviewguide-import ./standards.md                    # Import a local file
/aitask-reviewguide-import https://example.com/guidelines     # Import from a URL
/aitask-reviewguide-import https://github.com/org/repo/blob/main/docs/style.md   # GitHub file
/aitask-reviewguide-import https://github.com/org/repo/tree/main/docs/guides/    # GitHub directory (batch)
```

## Workflow Overview

1. **Fetch content** — Detects source type (local file, GitHub file, GitHub directory, generic URL) and retrieves the content. GitHub files are fetched via the `gh` CLI API
2. **Analyze** — Identifies the document type (coding standards, best practices, security, etc.) and categorizes sections as review-relevant (actionable checks) or non-relevant (workflows, setup, org processes). Non-relevant sections are skipped
3. **Transform** — Converts the content into the standard review guide format: actionable bullets under `## Review Instructions` with H3 subsections. Uses established tone ("Check that...", "Flag...", "Look for...", "Verify that..."). Preserves technical details while removing narrative
4. **Determine placement** — Assigns metadata (`name`, `description`, `reviewtype`, `reviewlabels`, `environment`) and determines the target subdirectory in `aireviewguides/`
5. **Preview and confirm** — Shows the complete generated file for review. Options: save as proposed, edit before saving, or cancel
6. **Save and classify** — Writes the file, checks for similarity with existing guides, updates vocabulary files, and commits. If similar guides are found, suggests running [`/aitask-reviewguide-merge`](../aitask-reviewguide-merge/)

**GitHub directory mode:** When pointing to a directory, lists all markdown files for selection (individual or batch import), then processes each through Steps 2-6.

## Key Capabilities

- **Multi-source support** — Import from local files, web URLs, or GitHub repositories. GitHub integration uses the `gh` CLI for authenticated access
- **Intelligent content filtering** — Automatically identifies which sections of a document contain actionable review checks vs. organizational/process content that doesn't belong in a review guide
- **Standard format transformation** — Converts narrative prose into concise, actionable review bullets that follow the established tone and structure of existing guides
- **Automatic similarity detection** — After saving, compares the new guide against all existing guides and sets `similar_to` if significant overlap is found
- **Batch import** — Import an entire directory of guidelines from a GitHub repository in a single session

After importing, consider running [`/aitask-reviewguide-classify`](../aitask-reviewguide-classify/) for fine-tuning metadata, or [`/aitask-reviewguide-merge`](../aitask-reviewguide-merge/) if similar guides were detected.
