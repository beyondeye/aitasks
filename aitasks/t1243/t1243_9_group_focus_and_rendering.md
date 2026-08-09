---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: [t1243_8]
issue_type: feature
status: Implementing
labels: [aitask_board, tui, python, custom_shortcuts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1243
implemented_with: claudecode/opus5
created_at: 2026-07-28 01:16
updated_at: 2026-08-09 12:45
---

## Context

**Child 9 of 14** in the t1243 decomposition (design plan:
`aiplans/p1243_board_task_groups_and_fast_reordering.md` — Workstream C).

Renders the groups whose data model t1243_8 landed, and — the larger half —
generalises the board's focus and navigation seams so a group header is a
first-class focusable thing.

**Anchor re-verification (do this first)** — see t1243_1; anchor on symbol names.

## The problem: declaring `GroupHeader` focusable is not enough

Every focus/nav seam in the board is `TaskCard`-or-placeholder centric
(verified in source):

| Seam | Current behaviour | Effect with a focused header |
|---|---|---|
| `_focused_card()` | `query("TaskCard:focus")` | returns `None` |
| `_get_column_cards` / `_visible_column_cards` | `query(TaskCard)` filtered by `column_id` | vertical nav skips headers entirely |
| `_get_focused_col_id()` | card, else placeholder | returns `None` -> `_nav_lateral` bails to `action_focus_board()`, `_shift_column` no-ops |
| `_column_focus_target()` | visible placeholder, else visible cards | a column of only collapsed groups yields **`None`** -> `_refocus_column` silently does nothing and **focus is lost** |
| all four `_move_task_*` | start from `_focused_card()` | no movement entry point from a header |

## Key files to modify

- `.aitask-scripts/board/aitask_board.py` — new `GroupHeader`;
  `KanbanColumn.compose`; `_focused_card` / `_get_column_cards` /
  `_visible_column_cards` / `_column_focus_target` / `_get_focused_col_id` /
  `_refocus_column`; `action_toggle_children`; the four `_move_task_*`.
- `tests/test_board_group_focus.py` — **new**.

## Reference files for patterns

- `TopicColumn` — the existing swimlane widget and its `ColumnHeader` usage.
- `KanbanColumn.compose` — how `.child-wrapper` rows are emitted as **flat
  siblings** of the parent card; groups take the same shape.
- `_swap_adjacent_cards` / `_card_block` (t1243_5) — the block concept.
- `EmptyColumnPlaceholder` + `CollapsedColumnPlaceholder` — the t1209 one-focus-
  anchor-per-column invariant this child restates.
- `.aitask-scripts/lib/board_groups.py` (t1243_8) — the INV-R derivation; consume
  it, do not re-derive grouping here.

## Implementation plan

### 1. `GroupHeader`

A focusable `Static` rendering `▾ perf work (3)` / `▸ perf work (3)`, **carrying
`column_id`** exactly like `TaskCard`. Members and headers are **flat siblings**
inside `KanbanColumn`, the same shape as `.child-wrapper` rows, so `_card_block`
generalises instead of forking. A collapsed group renders the header alone. A
single-member group renders as a plain card (no header).

### 2. The focus-unit abstraction

- `_focused_unit()` — `query("TaskCard:focus, GroupHeader:focus").first()`.
  `_focused_card()` **survives** as the narrow "focused *task*" accessor that the
  task-level gates genuinely need.
- `_get_column_units` / `_visible_column_units` replace the card-only variants
  for vertical navigation and positional indexing.
- `_column_focus_target` returns a visible placeholder, else the first visible
  **unit**. Restated invariant: *every board column owns exactly one focus
  anchor — a visible placeholder when it shows no units, otherwise its first
  visible unit.*
- `_get_focused_col_id` resolves unit -> placeholder.

### 3. Two different notions of "unit", kept distinct (this is the subtle part)

Expanded child tasks are **also** `TaskCard`s (inside `.child-wrapper`), they are
**already** included in today's `_get_column_cards` / `_column_focus_target`
indexing, and group membership **excludes** them. So:

- **Navigation stops** = every focusable content widget in DOM order:
  `GroupHeader`, member/ungrouped parent `TaskCard`, and expanded child
  `TaskCard`. This preserves today's behaviour.
- **Movement units** = what a movement key acts on: a `GroupHeader` -> the whole
  group; a parent `TaskCard` -> its `_card_block()` (card + its child-wrappers);
  a child `TaskCard` -> **refused**, as today.

### 4. Navigation sequence for the combined case

A grouped parent with visible children:

```
▾ perf work (2)                  <- GroupHeader
    t1243_2  gap indexing        <- member parent
      ↳ t1243_2_1 ...            <- its expanded child
      ↳ t1243_2_2 ...
    t1243_3  render scoping      <- next member
t1229 guard zero-collection      <- next unit (ungrouped)
```

`↓` walks header -> member -> its children in order -> next member -> ... -> the
next unit; `↑` is the exact reverse. `←`/`→` preserve the positional index across
columns via `_column_focus_target(col, preferred_pos)`, indexed over **navigation
stops** — unchanged from today.

### 5. Movement dispatch — settled, no refusal case for units

| Focus | `shift+←/→`, `shift+↑/↓`, `ctrl+↑/↓` |
|---|---|
| `GroupHeader` | moves the **whole group as a block** (implemented in t1243_11; this child wires the dispatch and the focus handling) |
| Member card in an expanded group | moves **only that member**. A lateral move carries its `boardgroup` into the destination column, where it joins a same-slug group if one exists, else renders as a plain single-member group — that falls straight out of the `(column, slug)` derivation, so there is no special case. **Notify** so it is not a surprise. |
| Child card | refused, as today |

### 6. `x` extended

`x` currently toggles children. On a `GroupHeader` it toggles group collapse; on
a parent card it keeps toggling children — one key, "expand/collapse the thing
under focus". Collapsing hides the members **and** their child-wrappers and moves
focus to the header (focus must never be left on an unmounted widget).

### 7. Refocus after every state change

After a filter pass (off a hidden header, via the unit-aware `_refocus_column`);
after collapsing (onto the header); after a block move (onto the header in the
destination); after a member move (onto that card).

### Scope decisions (settled at planning, confirmed with the user)

Three boundaries this decomposition left open. Recorded here because t1243_10 and
t1243_11 inherit them.

1. **Minimal filter awareness lands in this child, not t1243_10.** A collapsed
   group mounts a header and no member cards, so `cols_with_visible` omits the
   column, the `EmptyColumnPlaceholder` flips visible, and `_column_focus_target`
   returns the *placeholder* instead of the header — two focus anchors, breaking
   the very invariant this child restates. So `GroupHeader` becomes a filter unit
   here: visible iff ≥1 member **or ≥1 member's child** matches, counted toward
   `cols_with_visible`, and added to the focus-rescue tuple. t1243_10 still owns
   collapse **persistence**, the lifecycle owners, the prune sweep, the
   match-count badge and the full filtering matrix.
2. **Header movement is a dispatch seam.** t1243_11 owns the model write, so
   "movement from a header moves the block" is not verifiable in this child. This
   child lands the router (`_move_focused_group`) plus the `_apply_group_move`
   seam and the focus contract; t1243_11 fills the seam. The Verification bullet
   above was amended to match **before** implementation began.
3. **Grouped columns fall back to recompose.** `_swap_adjacent_cards` and
   `_transplant_block` assume a card-only column, and a member moved laterally
   carries its `boardgroup` into the destination. When a move touches grouping
   (`_move_needs_recompose`), fall back to `refresh_column(s)`, which re-derives
   the DOM from `build_column_units`. Zero cost until a group exists; t1243_11
   restores the fast path for group blocks.

## Verification

Real Pilot throughout:

- focus and navigation through a column containing **only collapsed groups** —
  the case that motivated the abstraction, and which returns `None` today;
- `↓` / `↑` enter and leave an expanded group correctly;
- `←` / `→` preserve the positional index across columns;
- movement from a header **dispatches** the block move — `_apply_group_move` is
  called with the group's members in order and focus lands on the header
  (t1243_11 implements the model write; see "Scope decision 2" below) — from a
  member moves only that member, from a child is refused;
- refocus lands correctly after collapse, after a block move, after a member move;
- **integration case for a grouped parent with visible children**, pinning the
  header -> member -> children -> next-member -> next-unit sequence, lateral
  positional preservation across it, collapse refocus, and child adjacency after
  a block move;
- a single-member group renders as a plain card with no header;
- `ctrl+left` / `ctrl+right` still resolve the focused column when focus is on a
  header.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-09T09:45:40Z status=pass attempt=1 type=human
