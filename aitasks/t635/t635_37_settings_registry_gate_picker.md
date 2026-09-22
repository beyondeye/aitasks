---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [gates, settings, ui]
gates: [risk_evaluated]
anchor: 635
created_at: 2026-07-19 23:33
updated_at: 2026-07-19 23:33
---

## Context

As of t635_33, the settings TUI's profile editor (`.aitask-scripts/lib/profile_editor.py`)
edits the profile gate knobs — `record_gates`, `default_gates`, `rendered_gates` — but the
two list keys are edited as FREE COMMA-SEPARATED TEXT rows (with the literal `[]`
affordance for a present-but-empty override). There is no registry-driven selection and no
view of the effective interplay between the keys. Typos in gate names are only caught later
(materialize-time strict validation rejects malformed profile lists, but a well-formed
wrong NAME silently declares a gate the registry cannot run).

Related surfaces: t635_30 owns the TASK-side gate editing surface (board add/remove +
`ait gate add/remove` CLI); this task owns the PROFILE-side settings UX. Both source the
same registry.

## Goal

Replace the free-text editing of `default_gates` / `rendered_gates` in the settings
profile editor with a registry-driven picker, and surface the effective render/enforce
interplay per profile.

## Scope

1. **Registry-driven multi-select:** for `default_gates` and `rendered_gates`, offer a
   checkbox-style multi-select sourced from `aitasks/metadata/gates.yaml` (gate name +
   type + description per row) instead of a raw text row. Unknown/legacy names already
   present in the profile must be shown (flagged, e.g. "not in registry") and remain
   removable — never silently dropped.
2. **Preserve the key-presence semantics:** the picker must distinguish the three
   `rendered_gates` states — unset (falls back to `default_gates`), explicit `[]`
   (render-nothing override), and a non-empty selection — with the same round-trip
   guarantees as the current `[]` literal affordance (see
   `tests/test_profile_editor_rendered_gates.py`; extend it for the picker).
3. **Effective-interplay display:** a read-only summary line per profile, e.g.
   "renders: risk_evaluated (from default_gates)" / "renders: nothing (explicit
   override)" — computed with the same key-presence rule as
   `gate_ledger._read_profile_rendered_gates` (do not fork the semantics; reuse or shim
   the canonical seam).
4. **Validation at edit time:** reject unknown gate names on save with a clear message
   (the registry is the source of truth), mirroring the materialize-time strict
   validation rather than duplicating its internals.

## Key files

- `.aitask-scripts/lib/profile_editor.py` — PROFILE_SCHEMA list handling, compose/collect
  paths, "Gates" group.
- `.aitask-scripts/lib/settings_app.py` (or the settings TUI host of the profile editor) —
  wiring for the new widget.
- `aitasks/metadata/gates.yaml` — registry source (read-only here).
- `tests/test_profile_editor_rendered_gates.py` — extend for picker round-trips.

## Reference patterns

- t635_33's `[]` literal affordance in `collect_profile_values` (the state model to keep).
- The board's registry read (`gate_registry()` in `aitask_board.py`) for loading gate
  metadata.
- TUI conventions: `aidocs/framework/tui_conventions.md` (read before editing the TUI).

## Verification

- Editor round-trip tests: picker selection → profile YAML → reload for all three
  `rendered_gates` states; unknown-name flagged not dropped; unknown-name save rejected.
- Render-level assertion for the interplay summary (widget.render().plain).
- Manual: `ait settings` → profile → Gates group shows the picker and summary.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:10:28Z.1123cd83f9d42ff3f31c05fa from=t1794_9 from_verified=yes at=2026-09-22T06:10:28Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
>
> | t1794 split the board mono-file `.aitask-scripts/board/aitask_board.py`
> | (children t1794_1..8 landed; the last extraction is commit 387d8cb20). Any
> | `aitask_board.py:NN` anchor in your body or plan is STALE: aitask_board.py is
> | now ~6.8k lines (was ~13.7k) and most classes moved. Re-derive by symbol
> | (grep the class/function name), not by line number.
> | 
> | Where symbols live now (.aitask-scripts/board/):
> | - aitask_board.py: KanbanApp (incl. action_* handlers, _do_archive,
> |   action_work_report, sync), Kanban/InFlight/Topic columns, board-only modals
> |   (delete/archive/rename/commit/settings/cross-repo/gate choice), key map,
> |   command palette provider
> | - board_task_manager.py: TaskManager (paths injected as required kw-only
> |   tasks_dir / metadata_file / gates_registry_file; no module-global reads)
> | - board_task_model.py: Task, MoveResult, MergeResult
> | - board_workflow_phase.py: workflow-phase / in-flight derivation
> | - board_widgets.py: TaskCard, ColumnHeader, PickerItem, badge/marker helpers,
> |   LoadingOverlay
> | - board_detail_screen.py: TaskDetailScreen + its field widgets and pickers
> | - board_column_dialogs.py: ColumnEdit/Select/Manage/MultiSelect screens,
> |   ColorSwatch, column confirm dialogs
> | - board_trail_view.py: pure trail rendering - trail cards/columns, trail
> |   modals (TrailDetailScreen, TrailSelectScreen, summary), TRAIL_CSS
> | - board_trail_screen.py: TrailScreenMixin (all By-Trail actions),
> |   TRAIL_BINDINGS, TrailHost protocol, TRAIL_ACTION_CAPABILITIES
> | - trails_app.py: the new stand-alone `ait trails` TUI, hosting the same mixin
> | 
> | Rules a change to these files must keep (full text: contracts C1-C3 in
> | aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md; note that the
> | line ranges in that plan's "Target file map" are PRE-split mono-file anchors,
> | not current ones):
> | 1. Flat imports between board/*.py (`import board_x`), never `board.`-qualified.
> | 2. No board/*.py other than aitask_board.py reads TASKS_DIR / METADATA_FILE /
> |    etc. at import time - moved code receives paths by parameter.
> | 3. No board/*.py imports aitask_board.
> | All three are test-enforced (tests/test_board_package_contract.py,
> | tests/test_board_fixture_harness.py). Test patch targets follow the symbol:
> | patch board_task_manager.X (etc.), not aitask_board.X, for moved code.
> | 
> | Advisory, not an instruction: tree-relative claims above are as of the base
> | SHA this note records.
