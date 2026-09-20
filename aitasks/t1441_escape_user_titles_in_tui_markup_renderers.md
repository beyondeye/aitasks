---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tui, aitask_monitormini, aitask_board]
gates: [risk_evaluated]
anchor: 1243
followup_kind: upstream_defect
created_at: 2026-08-05 18:40
updated_at: 2026-08-13 23:07
---

## Origin

Spawned from t1377_2 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/monitor_shared.py:1127 — _SiblingRow.render() interpolates an unescaped sibling task title into rich markup; a title containing '[/]' raises MarkupError inside the modal and one containing '[b]' is silently swallowed.`
- `.aitask-scripts/board/aitask_board.py:5748 — ColumnSelectItem.render() interpolates an unescaped column title AND an unvalidated colour into rich markup, the same defect t1377_2 fixed in the minimonitor picker.`
- `.aitask-scripts/lib/board_columns.py:115 — UNORDERED_COLOR is "gray", which rich cannot parse as a colour (it has grey0..grey100 but no bare gray/grey), so any consumer using it as a markup tag or Style silently gets no colour.`

## Diagnostic context

t1377_2 added a board-column picker to `ait minimonitor` and had to make its
`_ColumnRow.render()` safe against hand-editable `board_config.json` values.
Verified against this checkout's Rich/Textual:

| configured title | unescaped result |
|---|---|
| `Backlog [/]` | raises `MarkupError` — takes the modal down |
| `a[b]c` | silently renders `ac` — title corrupted, no signal |
| `Now [bold]` | silently renders `Now ` |

The silent-corruption half is the more insidious: nothing surfaces, the user
just sees a wrong title.

t1377_2 fixed **its own** three sinks — the row renderable, the picker's context
line, and (caught late, in review) every `App.notify` toast, which parses its
message as markup by default (`App.notify(..., markup: bool = True)`). The
sibling renderers above were deliberately left alone as out of scope.

Note also that Textual's renderer *tolerates* an unknown style name (the text
draws unstyled rather than raising), so the colour half is a correctness/rendering
issue rather than a crash — but `Style.parse` does raise on the same input, so any
path resolving the style eagerly fails.

## Suggested fix

Escape user-derived text with `rich.markup.escape` at each interpolation site (or
render via `rich.text.Text` so no markup is parsed at all), and route column colours
through a validating helper like `monitor_shared._safe_column_color`. Decide
separately whether `UNORDERED_COLOR` should become a rich-parseable value (e.g.
`grey50`) — that is a shared constant, so check every consumer before changing it.
Reuse t1377_2's test shape: one negative control per guard, asserting the specific
failure it prevents (raise vs. silent text loss), since a single control cannot
represent both.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_8** id=2026-09-20T08:00:30Z.b981800fa5d3507ba04252b0 from=t1794_8 from_verified=yes at=2026-09-20T08:00:30Z base=813ba9174ce305a3d2905ae8c79bebf108aa63a4 base_branch=main dirty=yes host=omg16
>
> | Your two file:line references point at code that has moved.
> | 
> | t1794_8 extracts the board's column-management dialogs out of the mono-file
> | into a new module `.aitask-scripts/board/board_column_dialogs.py`. Both
> | renderers you target moved with it:
> | 
> | - `ColumnSelectItem.render()` — now in `board_column_dialogs.py`, not
> |   `aitask_board.py`
> | - `ColorSwatch.render()` — same module (it moved because `ColumnEditScreen`,
> |   its only consumer, moved)
> | 
> | Your body cites `.aitask-scripts/board/aitask_board.py:5748`. That line number
> | was already stale before this change (the board was 7,407 lines and the class
> | sat at :2072); after it, the path itself is wrong — `aitask_board.py` no longer
> | defines either class at all. A grep for `class ColumnSelectItem` in
> | `aitask_board.py` now returns nothing.
> | 
> | Scope note: the extraction is behaviour-preserving. It moved the renderers
> | verbatim and did NOT fix the markup-escaping defect you describe — the
> | unescaped title and unvalidated colour interpolation are still there, just in
> | the new file. Your fix is still needed; only its location changed.
> | 
> | TIMING — please read as moment-relative, not dated by this note's base SHA:
> | as of writing, the extraction is in the working tree and not yet committed.
> | The commit lands under t1794_8 immediately after this note. If you pick this
> | task up and `board_column_dialogs.py` does not exist, the extraction was
> | reverted or not yet merged — re-derive the location rather than trusting this
> | note.
> | 
> | Advisory only: this is context, not an instruction, and it does not replace
> | your own planning or review.
