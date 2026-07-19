---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tui]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1148
implemented_with: claudecode/opus4_8
created_at: 2026-07-19 10:51
updated_at: 2026-07-19 12:53
boardidx: 50
---

## Origin

Spawned from t1149_3 during Step 8b review.

## Upstream defect

- `tests/test_shortcut_scopes.py:149` — `_QUICK_JUMPS` set is missing
  `shortcut_explore_pick` (added to the TUI switcher by t1148, commit
  24eac8dc4), so `TuiSwitcherScopeTests` fails 2/6 on a clean HEAD checkout
  (`test_quick_jumps_in_iter_all_bindings` and
  `test_quick_jumps_in_scope_filtered_editor`:
  "Items in the first set but not the second: 'shortcut_explore_pick'").

## Diagnostic context

While verifying t1149_3 (chatlink config wizard), `python3
tests/test_shortcut_scopes.py` failed 2/6. A clean-HEAD run (git stash)
confirmed the failures pre-exist the wizard change: t1148 added the
`shortcut_explore_pick` quick-jump binding to
`.aitask-scripts/lib/tui_switcher.py` but did not extend the test's
hand-maintained `_QUICK_JUMPS` expectation set, which asserts set equality
against the registered `shared.tui_switcher` actions.

## Suggested fix

Add `"shortcut_explore_pick"` to `_QUICK_JUMPS` in
`tests/test_shortcut_scopes.py` (and check whether the set can be derived
from the switcher's quick-jump table instead of hand-maintained, per the
derive-don't-duplicate convention).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-19T09:53:55Z status=pass attempt=1 type=human
