---
priority: medium
effort: medium
depends: [t1377_3]
issue_type: enhancement
status: Ready
labels: [ait_settings, board_columns, tui]
gates: [risk_evaluated]
anchor: 1243
created_at: 2026-08-04 09:57
updated_at: 2026-08-04 09:57
---

## Context

**Risk-mitigation follow-up for t1377** (timing: `after`, confirmed at t1377
planning). Addresses the goal-achievement risk that `ait settings` advertises a
stance the framework no longer holds.

The Settings TUI renders board columns read-only, labelled literally
"read-only — edit via board TUI" (`.aitask-scripts/settings/settings_app.py`,
Columns section). That label was **forced by capability**: column creation existed
only inside the board TUI, with no headless writer for
`aitasks/metadata/board_config.json`.

`t1377_3` removes that constraint by landing
`lib/board_columns.create_column(root, title, color)` — a Textual-free, root-scoped
writer that respects the project/user layer split. Once it exists, the settings
label is a stale claim rather than a real limitation: board, minimonitor and
settings would disagree about who may edit columns.

t1377_3 deliberately left the settings TUI unchanged (it was scoped to minimonitor)
and recorded the decision instead of widening. This task is where that decision is
revisited.

## Scope

Flip the Settings TUI's Columns section from read-only to editable on top of the
headless seam:

- add / edit (title, colour) / delete / reorder, reusing
  `lib/board_columns.py` (`create_column`, `generate_col_id`, `PALETTE_COLORS`) —
  **do not** re-implement slug generation or the palette;
- keep the board's own column UI as-is; both surfaces call the same seam;
- update the section label and any surrounding help text.

## Constraints

- **Layer discipline.** `columns` / `column_order` are **project-level** (tracked);
  `settings` is **user-level** (`board_config.local.json`, gitignored). Write only
  the project layer for column edits, exactly as `create_column` does. Writing a
  merged dict back to the project file leaks user settings into a tracked file.
- **No auto-commit from a TUI event handler.** Per
  `aidocs/framework/tui_conventions.md`, a runtime TUI may write project-level
  config but must never `git commit` / `./ait git push` from an event handler.
- **Single-source the key sets.** `_PROJECT_KEYS` / `_USER_KEYS` were triplicated
  across `aitask_board.py`, `settings_app.py` and `stats_config.py`; t1377_3
  consolidates them into `lib/board_columns.py`. Import, do not redefine.
- If, on inspection, the read-only stance turns out to be **deliberate product
  design** rather than a capability limit, the correct outcome is to keep it and
  update the label to say so — record that as the finding rather than forcing the
  change.

## Verification

- Column add / edit / delete / reorder from `ait settings` are reflected in
  `ait board` on next refresh.
- A round-trip test asserting `board_config.local.json` is untouched by a column
  edit and that no `settings` key appears in the project file.
- `bash tests/run_all_python_tests.sh` (read only the last line for the verdict).

## Dependency

Depends on **t1377_3**, which lands the headless writer this task builds on.
