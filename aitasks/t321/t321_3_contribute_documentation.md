---
priority: medium
effort: low
depends: [4]
issue_type: documentation
status: Implementing
labels: [auto-update]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-08 09:36
updated_at: 2026-03-08 22:03
---

## Context

This is child task 4 of t321 (aitask-contribute skill). It creates the website documentation page for the `/aitask-contribute` skill and updates the overview.md reference that currently claims an "AI agent-based framework update skill" exists.

## Key Files to Create

- `website/content/docs/skills/aitask-contribute.md` — new documentation page

## Key Files to Modify

- `website/content/docs/overview.md` — line 49, update the reference from vague "included AI agent-based framework update skill" to a proper link to `/aitask-contribute`

## Reference Files for Patterns

- `website/content/docs/skills/aitask-pr-import.md` — documentation page format to follow
- `website/content/docs/overview.md` — the file to modify (line 49)
- `.claude/skills/aitask-contribute/SKILL.md` (created in t321_3) — source of truth for workflow description

## Implementation Plan

### Step 1: Create skill documentation page

Create `website/content/docs/skills/aitask-contribute.md` following the format of `aitask-pr-import.md`:

```yaml
---
title: "/aitask-contribute"
linkTitle: "/aitask-contribute"
weight: <appropriate number>
description: "Contribute local framework changes back to the upstream aitasks repository"
---
```

Document:
- Overview of the skill and its purpose
- Two contribution modes (downstream project vs clone/fork)
- Available contribution areas (scripts, claude skills, gemini, codex, opencode, website)
- The 7-step workflow
- Multi-contribution support (separate issues for distinct changes)
- Contributor attribution (how Co-authored-by works when the issue is later imported)
- The fact that this is an alternative to creating a traditional pull request

### Step 2: Update overview.md

Change line 49 from:
```
...with the included AI agent-based framework update skill.
```
To:
```
...with the included [/aitask-contribute]({{< relref "skills/aitask-contribute" >}}) skill.
```

## Verification Steps

- `cd website && hugo build --gc --minify` succeeds (no broken links)
- The overview.md link resolves correctly to the new page
- Documentation page renders correctly with all sections
