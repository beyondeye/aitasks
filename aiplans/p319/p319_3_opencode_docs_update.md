---
Task: t319_3_opencode_docs_update.md
Parent Task: aitasks/t319_opencode_support.md
Sibling Tasks: aitasks/t319/t319_1_opencode_skill_wrappers.md, aitasks/t319/t319_2_opencode_setup_install.md, aitasks/t319/t319_4_opencode_model_discovery.md
Archived Sibling Plans: (check aiplans/archived/p319/ at implementation time)
Worktree: (none - working on current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Update Website Documentation for OpenCode Support

## Overview

Update website pages to document OpenCode support alongside Codex CLI. OpenCode uses `/skill-name` via its native `skill` tool (same syntax as Claude Code) and has native `ask` (no plan mode constraint).

## Step 1: Read the Codex docs update plan for reference

Read `aiplans/archived/p130/p130_3_codex_docs_update.md` to understand which pages were updated for Codex and what changes were made. Apply the same pattern for OpenCode.

## Step 2: Update skills page

**File:** `website/content/docs/skills/_index.md`

- Update the multi-agent callout block to include OpenCode:
  - OpenCode wrappers installed in `.opencode/skills/`
  - Invoke skills with `/aitask-pick` (same syntax as Claude Code, via native `skill` tool)
  - No plan mode requirement (OpenCode's `ask` works in all modes — unlike Codex)
- Update the intro line that lists supported agents

## Step 3: Update home page

**File:** `website/content/_index.md`

- Update the "Code Agent Integration" feature card to mention OpenCode alongside Claude Code and Codex
- Add release note for OpenCode support

## Step 4: Check for other pages

Based on the t130_3 plan, identify any additional pages that were updated for Codex support and apply the same OpenCode additions. Likely candidates:
- Getting started or installation pages
- Any "multi-agent" or "code agent" documentation
- Setup/configuration docs

## Step 5: Verify website builds

```bash
cd website && hugo build --gc --minify
```

## Step 6: Commit

```bash
git add website/
git commit -m "documentation: Add OpenCode support to website docs (t319_3)"
```

## Verification

- [ ] Website builds without errors
- [ ] OpenCode mentioned on skills page (`website/content/docs/skills/_index.md`)
- [ ] OpenCode mentioned on home page (`website/content/_index.md`)
- [ ] All pages that mention Codex CLI also mention OpenCode where appropriate
- [ ] Correct invocation syntax documented (`/skill-name` via native `skill` tool)

## Post-Implementation: Step 9

Follow task-workflow Step 9 for archival.
