---
Task: t1859_4_m8_4_completion_policy_full_selected.md
Parent Task: aitasks/t1859_testmap_m8_completion_policy_and_gates.md
Sibling Tasks: aitasks/t1859/t1859_1_*.md, aitasks/t1859/t1859_2_*.md, aitasks/t1859/t1859_3_*.md, aitasks/t1859/t1859_5_*.md, aitasks/t1859/t1859_6_*.md
Archived Sibling Plans: aiplans/archived/p1859/p1859_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1859_4 — M8.4 Completion policy `full` / `selected` (coarse)

## Context

Parent t1859 (M8); Module Map row **M8.4**; wave **E**. This child makes the
one completion gate (`tests_pass` running `./ait test --gate`) mean a
committed policy:
- `full` runs the whole registry (honouring `subsumed_by`);
- `selected` runs the task's selection after a readiness re-check, and demotes
  loudly to full when a criterion is unmet.

This coarse plan records what the proposal fixes for M8.4. It does not design internals against providers that do not exist yet; the Reality check below
does that when this child is picked.

**Automation-first:** `selected`'s human `approved_by` is an optional attended
alternative, and `auto` (M8.5) is the automated route. Under `selected`, a
missing or unmet approval demotes to full. This child reads the field and
never requires it.

**Dependency hold:** `Postponed` until M4.4 (t1855) and M5.1 (t1856) have
child ids in `depends:`.

## Proposal reading list

- The `#### M8` row (M8.4).
- Component *Completion policy*.
- *The registry directory* (the `completion:` block and its defaults).
- *Workflow Seam → Completion policy*.
- *Data Flow → A completion run under policy*.
- Component *Test entrypoint* (the `POLICY` hook).
- *Run Surface → Resolution, Output and exit contract*.
- Open question 3 (`on_empty_selection`) and Invariant 9.
- Parent plan Deviations 2 and 7.
- The t1854 note: `fallback_command` is read by the bash front without the
  engine.

## Owned files / provides / consumes

- **Owns:**
  - the `full` / `selected` arms of the `POLICY` hook in
    `.aitask-scripts/aitask_test.sh` (a named extension of M5.1);
  - `goengines/internal/testmap/feedback/policy/` (in M4.4's package);
  - verb `policy` (`decide`), a named extension of M1.2's verb table;
  - readiness's `POLICY:` line (additive to M4.4);
  - the data schema the `--policy selected` re-entry writes;
  - cases in `tests/test_ait_test_entrypoint.sh` (M5.1's file).
- **Provides:** the `completion:` block semantics, the `POLICY:` lines, and the
  verb. Consumers: M5.2 (brief), M6.1 (`detect --write`), M6.5
  (`--policy selected`), M8.5, M9.1.
- **Consumes:**
  - M8.1 `t1859_1` (the result carrier, exit rows);
  - M3.2 `t1854_2` (the full-suite runner);
  - M3.1 `t1854_1`, landed (`fallback_command:`);
  - held: M4.4 (`readiness`) and M5.1 (`aitask_test.sh`, its hook and test
    file);
  - `registry/config.go` (`Completion`, `RunGateAdmission` already parsed).

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded in this plan file)

1. Re-read the row, the component, and the interface rows "`ait test` modes …"
   and "the `completion:` block and `POLICY:` lines".
2. Inspect the actual state, naming the task and commit for each:
   - M5.1's `POLICY` hook and how it calls the engine;
   - M4.4's readiness lines and criteria;
   - the `feedback` package layout;
   - the `completion:` parse;
   - `runners.yaml`'s schema for `fallback_command`, and how bash can read it;
   - the carrier from `t1859_1`.
3. Tabulate *proposal* / *coarse plan* / *repository*.
4. Decide each difference and record it. Fix the `policy` verb's subcommand
   shape here (`decide` for full/selected; M8.5 adds the writes). **Stop if
   M4.4 or M5.1 has not landed.**
5. Send notes to `t1859_5`, t1857 (M6.1/M6.5) and t1860 (M9.1) where an
   assumption breaks, hedged.
6. Re-confirm ownership and the named-extension status of every edit in M4.4
   and M5.1 files.

## Implementation steps (coarse)

1. Write the `policy` package with the `full` / `selected` decision: the
   readiness re-check and `POLICY_DEMOTED:selected->full|<criterion>`. Expose
   it through the verb `policy decide` and through readiness's `POLICY:` line,
   so both use the same code.
2. Add the front's arms:
   - `deferred: run|fail`;
   - `on_empty_selection: skip|full` (skip → exit 2);
   - `engine_absent: error|fallback_command` (read `runners.yaml` without the
     engine; `MODE:fallback`).
3. Write `result="MODE:<full|selected>|<n units>|policy:<mode>"` through
   `AIT_GATE_RESULT_FILE`.
4. Document the `--policy selected` data schema (`completion.mode: selected`,
   `run_gate_admission.approved_by {who, at, statement}`).
5. Write the tests.

## Verification / acceptance

In `tests/test_ait_test_entrypoint.sh`, with the fake engine:

- `full`;
- `selected` with every criterion met;
- `selected` demoted, once per criterion;
- `engine_absent: error` (exit 3) and `fallback_command`;
- `on_empty_selection` skip and full;
- `deferred: run` and `fail`;
- the `result=` shape in the gate-run block;
- readiness `POLICY:`.

Also: `ait engine test` is green, and no path requires a human action.

## Step 9 reference

The shared post-implementation flow: current branch, no merge.
