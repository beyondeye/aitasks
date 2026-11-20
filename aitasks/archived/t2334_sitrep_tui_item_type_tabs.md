---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: feature
status: Done
labels: [sitrep, tui]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
implemented_with: claudecode/opus5_5
created_at: 2026-11-19 05:12
updated_at: 2026-11-20 09:08
completed_at: 2026-11-20 09:08
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2278_5** id=2026-11-20T06:49:19Z.0c56180f010ea3908ab8ef4c from=t2278_5 from_verified=yes at=2026-11-20T06:49:19Z base=b0bb6e2575e27ba8cd13b897b76f9c0d6f47c6ec base_branch=main dirty=yes host=omg16
>
> | Advisory, from t2278_5 (committed in 45539803d), as of that commit:
> | 
> | The docs now carry a generated screenshot of the sitrep window:
> | website/static/imgs/aitasks_sitrep_tui_main_view.svg, shown on
> | website/content/docs/tuis/sitrep/_index.md, recorded as the recipe
> | website/screenshots/scenes/sitrep_window.yaml (it replays the real sitrep TUI
> | on a sample project and expects texts that are on screen today).
> | 
> | A change to the sitrep TUI's layout or labels will make that image stale, and
> | may make the recipe's replay fail. After your change lands, refresh it with
> |   /aitask-docs-screenshots sitrep_window
> | (or: website/screenshots.sh replay --scene sitrep_window --png). Do not edit
> | the recipe file by hand; the skill re-records it. Contract:
> | aidocs/framework/docs_screenshots.md.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-19T20:15:34Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-20T07:06:01Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-20T07:08:34Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:c4933e72b15eae74

> **✅ gate:risk_evaluated** run=2026-11-20T07:08:34Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2334/risk_evaluated_2026-11-20T07:08:34Z-risk_evaluated-a1.log`
