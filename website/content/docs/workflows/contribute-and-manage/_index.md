---
title: "Contribute and Manage Contributions"
linkTitle: "Contributions"
weight: 36
description: "End-to-end guide for sharing changes and managing incoming contributions with aitasks"
---

The aitasks framework provides a complete toolkit for both sides of open-source contribution: **contributors** who want to share improvements, and **maintainers** who need to review, import, and implement those contributions. Four complementary features work together to create a streamlined contribution lifecycle.

## The Four Paths

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
6. The issue includes fingerprint metadata (areas, file paths, change type) that enables automatic overlap detection

**No fork required.** The contributor just makes the change locally and lets the skill package it for maintainer review.

### 4. Review and Import Contributions — `/aitask-contribution-review`

The [`/aitask-contribution-review`](../../skills/aitask-contribution-review/) skill provides AI-powered review of contribution issues. It fetches the target issue, searches for duplicates and related contributions (using fingerprint overlap scores and linked issue references), analyzes code diffs, and recommends whether to merge multiple issues into one task, import individually, fold into existing tasks, or update an existing task directly.

**Who uses it:** Maintainers reviewing incoming contribution issues.

**Flow:**
```
Contribution issue → /aitask-contribution-review → Duplicate check → Overlap analysis
    → AI diff review → Merge/single/fold/update decision → ait issue-import → aitask
```

See [Contribution Flow](contribution-flow/) for the full workflow and technical details.

## End-to-End Contribution Lifecycle

The four features connect to form a complete lifecycle:

```
Contributor's local repo                      Destination repository
──────────────────────                        ──────────────────────

1. Make local modifications
        │
2. /aitask-contribute
        │
3. AI analyzes changes ──────────────────────► Issue created (GH/GL/BB)
   + embeds fingerprint metadata                with fingerprint metadata
                                                       │
                                            3a. CI/CD overlap analysis
                                                (automatic, if configured)
                                                       │
                                               4. /aitask-contribution-review
                                                  - duplicate check
                                                  - related issue search
                                                  - AI diff analysis
                                                       │
                                               5. Import decision
                                                  (merge / single / fold /
                                                   update existing)
                                                       │
                                               6. aitask created (with
                                                  contributor metadata)
                                                       │
                                               7. /aitask-pick
                                                       │
                                               8. Implementation
                                                       │
                                               9. Commit with
                                                  Co-authored-by trailer
                                                       │
                                              10. Issue auto-closed
                                                  with notes
```

## Contributor Attribution

Attribution is preserved throughout the entire lifecycle:

1. **`/aitask-contribute`** — The issue includes the contributor's identity and fingerprint metadata
2. **`/aitask-contribution-review`** — When the maintainer reviews and imports the issue, contributor metadata (`contributor`, `contributor_email`) is extracted and stored in the task's frontmatter
3. **`/aitask-pick`** — During implementation, the task workflow detects contributor metadata and includes a `Co-authored-by` trailer in commit messages:

```
feature: Add portable sed helper (t142)

Co-authored-by: contributor-name <contributor@example.com>
```

This works identically for contributions arriving via PR (`/aitask-pr-import`) or via issue (`/aitask-contribute` + `/aitask-contribution-review`).

For merged contributions (multiple issues imported as one task via `/aitask-contribution-review`):
- The primary contributor (largest diff) gets the `Co-authored-by` trailer
- Additional contributors are listed in the commit body
- All source issue URLs are stored in the task's `related_issues` frontmatter

## Comparison of Contribution Methods

| Aspect | Traditional PR | `/aitask-contribute` workflow |
|--------|---------------|-------------------------------|
| Requires fork | Yes | No |
| Requires branch | Yes | No |
| Code review | Manual PR review | AI-powered analysis + overlap detection |
| Duplicate detection | Manual | Automatic (fingerprint scoring + AI review) |
| Merge | Direct merge or rebase | Re-implemented through aitask workflow |
| Attribution | Git history | `Co-authored-by` trailer (multi-contributor for merged imports) |
| Multiple changes | One PR per change | Multiple issues from one session, grouped automatically |
| Maintainer effort | Review + merge | AI-assisted review → import → implement |

## When to Use Each Path

- **Issue to Task** — For bug reports, feature requests, and general project management
- **PR to Task** — When contributors submit traditional pull requests that need review and re-implementation
- **Contribute Without Forking** — When contributors want to share framework improvements or project-repo changes without the overhead of forking and opening PRs
- **Review and Import Contributions** — When reviewing contribution issues with AI-assisted duplicate detection, overlap analysis, and merge recommendations
