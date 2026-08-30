---
Task: t1603_2_workflow_phase_model_and_degradation.md
Parent Task: aitasks/t1603_surface_deferred_plan_marker_on_the_board.md
Sibling Tasks: aitasks/t1603/t1603_1_*.md, aitasks/t1603/t1603_3_*.md, aitasks/t1603/t1603_4_*.md, aitasks/t1603/t1603_5_*.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1603_2 — Workflow-phase model + honest degradation

## Context

A **pure, app-free derivation seam** — no widgets, no Textual — consumed by
t1603_3 (lane + chips) and t1603_4 (expanded gate section). Building it first
makes the whole vocabulary unit-testable before any UI depends on it.

Depends on t1603_1 for `_plan_approved_marker`.

## The model it serves

Two independent axes; **each task has exactly one lane and exactly one phase**.
This child owns only the phase (and progress/provenance); the lane is t1603_3's.

- Lane: `planned` · `human` · `agent` · `blocked`
- Phase: `plan_approved` · `implementing` · `awaiting_review` ·
  `needs_attended_agent` · `post_impl`

## Implementation Steps

### 1. Extract plan-file presence

`TaskDetailScreen._resolve_plan_path` (`aitask_board.py:6480`) already handles
the `aiplans/p<parent>/` nesting for child tasks and returns a path only when it
exists. Extract it to a module-level function and have the screen call that.
Do not reimplement the nesting rule.

### 2. Phase, with a ledger

Evaluate in this order:

| Phase | Condition |
|---|---|
| `post_impl` | `archive_decision == "ALL_PASS"` or `resume_point == "POSTIMPL"` |
| `awaiting_review` | pending **human** gate, failed/errored gate, or `stale_signed` |
| `needs_attended_agent` | a gate in `archive_pending` whose registry entry has `kind: procedure` |
| `plan_approved` | `plan_approved` recorded `pass`, not yet past it |
| `implementing` | otherwise |

`needs_attended_agent` exists because `docs_updated` is `type: machine` with
`kind: procedure`: the headless engine defers it and only an attended agent can
run it, yet `_human_pending_gates` filters on `type == "human"` and never sees
it — so such a task currently reads "Agent can continue". Key the phase off the
registry's `kind`, so any future procedure gate inherits it.

The predicate is the one `gate_ledger.unmet_procedure_gates`
(`lib/gate_ledger.py:1871`) already implements. Evaluate it over the in-memory
state rather than re-reading the file, and **assert the two agree in a test** so
they cannot drift.

### 3. Progress — exactly ONE authority: `archive_pending`

Do **not** count statuses by hand. `_archive_status_from_state`
(`gate_ledger.py:1863`) computes `archive_pending` as the active gates that are
not satisfied, over the `effective` view in which stale signatures are demoted
(`gate_ledger.py:2098-2100`):

```
denominator = len(state.active_gates)      # enforced set; filtered excluded
numerator   = denominator - len(state.archive_pending)
current     = state.archive_pending[0]     # the gate being waited on
```

This is the same list the archival guard uses, so the surface **cannot claim
progress the workflow will reject**. It inherits, with no second implementation:

| Case | Handled because |
|---|---|
| profile-filtered gate | not in `active_gates` — out of both terms |
| `skip` | `_gate_satisfied` treats it as terminal-satisfied |
| stale signature | demoted in `effective`, so still pending despite a raw ledger `pass` |
| `fail` / `error` | not satisfied — still pending, plus a flag |
| procedure gate | counted normally; drives `needs_attended_agent` when pending |

`TaskGateState`'s docstring states the rule directly: *"TUI decision surfaces
(failed-gate classification, pending-human-gate detection, compact counts) must
key off the active set"* (`gate_ledger.py:162-165`). The same docstring warns
that `current` keeps the raw `pass` for a stale gate — precisely why a
hand-rolled count over `state.current` would over-report.

Budget the rendered form for a 34-column card (e.g. `3/5 · docs_updated`);
t1603_3 owns the rendering.

### 4. Degradation without a ledger — "unknown" is a state, not an inference

| Status | Plan file | Phase | Provenance |
|---|---|---|---|
| `Ready` + marker | any | `plan_approved` | `marker` |
| `Implementing` | present | `implementing` | `derived` |
| `Implementing` | **absent** | `implementing` | **`unknown`** |

An explicit `status: Implementing` must **never** be re-described as "still
planning". The status is the task's own assertion that implementation began; a
missing ledger *and* plan file mean we cannot tell how far it got — a different
claim from "it has not started". That case reports `implementing` with
provenance `unknown` and **no progress fraction**, not a fabricated `0/N`. This
is legacy and partially-migrated work; mislabelling it makes the view actively
misleading about the population it exists to serve.

## Verification

`tests/test_board_workflow_phase.py`, pure-unit, driven from **real task
fixtures on disk** rather than hand-built `TaskGateState` objects (a hand-built
state can encode a combination the parser never produces):

- one case per row of both tables;
- **named regression case** — `status: Implementing` + no ledger + no plan file
  ⇒ phase `implementing`, provenance `unknown`, no fraction;
- `progress == len(active_gates) - len(archive_pending)` for four fixtures:
  stale-signed, profile-filtered, `skip`, failed;
- invariant: no gate reported "passed" appears in `archive_pending`;
- the `needs_attended_agent` predicate agrees with
  `gate_ledger.unmet_procedure_gates` on the same fixture;
- **negative control**: mutate the ledger and confirm the ledger-free assertions
  change, proving the ledger-free path is not silently taking the ledger path.

`bash tests/run_all_python_tests.sh --test-dir tests` — read only the last line.

## Risk

### Code-health risk: low
- A new pure function plus one extraction; no widget or lifecycle changes. The
  single-authority progress rule avoids introducing a competing derivation.
  · severity: low · → mitigation: none (accepted residual)

### Goal-achievement risk: medium
- The phase vocabulary is new and its usefulness is only proven once t1603_3
  renders it; a vocabulary that turns out to be the wrong cut would ripple into
  two dependent children. · severity: medium · → mitigation: none (accepted
  residual — the seam is pure and cheap to reshape before its consumers land)

## Step 9 (Post-Implementation)

Standard closure: commit, merge per the plan header, archive the task and plan.
