---
priority: low
effort: low
depends: []
issue_type: documentation
status: Ready
labels: [tui]
gates: [risk_evaluated]
anchor: 1223
created_at: 2026-07-28 17:29
updated_at: 2026-07-28 17:29
boardidx: 66560
---

## Origin

Risk-mitigation ("after") follow-up for t1223_5, created at Step 8d after
implementation landed. Also the disposition of the **upstream defect** recorded
in that task's plan (the Step 8b offer was declined as duplicate of this task).

## Risk addressed

Verified documentation gap: two task files instruct the implementer to read a
rule in `aidocs/framework/tui_conventions.md` that is not in it.

## Goal

`aitasks/t1223/t1223_5_settings_tab_and_push_action.md` says verbatim:

> `aidocs/framework/tui_conventions.md` — required reading; note the
> render-level verification rule (assert `widget.render().plain`, prefer
> `markup=False`).

Verified during t1223_5: **that rule is not in that file, nor anywhere in
`aidocs/framework/`.** `markup=False` appears nowhere under `aidocs/`. The only
statement of it in the repo is a single line in
`aidocs/implementation_trail_design.md` ("Render-level tests (assert
`widget.render().plain`) + Pilot tests"), plus established *practice* in
`tests/test_syncer_rows.py` (`detail_text()`, `version_cells()`,
`settings_cells()`, the `#upgrade_text` / `#settings_text` body assertions).

A planner directed there finds nothing and either invents a convention or drops
the rule.

Add the rule to `aidocs/framework/tui_conventions.md` as its own `##` section,
stating at least:

- assert on `widget.render().plain` (or `str(table.get_cell(...))`), not on
  internal model state alone — one model assertion plus one render assertion;
- prefer plain-text cell content over Rich markup so cells stay assertable
  (`markup=False` where a widget takes it);
- give the DataTable idiom actually used in-repo: a per-table
  `cells(app, row_key) -> dict|list` helper keyed by column, e.g.
  `version_cells` / `settings_cells` in `tests/test_syncer_rows.py`;
- note that modal body text needs an explicit `id` because Textual's `Label`
  subclasses `Static`, so an id-less `query_one(Static)` resolves to the dialog
  title (the trap that cost t1223_3 three tests).

## Key files

- `aidocs/framework/tui_conventions.md` — the new section.
- `tests/test_syncer_rows.py` — the reference implementation to cite.

**Note:** another session had `aidocs/framework/tui_conventions.md` modified in
the working tree when this task was created — re-read it before editing.

## Verification

Re-read `aitasks/t1223/t1223_5_*.md`'s "Reference files for patterns" pointer and
confirm it now resolves to real content.
