---
Task: t321_3_contribute_documentation.md
Parent Task: aitasks/t321_removeautoupdatefromdocsorimplement.md
Sibling Tasks: aitasks/t321/t321_1_*.md, aitasks/t321/t321_2_*.md, aitasks/t321/t321_4_*.md, aitasks/t321/t321_5_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t321_3 — Documentation

## Overview

Create the website documentation page for `/aitask-contribute` and update the overview.md reference.

## Steps

### 1. Create skill documentation page

Create `website/content/docs/skills/aitask-contribute.md` following the format of `website/content/docs/skills/aitask-pr-import.md`.

Content should cover:
- What the skill does (contribute local framework changes via structured GitHub issues)
- Two modes: downstream project mode vs clone/fork mode
- Available contribution areas (scripts, claude skills, gemini, codex, opencode, website)
- The 7-step interactive workflow
- Multi-contribution support (separate issues for distinct changes)
- Contributor attribution flow (how Co-authored-by is preserved when issue is imported)
- Note: this is an alternative to traditional pull requests

### 2. Update overview.md

Change line 49 in `website/content/docs/overview.md`:

**From:**
```
...with the included AI agent-based framework update skill.
```

**To:**
```
...with the included [/aitask-contribute]({{< relref "skills/aitask-contribute" >}}) skill.
```

## Key Files

- **Create:** `website/content/docs/skills/aitask-contribute.md`
- **Modify:** `website/content/docs/overview.md` (line 49)
- **Reference:** `website/content/docs/skills/aitask-pr-import.md` (format pattern)
- **Reference:** `.claude/skills/aitask-contribute/SKILL.md` (created in t321_4) — workflow to document

## Verification

- `cd website && hugo build --gc --minify` succeeds
- The overview.md link resolves correctly
- Documentation page renders with all sections

## Step 9 Reference
Post-implementation: archive task via task-workflow Step 9.
