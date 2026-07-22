---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_board, tui]
gates: [risk_evaluated]
anchor: 1209
created_at: 2026-07-22 11:19
updated_at: 2026-07-22 11:19
---

## Origin

Spawned from t1209 during Step 8b review.

## Upstream defect

`.aitask-scripts/board/aitask_board.py:1083-1087` — `CollapsedColumnPlaceholder.on_focus`
/ `on_blur` set an **inline** `#444444` background. Inline styles beat CSS, so
this dead-letters the widget's own rule at
`.aitask-scripts/board/aitask_board.py:4467-4468`:

```css
.collapsed-placeholder:focus { background: $primary 30%; }
```

The existence of that unused rule shows the accent shade was the intent.

## Diagnostic context

Surfaced while implementing t1209, which added `EmptyColumnPlaceholder` — a
sibling focusable placeholder for columns that show no cards. The new widget
deliberately uses CSS-only focus styling (`.empty-placeholder:focus
{ background: $primary 30%; }`) and no inline `on_focus` / `on_blur` override.

The result is a visible inconsistency the two widgets did not previously have
between them: on a board with both a collapsed column and an empty column,
arrowing between them highlights one gray and the other in the theme accent.
Focus highlighting should use the accent shade, never flip to gray.

## Suggested fix

Delete `CollapsedColumnPlaceholder.on_focus` / `on_blur` entirely and let the
existing `.collapsed-placeholder:focus` CSS rule apply, matching how
`EmptyColumnPlaceholder` is styled. Verify with a render-level assertion or a
Pilot check that the focused collapsed placeholder resolves to the accent
background rather than `#444444` — `tests/test_board_empty_column_focus.py`
already has a fixture that renders a collapsed column (case 5).
