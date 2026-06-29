---
Task: t1034_document_anchor_topic_grouping.md
Worktree: .
Branch: current
Base branch: current
---

# t1034: Document Anchor Topic Grouping Outside Workflows

## Summary

Document topic anchoring across concepts, task format, and board docs. Do not add
or edit `website/content/docs/workflows/` pages.

## Key Changes

- Add `website/content/docs/concepts/topic-anchoring.md`.
  - Explain `anchor` as a loose topic-group key for related/follow-up work
    without parent-child structure.
  - Cover `--anchor`, `--followup-of`, root flattening, child inheritance,
    archived-root anchors, and clearing/editing with `aitask_update.sh --anchor`.
  - Include guidance on when to use anchors vs parent-child tasks, `depends`,
    and labels.
- Expand `website/content/docs/development/task-format.md`.
  - Keep the `anchor` frontmatter row concise, but link it to the new concept
    page.
  - Add a short "Topic anchoring" subsection near the frontmatter/schema
    discussion with storage rules and examples.
- Expand board documentation in `website/content/docs/tuis/board/reference.md`.
  - Link the `By-Topic` base-filter row to the concept page.
  - Add concise prose explaining topic lanes, "Ungrouped", archived/absent roots
    as stable lane keys, and the editable anchor field in task detail.
- Update concept navigation/index only if the existing concepts page list is
  manually curated.

## Public Interfaces

No CLI, schema, or runtime changes. This is documentation-only for existing
`anchor`, `--anchor`, `--followup-of`, inherited child anchors,
`aitask_update.sh --anchor`, and board `y By-Topic`.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Verification

- Run `cd website && hugo build --gc --minify`.
- Confirm new `relref` links resolve.

## Step 9 Notes

After implementation and review, run the normal post-implementation workflow:
record review approval, run configured gates/build verification, archive t1034,
and keep code/docs commits separate from task/plan commits.

## Final Implementation Notes

- **Actual work done:** Added `website/content/docs/concepts/topic-anchoring.md`
  as the narrative home for anchor/topic grouping, updated the Concepts index,
  expanded the task-format reference with storage and command rules, and linked
  the Board By-Topic reference to the new concept page.
- **Deviations from plan:** None. Per user direction, no
  `website/content/docs/workflows/` files were added or edited.
- **Issues encountered:** None. `hugo build --gc --minify` completed
  successfully with only pre-existing Hugo deprecation warnings from the theme.
- **Key decisions:** Kept the narrative in Concepts while preserving short
  reference entries in task-format and board docs. Documented current behavior
  from the live scripts: bare stored ids, flattened `--followup-of`, child
  inheritance, archived roots, and `aitask_update.sh --anchor ""` clearing.
- **Upstream defects identified:** None.
