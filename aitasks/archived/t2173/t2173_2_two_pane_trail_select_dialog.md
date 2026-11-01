---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: [t2173_1]
issue_type: feature
status: Done
labels: [trails, aitask_board, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2173
implemented_with: claudecode/opus5_5
created_at: 2026-10-31 19:29
updated_at: 2026-11-01 09:07
completed_at: 2026-11-01 09:07
---

## Context

Child 2 of t2173. The trail-selection dialog (`TrailSelectScreen` +
`TrailSelectItem` in `.aitask-scripts/board/board_trail_view.py` ~:704–:820) is
60% wide / max 50% high; each row is `title · owner · scope · freshness · updated`
followed by one `└ also references: <ref> (<other title>)` sub-line per shared
task, which makes a long list hard to scan. Replace it with a large two-pane
dialog: left = fuzzy search box + list of titles only (with `● open`), right =
details of the highlighted trail. It is shared by the board's By-Trail view
(`KanbanApp`, via `TrailScreenMixin`) and `ait trails` (`TrailsApp`); both get it.

t2173_1 (discovery cache) lands first: after it, `s` re-scans on every open in
both hosts. This child does not depend on its code.

**The full design and step list are in the child plan
`aiplans/p2173/p2173_2_two_pane_trail_select_dialog.md` — read it first.** Binding
decisions from the approved parent plan (incl. a review round on focus):

- Constructor signature, `GuardedModalScreen` base, `TRAIL_SELECT_RESCAN`,
  `open_handles`, `allow_rescan`, dismissal values unchanged; own ids
  (`#trail_select_dialog`, 90% × 80%) and a self-contained `DEFAULT_CSS`.
- Left: `Input#trail_select_search` (focused, keeps focus) + `TrailTitleList`
  (`OptionList` subclass, `can_focus=False`, option id = handle). Filtering =
  `lib/fuzzy_filter.rank` on the **title only**.
- Right: `TrailDetailPane` (`VerticalScroll` subclass, **`can_focus=False`** —
  `VerticalScroll` is focusable by default in Textual 8.2.7 and a focused pane
  would re-activate both Apps' priority `nav_up/down`), rendering a pure
  `trail_select_detail(info, overlap_notes, is_open) -> Text`: owner (archived /
  folded), scope, `_trail_stored_freshness`, `trail_generated_label`, open marker,
  the shared-task lines from `compute_trail_overlaps`, and for `load_error` trails
  the error + versions fallback.
- Keys: ↑/↓ list (screen bindings; both Apps' priority arrows are inactive while an
  `Input` is focused), PgUp/PgDn scroll the detail pane, Enter / click open, Esc /
  Cancel → None, **Ctrl+R** → rescan when `allow_rescan` (a typed `r` must reach the
  search box). Tab cycles search box ↔ Cancel only. Two-line hint fitting 80×24.
- Remove `TrailSelectItem` (and its re-export in `aitask_board.py`).

## Key files to modify

- `.aitask-scripts/board/board_trail_view.py`, `.aitask-scripts/board/aitask_board.py` (re-export).
- Tests: `tests/test_board_trail_view.py`, `tests/test_board_bytrail_view.py`,
  `tests/test_trails_app.py`, `tests/test_board_detail_followup_kind.py` (check),
  `tests/perf/trails_pilot_bench.py`.
- Docs: `website/content/docs/tuis/trails/{reference,how-to,_index}.md`,
  `website/content/docs/workflows/implementation-trails.md` (`r` → Ctrl+R, two panes).

## Reference files

- `lib/fuzzy_filter.py` (`rank`), `lib/agent_model_picker.py` `FuzzySelect`,
  `codebrowser/file_search.py` (Input + OptionList).
- `aidocs/framework/tui_conventions.md`: "Priority bindings", "Modal dismissal",
  "Modals pushed by multiple Apps".
- `KanbanApp.check_action` (`aitask_board.py` ~:2440–:2466), `TrailsApp.check_action`
  (`trails_app.py` ~:774).

## Verification

- Both hosts: filter by title only, subsequence match, ↑/↓ + detail update, Enter,
  click, Esc, typed `r` stays in the box, Ctrl+R only with `allow_rescan`, `● open`,
  error trail detail; focus cycle never lands on the list/detail pane; PgUp/PgDn
  scroll an overflowing detail pane; ↑ from Cancel returns to the box.
- `bash tests/run_all_python_tests.sh` — last line `PYTHON SUITE: PASSED`.
- `cd website && python3 check_links.py --build`.
- Step 8e: send t1647_5 a note (`TrailMergeSelectScreen` should build on the new
  two-pane widget; `TrailSelectItem` is gone).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-31T22:04:53Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-01T06:53:58Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-01T07:07:50Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:84be41454616cff1

> **✅ gate:risk_evaluated** run=2026-11-01T07:07:50Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2173_2/risk_evaluated_2026-11-01T07:07:50Z-risk_evaluated-a1.log`
