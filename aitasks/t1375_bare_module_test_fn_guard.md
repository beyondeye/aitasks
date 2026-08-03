---
priority: low
effort: low
depends: []
issue_type: test
status: Ready
labels: [test, bash_scripts]
gates: [risk_evaluated]
anchor: 1111
created_at: 2026-08-03 09:42
updated_at: 2026-08-03 09:42
---

## Origin

Risk-mitigation ("after") follow-up for t1354_3, created at Step 8d after implementation landed.

## Risk addressed

> The six script-style modules keep a tally-based `assert_eq` that never raises,
> so the *class* of defect (a module-level `def test_*` passing vacuously under
> pytest) can silently return the next time someone adds one · severity: low

## Goal

Add a structural guard asserting that no `tests/test_*.py` defines a
module-level `def test_*`, with a negative control proving the guard flags a
synthetic offender.

### Why a second guard, given t1354_3 shipped `tests/test_collection_parity.py`

The parity test compares per-file collected counts across both backends, and it
does catch this shape — but only on a machine that has the opt-in dev tier
installed. It is `skipUnless(pytest importable)`, so on a default install
(`unittest` backend, no `ait setup --with-dev`) it does not run at all. A
contributor without the tier can therefore add a bare module-level `def test_*`
and see a fully green suite.

A purely structural AST/grep guard has no such dependency: it runs on both
backends, costs milliseconds, and names the offending file and function
directly rather than reporting a count discrepancy the reader must then
diagnose.

### Why the shape matters (measured in t1354_3)

Four of the six modules use a tally-based `assert_eq` that increments a counter
instead of raising. Under pytest their bare driver functions were collected and
**passed vacuously** — a genuinely failing check reported green — while also
double-running every check and corrupting the module-global `PASS/FAIL/TOTAL`
counters that the module's own `ScriptChecksTest` asserts on. The other two use
raising asserts, so they merely ran everything twice. t1354_3 renamed 32 such
functions to `_check_*`; nothing currently prevents the 33rd.

## Suggested approach

- Scan every `tests/test_*.py` with `ast` for module-level `FunctionDef` /
  `AsyncFunctionDef` whose name starts with `test_`. Prefer AST over grep so a
  `def test_*` inside a docstring or string constant is not flagged (t1354_2's
  guard work established this distinction).
- Failure message should name file + function and state the fix: rename to
  `_check_*` and call it from the module's `main()`.
- Negative control: a synthetic module in the test's own tmpdir, asserted
  flagged **by name**; plus a clean module asserted **not** flagged, so the
  control cannot pass for the trivial reason that everything is flagged. Never
  mutate a real test file on disk to demonstrate the guard.
- Consider whether the guard belongs alongside the existing structural sweep in
  `tests/test_board_fixture_harness.py` (t1354_2) or in its own file — that file
  already owns a fail-closed AST scanner with an expression-scoped allowlist and
  is the closest prior art.
- Allowlist, if any, must be empty by design with a written justification per
  entry (the policy used by `ZERO_COLLECTION_ALLOWLIST` and `PARITY_ALLOWLIST`).
