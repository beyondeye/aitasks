---
title: "PR Import Workflow"
linkTitle: "PR Import"
weight: 35
description: "End-to-end guide for creating aitasks from pull requests"
depth: [advanced]
---

The framework supports creating tasks from external pull requests, providing a structured path for incorporating contributions that cannot be merged directly. Instead of accepting or rejecting a PR as-is, the workflow extracts the contributor's intent and approach, validates it against project conventions, and produces a task that goes through the standard implementation cycle — with proper attribution back to the original contributor.

## Motivation

Not every pull request can be merged directly. Common scenarios:

- **External contributions** need additional review, testing, or alignment with project conventions before the changes can be accepted
- **Code quality gates** require that all changes go through the project's planning and review workflow, regardless of source
- **Approach validation** — a PR may have the right idea but an implementation that doesn't fit the codebase patterns, requires refactoring, or has missing edge cases

Importing PRs as tasks solves this by:

- Preserving the contributor's ideas and implementation details as structured context for a new task
- Running the changes through the same planning → implementation → review cycle as any other task
- Crediting the original contributor via `Co-authored-by` trailers in the final commits
- Automatically closing the source PR with implementation notes once the task is complete

## How It Works

There are two paths for creating a task from a pull request:

### Path 1: AI-Powered Review (`/aitask-pr-import`)

The [`/aitask-pr-import`](../../skills/aitask-pr-import/) skill provides a fully interactive, AI-assisted workflow:

1. Select a PR (by number, browse open PRs, or use previously extracted data)
2. AI analyzes the PR — purpose, approach, quality, concerns, codebase alignment
3. Interactive Q&A to explore specific aspects
4. Discover and fold related pending tasks
5. Create a task with rich context and AI-generated implementation approach

This is the recommended path for most PRs, especially those requiring careful analysis.

### Path 2: Direct Import (`ait pr-import`)

The [`ait pr-import`](../../commands/pr-import/#ait-pr-import) command provides direct import without AI analysis. It supports both interactive and batch modes:

**Interactive mode** (default) — browse open PRs with fzf, preview details, select which to import, and choose between creating a basic task or extracting data for later use with `/aitask-pr-import`:

```bash
ait pr-import                                         # Interactive PR selection
```

**Batch mode** — for automation and scripting:

```bash
ait pr-import --batch --pr 42                         # Import a single PR as a task
ait pr-import --batch --pr 42 --data-only             # Extract data only (for /aitask-pr-import)
ait pr-import --batch --all --skip-duplicates         # Import all open PRs
```

This creates tasks with the PR title, description, and metadata — but without the AI analysis that `/aitask-pr-import` provides. Use this for bulk imports or when the PR is straightforward.

Both paths store the same metadata in the task frontmatter: `pull_request` (URL), `contributor` (username), and `contributor_email` (for attribution).

## End-to-End Flow

```
External PR
    │
    ├─── /aitask-pr-import ──── AI analysis ──── Task + Plan
    │                                                │
    └─── ait pr-import ────────────────────────── Task (basic)
                                                     │
                                              /aitask-pick
                                                     │
                                          Planning → Implementation
                                                     │
                                          Review → Commit (with Co-authored-by)
                                                     │
                                          Archive → PR closed with notes
```

## Automated Lifecycle

Once a task is created from a PR, the standard task workflow (invoked by [`/aitask-pick`](../../skills/aitask-pick/) and related skills) handles the rest automatically:

**Contributor attribution** — During the commit step (Step 8 of task-workflow), if the task has `contributor` and `contributor_email` metadata, the commit message includes a `Co-authored-by` trailer crediting the original contributor:

```
feature: Implement auth token refresh (t83)

Co-authored-by: contributor-name <contributor-email@users.noreply.github.com>
```

Platform-specific email formats:
- **GitHub:** `<id>+<username>@users.noreply.github.com` (resolved from GitHub API)
- **GitLab:** `<username>@users.noreply.gitlab.com`
- **Bitbucket:** Resolved from the PR author's profile

**PR close/decline** — During archival (Step 9 of task-workflow), if the task has a `pull_request` field, the workflow offers to close or decline the source PR with a comment containing:
- A reference to the resolved task
- Final implementation notes from the archived plan file
- Associated commits detected from git history
- A thank-you note to the contributor

The close behavior is platform-specific: GitHub and GitLab close the PR/MR, Bitbucket declines it.

## Task Metadata Fields

Tasks created from PRs include these additional frontmatter fields:

| Field | Description | Example |
|-------|-------------|---------|
| `pull_request` | URL of the source PR/MR | `https://github.com/org/repo/pull/42` |
| `contributor` | Platform username of the PR author | `octocat` |
| `contributor_email` | Pre-computed noreply email for `Co-authored-by` | `12345+octocat@users.noreply.github.com` |

These fields are preserved through the full task lifecycle and used during commit attribution and PR close/decline.

## Platform Examples

### GitHub

```bash
# Extract PR data for AI review
ait pr-import --batch --pr 42 --data-only --silent

# Review with AI
/aitask-pr-import    # Select "Use existing PR data", pick #42

# After implementation and archival:
# → Commit includes: Co-authored-by: user <id+user@users.noreply.github.com>
# → PR #42 is closed with implementation notes
```

### GitLab

```bash
# Import MR directly as a task
ait pr-import --batch --pr 15 --source gitlab

# For cross-repo MRs:
ait pr-import --batch --pr 15 --source gitlab --repo group/project
```

### Bitbucket

```bash
# Import from Bitbucket Cloud
ait pr-import --batch --pr 7 --source bitbucket

# After archival: PR is declined (Bitbucket uses "decline" semantics)
```
