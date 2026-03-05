---
Task: t317_document_codex_post_implementation_explicit_continue_require.md
Worktree: (none — working on current branch)
Branch: (none — working on current branch)
Base branch: main
---

# Plan: Document Codex Post-Implementation Explicit Continue Requirement (t317)

## Summary

Update skill documentation pages that embed the shared task workflow so Codex users know that, after implementation, they will often need to explicitly ask the agent to continue review/finalization/archive steps.

## Implementation Changes

1. Add a Codex-specific callout note to the seven target skill docs:
   - `website/content/docs/skills/aitask-pick/_index.md`
   - `website/content/docs/skills/aitask-pickrem.md`
   - `website/content/docs/skills/aitask-pickweb.md`
   - `website/content/docs/skills/aitask-explore.md`
   - `website/content/docs/skills/aitask-fold.md`
   - `website/content/docs/skills/aitask-review.md`
   - `website/content/docs/skills/aitask-pr-import.md`
2. Use the agreed wording: "after implementation, most of the times you will need..."
3. Use the agreed prompt examples only:
   - `Good, now finish the workflow`
   - `Good, now continue`
4. In `/aitask-pick`, also add an explicit reminder in Step 10 (Post-implementation).

## Verification

- `rg` confirmation that the new phrasing and prompt examples exist in all seven files.
- Hugo docs build:
  - `hugo --gc --minify` (from `website/`) passes.

## Final Implementation Notes

- **Actual work done:** Added Codex continuation guidance to all requested skill docs and added the extra `/aitask-pick` post-implementation reminder.
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Kept wording exactly aligned with user edits ("most of the times you will need") and limited examples to the two short prompts requested.
