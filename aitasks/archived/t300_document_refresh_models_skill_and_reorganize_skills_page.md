---
priority: medium
effort: low
depends: []
issue_type: documentation
status: Done
labels: [documentation]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-03 13:56
updated_at: 2026-03-03 15:22
completed_at: 2026-03-03 15:22
---

## Context

The `/aitask-refresh-code-models` skill is missing from the website documentation:
- Not listed in the skills overview table (`website/content/docs/skills/_index.md`)
- No dedicated documentation subpage exists

Additionally, the skills overview page lists 15 skills in a flat table with no grouping, making it harder to navigate as the skill count grows.

## Implementation Plan

### 1. Create `/aitask-refresh-code-models` documentation page

Create `website/content/docs/skills/aitask-refresh-code-models.md` documenting:
- Purpose: research latest AI code agent models via web and update `models_*.json` config files
- Supported agents: claudecode, geminicli, codex, opencode
- The 8-step workflow overview (read configs, select agents, research, compare, approve, update, verify URLs, commit)
- Model naming convention (lowercase, underscores, no dots)
- Key behaviors: never auto-removes models, preserves verification scores, syncs seed/ if present
- Relationship to `ait codeagent` and the Settings TUI Models tab
- Example invocation: `/aitask-refresh-code-models`

Reference: `.claude/skills/aitask-refresh-code-models/SKILL.md` for full details.

### 2. Add missing skill to overview table

Add `/aitask-refresh-code-models` entry to the skills table in `website/content/docs/skills/_index.md`.

### 3. Reorganize skills overview into grouped sections

Replace the single flat table with grouped tables. Suggested groups:

**Task Implementation** (core workflow):
- `/aitask-pick`, `/aitask-pickrem`, `/aitask-pickweb`, `/aitask-web-merge`

**Task Management** (create, organize, wrap):
- `/aitask-create`, `/aitask-explore`, `/aitask-fold`, `/aitask-wrap`

**Code Understanding** (explain, review):
- `/aitask-explain`, `/aitask-review`, `/aitask-pr-review`

**Review Guides** (manage review guides):
- `/aitask-reviewguide-classify`, `/aitask-reviewguide-merge`, `/aitask-reviewguide-import`

**Configuration & Reporting** (settings, stats, models):
- `/aitask-refresh-code-models`, `/aitask-stats`, `/aitask-changelog`

Each group gets a `### Group Name` heading followed by its table. The introductory text and "Important" note remain unchanged.

### 4. Also check if `/aitask-web-merge` is missing from the overview table

The file `website/content/docs/skills/aitask-web-merge.md` exists but may not be in the overview table — verify and add if missing.

## Key Files

- **Create:** `website/content/docs/skills/aitask-refresh-code-models.md`
- **Modify:** `website/content/docs/skills/_index.md`
- **Reference:** `.claude/skills/aitask-refresh-code-models/SKILL.md`

## Verification Steps

1. `cd website && hugo build --gc --minify` — site builds without errors
2. New skill page renders and is linked from the overview
3. Grouped tables display correctly in navigation
4. All skill links in the overview resolve to existing pages
