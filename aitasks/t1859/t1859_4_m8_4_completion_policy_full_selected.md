---
priority: medium
effort: high
depends: [t1859_1, t1854_2]
issue_type: feature
status: Postponed
labels: [testing, testmap, gates]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-19 15:43
updated_at: 2026-10-19 15:44
---

Child of t1859 (test-map **M8 — Completion policy and gates**), submodule
**M8.4 — Completion policy `full` / `selected`**, wave **E**. It makes the one
completion gate (`tests_pass` running `./ait test --gate`) mean a committed
policy:
- `full` runs the whole registry;
- `selected` runs the task's selection, after a readiness re-check that demotes
  loudly to full.

Authoritative spec: `aidocs/testing_engine/n014_explorer_006_proposal.md` —
the `#### M8` row, component *Completion policy*, *The registry directory*
(the `completion:` block), *Workflow Seam → Completion policy*, *Data Flow →
A completion run under policy*, *Test entrypoint* (the `POLICY` hook), and
Open question 3. The parent plan
`aiplans/p1859_testmap_m8_completion_policy_and_gates.md` lists the cut fixes
in *Deviations*: Dev 2 (the `result=` carrier) and Dev 7 (verb `policy`).

This coarse plan records what the proposal fixes for M8.4. It does not design
internals against providers that do not exist yet; the Reality check does that
when this child is picked.

**Automation-first:** `selected`'s human `approved_by` (written by M6.5's
`--policy selected`) is an optional attended alternative. `auto` (M8.5) is the
automated route. Under `selected`, a missing or unmet approval demotes to
`full`. M8.4 reads the field and never requires it.

## Dependency hold

`Postponed` only because providers have no child ids yet:

- **M4.4** (`readiness`, the `internal/testmap/feedback` package), in t1855;
- **M5.1** (`aitask_test.sh` and its `POLICY` hook,
  `tests/test_ait_test_entrypoint.sh`), in t1856.

Each provider parent's coarse pass adds the ids and flips this task to `Ready`
once nothing is left unresolved. In `depends:`: M8.1 `t1859_1`, M3.2
`t1854_2`. Landed: M3.1 `t1854_1` (defines `fallback_command:`).

## Key Files to Modify

- `.aitask-scripts/aitask_test.sh` (M5.1's): the `full` / `selected` arms of
  the `POLICY` hook:
  - the readiness re-check, `POLICY_DEMOTED:selected->full|<criterion>`;
  - `on_empty_selection` (skip → exit 2 | full);
  - `deferred: run|fail`;
  - `engine_absent: error|fallback_command`: the front reads `runners.yaml`'s
    full-suite `fallback_command` **without the engine** and prints
    `MODE:fallback`;
  - writes `result="MODE:<full|selected>|<n units>|policy:<mode>"` through
    M8.1's `AIT_GATE_RESULT_FILE`.
- `goengines/internal/testmap/feedback/policy/` (a new package in M4.4's
  `feedback`): the decision logic, shared by `readiness`'s `POLICY:` line and
  the new verb.
- `goengines/cmd/ait-testmap/verbs.go`: verb **`policy`** (`decide`, read-only
  for full/selected) as a named extension of M1.2's verb table. The exact
  subcommand shape is fixed in the Reality check.
- `readiness` (M4.4's): the additive `POLICY:<mode>|<what --gate would run
  now>` line.
- The data schema the `--policy selected` re-entry writes
  (`completion.mode: selected`, `run_gate_admission.approved_by {who, at,
  statement}`); M6.5 writes it.
- `tests/test_ait_test_entrypoint.sh` (M5.1's): the cases.

## Reference Files for Patterns

- `goengines/internal/testmap/registry/config.go` (`Completion`,
  `RunGateAdmission`, `FullRunEvery` already parsed).
- `.aitask-scripts/lib/yaml_utils.sh` (bash YAML reads).

## Implementation Plan

0. **Reality check (MANDATORY, before any code; record the outcome).** Stop if
   M4.4 or M5.1 has not landed.
1. Write the `policy` package and the verb.
2. Add the readiness line.
3. Add the front's arms and the fallback.
4. Write the `result=` line.
5. Write the tests.

## Verification Steps

- `full`; `selected` with every criterion met; `selected` demoted per
  criterion.
- `engine_absent: error` (3) and `fallback_command`.
- `on_empty_selection` skip/full; `deferred: run|fail`.
- The `result=` shape in the gate-run block; readiness `POLICY:`.
- `ait engine test` green.
- No path requires a human action.
