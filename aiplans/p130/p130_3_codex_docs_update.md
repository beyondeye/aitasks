---
Task: t130_3_codex_docs_update.md
Parent Task: aitasks/t130_codecli_support.md
Sibling Tasks: aitasks/t130/t130_1_codex_skill_wrappers.md, aitasks/t130/t130_2_codex_setup_install.md
Archived Sibling Plans: aiplans/archived/p130/p130_1_codex_skill_wrappers.md, aiplans/archived/p130/p130_2_codex_setup_install.md
Worktree: n/a (working on current branch)
Branch: main
Base branch: main
---

# Plan: Update Website Documentation for Codex CLI (t130_3)

## Overview

Add multi-agent invocation documentation to the aitasks website, noting that Codex CLI users invoke skills with `$skill-name` instead of `/skill-name`.

## Step 1: Update main skills page

**File:** `website/content/docs/skills/_index.md`

After line 8 (the intro paragraph about Claude Code skills), add:

```markdown

> **Multi-agent support:** These skills are also available in Codex CLI via
> wrapper skills in `.agents/skills/`. Invoke with `$aitask-pick`,
> `$aitask-create`, etc. Run `ait setup` to install Codex CLI skill wrappers
> when Codex is detected.
```

## Step 2: Update getting started page (optional)

**File:** `website/content/docs/getting-started.md`

Around line 54-70 where it documents `/aitask-pick`, add a brief note:

```markdown
> In Codex CLI, use `$aitask-pick` instead of `/aitask-pick`.
```

## Step 3: Update home page (optional)

**File:** `website/content/_index.md`

Around line 25-26 where it mentions slash commands, add:

```markdown
(or `$skill-name` in Codex CLI)
```

## Verification

- [ ] Website builds: `cd website && hugo build --gc --minify`
- [ ] Skills page shows the multi-agent callout
- [ ] No broken links

## Step 9 Reference

After implementation, follow task-workflow Step 9 for archival and cleanup.
