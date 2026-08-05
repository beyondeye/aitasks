---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [tui, textual, shortcuts]
gates: [risk_evaluated]
anchor: 1418
created_at: 2026-08-05 10:52
updated_at: 2026-08-05 10:52
---

## Origin

Risk-mitigation ("after") follow-up for t1418, created at Step 8d after implementation landed.

## Risk addressed

> Discovery-surface overlap between the `?` shortcuts editor and the `ctrl+p` command
> palette: neither surface shows the whole operation set, so a user cannot learn
> everything the board can do from either one.

## Goal

Reconcile the two discovery surfaces so there is a single answer to "what can this
TUI do, and which key does it".

The two are **not** duplicates today — that was checked while planning t1418:

- `ctrl+p` (`KanbanCommandProvider`, `.aitask-scripts/board/aitask_board.py:5782`)
  exposes 9 board commands **plus** Textual's built-ins (theme, screenshot, quit).
  Four of its nine have **no key binding at all** and therefore appear nowhere else:
  Add Column, Edit Column, Delete Column, Expand Column, and Clear Selection.
- `?` (`ShortcutsMixin`, `.aitask-scripts/lib/shortcuts_mixin.py`) lists and
  **rebinds** keys, so by construction it can only reach operations that already
  have one — the five above are invisible to it.

So each surface is missing something the other has, and the footer (even multi-row
after t1418) only ever shows *bound, shown* actions.

Directions to weigh (decide in planning, do not assume):

- Give the palette's binding-less commands real bindings so `?` and the footer can
  see them — simplest, but spends scarce keys on rare operations.
- Let the `?` editor list binding-less palette commands as unbound rows, with the
  option to assign a key. Keeps the palette as the execution surface and makes `?`
  the complete inventory.
- Have the palette read from the keybinding registry so every bound action is also
  palette-searchable, making `ctrl+p` the complete surface and `?` the rebinding one.

Whichever way it goes, state the resulting division of labour in
`aidocs/framework/tui_conventions.md` so the next TUI does not have to re-derive it,
and keep it generic across TUIs rather than board-only — `ShortcutsMixin` is shared.

## Related

- t1418 added the `+N more (<key>)` footer affordance, which points users at the `?`
  editor when the footer runs out of room — that pointer is only as good as the
  editor's coverage, which is what this task fixes.
- t1421 fixes a rebind bug in `_relink_live_bindings` that affects punctuation keys
  (including `?` itself); worth landing before reworking the editor.
