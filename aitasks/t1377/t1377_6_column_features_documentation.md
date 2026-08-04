---
priority: medium
effort: low
depends: [t1377_5]
issue_type: documentation
status: Ready
labels: [documentation, web_site, aitask_board, aitask_monitormini]
gates: [risk_evaluated]
anchor: 1243
created_at: 2026-08-04 09:56
updated_at: 2026-08-04 09:56
---

## Context

t1377 adds three user-visible surfaces: a pick-vs-move-to-column choice in
minimonitor (t1377_2), creating a column from minimonitor (t1377_3), and a
column-management dialog with **merge** in the board (t1377_5). Per
`aidocs/framework/planning_conventions.md`, documentation for a user-visible TUI
feature is a **first-class child**, not a verification afterthought.

## Key Files to Modify

- **`website/content/docs/tuis/board/how-to.md`**
- **`website/content/docs/tuis/board/reference.md`**
- **`website/content/docs/tuis/minimonitor/how-to.md`**

## Reference Files for Patterns

- `aidocs/framework/documentation_conventions.md` — the **current-state-only** rule
  (no version history in doc bodies), and genericising any passage that names the
  supported coding agents.
- The existing "How to Customize Columns" table in `board/how-to.md` — the
  operation / keyboard / mouse / command-palette matrix to extend.
- `board/reference.md` "Column Operations" and "Modal Dialogs" tables, and the
  `boardcol` / `boardidx` frontmatter descriptions.
- `minimonitor/how-to.md` "How to Pick a Task by Number" plus its "Key Bindings
  Quick Reference" table.

## Implementation Plan

### `board/how-to.md`

- Add the `e` column-management dialog to the "How to Customize Columns" operation
  table, and a **Merge** row.
- Extend the notes block with merge semantics: merged tasks receive **fresh
  appended indices** in the destination (not their old ones), relative order within
  each source is preserved, and the source column's collapsed state is cleaned up.
- Document that a merge is **not transactional**: if it fails part-way the source
  column remains with its unmoved tasks and re-running the merge completes it. This
  is the user-facing half of t1377_4's retry contract — say it plainly rather than
  leaving users to discover a half-merged board.
- Note that `unordered` ("Unsorted / Inbox") can be a merge source or destination.

### `board/reference.md`

- "Column Operations" table: the `e` binding.
- "Modal Dialogs" table: the Column Manage dialog row.
- Confirm the `boardcol` / `boardidx` descriptions still read correctly after merge
  exists — in particular that indices remain widely spaced and may be negative, and
  that only relative order is meaningful.

### `minimonitor/how-to.md`

- "How to Pick a Task by Number": the confirm step now offers **pick** or **move to
  a board column**, including creating a new column. Note that the move is visible
  in `ait board` on its next refresh, and that in multi-session mode the move
  targets the followed pane's own project.
- "Key Bindings Quick Reference": update the `p` row.

### Conventions

- Current-state prose only — no "previously…" / changelog narration in doc bodies.
- Use generic placeholder project names, never the author's real repositories.
- Do not reference `aidocs/framework/` internals from user-facing docs.
- If a new page were added, `website/content/docs/workflows/_index.md`-style index
  lists are hand-maintained — but this child only edits existing pages, so no index
  edit is expected.

## Verification Steps

```bash
cd website && hugo build --gc --minify
```

- Build succeeds with no broken `relref` links.
- Manually re-read each edited section against the landed code (not against this
  task's prose — the implementation is the source of truth, and children 2/3/5 may
  have deviated).
- Confirm no version-history phrasing crept in.

## Coordination

Depends on t1377_5, so every documented surface exists by the time this runs.
Re-read the landed implementations before writing — a doc written from the plan
rather than the code is the specific failure mode this note exists to prevent.
