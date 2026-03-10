---
title: "Contribute and Manage Contributions"
linkTitle: "Contributions"
weight: 36
description: "End-to-end guide for sharing changes and managing incoming contributions with aitasks"
---

The aitasks framework provides a complete toolkit for both sides of open-source contribution: **contributors** who want to share improvements, and **maintainers** who need to review, import, and implement those contributions. Three complementary features work together to create a streamlined contribution lifecycle.

## The Three Paths

### 1. Issue to Task — `ait issue-import`

Import issues from your issue tracker (GitHub, GitLab, Bitbucket) as structured aitasks, implement them through the standard workflow, and automatically close them with implementation notes.

**Who uses it:** Maintainers managing incoming issues.

**Flow:**
```
Issue tracker → ait issue-import → aitask → /aitask-pick → Implementation → Auto-close issue
```

See the [Issue Tracker workflow](../issue-tracker/) for full details.

### 2. PR to Task — `/aitask-pr-import`

Import pull requests as aitasks with AI-powered code review. Instead of merging PRs directly, extract the contributor's intent and approach, validate against project conventions, and produce a task that goes through the standard implementation cycle — with proper attribution back to the original contributor.

**Who uses it:** Maintainers reviewing incoming PRs.

**Flow:**
```
Pull request → /aitask-pr-import → AI analysis → aitask + plan → /aitask-pick → Implementation
    → Commit (with Co-authored-by) → Archive → PR closed with notes
```

See the [PR Import workflow](../pr-workflow/) for full details.

### 3. Contribute Without Forking — `/aitask-contribute`

The [`/aitask-contribute`](../../skills/aitask-contribute/) skill offers a simpler alternative to the usual fork → branch → PR flow. It helps contributors package local changes into a structured issue that a maintainer can later import as an aitask.

**Who uses it:** Contributors who want to share improvements with the `aitasks` framework or with a project repository that uses aitasks.

**How it works:**
1. The contributor makes local changes in the framework repo or in a project repo that uses aitasks
2. Running `/aitask-contribute` helps select the relevant area and files
3. AI analyzes the diffs and prepares a concise contribution summary
4. The contributor reviews the proposal, adds motivation, and confirms
5. A structured issue is created on the destination repository (GitHub, GitLab, or Bitbucket)

**No fork required.** The contributor just makes the change locally and lets the skill package it for maintainer review.

## End-to-End Contribution Lifecycle

The three features connect to form a complete lifecycle:

```
Contributor's local repo                      Destination repository
──────────────────────                        ──────────────────────

1. Make local modifications
        │
2. /aitask-contribute
        │
3. AI analyzes changes ──────────────────────► Issue created (GH/GL/BB)
                                                       │
                                               4. ait issue-import
                                                       │
                                               5. aitask created (with
                                                  contributor metadata)
                                                       │
                                               6. /aitask-pick
                                                       │
                                               7. Implementation
                                                       │
                                               8. Commit with
                                                  Co-authored-by trailer
                                                       │
                                               9. Issue auto-closed
                                                  with notes
```

## Contributor Attribution

Attribution is preserved throughout the entire lifecycle:

1. **`/aitask-contribute`** — The issue includes the contributor's identity in its metadata
2. **`ait issue-import`** — When the maintainer imports the issue, contributor metadata (`contributor`, `contributor_email`) is extracted and stored in the task's frontmatter
3. **`/aitask-pick`** — During implementation, the task workflow detects contributor metadata and includes a `Co-authored-by` trailer in commit messages:

```
feature: Add portable sed helper (t142)

Co-authored-by: contributor-name <contributor@example.com>
```

This works identically for contributions arriving via PR (`/aitask-pr-import`) or via issue (`/aitask-contribute` + `ait issue-import`).

## Comparison of Contribution Methods

| Aspect | Traditional PR | `/aitask-contribute` |
|--------|---------------|---------------------|
| Requires fork | Yes | No |
| Requires branch | Yes | No |
| Code review | Manual PR review | AI-powered analysis on import |
| Merge | Direct merge or rebase | Re-implemented through aitask workflow |
| Attribution | Git history | `Co-authored-by` trailer |
| Multiple changes | One PR per change | Multiple issues from one session |
| Maintainer effort | Review + merge | Import + implement (guided by AI) |

## When to Use Each Path

- **Issue to Task** — For bug reports, feature requests, and general project management
- **PR to Task** — When contributors submit traditional pull requests that need review and re-implementation
- **Contribute Without Forking** — When contributors want to share framework improvements or project-repo changes without the overhead of forking and opening PRs
