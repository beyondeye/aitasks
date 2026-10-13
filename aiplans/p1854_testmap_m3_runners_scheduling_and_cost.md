---
Task: t1854_testmap_m3_runners_scheduling_and_cost.md
Base branch: main
Output branch: main
---

# Plan: t1854 — Testmap M3: Runners, scheduling and cost (coarse planning pass)

## Context

The test map feature (`aidocs/testing_engine/n014_explorer_006_proposal.md`) is
cut into ten modules, one parent task each (t1852–t1861). This task is **M3 —
Runners, scheduling and cost**: everything that executes a test and records
what it cost.

The task body binds the protocol. This session performs only the **coarse
planning pass**: one child per submodule row (M3.1–M3.4), and a coarse plan
per child recording scope, owned files, provided and consumed interfaces,
acceptance list, wave and the **mandatory Reality-check step**. It then
**stops** at the child checkpoint, so no engine code is written. The task
body prescribes both "Yes, create child tasks" and "Stop here", so they are
treated as decided.

**Sequencing.** M3's wave-earliest child (M3.1, wave B) consumes M1.2, M2.1
and M2.2. All three are landed and archived:

| provider | task | commit |
|---|---|---|
| M1.2 | t1852_2 | `33012bff7` |
| M2.1 | t1853_1 | `0d04347ab` |
| M2.2 | t1853_2 | `f096db065` |

The pass is therefore admissible under the submodule-granular rule (memory
`feedback_testmap_parents_in_strict_wave_order`).

**Inbox (5 notes, acknowledged, advisory).** They are used as follows:

| note | used for |
|---|---|
| 1 (t1852) | the `goengines/` layout |
| 2 (t1852_2) | the skeleton's rules |
| 3 (t1853) | M3.1 plugs the runner lister into `scan`/`check`; wire the t1853_4 → M3.1 edge; the automation-first directive |
| 4 (t1853_1) | the `registry.UnitLister` shape |
| 5 (t1853_3) | it suggests `bash-file list --invocations` print M2.3's facts; superseded by Deviation 5, which deletes the verb because M2.3 already feeds the seeder those facts directly |

**Plan review.** The draft was reviewed adversarially by a read-only
planning agent against the proposal and the tree. Its findings are
incorporated:

- the provenance rule for Deviation 7 is redesigned;
- the missing `t1853_7` edge is added;
- the invocation grouping has a single owner;
- `list --invocations` is deleted;
- the axis-field ownership, the line-protocol homes, the "full-suite p95"
  definition and the M2.2 dependency are fixed;
- the M4.5 wave contradiction is noted to t1855.

The user's review of the revised plan raised three blocking concerns, all
verified as valid and addressed:
- Dev 9: the grouping key makes `batch: no` units singletons and takes a
  wave-class input.
- Dev 7: `reads` throughout the test-side closure, with M2.5 as the
  provider; M3.4 now depends on `t1853_5`.
- Dev 13: disjoint parent/child accounting.

## Repository reality anchors (verified 2026-10-13, main @ a2395c309)

| fact | state now |
|---|---|
| Go module | `goengines/` (`go 1.26.0`, toolchain `go1.27.1`); deps `doublestar/v4`, `x/sync`, `yaml.v3` |
| verb table | `goengines/cmd/ait-testmap/verbs.go`: `schedule`, `run`, `costs`, `runner` (and `test`, `select`, …) are `stub(...)` rows (exit 64 `NOT_IMPLEMENTED:`); `scan`/`check`/`annotate`/`verify` are real |
| exit codes | `internal/lineproto`: `ExitOK 0`, `ExitFail 1`, `ExitNothingRan 2`, `ExitFramework 3`, `ExitUsage 64`, `ExitRefused 75`; `lineproto.Enforce` maps an out-of-contract code to 3 |
| shared helpers | `internal/platform`: `Lock(path)` (flock), `Workers`, `NewGroup(ctx, n)` (errgroup, cap 8), `CacheRoot`; `internal/gitx`: `RevParse`, `IsAncestor`, `LsTree`, `ListFiles`, `BlobDigest`, scrubbed `Env` |
| lister seam (M2.1) | `registry.UnitLister{List(ctx, root) ([]Listing, error)}`; `Listing{Runner, Bound, ArtifactGlobs, Units []ListedUnit{ID, Kind, Lowering, Artifact}}` in `goengines/internal/testmap/registry/inputs.go`; wired via `Lister` in `testmapInputs()` (`cmd/ait-testmap/scancheck.go`); until then `scan`/`check` exit 3 `INPUT_UNAVAILABLE:lister` |
| config keys (M2.1) | `registry/config.go` already parses `concurrency`, `broad_after_unit`, `device_policy`, `host_class` (default hostname), `flake_threshold`, `suite_budget_s`, `completion.*` |
| annotations (M2.2) | `annot` parses `testmap:kind`, `batch`, `needs`, `area`, `scope`, `trigger`, `reads`, `axis`; **only `covers` reaches `registry.UnitAnnotation`**; other fields are added additively in `annot/source.go` `toRegistry` by their consumer, as a named extension of M2.2 |
| scanners (M2.3) | `internal/testmap/deps` (landed `2c04a9639`, t1853_3): static facts + closure; per the proposal (*Dependency scanners*, "read once") they are exposed to `internal/seed` directly; `deps.FileFacts.Reads` holds **scanner-plugin** globs only |
| `testmap:reads` | `testmap:reads <glob>` is valid on **helper files only** (proposal *Annotation scanner*). `annot` parses it, but `toRegistry` drops it. Getting `reads` into the registry is **M2.5's** (Module Map M2.5 row) |
| `internal/testmap/{runner,sched,cost}` | none exist |
| M2.5 (t1853_5) | `Ready`, not implemented; owns scoped rows + kind ranking data |
| M2.4 (t1853_4) | `depends: [t1853_1]`; body says "M3.1 (pending: t1854 not decomposed)" |
| t1853_7 | `Postponed`; `depends: [t1853_1..6]`; its provider table asks each provider's decomposition to fill its child edge (M3.1 → t1854) |
| `.aitask-testmap/` gitignore | in this repo's `.gitignore`; setup's job (M1.5, landed) |
| serial carve-out | `tests/test_serial_carveout_doc_drift.sh` compares `SERIAL_CARVE_OUT` with the `CLAUDE.md` marker block; no `testmap:batch` annotations exist anywhere (M10.1 adds them) |
| cross-linking | t1863 (`Ready`) audits children against each parent's `## Submodules` table; archived providers are satisfied and not written into `depends:` |

## Decomposition — four children, one per submodule row

Create all four with `--no-sibling-dep`, then set `depends:` exactly as in
the table below. Children are created in row order, so `t1854_<n>` =
`M3.<n>`. Archived providers (M1.2 = t1852_2, M2.1 = t1853_1,
M2.2 = t1853_2, M2.3 = t1853_3) are recorded in the bodies and never written
into `depends:`.

| child | name | scope (Module Map row, after the Deviations below) | depends | wave | effort |
|---|---|---|---|---|---|
| t1854_1 | `m3_1_runner_contract_and_repository` | See the scope list below this table. | — (M1.2, M2.1, M2.2 landed) | B | high |
| t1854_2 | `m3_2_reference_runners` | `ait-testmap runner <name>`: `bash-file`, `pytest` (junitxml; `testmap:batch no` honoured), `go-test` (per-file `-run` regex, `-json`), `gradle-class` (`--tests <lowering>` batch, one invocation per `group_by` group, JUnit XML inverted through the list table, zero-match trap = mechanism failure), `suite` (any command as one unit, optional child rows from a `children:` post-processor), `device` (reads the allocator handle from the manifest field, Dev 3), `engine-test` over `goengines/`; the `full` suite wrapper's `children:` post-processors (pytest junitxml, bash-file per-file exit — Open question 8 default, `go test -json`). **No `list --invocations`** (Dev 5); **the serial carve-out drift-test pin moves to M10.1** (Dev 6) | t1854_1 | B | high |
| t1854_3 | `m3_3_scheduler_and_resources` | resource kinds `mutex`/`semaphore`/`admission`/`allocator`, scopes `host`/`worktree`/`run`, `acquired_by` planning, `resources.yaml`, `flock(2)` slot files in canonical order, admission exec with 75 deferral and backoff to the run deadline, allocator exec with signal-safe release, `errgroup` execution of the invocations **M3.1's key forms (never re-formed, Dev 9)**, `broad_after_unit` waves (kinds from M2.5, Dev 4) with variant-bearing units in the unit wave and admission-holding invocations last, `device_policy: filter_by_resource`, `concurrency: serial\|parallel` (serial at bootstrap; `--serial`/`--parallel`), the `schedule` verb and its check half **`schedule --check`** (Dev 12); **plugs the scheduler into M3.1's `run` and fills the allocator-handle field** (named extensions of M3.1); refusal at the deadline = exit 75 | t1854_1, **t1853_5** | C | high |
| t1854_4 | `m3_4_cost_ledger` | Welford + P² p95 + last per `(id, host class)` (id opaque, may be a variant); `.aitask-testmap/ledger.jsonl` filled as a **subscriber of M3.1's post-run hook** (Dev 2) with result and invocation rows; **anchor eligibility decided at run time** (Dev 7, incl. helpers' `testmap:reads` from M2.5) and `last_pass {sha, at, run_id}` advancing only from eligible passes; `costs --update` folding into `aitestmap/costs/<hostclass>.yaml` and truncating; flake rate vs `flake_threshold`; the per-group estimate over the canonical grouping (kinds/waves supplied by the caller); **the disjoint full-suite p95** (Dev 13); `costs/predictions.yaml` (store; `score` writes it in M4.4); `costs --gate-timeout` → `GATE_TIMEOUT_SUGGESTED:` (homed here, Dev 12); the run-id prefixes `test-`/`gate-`/`full-`/`review-`; the `costs/policy.yaml` format with read/write helpers (writer logic M8.5); verb `costs` | t1854_1, **t1853_5** (M2.3 landed) | C | medium |

**t1854_1 scope (M3.1):**

- `describe` (`unit file|class|method|variant|suite`, `batch`, `needs`,
  `group_by:`, `filter_scope:`, `full:`, `children:`, `artifact_glob:`).
  `axis:`/`token_format:` are **M2.4's** extension (Dev 10); until M2.4
  lands they are refused as unknown fields.
- `list` TSV `<id> <kind> <lowering> [<artifact>]`, with member and variant
  ids. A malformed row gives `INPUT_ERROR:lister`.
- `run --manifest` with ids, lowerings, groups **and the allocator-handle
  field** (Dev 3).
- `results.jsonl` per id, with child rows under a suite parent.
- `runner.json` with per-group overhead rows.
- `runners.yaml` first-match bindings + per-test override.
- The `builtin:` scheme with `command:`/`cwd:` overrides and shadow-by-name,
  with a resolution record that M4.1's `explain` prints.
- **The canonical grouping function** (Dev 9), the one pure function that
  M3.3, M4.1 and M3.4's estimate use. Its key is `(runner, group_by group,
  resource set, wave class, batch identity)`:
  - `batch identity` is the unit's own id when it is `batch: no`, so it is a
    singleton invocation;
  - `wave class` (`unit` | `broad`) is an input the caller derives from
    M2.5's kind data, with no kind data meaning `unit`.
- Per-unit timeouts.
- `units_expected`/`units_reported` reconciliation: zero-reported with some
  expected, and no-registered-id, are mechanism failures.
- Exit contract `0/1/2/75/64`.
- `subsumed_by:`, `fallback_command:`, and `full: true` + `children:`.
- The runner-backed **UnitLister** wired into `scan`/`check` (named
  extension of M2.1).
- `batch`/`needs` into `registry.UnitAnnotation` (named extension of M2.2's
  `toRegistry`).
- The engine **`run` verb**:
  - `run --all` honours `subsumed_by`.
  - It runs over a **plan-executor seam** with a built-in serial plan that
    **refuses any invocation with a non-empty resource set (exit 3)** until
    M3.3 plugs in (Dev 1).
  - It has an **ordered, multi-subscriber post-run hook** (Dev 2).
  - It keeps an **engine-owned per-invocation record**: `cause`, HEAD at
    start/end, and the modified-path set (Dev 7).

Each child gets the parent's labels (`testing,testmap,go_engine`), priority
`medium` and type `feature`. The profile injects `--gates risk_evaluated`.

## Deviations from the proposal (cut fixes, edited into the proposal per protocol §1)

1. **`run` ↔ scheduler cycle (M3.1 ↔ M3.3).** M3.1 owns the `run` verb;
   M3.3 provides "the wave plan `run` executes" (Module Map M3.3 row) and
   depends on M3.1. Following the proposal's own rule, M3.1 ships `run` over
   an injected plan-executor seam with a built-in serial plan: one invocation
   per grouping-function key, no waves. That plan **refuses any invocation with a
   non-empty resource set** (exit 3, naming the scheduler as unavailable).
   Otherwise `needs:` and cross-process admission would be silently ignored
   in wave B. **M3.3** plugs the scheduler into the seam (named extension of
   M3.1's `run`). Both rows say so.
2. **Ledger rows have no writer in `run` (M3.1 ↔ M3.4).** "Every run" writes
   `.aitask-testmap/ledger.jsonl`, but the ledger is M3.4's and `run` is
   M3.1's. Fix: M3.1 leaves an **ordered, multi-subscriber post-run hook** in
   `run`. It carries the run id, the result rows and the engine's
   per-invocation records. **M3.4** subscribes, appending ledger rows. M4.4's
   automatic `score` "after a `full: true` suite run" can subscribe to the
   same seam later. An API-only test would pass while `run` never called the
   hook, so M3.4's acceptance has a command-level case through the real `run`.
3. **The `device` runner's allocator handle has no carrier.** M3.2 (wave B)
   lists `device` "(allocator handle)"; the allocator is M3.3's (wave C); the
   runner contract names no handle. Fix: M3.1's `run --manifest` format gains
   an allocator-handle field, empty when none is held. **M3.3** fills it.
   **M3.2**'s `device` reads it and is tested with a fixture handle.
4. **M3.3 consumes M2.5.** `broad_after_unit` waves and
   `device_policy: filter_by_resource` need each unit's kind
   (`unit|integration|e2e|device`) and scoped rows. Those are M2.5's ("kind
   ranking data", `_scoped.yaml`) and do not reach the registry today. M3.3's
   "depends on" becomes `M3.1, M2.5`; B before C, so no wave changes. M3.4's
   estimate "per kind" takes the kind from its caller (M4.1, which already
   depends on M2.5).
5. **Delete `bash-file list --invocations`.** It prints the literal repo
   paths a test references "for the seeder's `static:invocation` origin". But
   *Dependency scanners* already exposes exactly those facts to
   `internal/seed`: "same scan, same cache, read once". A second bash
   resolver could only disagree. Remove it from:
   - the M3.2 row;
   - the *Reference runners* component;
   - the process map line for `internal/runner`.

   M3.2 keeps `depends on: M3.1`.
6. **The serial carve-out pin needs annotations only M10.1 writes.** M3.2
   owns "the serial carve-out pin in
   `tests/test_serial_carveout_doc_drift.sh`". The pin asserts that the
   `testmap:batch no` annotations agree with `SERIAL_CARVE_OUT`, but no
   annotation exists before M10.1 (wave I). Fix: M3.2 keeps the `pytest`
   builtin's honouring of `testmap:batch no` with its own Go tests. The
   drift-test extension moves to **M10.1**, which writes the four
   annotations. The *Onboarding* detection table already places it there.
   Note to t1861.
7. **Evidence anchors lack provenance (correctness fix).** The evidence join
   (M4.3) drops passes "from invocations with a cause", a field the ledger
   schema never records. It also treats a pass at `head_sha` as proof that
   the edge held against that commit's tree. Step-7 interactive runs happen
   on a dirty worktree, as do runs in a worktree shared with other sessions.
   A pass after an uncommitted edit (a weakened assertion, a dirty helper, a
   dirty source) would therefore anchor commit C, and M4.3 would report
   `EVIDENCED` for a tree that never ran. The fix decides eligibility **at
   run time**, where the engine has the registry loaded:
   - **M3.1** records, in its **own** per-invocation record, its `cause`
     (empty | mechanism failure | timeout | reconciliation) and the worktree
     provenance:
     - HEAD at invocation start and end;
     - the modified-path set captured at both moments (start ∪ end): staged
       and unstaged modifications, deletions, and untracked non-ignored
       files.

     This record is not the runner-produced `runner.json`: a runner script
     cannot judge its own reconciliation. It is handed to the post-run hook.
   - **M3.4** (the subscriber) marks a passing result **anchor-eligible**
     only if:
     - the invocation had no cause;
     - HEAD did not move;
     - the modified set is disjoint from all of the following:
       - the test file and the unit's whole test-side closure, i.e. every
         helper it reaches (M2.3, landed);
       - every `covers` source of the unit;
       - **the `reads` globs of every file in that closure**: the helpers'
         `testmap:reads` annotations, which reach the registry through
         **M2.5**, plus scanner-plugin `reads` from M2.3's `FileFacts`. A
         dirty data file matched only by a helper's `reads` glob therefore
         blocks the anchor;
       - the runner's command and configuration (`aitestmap/runners.yaml`,
         `aitestmap/runners/**`, the `children:` post-processor inputs);
     - when the closure is opaque or not computable (suite / `full: true`
       child rows, whole-run filters), the modified set is **empty**.

     The ledger row carries `anchor` (+ reason). `last_pass {sha, at,
     run_id}` advances only from eligible passes. **No path lists are
     written to committed files.**
   - **M4.3** adds one guard: ignore an anchor whose `at` date is not
     strictly later than the edge's stamp date. This covers edges stamped
     after the anchoring run's eligibility was judged. A same-day anchor is
     ignored, which is fail-safe.
   - Every rejection yields `STALE`, so the loop fails only toward running
     more (Invariant 1).
   - **Residual, stated in the component:** a file edited and reverted
     during a run is invisible to start/end snapshots.
   - M3.4's "depends on" becomes `M3.1, M2.3, M2.5`. M2.3 has landed; M2.5
     is wave B, before M3.4's wave C, so no wave changes.
   - The child gets `depends: [t1854_1, t1853_5]`.
   - The exact encoding is left to M3.1/M3.4's Reality checks, and the
     acceptance is red-proved. Note to t1855.
8. **The `SCAFFOLD_TODO` `check` report has no owner.** The line is homed and
   in M6.4's scope, but "which `check` reports" (*Runner contract*) is owned
   by nobody. Fix: until M6.4, M3.1's lister refuses a malformed `list` row
   with `INPUT_ERROR:lister` (fail-closed). **M6.4** adds `SCAFFOLD_TODO`
   recognition and its `check` report as a named extension of M3.1's lister
   and M2.1's `check`. Note to t1857.
9. **Invocation forming has two owners, and the key is wrong.** M3.1's row
   has "batching keys" and its component has "batching by (runner, group,
   resource set, batch flag)". M3.3's row has "batching per `group_by`". If
   both form invocations, the `SELECTED:` `<groups>` count and the
   estimate's Σ over groups disagree with what M3.3 runs. The key as written
   is also unsound:
   - two `batch: no` units with otherwise identical fields share a key and
     would be batched together;
   - a unit test and an integration test with the same runner, group and
     resources share one invocation, which cannot run before and after a
     green unit wave at once.

   Fix: **M3.1 owns one canonical grouping function**, keyed by `(runner,
   group_by group, resource set, wave class, batch identity)`:
   - `batch identity` is a shared marker for batchable units and the
     **unit's own id** for `batch: no` units, which makes them singletons;
   - `wave class` (`unit` | `broad`) is an **input**. The caller derives it
     from M2.5's kind data: `unit` and variant-bearing units → `unit`;
     `integration|e2e|device` → `broad`. Without kind data every unit is
     `unit`, which is sound because no broad unit can exist before M2.5.

   With that function:
   - M3.1 stays independent of M2.5;
   - the grouping is the same whether or not `broad_after_unit` is set, so
     estimates do not depend on config;
   - M3.3 orders, admits and executes those invocations and **never
     re-forms them**; its `broad_after_unit` waves are a pure ordering over
     invocations that are already wave-homogeneous;
   - M4.1's groups and M3.4's estimate call the same function with the same
     inputs, so the estimate and the execution agree by construction.
10. **`axis:` / `token_format:` have two owners.** They appear in M3.1's
    `describe` list and as M2.4's named extension of that parse. Fix: they
    are M2.4's alone. M3.1 refuses them as unknown until M2.4 lands, and the
    component text is annotated. M2.4's row also drops "cost" from its
    provides. M3.4 treats ids, variants included, as opaque strings from run
    results and does not consume M2.4. The matching "M3.4" in t1853_4's
    Provides line is edited.
11. **M3.1 consumes M2.2.** The `batch` / `needs` annotations reach the
    registry only through M2.2's `toRegistry`. M3.1's "depends on" becomes
    `M1.2, M2.1, M2.2`; M2.2 has landed.
12. **M3's output lines have no home.** None of these appear in the
    line-protocol index:
    - `run`'s wave and per-id result lines and its mechanism-failure lines;
    - the `schedule` report and its check half;
    - `costs` output.

    `GATE_TIMEOUT_SUGGESTED:` is homed under the onboarding verbs but defined
    and owned by the cost ledger. Fix:
    - add an M3 row to the index, homing the run/schedule lines in the
      *Scheduler* / *Runner contract* components and the `costs` lines in
      *Cost ledger*;
    - move `GATE_TIMEOUT_SUGGESTED:` there;
    - define the check half as `schedule --check`, which prints M3.3's own
      lines and is not an M2.1 `check` rule.

    The exact line names are left to the children's Reality checks.
13. **"p95 of the newest full run" is undefined, and a naive sum
    double-counts.** M3.4 keeps per-id statistics only, yet
    `--gate-timeout`, the cadence's `selection_ratio_above` (M8.5) and
    `FULL_GATE:` consume a full-suite p95. The runner contract allows a
    suite parent result *and* its child results. Summing every id would
    count a 100 s suite with 40 s and 60 s children as 200 s before
    overhead. Fix, a **disjoint accounting rule**:
    - every estimate (selection and full) sums, per invocation group,
      `overhead.p95` plus the p95 of each **top-level** id only, i.e. an id
      that is not a child row of a suite parent in that invocation;
    - an invocation's `overhead_ms` is its elapsed time minus the sum of its
      top-level results' durations, clamped at 0;
    - child rows keep their own cost statistics and their evidence, and
      never add to an estimate that includes their parent;
    - the **full-suite p95** is that estimate applied to the invocation
      groups and top-level ids of the newest `full-` run on this host class.

    M3.1's results mark each row top-level or child (they already nest child
    rows under a suite parent). Note to t1859.
14. **`costs/policy.yaml` schema mismatch.** *The registry directory* sketch
    omits `contract`, which *Where state lives* includes. Add it to the
    sketch.

**Automation-first (user directive, 2026-10-11, relayed by t1853).** No M3
verb may make a human action a precondition of any path. Specifically:

- `concurrency`, `--serial`/`--parallel`, `resources.yaml` and
  `costs --gate-timeout` are values and computed suggestions, never
  approvals.
- The schedule report and `schedule --check` are informational, never
  gates.
- M3 encodes no "awaiting a person" state.

Two human-flavoured steps sit next to M3 and are owned elsewhere:

- "declarations are reviewed in the schedule report before concurrency is
  trusted" (`tradeoff_resource_declaration_completeness`);
- `runners.yaml` "confirmed per runner" by `onboard detect --write`.

Both are onboarding's (M6). The step-6 note asks t1857 to automate them, for
example by flipping `concurrency` on measured serial/parallel full-run
agreement. Every child body and plan carries this paragraph.

**Not deviations** (recorded so the children do not re-derive them):

- Owns cells read `internal/<pkg>` as `goengines/internal/testmap/<pkg>`.
- `run --all` with `subsumed_by` is M3.1's verb. M4.5 composes it and
  triggers `score`.
- Shadow-by-name: the resolution record is M3.1's; M4.1's `explain` prints
  it.
- `onboard detect`'s detectors and the `RESOURCE_HINT` → `resources.yaml`
  writes are M6.1/M6.4's. M3.3 only reads `resources.yaml`.
- Committing `costs/*.yaml` is the front's or the skill's job. The engine
  never commits (Invariant 5).
- The `.aitask-testmap/` gitignore is M1.5's.
- The `kind` / `area` / `scope` fields reach the registry through M2.5; M3.1
  carries only `batch` / `needs`.
- A `full` suite runner whose command reaches `./ait test` recurses, and it
  would reach `aitask_test.sh`, which Invariant 5 forbids. M3.2's Reality
  check decides the refusal. The note asks t1857 to make `detect` snapshot
  the pre-enable `test_command`.

## Cross-module seams (recorded in every child body)

**Provides:**

| what | provider | consumers |
|---|---|---|
| the runner contract, `results.jsonl`, the plan-executor seam, the post-run hook, the per-invocation record | M3.1 | M3.2, M3.3, M3.4, M4.4, M6.1 |
| the lister | M3.1 | M2.1 `scan`/`check` |
| the `describe` parse | M3.1 | M2.4 `axis:`/`token_format:` |
| the canonical grouping function (singleton `batch: no`, wave-class input) | M3.1 | M3.3, M4.1, M3.4 |
| builtins | M3.2 | M4.5, M6.2, M8.4, M10.4, M10.5 |
| `resources.yaml`, the wave plan, exit 75 | M3.3 | M4.5, M6.1, M6.4 |
| cost rows, eligible `last_pass`, the estimate and full-suite p95, `predictions.yaml`, the `policy.yaml` format | M3.4 | M4.1, M4.3, M4.4, M6.5, M8.5 |

**Consumes** (landed unless marked): M1.2, M2.1, M2.2, M2.3; **M2.5**
(pending; M3.3 for the kind → wave class mapping and scoped rows, M3.4 for
the helpers' `testmap:reads` in the eligibility rule).

**Named extensions:**

| extension | owner | added by |
|---|---|---|
| the runner lister | M2.1 | M3.1 |
| `batch`/`needs` in `toRegistry` | M2.2 | M3.1 |
| the scheduler + allocator handle in `run` | M3.1 | M3.3 |
| the ledger subscriber to the post-run hook | M3.1 | M3.4 |
| `axis:`/`token_format:` in `describe` | M3.1 | M2.4 |
| `SCAFFOLD_TODO` in the lister + `check` | M3.1, M2.1 | M6.4 |
| the `policy.yaml` writer | M3.4 helpers | M8.5 |
| `predictions.yaml` writes | M3.4 store | M4.4 |
| the score subscriber to the post-run hook (optional) | M3.1 | M4.4 |

Invariant 1 (the loop fails only toward running more) and Invariant 4 (the
engine never launches a code agent) bind the runner and the scheduler.

## Child plan template (`aiplans/p1854/p1854_<n>_<name>.md`)

Child header per `planning.md`: `Task:`, `Parent Task:`, `Sibling Tasks:`,
`Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md`,
`Base branch: main`, `Output branch: main`, no `Worktree:`. Then:

1. **Context.** The parent goal, this row, the wave, and verbatim: *"This
   coarse plan records what the proposal fixes for M3.<n>. It does not
   design internals against providers that do not exist yet; the Reality
   check below does that when this child is picked."*, plus the
   automation-first paragraph.
2. **Proposal reading list.**
   - The Module Map `#### M3` row.
   - The component subsection(s): *Runner contract and repository* /
     *Reference runners* / *Scheduler and resources* + *Broad-test
     scheduling (M3.3 half)* / *Cost ledger* (+ *Evidence join* as M3.4's
     consumer).
   - *Architecture → Process map, Where state lives, Line-protocol index*.
   - *Running Tests*; *The Run Surface → Output and exit contract*.
   - *Assumptions → Variants, broad tests and runners*; *Tradeoffs → Map and
     registry structure*; *Open questions* (8 for M3.2).
   - The parent plan's Deviations; `goengines/README.md`.
3. **Owned files / provides / consumes**, from the tables above.
4. **Step 0 — Reality check (MANDATORY, before any code; outcome recorded in
   this plan file).** The six sub-steps of the parent body §2, starting from
   the anchors table above; by pick time those anchors are claims, not facts.
   Child-specific items:
   - **M3.1:** the actual lister seam and `testmapInputs()`; the
     `toRegistry` extension point; the per-invocation record's encoding.
   - **M3.2:** M3.1 as landed; the `./ait test` recursion refusal.
   - **M3.3:** M3.1's plan-executor seam, grouping function and handle field;
     M2.5's kind data. **Stop if M2.5 has not landed.**
   - **M3.4:** M3.1's hook, per-invocation record and top-level/child
     marking; M2.3's closure API and plugin `reads`; M2.5's `testmap:reads`
     data in the registry; M4.3's plan (send a note if the anchor shape
     differs). **Stop if M2.5 has not landed.**
5. **Implementation steps (coarse)**: the scope cell expanded into ordered
   steps naming the package and the verb row.
6. **Verification / acceptance:**
   - **M3.1:**
     - `describe` parse goldens per field; an unknown field (including
       `axis:` until M2.4) is refused.
     - `list` TSV with member/variant ids and the artifact column; a
       malformed row gives `INPUT_ERROR:lister`.
     - First-match bindings + per-test override; shadow-by-name picks the
       project script and records why.
     - Grouping function:
       - each key component splits invocations;
       - two `batch: no` units with otherwise identical fields yield two
         singleton invocations;
       - the same runner/group/resources with `wave class` `unit` vs
         `broad` yields two invocations;
       - missing kind data means `unit`.
     - Results mark each row top-level or child.
     - A per-unit timeout fails that unit with a timeout cause.
     - Reconciliation: zero-reported-some-expected and no-registered-id are
       mechanism failures; missing ids fail.
     - Runner exit 75 → run exit 75; out-of-contract → 3.
     - `run --all` runs a `subsumed_by` pair's suite once and never the
       subsumed runner.
     - `full: true` child rows land under the parent; `fallback_command:` is
       accepted only on a suite runner.
     - A non-empty resource set under the built-in plan → exit 3.
     - Real-lister `scan`/`check` on a fixture repo, with no
       `INPUT_UNAVAILABLE`.
     - **Provenance, red-proved:** a fixture with a staged deletion, an
       unstaged deletion, an untracked file and a modified tracked file
       records all four; HEAD advanced mid-run is recorded; a mechanism
       failure records its `cause`.
     - Hook subscribers fire once each, in order.
     - Invariants 4–5 tripwire green.
   - **M3.2:**
     - Per builtin, a fixture repo listing and running one pass and one
       fail unit.
     - pytest junitxml inversion; `testmap:batch no` units run outside the
       batch.
     - `go-test -json` per file.
     - `gradle-class` against a fake Gradle emitting JUnit XML, incl. one
       invocation per `group_by` group and the zero-match trap.
     - `suite` child rows through each of the three `children:`
       post-processors.
     - `device` reads a fixture handle and refuses without one.
     - `engine-test` lists `goengines/` packages.
     - A `full` suite command reaching `./ait test` is refused.
   - **M3.3:**
     - Two real processes contend on a `mutex` slot and serialize;
       `semaphore` n.
     - Runs acquiring `{a,b}` / `{b,a}` never deadlock.
     - `host` / `worktree` / `run` scope slot paths.
     - Admission answering 75 retries with backoff and exits 75 at the
       deadline (advisory `skip:admission_refused`).
     - **Allocator released under SIGINT and SIGTERM** of the engine
       process.
     - `broad_after_unit`: scoped rows run only after a green unit wave, and
       are skipped and printed after a red one.
     - Variant-bearing units ride the unit wave; admission-holding
       invocations run last.
     - `device_policy: filter_by_resource`; serial by default;
       `--serial`/`--parallel`.
     - The pool never exceeds 8.
     - Invocations are never re-formed: they are identical to the grouping
       function's output, and the executed invocation count equals the
       estimate's group count for the same selection.
     - Two `batch: no` units with otherwise identical fields run as two
       invocations.
     - **A mixed unit + integration selection that shares runner, group and
       resources, where the unit test fails, under `broad_after_unit: true`:**
       the integration invocation is not run, and the skip is printed.
     - `schedule` report and `schedule --check` refusing an undeclared
       resource name.
     - The allocator handle reaches the manifest.
   - **M3.4:**
     - Welford vs direct mean/variance; P² p95 within tolerance of the exact
       quantile.
     - **Command-level:** a real `run` appends one ledger row per result and
       one per invocation through the hook.
     - `costs --update` folds (sorted; byte-identical on a re-run with
       nothing new) and truncates.
     - **Concurrent append during `--update` loses no row** (two processes,
       one lock).
     - **Eligibility red-proved.** A pass is not eligible in any of these
       cases:
       - after an uncommitted weakening of the test;
       - with a dirty helper in its closure;
       - with a dirty `covers` source;
       - with **only a dirty data file matched by a helper's `testmap:reads`
         glob**, or by a scanner-plugin `reads` glob;
       - when the invocation had a cause;
       - when HEAD moved;
       - for an opaque/suite unit with any modified path.

       A pass with only unrelated dirty paths is eligible. No path list
       appears in `costs/<hostclass>.yaml`.
     - Flake rate vs `flake_threshold`.
     - Estimate = Σ groups `overhead.p95` + Σ top-level ids p95, over the
       canonical grouping with the caller's wave/kind inputs; an id with no
       row follows the Reality-check-decided fallback.
     - **Disjoint accounting:** in a full run with one invocation, a suite
       parent of 100 s with child rows of 40 s and 60 s, and 105 s elapsed,
       contributes 100 + 5 overhead = 105 s, never 205 s. The child cost
       statistics (40 s, 60 s) and child evidence are still recorded. The
       full-suite p95 and `GATE_TIMEOUT_SUGGESTED:` use that figure.
     - `predictions.yaml` keeps the last 200.
     - `GATE_TIMEOUT_SUGGESTED:<gate>|<s>` = `max(600, 3 × full-suite
       p95)`.
     - Run-id prefixes; `review-` writes no cost rows.
     - `policy.yaml` helpers; a newer `contract:` → `CONTRACT_MISMATCH`.
   - **Every child:**
     - `ait engine test` green.
     - No path requires a human action. A human-only step met in the
       proposal is reported to its owning parent, never encoded.
7. **Step 9 reference.** The shared post-implementation; current branch, no
   merge.

## Post-approval sequence

0. **Edit the proposal for Deviations 1–14 in one change.** The edits:
   - **Module Map rows.**
     - M3.1–M3.4 scope cells, and their depends cells: exactly
       `M1.2, M2.1, M2.2` / `M3.1` / `M3.1, M2.5` / `M3.1, M2.3, M2.5`.
     - M3.2 owns the builtins only (no drift-test pin).
     - M2.4 provides "for the selector and evidence".
     - M6.4 gains the `SCAFFOLD_TODO` `check` report.
     - M10.1 gains the drift-test pin.
   - **Cross-module interfaces rows** for M3.1/M3.3/M3.4: plan seam, hook,
     canonical grouping function, handle, eligible anchors, full-suite p95.
   - **Process map:** the `internal/runner` line loses
     `bash-file list --invocations`.
   - **The registry directory:** `policy.yaml` gains `contract`.
   - **Where state lives:** the "runs, ledger" row carries the ledger
     schema, incl. `cause` / `anchor`.
   - **Line-protocol index:** the M3 row; `GATE_TIMEOUT_SUGGESTED:` moved.
   - **Components:**
     - *Runner contract*: handle field; engine per-invocation record;
       the canonical grouping function (singleton `batch: no`, wave-class
       input); top-level/child marking; plan seam + resource refusal; hook;
       `axis:`/`token_format:` → M2.4; malformed row; `SCAFFOLD_TODO` →
       M6.4.
     - *Reference runners*: `device` handle; no `list --invocations`; pin →
       M10.1.
     - *Scheduler and resources*: executes, never re-forms; waves are an
       ordering over wave-homogeneous invocations; plugs into `run`;
       handle; kind → wave class from M2.5; `schedule --check`.
     - *Cost ledger*: hook subscriber; eligibility rule (incl. closure
       `reads` via M2.5) + residual; no path lists committed; disjoint
       accounting and full-suite p95.
     - *Evidence join*: stamp-date guard; cause filter pre-applied.

   Commit path-scoped:
   `git commit -m "documentation: Fix the M3 cut in the testmap proposal (t1854)" -- aidocs/testing_engine/n014_explorer_006_proposal.md`.
0b. **Sync t1854's own body with the corrected cut**, with the Edit tool and
   never touching `## Inbox`:
   - the `## Submodules` scope cells, and depends cells exactly as in step 0;
   - the M3.2 owns note;
   - the *Hooks and extensions* bullets (the named-extensions table above,
     the pin → M10.1, the `SCAFFOLD_TODO` → M6.4);
   - the automation-first paragraph.

   Commit with
   `aitask_task_commit.sh -m "ait: Sync t1854 submodule table with the corrected M3 cut" aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md`.
1. **Externalize this plan** with
   `aitask_plan_externalize.sh 1854 --force --profile aitasks/metadata/profiles/fast.yaml --no-worktree`,
   then commit it with `aitask_task_commit.sh`.
2. **Create the four children** with `aitask_create.sh --batch --commit
   --parent 1854 --no-sibling-dep …`. Each description carries the Child
   Task Documentation Requirements sections. Then set `depends:` per the
   table: `aitask_update.sh --batch 1854_2 --deps t1854_1`; `1854_3 --deps
   "t1854_1,t1853_5"`; `1854_4 --deps "t1854_1,t1853_5"`.
3. **Wire the pending consumer edges.** Read each current list first,
   because `--deps` replaces it.
   - **t1853_4:** `aitask_update.sh --batch 1853_4 --deps
     "t1853_1,t1854_1"`. In its body (keeping `## Inbox`), change "M3.1
     (pending: t1854 not decomposed)" to "M3.1 (`t1854_1`)", and remove M3.4
     from its Provides line (Dev 10). Make the same Context change in
     `aiplans/p1853/p1853_4_*.md`.
   - **t1853_7:** `aitask_update.sh --batch 1853_7 --deps
     "t1853_1,t1853_2,t1853_3,t1853_4,t1853_5,t1853_6,t1854_1"`. Keep its
     status `Postponed`, since other provider rows are still unresolved. In
     its provider table, record that the M3.1 row resolves to `t1854_1`.

   Commit with `aitask_task_commit.sh`, naming the three paths.
4. **Revert the parent:** `aitask_update.sh --batch 1854 --status Ready
   --assigned-to "" --plan-approved-at ""`, then `aitask_lock.sh --unlock
   1854`.
5. **Write the four child plans** to `aiplans/p1854/` and commit them
   together, naming every file.
6. **Send notes** with `/aitask-note`, citing the proposal commit from
   step 0:

   | to | content |
   |---|---|
   | t1855 (M4) | Dev 7: anchors are pre-filtered at run time; M4.3 adds the stamp-date guard; the cause filter is pre-applied; M4.3 newly reads the `anchor` field.<br>Dev 9: M4.1 groups with M3.1's canonical grouping function and the same wave-class input (from M2.5 kinds), so `SELECTED:` `<groups>` and the estimate match execution; `batch: no` units are singletons.<br>Dev 13: disjoint accounting (top-level ids only) and the full-suite p95.<br>`explain` prints M3.1's shadow resolution.<br>The estimate takes kinds from the caller.<br>M4.5 composes `run --all`; the scheduler sits inside `run`.<br>**M4.5 is wave C but depends on M4.4 (wave D)**: M4.5 should ship `--all` without the `score` trigger, and M4.4 add it as a post-run hook subscriber.<br>`RESULT:` has two shapes (Run Surface vs the `test` composite). |
   | t1856 (M5) | the two `RESULT:` shapes. |
   | t1857 (M6) | Dev 8: the `SCAFFOLD_TODO` `check` report is M6.4's.<br>`GATE_TIMEOUT_SUGGESTED:` is now homed in *Cost ledger*.<br>Automate the two human-flavoured steps: concurrency trust, and `runners.yaml` confirmed per runner.<br>`detect` must snapshot the pre-enable `test_command` for `full` / `fallback_command`, never `./ait test`. |
   | t1859 (M8) | Dev 13: the full-suite p95 used by M8.5's cadence is disjoint (a suite parent's inclusive time, never parent + children).<br>Dev 14: `policy.yaml` carries `contract`. |
   | t1861 (M10) | Dev 6: the drift-test pin is M10.1's. |
   | t1863 | New edges `t1854_3 → t1853_5`, `t1854_4 → t1853_5`, `t1853_4 → t1854_1`, `t1853_7 → t1854_1`.<br>M3.1 → M1.2/M2.1/M2.2 and M3.4 → M2.3 are omitted as archived. |

   Then update memory `feedback_testmap_parents_in_strict_wave_order`:
   t1854 decomposed; the t1853_4 / t1853_7 edges wired; the next coarse pass
   in order is t1855 (M4), waiting for its wave-earliest providers.
7. **Manual-verification sibling prompt**; child checkpoint → **Stop here**.

### Post-phase (risk mitigations)

1. **[verify_child_plans_carry_reality_check]** After step 5 writes the four
   plans and before they are committed, run
   `grep -L 'Step 0 — Reality check' aiplans/p1854/p1854_*_*.md` and
   `grep -L 'does not design internals against providers that do not exist yet' aiplans/p1854/p1854_*_*.md`.
   Both must print nothing. Any file named is fixed before the commit.
2. **[verify_child_dependency_graph]** After steps 2–3, read back
   `grep '^depends:' aitasks/t1854/t1854_*_*.md aitasks/t1853/t1853_4_*.md aitasks/t1853/t1853_7_*.md`.
   It must show exactly:

   | task | `depends:` |
   |---|---|
   | `_1` | `[]` |
   | `_2` | `[t1854_1]` |
   | `_3` | `[t1854_1, t1853_5]` |
   | `_4` | `[t1854_1, t1853_5]` |
   | `t1853_4` | `[t1853_1, t1854_1]` |
   | `t1853_7` | `[t1853_1, t1853_2, t1853_3, t1853_4, t1853_5, t1853_6, t1854_1]` |

   Any other value is corrected with `aitask_update.sh` before the parent is
   reverted.
3. **[verify_parent_table_matches_graph]** After steps 0, 0b and 2, extract
   the M3 "depends on" cells from both tables. Count fields **from the end**,
   because scope cells contain an escaped `\|` (e.g. `serial\|parallel`). The
   proposal's depends cell is `$(NF-1)`; t1854's `## Submodules` depends cell
   is `$(NF-2)`:
   ```bash
   x() { awk -F'|' -v off="$2" '/^\| \*\*M3\.[1-4]\*\*/{c=$(NF-off); gsub(/^ +| +$/,"",c); print c}' "$1"; }
   x aidocs/testing_engine/n014_explorer_006_proposal.md 1 > "$S/prop.txt"
   x aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md 2 > "$S/parent.txt"
   printf '%s\n' 'M1.2, M2.1, M2.2' 'M3.1' 'M3.1, M2.5' 'M3.1, M2.3, M2.5' > "$S/expected.txt"
   diff "$S/expected.txt" "$S/prop.txt" && diff "$S/expected.txt" "$S/parent.txt"
   grep -n -- '--invocations' aidocs/testing_engine/n014_explorer_006_proposal.md
   grep -n '^| \*\*M3\.2\*\*.*test_serial_carveout_doc_drift' aidocs/testing_engine/n014_explorer_006_proposal.md
   ```
   `$S` is the session scratchpad. Both diffs must be empty, with exactly four
   lines each, and both greps must print nothing. Then map each cell onto the
   child graph:
   - `M1.2` / `M2.1` / `M2.2` / `M2.3` → omitted (archived t1852_2 /
     t1853_1 / t1853_2 / t1853_3).
   - `M2.5` → `t1853_5` (in both `_3` and `_4`).
   - `M3.1` → `t1854_1`.

   Any mismatch is fixed before the parent is reverted.

## Verification (of this pass)

- `aitask_ls.sh -v --children 1854 99` lists four `Ready` children. t1854_1
  is unblocked; the rest are blocked exactly per the table.
- The two Reality-check greps over `aiplans/p1854/` print nothing.
- The parent is `Ready`, unassigned and unlocked, with
  `children_to_implement: [1854_1 … 1854_4]`.
- In the proposal:
  - the M3 depends cells read exactly as in step 0;
  - `grep -n -- '--invocations'` returns nothing;
  - `test_serial_carveout_doc_drift` appears in no M3.2 cell;
  - the *Cost ledger* component states the eligibility rule;
  - the line-protocol index has an M3 row.
- t1853_4 depends `[t1853_1, t1854_1]` and its body no longer says
  "pending". t1853_7's depends includes `t1854_1`.

## Risk

### Code-health risk: low
- The pass writes task/plan data and one documentation edit. A wrong `depends:` cell would mis-block or early-unblock a child · severity: low (residual — checked by the inline post-phase) · → mitigation: inline post-phase verify_child_dependency_graph

### Goal-achievement risk: medium
- The fourteen cut fixes are hypotheses made before M4/M6/M8/M10 are planned. A child implemented without executing its Reality check would build against the proposal's description instead of the tree · severity: low (residual — heading and sentence grep-verified; executing the step remains the child's obligation) · → mitigation: inline post-phase verify_child_plans_carry_reality_check
- t1863 audits children against each parent's `## Submodules` table. A stale table, or an unwired consumer edge (t1853_4, t1853_7 → M3.1), would let a consumer unblock before its provider lands · severity: medium (residual low — table/proposal diff + edge read-back) · → mitigation: inline post-phase verify_parent_table_matches_graph (plus the step-6 note to t1863)
- Evidence anchors without run-time eligibility, including dirty data files reached only through a helper's `testmap:reads`, would let a dirty-tree pass manufacture `EVIDENCED` · severity: high before the fix · → mitigation: Deviation 7 proposal fix (M2.5 as the `reads` provider) + red-proved M3.1/M3.4 acceptance cases (residual: an edit-and-revert during a run is invisible; stated in the component)
- An invocation key that merges `batch: no` units or mixes unit and broad tests would break `broad_after_unit` and make estimates disagree with execution · severity: high before the fix · → mitigation: Deviation 9 canonical grouping function + the M3.1/M3.3 acceptance cases (two `batch: no` units; mixed selection with a failing unit test)
- Counting a suite parent and its children together would inflate the full-suite p95 used by the cadence and the gate timeout · severity: medium before the fix · → mitigation: Deviation 13 disjoint accounting + the suite-parent-plus-children M3.4 case
- The run/ledger seams are API-level and could be tested without the real verb calling them · severity: medium before the fix · → mitigation: Deviations 1–2 + the command-level M3.4 ledger case

### Planned mitigations
- timing: post-phase | name: verify_child_plans_carry_reality_check | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — child plan lacking the mandatory Reality check | desc: grep every child plan for the Step 0 heading and the no-internals sentence before committing them
- timing: post-phase | name: verify_child_dependency_graph | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — a wrong depends cell mis-blocking a child | desc: read the four child depends lines plus t1853_4 / t1853_7 back and compare with the decomposition table before reverting the parent
- timing: post-phase | name: verify_parent_table_matches_graph | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — t1863 auditing children against a stale parent submodule table | desc: diff the proposal's and t1854's M3 depends cells against the expected strings, map them onto the child graph, and grep out the removed list --invocations / drift-pin mentions
