---
Task: t254_ask_about_existing_tasks.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

Task t254 asks to document an interesting workflow: during a Claude Code session (e.g., while implementing a task), a user can ask Claude about **existing** tasks rather than only creating new follow-up tasks. For example, discovering an issue during implementation and asking "are there already tasks for this?" — Claude can search existing tasks, confirm whether one already covers the issue, or update an existing task to address it.

The current follow-up tasks workflow page (`website/content/docs/workflows/follow-up-tasks.md`) only covers **creating** new follow-up tasks. This plan adds sections about **querying and updating** existing tasks.

## Changes

**File:** `website/content/docs/workflows/follow-up-tasks.md`

1. **Update page metadata** — Broaden title/description to cover querying and updating tasks
2. **Update intro paragraph** — Mention querying existing tasks alongside creating new ones
3. **Add "Querying Existing Tasks" section** — Workflow, outcomes, example prompts
4. **Add "Updating Existing Tasks" section** — Enriching partially-matching tasks
5. **Add "Example: Discovering Related Tasks During Implementation" section** — Concrete walkthrough
6. **Update "Advantages" section** — Add bullets about avoiding duplicates and enriching existing tasks

## Verification

- `cd website && hugo build --gc --minify` to verify build
- Visually inspect rendered page structure

## Final Implementation Notes
- **Actual work done:** Updated `website/content/docs/workflows/follow-up-tasks.md` with three new sections (Querying Existing Tasks, Updating Existing Tasks, Example walkthrough) plus updated metadata and advantages. All changes as planned.
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None. Hugo build passed cleanly.
- **Key decisions:** Used a codebrowser-inspired example (t195 keyboard navigation discovering t210 rendering performance) since the original example in the task was cut off. Kept the example concrete with specific task numbers and file references to match the style of other workflow docs.
