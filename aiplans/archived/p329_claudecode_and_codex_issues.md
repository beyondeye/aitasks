---
Task: t329_claudecode_and_codex_issues.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Installation Known Issues Page for Claude Code and Codex CLI

## Overview

Add a dedicated Installation subpage that documents current agent-specific caveats for aitasks users, focused on Claude Code model reliability and Codex CLI workflow constraints, with references and a practical OpenCode alternative.

## Step 1: Add installation subpage

Create `website/content/docs/installation/known-issues.md` with:

- Clear scope that these are integration caveats specific to current aitasks workflows
- Section 1: Claude Code recommendation to avoid medium-effort models for strict workflow compliance
- Section 2: Codex CLI caveats for interactive checkpoints and command approval friction in aitasks workflows
- Section 3: OpenCode as a practical alternative when using OpenAI models with aitasks
- References to official Codex and OpenCode docs plus aitasks integration docs

## Step 2: Link from installation index

Update `website/content/docs/installation/_index.md` to add a link to the new known issues page so users can discover it from the main installation guide.

## Step 3: Verify docs build

Run:

```bash
hugo build --gc --minify
```

from `website/` to confirm the docs site builds cleanly.

## Step 4: Step 9 Reminder

After implementation and review, follow task-workflow Step 9 for archival and post-implementation cleanup.

## Post-Review Changes

### Change Request 1 (2026-03-08 08:02)
- **Requested by user:** Restructure the page into main sections for Claude Code and Codex CLI only, move OpenCode recommendation under Codex CLI, and make language less verbose.
- **Changes made:** Rewrote the page structure to two top-level sections (`Claude Code`, `Codex CLI`) with short issue-focused subsections; moved OpenCode guidance into a Codex subsection and tightened wording throughout.
- **Files affected:** `website/content/docs/installation/known-issues.md`

### Change Request 2 (2026-03-08 08:06)
- **Requested by user:** Remove the "Current Claude Code and Codex CLI caveats" line and reduce subsection heading prominence.
- **Changes made:** Replaced that description with a neutral shorter sentence and downgraded issue headings from `###` to `####` to better match Docsy page hierarchy.
- **Files affected:** `website/content/docs/installation/known-issues.md`

## Final Implementation Notes
- **Actual work done:** Added a new installation subpage at `website/content/docs/installation/known-issues.md` and linked it from `website/content/docs/installation/_index.md`.
- **Deviations from plan:** Initial draft used a separate top-level OpenCode section; after review, restructured to two top-level sections only (Claude Code and Codex CLI) with OpenCode moved under Codex CLI as requested.
- **Issues encountered:** No build or tooling issues. Two user-driven copy/structure revisions were applied.
- **Key decisions:** Kept claims scoped to current `aitasks` integration behavior and cited both official Codex/OpenCode docs and internal mapping references.
- **Build verification:** `hugo build --gc --minify` completed successfully after each revision.
