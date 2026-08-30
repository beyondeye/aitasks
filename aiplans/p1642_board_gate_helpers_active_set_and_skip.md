---
Task: t1642_board_gate_helpers_active_set_and_skip.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1642 — Board gate helpers: active-set scoping and skip semantics

## Context

t1603_2 built `derive_workflow_phase` (the board's workflow-phase derivation
seam) and **deliberately did not reuse** the board's two existing gate-decision
helpers, because each carries a defect. That divergence was recorded as an
accepted residual in a comment at `aitask_board.py:285`. This task is the
reconciliation: fix both helpers by collapsing them onto the predicates
`derive_workflow_phase` already computes, so the **phase axis** and the
**in-flight actor axis** cannot disagree about who owes what.

The two defects, in `.aitask-scripts/board/aitask_board.py`:

1. **`_human_pending_gates` (line 2049)** tests `current.status != "pass"`.
   `gate_ledger.SATISFIED_STATUSES` is `{"pass", "skip"}`, so a **skipped**
   human gate — terminal-satisfied, absent from `archive_pending` — is reported
   as a pending human gate. Consequences today: the card offers `[s sign-off]`
   / `[f fail]` on a gate nothing is owed for, and when some *other* active gate
   is still pending the task is filed under the `human` actor column with
   `next_action: "pending human gate"` while the real owner is an agent.

2. **`_has_failed_gate` (line 2066)** iterates all of `state.current` minus
   `state.filtered_gates`. A gate **deleted outright** from the task's `gates:`
   field is in *neither* `active_gates` nor `filtered_gates`
   (`gate_ledger.read_active_tuple_from_text`, gate_ledger.py:720-738, fills
   `filtered` only from `active_gates_filtered` and otherwise falls back to
   `[]`), so a stale historical `fail` for such a gate still classifies the task
   as having a failed gate. This contradicts `TaskGateState`'s own documented
   rule (gate_ledger.py:157-162) that decision surfaces key off the active set.

Intended outcome: both helpers become thin delegations to two extracted,
shared predicates that `derive_workflow_phase` also uses; the accepted-residual
comment is replaced by the reuse it describes; the two newly-correct cases are
pinned in the in-flight view's own tests; and the *delegation itself* is guarded
so the drift cannot silently come back.

## Deliberate behavior change (call it out at review)

Deriving pending-human from `archive_pending` also means a **stale-signed**
human gate (ledger `pass`, code-bound witness no longer binding — t1416) now
appears in `human_gates`, because `demote_stale_signed` removes it from the
effective view and it is therefore in `archive_pending`. This is correct and is
what the task's diagnostic context asks for ("a stale signature is not"
satisfied), and it closes an existing gap: today such a card says
`awaiting re-sign: review_approved` but offers **no** `[s sign-off]` op, and
pressing `s` answers "No pending human gate for this task."

Group/`next_action` are unaffected — `_inflight_item_for`'s `stale_signed`
branch already sits ahead of the `human_gates` branch.

## Implementation

### 1. Extract the two shared predicates

`.aitask-scripts/board/aitask_board.py`, module level, immediately after
`_gate_progress` (~line 201) and before `derive_workflow_phase` (line 207) —
the same seam, same file region:

```python
def _pending_human_gates(state, registry: dict) -> list[str]:
    """Active HUMAN gates a person still owes, from ONE authority (t1642).

    Derived from ``archive_pending`` — the same list the archival guard reads —
    rather than a raw ``status != "pass"`` comparison, so it inherits
    `gate_ledger._gate_satisfied` for free: a ``skip`` is terminal-satisfied and
    cannot read as pending, while a ledger-``pass`` whose code-bound signature no
    longer binds IS pending (it needs re-signing, and `s`/`f` must reach it).
    ``archive_pending`` is a subset of ``active_gates`` by construction
    (`gate_ledger._archive_status_from_state` is passed the active set), so the
    result is active-set-scoped with no second filter — a profile-filtered or
    deleted human gate can never appear.

    An unreadable ledger (``state is None``) yields ``[]``: "could not tell" is
    not "a human owes something".
    """
    if state is None:
        return []
    return [g for g in state.archive_pending
            if registry.get(g, {}).get("type") == "human"]


def _failed_active_gates(state) -> list[str]:
    """ACTIVE gates whose current run failed, from ONE authority (t1642).

    Iterates ``active_gates`` rather than all of ``state.current`` minus
    ``filtered_gates``: a gate deleted outright from the task's ``gates:`` field
    is in NEITHER list, so subtracting only the filtered list still classifies
    on its stale historical ``fail``. Keying off the active set is
    `TaskGateState`'s own documented rule for decision surfaces.
    """
    if state is None:
        return []
    return [g for g in state.active_gates
            if g in state.current and state.current[g].status in ("fail", "error")]
```

### 2. Have `derive_workflow_phase` consume them

In the `--- B2. The ledger ladder ---` block (~line 277-292), replace the two
inline comprehensions for `pending_human` / `failed` with calls, and **rewrite
the "These deliberately do NOT reuse …" paragraph** (line 285-292) — it now
describes the opposite of the code. Replacement wording: the two functions are
the shared implementation, `TaskManager._human_pending_gates` /
`_has_failed_gate` delegate to them, so the phase axis and the actor axis cannot
disagree; the delegation is frozen by `SharedGatePredicateContractTest`.
`pending_procedure` (keyed on `kind == "procedure"`) stays inline — it has no
second consumer.

### 3. Collapse the two `TaskManager` helpers onto them

Replace the bodies at lines 2049-2074. `_has_failed_gate` keeps its `bool`
return — its name promises one, and `_inflight_item_for` consumes it as one:

```python
    def _human_pending_gates(self, result: GateStateResult) -> list[str]:
        """Pending human gates for the In-Flight view — the SAME predicate the
        phase axis uses (t1642); see `_pending_human_gates`. Body kept free of
        gate logic on purpose: `SharedGatePredicateContractTest` fails if any
        reappears here."""
        if result.state is None:
            return []
        return _pending_human_gates(result.state, self.gate_registry())

    def _has_failed_gate(self, result: GateStateResult) -> bool:
        """Whether an ACTIVE gate's current run failed (t1642); see
        `_failed_active_gates`. Same no-gate-logic contract as above."""
        return bool(_failed_active_gates(result.state))
```

`_inflight_item_for` is **unchanged**.

### 4. Fix the now-wrong `InFlightItem.stale_signed` comment

Lines 129-132 currently read "Distinct from human_gates … these DID pass". After
step 3 a stale-signed gate **is** in `human_gates`. Rewrite to: it is in
`human_gates` (the archival guard owes a person, and `s`/`f` must work), and
this list is the separate fact of *why* — a re-signature of an approval
invalidated by a code change, not a first signature — which is what
`_inflight_item_for` renders ahead of the generic pending-human wording.

### 5. Share the active-tuple fixture helper

`tests/test_board_workflow_phase.py` has `_active_tuple_fm` (line 170) building
a **valid** `active_gates` tuple with the production digest helpers. The new
in-flight tests need exactly this, and a second copy would drift.

- Move it to `tests/lib/board_fixture.py` as `active_tuple_fm(gates, active,
  filtered)` (add `import gate_ledger`; the module already puts
  `.aitask-scripts/lib` on `sys.path` for `task_yaml`).
- In `test_board_workflow_phase.py` replace the `def` with the one-line alias
  `_active_tuple_fm = bf.active_tuple_fm`, leaving its ~20 call sites untouched.

### 6. Behavior tests — `tests/test_board_inflight_view.py`

New class `InFlightActiveSetTests(bf.FixtureBoardTestBase, unittest.TestCase)`,
using `bf.active_tuple_fm` + the file's existing `_task` / `_body` helpers and
`_manager(self.ab)`. The class fixture stages `metadata/gates.yaml`, so
`review_approved`/`plan_approved` are `type: human` and `tests_pass`/`lint` are
`type: machine`.

Defect 1 (skip):

1. `test_skipped_human_gate_is_not_pending` — active `[plan_approved,
   review_approved]`; ledger `plan_approved: pass`, `review_approved: skip`.
   Precondition `archive_decision == "ALL_PASS"`. Assert `item.human_gates ==
   []` and `next_action == "all gates pass — archive/re-enter"`.
2. `test_skipped_human_gate_does_not_own_the_actor_column` — **the
   discriminating case**: active `[plan_approved, review_approved, tests_pass]`;
   `plan_approved: pass`, `review_approved: skip`, `tests_pass: pending`. Today
   → `human` / `"pending human gate"`. After → `human_gates == []`, group
   `agent`, `"plan approved — resume implementation"`.
3. `test_pending_human_gate_still_owns_the_actor_column` — **negative control**
   for #2: the identical fixture with `review_approved: pending` instead of
   `skip` must still give `human_gates == ["review_approved"]` and group
   `human`, proving #2 discriminates on the `skip` and not on the fixture shape.

Defect 2 (inactive historical failure):

4. `test_historical_failure_of_inactive_gate_does_not_classify` — active
   `[plan_approved, review_approved]`; ledger `plan_approved: pass`,
   `review_approved: pending`, plus `tests_pass: fail`. Preconditions:
   `tests_pass` in `current`, in **neither** `active_gates` nor
   `filtered_gates`. Today → `"failed gate — inspect/sign off or fail"`. After →
   `"pending human gate"`, `human_gates == ["review_approved"]`.
5. `test_profile_filtered_failure_still_does_not_classify` — the already-correct
   sibling route into "not active", asserted so the rewrite does not regress it:
   `gates: [plan_approved, review_approved, lint]`, active
   `[plan_approved, review_approved]`, filtered `[lint]`; `plan_approved: pass`,
   `review_approved: pending`, `lint: fail` → `"pending human gate"`.
6. `test_active_gate_failure_still_classifies` — **positive control** for #4/#5:
   active `[plan_approved, tests_pass]`, `plan_approved: pass`,
   `tests_pass: fail` → group `human`, `"failed gate — inspect/sign off or
   fail"`. Without this, #4 and #5 could pass against a `_has_failed_gate` that
   always returns `False`.

### 7. Guard the delegation itself (the anti-drift half)

Step 6 pins the *answers* on one surface and the existing
`test_board_workflow_phase.py` cases pin them on the other — but a
re-implementation that **duplicates** the corrected logic in both places would
pass every one of them today and quietly restore the drift this task exists to
remove. Two cheap guards close that, one structural and one behavioral.

**7a. `SharedGatePredicateContractTest` — `tests/test_board_gate_digest_budget.py`.**
Same `ast` + `BOARD_SRC` idiom as the `ClearGateCacheCallersTest` already in
that file (line 267), which freezes call sites for exactly this reason:

- **Frozen call sites.** Callers of `_pending_human_gates` must be exactly
  `{"derive_workflow_phase", "_human_pending_gates"}`; callers of
  `_failed_active_gates` exactly `{"derive_workflow_phase", "_has_failed_gate"}`.
  Assert non-empty first, so a renamed predicate fails loudly instead of
  passing vacuously. The visitor must match `ast.Name` calls (these are bare
  module-level functions), not only `ast.Attribute` as the existing one does.
- **No re-duplicated logic.** Within the bodies of
  `TaskManager._human_pending_gates` and `TaskManager._has_failed_gate`,
  assert there is **no** attribute access named `archive_pending`,
  `active_gates`, `filtered_gates` or `current`, and **no** string constant in
  `{"pass", "skip", "fail", "error", "human"}`. That is the precise shape of the
  defect being removed, so its reappearance in either method fails here.
  (`derive_workflow_phase` is *not* subject to this half — it legitimately still
  reads `archive_pending` for `pending_procedure` — only the frozen-call-site
  half applies to it.)

**7b. `TwoAxisAgreementTests` — `tests/test_board_workflow_phase.py`.**
The behavioral counterpart, so the contract does not rest on source shape alone.
One fixture matrix (reusing `_active_tuple_fm` and covering both defect cases
plus their controls) driven through **both** surfaces, asserting per fixture:

- `TaskManager._human_pending_gates(mgr, result)` equals
  `ab._pending_human_gates(result.state, mgr.gate_registry())`;
- `TaskManager._has_failed_gate(mgr, result)` equals
  `bool(ab._failed_active_gates(result.state))`;
- and the phase axis agrees with that same predicate: where the shared
  pending-human set is non-empty (and no `stale_signed` / failed gate precedes
  it) `derive_workflow_phase` reports `awaiting_review`; where it is empty, it
  does not.

Vacuity guard: assert the matrix contains at least one fixture with a non-empty
pending-human set and at least one with a non-empty failed set, so the equalities
cannot all hold merely by both sides being empty everywhere.

### 8. Test — the deliberate stale-signed change

Staleness needs a real witness file plus a code mutation, which
`tests/test_board_gate_digest_budget.py` already provides (`_sign_all()` /
`_mutate_code()` / `_refresh()`). Add to `DigestInvalidationTest`, beside
`test_gate_summary_shows_both_facts`:

- `test_stale_signature_is_offered_for_re_sign` — sign, refresh, mutate code,
  refresh; assert `item.stale_signed == ["review_approved"]`, `item.human_gates
  == ["review_approved"]`, `next_action == "awaiting re-sign: review_approved"`
  (unchanged — group precedence is untouched), and `"[s sign-off]" in
  self.ab.InFlightTaskCard._ops_hint(item)`.

Do **not** duplicate this in the fixture-tree tests; that file has no witness
machinery.

### 9. Docs

`website/content/docs/tuis/board/how-to.md:208` says `s`/`f` "sign off or fail a
pending human gate". Extend it to note that this includes a gate whose signature
has gone stale and needs re-signing. `reference.md:65-66` stays accurate as-is.

## Risk

### Code-health risk: low

- The stale-signed inclusion is a real behavior change to the `s`/`f` action
  surface and to `_ops_hint`, reached only through a fix framed as scoping ·
  severity: medium · → mitigation: covered by plan steps 4 (comment rewrite) and
  8 (explicit pinning test).
- The whole point of the change — one predicate, two consumers — is invisible to
  outcome-only tests: a later edit could re-inline the corrected logic in
  `TaskManager` and keep every behavior test green while restoring the drift ·
  severity: medium · → mitigation: covered by plan step 7 (frozen call sites +
  no-gate-logic assertion + behavioral two-axis parity).
- Blast radius is one module region plus three test files; `_inflight_item_for`
  and the ladder ordering are untouched · severity: low · → mitigation: none
  needed.

### Goal-achievement risk: low

- The task's own example ("shows 'pending human gate'" for an `ALL_PASS` task
  with a skipped `review_approved`) does not hold literally — the `ALL_PASS`
  branch precedes the `human_gates` branch in `_inflight_item_for`, so
  `next_action` reads "all gates pass". A test written only against that example
  would be vacuous about the actor-column claim · severity: medium · →
  mitigation: covered by plan step 6, cases 2 and 3 (a fixture where the actor
  column genuinely flips, plus its negative control).

No mitigations are spawned as separate tasks: all three are test-and-comment
deliverables already required by the plan steps above.

## Verification

1. Targeted, from the repo root:
   ```bash
   python3 -m unittest tests.test_board_inflight_view \
       tests.test_board_workflow_phase tests.test_board_gate_digest_budget -v
   ```
2. **Discrimination check** — before applying the source change (or by
   temporarily reverting it), the six new in-flight cases must FAIL on the
   shipped helpers except the three controls (#3, #5, #6), which must pass in
   both states.
3. **Guard check** — verify step 7a can actually fail: temporarily re-inline the
   old comprehension into `TaskManager._human_pending_gates` and confirm both
   the frozen-call-site and no-gate-logic assertions report it, then revert.
4. Full suite; read the **last line** for the verdict and keep the exit status:
   ```bash
   set -o pipefail
   bash tests/run_all_python_tests.sh
   ```
5. Live board sanity check: `ait board`, press `i`, confirm the In-Flight rows
   and their `[s sign-off]` hints still render.

## Step 9 (Post-Implementation)

Cleanup, archival, and merge follow `task-workflow` Step 9 — the task is
current-branch (`create_worktree: false`), so there is no task branch to merge.
Active gate: `risk_evaluated`.
