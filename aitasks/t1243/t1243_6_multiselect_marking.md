---
priority: high
effort: medium
depends: [t1243_5]
issue_type: feature
status: Implementing
labels: [aitask_board, tui, python, custom_shortcuts]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1243
created_at: 2026-07-28 01:14
updated_at: 2026-08-04 09:28
---

## Context

**Child 6 of 14** in the t1243 decomposition (design plan:
`aiplans/p1243_board_task_groups_and_fast_reordering.md` — Workstream D).

The board has **no selection state at all** today — no marking, no multi-select
anywhere. Every later bulk command (t1243_7 move-to-column, t1243_12 group
membership) operates on a marked set, so this child lands the primitive.

**Anchor re-verification (do this first)** — see t1243_1; anchor on symbol names.

## Key files to modify

- `.aitask-scripts/board/aitask_board.py` — new `MarkedSelection`, `KanbanApp`
  `BINDINGS` + `check_action`, `TaskCard.compose`, `KanbanApp.CSS`.
- `tests/test_board_marking.py` — **new**.

## Reference files for patterns

- `.aitask-scripts/brainstorm/utils.py` `NodeSelection` — the model to mirror: a
  `primary` cursor plus a `marked` set, with the documented rule that SINGLE-item
  operations act on `primary` and MULTI-item operations act on `marked`.
- `.aitask-scripts/brainstorm/brainstorm_app.py` `action_browse_mark` — the
  `space` handler, including the `isinstance(self.screen, ModalScreen)`
  early-return (the board's equivalent is `_modal_is_active()`).
- `.aitask-scripts/brainstorm/widgets.py` `NodeRow.render` and
  `.aitask-scripts/monitor/monitor_shared.py` `_ConcernRow.render` — the t1004
  glyph convention.
- `.aitask-scripts/brainstorm/styles.py` — the `:focus` / `:hover` /
  `:focus:hover` accent triple.

## Implementation plan

### 1. `MarkedSelection`

App-level, keyed by **filename** (the board's card identity, alongside
`column_id`). Mirror `NodeSelection`: cursor + marked set, `toggle`, `clear`,
`cardinality`.

### 2. `space` binding

`space` is **free** in `KanbanApp.BINDINGS` (verified). Add it, gated:

- early-return when `_modal_is_active()` — `SelectionList`-based modals use
  `space` for their own toggling;
- `check_action` hides/disables it wherever movement is already hidden
  (`inflight`, `bytopic`, `bytrail` base filters).

### 3. Glyph, not border (NON-NEGOTIABLE)

`TaskCard.on_focus` / `on_blur` set `self.styles.border` **imperatively**, so a
CSS-class "marked" border would be stomped on every focus change. Render the mark
as a glyph in the card's `.task-title-row`, per t1004:

- marked: `[bold yellow]☑[/]`
- unmarked: `[#6272A4]☐[/]`
- **always shown**, never a dot, same glyph in every surface.

### 4. Child tasks are excluded — explicitly, not silently

Every movement action already early-returns on `focused.is_child`,
`check_action` hides movement for child cards, and
`TaskManager.move_task_col` resolves `self.task_datas` (**parents only**) — a
marked child handed to the persistence API would be silently ignored. So:

`space` on a child card is a **no-op with a notify** — "child tasks move with
their parent" — not a silent nothing. Independently movable children is a
separate design question (it conflicts with the filesystem parent-child model)
and is out of scope.

### 5. Lifecycle

Clear the marked set on view change and on board refresh. Marks **survive** a
filter pass (filtering is a view operation, not a selection operation).

### 6. Footer and CSS

Add the binding with a short footer label. The board currently has **no `:hover`
or `:focus:hover` rules at all**; add the accent triple used elsewhere in the
repo (`:focus` -> `$accent`, `:hover` -> `$surface-lighten-1`, `:focus:hover` ->
`$accent-lighten-1`) so a hovered+focused card never flips to a gray hover.

## Verification

- **Render assertions** (`widget.render().plain`) for both glyph states on a real
  `TaskCard`.
- Marks **survive** a filter pass; marks are **cleared** on view switch.
- `space` is inert while a modal is open (push a modal, press `space`, assert the
  marked set is unchanged).
- A child card is **refused with a reason**: pressing `space` on it leaves the
  marked set unchanged and emits the notify.
- `check_action` hides the binding in `inflight` / `bytopic` / `bytrail`
  (extend `tests/test_board_footer_visibility.py`'s style of assertion).
