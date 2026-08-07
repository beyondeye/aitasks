---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_board, tui, testing]
gates: [risk_evaluated]
anchor: 1243
created_at: 2026-08-07 11:26
updated_at: 2026-08-07 11:26
---

## Origin

Spawned from t1377_5 during Step 8b review. Both defects were hit directly while
building the board column-management dialog; neither is caused by that task.

## Upstream defect

- `tests/lib/board_fixture.py:561-583 (PristineTreeMixin) — restores only
  **/*.md, while snapshot() in the same module treats
  metadata/board_config*.json as part of the tree. Any test class that mutates
  COLUMNS leaks board config into the next test, and the leak is
  self-concealing: with the column already dropped from config, merge_columns
  refuses it as unknown_column and writes nothing, while a "the source column
  was removed" assertion still passes — because the previous test removed it.
  Cost t1377_5 a vacuous pair of assertions. Worked around locally with a
  _PristineConfigMixin in tests/test_board_column_dialog.py rather than editing
  a harness 31 modules share.`
- `.aitask-scripts/board/aitask_board.py:8223-8230 (action_focus_board) — the
  app's priority=True escape binding closes ANY active modal with a bare
  self.screen.dismiss(), discarding the dismiss result. Every modal whose
  dismiss value carries meaning silently loses it when closed with Escape; it
  is benign only because every other board modal happens to treat None as
  "cancelled". The handle_escape hook checked one line above is the escape
  valve and had no implementers until t1377_5. A modal author has no way to
  discover this except by hitting it.`

## Diagnostic context

**Defect 1** surfaced as a single failing test in t1377_5 whose delete-then-merge
ordering left `c1` absent from `board_config.json`. Because `merge_columns`
validates ids before writing, the merge was *refused* rather than failing — so
the two assertions checking that the source column had been removed passed
vacuously, and only the third (destination membership) failed. Running the merge
test alone passed; running it after the delete test failed. The asymmetry between
`PristineTreeMixin` (`*.md` only) and `snapshot()` (`*.md` + `board_config*.json`)
in the same module is the root cause.

**Defect 2** surfaced only in a real terminal. Every unit test passed while the
board behind the dialog kept rendering a merged-away column: the dialog defers
`refresh_board()` to close and signals "something changed" through its dismiss
value, but Escape never reached the modal's own `action_cancel` — the app's
priority binding closed it with `dismiss()` and the flag became `None`. A probe
confirmed `screen.dismiss(True)` fires the callback while `pilot.press("escape")`
does not.

## Suggested fix

1. Make `PristineTreeMixin` restore the same allowlist `snapshot()` uses (add
   `metadata/board_config*.json`), then drop the local `_PristineConfigMixin`
   workaround in `tests/test_board_column_dialog.py`. Re-run the board test
   modules — most do not mutate config, so this should be a no-op for them.
2. Either have `action_focus_board` delegate to the screen's own `action_cancel`
   when one exists (preserving each modal's dismiss contract), or document
   `handle_escape` where modal authors will actually see it — e.g. in
   `aidocs/framework/tui_conventions.md` alongside the footer/binding rules.
