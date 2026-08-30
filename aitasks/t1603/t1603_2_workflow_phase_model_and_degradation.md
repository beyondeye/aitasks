---
priority: medium
effort: medium
depends: [t1603_1]
issue_type: feature
status: Ready
labels: [board, gates, task_workflow]
gates: [risk_evaluated]
anchor: 1595
created_at: 2026-08-30 13:28
updated_at: 2026-08-30 13:28
---

## Context

Part of t1603 (surface the deferred-plan marker on the board). The board's
in-flight view groups tasks by *required next actor* and shows gate progress
only as a raw dump of every current run. It cannot answer "what phase is this
task in?", and under a profile that records no gates (`default.yaml`) it
degrades to the useless string "No gate information yet".

This child builds the **pure, app-free derivation seam** that t1603_3 (in-flight
lane + chips) and t1603_4 (expanded gate surface) both consume. No widgets, no
Textual — so the entire vocabulary is unit-testable before any UI depends on it.

Depends on t1603_1 for `_plan_approved_marker`.

## The two axes (the model this seam serves)

The in-flight view has two independent axes. **Each task occupies exactly one
lane and carries exactly one phase** — `InFlightItem.group` is a scalar `str`
and nothing here changes that.

- **Lane = what happens next** (t1603_3's job): `planned` · `human` · `agent` ·
  `blocked`.
- **Phase = where the task sits in the workflow** (this child's job):
  `plan_approved` · `implementing` · `awaiting_review` · `needs_attended_agent`
  · `post_impl`.

"Independent" means neither axis determines the other. It does **not** mean a
task spans lanes.

## Key Files to Modify

- `.aitask-scripts/board/aitask_board.py` — the new derivation function(s),
  placed near `_gate_summary` / `_human_pending_gates` (~lines 1821-1871).
- Extract `TaskDetailScreen._resolve_plan_path` (~line 6480) to a module-level
  function so plan-file presence is not reimplemented.
- `tests/test_board_workflow_phase.py` — new, pure-unit.

## Reference Files for Patterns

- `.aitask-scripts/lib/gate_ledger.py:156-190` — the `TaskGateState` dataclass
  and, critically, its docstring, which states the rule this child must follow.
- `.aitask-scripts/lib/gate_ledger.py:1863` `_archive_status_from_state` — how
  `archive_pending` is computed.
- `.aitask-scripts/lib/gate_ledger.py:1871` `unmet_procedure_gates` — the
  existing `kind: procedure` + not-satisfied predicate.
- `.aitask-scripts/board/aitask_board.py:1873` `_inflight_item_for` — the
  existing classifier this seam will eventually feed.
- `tests/test_board_inflight_view.py` — bare-`TaskManager` construction idiom.

## Implementation Plan

Derive, from `(task, GateStateResult, plan-file presence, gate registry)`, a
`(phase, provenance, progress)` triple.

### 1. Phase, with a ledger

Evaluated in this order:

| Phase | Condition |
|---|---|
| `post_impl` | `archive_decision == "ALL_PASS"` or `resume_point == "POSTIMPL"` |
| `awaiting_review` | pending **human** gate, failed/errored gate, or `stale_signed` |
| `needs_attended_agent` | some gate in `archive_pending` whose registry entry has `kind: procedure` |
| `plan_approved` | `plan_approved` recorded `pass`, implementation not yet past it |
| `implementing` | otherwise |

`needs_attended_agent` exists because `docs_updated` is `type: machine` but
`kind: procedure`: the headless engine defers it and only an attended agent can
run it, yet `_human_pending_gates` (which filters on `type == "human"`) never
sees it, so such a task currently reads "Agent can continue". Drive the phase
off the registry's `kind` field, so any future procedure gate inherits it.

Reuse the predicate `gate_ledger.unmet_procedure_gates` already implements —
same `kind: procedure` + not-terminal-satisfied rule — but evaluate it over the
**in-memory** state rather than re-reading the file. Add a test asserting the
two agree, so they cannot drift.

### 2. Progress has exactly ONE authority: `archive_pending`

**Do not count statuses by hand.** `_archive_status_from_state` already computes
`archive_pending` as the active gates that are not satisfied, over the
`effective` view in which stale signatures have been demoted
(`gate_ledger.py:2098-2100`):

```
denominator = len(state.active_gates)          # enforced set; filtered excluded
numerator   = denominator - len(state.archive_pending)
current     = state.archive_pending[0]          # the gate being waited on
```

This is precisely the list the archival guard uses, so the surface **cannot
claim progress the workflow will reject**. It inherits every case a naive count
gets wrong, with no second implementation:

| Case | Handled because |
|---|---|
| profile-filtered gate | not in `active_gates`, so out of both terms |
| `skip` | `_gate_satisfied` treats it as terminal-satisfied |
| stale signature | demoted in `effective`, so it stays in `archive_pending` despite a raw ledger `pass` |
| `fail` / `error` | not satisfied, so still pending; additionally flagged |
| procedure gate | counted normally; drives `needs_attended_agent` when pending |

This is the rule `TaskGateState`'s own docstring states: *"TUI decision surfaces
(failed-gate classification, pending-human-gate detection, compact counts) must
key off the active set"* (`gate_ledger.py:162-165`). The same docstring warns
that `current` deliberately keeps the raw `pass` for a stale gate — which is
exactly why a hand-rolled count over `state.current` would over-report.

Budget the rendered form to fit a 34-column in-flight card (e.g.
`3/5 · docs_updated`); t1603_3 owns the actual rendering.

### 3. Degradation without a ledger — "unknown" is a state, not an inference

`has_ledger` false (the `default.yaml` case):

| Status | Plan file | Phase | Provenance |
|---|---|---|---|
| `Ready` + marker | any | `plan_approved` | `marker` |
| `Implementing` | present | `implementing` | `derived` |
| `Implementing` | **absent** | `implementing` | **`unknown`** |

The last row is load-bearing. An explicit `status: Implementing` must **never**
be re-described as "still planning". The status is the task's own assertion that
implementation began; a missing ledger *and* a missing plan file mean we cannot
tell how far it got — a different claim from "it has not started". Such a task
reports `implementing` with provenance `unknown` and **no progress fraction at
all**, not a fabricated `0/N`. This is legacy and partially-migrated work, and
mislabelling it would make the view actively misleading.

Plan-file presence must reuse the extracted `_resolve_plan_path` logic (it
already handles the `aiplans/p<parent>/` nesting for child tasks), not a
reimplementation.

## Verification

New `tests/test_board_workflow_phase.py`, pure-unit (no board boot):

- one case per row of **both** tables above;
- the exact combination `status: Implementing` + no ledger + no plan file — a
  **named regression case** asserting phase `implementing`, provenance
  `unknown`, and no fraction. This is the case the naive "still planning"
  inference gets wrong;
- `progress` equals `len(active_gates) - len(archive_pending)` for four
  fixtures: stale-signed, profile-filtered, `skip`, and failed;
- an invariant test that no gate reported "passed" by the seam appears in
  `archive_pending`;
- the `needs_attended_agent` predicate agrees with
  `gate_ledger.unmet_procedure_gates` on the same fixture;
- a **negative control** proving the ledger-free path is not silently taking the
  ledger path (mutate the ledger and confirm the ledger-free assertions change).

Drive these from real task fixtures written to disk, not hand-built
`TaskGateState` objects — a hand-built state can encode a combination the real
parser never produces, and the whole point is to match production semantics.

Run: `bash tests/run_all_python_tests.sh --test-dir tests` — read only the last
line.
