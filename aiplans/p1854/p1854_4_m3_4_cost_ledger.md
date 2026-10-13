---
Task: t1854_4_m3_4_cost_ledger.md
Parent Task: aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md
Sibling Tasks: aitasks/t1854/t1854_1_*.md, aitasks/t1854/t1854_2_*.md, aitasks/t1854/t1854_3_*.md
Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1854_4 — M3.4 Cost ledger

## Context

Parent goal: M3 — Runners, scheduling and cost. This is **M3.4 Cost
ledger**, wave **C**: the costs and evidence anchors read by the selector,
the evidence join, `readiness` and the cadence, plus the `costs/policy.yaml`
file format. Providers:

- M3.1 (`t1854_1`);
- M2.3 (`t1853_3`, landed): the closure and plugin `reads`;
- **M2.5 (`t1853_5`)**: the helpers' `testmap:reads` in the registry.

This coarse plan records what the proposal fixes for M3.4. It does not design internals against providers that do not exist yet; the Reality check below does that when this child is picked.

**Automation-first (user directive, 2026-10-11).** Human review belonged to
an older design. No verb shipped here may make a human action a
precondition of any path. `costs --gate-timeout` is a computed suggestion,
never an approval. A human-only step met in the proposal is reported to its
owning parent with a note, never encoded here.

## Proposal reading list

In `aidocs/testing_engine/n014_explorer_006_proposal.md` (M3 cut fixed in
`6a3a81efc`):

- the Module Map row M3.4;
- *Cost ledger (M3.4)*;
- the consumer *Evidence join (M4.3)*;
- *Runner contract and repository*: the per-invocation record, the post-run
  hook, the grouping function, top-level / child rows;
- *Architecture → Where state lives*: the "runs, ledger, predictions" and
  "the engine's policy ledger" rows; *The registry directory*
  (`policy.yaml`);
- *Assumptions → `assumption_passing_run_anchors_edges`*;
- *Tradeoffs → `tradeoff_batch_misreport_risk`*;
- *Open questions* 13 (cadence defaults, consumed by M8.5);
- *Invariants every module honours*.

Also read the parent plan
`aiplans/p1854_testmap_m3_runners_scheduling_and_cost.md` (Deviations 2, 7,
12, 13, 14) and `goengines/README.md`.

## Owned files / provides / consumes

- **Owns:**
  - `goengines/internal/testmap/cost/**`;
  - the `costs` row in `verbs.go`;
  - the ledger subscription to M3.1's post-run hook (named extension of
    M3.1).
- **Provides:**
  - cost rows, eligible `last_pass`, the estimate (disjoint, top-level ids)
    and the full-suite p95 → M4.1, M4.3, M4.4, M8.5;
  - `predictions.yaml` (a store; M4.4 writes it);
  - the `policy.yaml` format and helpers (M8.5 is the writer);
  - `GATE_TIMEOUT_SUGGESTED:` → M6.5.
- **Consumes:**
  - M3.1: the hook, the per-invocation record, the grouping function and
    the row marking;
  - M2.3: the closure and plugin `reads`;
  - M2.5: `testmap:reads`.

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded in this plan file)

Execute and record here, before writing any code:

1. Re-read the proposal's Module Map row for M3.4, its component subsection,
   and the row of every interface it consumes (*Cross-module interfaces*).
2. Inspect the **actual current state** of every provider on the merge
   target: verbs, line protocols, files, hooks and tests. Name the task and
   commit that landed each one. The proposal and this coarse plan are claims
   to verify, never facts. Specifically:
   - M3.1 as landed (`t1854_1`): the post-run hook payload, the
     per-invocation record (`cause`, HEAD start/end, modified paths), and
     the top-level / child marking. If M3.1 has not landed, **stop**.
   - M2.3 (`t1853_3`, `2c04a9639`): the test-side closure API and
     `FileFacts.Reads` (plugin globs).
   - M2.5 as landed (`t1853_5`): how helpers' `testmap:reads` globs reach
     the registry. If M2.5 has not landed, **stop**: the eligibility rule
     must not ship without it.
   - M4.3's plan, if t1855 has been decomposed: whether its join reads the
     `anchor` field and the stamp-date guard. Send a note if the shape
     differs.
   - The parent plan's *Repository reality anchors* (verified 2026-10-13 at
     `a2395c309`): re-verify each one this child relies on.
3. Tabulate every difference: *proposal says* / *coarse plan says* /
   *repository has*.
4. Decide, per difference: adapt this child to reality; revise this coarse
   plan; or revise the proposal (cut errors and interface changes go there,
   per the parent body's protocol §1). Record the decision and its reason.
   Also decide:
   - the estimate's fallback for an id with no cost row;
   - the `costs` line names, homed in *Cost ledger*.
5. Send a note (`/aitask-note`) to every downstream child whose assumptions a
   difference or decision breaks (M4.1, M4.3, M4.4, M6.5, M8.5), hedging what
   the tree cannot prove.
6. Re-confirm that every file this child will touch is owned by M3.4 or is
   the owner's named extension (the "one owning submodule" rule).

## Implementation steps (coarse)

1. Step 0 — Reality check (above).
2. Welford + P² p95 + last per `(id, host class)`. Subscribe the ledger to
   the post-run hook, writing one row per result and one per invocation
   (with `cause`). Add `costs --update`, which folds into
   `aitestmap/costs/<hostclass>.yaml` (sorted, written only on change) and
   truncates, under a lock that appends also take.
3. Anchor eligibility at run time:
   - no cause, and HEAD unmoved;
   - the modified-path set disjoint from all of:
     - the test file and its test-side closure;
     - the `covers` sources;
     - the closure's `reads` globs (M2.5 `testmap:reads` + plugin `reads`);
     - the runner configuration;
   - the set must be empty when the closure is opaque.

   `last_pass` advances only from eligible passes. Never write a path list
   to a committed file. Compute the flake rate against `flake_threshold`.
4. The estimate over the canonical grouping, with disjoint accounting:
   - top-level ids only;
   - `overhead_ms` = elapsed − Σ top-level durations, clamped at 0.

   The full-suite p95 is this estimate over the newest `full-` run.
   `costs --gate-timeout` → `GATE_TIMEOUT_SUGGESTED:`.
5. The `predictions.yaml` store (last 200); the run-id prefixes (`review-`
   writes no cost rows); the `policy.yaml` read/write helpers with the
   `contract:` refusal; replace the `costs` stub row.

## Verification

- Welford matches a direct mean/variance. P² p95 is within tolerance of the
  exact quantile on fixed distributions.
- **Command-level:** a real `run` appends one ledger row per result and one
  per invocation, through the hook.
- `costs --update` folds and truncates. Its output is sorted and
  byte-identical on a re-run with nothing new.
- **A concurrent append during `--update` loses no row** (two processes, one
  lock).
- **Eligibility, red-proved.** A pass is not eligible in any of these
  cases:
  - after an uncommitted weakening of the test;
  - with a dirty helper in its closure;
  - with a dirty `covers` source;
  - with **only a dirty data file matched by a helper's `testmap:reads`
    glob**, or by a plugin `reads` glob;
  - when the invocation has a cause;
  - when HEAD moved;
  - for an opaque or suite unit with any modified path.

  A pass with only unrelated dirty paths is eligible. No path list appears
  in `costs/<hostclass>.yaml`.
- Flake rate against `flake_threshold`.
- Estimate = Σ groups `overhead.p95` + Σ top-level ids p95, grouped by the
  caller's wave and kind inputs.
- **Disjoint accounting.** In a full run of one invocation, a suite parent
  of 100 s with child rows of 40 s and 60 s, and 105 s elapsed, contributes
  100 + 5 = 105 s, never 205 s. The child statistics (40 s, 60 s) and child
  evidence are still recorded. The full-suite p95 and
  `GATE_TIMEOUT_SUGGESTED:<gate>|<s>` = `max(600, 3 × full-suite p95)` use
  that figure.
- `predictions.yaml` keeps the last 200.
- Run-id prefixes `test-` / `gate-` / `full-` / `review-` are handled, and
  `review-` writes no cost rows.
- `policy.yaml` helpers work; a newer `contract:` gives `CONTRACT_MISMATCH`.
- `ait engine test` is green; the Invariants 4–5 tripwire passes.
- No path shipped here requires a human action (automation-first).

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9 (archival; current
branch, no merge).
