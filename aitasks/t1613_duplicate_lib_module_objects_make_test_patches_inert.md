---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [testing, test_infrastructure]
anchor: 1527
followup_kind: upstream_defect
created_at: 2026-08-25 18:46
updated_at: 2026-08-25 18:46
---

The Python test suite loads modules from `.aitask-scripts/lib/` under **more than
one module object**, so a test that patches a lib module by its own `import`
name can silently intercept nothing — and every assertion that was supposed to
observe the patch passes vacuously.

## Evidence (measured in t1527)

`tests/test_local_dep_parity.py` counter-wraps `gate_ledger.read_registry` and
`gate_ledger.code_digest` to prove the shared `DependentsEvaluator` really hoists
them out of a whole-tree scan. In isolation the test passed. Under
`bash tests/run_all_python_tests.sh` it failed with **`registry: 0`** — the patch
had intercepted nothing. Asserting module identity made the cause explicit:

```
AssertionError:
  <module 'gate_ledger' from '/…/.aitask-scripts/lib/gate_ledger.py'>
  is not
  <module 'gate_ledger' from '/…/.aitask-scripts/lib/gate_ledger.py'>
```

Two distinct module objects, same file. The test was fixed locally by patching
`dep_resolution.gate_ledger` (the object the code under test actually holds), but
that is a per-test workaround for a suite-wide hazard.

## Why it is dangerous

The failure mode is **silence in the passing direction**. A patch that
intercepts nothing does not raise; the counter simply stays at its initial
value, and a `assertLessEqual(counts["digest"], 1)`-shaped assertion is
*satisfied by zero*. Any test that patches a lib module to observe a call —
counting, faulting, stubbing a subprocess — can be inert and green. That is the
same class as t1207's subshell counters and the `|| echo SENTINEL` exit-0 trap:
the test reports success because the mechanism never ran.

## Likely cause

Suspected: `tests/lib/board_fixture.load_board_module()` imports
`aitask_board.py` under a synthetic module name via
`importlib.util.spec_from_file_location`, and the `sys.path` state at that
moment differs from a plain `import`, so the board's own `import gate_ledger`
resolves to a fresh object. Other candidates: test modules that `os.chdir` and
re-`sys.path.insert` the same directory under a different absolute/relative
spelling, and `.aitask-scripts` vs `.aitask-scripts/lib` both being on the path.
**Confirm before fixing** — the exact mechanism decides whether the fix is in
the fixture harness, in the path setup, or in a `conftest`.

## Scope

1. Identify how a second object is created (`sys.modules` census at suite start
   vs mid-suite, keyed by `module.__file__`).
2. Make lib imports single-instance, or — if a second object is unavoidable for
   the synthetic-board-module seam — make the hazard **loud**.
3. A guard is the point: a suite-level check that no two entries in
   `sys.modules` share a `__file__` under `.aitask-scripts/lib/`, failing with
   the duplicated names. This is what turns a silent vacuous pass into a test
   failure.

## Verification

- The guard must FAIL on today's tree (it is a real, present condition) and pass
  after the fix — demonstrate both, not just the second.
- A negative control: deliberately re-import a lib module under a second name
  inside a test and confirm the guard names it.
- Re-run `tests/test_local_dep_parity.py::EvaluatorFanOutTests` with its patch
  reverted to the local-import form and confirm it now fails loudly (it is the
  known instance of the hazard).
- `bash tests/run_all_python_tests.sh` stays green.

## Related

- **t1527** — surfaced this while single-sourcing local dependency resolution;
  its plan's "Issues encountered" records the measurement.
