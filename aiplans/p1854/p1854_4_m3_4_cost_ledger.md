---
Task: t1854_4_m3_4_cost_ledger.md
Parent Task: aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md
Sibling Tasks: aitasks/t1854/t1854_1_*.md, aitasks/t1854/t1854_2_*.md, aitasks/t1854/t1854_3_*.md
Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-20 09:49
---

# Plan: t1854_4 — M3.4 Cost ledger (verified + detailed, 2026-10-19)

## Context

This is M3.4 of t1854 (testmap M3: runners, scheduling and cost), wave C. It
provides cost statistics, run-time anchor eligibility with `last_pass`, the
disjoint estimate and full-suite p95, `GATE_TIMEOUT_SUGGESTED:`, the
`predictions.yaml` store and the `policy.yaml` format.

- **Consumers:** M4.1 (ranking, budget), M4.3 (anchors), M4.4 (score,
  readiness), M6.5 (gate timeout) and M8.5 (cadence).
- **Sources:**
  - the proposal `aidocs/testing_engine/n014_explorer_006_proposal.md`
    (*Cost ledger (M3.4)*, *Where state lives*,
    `assumption_passing_run_anchors_edges`, `tradeoff_batch_misreport_risk`);
  - the parent plan's Deviations 2, 7, 12, 13 and 14.

**Automation-first (user directive, 2026-10-11).** No path shipped here makes
a human action a precondition:

- `costs --gate-timeout` is a computed suggestion, never an approval;
- `policy.yaml` is engine-written;
- nothing encodes an "awaiting a person" state.

## Step 0 — Reality check (done in this verify pass; main @ 00322dab0)

### Providers as landed

**M3.1 — `t1854_1`, landed in `3d1a2b628`**

- **Post-run hook:** `runner.RegisterPostRunHook(name, func(ctx, *RunReport) error)`.
  - Subscribers run in registration order, after `record.json` is written.
  - A failing subscriber does not stop the next; it is reported as
    `RUN_HOOK_ERROR:<hook>|<detail>` with exit 3.
- **`RunReport`:** `{RunID, Root, Dir, Selected, Invocations []Record, Results []Result}`.
- **`Record`** fields:
  - `group` (= `Key.String()`), `runner`, `units_reported`;
  - `elapsed_ms`, `overhead_ms` (already elapsed − Σ top-level, ≥ 0);
  - `cause`, `cause_detail`;
  - `head_start`, `head_end` (`""` on an unborn HEAD);
  - `modified` (start ∪ end, minus `.aitask-testmap/`).
- **`Result`:** `{ID, Status, DurationMS, Parent, Child, Invocation}`.
  - Engine-synthesized statuses: `timeout`, `not_started`, `batch_timeout`,
    `missing`, `refused`, `error`.
- **Grouping:** `runner.Group(units, wave)`, with `Invocation{Index, Key, Units, Runner}`.
- **Unit facts:** `Repository.Units[].Kind` is the granularity
  (`file|class|method|variant|suite`).
  `Runner{Entry{Script, Command, Cwd}, Resolution{Path}, Describe{Unit, Full, FilterScope, Children}}`.
- **Run ids:** `--run-id`, else `$AIT_GATE_RUN_ID`, else `run-<UTC>-<pid>`.

**M2.3 — `t1853_3`, landed in `2c04a9639`**

- `deps.Scan(ctx, root, deps.Options{Config})` returns a `*Graph`.
- `Graph.Closure(path, 0)` is a BFS over facts.
- `Graph.Opaque(path)` and `Graph.Facts(path).Reads` hold the scanner-plugin
  globs.
- The universe is the git-visible files minus `exclude:`.

**M2.5 — `t1853_5`, landed in `6f6d1ed79`**

- `registry.ScopedOf(reg).Reads` is `[]ReadsRow{Helper, Globs, Line, File}`.
  It is persisted in `_scoped.yaml` and built by `scan --apply`.
- `UnitAnnotation.Reads` holds the current annotation.
- `registry.ReadsHelper(f)` identifies a helper file.
- `Scoped.Join` matches with `doublestar.Match(glob, changedPath)`.

**Shared helpers**

- `platform.Lock(path)`: flock.
- `testmap.CheckContract` / `ContractMismatchError` (`CONTRACT_MISMATCH`, 3).
- `registry.Render` / `registry.WriteFile` (deterministic YAML, written only
  on change, atomic rename).
- `registry.Config.HostClass()` (default: the hostname) and
  `FlakeThreshold` (default 0.2).

**M4.3** — t1855 is **not decomposed**, so there is no plan to inspect. A note
goes there instead (step 0.5 below).

### Differences and decisions

| # | proposal / coarse plan says | repository has | decision |
|---|---|---|---|
| D1 | the subscriber decides eligibility "where the registry is loaded" | `RunReport` carries neither the loaded `Repository` (unit granularity, runner describe and entry) nor whether the run was `--all` | **Adapt (a named extension of M3.1):** add `Repo *Repository` and `All bool` (both `json:"-"`) to `RunReport`, set in `Run`. Otherwise the hook would re-run every runner's `describe`/`list`. |
| D2 | covers and helper reads come from "the registry" | the persisted `_scanned.yaml` / `_scoped.yaml` lag the annotations until `scan --apply`. A fresh, unscanned repo has no covers edges, so a dirty covered source would **not** block the anchor (fail-open). | **Adapt:** eligibility uses the **union** of the current annotations (`annot.Source{}.Annotations`: covers, and the `Reads` of `ReadsHelper` files) with the persisted registry (`registry.Load` edges + `ScopedOf(reg).Reads`). The union is stricter, so it fails toward running more. |
| D3 | run-id prefixes `test-` / `gate-` / `full-` / `review-` | M3.1's default id is `run-…` | **Adapt:** an unknown prefix is surface `other`, with ordinary rows like `test-`. The full-suite p95 counts only a run that is **`full-` and `--all`**, so a mis-prefixed partial run never becomes "the full suite". Note to t1855 (M4.5 must pass `--run-id full-…`). |
| D4 | ledger rows `{run_id, id, parent?, status, duration_ms, head_sha, anchor, anchor_reason?}` / `{run_id, group, overhead_ms, units_reported, cause}` | folding needs host class, time and invocation linkage | **Revise the proposal (additive):** add `row`, `surface`, `host_class`, `at`, `invocation`, `group`, `clean` to result rows and `row`, `surface`, `host_class`, `at`, `invocation`, `runner`, `elapsed_ms`, `refused`, `all` to invocation rows. Also add a `run_end` row `{run_id, host_class, at, invocations, results}` as complete-run framing, and the reserved store basenames. Edit *Where state lives* and the component. |
| D5 | "a flake rate against `flake_threshold`" (undefined) | — | **Decide:** flake rate = flips / pairs over consecutive **clean** observations of an id at the **same `head_sha`**. Outcomes: pass vs fail-like (`fail`, `error`, `timeout`); skips are ignored. A failing-but-stable test is not flaky. Recorded in the component. |
| D6 | the estimate's fallback for an id with no cost row (step 0.4) | — | **Decide:** an unknown id contributes the table's **median top-level p95**, and an unknown group the median group overhead p95 (0 when the table is empty). `Estimate` reports `Unknown` / `UnknownGroups` counts so each consumer applies its own safe direction (the budget vs `selection_ratio_above`). |
| D7 | failure policy of the eligibility inputs (`deps.Scan`, registry, annotations) | — | **Decide (fail closed, never fail the run):** the rows are still written with `anchor=false`, `anchor_reason=eligibility-error:<input>:<detail>`. Only a ledger **write** failure returns a hook error (`RUN_HOOK_ERROR`, exit 3). |
| D8 | the `costs` line names, homed in *Cost ledger* (Dev 12) | the stub verb only | **Decide:** see Step 6. Recorded in the component. |
| D9 | `--update` "truncates" | a crash between a cost-file write and the truncation would double-fold on retry | **Decide:** each `<hostclass>.yaml` records `ledger_fold {bytes, sha256}`, the ledger prefix it already contains. A retry (and the in-memory read) skips that prefix for that host class, so retry converges. |
| D11 | the modified set and the registry paths share one root | `Record.Modified` is `git status --porcelain` output, which is relative to the **git toplevel**, not to `root` (= cwd). That makes the `gitx.ModifiedPaths` doc comment ("relative to Dir") wrong for a subdirectory `aitestmap/`. | **Adapt, fail closed:** the hook asks `git rev-parse --show-prefix` through a new read-only `gitx.Repo.Prefix`. A non-empty prefix marks every result `eligibility-error:root-not-toplevel`. Upstream defect recorded: the doc comment and M3.1's `.aitask-testmap/` filter under a subdirectory root. |
| D12 | "the test-side closure" | `Graph.Closure` follows only resolved `Deps`. A `source`/`exec` of an `exclude:`d, symlinked or deleted target lands in `Unresolved`, with no edge. `Closure` also excludes the start path. | **Adapt:** all checks iterate over {test file} ∪ closure. A non-empty `Unresolved` on any of those files, under a non-empty modified set, is `opaque:unresolved:<file>`. The runner script's own closure and its opaque or unresolved reasons join `runner-config`. *Measure:* during implementation, count this repo's bash tests with `Unresolved`. If most have it, report the number in the Final Notes, because anchors on dirty trees become rare (fail-safe direction). |
| D13 | eligibility is "decided at run time" | the hook runs after every invocation, so a long `--all` run gives the tree time to change before the hook reads the closure and annotations | **Adapt:** when the inputs are needed, take one HEAD + modified snapshot at hook start. Each invocation additionally requires `HEAD == head_end` and snapshot ⊆ `record.modified`, else `tree-changed`. *Why sufficient:* any modified file reachable at run time is reached through unmodified files, whose deps are unchanged, so it is still reachable at hook time and still blocks. |
| D10 | `predictions.yaml` "last 200" | M4.4 owns the entry schema | **Decide:** the envelope is `{contract, scored: [<mapping>]}`. An entry needs a non-empty `run_id`. Appending replaces a same-`run_id` entry (moving it to the end), then keeps the newest 200. |

**Differences in the parent's reality anchors this child relies on.** The
verb table still stubs `costs`, and the shared helpers and config keys are as
listed. One fact changed: M2.5 has since landed, so `reads` now reaches the
registry.

### Notes (step 0.5, sent post-approval with `/aitask-note`, hedged as tree claims)

- **t1855 (M4.1 / M4.3 / M4.4 / M4.5):**
  - the `cost` package API (`Load`, `LastPass`, `Flaky`, `Estimate`,
    `FullSuiteP95`, `AppendPrediction`);
  - the ledger fields `anchor` / `anchor_reason` / `clean`;
  - `last_pass.at` is RFC 3339 UTC, for M4.3's strictly-later stamp guard;
  - an id's anchors are per host class (M4.3 merges them);
  - M4.5 must name full runs `full-…` and run them `--all`;
  - the fallback counts (D6).
- **t1859_5 (M8.5):** `ReadPolicy` / `WritePolicy`, `PolicyPath`, the
  `CONTRACT_MISMATCH` refusal on read and write, and
  `FullSuiteP95(table) (ms, runID, ok)`.
- **t1857 (M6.5):** `costs --gate-timeout <gate>` prints
  `GATE_TIMEOUT_SUGGESTED:<gate>|<s>`. With no measured full run it prints
  `COSTS_NO_FULL_RUN:<hostclass>` on stderr and exits 2.

### Ownership (step 0.6)

**Owned:**

- `goengines/internal/testmap/cost/**` (new);
- `cmd/ait-testmap/costs.go` (new);
- the `costs` row in `verbs.go`.

**Named extensions:**

- M3.1's `runner/run.go`: two `RunReport` fields (D1);
- the hook registration in `cmd/ait-testmap/costs.go`;
- a read-only `gitx.Repo.Prefix(ctx)` (`rev-parse --show-prefix`) in
  `internal/gitx`, with its own test (D11).

**Shared docs:**

- new `goengines/README.md` Interfaces rows;
- proposal edits to the *Cost ledger* component and the *Where state lives*
  row (D4, D5, D8).

No other sibling is in flight on these files. t1854_2 and t1854_3 are `Ready`.

## Implementation steps

### 1. Named extension of M3.1 — `goengines/internal/testmap/runner/run.go`

- `RunReport` gains `Repo *Repository` and `All bool`, both tagged `json:"-"`.
- `Run` sets `Repo: repo, All: opts.All` when it builds the report, including
  the empty-selection early return.
- `runner/run_test.go` / `TestPostRunHookOrder`: assert that the hook sees a
  non-nil `Repo` and the right `All`.

### 2. Package `goengines/internal/testmap/cost/` — statistics (`stats.go`)

- **`Welford{N int64; Mean, M2 float64}`:** `Add(x)` and `Var()`.
- **`P2{Count int64; Q [5]float64; Pos [5]int64}`** (Jain–Chlamtac, p = 0.95):
  - while `Count < 5`, `Q[:Count]` holds the samples and the value is exact
    (nearest rank);
  - from 5 on, the markers are updated. The desired positions are always
    **computed** from `Count` after the increment
    (`np_i = init_i + (Count−5)·dn_i`), never accumulated. The same formula
    serves the live update and a reload, so a mid-stream round trip is
    exact. Only `Count`, `Q` and `Pos` are persisted.
  - `Value() float64`.
- **`Stat{N, MeanMS, M2, P2, P95MS, LastMS}`:** `Add(ms)` keeps `P95MS`
  rounded and `LastMS`.

### 3. Run-id surfaces (`surface.go`)

- `Surface(runID) string` returns `test|gate|full|review|other`, by prefix
  `test-` / `gate-` / `full-` / `review-`.
- `review` writes no rows at all.

### 4. Ledger subscriber (`ledger.go`, `eligibility.go`)

**`LedgerPath = ".aitask-testmap/ledger.jsonl"` and `LockPath = ".aitask-testmap/ledger.lock"`**

- Both are built on `runner.StateDir`.
- The lock is `platform.Lock`, shared by every append, `--update` and the
  in-memory read.

**`Hook(ctx, rep *runner.RunReport) error`** (the registered subscriber, name
`"cost-ledger"`)

1. If `Surface(rep.RunID) == "review"`, or the report has no invocations,
   return nil.
2. Host class = `registry.LoadConfig(rep.Root).HostClass()`, validated by
   `ValidHostClass`:
   - it must match `^[A-Za-z0-9][A-Za-z0-9._-]*$`;
   - its lowercase form must not be a **reserved store basename** —
     `policy` or `predictions` (`reservedStores`, compared case-insensitively
     because macOS file systems alias case).

   Invalid → return an error (`host-class:reserved|<hc>` or
   `host-class:invalid|<hc>`). A host class therefore never aliases the
   `policy.yaml` / `predictions.yaml` stores. The same validator guards
   `costs --host-class`, `Load` and `Update`.
3. `at = now().UTC().Format(time.RFC3339)`; `now` is a package var for tests.
4. Build the rows:
   - one **invocation row** per `Record`:
     `{row:"invocation", run_id, surface, host_class, at, invocation, group, runner, elapsed_ms, overhead_ms, units_reported, cause, refused, all}`.
     `refused` is persisted because a clean exit-75 refusal has an empty
     `cause` (`TestRunExitOutcomes`);
   - one **result row** per `Result`:
     `{row:"result", run_id, surface, host_class, at, invocation, group, id, parent?, status, duration_ms, head_sha (= head_start), clean, anchor, anchor_reason?}`;
   - one final **`run_end` row**:
     `{row:"run_end", run_id, host_class, at, invocations: <n>, results: <m>}`.
     It is the run's completion record (complete-run framing).
5. `Append(root, rows)`:
   - `MkdirAll` the state directory;
   - take the lock;
   - **then** open the ledger with `O_APPEND|O_CREATE`; opening after the lock
     means no stale offset survives a truncate;
   - if the file is non-empty and does not end in `\n`, write `\n` first
     (this heals a torn line);
   - write every row of the run in one `Write`: all invocation rows, then
     all result rows, then the `run_end` row;
   - unlock.

   Inside the package, flock is taken **once** per operation. `Update` uses
   unlocked internal readers and never calls `Load`/`Append`, because a
   second `platform.Lock` in the same process opens a new file description
   and would self-deadlock.
6. Return only an append error.

**`eligibility.go` — `clean(result, record, unit facts)`**

Evaluated in this order; the first failing check is the reason:

1. `cause != ""` → `cause:<cause>`.
2. `head_start == ""` → `head-unborn`; `head_start != head_end` →
   `head-moved`.
3. `len(modified) == 0` → clean (no inputs are needed: the lazy fast path).
4. **Root and tree** — the hook-level checks:
   - `root-not-toplevel` (D11);
   - `tree-changed` (D13).
5. **Opaque** → `opaque:<why>`, ineligible because the set is non-empty:
   - `child` — the result is a child row;
   - `suite` — `unit.Kind == "suite"` or the runner's `Describe.Full`;
   - `whole-run` — `Describe.FilterScope == whole_run`;
   - `no-facts` — the test file has no `deps` facts;
   - `closure-opaque:<file>` — a file of F = {test} ∪ closure has an opaque
     reason;
   - `unresolved:<file>` — a file of F has a non-empty `Unresolved` (D12).
6. **Disjointness** — `modified ∩` each of the following, first hit wins:
   - the test file → `test-file`;
   - closure files → `closure:<path>`;
   - covers → `covers:<src>`, by **string equality** (covers are literal
     paths; `[`/`{` are legal in them):
     - from the current annotations: the file-level block and the member
       block of `id.Base()`;
     - from registry edges: of `id.Base()` and of the file-level id;
   - helper reads → `reads:<glob>`: for each file of F, the current-annotation
     `Reads` ∪ `ScopedOf(reg).Reads` by helper path;
   - plugin reads → `plugin-reads:<glob>`: `Facts(f).Reads` for every file of
     F.

     For both reads checks, a glob that fails to parse counts as a **hit**
     (fail closed).
   - runner config → `runner-config:<path>`:
     - `aitestmap/runners.yaml` and `aitestmap/runners/**`;
     - a non-builtin script path, plus the closure of that script; an opaque
       or unresolved file in that closure is
       `runner-config:opaque:<file>`;
     - each whitespace token of `Entry.Command` that, cleaned and joined
       with `Cwd`, equals a modified path.

**Lazy inputs**

- `deps.Scan`, `registry.Load` and `annot.Source{}.Annotations` are computed
  once per hook call, **only** when some result reaches check 5.
- An input error marks every such result
  `eligibility-error:<input>:<detail>` (D7).

**Row fields**

- `anchor = clean && status == "pass"`.
- `anchor_reason` is the failing reason, or `status:<s>` for a clean
  non-pass.
- A reason carries at most one path, and only in the gitignored ledger, so no
  path list ever reaches a committed file.

### 5. Cost tables, fold and readers (`table.go`, `fold.go`)

**`aitestmap/costs/<hc>.yaml`**

- Header: `# Generated by ait-testmap costs --update. Do not edit.`
- Schema:
  `{contract, host_class, ledger_fold{bytes, sha256}, full_run{run_id, at}, ids: [IDRow], groups: [GroupRow]}`.
- `IDRow`: `{id, stat, last_at, last_pass{sha, at, run_id}?, flake{pairs, flips, last_sha, last_outcome}, full_top?}`.
- `GroupRow`: `{group, stat, full_run?}`.
- Ids and groups are sorted. The file is rendered with `registry.Render` and
  written with `registry.WriteFile`.
- The table is read with `testmap.CheckContract`. A newer contract →
  `*ContractMismatchError`.

**Fold rules, row by row in ledger order**

- **Timing:**
  - pass/fail results of an invocation without a cause feed the id's `Stat`;
  - invocations with no cause and not refused feed the group `overhead_ms`
    `Stat`;
  - child rows keep their own stats (Dev 13).
- **`last_at`:** every observation.
- **`last_pass`:** advances only when `anchor` is true, comparing `at` with
  `>=`. Folding runs in ledger order, so a second run in the same second
  still advances it.
- **Flake:** clean pass/fail-like observations update `pairs`/`flips` against
  `last_sha` / `last_outcome` (D5).
- **Complete-run framing.** The fold is per run, never per row:
  - rows are grouped by `run_id` in ledger order;
  - a run is folded **only when** its `run_end` row is present and well-formed,
    and the run has exactly `invocations` invocation rows and `results`
    result rows, every one well-formed with the same `run_id` and
    `host_class`;
  - otherwise the **whole run** is reported as
    `Skipped{Run: <id>, Reason: incomplete|count-mismatch|malformed}`. Its
    surviving rows feed no statistic, no anchor, no flake pair and no
    full-run baseline — the fail-safe direction;
  - a torn batch never reaches the table, at a row boundary or midway
    through a row, so a partial full run can never set `full_run`.
- **Full run** — processed per complete run:
  - A run qualifies only when all of these hold:
    - it is `surface:"full"` and `all:true`;
    - **every** invocation has an empty `cause` and `refused:false`;
    - at least one top-level result fed a `Stat`. An all-skip run measured
      nothing.

    Only a qualifying run sets `full_run` (`>=` on `at`).
  - **Membership is recorded independently of timing.** Every top-level
    result of the qualifying run stamps `full_top=<run_id>`, whatever its
    status, `skip` included. Every group of the run stamps
    `full_run=<run_id>`.
  - A skipped unit keeps its earlier measurements, so a known slow unit that
    skips this time still counts with its existing p95.
- **Refused invocations** feed neither group overhead nor a baseline.
- **`FullSuiteP95`** is defined in Step 6. A timed-out or refused full run
  never qualifies, so it never suggests 600 s for a suite that just overran.

**`Load(root, hc) (*Table, error)`**

- Reads the committed table, then folds the **pending** ledger rows for `hc`
  in memory.
- The read happens under the lock, and the `ledger_fold` prefix is skipped.
  An absent ledger or state directory reads the committed table alone,
  without locking, so a fresh clone works.
- `ledger_fold` is per clone inside a committed file. Two machines sharing one
  `host_class` therefore conflict on it at merge. That is accepted, because
  the marker must be atomic with the table; it is documented in the
  component.
- Readers therefore see a run's anchors before any `--update`.
- **`LoadAll(root)`** enumerates `costs/*.yaml`, but:
  - **excludes the reserved stores** `policy.yaml` / `predictions.yaml`
    (case-insensitive);
  - **discriminates** what remains: a host table must carry
    `host_class:` equal to its file stem, else `COSTS_ERROR:table|<path>: not a host table`
    (exit 3). A table is never merged under the wrong name;
  - adds any valid host class that has only pending ledger rows.

**`Update(root) (UpdateResult, error)`**

1. Take the lock and read the ledger.
2. A malformed line is reported as `Skipped{Line, Reason}`, never silently
   dropped and never folded. A torn trailing line is treated the same way.
3. Per host class, in sorted order:
   - load the table;
   - skip the already-folded prefix;
   - fold the new rows;
   - set `ledger_fold` to the folded prefix (`bytes`, `sha256`);
   - `WriteFile` it.
4. Then truncate the ledger to 0 and unlock.
5. An empty ledger writes nothing, so a re-run is byte-identical.
6. A write error stops the update **before** the truncation. The prefix
   markers make the retry converge.

**Accessors**

- `(*Table).LastPass(id)`.
- `(*Table).FlakeRate(id) (rate float64, pairs int64)`.
- `(*Table).Flaky(id, threshold) bool` — rate > threshold with ≥ 1 pair.
- `(*Table).Stat(id)`.

### 6. Estimate, full-suite p95, gate timeout (`estimate.go`)

**`Estimate(t *Table, invs []*runner.Invocation, kindOf func(registry.ID) string) Result`**

- `Result` is `{TotalMS, OverheadMS int64, ByKind map[string]int64, Unknown, UnknownGroups int}`.
- `invs` comes from `runner.Group` with the caller's wave input, and its units
  are top-level ids.
- `TotalMS` = Σ `group.p95` + Σ `id.p95`. The D6 fallback applies to unknown
  ids and groups.

**`FullSuiteP95(t) FullSuite{MS int64, RunID string, Unmeasured int, OK bool}`**

- `OK=false` only when no full run qualified.
- `MS` = Σ `p95` of the groups with `full_run == RunID`, plus Σ over the
  member ids (`full_top == RunID`) of:
  - the id's existing `p95` when `N > 0`;
  - else the D6 fallback, counted in `Unmeasured` (for example, a unit that
    has only ever skipped).
- These are top-level only, so the result is disjoint.
- The `costs` verb prints `Unmeasured`. `--gate-timeout` uses `MS` as is
  (fallback included) and prints `COSTS_UNMEASURED:<hc>|<n>` on stderr when
  `n > 0`.

**`GateTimeoutS(p95ms) int64`** = `max(600, ceil(3·p95ms/1000))`.

### 7. Stores (`predictions.go`, `policy.go`)

**`PredictionsPath = "aitestmap/costs/predictions.yaml"`**

- `ReadPredictions(root)` and `AppendPrediction(root, entry map[string]any)`.
- An entry without a non-empty `run_id` is refused.
- A same-`run_id` entry is replaced, then the newest 200 are kept.
- The write carries `contract: testmap.Contract` and is skipped when unchanged.

**`PolicyPath = "aitestmap/costs/policy.yaml"`**

- The struct is
  `Policy{Contract, LastFullRun *FullRunRef{RunID, At, Task, SHA}, SelectedSinceFull int, ApprovedBy *Approval{Who, At, Mode, Statement}, Extra map[string]any `yaml:",inline"`}`.
- `ReadPolicy(root) (Policy, found bool, err)` checks the contract first.
- `WritePolicy(root, p) (changed bool, err)` re-reads the on-disk contract and
  refuses a newer one with `CONTRACT_MISMATCH`. It writes `contract: 1`,
  keeps the extra keys and validates `selected_since_full ≥ 0`.
- No verb is added: M8.5 writes the file.

### 8. Verb `costs` — `cmd/ait-testmap/costs.go` + the `verbs.go` row

- `func init() { runner.RegisterPostRunHook(cost.HookName, cost.Hook) }` is
  the production wiring.
  - It lives in one place, `costs.go`, which carries a comment: M4.4's
    automatic `score` hook must register in the same `init`, after this one.
    That keeps the order explicit rather than dependent on file names.
  - This goes in the t1855 note.
- The exit contract is `costsExits` = 0, 2, 3, 64.

**`costs [--host-class <hc>] [--json] [<id>...]`**

- One `COST:<id>|<n>|<mean_ms>|<p95_ms>|<last_ms>|<flake_rate>|<pairs>|<last_pass_sha>|<last_pass_at>|<last_pass_run>` line per id.
- Then `GROUP:<key>|<n>|<p95_ms>`.
- Then `FULL_SUITE:<hc>|<run_id>|<p95_ms>|<unmeasured>`, when a full run exists.
- Then `COSTS:<hc>|<ids>|<groups>|<pending rows>`.

**`costs --update [--json]`**

- `LEDGER_SKIPPED:<line>|<reason>` for a malformed ledger line;
- `LEDGER_RUN_SKIPPED:<run_id>|<incomplete|count-mismatch|malformed>` for a
  run without complete framing;
- `COSTS_FOLDED:<hc>|<rows>`;
- `WROTE:<path>`;
- `LEDGER_TRUNCATED:<rows>`.

**`costs --gate-timeout <gate> [--host-class <hc>]`**

- `GATE_TIMEOUT_SUGGESTED:<gate>|<s>`, exit 0.
- With no full run: `COSTS_NO_FULL_RUN:<hc>` on stderr, exit 2.

**Errors**

- `TESTMAP_ABSENT:` → 2.
- `CONTRACT_MISMATCH:` → 3.
- `COSTS_ERROR:<what>|<detail>` → 3: a bad host class, an unreadable
  ledger or table.

### 9. Docs

- **`goengines/README.md` Interfaces rows:**
  - the ledger and subscriber;
  - anchor eligibility;
  - the cost tables and fold;
  - the estimate and full-suite p95;
  - the `costs` verb;
  - the `predictions.yaml` and `policy.yaml` helpers.

  Each row cites the pinning tests below.
- **Proposal:**
  - the *Where state lives* runs/ledger row (D4);
  - the *Cost ledger* component: the flake definition (D5), the fallback
    (D6), the line names (D8), the eligibility-failure policy (D7) and the
    `ledger_fold` marker (D9);
  - stated in current-state form.

### Post-phase (risk mitigations)

1. **[measure_hook_cost_and_unresolved_rate]** After the implementation is
   green, measure on this repository, from the repo root, with the new
   binary (`ait engine build`, `AIT_ENGINE=dev`):
   - **Hook latency:** dirty one unrelated file, then run one bash test unit
     through `run --run-id test-measure <id>`. Record the hook's wall time,
     taken from timing the run with and without the hook. Use a test-only env
     switch, or compare against a clean-tree run, which takes the lazy fast
     path.
   - **Unresolved rate:** count the bash test files whose {test} ∪ closure
     carries a non-empty `Unresolved`, against all bash test files, using a
     small Go test helper or a `deps.Scan` one-off in a `_test.go` run with
     `-run`.
   - **Report:** both numbers go in the Final Notes. If the unresolved share
     is above 50 %, say explicitly that dirty-tree anchors are effectively
     disabled on this repo, and name it as input for
     `testmap_closure_implicit_inputs_audit`.
   - **Cleanup:** remove the dirty file and the run's ledger rows afterwards.
     Never commit them.

## Verification

Go tests live in `internal/testmap/cost/*_test.go`, plus `cmd/ait-testmap/costs_test.go`.

**Statistics**

- `TestWelfordMatchesDirect`: Welford's mean/variance equal a direct two-pass
  computation.
- `TestP2WithinTolerance`: P² p95 lands within 5 % of the exact quantile on
  fixed-seed uniform, exponential and bimodal samples. The value is exact for
  n < 5, and a persisted state survives a round trip mid-stream.

**Ledger, command level** — `TestCostsLedgerThroughRun` (cmd):

- the real `run --all --run-id test-1` on the `runnerRepo` fixture appends 2
  result rows + 1 invocation row through the registered hook;
- `costs --update` writes `aitestmap/costs/<hc>.yaml` and truncates the
  ledger;
- a second `--update` writes nothing and leaves the bytes identical;
- `review-1` appends nothing.

**Concurrent append** — `TestConcurrentAppendDuringUpdate` (Linux):

- `Update` pauses at a test seam while holding the lock;
- a re-exec'd helper process calls `Append`;
- the test **proves the helper is waiting** by polling `/proc/locks` for a
  `-> FLOCK` waiter on the lock file's inode, with a bounded deadline. Only
  then does it release;
- after the release, the helper's row is in the ledger and the earlier rows
  are folded.
- The paused test process itself never calls `Load`/`Append`.
- Red control: the append lock is bypassed (a test-only switch), and the test
  waits for the helper to exit *before* releasing. The row must be lost.
- Every helper process gets a bounded `exec.CommandContext` deadline.

**Eligibility, red-proved** — `TestEligibility*`, run through the real
`runner.Run` on a fixture repo, asserting the **exact reason**:

- *the fixture:*
  - `tests/test_a.sh` sources `tests/lib/helper.sh`;
  - the helper declares `testmap:reads tests/data/*.txt`;
  - the test covers `src/a.sh`;
  - a scanner plugin declares reads `fixtures/*.json` for the test.
- *rejections, one per case:*
  - a weakened, uncommitted test → `test-file`;
  - a dirty helper → `closure:tests/lib/helper.sh`;
  - a dirty covered source → `covers:src/a.sh`;
  - **only** `tests/data/x.txt` dirty → `reads:tests/data/*.txt`;
  - **only** `fixtures/y.json` dirty → `plugin-reads:fixtures/*.json`;
  - a reconciliation cause → `cause:reconciliation`;
  - the runner commits during the run → `head-moved`;
  - a `unit: suite` runner, or a child row of a `full: true` runner, with
    one unrelated dirty file → `opaque:suite` / `opaque:child`;
  - a dirty `aitestmap/runners/shell.sh` → `runner-config:…`.
- *the positive control:* unrelated dirty files leave a per-unit pass
  eligible.
- An unscanned repo (no `scan --apply`) still rejects the dirty covered
  source (D2).
- More rejections, each with its exact reason:
  - a test that sources an `exclude:`d dirty helper →
    `opaque:unresolved:tests/test_a.sh` (D12);
  - a reads glob attached to the **test file** by the plugin is honoured
    (D12);
  - a script runner outside `aitestmap/runners/` whose sourced lib is dirty
    → `runner-config:…`;
  - the tree is edited between the run and the hook (a test seam) →
    `tree-changed` (D13);
  - `aitestmap/` in a subdirectory → `eligibility-error:root-not-toplevel`
    (D11);
  - a covered source named `src/[id].ts` that is dirty →
    `covers:src/[id].ts`.
- Fold tests:
  - a full run with a timed-out invocation does not set `full_run`;
  - a refused full run (exit 75, empty cause) contributes no overhead sample
    and sets no baseline. This is a ledger round trip through
    `Append` → `Update`;
  - an all-skip full run sets no baseline;
  - a known slow unit (an earlier p95 of 50 s) that **skips** in the newest
    full run still counts 50 s, while an unknown skipped unit counts the
    fallback with `Unmeasured=1`;
  - truncation **at a row boundary** before `run_end`, and truncation
    **midway through a result row**: the whole run is reported skipped, and
    no `full_run`, stat or anchor comes from it. The next complete run folds
    normally, with the torn tail healed;
  - two runs within the same second both advance `last_pass`;
  - `costs` on a clone without `.aitask-testmap/` reads the committed table
    (exit 0).
- An eligibility input error writes rows with
  `anchor_reason=eligibility-error:…` and the run exit is unchanged (D7).

**Mutant red-proofs, recorded in the Final Notes**

- Each check (test file, closure, covers, helper reads, plugin reads, runner
  config, opaque, head, cause, the annotation union) is disabled in turn.
- Each mutant must fail its own test. Mutants are applied in isolation and
  restored byte-identical.

**No path list in a committed file**

- After folding the dirty-tree runs, no path from `modified` appears in
  `<hc>.yaml`. The only paths in it are the ids.

**Disjoint accounting** — `TestFullSuiteDisjoint`:

- one invocation: `elapsed 105 s`, a suite parent of 100 s, children of 40 s
  and 60 s;
- the full-suite p95 is 105 s, not 205 s;
- the children's stats (40 s, 60 s) and their flake/anchor fields are
  recorded;
- `GateTimeoutS` = 600, and 1200 for a 400 s suite.

**Estimate** — `TestEstimate`:

- the per-kind sum over top-level ids plus overhead;
- the fallback counts for unknown ids and groups.

**Smaller checks**

- `TestFlakeRate`: flips at the same sha only; a stable failure is not
  flaky; the threshold is applied.
- `TestPredictionsKeep200`: replace-by-`run_id`, the 200 cap, and a missing
  `run_id` refused.
- `TestSurfaces`: the four prefixes plus `other`.
- `TestReservedHostClasses`: `policy`, `Predictions` and `POLICY` are refused
  by the hook, `--host-class` and `Load`.
- `TestLoadAllDiscriminates`: with `ci.yaml`, `policy.yaml` and
  `predictions.yaml` present, `LoadAll` returns exactly `ci`. A `rogue.yaml`
  whose `host_class` differs from its stem is refused.
- `TestPolicyRoundTrip`: extras are kept; a newer `contract:` →
  `CONTRACT_MISMATCH` on read and on write.
- `TestLedgerTornLine`: a torn line is healed on append and reported as
  skipped by update.
- `TestUpdateRetryConverges`: a write failure after one host class does not
  double-fold on retry.
- `TestCostsVerbLines`: `costs`, `--gate-timeout`, `COSTS_NO_FULL_RUN` exit 2,
  usage 64.

**Suites**

- `ait engine test` (go vet + go test) is green.
- `goengines/guards_test.go` (the Invariants 4–5 tripwire) passes.
- `ci/preflight.sh` passes, including the runner isolation tripwire after the
  `run.go` change.

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9: archival, on the
current branch, with no merge.

## Risk

### Code-health risk: medium
- **Every `run` gains a subscriber.** A dirty tree triggers a `deps.Scan`
  plus an annotation and registry read, which adds latency and new failure
  surface to a load-bearing verb. · severity: medium (bounded: lazy inputs;
  input errors fail closed into the rows, never into the run exit; residual
  latency measured by the inline post-phase) · → mitigation: inline post-phase
  measure_hook_cost_and_unresolved_rate
- **The per-clone `ledger_fold` marker sits in a committed file**, so machines
  sharing a `host_class` conflict on it at merge. · severity: low (documented,
  accepted) · → mitigation: none
- **Named extension of M3.1's `RunReport`**: two `json:"-"` fields; the `--json`
  shape is unchanged. · severity: low · → mitigation: none

### Goal-achievement risk: medium
- **Anchor eligibility can only be as sound as M2.3's closure.** Implicit
  runner inputs that no scanner models (pytest `conftest.py` ancestors,
  Gradle build files, Go package siblings outside the facts) are not in the
  disjointness set, so a dirty one can still anchor. This sits alongside the
  stated edit-and-revert residual. · severity: medium · → mitigation:
  testmap_closure_implicit_inputs_audit
- **D12's unresolved-ref rule may make dirty-tree anchors rare**, which means
  fewer `EVIDENCED` rows and less self-healing (the fail-safe direction, but
  it erodes the feature's value). · severity: medium (residual — quantified by
  the inline post-phase; any remedy is fed to the audit task) · → mitigation:
  inline post-phase measure_hook_cost_and_unresolved_rate

### Planned mitigations
- timing: after | name: testmap_closure_implicit_inputs_audit | type: enhancement | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: goal-achievement — implicit runner inputs missing from the eligibility closure | desc: Audit pytest/go-test/gradle-class/bash-file implicit inputs (conftest.py ancestors, build files, package siblings) and add them to M3.4 anchor eligibility (or mark opaque) with red-proved fixtures
- timing: post-phase | name: measure_hook_cost_and_unresolved_rate | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health hook latency; goal-achievement unresolved-ref anchor rarity | desc: Measure the ledger hook's wall time on a dirty tree and the share of bash tests with Unresolved closure refs; report both in Final Notes

## Post-Review Changes

### Change Request 1 (2026-10-20 08:10)
- **Requested by user:** three confirmed defects:
  - (1) `Load` read the host table before taking the ledger lock, so a concurrent `Update` could hide a folded run from both views. `LoadAll` discovery had the same race.
  - (2) `AppendPrediction` did an unlocked read-modify-write, so a concurrent scorer's run could be lost.
  - (3) The unmeasured-id fallback median included child-only ids, contradicting D6 ("median top-level p95").
- **Changes made:**
  - (1) `withLedger` holds the ledger lock across the table read(s) and the ledger read. `Load` → `loadFrom`; `LoadAll` discovers and reads under the same hold. With no ledger file it takes no lock and creates nothing.
  - (2) `lockStores` (`<git-dir>/ait-testmap/costs.lock`, the adoption tables' convention) covers the whole read/replace/cap/write. The store tests now use a git fixture root.
  - (3) `IDRow.TopN` counts timed top-level observations, and `medians()` uses only ids with `TopN > 0`.
- **New tests:**
  - `TestLoadConsistentWithConcurrentUpdate` (Load and LoadAll; the reader is proved blocked through /proc/locks);
  - `TestAppendPredictionInterleaving` (barrier at the seam after the read; the second writer is proved blocked);
  - `TestFallbackMedianIgnoresChildOnlyIDs` (100000 ms parent, 1 ms children, unmeasured skip → 200000; estimate fallback 100000).
- **Red proofs (isolated, restored byte-identical):** each fails its own test:
  - Load pre-reading the table;
  - `withLedger` without the lock;
  - `AppendPrediction` without the stores lock;
  - the median over `Stat.N` instead of `TopN`.
- **Files affected:** `goengines/internal/testmap/cost/{table.go,stores.go,estimate.go,concurrency_test.go,fold_test.go}`, `goengines/README.md`, `aidocs/testing_engine/n014_explorer_006_proposal.md`

### Change Request 2 (2026-10-20 08:25)
- **Requested by user:** `parseTable` seeded `HostClass` from the file name before decoding, so an existing table with no `host_class:` passed the identity check (`LoadAll` accepted `rogue.yaml` = `contract: 1` + an unrelated key).
- **Changes made:**
  - An existing file is now decoded into a table with an empty identity. It must state a `host_class` equal to its file stem.
  - An absent file is still an empty table.
  - Coverage added to `TestLoadAllDiscriminates`: missing identity is refused by both `LoadAll` and `Load`, and an absent table loads empty.
  - Red proof: accepting an empty `host_class` fails the test ("identity-less table accepted by LoadAll"). The mutant was isolated and restored byte-identical.
- **Files affected:** `goengines/internal/testmap/cost/{table.go,fold_test.go}`, `goengines/README.md`

## Final Implementation Notes

- **Actual work done:**
  - **New package `goengines/internal/testmap/cost/`:**
    - `stats.go`: Welford, plus P² p95 with desired positions derived from Count;
    - `surface.go`: run-id surfaces, `ValidHostClass` with the reserved `policy`/`predictions`, `cost.Error` → `COSTS_ERROR`;
    - `ledger.go`: row types, `Batch`, the locked `Append` with `O_APPEND` after the lock and a torn-line heal, and `parseLedger` with `run_end` complete-run framing;
    - `eligibility.go`: the run-time judge with lazy inputs;
    - `hook.go`: `Hook`/`Rows`;
    - `table.go`: host tables, the fold, `ledger_fold`, `Load`/`LoadAll` under one lock hold, `Update`;
    - `estimate.go`: `Estimate`, `FullSuiteP95`, `GateTimeoutS`;
    - `stores.go`: predictions under `<git-dir>/ait-testmap/costs.lock`, and policy.
  - **Verb `costs`** (`cmd/ait-testmap/costs.go`, the `verbs.go` row). The hook is registered in one ordered `init` there.
  - **Named extensions:**
    - `runner.RunReport.Repo`/`All`;
    - `gitx.Repo.Prefix`, plus a corrected `ModifiedPaths` doc comment.
  - **Docs:** README Interfaces rows; the proposal's *Where state lives* row and *Cost ledger* component.
- **Deviations from plan:**
  - Plan D2–D13 were applied as approved, and the four plan-review concerns (reserved names, run framing, skipped members, persisted `refused`) were folded in before implementation.
  - **Eligibility order:** kind-opaque checks (child/suite/whole-run) run before the lazy input load, so suite-only runs never trigger `deps.Scan`.
  - **`refused`** is an explicit early rejection reason.
  - **`top_n`** was added to id rows (post-review change 1).
  - **Host-table identity** must be explicit (post-review change 2).
  - **Store tests** need a git fixture root, because the stores lock lives in the git directory.
- **Issues encountered:**
  - The fixture `chmod` after commit dirtied the tree. The fixture now sets the mode before committing.
  - Run-id reuse across `judged()` calls (`run-exists`) was fixed with a counter.
  - Three first-round mutants were invalid (compile errors from unused loop variables) and were re-run as valid ones.
  - One test literal was mis-escaped by a scripted edit; it was caught by vet before any mutant was counted.
- **Key decisions:**
  - **D7:** an eligibility input that cannot be read becomes `eligibility-error:` in the rows and never changes the run's exit; only a failed ledger write is a hook error.
  - **D12 kept strict, by user decision:** a narrowing to "only when a modified path is outside the scan universe" was proposed and rejected. Counterexample: an unchanged excluded helper reached through an unresolved ref can itself read a dirty in-universe file.
  - **D6:** the fallback median is over top-level-timed ids only.
- **Measurement (post-phase `measure_hook_cost_and_unresolved_rate`):** taken on this repo with a throwaway test, since the repo has no `aitestmap/` yet so `run` cannot execute here.
  - **Hook inputs (dirty tree only):** git snapshot ≈ 9 ms; `deps.Scan` ≈ 737 ms cold / 112 ms warm; annotations ≈ 145 ms. Total ≈ 0.9 s cold / 0.27 s warm.
  - **Unresolved rate:** 400 / 448 bash tests (89 %) have an unresolved `source`/`exec` ref in {test} ∪ closure, mostly fixture paths created at test time (e.g. `aitasks/t10_alpha.md`, `.codex/`, `.opencode/skills/...`). 0 are closure-opaque, 0 lack facts.
  - **Consequence:** on this repo dirty-tree anchors are **effectively disabled**: only a clean tree anchors. This is input for `testmap_closure_implicit_inputs_audit`, which must also carry the excluded-helper counterexample as a test before any relaxing.
- **Red proofs:** every mutant was isolated and restored byte-identical (`cmp`), and each failed its own test.
  - **Eligibility checks (15):** test-file, closure, covers, annotation-union, registry-union, helper-reads, plugin-reads, runner-config, opaque/unresolved, cause, head, suite, child, tree-changed, root.
  - **Fold:**
    - framing count, incomplete run, refused overhead;
    - full-run membership, fold mark, child-only qualification. The last needed the new `child-only-timed` case: its first mutant was green.
  - **Review fixes:**
    - Load pre-reading the table;
    - unlocked `withLedger`;
    - unlocked predictions;
    - child-inclusive median;
    - identity-less table.
  - **Concurrency:** `TestConcurrentAppendDuringUpdate` carries its own unlocked red control.
- **Upstream defects identified:**
  - `goengines/internal/testmap/runner/invoke.go:200` — `provenance()` filters `.aitask-testmap/` from `git status` paths, which are top-level-relative. With `aitestmap/` in a subdirectory (root ≠ git top level) the filter misses `sub/.aitask-testmap/...`, and the record's `modified` set is top-level-relative while every other path is root-relative. M3.4 fails closed on it (`eligibility-error:root-not-toplevel`).
- **Notes for sibling tasks:**
  - **Hook wiring:** subscribers register in the single ordered `init` in `cmd/ait-testmap/costs.go`. M4.4's `score` goes after `cost-ledger`.
  - **For M4.x readers:**
    - `cost.Load(root, hc)` / `LoadAll(root)` fold pending ledger runs in memory;
    - `LastPass(id)` is per host class (merge across `LoadAll`);
    - `Flaky(id, cfg.FlakeThreshold)` excludes flaky ids;
    - `last_pass.at` is RFC 3339 UTC;
    - `Estimate(t, runner.Group(...), kindOf)` reports `Unknown`/`UnknownGroups`.
  - **For M4.5:** a full run must use `--run-id full-…` **and** `--all`, or it never becomes the baseline.
  - **For M8.5:** `ReadPolicy`/`WritePolicy`, plus `FullSuiteP95(t).MS`/`.OK`.
  - **For M6.5:** `costs --gate-timeout <gate>` exits 2 with `COSTS_NO_FULL_RUN:<hc>` until a full run qualifies.
  - **Test fixtures:** `eligibility_test.go`'s `eligRepo` is a full real-input fixture (helper reads, scanner plugin, hand edge, runner script). Commit file modes before any run, or the tree is dirty.
