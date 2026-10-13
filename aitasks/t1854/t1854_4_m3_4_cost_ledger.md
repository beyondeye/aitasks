---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-13 19:18
updated_at: 2026-10-13 19:18
---

## Context

Child **M3.4 — Cost ledger** of t1854 (test map, module M3). Wave **C**. It
provides:

- the costs and evidence anchors the selector, the evidence join,
  `readiness` and the cadence read;
- the `costs/policy.yaml` file format.

**Providers:** M3.1 (`t1854_1`), M2.3 (`t1853_3`, landed — the dependency
closure and plugin `reads`) and **M2.5** (`t1853_5` — the helpers'
`testmap:reads` in the registry).

Authoritative specification: `aidocs/testing_engine/n014_explorer_006_proposal.md`
(M3 cut fixed in `6a3a81efc`):

- the Module Map row M3.4;
- the component *Cost ledger (M3.4)*, plus its consumer *Evidence join
  (M4.3)*;
- *Architecture → Where state lives* (the "runs, ledger" and "policy
  ledger" rows);
- *Assumptions → `assumption_passing_run_anchors_edges`*;
- *Tradeoffs → `tradeoff_batch_misreport_risk`*.

Parent plan: `aiplans/p1854_testmap_m3_runners_scheduling_and_cost.md`
(Deviations 2, 7, 12, 13 and 14).

**Coarse plan only.** `aiplans/p1854/p1854_4_m3_4_cost_ledger.md` records
what the proposal fixes. Its mandatory **Step 0 — Reality check** runs
before any code and is recorded in the plan. It inspects:

- M3.1's hook, the per-invocation record and the top-level/child marking;
- M2.3's closure API;
- M2.5's `reads` data;
- M4.3's plan.

**Stop if M2.5 has not landed.**

## Scope (from the proposal, after the M3 cut fix)

- **Statistics and ledger.**
  - Welford + P² p95 + last per `(id, host class)`; ids are opaque and may
    be variants.
  - `.aitask-testmap/ledger.jsonl`, written as a **subscriber of M3.1's
    post-run hook**: one row per result and one per invocation (with
    `cause`).
- **Anchor eligibility, decided at run time.** A pass is eligible only when
  all of these hold:
  - it has no cause;
  - HEAD did not move;
  - its modified-path set is disjoint from the test file, the whole
    test-side closure (M2.3), every `covers` source, **the `reads` globs of
    every file in the closure** (helpers' `testmap:reads` via M2.5 and
    scanner-plugin `reads`), and the runner's command and configuration.

  The set must be empty for an opaque or suite closure. `last_pass {sha,
  at, run_id}` advances only from eligible passes, and no path list is
  written to a committed file.
- **`costs --update`** folds into `aitestmap/costs/<hostclass>.yaml` and
  truncates, under a lock shared with appends.
- **Flake rate** vs `flake_threshold`.
- **Estimate and full-suite p95.**
  - The estimate over the canonical grouping sums Σ groups `overhead.p95` +
    Σ **top-level** ids p95. The kinds/waves come from the caller.
  - Accounting is **disjoint**: child rows never add to an estimate that
    includes their parent, and `overhead_ms` = elapsed − Σ top-level
    durations, clamped at 0.
  - The **full-suite p95** applies that estimate to the newest `full-` run.
- **Stores and helpers.**
  - `costs/predictions.yaml` is a store; M4.4's `score` writes it.
  - `costs --gate-timeout` → `GATE_TIMEOUT_SUGGESTED:<gate>|<s>` =
    `max(600, 3 × full-suite p95)` (the line is homed here).
  - Run-id prefixes `test-` / `gate-` / `full-` / `review-`; `review-`
    writes no cost rows.
  - The `costs/policy.yaml` format with its read/write helpers, including
    the `contract:` refusal. The writer logic is M8.5's.
- **Verb:** `costs`.

## Key files to modify

- `goengines/internal/testmap/cost/**` — new package (owned).
- `goengines/cmd/ait-testmap/verbs.go` — replace only the `costs` stub row.
- The subscription into M3.1's post-run hook — the named extension.

## Reference files for patterns

- `goengines/internal/platform/lock_unix.go` (`Lock`).
- `goengines/internal/testmap/contract.go` (`CheckContract`).
- `goengines/internal/testmap/deps` (the closure).
- M2.1's `registry/write.go` for sorted, write-only-on-change YAML.

## Provides / consumes

- **Provides:** cost rows, eligible `last_pass`, the estimate and full-suite
  p95, `predictions.yaml`, and the `policy.yaml` format. Consumers: M4.1,
  M4.3, M4.4, M6.5 and M8.5.
- **Consumes:** M3.1, M2.3 and M2.5.

## Implementation plan (coarse)

1. Step 0 — Reality check (in the plan file).
2. Welford / P²; the ledger subscriber; `costs --update` with the shared
   lock.
3. The eligibility rule and `last_pass`; flake rate.
4. The estimate with disjoint accounting; the full-suite p95;
   `--gate-timeout`.
5. `predictions.yaml` store; `policy.yaml` helpers; run-id prefixes; the
   `costs` verb row.

## Verification

- **Statistics:**
  - Welford matches a direct mean/variance;
  - P² p95 is within tolerance of the exact quantile.
- **Ledger:**
  - **command-level:** a real `run` appends one row per result and one per
    invocation;
  - `--update` folds into sorted output that is byte-identical when nothing
    is new, then truncates;
  - **a concurrent append during `--update` loses no row**.
- **Eligibility, red-proved.** A pass is *not* eligible when:
  - the test is weakened but uncommitted;
  - a helper is dirty;
  - a `covers` source is dirty;
  - **only a data file matched by a helper's `testmap:reads` glob is
    dirty**, or one matched by a plugin `reads` glob;
  - the invocation has a cause;
  - HEAD moved;
  - an opaque or suite unit has any modified path.

  Unrelated dirty paths leave the pass eligible.
- **Disjoint accounting:** a 100 s suite parent with 40 s and 60 s children
  in a 105 s invocation contributes 105 s, not 205 s. The child statistics
  and evidence are still recorded.
- **Smaller checks:**
  - flake rate;
  - `predictions.yaml` keeps the last 200 entries;
  - `GATE_TIMEOUT_SUGGESTED:`;
  - the run-id prefixes;
  - a `policy.yaml` with a newer `contract:` gets `CONTRACT_MISMATCH`.
- `ait engine test` is green.

## Automation-first (user directive, 2026-10-11)

Human review belonged to an older design. No path shipped here may make a
human action a precondition. `--gate-timeout` is a computed suggestion, never
an approval. A human-only step met in the proposal is reported to its owning
parent with a note, never encoded here.
