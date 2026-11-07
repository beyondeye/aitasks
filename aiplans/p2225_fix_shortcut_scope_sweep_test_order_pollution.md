---
Task: t2225_fix_shortcut_scope_sweep_test_order_pollution.md
Base branch: main
Output branch: main
---

# t2225 — Make `test_S_is_a_registered_quick_jump` independent of registry state

## Context

`SwitcherSitrepTests::test_S_is_a_registered_quick_jump`
(`tests/test_monitor_sitrep_harvest_close.py:891-896`) asserts
`resolve_key(ts._TUI_SWITCHER_SCOPE, "shortcut_sitrep") == "S"`. That reads the
process-global `keybinding_registry._DEFAULTS`, which `tui_switcher` populates
only at **first import** (module-level `register_app_bindings(_TUI_SWITCHER_SCOPE,
_QUICK_JUMP_BINDINGS)`, `lib/tui_switcher.py:493`). Any earlier test in the same
process that calls `keybinding_registry._reset_for_tests()` (19 test files do,
e.g. `tests/test_shortcut_scopes.py` in setUp *and* tearDown) clears it, and the
import-time registration is never replayed → `resolve_key` returns `None`.

**Reproduced (mechanism confirmed, no longer "unverified"):**
`~/.aitask/venv/bin/python -m pytest -q -p no:randomly tests/test_shortcut_scopes.py tests/test_monitor_sitrep_harvest_close.py`
→ `AssertionError: None != 'S'` at line 895; `1 failed, 80 passed`.

The test also reads `_OVERRIDES_CACHE`, i.e. whatever overrides the real
`aitasks/metadata/userconfig.yaml` holds (or a previous test left cached) — a
second, latent non-hermetic input: a developer who rebinds the sitrep quick-jump
would see it fail.

**Why fix the consumer, not the polluter:** the polluter is not one file —
19 test modules reset the registry, and resetting is their legitimate isolation
step. Making `test_shortcut_scopes.py` restore on tearDown would fix this one
pairing and leave 18 other producers able to cause the same flake. The test that
depends on import-time global state is the single point that must own its
precondition.

**Blast-radius check (done):** every other test module that reads the registry
without resetting it was run alone and after `test_shortcut_scopes.py` in one
process (`test_agent_command_dialog_narrow`, `test_agent_command_open_debounce`,
`test_board_footer_multirow`, `test_board_bytrail_view`, `test_frozenagent_app`,
`test_brainstorm_crew`, …). All pass in both orders (survey for the remaining few
completed: all 11 non-resetting registry consumers pass alone and after the sweep).
So the defect is local to this one test.

## Implementation

### 1. `tests/test_monitor_sitrep_harvest_close.py` — `SwitcherSitrepTests`

Rewrite `test_S_is_a_registered_quick_jump` so it establishes its own registry
state and restores the prior state afterwards (so it never becomes a polluter
itself):

```python
def test_S_is_a_registered_quick_jump(self):
    import tui_switcher as ts
    keys = {b.key: b.action for b in ts._QUICK_JUMP_BINDINGS}
    self.assertEqual(keys.get("S"), "shortcut_sitrep")

    # The registry is process-global and other modules' tests clear it
    # (keybinding_registry._reset_for_tests) without replaying tui_switcher's
    # import-time registration, so this assertion must not rely on whatever
    # state an earlier test left (t2225). Snapshot, start clean with no user
    # overrides, re-execute the module's real registration via the same sweep
    # the `?` editor uses, then restore.
    import keybinding_registry as kr
    import shortcut_scopes
    saved_defaults = dict(kr._DEFAULTS)
    saved_overrides = kr._OVERRIDES_CACHE

    def _restore():
        kr._DEFAULTS.clear()
        kr._DEFAULTS.update(saved_defaults)
        kr._OVERRIDES_CACHE = saved_overrides
    self.addCleanup(_restore)

    kr._reset_for_tests()
    kr._OVERRIDES_CACHE = {}  # hermetic: ignore the real userconfig.yaml
    failed = shortcut_scopes.register_scope_bindings("shared.tui_switcher")
    self.assertEqual(failed, [], f"sweep import failures: {failed}")
    self.assertEqual(kr.resolve_key(ts._TUI_SWITCHER_SCOPE, "shortcut_sitrep"),
                     "S")
```

Notes on the choices:
- `register_scope_bindings("shared.tui_switcher")` (`lib/shortcut_scopes.py:217`)
  **re-executes `lib/tui_switcher.py` under its probe name**, so the assertion
  still exercises the module's real import-time `register_app_bindings` call —
  not a hand replay of `_QUICK_JUMP_BINDINGS`, which would make the second
  assertion a tautology of the first. The probe name keeps
  `sys.modules["tui_switcher"]` untouched (t1211 design), so `ts` and every other
  test's top-level import keep their identity. It loads only the three
  `shared*`-scoped manifest modules (`agent_command_screen`, `stale_entry_modal`,
  `tui_switcher`), all light.
- `_OVERRIDES_CACHE = {}` after the reset makes the expected `"S"` a fact about
  the shipped default, not about the developer's userconfig.
- `addCleanup` restore keeps the rest of this module's (and later modules')
  view of the registry exactly as before the test.

No production code changes.

## Verification

1. Failing pair, now green:
   `~/.aitask/venv/bin/python -m pytest -q -p no:randomly tests/test_shortcut_scopes.py tests/test_monitor_sitrep_harvest_close.py`
2. Pre-fix control: the same command against the unmodified test already shown
   failing above (`None != 'S'`) — recorded in Context; re-confirm by running the
   pair with the hunk reverted in a scratch copy of the file (never `git
   stash`/`git restore` in this shared worktree).
3. Alone: `~/.aitask/venv/bin/python -m pytest -q tests/test_monitor_sitrep_harvest_close.py`
4. Reverse order (cleanup restores state, sweep tests still pass):
   `~/.aitask/venv/bin/python -m pytest -q -p no:randomly tests/test_monitor_sitrep_harvest_close.py tests/test_shortcut_scopes.py`
5. Hermetic-override check: temporarily (in-process, via a one-off scratch
   script) set `kr._OVERRIDES_CACHE = {"shared.tui_switcher": {"shortcut_sitrep": "X"}}`
   before running the test → still passes (the test pins `{}` itself).
6. Serial suite: `AIT_TEST_PARALLEL=0 bash tests/run_all_python_tests.sh`; read
   only the last line (`PYTHON SUITE: PASSED|FAILED`), check `${PIPESTATUS[0]}`
   if piped.

## Step 9 (Post-Implementation)

Commit `bug: Make the sitrep quick-jump test independent of registry state (t2225)`
naming only `tests/test_monitor_sitrep_harvest_close.py`; then the standard
Step 9 archival (current branch, no merge).

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
