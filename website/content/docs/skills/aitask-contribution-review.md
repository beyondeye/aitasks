---
title: "/aitask-contribution-review"
linkTitle: "/aitask-contribution-review"
weight: 24
description: "Analyze contribution issues for duplicates and overlaps, then import as grouped or single tasks"
maturity: [stable]
depth: [advanced]
---

Use `/aitask-contribution-review` to review incoming contribution issues with AI-powered duplicate detection, overlap analysis, and merge recommendations. The skill fetches the target issue, finds related contributions, analyzes code diffs, and helps you decide whether to merge, import individually, fold into existing tasks, or update an existing task directly.

**Usage:**
```
/aitask-contribution-review 42       # Review a specific issue
/aitask-contribution-review          # List open contribution issues and choose
```

> **Note:** Must be run from the project root directory. Requires the platform CLI installed and authenticated: `gh` for GitHub (default), `glab` for GitLab. The skill uses a helper script that encapsulates all platform-specific API calls. See [Skills overview](..) for details.

## Step-by-Step

1. **Resolve issue** — Provide an issue number, or browse an interactive listing of open contribution issues (only those with `aitask-contribute-metadata` are shown)
2. **Validate and fetch** — Verifies the issue is a valid contribution with metadata, displays a summary of the contributor, areas, and change type
3. **Duplicate check** — Detects if the issue was already imported as an aitask, preventing accidental re-imports
4. **Gather related issues** — Finds related contributions via CI/CD bot comment overlap scores and linked issue references (`#N` patterns). If no bot comment exists, offers to run a local overlap check
5. **Fetch candidate details** — Retrieves full content of related issues and presents a summary table with scores, contributors, and changed files
6. **AI diff analysis** — Reads code diffs across all candidates and the target issue. Identifies same files/functions touched, same bugs fixed differently, or complementary changes
7. **Propose action** — Recommends merging multiple issues into one task, importing the target individually, or skipping
8. **Check existing tasks** — Searches for existing aitasks that already cover the contribution's scope. Offers to fold overlapping tasks into the new import, update an existing task instead, or ignore the overlap
9. **Execute import** — Runs `ait issue-import` (with `--merge-issues` for grouped imports). Produces at most one task per invocation
10. **Attribution** — For merged imports, the primary contributor (largest diff) gets the `Co-authored-by` trailer, additional contributors are listed in the commit body

## Key Capabilities

- **Platform-agnostic** — Works on GitHub, GitLab, and Bitbucket through a helper script that encapsulates platform-specific API calls

- **Duplicate detection** — Prevents re-importing issues that are already tracked as aitasks

- **Fingerprint overlap scoring** — Leverages the CI/CD overlap analysis bot comment to find related issues by file paths, directories, areas, and change type

- **AI-powered merge recommendations** — Analyzes actual code diffs across candidates, not just metadata similarity, to recommend whether issues should be merged

- **Flexible import options** — Merge multiple issues into one task, import individually, fold into existing tasks, or update an existing task with the contribution content

- **Multi-contributor attribution** — Preserves contributor identity through the entire workflow. Merged imports track all contributors via a `contributors:` frontmatter field

## Workflows

For the full technical details on fingerprint metadata, overlap scoring, CI/CD setup, and platform support, see [Contribution Flow](../../workflows/contribute-and-manage/contribution-flow/).

For the end-to-end contribution lifecycle including the contributor side, see [Contribute and Manage Contributions](../../workflows/contribute-and-manage/).
