---
Task: t1377_6_column_features_documentation.md
Parent Task: aitasks/t1377_minimonitor_pick_column_action_and_board_column_management.md
Sibling Tasks: aitasks/t1377/t1377_1_*.md, aitasks/t1377/t1377_2_*.md, aitasks/t1377/t1377_3_*.md, aitasks/t1377/t1377_4_*.md, aitasks/t1377/t1377_5_*.md
Archived Sibling Plans: aiplans/archived/p1377/p1377_*_*.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# p1377_6 — documentation for the new column features

## Goal

Document three user-visible surfaces landed by this parent: the minimonitor
pick-vs-move choice (t1377_2), creating a column from minimonitor (t1377_3), and
the board column-management dialog with merge (t1377_5).

Docs are a **first-class child** here, not a verification afterthought
(`aidocs/framework/planning_conventions.md`).

## Steps

### `website/content/docs/tuis/board/how-to.md`

- "How to Customize Columns" operation table: add the **`e`** column-management
  dialog and a **Merge** row.
- Notes block — merge semantics:
  - merged tasks get **fresh appended indices** in the destination, not their old
    ones;
  - relative order within each source is preserved;
  - the source column's collapsed state is cleaned up;
  - `unordered` ("Unsorted / Inbox") may be a merge **source or destination**.
- **Document that a merge is not transactional.** If it fails part-way, the source
  column remains with its unmoved tasks and re-running the merge completes it. This
  is the user-facing half of t1377_4's retry contract — state it plainly rather than
  letting users discover a half-merged board.

### `website/content/docs/tuis/board/reference.md`

- "Column Operations" table: the `e` binding.
- "Modal Dialogs" table: the Column Manage dialog row.
- Re-read the `boardcol` / `boardidx` descriptions: indices stay widely spaced, may
  be negative, and only relative order is meaningful — confirm nothing merge
  introduces contradicts that.

### `website/content/docs/tuis/minimonitor/how-to.md`

- "How to Pick a Task by Number": the confirm step now offers **pick** or **move to
  a board column**, including creating a new column. Note the move is visible in
  `ait board` on its next refresh, and that in multi-session mode it targets the
  followed pane's **own** project.
- "Key Bindings Quick Reference": update the `p` row.

## Conventions

- **Current-state prose only** — no "previously…" / changelog narration in doc
  bodies (`aidocs/framework/documentation_conventions.md`).
- Generic placeholder project names, never real repositories.
- Do not reference `aidocs/framework/` internals from user-facing docs.
- This child edits existing pages only, so no hand-maintained index list needs
  updating.

## Verification

```bash
cd website && hugo build --gc --minify
```

- Build succeeds; no broken `relref` links.
- **Re-read each edited section against the landed code, not against this plan.**
  Children 2 / 3 / 5 may have deviated during implementation, and a doc written from
  the plan rather than the source is the specific failure this note exists to
  prevent.
- Confirm no version-history phrasing crept in.

## Coordination

Depends on t1377_5, so every documented surface exists by the time this runs.

## Notes for sibling tasks

*(fill in at Step 8.)*
