---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [sitrep, tui]
gates: [risk_evaluated]
anchor: 2175
followup_kind: upstream_defect
created_at: 2026-11-07 19:25
updated_at: 2026-11-07 19:25
---

## Origin

Spawned from t2211_1 during Step 8b review.

## Upstream defect

- `tests/test_monitor_sitrep_harvest_close.py:891-896 — test_S_is_a_registered_quick_jump fails when run after tests/test_shortcut_scopes.py in the same process (the scope sweep resets keybinding_registry; tui_switcher's import-time shared-scope registration is not replayed). Reproduced on a pristine HEAD copy; passes alone and in the full suite's current worker split.`

## Diagnostic context

While verifying t2211_1 (sitrep TUI read views), this pair was run in one pytest
process:

```bash
~/.aitask/venv/bin/python -m pytest -q tests/test_shortcut_scopes.py tests/test_monitor_sitrep_harvest_close.py
```

`SwitcherSitrepTests::test_S_is_a_registered_quick_jump` fails at its
`resolve_key(ts._TUI_SWITCHER_SCOPE, "shortcut_sitrep") == "S"` assertion. It
passes when run alone. The same failure reproduces on a pristine `git archive
HEAD` copy of `.aitask-scripts/` + `tests/` (with `aitasks/metadata/` copied
in), i.e. before t2211_1's changes — so it is pre-existing order-dependent
pollution, not caused by the new `sitrep_tui_app` manifest entry.

The full suite (`bash tests/run_all_python_tests.sh`) currently passes because
`--dist loadfile` happens not to place these two files in the same worker in
that order; a different worker split (or `AIT_TEST_PARALLEL=0` / a different
file set) can surface it as a flake.

Likely mechanism (unverified): `test_shortcut_scopes.py` resets
`keybinding_registry` around its sweeps, and `tui_switcher`'s module-level /
class-body registration of the `shared.tui_switcher` scope only runs at first
import, so a later `resolve_key` on that scope returns the post-reset (empty)
state. `aidocs/framework/tui_conventions.md` ("Import semantics of the sweep")
documents the re-exec-under-a-probe-name design this interacts with.

## Suggested fix

Make the test independent of registry state left by other modules: have
`test_S_is_a_registered_quick_jump` (re-)register the switcher scope itself
(e.g. via the sweep's `register_scope_bindings("shared.tui_switcher")` or by
re-importing under the sweep), or have `test_shortcut_scopes.py` restore the
registry it resets in `tearDown`. Confirm with the failing pair above plus an
`AIT_TEST_PARALLEL=0` run.
