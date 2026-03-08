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

Update the Hugo/Docsy website to document Gemini CLI as a supported agent, alongside OpenCode and Codex CLI.

## Step 1: Update installation page

File: `website/content/docs/installation/_index.md`

Add a new section: **"Optional: Gemini CLI support"** below the existing OpenCode support section, listing the specific directories (`.gemini/skills/`, `.gemini/commands/`) and instructions (`GEMINI.md`) created during setup.

## Step 2: Update overview page

File: `website/content/docs/overview.md`

Under "Key Features & Architecture", change the bullet point from "- **Claude Code optimized.**" to "- **Multi-Agent Support:** Optimized for Claude Code, with full support for Gemini CLI, Codex CLI, and OpenCode."

## Step 3: Update about page

File: `website/content/about/_index.md`

Update the feature bullet from "**17 Claude Code skills** built-in" to "**17 AI Agent skills** built-in (Claude Code, Gemini CLI, Codex CLI, OpenCode)".

## Step 4: Verify other documentation pages

Verify that other pages (like the TUIs/Settings docs) which list supported agents also include `geminicli`.

## Verification

```bash
cd website && hugo build --gc --minify
```

## Post-Implementation

- Refer to Step 9 (Post-Implementation) in `.claude/skills/task-workflow/SKILL.md`
