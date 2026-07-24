---
Task: t1211_fix_python_test_suite_discovery_isolation.md
Base branch: main
plan_verified: []
---

# t1211 — Fix Python test-suite discovery isolation

## Context

`bash tests/run_all_python_tests.sh` (1802 tests) exits non-zero on a clean
tree: `FAILED (failures=4, errors=1)`. Because the aggregate suite is red at
rest, a real regression is indistinguishable from the standing noise, so every
task has to hand-pick its own modules — exactly the check most likely to be
skipped. Surfaced while verifying t1208.

Two independent defects, both now traced to root cause and reproduced.

### Defect 1 — the sweep clobbers `sys.modules` (the isinstance failures)

`.aitask-scripts/lib/shortcut_scopes.py:111` loads each manifest module with
`spec_from_file_location(module_name, path)` and then does
`sys.modules[module_name] = module` + `exec_module` **unconditionally** — even
when that module is already imported. The canonical entry is rebound to a fresh
module object, so its classes get a **second identity**.

Confirmed empirically: before the sweep `agent_command_screen.AgentCommandScreen`
is one class object; after `register_all_known_bindings()` `sys.modules` holds a
different module with a different class object.

Under discovery the sequence is:

1. discovery imports every `tests/test_*.py`, so `test_tui_switcher_agent_launch.py:24`
   binds `AgentCommandScreen` (identity **A**) at import time;
2. `tests/test_shortcut_scopes.py` (alphabetically before `test_tui_*`) calls
   `register_all_known_bindings()`, replacing `sys.modules["agent_command_screen"]`
   with identity **B**;
3. `tui_switcher.py:1144` / `:1238` do a **function-local**
   `from agent_command_screen import AgentCommandScreen`, resolved at call time →
   identity **B**;
4. `assertIsInstance(screen, AgentCommandScreen)` compares **B** against **A** → fail.

Reproduced in isolation:
`python3 -m unittest tests.test_shortcut_scopes tests.test_tui_switcher_agent_launch`
→ the same 4 failures.

**This is not only a test artifact.** `shortcuts_mixin.py:155` calls
`register_scope_bindings(self._shortcuts_scope)` when the user presses `?` in a
live TUI, and `shared.*` scopes always match — so pressing `?` in the board
re-executes `agent_command_screen.py` and `tui_switcher.py` and swaps their
classes underneath the running app.

### Defect 2 — script-style tests are invisible to (or break) discovery

`tests/test_gate_orchestrator_registry.py:198-203` runs its driver at module
level and ends with `sys.exit(...)`, so discovery reports a collection **ERROR**
(`SystemExit: 0`) and the aggregate run exits non-zero regardless of the code
under test.

Its 5 peers (`test_prompt_detection.py`, `test_gate_ledger_python_parser.py`,
`test_idle_compare_modes.py`, `test_stats_include_registered.py`,
`test_stats_multistage.py`) already carry `if __name__ == "__main__":` guards —
so they import cleanly but contribute **zero** collected tests. Merely guarding
the sixth file would make it match its peers while silently dropping 25 checks
out of the gate, and AC #2 ("a deliberately failing assertion in any collected
test makes the runner exit 1") could never reach any of them.

Per the decision taken during planning, all **6** script-style files are brought
into discovery — 102 previously-unrun checks.

## Approach

### Fix 1 — load manifest modules under a private probe name

Re-execution of the module body must be **kept**: `keybinding_registry` is reset
between sweeps (`_reset_for_tests()`), and module-level / class-body
registrations (`shared.tui_switcher`, `brainstorm.dag`) only re-fire on a fresh
exec. A "reuse the already-imported module" variant was prototyped and **breaks
4 of the 6 `test_shortcut_scopes` tests** for exactly this reason — rejected.

What must change is only the *name* the module is executed under. Load it as
`_shortcut_scopes_probe_<module_name>` so `sys.modules[<module_name>]` is never
rebound. This is already the established idiom in this repo —
`tests/test_board_archived_relation_lookup.py:42` loads the board under a unique
throwaway name for the same reason.

In `.aitask-scripts/lib/shortcut_scopes.py`:

- add a module constant `_PROBE_PREFIX = "_shortcut_scopes_probe_"`;
- in `_load_and_register`, compute `probe_name = _PROBE_PREFIX + module_name` and
  use it for `spec_from_file_location`, for the pre-`exec_module` `sys.modules`
  registration (the Python 3.14 dataclass workaround at the current line 111 —
  keep that comment, it is still load-bearing), and for the `sys.modules.pop` on
  the failure path;
- change the class filter from `cls.__module__ != module_name` to
  `!= probe_name` (classes defined in the probe-loaded module carry the probe
  name);
- keep `failed.append(module_name)` and the stderr message keyed on the
  **canonical** name — that is the caller-facing identifier the drift-guard test
  reports;
- extend the docstring to state the invariant: the sweep must never rebind a
  canonical `sys.modules` entry, and *why* re-exec is nonetheless required.

Probe entries are intentionally **left resident** in `sys.modules` after the
sweep (popping them risks breaking later lazy `__module__` resolution, and the
current code already leaves a re-exec'd module resident — just under the wrong
key). Because the probe name is a fixed key, repeated sweeps *overwrite* the
previous probe entry rather than accumulating: residency is bounded at one extra
copy per manifest module regardless of how many times the editor sweeps.

Verified: with this change `test_shortcut_scopes` stays 6/6 green **and**
`test_shortcut_scopes` + `test_tui_switcher_agent_launch` together run 20/20 OK,
with `sys.modules["agent_command_screen"]` and its class object identical
before/after the sweep.

Touch up the now-imprecise comment at `.aitask-scripts/settings/settings_app.py:3659`
("The sweep re-executes module bodies") to note it does so under a probe name.

### Fix 2 — uniform `main()` + unittest wrapper for the 6 script-style tests

One pattern for all six, chosen so the driver is **not duplicated** — the
wrapper delegates to the same `main()` the direct-run path uses, so a check
added to `main()` automatically enters discovery:

```python
class ScriptChecksTest(unittest.TestCase):
    """Collects this file's script-style checks under unittest discovery (t1211)."""

    def test_all_checks_pass(self):
        self.assertEqual(main(), 0, "script checks failed — see stdout above")


if __name__ == "__main__":
    sys.exit(main())
```

Per-file work:

| File | Work |
|---|---|
| `test_gate_ledger_python_parser.py` | has `main() -> int`; add `import unittest` + wrapper |
| `test_stats_include_registered.py` | has `main() -> int`; add `import unittest` + wrapper |
| `test_stats_multistage.py` | has `main() -> int` (owns its `tempfile` setup); add `import unittest` + wrapper |
| `test_gate_orchestrator_registry.py` | **no** `main()`: move the module-level driver loop + `print` + `sys.exit` into a new `main() -> int` returning `1 if FAIL else 0`, then add the wrapper. This is what removes the collection ERROR. |
| `test_idle_compare_modes.py` | driver inline in `__main__`: extract it into `main() -> int` (bare `assert`s propagate, so `return 0` at the end), then add the wrapper |
| `test_prompt_detection.py` | driver inline in `__main__` with a try/except tally: extract verbatim into `main() -> int` returning `1 if failures else 0`, then add the wrapper |

The counter-style files (`check`/`assert_eq` increment `FAIL` instead of raising)
are why the wrapper asserts on `main()`'s **return code** rather than relying on
an exception. Bare-assert files still surface a full traceback through `main()`.

Verified in a shared process: all six drivers run green together
(25 + 38 + 5 + 7 + 5 + 22 = 102 checks, aggregate rc 0).

### Fix 3 — pin the invariant

Add a `ModuleIdentityTests` case to `tests/test_shortcut_scopes.py`:

- **live failure surface** — import `agent_command_screen`, capture the module
  and class objects, run `register_all_known_bindings()`, assert `assertIs` on
  both. A second test does the same through `register_scope_bindings("board")`
  (the `?`-editor path, since `shared.*` is always relevant).
- **repeated sweeps** — the probe name is a *fixed* key, so every later sweep
  overwrites the previous probe entry; and the live shortcuts editor can invoke
  the filtered sweep many times over a process lifetime (`shortcuts_mixin.py`
  guards with `_subscopes_registered` per *instance*, so a second TUI screen
  sweeps again). Assert canonical identity after **each** of several consecutive
  calls — at minimum two `register_all_known_bindings()` and two
  `register_scope_bindings(...)` calls, checked after every call rather than only
  at the end. Also assert the probe entry *is* replaced between rounds while the
  canonical entry is not, so the test distinguishes "probe churn" (expected) from
  "canonical churn" (the bug). Prototyped: 3 rounds × (1 full + 2 filtered)
  sweeps keep the canonical module and class stable and the registered-scope
  count fixed at 19.
- **negative control** — prove the assertion is not vacuous: perform a
  deliberate canonical-name `spec_from_file_location` + `sys.modules[name] = …`
  load of the same file (the pre-fix behaviour) and assert the identity check
  *does* detect it, restoring the canonical entry in a `finally`. Without this,
  an `assertIs` that can never fail would pass forever.
- assert the probe key (`_shortcut_scopes_probe_agent_command_screen`) exists
  after a sweep and is a **different** object from the canonical entry — pins the
  mechanism structurally, not just its symptom.
- the case docstring must record *why* re-exec is load-bearing (the existing
  `ManifestDriftTests` / `TuiSwitcherScopeTests` already fail under a
  reuse-the-imported-module implementation, because module-level registrations
  do not re-fire after `keybinding_registry._reset_for_tests()`), so a future
  reader does not "simplify" the probe name away.

Do **not** restore state with `git checkout --`; the negative control undoes only
its own `sys.modules` mutation.

### Docs

`aidocs/framework/tui_conventions.md` (the `KNOWN_BINDING_SOURCES` section,
around lines 386-420) documents the sweep but not its import semantics. Add a
short paragraph: the sweep re-executes module bodies under a private probe name,
never rebinding the canonical `sys.modules` entry, and why (re-exec is needed to
re-fire module-level registrations; rebinding would give classes a second
identity).

## Files to modify

- `.aitask-scripts/lib/shortcut_scopes.py` — probe-name load (root-cause fix)
- `tests/test_shortcut_scopes.py` — `ModuleIdentityTests` + negative control
- `tests/test_gate_orchestrator_registry.py` — extract `main()`, guard, wrapper
- `tests/test_gate_ledger_python_parser.py`, `tests/test_idle_compare_modes.py`,
  `tests/test_prompt_detection.py`, `tests/test_stats_include_registered.py`,
  `tests/test_stats_multistage.py` — `main()` (where missing) + wrapper
- `aidocs/framework/tui_conventions.md` — document the probe-name invariant
- `.aitask-scripts/settings/settings_app.py` — one-line comment accuracy

## Verification

**Every command below must run under the same interpreter and import
environment as the harness.** `run_all_python_tests.sh:10-18` deliberately
resolves the aitask venv via `python_resolve.sh` instead of bare `python3`,
because `python3` may be a system interpreter lacking `yaml`/`textual`/`rich`
(t935) — a check that passes under bare `python3` proves nothing about the gate.
Preamble for steps 2-6:

```bash
source .aitask-scripts/lib/python_resolve.sh
PY="$(require_ait_python)"
export PYTHONPATH="$PWD/.aitask-scripts/board:$PWD/.aitask-scripts/lib"
export PYTHONDONTWRITEBYTECODE=1
```

(On a machine where `ait setup` has shimmed `PATH`, `python3` happens to resolve
to the same venv — which is exactly why the difference is easy to miss. Use
`"$PY"` regardless.)

1. **Aggregate gate green (AC 1)** — `bash tests/run_all_python_tests.sh`; expect
   exit 0, no failures, no collection errors, and a test count ~102 checks higher
   in coverage (collected-test count rises by 6 wrapper cases).
2. **Targeted regression (AC 4)** —
   `"$PY" -m unittest tests.test_shortcut_scopes tests.test_tui_switcher_agent_launch`
   → 20/20 OK. This is the pair that fails today.
3. **Direct-run preserved (AC 3)** — run each of the 6 files as
   `"$PY" tests/<file>.py`; each must still print its own summary and exit 0.
4. **Negative control — root cause (AC 4)** — revert only the `probe_name` change
   in `shortcut_scopes.py`, re-run (2): the 4 `assertIsInstance` failures **and**
   the new `ModuleIdentityTests` must fail. Restore by re-applying the edit.
5. **Negative control — harness can fail (AC 2)** — break one assertion inside a
   *newly wrapped* file (e.g. flip an expected value in
   `test_gate_orchestrator_registry.py`) and confirm
   `bash tests/run_all_python_tests.sh` exits **1**. Repeat for one bare-assert
   file (`test_idle_compare_modes.py`) to cover both harness shapes. Revert.
6. **Negative control — collection error (AC 3)** — temporarily restore the
   module-level `sys.exit` in `test_gate_orchestrator_registry.py` and confirm
   discovery reports it as an ERROR again. Revert.
7. **Live TUI smoke** — launch `ait board`, press `?` to open the shortcuts
   editor (this is the `register_scope_bindings` path), confirm the shared
   scopes still list and the board keeps working; then open
   `ait settings` → Shortcuts tab and confirm every TUI's bindings still appear
   (the `register_all_known_bindings` path — the drift guard would catch an
   empty sweep, but confirm visually).

Step 9 (Post-Implementation) handles merge approval, gate orchestration
(`risk_evaluated`), cleanup, and archival.

## Risk

### Code-health risk: medium

- `shortcut_scopes._load_and_register` is load-bearing for the Settings
  Shortcuts tab and every TUI's `?` editor; a wrong module identity there would
  silently empty the shortcuts list rather than raise · severity: medium ·
  → mitigation: none (accepted — `test_shortcut_scopes.py` is an existing
  characterization guard: the rejected reuse variant failed 4 of its 6 tests)
- Admitting 102 previously-unrun checks into the aggregate suite may expose new
  cross-test interference (shared `sys.modules` mutations, subprocess calls in
  `test_gate_ledger_python_parser.py`), which would make the gate red for a new
  reason · severity: medium · → mitigation: none (accepted — verification step 1
  runs the full suite in-task; new interference is in-scope to diagnose)
- Probe modules stay resident in `sys.modules`, so each manifest module has two
  live copies in a TUI process — memory only, no identity leak, bounded at one
  extra copy per module (the fixed probe key is overwritten, not accumulated,
  across repeated sweeps) · severity: low · → mitigation: none (accepted)

### Goal-achievement risk: medium

- The root cause is proven and the fix verified on the failing pair (20/20), but
  the full 1802-test discovery run with the 6 newly collected files has not yet
  been executed end-to-end — new interference could surface only there ·
  severity: medium · → mitigation: none (accepted — verification step 1)
- AC 2's negative control is a manual, non-committed step; if skipped, a
  "passing" aggregate suite could still be pinning nothing · severity: low ·
  → mitigation: guard_no_zero_collection_test_files

### Planned mitigations
- timing: after | name: guard_no_zero_collection_test_files | type: test | priority: medium | effort: low | addresses: goal-achievement — AC 2's negative control is manual / defect-2 class | desc: Add a discovery guard asserting every tests/test_*.py contributes at least one collected test, so a script-style or import-guarded file can never again silently drop out of the aggregate suite. Implementation constraint (measured during t1211 planning, carry into the task body): the guard must inspect discovery EXTERNALLY — run `unittest discover` in a subprocess and count collected tests per module — not from an in-process TestCase that imports its siblings, which is circular and re-triggers import-time side effects. It must also assert there are no `unittest.loader._FailedTest` entries: an import-failing module is attributed to the `unittest.loader` module, not its own name, so a broken file would otherwise still register a passing "test". Baseline at t1211 completion is an EMPTY zero-collection set across all 135 `tests/test_*.py` files, so no exclusion list is needed on day one — if one becomes necessary later it must be an explicit, commented allowlist, not a silent skip. Finally, `run_all_python_tests.sh` prefers pytest when installed and falls back to unittest; the two branches name modules differently, so the guard must state which branch it validates.

## Final Implementation Notes

- **Actual work done:** All three fixes landed as planned.
  1. `shortcut_scopes.py` — added `_PROBE_PREFIX = "_shortcut_scopes_probe_"`; `_load_and_register`
     now execs each manifest module under `probe_name`, using it for
     `spec_from_file_location`, the pre-`exec_module` `sys.modules` registration, the
     failure-path `pop`, and the `cls.__module__` class filter. `failed.append()` and the
     stderr message stay keyed on the **canonical** name. Docstring extended with the
     two-part invariant (re-exec is required; canonical rebinding is forbidden) and why.
  2. Six script-style test files brought into discovery with a uniform
     `main() -> int` + `ScriptChecksTest.test_all_checks_pass` wrapper that delegates to
     the same `main()` the `__main__` path uses (driver never duplicated).
     `test_gate_orchestrator_registry.py` needed the module-level driver + `sys.exit`
     extracted into `main()` — that is what removed the collection ERROR.
  3. `ModuleIdentityTests` in `tests/test_shortcut_scopes.py`: full-sweep and
     filtered-sweep (`?`-editor path) identity assertions, a repeated-sweep test
     (3 rounds × 3 sweeps, checked after every call) that also distinguishes expected
     probe churn from canonical churn, and a negative control that reproduces a
     canonical-name re-exec and asserts the check catches it.
  Docs: `aidocs/framework/tui_conventions.md` gained an "Import semantics of the sweep"
  paragraph; `settings_app.py:3659` comment corrected to mention the probe name.

- **Deviations from plan:**
  - The task was implemented in a session that **crashed** (PID 151619 on omg16); this
    session reclaimed the in-flight lock (`RECLAIM_CRASH`) and resumed at
    `resume_point = IMPLEMENT` rather than planning from scratch.
  - Verification step 2 expected 20/20 on the AC4 pair; the actual count is **24/24**,
    because `ModuleIdentityTests` adds 4 cases to `test_shortcut_scopes`. Not a
    regression — the plan's figure predated Fix 3 being written.

- **Issues encountered:** The crashed session died **mid-negative-control**: it had
  restored the module-level driver + `sys.exit(1 if FAIL else 0)` in
  `test_gate_orchestrator_registry.py` (Verification step 6) and never reverted it, leaving
  the block tagged `# NEGCTRL t1211 — remove this block` in the working tree. That
  re-introduced the exact collection ERROR Fix 2 exists to remove, so the task looked
  implemented but its headline AC was still failing. Removed it on resume. This is the
  concrete argument for running the *final* full-suite confirmation **after** every
  negative control has been reverted, not before.

- **Key decisions:**
  - For the AC4 root-cause negative control, temporarily setting `_PROBE_PREFIX = ""`
    (so `probe_name == module_name`) reproduces the pre-fix behaviour exactly with a
    **one-line, trivially reversible** edit, instead of reverting four call sites.
  - Negative-control state was restored by undoing only the specific mutation — never
    `git checkout --`, which would have wiped concurrent sessions' uncommitted work in
    this shared checkout.
  - The live TUI smoke (Verification step 7) is interactive and was **not** run in this
    session; queued as a manual-verification follow-up instead of being silently skipped.

- **Verification results:**
  - AC1 — `bash tests/run_all_python_tests.sh`: **1988 tests, OK, exit 0** (was
    `FAILED (failures=4, errors=1)`). Re-confirmed green after all negative controls
    were reverted.
  - AC2 — harness can fail, **both shapes**: breaking a counter-style check
    (`test_gate_orchestrator_registry.py`) → harness exit 1; breaking a bare-assert check
    (`test_idle_compare_modes.py`) → harness exit 1 with the AssertionError attributed to
    `test_idle_compare_modes.ScriptChecksTest.test_all_checks_pass`. The same run showed
    all **6** `ScriptChecksTest` cases collected, confirming no wrapped file dropped out.
  - AC3 — all 6 files still exit 0 when run directly; restoring the module-level
    `sys.exit` makes harness-identical discovery report `FAILED (errors=1)` /
    `SystemExit: 0` again.
  - AC4 — targeted pair 24/24 OK; with `_PROBE_PREFIX` neutralised the run fails with
    **7** failures (the 4 original `assertIsInstance` failures plus 3 `ModuleIdentityTests`),
    proving both the fix and the new tests are load-bearing.

- **Upstream defects identified:** None
