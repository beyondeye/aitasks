---
Task: t321_4_contribute_skill_and_wrappers.md
Parent Task: aitasks/t321_removeautoupdatefromdocsorimplement.md
Sibling Tasks: aitasks/t321/t321_1_*.md, aitasks/t321/t321_2_*.md, aitasks/t321/t321_3_*.md, aitasks/t321/t321_5_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t321_4 — Claude Code Skill + Agent Wrappers

## Overview

Create the Claude Code skill definition (source of truth) and all agent wrappers for `/aitask-contribute`.

## Steps

### 1. Create Claude Code skill

Create `.claude/skills/aitask-contribute/SKILL.md` with the 7-step interactive workflow:

**Frontmatter:**
```yaml
---
name: aitask-contribute
description: Contribute local aitasks framework changes back to the upstream repository by opening structured GitHub issues.
user-invocable: true
---
```

**Step 1: Prerequisites check**
- Verify `gh` CLI + authentication
- Run `./.aitask-scripts/aitask_contribute.sh --list-areas`
- Parse output: first line `MODE:<clone|downstream>`, then `AREA|<name>|<dirs>|<description>` lines
- Inform user of detected mode

**Step 2: Area selection**
- AskUserQuestion multiSelect with areas from step 1
- Filter `website` for downstream mode

**Step 3: File discovery**
- Run `--list-changes --area <area>` for each selected area
- Present changed files via AskUserQuestion multiSelect

**Step 4: Upstream diff + AI analysis**
- Run `--dry-run` with placeholder metadata to get diff output
- AI analyzes changes, summarizes purpose

**Step 5: Contribution grouping**
- If multiple distinct changes, suggest groups
- AskUserQuestion to confirm/adjust

**Step 6: Motivation & scope per contribution**
- AskUserQuestion for: title, motivation, scope, merge approach

**Step 7: Review & confirm → create issue(s)**
- Show preview, confirm, run script without `--dry-run`
- Display issue URLs

### 2. Create Gemini CLI wrapper

**`.gemini/skills/aitask-contribute/SKILL.md`** — copy pattern from `.gemini/skills/aitask-pr-import/SKILL.md`:
- Reference planmode prereqs, tool mapping, source SKILL.md

**`.gemini/commands/aitask-contribute.md`** — copy pattern from `.gemini/commands/aitask-pr-import.md`:
- Reference tool mapping + prereqs + source SKILL.md

### 3. Create Codex CLI wrapper

**`.agents/skills/aitask-contribute/SKILL.md`** — copy pattern from `.agents/skills/aitask-pr-import/SKILL.md`:
- Reference interactive prereqs, tool mapping, source SKILL.md

### 4. Create OpenCode wrapper

**`.opencode/skills/aitask-contribute/SKILL.md`** — copy pattern from `.opencode/skills/aitask-pr-import/SKILL.md`:
- Reference planmode prereqs, tool mapping, source SKILL.md

**`.opencode/commands/aitask-contribute.md`** — copy pattern from `.opencode/commands/aitask-pr-import.md`

## Key Files

- **Create:** `.claude/skills/aitask-contribute/SKILL.md`
- **Create:** `.gemini/skills/aitask-contribute/SKILL.md`, `.gemini/commands/aitask-contribute.md`
- **Create:** `.agents/skills/aitask-contribute/SKILL.md`
- **Create:** `.opencode/skills/aitask-contribute/SKILL.md`, `.opencode/commands/aitask-contribute.md`
- **Reference:** All corresponding `aitask-pr-import` wrapper files for each platform

## Verification

- SKILL.md has valid YAML frontmatter
- All wrapper files reference correct paths
- `/aitask-contribute` appears in Claude Code skill list
- Wrapper directory structure matches existing skills

## Step 9 Reference
Post-implementation: archive task via task-workflow Step 9.
