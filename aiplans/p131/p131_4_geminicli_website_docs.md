---
Task: t131_4_geminicli_website_docs.md
Parent Task: aitasks/t131_geminicli_support.md
Sibling Tasks: aitasks/t131/t131_1_*.md, aitasks/t131/t131_2_*.md, aitasks/t131/t131_3_*.md
Worktree: (none — working on current branch)
Branch: (current)
Base branch: main
---

# Plan: Gemini CLI Website Documentation (t131_4)

## Overview

Update the Hugo/Docsy website to document Gemini CLI as a supported agent.

## Step 1: Update installation page

File: `website/content/docs/installation/_index.md`

Add after the "Optional: OpenCode support" section (after line 79):

```markdown
**Optional: Gemini CLI support** (when `ait setup` detects Gemini CLI):

- `.gemini/skills/` — Gemini CLI skill wrappers
- `.gemini/commands/` — Gemini CLI command wrappers
- `GEMINI.md` — aitasks instructions for Gemini CLI
```

## Step 2: Review and update other pages

Check each page that mentions Codex/OpenCode and add Gemini CLI where appropriate:

- `website/content/docs/overview.md` — Check for agent listings
- `website/content/about/_index.md` — Check for agent listings
- `website/content/docs/commands/codeagent.md` — Already covers Gemini CLI (verify, no changes expected)
- `website/content/docs/skills/aitask-refresh-code-models.md` — Check if mentions agents
- `website/content/docs/tuis/settings/` — Check settings docs

## Verification

```bash
cd website && hugo build --gc --minify
```

## Post-Implementation

- Refer to Step 9 (Post-Implementation) in `.claude/skills/task-workflow/SKILL.md`
