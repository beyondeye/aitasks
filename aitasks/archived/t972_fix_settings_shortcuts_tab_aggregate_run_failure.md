---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [tests]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-11 10:36
updated_at: 2026-06-11 10:59
completed_at: 2026-06-11 10:59
---

## Origin

Spawned from t953 during Step 8b review.

## Upstream defect

- `tests/test_settings_shortcuts_tab.py:488 (test_tab_titles_carry_current_shortcut)` — fails ONLY under `tests/run_all_python_tests.sh` (aggregate single-process run), passes standalone. Assertion diff: `'Proje(c)t Config' != 'Proje(C)t Config'`. Pre-existing on HEAD before t953 (verified by running the aggregate suite on a stashed tree).

## Diagnostic context

While verifying t953 (dedicated tmux socket), the full python suite was run via `tests/run_all_python_tests.sh` and this test failed alongside the (since-fixed) t953 discover-test failures. Re-running it standalone passes on both HEAD and the t953 tree; re-running the aggregate suite on stashed HEAD reproduces the failure with no t953 changes present — so it is cross-test state leakage in the aggregate single-process run, not a t953 regression.

The failing assertion compares a tab label's shortcut-letter casing (`(c)` vs `(C)`), which suggests another test module mutates shared shortcut-label state (e.g. the `shortcut_label_case` userconfig handling or a module-level shortcuts registry) before `test_settings_shortcuts_tab` runs, and the state is not reset between modules.

## Suggested fix

Identify which earlier-loaded test module leaves shortcut-label casing state behind (bisect the module list fed to the aggregate runner), then either reset the shared state in that module's tearDown or make `test_settings_shortcuts_tab` set up its expected casing explicitly in setUp.
