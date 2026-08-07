---
Task: t1377_6_column_features_documentation.md
Parent Task: aitasks/t1377_minimonitor_pick_column_action_and_board_column_management.md
Sibling Tasks: aitasks/t1377/t1377_7_manual_verification_column_features.md
Archived Sibling Plans: aiplans/archived/p1377/p1377_1_headless_board_column_seam.md, aiplans/archived/p1377/p1377_2_minimonitor_pick_or_move_to_column.md, aiplans/archived/p1377/p1377_3_minimonitor_create_new_column.md, aiplans/archived/p1377/p1377_4_column_merge_engine.md, aiplans/archived/p1377/p1377_5_board_column_management_dialog.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-07 12:21
---

# p1377_6 — documentation for the new column features

## Context

t1377 landed three user-visible surfaces that no documentation page currently
describes:

- **t1377_2** — minimonitor's `p` (pick by number) confirm dialog now offers
  *move to a board column* alongside *pick*.
- **t1377_3** — that column picker can also **create** a new column.
- **t1377_4 / t1377_5** — the board gained an `e` column-management dialog and
  an N→1 **column merge**.

`website/content/docs/tuis/board/how-to.md`, `board/reference.md` and
`minimonitor/how-to.md` document the *old* surfaces only: board column
operations are listed as palette-or-mouse-only with no key at all, merge is
absent everywhere, and minimonitor's `p` is documented as pick-and-launch. Per
`aidocs/framework/planning_conventions.md` documentation for a user-visible TUI
feature is a first-class child, which is what this task is.

This plan was **re-verified against the landed source**, not against the
sibling plans — children 2/3/5 deviated from their plans in ways that change
what the docs must say (below).

## Verified behaviour (source of truth for the prose)

**Board column-management dialog** — `.aitask-scripts/board/aitask_board.py`

- `Binding("e", "column_manage", "Columns")` (:7013), shown in the footer as
  **Columns**.
- `ColumnManageScreen` (:6322) header reads *"Manage columns — shift+↑/↓
  reorder, Enter edit, Esc close"*; each row (`ColumnManageItem`, :6254) renders
  `position. ██ Title (id) — N tasks`.
- Four buttons: **Add / Edit / Delete / Merge** (:6369-6372). There is no Close
  button — Esc closes.
- Two palette entries (:6615-6618): *"Manage Columns"* and *"Merge Columns"*
  (the latter opens straight into the merge sub-flow).
- **Unavailable in In-Flight / By-Topic / By-Trail** — `check_action` hides `e`
  (:7282) and `_open_column_manage` re-checks and explains via a toast
  (:10532). Those views render derived lanes, not columns.
- The board recomposes **once**, on close, and only if something changed
  (:10539).

**Merge** — `TaskManager.merge_columns` (:2014), `MergeResult` (:1067)

- Flow: **Merge** → multi-select sources (prompt *"Merge FROM"*) → destination
  (*"Merge into"*) → a confirm screen naming the sources, the destination and
  how many tasks move.
- Needs **at least two columns to choose from**, else a warning (:6500).
- Sources are offered via `_work_report_columns`, which includes **Unsorted /
  Inbox only when it holds tasks** (:10473). As a *destination* it is always
  offered unless it is a source (:6518).
- Tasks land **at the bottom of the destination with fresh appended indices**
  (`indices_for_append_run`); **relative order within each source is
  preserved**; sources are processed in board order (:2066).
- Source columns are removed once their tasks land, and the removed ids are
  pruned from the **collapsed-column state** (:2110).
- **Not transactional.** A source is kept whenever any of its members did not
  land, and re-running completes it (:2088). `_report_merge` (:10483) emits
  four distinct outcomes: refused (nothing changed), partial (*re-run to
  finish*), column-list write failed (*re-run the merge to finish*), and
  local-state-only pending (*self-heals on next launch* — do **not** re-run).
- An **unreadable task file blocks source removal** entirely: the toast names
  the files and asks the user to fix them and re-run (:2097).

**Minimonitor `p`** — `.aitask-scripts/monitor/minimonitor_app.py`,
`monitor_shared.py`

- The confirm dialog's button row is **OK** (or **Launch anyway**) ·
  **Move to column** · **Cancel** (`monitor_shared.py`:1124-1138).
- **"Move to column" appears for parent tasks only** — `offers_column_action`
  is `"_" not in task_id` (:1064); the board has no card for a child, and the
  seam refuses a child id.
- `ColumnPickerModal` (:1608) is headed **"Move to Column"**, shows
  `Task: t<id> · now in: <title>`, lists every column including Unsorted, marks
  the current one, and — with `allow_new` — appends a **`＋ New column…`** row.
- `NewColumnTitleModal` (:1748) asks for a title only; a blank title is
  rejected in place. The **colour is auto-assigned** from the palette and the
  new column is **appended to the right end** of the board
  (`lib/board_columns.py:create_column`, :659).
- Feedback: `Moved t<id> → <title>`; picking the current column says
  `t<id> is already in <title>`; a create that lands but whose move fails says
  so explicitly so the user does not create a duplicate (:1733).
- **Multi-session:** the seam runs against `target_root` — the *followed pane's
  own project* (:1598 docstring) — not the minimonitor's own repo.
- The board is not signalled; the move is visible in `ait board` on its next
  refresh.

## Steps

### 1. `website/content/docs/tuis/board/how-to.md` — "How to Customize Columns" (lines 81-102)

Rewrite the lead sentence to name `e` as the primary route, then extend the
operation table (existing columns: Operation | Keyboard | Mouse | Command
palette) so every row that gains a keyboard route says so:

- `Add column` → Keyboard: **e** → **Add**
- `Edit column` → Keyboard: **e** → focus a column → **Enter** (or **Edit**)
- `Delete column` → Keyboard: **e** → focus a column → **Delete**
- `Reorder column` → add **e** → **Shift+Up / Shift+Down** alongside the
  existing Ctrl+Left/Right
- **New row — `Merge columns`**: Keyboard **e** → **Merge**; Command palette
  "Merge Columns"; Mouse —

Then extend the `Notes:` bullet list (plain `Notes:` + bullets, matching the
page — not a blockquote) with, in this order:

1. What the dialog shows (position, colour, title, id, task count) and that
   Esc closes it.
2. Merge semantics: sources are merged in board order; tasks land at the
   **bottom** of the destination with **fresh indices** (they do not keep their
   old ones); **relative order within each source is preserved**; the source
   columns are removed and their collapsed state cleaned up.
3. "Unsorted / Inbox" may be a merge **destination**, and a **source** when it
   holds tasks.
4. **Merge is not transactional** — if it fails part-way the source column
   remains with its unmoved tasks and **re-running the merge completes it**;
   the exception is the "collapsed state was not saved" message, which
   self-heals on the next launch and must not be re-run.
5. Column management is unavailable in the In-Flight / By-Topic / By-Trail
   views, which render derived lanes rather than columns.

### 2. `website/content/docs/tuis/board/reference.md`

**"Column Operations" table (lines 68-75)** — add one row, backticked-key style
to match the table:

| `e` | Open the column management dialog (add, edit, delete, reorder, merge) | Board (not In-Flight / By-Topic / By-Trail) |

Also add the two in-dialog reorder keys (`Shift+Up` / `Shift+Down`, context
"Column manage dialog").

**"Modal Dialogs Reference" table (lines 367-384)** — add four rows near the
existing Column Edit / Column Select rows:

- **Column Manage** — `e` / palette "Manage Columns" — list every column with
  its position, colour, id and task count; Add / Edit / Delete / Merge, and
  Shift+Up/Down to reorder
- **Column Multi-Select (Merge FROM)** — "Merge" in Column Manage, or palette
  "Merge Columns" — pick one or more source columns
- **Column Select (Merge into)** — after choosing sources — pick the
  destination (sources are omitted; Unsorted / Inbox is offered unless it is a
  source)
- **Merge Confirm** — after choosing a destination — names the sources, the
  destination and how many tasks will move

**`boardcol` / `boardidx`** (lines 333-334 and the "Board Data Fields" section,
340-341) — **verified: no edit needed.** Merge assigns fresh appended indices
via the same gap-indexing path the existing prose already describes ("widely
spaced… may be negative… only the relative order is meaningful"). Confirm and
leave as-is rather than adding merge-specific wording.

### 3. `website/content/docs/tuis/minimonitor/how-to.md`

**"How to Pick a Task by Number" (lines 130-142)** — rework step 2/3 and add a
short paragraph:

- Step 2 now lists the three buttons: **OK** (or **Launch anyway**),
  **Move to column**, **Cancel**, plus the kill-followed-agent checkbox.
- Step 3 stays the launch path.
- New paragraph after the checkbox paragraph: choosing **Move to column** opens
  a picker listing the board's columns with the task's current one marked, plus
  a **`＋ New column…`** entry that asks only for a title (the colour is picked
  automatically and the column is appended at the right end of the board). The
  move is written straight to the task file, so it shows up in `ait board` on
  its **next refresh**. In multi-session mode the move targets the **followed
  pane's own project**, not the one minimonitor was started in.
- Note that **Move to column** is offered for parent tasks only — child tasks
  have no board card.

**"Key Bindings Quick Reference" (line 271)** — update the `p` row to:

| `p` | Pick any task by typing its number, then launch it or move it to a board column |

## Conventions

- **Current-state prose only** — no "previously…" / changelog narration
  (`aidocs/framework/documentation_conventions.md`).
- Keys are **bold** in prose, **backticked** in reference tables; the board
  how-to "Customize Columns" table uses bold inside its prose-like cells —
  match the surrounding cell, not a global rule.
- Glyphs and identifiers stay backticked (`` `✎` ``, `` `boardidx` ``).
- No `{{% alert %}}` shortcodes on these pages — a bold-lead blockquote
  (`> **Note:** …`) is the local admonition idiom.
- Generic placeholder project names; no `aidocs/framework/` references from
  user-facing docs.
- Existing pages only — no hand-maintained index list needs updating.

## Verification

```bash
cd website && hugo build --gc --minify
```

- Build succeeds; no broken `relref` links.
- Re-read each edited section against the landed source cited above (the
  implementation is the source of truth, not this plan).
- Grep the three pages for version-history phrasing ("previously", "used to",
  "now also") and remove any that crept in.

## Coordination

Depends on t1377_5, which has landed. t1377_7 (aggregate manual verification)
covers the live TUI checks; this task covers the prose.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes

- **Actual work done:** All three pages edited as planned, nothing else touched.
  `board/how-to.md` — "How to Customize Columns" lead rewritten around `e`, four
  existing operation rows given their keyboard route, a **Merge columns** row
  added, a sixth note on the derived-view restriction, plus a
  `**Merging columns.**` paragraph and a non-transactional `> **Note:**`.
  `board/reference.md` — three rows added to "Column Operations" (`e`,
  `Shift+Up`, `Shift+Down`, `Enter`) and four to "Modal Dialogs Reference"
  (Column Manage, Column Multi-Select (Merge from), Column Select (Merge into),
  Merge Confirm), with the existing **Column Edit** trigger cell extended to
  mention Add/Edit from the manage dialog. `minimonitor/how-to.md` — steps 2/3
  of "How to Pick a Task by Number" rewritten, a
  `**Moving the task to a board column instead.**` paragraph added, and the `p`
  row of the quick reference updated. 25 insertions, 9 deletions.

- **Deviations from plan:** none of substance. Two additions the plan did not
  spell out: the reference "Column Operations" table also gained an `Enter`
  row (edit the focused column) because the dialog's own hint line advertises
  it, and the existing **Column Edit** modal row was amended rather than left
  alone, since Add/Edit are now reachable from the manage dialog and the old
  trigger cell would have been incomplete.

- **Issues encountered:** the plan as written before this session was **stale in
  four places**, because children 2/3/5 deviated during implementation. Verifying
  against the landed source rather than the sibling plans is what caught them:
  1. **The plan's blanket "re-run the merge to finish" advice was wrong for one
     of the four outcomes.** `_report_merge` (`aitask_board.py:10483`) emits four
     distinct messages, and the `<metadata:local>` one means the merge is already
     durable — only the user-local collapsed-state prune is pending, it
     self-heals at next launch, and re-running refuses with `unknown_column`.
     Documenting the single retry rule would have sent users down a path the
     code explicitly refuses.
  2. **`<unverifiable>` — an unreadable task file blocks source removal
     entirely** (`:2097`). Absent from the plan; without it the "source column
     remains" prose looks like a bug rather than a deliberate refusal.
  3. **Column management is unavailable in In-Flight / By-Topic / By-Trail**
     (`check_action` :7282, re-checked in `_open_column_manage` :10532). Absent
     from the plan and the single most likely "why doesn't `e` work?" question.
  4. **"Move to column" is offered for parent tasks only** —
     `offers_column_action` is `"_" not in task_id` (`monitor_shared.py`:1064).
     Absent from the plan.

  A fifth check retired a planned edit: the plan asked to "confirm the
  `boardcol` / `boardidx` descriptions still read correctly after merge exists".
  They do, unchanged — `merge_columns` composes `move_tasks_to_column` and gets
  fresh appended indices from `indices_for_append_run`, which is the same
  gap-indexing path the existing prose already describes. No edit made.

- **Key decisions:**
  - `e` is presented as the *primary* route in the how-to lead and in each
    operation row, rather than as an extra column on the table. Before this
    dialog no column operation had a key at all, so a reader scanning the
    "Keyboard" column previously saw four em-dashes.
  - The merge failure contract is split: the general non-transactional rule sits
    in a `> **Note:**` blockquote (the page's admonition idiom), while the two
    exceptions are named inside it rather than deferred to a table. A table of
    four failure classes would out-weigh the feature on a how-to page.
  - Collapse/expand deliberately stay documented as board-level operations —
    they are not in the manage dialog, and the lead sentence says so.

- **Upstream defects identified:** None

- **Notes for sibling tasks:** t1377_7 (aggregate manual verification) should
  check the four behaviours listed under "Issues encountered" against the live
  TUIs — they are the ones no unit test asserts as *user-visible* and the ones
  this documentation now commits to. In particular the `<metadata:local>` toast
  wording ("self-heals on next launch") is hard to reach by hand; verifying the
  other three is cheap. Anyone re-verifying a t1377 plan should read the landed
  source, not the sibling plans: four of the five things this task documents
  were introduced as deviations during implementation.
