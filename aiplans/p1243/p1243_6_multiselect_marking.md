---
Task: t1243_6_multiselect_marking.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_*.md
Parent Plan: aiplans/p1243_board_task_groups_and_fast_reordering.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
---

# t1243_6 — Multi-select marking

> Read `aiplans/p1243_board_task_groups_and_fast_reordering.md` first — it holds
> the verified current-state table, the design decisions and the rejected
> alternatives. The task file `aitasks/t1243/t1243_6_multiselect_marking.md` is the spec;
> this file is the execution order.

## Step 0 — anchor re-verification (every child starts here)

`aitask_board.py` grew 7378 → 9043 lines across six commits while t1243 was
planned, and it keeps moving. Before editing, re-locate every symbol this plan
names and confirm the behaviour still matches the parent plan's table. Anchor on
symbol names; never on line numbers. If a premise has changed, stop and record
it rather than working around it.

## Step 1 — `MarkedSelection`

App-level, keyed by filename, mirroring `brainstorm/utils.py::NodeSelection`
(cursor + marked set; single-item ops use the cursor, multi-item ops use the
set).

## Step 2 — `space`

Add the binding (verified free). Early-return on `_modal_is_active()` —
`SelectionList` modals own `space`. Gate in `check_action` alongside the existing
movement gates (`inflight` / `bytopic` / `bytrail`).

## Step 3 — the glyph, not a border

`TaskCard.on_focus` / `on_blur` set the border imperatively, so a CSS-class mark
would be stomped on every focus change. Render `☑` / `☐` in `.task-title-row`
per t1004: `[bold yellow]☑[/]` marked, `[#6272A4]☐[/]` unmarked, always shown.

## Step 4 — child refusal

`space` on a child card is a no-op **with a notify**, not silence. The
persistence API resolves parents only, so a marked child would be dropped later
without explanation.

## Step 5 — lifecycle and CSS

Clear on view change and refresh; marks survive a filter pass. Add the
`:focus` / `:hover` / `:focus:hover` accent triple the board currently lacks, so
a hovered+focused card never flips to gray.

## Verification

Render assertions for both glyph states; marks survive filtering and clear on
view switch; `space` inert under a modal; child refusal asserted with its reason;
`check_action` hides the binding in the three views.
