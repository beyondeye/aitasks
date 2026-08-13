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
