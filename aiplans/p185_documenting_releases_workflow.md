---
Task: t185_documenting_releases_workflow.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Document the Releases Workflow (t185)

## Context

Every open-source project needs release notes, and writing them manually is tedious. The aitasks framework already generates structured data during regular development (commit messages with task IDs, archived plan files with implementation notes). This documentation page explains how the `/aitask-changelog` skill, `create_new_release.sh`, and GitHub Actions form an integrated pipeline that turns this data into published release notes automatically.

## What to Create

**Single new file:** `website/content/docs/workflows/releases.md`

No existing files need modification — Hugo auto-discovers the page from frontmatter.

## Content Structure

### Frontmatter
- `title: "Releases Workflow"`, `linkTitle: "Releases"`, `weight: 80`
- Weight 80 places it after code-review (70) and exploration-driven (75) — logical since releasing is the final development step

### Sections

1. **Opening paragraph** — Frame the problem (release notes are tedious) and the solution (aitasks generates them from existing task data). Include the key insight: regular development with `/aitask-pick` automatically creates raw material for release notes.

2. **The Release Pipeline** — Brief 3-step numbered overview:
   - Generate changelog with `/aitask-changelog`
   - Create release with `./create_new_release.sh`
   - GitHub Actions publishes automatically

3. **Walkthrough: Releasing v0.4.0** — Concrete example using aitasks' own v0.4.0 release:
   - **Step 1: Generate the changelog** — Run `/aitask-changelog`, show how it gathers data (commits since last tag, task IDs, archived plans), AI generates summaries grouped by issue type. Show a real CHANGELOG.md excerpt.
   - **Step 2: Create the release** — Run `./create_new_release.sh`, show the terminal interaction (version prompt, changelog validation, tag creation, push).
   - **Step 3: GitHub Actions publish** — Explain the automated steps: version verification, tarball creation, changelog extraction for release notes, documentation site deployment.

4. **Where the Data Comes From** — Explain the data pipeline: `/aitask-pick` commits carry `(tNN)` IDs, archived plans have "Final Implementation Notes", `ait changelog --gather` harvests both, `/aitask-changelog` summarizes with AI. Include a text flow diagram.

5. **Tips** — Practical advice: run changelog before release, review AI summaries, post-release `ait zip-old` cleanup.

### Cross-references
- `[/aitask-changelog](../../skills/aitask-changelog/)`
- `[/aitask-pick](../../skills/aitask-pick/)`
- `[ait changelog](../../commands/issue-integration/#ait-changelog)`
- `[Release Process](../../development/#release-process)`

## Style
- Match existing workflow pages (issue-tracker.md, code-review.md): narrative + code blocks, concise user-focused language
- Approximately 100-120 lines
- No screenshots/images needed

## Verification
- Preview locally: `cd website && hugo server` → check `/aitasks/docs/workflows/releases/`
- Verify page appears in sidebar under Workflows section
- Verify all cross-reference links resolve correctly

## Final Implementation Notes
- **Actual work done:** Created `website/content/docs/workflows/releases.md` (113 lines) documenting the full releases pipeline. Followed the plan exactly — all five sections implemented as designed.
- **Deviations from plan:** None. The page structure, content, and cross-references match the plan.
- **Issues encountered:** None. Straightforward single-file documentation task.
- **Key decisions:** Used weight 80 to place after all implementation-focused workflow pages. Used real v0.4.0 changelog excerpts as concrete examples. Included both GitHub Actions workflows (release.yml and hugo.yml) in the walkthrough.
