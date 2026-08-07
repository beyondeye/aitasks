---
priority: medium
effort: medium
depends: [1377_6]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 1243
created_at: 2026-08-07 13:08
updated_at: 2026-08-07 13:08
---

## Failed verification item from t1377_6

> [t1377_6] Read the updated board and minimonitor doc pages against the shipped behaviour and confirm no statement is stale

### Source

- **Manual-verification task:** `aitasks/t1377/t1377_7_manual_verification_column_features.md` (item #20)
- **Origin feature task:** t1377_6
- **Origin archived plan:** `aiplans/archived/p1377/p1377_6_column_features_documentation.md`

### Commits that introduced the failing behavior

- e8e782300 documentation: Document the board column dialog, merge and minimonitor move (t1377_6)

### Files touched by those commits

- website/content/docs/tuis/board/how-to.md
- website/content/docs/tuis/board/reference.md
- website/content/docs/tuis/minimonitor/how-to.md

### Stale statements found (all in `website/content/docs/tuis/board/how-to.md`)

`minimonitor/how-to.md` was checked line by line against live behaviour and
is **accurate** — lines 135, 140 and 273 all match what ships. The board
page has three wrong statements:

1. **Line 91 — `| Delete column | **e** → focus the column → **Delete** →
   confirm |`.** This path does not work: pressing the dialog's `Delete`
   button always reports `Select a column to delete` and deletes nothing.
   There is no other delete path inside the dialog, so the row documents an
   operation the dialog cannot perform. See **t1454** for the underlying
   defect — this doc row should be corrected in step with that fix (or the
   fix lands first and the row becomes true).

2. **Line 90 — `| Edit column | **e** → focus the column → **Enter** (or
   **Edit**) |`.** The `Enter` path works; the parenthesised `(or **Edit**)`
   button alternative does not (same root cause, `Select a column to edit`).

3. **Line 85 — "reachable … from the command palette
   (**Ctrl+Backslash**)".** The palette opens with **Ctrl+P**; the board's
   own footer reads `^p palette`, and `Ctrl+Backslash` was verified live to
   do nothing.

### Also noticed (pre-existing, not introduced by t1377_6)

- **Line 102** — "Collapse/expand state is saved in `board_config.json`".
  It is saved in **`board_config.local.json`**: `collapsed_columns` lives
  under `settings`, and `settings` is a USER key
  (`board_columns.py:144` / `aitask_board.py` `_USER_KEYS`), so the layered
  save routes it to the gitignored local file. Verified live: collapsing a
  column left `board_config.json` byte-identical and wrote
  `board_config.local.json`. Introduced by `633f73bc13` (2026-04-19), so it
  is out of t1377_6's scope but worth fixing on the same pass.

### Next steps

Correct the statements above. Items 1 and 2 depend on how **t1454** is
resolved — sequence them together.
