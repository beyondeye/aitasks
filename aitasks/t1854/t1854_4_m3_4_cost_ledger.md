---
priority: medium
effort: medium
depends: [t1854_1, t1853_5]
issue_type: feature
status: Implementing
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
created_at: 2026-10-13 19:18
updated_at: 2026-10-19 17:04
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1854_1** id=2026-10-14T14:40:27Z.350a6da90b33121ac07c4fd2 from=t1854_1 from_verified=yes at=2026-10-14T14:40:27Z base=02e4a1badd5a7a8af9d2e250e7108cb8e1cd993e base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1854_1 (M3.1), as landed in 3d1a2b628. Verify against goengines/README.md → Interfaces ("invocation outcome / record", "run seams").
> | 
> | - Subscribe with runner.RegisterPostRunHook(name, func(ctx, *RunReport) error). Subscribers run once each, in registration order, after every record.json is written. A failing subscriber does not stop the next, but makes `run` exit 3 (RUN_HOOK_ERROR).
> | - RunReport carries RunID, Root, Dir (repo-relative), Invocations []Record and Results []Result.
> | - Record (also on disk at .aitask-testmap/runs/<run-id>/inv-<NNN>/record.json): contract, run_id, invocation, group, runner, units_expected/reported/started, exit_code, elapsed_ms, timeouts, deadline_s, killed, refused, timed_out, protocol_errors[], overhead_ms, cause, cause_detail, head_start, head_end, modified[].
> |   - cause precedence: mechanism > reconciliation > timeout.
> |   - An invocation's results may anchor only if cause == "".
> |   - modified = start ∪ end of gitx.ModifiedPaths, minus .aitask-testmap/.
> |   - head_start is "" on an unborn HEAD.
> |   - overhead_ms already follows Dev 13 (elapsed − Σ top-level durations, ≥ 0).
> | - Result: Child=true plus Parent for suite child rows, otherwise top-level. Engine-synthesized statuses: timeout, not_started, batch_timeout, missing, refused, and error (a protocol error).
> | - Run ids: --run-id, else $AIT_GATE_RUN_ID, else run-<UTC>-<pid>. The test-/gate-/full-/review- prefixes are still yours to define.

> **✉ note:t1853_5** id=2026-10-18T15:59:24Z.fd255190743331b33799423b from=t1853_5 from_verified=yes at=2026-10-18T15:59:24Z base=6f6d1ed799167c432f1ae5ed90abeb346b712f4f base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1853_5 (M2.5) as landed in 6f6d1ed79; re-verify in your Reality check.
> | 
> | Helpers' `testmap:reads` globs reach the registry as `registry.ScopedOf(reg).Reads` (`[]ReadsRow{Helper, Globs, Line, File}`), persisted in the `reads:` table of `aitestmap/registry/_scoped.yaml`.
> | 
> | The proposal's `reads_from` row field was NOT persisted; the proposal component was revised accordingly. Which helpers a unit inherits from depends on its test-side closure, so it is computed at join time.
> | 
> | For anchor eligibility you will need the same rule: the reads globs of every helper in the unit's closure. `Scoped.Join` shows the matching rule, and you can reuse `Reads` directly.
> | 
> | Scoped rows are digest-exempt: `ScopedOf(reg).DigestExempt(id)`.

> **✉ note:t1859** id=2026-10-19T12:47:07Z.d8fed4608e79b93601cafd45 from=t1859 at=2026-10-19T12:47:07Z base=bf32b336c0b0673eccba125bf097df173405e8d7 base_branch=main dirty=yes host=omg16
>
> | Advisory, from the t1859 (M8) coarse pass. Proposal fix: commit bf32b336c (Dev 7).
> | 
> | A new engine verb `policy` (M8.4 adds `decide`; M8.5, t1859_5, adds the auto arm) is the only writer of aitestmap/costs/policy.yaml under `ait test --gate`. It calls your policy.yaml read/write helpers, including the `contract` field and the CONTRACT_MISMATCH refusal. The writer logic stays M8.5's.
> | 
> | M8.5 also uses your disjoint full-suite p95 for the selection_ratio_above trigger. A tree claim; verify it when you implement.

> **👁 note:read** id=2026-10-19T14:04:17Z.453ed1c106defb2589ac0f81 by=t1854_4 at=2026-10-19T14:04:17Z mode=explicit ids=2026-10-14T14:40:27Z.350a6da90b33121ac07c4fd2,2026-10-18T15:59:24Z.fd255190743331b33799423b,2026-10-19T12:47:07Z.d8fed4608e79b93601cafd45
