---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_board, board_columns, tui]
gates: [risk_evaluated]
anchor: 1243
followup_kind: upstream_defect
created_at: 2026-08-06 00:28
updated_at: 2026-08-13 23:07
---

## Origin

Spawned from t1377_3 during Step 8b review.

## Upstream defect

- `.aitask-scripts/board/aitask_board.py:5748 — ColumnSelectItem.render() interpolates an unescaped column title AND an unvalidated colour into rich markup; a title containing '[/]' raises MarkupError inside the board.` (Recorded by t1377_2 and still open; t1377_3 narrows the exposure by refusing malformed colours at the new write site but does not fix the renderer.)
- `.aitask-scripts/board/aitask_board.py:5517 — ColorSwatch.render() interpolates an unvalidated colour into a rich markup tag, the same defect as ColumnSelectItem.`
- `.aitask-scripts/monitor/monitor_shared.py:1088 — _SiblingRow.render() interpolates an unescaped sibling task title into rich markup. Recorded by t1377_2, still open.`
- `.aitask-scripts/lib/config_utils.py:244 — save_project_config's docstring claims "Creates parent directories if they don't exist", which is true only because _prepare_atomic does the mkdir; the claim belongs to the helper, not this wrapper. Harmless today, misleading if the two ever diverge.`

## Diagnostic context

t1377_2 fixed exactly this class of defect in the minimonitor column picker and
recorded the three sibling renderers as out-of-scope upstream defects. t1377_3
then made the first two **more reachable**: minimonitor can now create board
columns, so a user-supplied title reaches `ColumnSelectItem.render()` in the
board without ever passing through the board's own dialog.

Verified behaviour at the parse boundary (t1377_2, re-confirmed in t1377_3):

- a title containing `[/]` **raises `MarkupError`**, taking the surface down;
- a title containing `a[b]c` is **silently swallowed** to `ac` — corruption with
  no signal at all, the worse half;
- a colour is interpolated as a markup *tag*, so a `]` closes it early and
  injects markup. Textual's renderer tolerates an unknown style name, but
  `Style.parse` does raise, so relying on that tolerance is relying on an
  implementation detail.

t1377_3 refuses a malformed colour at its new write site (`create_column`,
`_COLOR_RE`) and keeps readers tolerant of hand-edited config, so the seam is
guarded — but `board_config.json` is hand-editable and these three renderers
remain unguarded on the read side.

## Suggested fix

Apply the pattern t1377_3 already landed in `monitor_shared.py`: escape every
user-derived field with `rich.markup.escape` at each interpolation site, and
validate the colour before using it as a tag (`_safe_column_color` for the
Textual-importing side; note `lib/board_columns._COLOR_RE` is the dependency-free
equivalent and deliberately accepts `gray`, the seam's own `UNORDERED_COLOR`,
which rich cannot parse). Give each guard a one-mutation negative control
asserting the specific failure it prevents — `[/]` raises, `[b]` silently
corrupts — since one control cannot cover both. The `config_utils` docstring fix
is a one-line correction, unrelated to the markup work but too small for its own
task.
