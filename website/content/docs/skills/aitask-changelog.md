---
title: "/aitask-changelog"
linkTitle: "/aitask-changelog"
weight: 60
description: "Generate a changelog entry from commits and archived plans"
---

Generate a changelog entry by analyzing commits and archived plans since the last release. Orchestrates the `ait changelog` command with AI-powered summarization.

**Usage:**
```
/aitask-changelog
```

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

## Step-by-Step

1. **Gather release data** — Runs `ait changelog --gather` to collect all tasks since the last release tag, with their issue types, plan files, commits, and implementation notes
2. **Summarize plans** — Reads each task's archived plan file and generates concise user-facing summaries (what changed from the user's perspective, not internal details)
3. **Draft changelog entry** — Groups summaries by issue type under `### Features`, `### Bug Fixes`, `### Improvements` headings. Format: `- **Task name** (tNN): summary`
4. **Version number** — Reads `VERSION` file, calculates next patch/minor, asks user to select or enter custom version
5. **Version validation** — Ensures the selected version is strictly greater than the latest version in CHANGELOG.md (semver comparison)
6. **Overlap detection** — Checks if any gathered tasks already appear in the latest changelog section. If overlap found, offers: "New tasks only", "Replace latest section", or "Abort"
7. **Review and finalize** — Shows the complete formatted entry for approval. Options: "Write to CHANGELOG.md", "Edit entry", or "Abort"
8. **Write and commit** — Inserts the entry into CHANGELOG.md (after the `# Changelog` header) and commits

## Key Features

- User-facing summaries: focuses on what changed, not implementation details
- Version validation prevents duplicate or regressive version numbers
- Overlap detection handles incremental changelog updates when some tasks were already documented
- Supports both new CHANGELOG.md creation and insertion into existing files

## Workflows

For a full workflow guide covering the release pipeline, see [Releases](../../workflows/releases/).
