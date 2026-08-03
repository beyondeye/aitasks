---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: test
status: Implementing
labels: [test]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1111
implemented_with: claudecode/opus5
created_at: 2026-08-03 15:25
updated_at: 2026-08-03 16:59
boardidx: 12288
---

## Origin

Risk-mitigation ("after") follow-up for t1354_4, created at Step 8d after
implementation landed.

## Risk addressed

Code-health, severity low: "The duplicate-inheritance pattern can silently
return the next time someone subclasses a test-defining class."

In t1354_4, `TabbedShellTests` in `tests/test_syncer_rows.py` defined 25 test
methods *and* served as the helper base for three subclasses. Because unittest
and pytest both collect inherited test methods, each subclass silently re-ran
all 25 — **75 duplicate `SyncerApp` boots, ~46s, about half that file's
runtime**, testing nothing the base run had not already covered. It was
invisible for as long as it existed: every duplicate passed.

## Goal

Add a structural guard asserting that no class in a `tests/test_*.py` module
subclasses another class **in the same module** that defines its own `test_*`
methods.

Reuse the AST scan written during t1354_4 planning (it walks each module's
top-level `ClassDef`s, maps base names via `ast.Name`, and counts the base's own
`test_*` / `async def test_*` members). Run tree-wide it found exactly one
instance — the one t1354_4 fixed — so the guard should currently report **ZERO**
and the allowlist should be empty by design, like `ZERO_COLLECTION_ALLOWLIST`.

The sanctioned fix when the guard fires is the one t1354_4 used: extract a
test-free `_PrefixedBase` holding only the helpers, keep the tests in a concrete
subclass, and re-point the other subclasses at the base. The leading underscore
is what keeps the base out of collection (same pattern as `GitRepoTestBase` /
`BrainstormCrewTestBase`).

## Verification Steps

- Guard reports zero violations on the current tree with an empty allowlist.
- **Negative control:** run the guard against a synthetic tests dir containing a
  base class with its own `test_*` plus a subclass, and assert it flags **that
  file and class pair by name** — observed failing before the guard is trusted.
  A guard that cannot detect the exact defect class t1354_4 just removed would
  be decorative.
- Note the related-but-distinct t1375 guard (`bare_module_test_fn_guard`) covers
  module-level `def test_*`; this one covers inherited class tests. Consider
  whether they belong in one module.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-03T13:59:44Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-03T19:37:31Z status=pass attempt=1 type=human
