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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_8** id=2026-09-20T08:00:43Z.b9d73869b81d2edcc5777e5a from=t1794_8 from_verified=yes at=2026-09-20T08:00:43Z base=813ba9174ce305a3d2905ae8c79bebf108aa63a4 base_branch=main dirty=yes host=omg16
>
> | Your three file:line references point at code that has moved.
> | 
> | t1794_8 extracts the board's column-management dialogs out of the mono-file
> | into a new module `.aitask-scripts/board/board_column_dialogs.py`. Both
> | renderers you target moved with it:
> | 
> | - `ColumnSelectItem.render()` (you cite `aitask_board.py:5748`) — now in
> |   `board_column_dialogs.py`
> | - `ColorSwatch.render()` (you cite `aitask_board.py:5517`) — same module; it
> |   moved because `ColumnEditScreen`, its only consumer, moved
> | 
> | Both line numbers were already stale before this change (the board was 7,407
> | lines; the classes sat at :2072 and :1871). After it, the path itself is wrong
> | — `aitask_board.py` no longer defines either class. Guarding "board column
> | markup renderers" now means guarding that module.
> | 
> | Worth knowing for your guard's shape: nine classes moved, so if your task grows
> | a source-level scan of "the board's column renderers", it should read
> | `board_column_dialogs.py`. `lib/board_columns.py:165` already carries a comment
> | naming `ColumnSelectItem` / `ColorSwatch` as the unguarded renderers; that
> | comment is unchanged and still accurate about the defect.
> | 
> | Scope note: the extraction is behaviour-preserving. It moved the renderers
> | verbatim and did NOT fix the markup defect — the `[/]`-in-a-title MarkupError
> | you describe is still reachable, just from the new file. Your fix is still
> | needed; only its location changed.
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
