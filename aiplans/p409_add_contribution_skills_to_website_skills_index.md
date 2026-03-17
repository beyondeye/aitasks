---
Task: t409_add_contribution_skills_to_website_skills_index.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

The website skills index page (`website/content/docs/skills/_index.md`) lists all skills in categorized tables but is missing `/aitask-contribute` and `/aitask-contribution-review`. Additionally, `/aitask-pr-import` is in "Task Management" but logically belongs with the other two contribution skills.

## Plan

**File:** `website/content/docs/skills/_index.md`

### Step 1: Remove `/aitask-pr-import` from "Task Management" table (line 39)

Delete this row:
```
| [`/aitask-pr-import`](aitask-pr-import/) | Import a pull request as an aitask with AI-powered analysis and implementation plan |
```

### Step 2: Add new "Contributions" section between "Task Management" and "Code Review"

Insert after the Task Management table (after line 40):

```markdown
### Contributions

Import external work and contribute changes back.

| Skill | Description |
|-------|-------------|
| [`/aitask-pr-import`](aitask-pr-import/) | Import a pull request as an aitask with AI-powered analysis and implementation plan |
| [`/aitask-contribute`](aitask-contribute/) | Turn local changes into structured contribution issues for upstream repos |
| [`/aitask-contribution-review`](aitask-contribution-review/) | Analyze contribution issues for duplicates and overlaps, then import as tasks |
```

## Verification

1. `cd website && hugo build --gc --minify` — confirm no build errors
2. Check rendered page has four sections: Task Implementation, Task Management, Contributions, Code Review, Configuration & Reporting

## Final Implementation Notes
- **Actual work done:** Moved `/aitask-pr-import` from Task Management section and created a new "Contributions" section with all three contribution skills (`/aitask-pr-import`, `/aitask-contribute`, `/aitask-contribution-review`)
- **Deviations from plan:** None — implemented exactly as planned
- **Issues encountered:** None
- **Key decisions:** Placed "Contributions" section between "Task Management" and "Code Review" for logical grouping
