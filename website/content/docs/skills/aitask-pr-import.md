---
title: "/aitask-pr-import"
linkTitle: "/aitask-pr-import"
weight: 22
description: "Analyze a pull request and create an aitask with implementation plan"
---

Analyze pull requests from GitHub, GitLab, or Bitbucket using AI-powered code review, then create a well-structured aitask with contributor attribution. This skill bridges external contributions and the aitasks workflow — instead of merging PRs directly, it extracts the intent and approach, validates them against the codebase, and produces a task ready for implementation.

**Usage:**
```
/aitask-pr-import
```

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.
>
> **Codex CLI note:** When continuing from this skill into implementation, in Codex wrappers, after implementation, most of the times you will need to explicitly tell the agent to continue the workflow because `request_user_input` is only available in plan mode. Example prompts: `Good, now finish the workflow` or `Good, now continue`.

## Step-by-Step

1. **Profile selection** — Same profile system as `/aitask-pick`
2. **PR selection** — Choose how to select a pull request:
   - *Enter PR number* — Fetches PR data directly from the platform
   - *Browse open PRs* — Lists open PRs via [`ait pr-import --list`](../../commands/pr-import/#ait-pr-import) and presents them for selection
   - *Use existing PR data* — Select from previously extracted `.aitask-pr-data/*.md` files
3. **PR analysis** — AI-powered analysis of the pull request covering:
   - Purpose and intent behind the PR
   - Proposed solution and implementation approach
   - Code quality assessment (test coverage, edge cases, error handling)
   - Concerns (breaking changes, security, missing tests)
   - Codebase alignment (does the approach match existing conventions?)
4. **Interactive Q&A** — Explore specific aspects of the PR, ask questions about the codebase, or continue analyzing. Loop until satisfied
5. **Related task discovery** — Scans pending tasks for overlap with the PR scope. Related tasks can be "folded in" — their content is incorporated into the new task, and originals are deleted when the task is archived
6. **Task creation** — Creates the task with PR metadata (`pull_request`, `contributor`, `contributor_email`), AI-generated description, implementation approach, and folded task references
7. **Decision point** — Save the task for later (default) or continue directly to implementation via the standard task workflow

## Key Capabilities

- **Multi-platform PR support** — GitHub, GitLab, and Bitbucket Cloud. Auto-detected from git remote
- **Structured intermediate data** — Uses [`ait pr-import --data-only`](../../commands/pr-import/#ait-pr-import) to extract PR metadata, description, comments, reviews, changed files, and diff into a structured format for analysis
- **Codebase-aware analysis** — Explores the actual codebase during analysis to compare the PR approach against existing patterns and conventions
- **Related task folding** — Discovers pending tasks that overlap with the PR scope. Selected tasks are folded in, avoiding duplicate work
- **Contributor attribution** — Stores contributor username and email in task metadata. During implementation, the task workflow uses this for `Co-authored-by` commit trailers
- **Automated PR lifecycle** — After the task is implemented and archived via [`/aitask-pick`](../aitask-pick/), the task workflow automatically offers to close/decline the source PR with implementation notes

**Profile key:** `explore_auto_continue` — Set to `true` to skip the "save for later or continue" prompt and automatically proceed to implementation.

## Workflows

For a full workflow guide covering the motivation and end-to-end flow, see [PR Import Workflow](../../workflows/pr-workflow/).
