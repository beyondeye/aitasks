---
title: "Contribute and Manage Contributions"
linkTitle: "Contributions"
weight: 36
description: "End-to-end guide for contributing to and managing contributions for open-source projects using aitasks"
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

The [`/aitask-contribute`](../../skills/aitask-contribute/) skill offers an alternative to the traditional fork → branch → PR contribution model. Contributors simply make their modifications locally and the skill handles the rest:

**Who uses it:** Contributors who want to share improvements with the upstream project.

**How it works:**
1. The contributor modifies framework files locally (scripts, skills, website, etc.)
2. Running `/aitask-contribute` detects what changed compared to upstream
3. AI analyzes the diffs, identifies logical groups, and proposes titles and scope
4. The contributor reviews, adds motivation, and confirms
5. A structured GitHub issue is created on the upstream repository with embedded diffs, motivation, scope, and merge approach

**No fork required.** No branch to create, no PR to open. The contributor just makes changes and the skill creates a detailed issue that the maintainer can import as an aitask.

## End-to-End Contribution Lifecycle

The three features connect to form a complete lifecycle:

```
Contributor's project                          Upstream repository
─────────────────────                          ────────────────────

1. Make local modifications
        │
2. /aitask-contribute
        │
3. AI analyzes changes ──────────────────────► GitHub issue created
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
- **Contribute Without Forking** — When contributors want to share framework improvements without the overhead of forking and creating PRs. Especially useful for downstream projects that have customized their aitasks installation
