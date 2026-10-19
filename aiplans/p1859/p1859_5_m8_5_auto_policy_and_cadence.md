---
Task: t1859_5_m8_5_auto_policy_and_cadence.md
Parent Task: aitasks/t1859_testmap_m8_completion_policy_and_gates.md
Sibling Tasks: aitasks/t1859/t1859_1_*.md, aitasks/t1859/t1859_2_*.md, aitasks/t1859/t1859_3_*.md, aitasks/t1859/t1859_4_*.md, aitasks/t1859/t1859_6_*.md
Archived Sibling Plans: aiplans/archived/p1859/p1859_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1859_5 — M8.5 Auto policy and cadence (coarse)

## Context

Parent t1859 (M8); Module Map row **M8.5**; wave **G**. This child is the
self-approving `auto` policy, the loop closing without a person (Overview,
mechanism 4):

- On the first `ADMISSIBLE` completion run it flips to the selection,
  recording `approved_by: engine:readiness@<run>` in the engine's own ledger
  `aitestmap/costs/policy.yaml`, never in `config.yaml`.
- A cadence (`full_run_every {tasks, selection_ratio_above, days}`) forces
  full runs, so scoring never stops.
- Any unmet criterion demotes loudly and clears `approved_by`.

This coarse plan records what the proposal fixes for M8.5. It does not design internals against providers that do not exist yet; the Reality check below
does that when this child is picked.

**Automation-first:** this child *is* the automated approval. Every write
carries its provenance (Invariant 7).

**Dependency hold:** `Postponed` until M4.4 (t1855) and M5.2 (t1856) have child
ids in `depends:`.

## Proposal reading list

- The `#### M8` row (M8.5).
- Component *Auto completion policy and cadence*.
- *Cost ledger* (the `policy.yaml` format and helpers; the disjoint
  full-suite p95).
- *Feedback tools* (`CADENCE:`, `cadence_declared`, `approved_by`, the window
  score).
- *Agent brief* (`next full in`, `FULL_GATE:`).
- *Data Flow → The policy flip*.
- *Where state lives* (the policy ledger row).
- Invariants 1, 5, 7 and 9; Open question 13.
- Parent plan Deviations 2 and 7; the t1854 note (Dev 13 p95, Dev 14
  `contract`).

## Owned files / provides / consumes

- **Owns:**
  - `goengines/internal/testmap/feedback/cadence.go`;
  - the `auto` arm and the writes of verb `policy` (an extension of M8.4's
    verb);
  - the `auto` arm and the path-scoped policy commit in `aitask_test.sh` (a
    named extension of M5.1);
  - the additive lines in `readiness` (M4.4) and `brief` (M5.2);
  - the window-score trigger in `score` (M4.4);
  - the `auto` matrix in `tests/test_ait_test_entrypoint.sh`.
- **Provides:** the self-approving policy behind the scheduled full run.
  Consumers: M9.4 (docs) and every completion run.
- **Consumes:**
  - M8.4 `t1859_4`;
  - M3.4 `t1854_4` (`policy.yaml` helpers, the per-group estimate, the
    full-suite p95);
  - held: M4.4 (`readiness`, `score`) and M5.2 (`brief`).

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded in this plan file)

1. Re-read the row, the component, and the interface rows for cost and
   readiness.
2. Inspect the actual state, naming the task and commit for each:
   - M3.4's helpers and p95;
   - M4.4's `score` / `readiness`;
   - M5.2's `brief`;
   - M8.4's verb and package as landed.
3. Tabulate *proposal* / *coarse plan* / *repository*.
4. Decide each difference and record it. Also decide the concurrency of the
   committed counter across sessions and worktrees: a lock, read-modify-write,
   and a merge-conflict rule that fails toward running more (e.g. take the
   max of `selected_since_full` and the oldest `last_full_run`). **Stop if
   M3.4, M4.4 or M5.2 has not landed.**
5. Send notes to t1860 (M9.4 docs) and t1861 (cadence defaults per target,
   Open question 13), hedged.
6. Re-confirm ownership.

## Implementation steps (coarse)

1. Write `cadence.go` with the three triggers:
   - `selected_since_full ≥ tasks`;
   - the estimate ≥ `selection_ratio_above` × the newest full p95 on this host
     class;
   - `now − last_full_run.at ≥ days`.

   Budget: < 50 ms.
2. Extend the `policy` verb:
   - decision order: `NOT_YET` → full (`POLICY:auto|full|not_yet:<c>`);
     `ADMISSIBLE` with no `approved_by` → `POLICY_FLIPPED:…` and the write; a
     cadence trigger due → full (`cadence:<trigger>`); otherwise
     `selected|next_full_in:<n>`;
   - the write points: pre-run (flip / demotion) and post-run (full-run reset
     / selected increment), each printing `POLICY_WRITE:`.
3. Add the front's `auto` arm:
   - a cadence full run ignores `on_empty_selection`, honours `subsumed_by`
     and `deferred: run`;
   - commit `ait: testmap policy <flip|full-run> (t<id>)` with plain git,
     path-scoped;
   - `result=` through the carrier.
4. Add the readiness lines (`cadence_declared`, `CADENCE:`,
   `approved_by|met|engine`), the window-score trigger, and the brief fields.
5. Write the tests.

## Verification / acceptance

- The `auto` matrix:
  - `NOT_YET` → full;
  - first `ADMISSIBLE` → flip, write and a path-scoped commit;
  - each of the three cadence triggers → full, with a counter reset;
  - the steady selection with the counter incremented;
  - a demotion clears `approved_by`;
  - a cadence full run ignores `on_empty_selection`.
- Engine tests: the window score attributes a miss to the right task; a
  `CONTRACT_MISMATCH` on a newer `policy.yaml`.
- The cadence budget holds.
- `ait engine test` is green.

## Step 9 reference

The shared post-implementation flow: current branch, no merge.
