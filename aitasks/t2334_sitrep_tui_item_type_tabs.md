---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [sitrep, tui]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
implemented_with: claudecode/opus5_5
created_at: 2026-11-19 05:12
updated_at: 2026-11-19 22:15
---

## Problem

The sitrep TUI (`ait sitrep tui`) shows every item in one list: triage questions, review cases, task picks, push reminders, trail watches and crash-recovery items are mixed, separated only by the Now / Next / Waiting groups. With more than a dozen items it is hard to see "what do I have to triage" or "what crashed" at a glance.

## Goal

A one-row tab strip above the main list that filters it by item type, switched with the left / right arrow keys.

```
 All 14 |[Triage 3]| Tasks 6 | Recovery 2 | Watches 3
```

## Scope

- Tabs: **All**, **Triage** (classes `triage`, `review`, `decide`), **Tasks** (`pick*`, `push`, `do`), **Recovery** (`recover` and its categories), **Watches** (`watch*`). The mapping is one table in `sitrep_tui_model.py`, keyed by the existing `classify` result. Every class `classify` can return must land in exactly one type tab (a test iterates the `NEXT_STEPS` keys, so a new class cannot silently fall out of every tab). `unknown*` items go to the tab of their kind.
- Each label shows the count of **open** items of that type; a tab with zero items stays visible and selectable (an empty-state line, no jump).
- `left` / `right` cycle (wrapping), remappable like the other keys (shortcut scope of the main screen); a mouse click on a tab selects it. The strip stays on one row and elides labels on a narrow pane (the TUI pane is 40% of a window).
- Inside a tab the Now / Next / Waiting grouping, the `d` closed-items toggle and the label filter (`f` / `F`) keep working and compose with the tab. The header or strip must show when the label filter is hiding items of the active tab.
- The active tab is per-session UI state, never written to the store. A store reload keeps the active tab and the selected item when it is still in the tab; otherwise selection moves to the nearest row.
- Build the strip so a later non-item tab ("Directions", see the work-directions task) can be appended: the strip is a list of tab descriptors, not a hardcoded filter enum.
- Check `board_trail_view.py` / `trails_app.py` `TrailTabStrip` before writing a new widget; reuse it if it fits without dragging board imports into `sitrep_tui/`.

## Out of scope

Work directions and their tab (separate task). No store or skill change.

## Docs

`aidocs/framework/sitrep.md` ("Views"), `website/content/docs/tuis/sitrep/` (`_index`, `how-to`, `reference`); run `python3 check_links.py --build` in `website/`.

## Verification

- New cases in `tests/test_sitrep_tui_app.py` over the fixture store: per-tab membership, counts, wrap-around, empty tab, composition with `d` and the label filter, selection kept across a reload, the class-coverage test above.
- `bash tests/run_all_python_tests.sh --test-dir tests` subset for `test_sitrep_tui_*`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-19T20:15:34Z status=pass attempt=1 type=human
