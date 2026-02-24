---
Task: t236_create_aitaskpickweb_website_documentation_page.md
Branch: main (current branch, no worktree)
---

# Plan: Create aitask-pickweb Website Documentation Page

## Context

The `/aitask-pickweb` skill exists but has no website documentation page. The existing `/aitask-pickrem` page already links to it. This task creates the page following the established pattern.

## Steps

1. Create `website/content/docs/skills/aitask-pickweb.md` with full documentation
2. Update `website/content/docs/skills/_index.md` to add table row
3. Verify with `hugo build`

## Files to Modify

- **Create:** `website/content/docs/skills/aitask-pickweb.md`
- **Edit:** `website/content/docs/skills/_index.md`

## Verification

- `cd website && hugo build --gc --minify`

## Final Implementation Notes
- **Actual work done:** Created `website/content/docs/skills/aitask-pickweb.md` with full documentation following the aitask-pickrem.md pattern. Added entry to skills overview table in `_index.md`. Included comparison tables with both `/aitask-pickrem` and `/aitask-pick`, an ASCII workflow diagram, callout about branch restrictions and recommended pre-locking, and notes about the interactive planning phase.
- **Deviations from plan:** None — implemented as planned.
- **Issues encountered:** None.
- **Key decisions:** Used weight 12 (between pickrem at 11 and explore at 20). Followed the pickrem page structure closely as it's the most similar skill. Included a practical "Suggested Workflow" section with ASCII diagram showing the 3-step local-web-local flow.
