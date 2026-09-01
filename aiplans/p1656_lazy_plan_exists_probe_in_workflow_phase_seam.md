---
Task: t1656_lazy_plan_exists_probe_in_workflow_phase_seam.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1656 — Lazy `plan_exists` probe in the workflow-phase seam

## Context

`derive_workflow_phase` (`.aitask-scripts/board/aitask_board.py:266`) takes
`plan_exists: bool` as an **eagerly-evaluated** keyword but reads it on
**exactly one** of its branches — B1, the no-ledger degradation at line 335
(`"derived" if plan_exists else "unknown"`). The deferred-plan-marker branch
(A), the `result.error` branch (B0) and the whole B2 ledger ladder all return
without touching it.

So `_inflight_item_for` (`aitask_board.py:2305`) pays one `Path.exists()` per
admitted in-flight item, per board refresh, and discards it in every state but
one. The cost is bounded by the in-flight set — the `status` pre-filter rejects
`Ready`-without-marker before any of this — so it is small but avoidable, and it
works against the cheap-pre-filter goal t1603_3 adopted for exactly this path.

The caller-side fix is the wrong one: computing it conditionally
(`if not result.error and (not result.has_ledger or result.state is None)`)
restates the ladder's own branch conditions in its caller — a second authority
over precisely the derivation t1603_2/t1603_3 centralised, which drifts the
moment the ladder's ordering changes. The laziness belongs **in the seam**.

The pattern already exists in this file: `TaskManager.gate_state_for` passes
`self.code_digest_for_refresh` — the **bound method, not its value** — so a
~5 ms git subprocess is never paid by a board with no signed witnesses
(`aitask_board.py:2164-2168`, resolved by `gate_ledger._resolve_digest`).

**Outcome:** a laziness change only. Every phase/provenance answer is
byte-identical; what changes is *when* the filesystem is touched.

---

## Deliberate deviation from the task text

The task writes the new signature as `derive_workflow_phase(..., *, plan_exists)`.
**This plan renames the parameter to `plan_exists_probe`** and makes it
**callable-only** (no `bool | Callable` union). Both choices are safety
properties, not cosmetics:

- A parameter named `plan_exists` that now holds a callable makes
  `"derived" if plan_exists else "unknown"` — the *existing* line — silently
  always-truthy if anyone forgets the `()`. Every in-flight legacy task would
  report `derived` when it should report `unknown`, with no test failing on the
  *type*. The rename makes that line impossible to leave un-updated.
- The parameter is keyword-only, so the rename turns every un-updated call site
  into an immediate `TypeError` instead of a silent semantic flip. There are
  only two call sites (one production, one test helper), so the churn is nil.
- A union would add a `callable(x)` branch — the four-state ambiguity
  `_resolve_digest` needs a load-bearing ordering note to keep straight — for no
  benefit at two call sites.

---

## The change

### 1. `.aitask-scripts/board/aitask_board.py` — the seam

**a. Import.** Add `from typing import Callable` beside `from pathlib import Path`
(line 14). The file has `from __future__ import annotations`, so the annotation
is never evaluated at runtime, but the import keeps the name resolvable for
linters/readers.

**b. Signature** (line 266-267):

```python
def derive_workflow_phase(task: "Task", result: GateStateResult, registry: dict,
                          *, plan_exists_probe: Callable[[], bool]) -> WorkflowPhase | None:
```

**c. B1 branch** (line 335) — resolve the probe *here*, the only place that
reads it:

```python
        return WorkflowPhase("implementing",
                             "derived" if plan_exists_probe() else "unknown")
```

**d. Docstring.** Replace the `callers thread ``plan_exists`` from
`_resolve_plan_path_for_task`` sentence in the "Pure and app-free" paragraph
with the lazy-probe contract, and add a short paragraph stating:

- The probe is a **callable**, invoked **at most once** and **only** on the B1
  no-ledger branch — so a task in any other state costs no filesystem access.
  This mirrors `TaskManager.gate_state_for` passing `code_digest_for_refresh`
  as a bound method; the laziness lives here rather than in the caller
  precisely so the caller never restates the ladder's branch conditions.
- Total by contract, same rule as `gate_ledger._resolve_digest`: a raising
  probe **propagates**. Making the probe total is the caller's job; swallowing
  here would reinterpret a caller bug as a phase answer.
- The seam stays app-free — it performs no filesystem access *of its own*; the
  closure the caller supplies does.

### 2. `.aitask-scripts/board/aitask_board.py` — the call site

`_inflight_item_for`, lines 2297-2307. Replace the `KNOWN COST, tracked as
t1656` comment block with the resolved note, and pass the closure:

```python
        phase = derive_workflow_phase(
            task, result, self.gate_registry(),
            # The CALLABLE, not its value (t1656) — the same shape
            # `gate_state_for` uses for `code_digest_for_refresh`. Exactly one
            # of `derive_workflow_phase`'s branches reads it (the no-ledger
            # degradation), so an in-flight item in any other state now pays no
            # `Path.exists()` at all. Do NOT hoist the decision here by testing
            # `result.error` / `result.has_ledger`: that restates the ladder's
            # branch conditions in the caller and drifts the moment their order
            # changes. The laziness belongs in the seam.
            plan_exists_probe=lambda: _resolve_plan_path_for_task(task, self) is not None)
```

No other production call site exists (verified: `grep -rn derive_workflow_phase`
finds only this one plus docstring/comment references).

### 3. `tests/test_board_workflow_phase.py` — the seam

**a. Import.** Add `import inspect` beside `import sys` / `import unittest`
(line 12). The module does not currently import it, and the signature-contract
test in **(d)** would error rather than verify without it.

**b. `_CountingProbe`** — new module-level helper beside `_write` / `_task`:

```python
class _CountingProbe:
    """Plan-existence probe that records how many times it was invoked (t1656).

    A COUNTING SPY, not a mock. `mock.assert_not_called()` would pass vacuously
    if the parameter were dropped, renamed, or silently coerced to a bool at the
    call boundary; a spy that is threaded through `_derive` and then counted
    cannot pass without actually reaching the seam.
    """

    def __init__(self, inner):
        self._inner = inner
        self.calls = 0

    def __call__(self) -> bool:
        self.calls += 1
        return self._inner()
```

**c. `WorkflowPhaseTestBase._derive`** (line 191) — wrap the real probe and
expose it, plus an injection hatch:

```python
    def _derive(self, name: str, body: str, *, plan: bool = False,
                break_ledger_read: bool = False, probe=None):
        ...
        # Wrapped for EVERY fixture, not only the laziness tests: the whole
        # existing matrix then doubles as invocation accounting, and the phase
        # answers below stay the production answers.
        self.last_probe = _CountingProbe(
            probe if probe is not None
            else (lambda: self.ab._resolve_plan_path_for_task(task, mgr) is not None))
        phase = self.ab.derive_workflow_phase(
            task, result, mgr.gate_registry(), plan_exists_probe=self.last_probe)
        return phase, result
```

Every existing test keeps its assertions unchanged — that *is* the "phase
answers are unchanged" half of the verification.

**d. Single canonical enumeration.** Lift
`LadderTotalityAndPrecedenceTests._matrix`'s body (line 624) to a module-level
`_phase_matrix()`; the method becomes `return _phase_matrix()`. The new
laziness test then walks the **same** rung list the totality test does, so a
future rung added to the ladder is covered by both without a second edit.

**e. New class `PlanExistsProbeLazinessTests(WorkflowPhaseTestBase,
unittest.TestCase)`** — placed after `LadderTotalityAndPrecedenceTests`:

- `test_probe_is_untouched_on_every_branch_that_does_not_read_it` — walk
  `_phase_matrix()` and assert `self.last_probe.calls == expected`, where
  **`expected` is derived from the matrix row**, not hardcoded per fixture:
  `1 if want_prov in ("derived", "unknown") else 0` (those two provenances are
  exactly B1's outputs). This covers, from the existing matrix: the three
  `None` answers (`t940` Ready, `t941` Editing, `t942` Done), the marker branch
  (`t943`), the unreadable-ledger branch (`t946`), and every rung of the ladder
  (`t947` awaiting_review, `t948` needs_attended_agent, `t949` post_impl,
  `t950` plan_approved, `t951` implementing).

- `test_no_ledger_branch_invokes_the_probe_exactly_once_and_reads_it` —
  **POSITIVE CONTROL**, both outcomes, via the `probe=` hatch:
  `probe=lambda: True` → `("implementing", "derived")` and `calls == 1`;
  `probe=lambda: False` → `("implementing", "unknown")` and `calls == 1`.
  Docstring states why: without this, every assertion above would pass against
  a seam that ignores the parameter entirely, and `calls == 1` (not `>= 1`)
  is what pins "resolved once on the branch", not re-probed per read.

- `test_the_probe_parameter_is_keyword_only_and_named_for_its_laziness` —
  `inspect.signature(self.ab.derive_workflow_phase)`: the parameter is
  `KEYWORD_ONLY` and named `plan_exists_probe`. Docstring carries the reason
  the name is load-bearing (a callable bound to `plan_exists` makes the B1
  ternary silently always-truthy, and keyword-only + renamed is what turns an
  un-updated call site into a `TypeError` instead of a wrong phase).

### 4. `tests/test_board_inflight_planned_lane.py` — the caller boundary

**Everything in §3 tests the seam with a probe the test itself supplies, so
none of it constrains what `_inflight_item_for` passes.** A caller that
regressed to an eager expression —
`plan_exists_probe=_resolve_plan_path_for_task(task, self) is not None`, or a
lambda whose body got hoisted out — still pays one `Path.exists()` per admitted
in-flight item on every refresh, which is precisely the cost t1656 exists to
remove, while every §3 test stays green. This is the test that fails on that.

The spy is unambiguous here: within the `get_inflight_items()` →
`_inflight_item_for` path, line 2307 is the **only** `_resolve_plan_path_for_task`
call site (the other two, `TaskDetailScreen.plan_path` at 7013 and
`KanbanApp` at 13421, are not on this path). And `_inflight_item_for` resolves
the helper as a module global, so patching the attribute on the fixture-bound
board module is seen by the production function.

New class `PlanProbeCallerBoundaryTests(PlannedLaneTestBase, unittest.TestCase)`,
placed after `PlannedAdmissionTests`. No new import — the spy is installed by
attribute assignment with `addCleanup` restore, matching how the module already
avoids `mock`:

```python
    def _item_with_spy(self, name: str, body: str):
        """`_item`, with every production `_resolve_plan_path_for_task` recorded."""
        calls: list[str] = []
        real = self.ab._resolve_plan_path_for_task

        def spy(task, manager):
            calls.append(task.filename)
            return real(task, manager)        # delegate: the answers stay real

        self.addCleanup(setattr, self.ab, "_resolve_plan_path_for_task", real)
        self.ab._resolve_plan_path_for_task = spy
        item, _ = self._item(name, body)
        return item, calls
```

- `test_admitted_items_that_do_not_read_it_resolve_no_plan_path` — subTests over
  the two admitted non-B1 states, asserting `calls == []` **and** the real
  phase/provenance, so it cannot pass because the fixture fell out of admission
  (`_item` already asserts exactly one item):
  - `_implementing_twin_body()` → B2 ladder, `("plan_approved", "ledger")`;
  - `_planned_body()` → branch A, `("plan_approved", "ledger")` — the marker
    branch, and the most common state on a real board.

- `test_no_ledger_item_resolves_the_plan_path_exactly_once` — **POSITIVE
  CONTROL** at this boundary: `_body("Implementing")` (no ledger, no plan file)
  must give `len(calls) == 1` and `("implementing", "unknown")`. Without it the
  test above would pass against a caller that dropped the argument entirely, or
  against a seam that never reads it.

### 5. Not edited

`tests/test_board_gate_digest_budget.py` needs no change — its
`SharedGatePredicateContractTest` freezes `_pending_human_gates` /
`_failed_active_gates`, neither of which this touches, and
`PhaseIsTheOnlyLaneAuthorityTest`'s `_inflight_item_for` scan forbids
`archive_pending` / `active_gates` / `filtered_gates` / `current`, none of which
the new lambda introduces. Both are run as regression checks.

---

## Verification

Targeted first, then the suite:

```bash
~/.aitask/venv/bin/python -m pytest tests/test_board_workflow_phase.py \
                                   tests/test_board_inflight_planned_lane.py \
                                   tests/test_board_gate_digest_budget.py -q
bash tests/run_all_python_tests.sh --test-dir tests
```

Read **only the last line** of the runner output —
`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`; an earlier
`Results: N passed, 0 failed` belongs to one script-style module, not the suite.
Do not pipe to `tail` without `set -o pipefail` / `${PIPESTATUS[0]}`.

What each check buys:

- **Laziness at the seam** —
  `test_probe_is_untouched_on_every_branch_that_does_not_read_it` proves no
  non-B1 branch resolves the probe, over the canonical rung list.
- **Laziness at the production boundary (the actual performance claim)** —
  `PlanProbeCallerBoundaryTests` proves `_inflight_item_for` supplies the probe
  *unevaluated*: zero `_resolve_plan_path_for_task` calls for an admitted
  ledger-backed item and for a marker-branch item. The seam tests alone cannot
  show this, because they supply the probe themselves.
- **Non-vacuity** — a positive control at **each** level (seam: exactly one
  invocation answering `derived`/`unknown` correctly on both outcomes;
  boundary: exactly one `_resolve_plan_path_for_task` call for a no-ledger
  item). Without them, both zero-call assertions would pass against a parameter
  that was dropped outright.
- **No semantics change** — the full pre-existing
  `tests/test_board_workflow_phase.py` matrix (totality, reachability,
  precedence, progress authority, two-axis agreement) runs unchanged against
  the wrapped probe.
- **No structural regression** — `test_board_gate_digest_budget.py`'s AST
  contract tests still pass.

Post-implementation cleanup, archival and merge follow **Step 9** of the
task-workflow skill.

## Risk

### Code-health risk: low

- A callable bound to a name that reads as a boolean makes the existing B1
  ternary silently always-truthy — the phase would degrade to `derived` for
  every legacy in-flight task with no test failing on type · severity: medium ·
  → mitigation: inline — the `plan_exists_probe` rename (keyword-only, so an
  un-updated call site is a `TypeError`) plus the positive control pinning both
  `derived` and `unknown` outcomes; both are plan steps above.
- Wrapping the probe for *every* fixture in `_derive` changes the shared test
  base, so a mistake there would silently alter what the whole existing matrix
  exercises · severity: low · → mitigation: inline — the wrapper only counts and
  delegates; the unchanged pass of the full pre-existing matrix is the check.

### Goal-achievement risk: low

- The stated goal is a **performance** one, but the seam-level tests verify only
  that the seam resolves a supplied probe lazily — they are blind to an eager
  caller expression, which would leave the board paying exactly the
  `Path.exists()` per admitted item that the task exists to remove, with the
  whole suite green · severity: high · → mitigation: inline — §4's
  `PlanProbeCallerBoundaryTests` spies on `_resolve_plan_path_for_task` at the
  production boundary (`get_inflight_items` → `_inflight_item_for`) and asserts
  zero calls for ledger-backed and marker-branch items, one for no-ledger.
- Requirement coverage is otherwise complete: the task specifies the seam, the
  pattern to follow, the call sites, and the verification shape. The only
  deviation (parameter name, callable-only rather than a union) is stated
  explicitly above and the task text leaves both open.
