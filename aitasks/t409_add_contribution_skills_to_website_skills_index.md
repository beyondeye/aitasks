---
priority: medium
effort: low
depends: []
issue_type: documentation
status: Ready
labels: [website]
created_at: 2026-03-17 12:35
updated_at: 2026-03-17 12:35
---

## Context

The main skills index page (`website/content/docs/skills/_index.md`) is missing entries for `/aitask-contribute` and `/aitask-contribution-review`. Additionally, `/aitask-pr-import` is currently listed under "Task Management" but should be grouped with the other two contribution skills in a dedicated section.

All three skills have their individual documentation pages already created:
- `website/content/docs/skills/aitask-pr-import.md`
- `website/content/docs/skills/aitask-contribute.md`
- `website/content/docs/skills/aitask-contribution-review.md`

## Implementation Plan

### Step 1: Update the skills index page

In `website/content/docs/skills/_index.md`:

1. **Remove** `/aitask-pr-import` from the "Task Management" table
2. **Add a new "Contributions" section** (between "Task Management" and "Code Review") with a table containing:

| Skill | Description |
|-------|-------------|
| [`/aitask-pr-import`](aitask-pr-import/) | Import a pull request as an aitask with AI-powered analysis and implementation plan |
| [`/aitask-contribute`](aitask-contribute/) | Turn local changes into structured contribution issues for upstream repos |
| [`/aitask-contribution-review`](aitask-contribution-review/) | Analyze contribution issues for duplicates and overlaps, then import as tasks |

### Verification

1. Build the website: `cd website && hugo build --gc --minify`
2. Check the skills index page renders with the new section
3. Verify all three links resolve to their respective doc pages
