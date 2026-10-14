---
Task: t1854_1_m3_1_runner_contract_and_repository.md
Parent Task: aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md
Sibling Tasks: aitasks/t1854/t1854_2_*.md, aitasks/t1854/t1854_3_*.md, aitasks/t1854/t1854_4_*.md
Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-14 08:27
---

# Plan: t1854_1 — M3.1 Runner contract and repository

## Context

Parent goal: M3 — Runners, scheduling and cost. This child, **M3.1** (wave
B), delivers four things:

- the runner interface every builtin and project script implements;
- the engine `run` verb;
- the canonical grouping function;
- the seams that M3.2, M3.3, M3.4, M2.1 (`scan` / `check`) and M2.4 plug
  into.

Its providers are M1.2 (`t1852_2`), M2.1 (`t1853_1`) and M2.2 (`t1853_2`).
All three are landed and archived.

Today `scan` and `check` exit 3 with `INPUT_UNAVAILABLE:lister`, and `run` is
a stub (exit 64). After this task:

- `scan` / `check` run over the real runner repository;
- `ait-testmap run` executes units through `describe` / `list` /
  `run --manifest` runners;
- `run` records the engine's own provenance per invocation;
- `run` hands its results to an ordered post-run hook.

**Automation-first (user directive, 2026-10-11).** Human review belonged to
an older design. No verb or seam shipped here makes a human action a
precondition of any path. A human-only step met in the proposal is reported
to its owning parent with a note, never encoded here. None was found for
M3.1: the "runners.yaml confirmed per runner" step is M6's.

Proposal: `aidocs/testing_engine/n014_explorer_006_proposal.md` (M3 cut fixed
in `6a3a81efc`). Parent plan: `aiplans/p1854_testmap_m3_runners_scheduling_and_cost.md`
(Deviations 1, 2, 3, 7, 8, 9, 10, 11, 12, 13).

## Step 0 — Reality check (EXECUTED 2026-10-13, main @ 6a3a81efc)

### 0.1 Proposal re-read

Read the following:

- the Module Map row M3.1;
- the component *Runner contract and repository (M3.1)*;
- the three M3.1 rows of *Cross-module interfaces*;
- *Process map*, *Where state lives* ("runs, ledger, predictions") and
  *Line-protocol index* (the M3 row);
- *Run Surface → Output and exit contract*;
- *Assumptions → Variants, broad tests and runners*;
- `tradeoff_batch_misreport_risk` and `tradeoff_whole_run_filter_soundness`;
- *Invariants*;
- the M2.2 grammar (`runner <name>`, `needs <resource>…`, `batch yes|no`).

### 0.2 Providers as they exist

| provider | landed by | what is really there |
|---|---|---|
| M1.2 `lineproto` | t1852_2 `33012bff7` | `ExitOK 0/ExitFail 1/ExitNothingRan 2/ExitFramework 3/ExitUsage 64/ExitRefused 75`; `Enforce(verb, contract, code, stderr)` maps an out-of-contract code to 3 with `EXIT_CONTRACT_VIOLATION:`; `Format` refuses `\|` and line breaks |
| M1.2 `platform` | t1852_2 | `Lock(path)` flock (unix), `Workers`, `NewGroup` (cap 8), `CacheRoot` |
| M1.2 `gitx` | t1852_2, extended by t1853_2 (`lsfiles.go`) | `Repo.Run/RunEnv`, `RevParse`, `IsAncestor`, `ObjectFormat`, `ListFiles` (any git stderr is an error), `LsTree`, `BlobDigest`, scrubbed `Env`. **There is no status / modified-path helper.** |
| M1.2 `fixture` | t1852_2 | `New`, `Write`, `Remove`, `Commit`, `CommitMessage`, `History`, `Head`, `Run`, with isolated git config |
| M1.2 verb table | t1852_2 | `verbs.go`: `stub("run")`, `stub("runner")`. `TestStubsExit64` lists `run` as a stub, and `TestVerbTableMatchesProposal` pins the table |
| M2.1 lister seam | t1853_1 `0d04347ab` | `registry.UnitLister{List(ctx, root) ([]Listing, error)}`, `Listing{Runner, Bound, ArtifactGlobs, Units []ListedUnit{ID, Kind, Lowering, Artifact}}`, `InputError` → `INPUT_ERROR:lister\|<detail>` (exit 3), `readInputs` validates Bound paths, globs and ids. `testmapInputs()` sets only `Annotations: annot.Source{}`. `TestScanCheckInputUnavailable` pins the production `INPUT_UNAVAILABLE:lister` |
| M2.1 config | t1853_1 | `registry.LoadConfig`, `Config.Excluded`, `registry.Dir = "aitestmap"`, `CheckPath`, `ParseID`, `ID.Base/Valid/String` |
| M2.2 annotations | t1853_2 `f096db065` | `annot.Unit` carries `Runner *KeyVal`, `Batch *KeyVal` (yes\|no), `Needs []KeyVal`. `toRegistry` copies **only** `Member`, `Line` and `Covers` into `registry.UnitAnnotation` |
| M2.3 deps | t1853_3 `2c04a9639` | The `plugin.go` exec pattern: `Setpgid`, group kill on `Cancel`, `WaitDelay`, and a `capWriter` that bounds stdout and stderr. Not consumed; mirrored |
| M2.5 | t1853_5 | `Ready`, not landed. No kind data reaches the registry, so the wave class is always `unit` today |
| M2.4 | t1853_4 | `Ready`; `depends: [t1853_1, t1854_1]` already set |
| invariants tripwire | `goengines/guards_test.go` | Forbids `aitasks/`, `aiplans/`, `.aitask-data`, `CLAUDE.md`, `gates.yaml`, `project_config.yaml` and `aitask_*.sh` literals. `.aitask-testmap` is allowed |

### 0.3 Differences and decisions

| # | proposal says | coarse plan says | repository has | decision |
|---|---|---|---|---|
| D1 | "per-test override" of bindings | same | the override is the grammar's `testmap:runner <name>`, but `toRegistry` drops it | **Adapt.** Add `Runner` next to `Batch` / `Needs` in `registry.UnitAnnotation` (same named extension of M2.2). **Revise the proposal**: the M3.1 row and the component say "`runner` / `batch` / `needs`". |
| D2 | modified-path set "staged/unstaged, deletions, untracked non-ignored" | same | `gitx` has no status reader | **Adapt.** Add read-only `gitx/status.go` (`ModifiedPaths`). Precedent: t1853_2 added `lsfiles.go` to the shared `gitx`. It uses `git --no-optional-locks status --porcelain=v1 -z --untracked-files=all`, so it never takes `index.lock` or refreshes the index. A rename contributes both paths. Any stderr is an error, as in `ListFiles`. |
| D3 | wire formats of `describe`, `list`, the manifest, `results.jsonl`, `runner.json`, `runners.yaml` and the record | "decided at the Reality check" | none exist | **Decide here** (*Contract shapes* below). Each shape is pinned by a test and by a row in `goengines/README.md` → Interfaces. |
| D4 | `group_by:` names the grouping | same | the `list` TSV has no group column | **Decide.** `group_by:` is computed from the id. The values are `none` (default), `file`, `dir`, and `regex:<re>`. `regex:` takes the first submatch on the id's path; no match is a malformed `list`. Gradle module grouping is `regex:^(.*?)/src/`. |
| D5 | "per-unit timeouts" | same | no source for the value, and no rule for who enforces it inside a batch | **Decide, then revise the proposal.** Every unit gets a guaranteed individual bound through *Timeout model* (below). A runner declares in `describe` how it bounds units: `timeouts: per_unit \| batch \| none`. The engine enforces each mode, keeps a separate `max_invocation_s` ceiling, and records a start-versus-result distinction. A unit that timed out is never confused with a unit that never started. |
| D6 | thinking_app's `runners.yaml` carries `unit: suite, full: true, children: …` | — | — | **Decide.** A `runners.yaml` entry may override any describe key. The effective describe is the runner's own `describe` with the yaml keys over it. The generic `suite` builtin cannot know `full` / `children` itself. |
| D7 | the `list` TSV `<kind>` column | — | `ListedUnit.Kind` is a free string | **Decide.** It is the **granularity** vocabulary `file\|class\|method\|variant\|suite`, the same set as `describe`'s `unit`. Test kinds (`unit\|integration\|…`) are M2.5's annotations, never `list`'s. A `variant` row must carry an `@variant`. |
| D8 | absent `runners.yaml` | — | — | **Decide, fail-closed.** The lister returns `INPUT_ERROR:lister\|aitestmap/runners.yaml: absent` (exit 3), so `check` never passes over zero runners (Invariant 1). |
| D9 | hook failures | — | — | **Decide.** Every subscriber runs once, in order, even after another failed. Each failure prints `RUN_HOOK_ERROR:<name>\|<detail>` and the run exits 3 (framework). Results are printed first. |
| D10 | run ids | the prefixes are M3.4's | — | **Decide.** `run --run-id <id>` (`[A-Za-z0-9._-]+`), else `$AIT_GATE_RUN_ID`, else `run-<UTC yyyymmddThhmmssZ>-<pid>`. An existing run directory is refused (exit 3). M3.4 adds its prefixes later. |
| D11 | the engine's own output in the modified set | — | `.aitask-testmap/` is gitignored by setup, but not in a fixture | **Adapt.** `ModifiedPaths` callers drop the `.aitask-testmap/` prefix explicitly, so the engine's own writes never block an anchor. |
| D12 | builtins are `ait-testmap runner <name>` | — | the `runner` verb is a stub (M3.2) | **Adapt.** A `builtin:` runner execs `<self> runner <name> <verb>`. `runner.RegisterBuiltin(name)` is the registration seam M3.2 fills. An unregistered builtin is refused (`RUNNER_UNRESOLVED`, exit 3). `runner.SelfExe` is a var so tests can stand in for the binary. |
| D13 | `subsumed_by: <suite>` lets `run --all` "execute the suite once and never the subsumed runner" | same | — | **Decide, fail-closed.** Validation alone ("names a `full: true` runner") would accept a self-reference or a mutual pair, and `--all` would then silently drop both runners' tests behind a suite that never runs, so an unrelated passing runner yields a green, incomplete run. Load therefore refuses self-references and cycles and requires every chain to end at a `full: true` terminal. `run --all` additionally refuses (exit 3, before anything runs) when an omitted runner's terminal suite contributes no selected unit. |
| D14 | — | the first draft reconciled before recognising refusal, and validated rows only on a normal exit | — | **Decide.** There is one *Invocation outcome table*, applied after row validation and before any unreported-unit synthesis. Row validation runs on both the normal and the kill path. Protocol errors and a timeout are both preserved (`protocol_errors`, `timed_out`), and the primary `cause` is picked by precedence. All-skipped is exit 2 (no pass evidence). |

No cut error (a file with two owners, or a wave contradiction) was found.
There are two proposal edits, both in M3.1's own row and component:

- D1, the `runner` field;
- D5, one paragraph stating the timeout model, which replaces "per-unit
  timeouts".

Interface shapes go into `goengines/README.md` → Interfaces.

### Timeout model (D5)

A runner's `describe` declares `timeouts:`. The value decides who
guarantees each unit's bound and how units may be grouped.

| `timeouts:` | who bounds each unit | batching | engine deadline per invocation | an unreported unit after the engine kills the invocation |
|---|---|---|---|---|
| `per_unit` | the **runner**. It runs each unit under the manifest's `timeout_s`, kills that unit's process tree on expiry, reports `status: timeout` and moves to the next unit. It writes a `{"id","event":"start"}` row before each unit | allowed | `max_invocation_s` | start row, no result → `timeout`; no start row → `not_started` |
| `batch` | **nobody per unit**. Only an explicitly bounded batch timeout is supported. `runners.yaml` must set `batch_timeout_s`, or the runner is refused | allowed | `min(batch_timeout_s, max_invocation_s)` | start rows present: started → `timeout`, unstarted → `not_started`. No start rows at all: every unreported unit → `batch_timeout`, an explicit "the batch bound fired; per-unit attribution unknown" status |
| `none` (the default) | the **engine**. The unit runs as a **singleton invocation** and its own `timeout_s` is the invocation's deadline | forced off: the unit is `BatchNo`, so the grouping function makes it a singleton | `min(timeout_s, max_invocation_s)` | the one unit → `timeout`. Its invocation was running, so it is attributable |

- **Separate engine ceiling.** `max_invocation_s` is a `runners.yaml`
  top-level value (default 3600), optionally set per runner. It is never
  derived from Σ `timeout_s`, and it bounds every invocation whatever the
  mode. `timeout_s` defaults to 600.
- **Enforcement is checked, not trusted.** A `per_unit` runner that reports
  a non-timeout result with `duration_ms` > `timeout_s` × 1000 + 2 s
  (`TimeoutSlack`) did not enforce its declared bound. That is a
  reconciliation mechanism failure (`timeout_not_enforced`), so the unit
  never anchors.
- **Started vs never started after a normal runner exit.** An expected unit
  with no result after the runner exited on its own is `missing`, which is a
  reconciliation failure. The kill-path statuses `timeout` / `not_started` /
  `batch_timeout` are only assigned when the **engine** ended the
  invocation.
- **Cleanup ownership (session sweep).** Process groups do not nest. A
  `per_unit` runner that gives each test its own group (`set -m`,
  `setpgid`) would leave that group alive after a kill of the runner's own
  group, and a SIGKILLed runner cannot clean up. So the unit of ownership is
  the **session**, not the group:
  - The engine starts every runner with `SysProcAttr{Setsid: true}`. The
    runner leads a new session, and every process group it or its tests
    create with `setpgid` stays inside that session (POSIX: `setpgid`
    cannot leave the caller's session).
  - **The engine owns every process in that session.** On every exit path —
    a normal exit, an engine kill, an engine error — `sweepSession(sid)`
    runs before the invocation returns:
    1. Enumerate the processes whose session id is `sid`.
    2. SIGKILL each distinct process group among them (`kill(-pgid)`),
       then each remaining pid.
    3. Re-enumerate until no **live** process remains. A zombie counts as
       gone. The loop is bounded by `SweepTimeout` (5 s).
  - Enumeration uses `proc_linux.go` (`/proc/<pid>/stat`: state and
    session, parsed after the last `)`) and `proc_darwin.go` (`ps -A -o
    pid=,stat=` with `syscall.Getsid`). A host where enumeration fails is a
    mechanism failure (`cleanup_unverified`) and the run exits 3. The engine
    never claims a cleanup it could not observe.
  - A sweep that times out with live processes left is a mechanism failure
    (`cleanup_incomplete`, exit 3), and the surviving pids are named in
    `cause_detail`.
  - The `per_unit` runner still owns killing its own unit's group on a
    per-unit timeout, since it must continue to the next unit. The engine
    owns everything left when the invocation ends.
  - **Residual, stated:** a process that calls `setsid()` itself (a
    daemonizing test) leaves the session and escapes the sweep, as for
    scanner plugins. The runner contract forbids it, and M3.2's builtins
    never do it.
  - `WaitDelay` still bounds the wait for pipes held by a leaked process.
- **Invocation cause.** An engine-fired deadline sets `cause: timeout` with
  `cause_detail` set to `unit` (none), `batch` (batch) or `invocation_max`
  (any mode hitting `max_invocation_s`). A runner-enforced unit `timeout` in
  `per_unit` mode is a unit result, not an invocation cause. The other units
  of that invocation keep their own outcomes.
- **Builtins.** M3.1 defines the contract and the tests. Each M3.2 builtin
  declares its own mode and proves it with its own tests (note to t1854_2,
  §0.4). The suggested modes are:
  - `bash-file`: `per_unit`, one process group per file;
  - `pytest`: `none`, or `per_unit` only with a per-test kill;
  - `go-test`: `batch`;
  - `gradle-class`: `batch`;
  - `suite`: one unit, so `none`;
  - `device`: `none`.

### 0.4 Downstream notes (sent after implementation, once the shapes are real; Post-phase step 3)

- **t1854_2** (M3.2) receives:
  - the **Timeout model**: each builtin must declare `timeouts:` and prove
    it with its own enforcement and cleanup tests. A `per_unit` builtin
    must emit start rows and kill each unit's process tree. A builtin that
    cannot bound units inside a batch declares `batch` (and its runner
    entry needs `batch_timeout_s`) or `none` (engine singletons). The
    suggested per-builtin modes are as in *Timeout model*;
  - **cleanup ownership**:
    - the engine sweeps the runner's whole session on every exit path;
    - a builtin may put each test in its own process group (`setpgid`), but
      must never `setsid`;
    - a `per_unit` builtin kills its own unit's group on a per-unit timeout
      before moving on;
  - the builtin protocol (`RegisterBuiltin`, `SelfExe`, the env vars);
  - the describe-override rule (D6);
  - `children:` as an opaque string;
  - the manifest's `handle` field;
  - the results row schema;
  - `group_by` (D4).
- **t1854_3** (M3.3) receives:
  - `Executor` / `RegisterExecutor`;
  - the per-invocation callback;
  - `RegisterWaveClassifier`;
  - `Invocation.Handle`;
  - the rule that the serial plan refuses resources.
- **t1854_4** (M3.4) receives:
  - `RegisterPostRunHook`, the `RunReport` shape and the record encoding
    (D2, D11);
  - top-level / child marking via `parent`;
  - the run-id rule (D10).
- **t1853_4** (M2.4) receives the `RegisterDescribeKey` seam for
  `axis:` / `token_format:`.
- **t1853_5** (M2.5) receives:
  - the `UnitAnnotation` fields added (D1), next to which M2.5's
    kind / area / scope / reads fields go;
  - the wave-classifier seam.
- **t1857** (M6) receives:
  - the `runners.yaml` schema `detect --write` must emit, including the
    D13 subsumption rules (thinking_app's `screen-matrix` / `gradle-class`
    → `verify-active` chains are valid);
  - the rule that a `SCAFFOLD_TODO` `list` row is refused as
    `INPUT_ERROR:lister` until M6.4 adds recognition.

Hedge: shapes as of the implementation commit.

### 0.5 Ownership re-confirmation

- `goengines/internal/testmap/runner/**` (excluding `builtin/`): owned.
- `cmd/ait-testmap/verbs.go`: the `run` row only. The new
  `cmd/ait-testmap/run.go` is owned, like `scancheck.go` is M2.1's.
- `cmd/ait-testmap/scancheck.go`: the `Lister` line in `testmapInputs()`
  (named extension of M2.1).
- `annot/source.go` `toRegistry` and the `registry.UnitAnnotation` fields
  (named extension of M2.2).
- `cmd/ait-testmap/main_test.go`: drop `run` from the stub list (the
  verb-table test follows the table).
- `scancheck_test.go`: the production-wiring assertion changes (D8).
- `internal/gitx/status.go`: new shared helper, following the `lsfiles.go`
  precedent (D2).
- `goengines/README.md`: add Interfaces rows.
- The proposal: the D1 / D5 / D13 edits, all inside M3.1's own row and
  component.
- `internal/testmap/runner/proc_{linux,darwin}.go`: owned (the session
  sweep is runner-specific, so it does not go into the shared `platform`).

## Contract shapes (decided in Step 0)

**`describe`** — stdout is one YAML mapping, decoded with
`KnownFields(true)`:

```yaml
unit: file            # file|class|method|variant|suite (required)
batch: true           # runner can take many units per invocation (default true)
needs: [heavy-run]    # runner-level resources (default [])
group_by: none        # none|file|dir|regex:<re> (default none)
filter_scope: per_unit  # per_unit|whole_run (default per_unit)
full: false           # true: a full-suite runner (child rows allowed)
children: pytest-junitxml   # post-processor name; requires full: true
artifact_glob: ["app/src/**/screens/*.kt"]
timeouts: none        # per_unit|batch|none (default none) — the Timeout model (D5)
```

- An unknown key is refused. That includes `axis:` and `token_format:`
  until M2.4 calls `runner.RegisterDescribeKey("axis")`; a registered key
  lands raw in `Describe.Ext`.
- `group_by: regex:` must compile.

**`list`** — `<id>\t<kind>\t<lowering>[\t<artifact>]` per line, and only a
final newline. A row is malformed, as `INPUT_ERROR:lister|<runner>: list
line <n>: <reason>`, never skipped, when:

- it does not have 3 or 4 fields, or a field is empty;
- the id is invalid, or duplicated within the runner;
- the kind is outside the D7 vocabulary;
- a `variant` row has no `@variant`;
- the artifact is not a valid path;
- `group_by: regex:` does not match.

**Runner invocation** — the commands are `<exe> describe`, `<exe> list` and
`<exe> run --manifest <abs path>`, run in `cwd`.

- Env: `AIT_TESTMAP_ROOT`, `AIT_TESTMAP_RUNNER`, `AIT_TESTMAP_COMMAND`
  (`command:` override, builtins only), `AIT_TESTMAP_RUN_ID` (run only).
- Each runner leads its own **session** (`Setsid`). Every invocation of
  `describe`, `list` or `run` ends with the session sweep (*Cleanup
  ownership*), whatever the exit path.
- stdout is capped at 64 MiB and stderr at 64 KiB; the first stderr line is
  reported.
- `describe` / `list` time out after 300 s (`ListTimeout` var).
- Runner `run` exit contract: `0` all passed · `1` a unit failed · `2`
  nothing ran · `75` refused · `64` usage.

**Manifest** (`.aitask-testmap/runs/<run-id>/inv-<NNN>/manifest.json`):

```json
{"contract":1,"run_id":"…","invocation":1,"group":"<key string>","handle":"",
 "timeouts":"per_unit","deadline_s":3600,
 "results":"<abs>/results.jsonl","runner_json":"<abs>/runner.json",
 "units":[{"id":"tests/test_a.sh","lowering":"tests/test_a.sh","timeout_s":600}]}
```

- `handle` is empty unless an executor set `Invocation.Handle` (M3.3).
- `deadline_s` is the engine's deadline for this invocation, per the
  Timeout model.

**`results.jsonl`** — one JSON object per line, strict (unknown fields
refused). There are two row forms:

- start: `{"id":"…","event":"start"}`;
- result: `{"id":"…","status":"pass|fail|skip|error|timeout",
  "duration_ms":12,"parent":"<top-level id>"?,"message":"…"?}`.

The rules:

- `status: timeout` is accepted only from a `per_unit` runner.
- Start rows are for top-level ids only. A start after the same id's result,
  or a second start, is malformed.
- A result row with `parent` is a **child** row; one without is
  **top-level**.
- Child rows are allowed only when the effective describe has `full: true`.
  Their parent must be a manifest id, and their own id must be a registered
  (listed, owned) id.
- **Every complete line is validated on both paths**, a normal exit and an
  engine kill alike. The one exception is narrow: after an **engine kill**,
  a final line with **no trailing newline** is ignored as truncated. A
  malformed line that ends in a newline is a protocol error on either path.
  So is an unterminated final line after a normal exit that does not parse.

**Row validation (both paths).** Validation yields the set of valid rows
and a list of protocol errors. Each error is `reconciliation` detail
`malformed`, `duplicate`, `unexpected_id`, `unregistered_id`,
`invalid_child` or `timeout_not_per_unit`.

- An expected id with any invalid row of its own (a duplicate result, a
  start after its result, `status: timeout` from a non-`per_unit` runner)
  gets status `error`, with message `protocol:<detail>`. It is never
  `pass`, and never re-synthesized as `timeout` / `missing`.
- Rows naming ids outside the manifest, and invalid child rows, are
  discarded. Each is recorded as a protocol error.
- Only valid rows drive outcome synthesis.

**Unit statuses in results.** The runner reports
`pass|fail|skip|error|timeout`. The engine synthesizes four more:

- `timeout`: the engine killed the invocation while the unit was attributably
  running;
- `not_started`: the engine killed the invocation before the unit's start
  row;
- `batch_timeout`: the bounded batch timeout fired and no start rows
  existed;
- `missing`: the runner exited on its own without reporting the unit, which
  is a reconciliation failure;
- `refused`: the runner exited 75 with no rows. The unit was neither run
  nor failed;
- `error`: also used for an expected id whose own rows broke the protocol
  (above).

**Invocation outcome table.** It is applied **after** row validation and
**before** any unreported-unit synthesis. "Rows" means valid rows of either
form. "Failing" means `fail|error|timeout` on a top-level or child row.

| how the invocation ended | rows | unit outcome for valid expected ids still unreported | invocation cause | contributes to run exit |
|---|---|---|---|---|
| runner exit **75** | **nothing emitted** (results file absent or whitespace-only) **and** no protocol errors | `refused` | `""` (`refused: true`) | 75 |
| runner exit **75** | anything emitted — valid rows, rows validation rejected (unexpected id, malformed, invalid child…) or an unterminated final line | `missing` | `reconciliation/exit_mismatch`, with every protocol error kept in `protocol_errors`; **`refused: false`** | 1 |
| runner exit **0** | all results `pass`/`skip`, every expected id reported | — | `""` | 0 (or 2, see the final-exit rule) |
| runner exit **0** | a failing row | `missing` | `reconciliation/exit_mismatch` | 1 |
| runner exit **1** | at least one failing row | `missing` | `""` when every expected id is reported, else `reconciliation/missing` | 1 |
| runner exit **1** | no failing row | `missing` | `reconciliation/exit_mismatch` | 1 |
| runner exit **0 / 1** | no top-level result rows | `missing` | `reconciliation/zero_reported` | 1 |
| runner exit **2** | none | `missing` | `reconciliation/zero_reported` (a manifest is never empty) | 1 |
| runner exit **2** | any | `missing` | `reconciliation/exit_mismatch` | 1 |
| runner exit **64** or out of contract | — | `missing` | `mechanism/runner_exit:<code>` | 3 |
| **engine kill** (deadline) | ignored for the decision | `AttributeKill` (`timeout` / `not_started` / `batch_timeout`) | `timeout/<unit\|batch\|invocation_max>` | 1 |
| any of the above + protocol errors | — | as above | the higher of the row's cause and `reconciliation/<first protocol error>` by precedence `mechanism > reconciliation > timeout`; every protocol error is kept in `protocol_errors` and the timeout in `timed_out` | max |
| sweep failure on any path | — | as above | `mechanism/cleanup_incomplete\|cleanup_unverified` | 3 |

- "Rows" in this table means **valid** rows, with one exception: the two
  exit-75 rows test **emitted output**, meaning any non-whitespace byte in
  `results.jsonl`, valid or not. A clean refusal requires that nothing was
  emitted and that no protocol error was recorded. A report that
  validation rejected entirely is a protocol failure, never an admission
  refusal: `refused` stays `false`, so the final-exit precedence (75 ahead
  of 1) cannot hide it.
- "Every expected id reported" is checked before `missing` synthesis, so a
  normal exit-0 or exit-1 run with gaps is a `missing` reconciliation
  failure. A clean refusal never acquires `missing` rows or a cause.
- An invocation is `refused` **only** through the clean-refusal row. It
  never carries both `refused: true` and a cause.
- **Final run exit**, over all invocations:
  1. 3 if any invocation is a mechanism failure, or on any engine error or
     hook error.
  2. Else 75 if any invocation was refused.
  3. Else 1 if any unit is failing, `missing`, `not_started`,
     `batch_timeout` or `timeout`, or any invocation has a cause.
  4. Else 2 if **no unit passed**: nothing selected, or every selected unit
     `skip`ped. No pass evidence exists, so the gate reads it as "nothing
     ran" (Invariant 1), never as a pass.
  5. Else 0: every unit is `pass` or `skip`, at least one passed, and no
     invocation has a cause.

**`runner.json`** (optional) — `{"overhead":[{"group":"…","overhead_ms":N}]}`,
strict.

**Engine record** (`inv-<NNN>/record.json`, written by the engine only):

```json
{"contract":1,"run_id":"…","invocation":1,"group":"<key string>","runner":"…",
 "units_expected":3,"units_reported":3,"units_started":3,"exit_code":0,"elapsed_ms":420,
 "timeouts":"per_unit","deadline_s":3600,"killed":false,"refused":false,
 "timed_out":"","protocol_errors":[],
 "overhead_ms":12,"cause":"","cause_detail":"",
 "head_start":"<sha|empty for unborn>","head_end":"…","modified":["sorted, start ∪ end"]}
```

- `cause` takes one of four values: `""`, `mechanism`, `timeout` or
  `reconciliation`. It is the **primary** cause by precedence `mechanism >
  reconciliation > timeout`. Nothing is lost:
  - `timed_out` keeps the timeout bound (`unit|batch|invocation_max`)
    whenever the engine killed the invocation;
  - `protocol_errors` keeps every row-validation error (`<detail>:<id or
    line>`).

  M3.4 needs only "cause is empty".
- `cause_detail` is the primary cause's detail:
  - `mechanism`: `runner_exit:<code>`, `cleanup_incomplete:<pids>` or
    `cleanup_unverified`;
  - `reconciliation`: `zero_reported`, `missing`, `exit_mismatch`,
    `timeout_not_enforced`, or the first protocol error;
  - `timeout`: the bound.
- `overhead_ms` is elapsed time minus the Σ top-level durations, clamped at
  0 (Dev 13).

**`runners.yaml`** (`aitestmap/runners.yaml`, strict, `contract:` checked via
`testmap.CheckContract`):

```yaml
contract: 1
max_invocation_s: 3600         # engine ceiling per invocation, every mode (D5)
runners:
  - name: bash-file            # word, unique
    builtin: bash-file         # or script: aitestmap/runners/x.sh
    command: "bash"            # builtin only: passed as AIT_TESTMAP_COMMAND
    cwd: "."                   # repo-relative dir (default root)
    bind: ["tests/**/test_*.sh"]
    timeout_s: 300             # per-unit bound (default 600)
    batch_timeout_s: 1800      # required iff effective timeouts: batch; refused otherwise
    max_invocation_s: 7200     # optional per-runner ceiling override
    subsumed_by: full          # a full: true runner; no self-reference, no cycle (D13)
    fallback_command: "…"      # only on a unit: suite runner
    # any describe key (unit, batch, needs, group_by, filter_scope, full,
    # children, artifact_glob) overrides the runner's own describe (D6)
```

**Resolution and the resolution record.** A runner name resolves in this
order:

1. `script:`.
2. Else an executable `aitestmap/runners/<name>.sh`. This is
   **shadow-by-name**, and it shadows `builtin:` when one is set.
3. Else `builtin:`, which must be registered.
4. Else it is refused.

The record is `Resolution{Runner, Source: script|shadow|builtin, Path,
Reason}`. Its `Reason` reads, for example, `aitestmap/runners/pytest.sh
shadows builtin:pytest`. M4.1's `explain` prints it.

**Unit ownership** — the first match below wins:

1. The `testmap:runner` annotation: on a member block for that member, on
   the file-level block for the file and all its units.
2. The first runner whose `bind:` glob matches the id path.
3. The single runner that listed the id.

Two unbound runners listing the same id is malformed. A unit listed by a
runner that does not own it is dropped from that runner. An override naming
an unknown runner is `RUNNER_UNKNOWN`. Excluded paths are dropped.

## Implementation steps

New package `goengines/internal/testmap/runner/`. Error values carry
`Line()` / `ExitCode()` like `registry.InputError`, so `reportError`-style
printing works.

1. **`describe.go`** — `Describe` struct, `ParseDescribe([]byte)
   (Describe, error)`, `RegisterDescribeKey(key)`, `Ext map[string]yaml.Node`,
   `(Describe).Merge(overrides)` for D6, and `GroupOf(id) (string, error)`
   for D4.
2. **`list.go`** — `ParseList(runner string, d Describe, data []byte)
   ([]registry.ListedUnit, []string /*groups*/, error)` with every malformed
   case above.
3. **`exec_unix.go`** — `invoke(ctx, Command, args, env, deadline, stdin)
   (stdout, stderrFirst, exitCode, killed bool, sweepErr, err)`. It starts
   the runner with `Setsid: true`; its sid is its pid. `Cancel` kills the
   runner's group. After `Run` returns — on every path — it runs
   `sweepSession(sid)` (*Cleanup ownership*). `WaitDelay` and `capWriter`
   are as in `deps/plugin.go`. Add **`proc_linux.go`** /
   **`proc_darwin.go`**: `sessionProcs(sid) ([]proc{pid, pgid, zombie},
   error)`. `SweepTimeout` is a var.
4. **`repo.go`** — the `runners.yaml` loader (`LoadConfig(root)`, strict,
   contract checked) and resolution with `Resolution`. `RegisterBuiltin`
   and `SelfExe` (D12). The validations:
   - `command:` is only valid with `builtin:`;
   - `cwd` must be an existing directory under root;
   - **subsumption (D13):**
     - `subsumed_by` must name an existing runner other than itself, whose
       effective describe is `full: true`;
     - following `subsumed_by` links from any runner must never revisit a
       runner (a cycle, including mutual `A↔B`, is refused as
       `RUNNER_INVALID:<runner>|subsumption cycle <A→B→A>`);
     - every chain ends at a **terminal** runner with no `subsumed_by` and
       `full: true`;
   - `fallback_command` is only valid on a `unit: suite` runner;
   - bind globs must be valid.

   `Load(ctx, root) (*Repository, error)` runs `describe` + `list` per
   runner, applies the yaml overrides, reads annotations
   (`annot.Source{}`) for overrides, `batch` and `needs`, and computes
   ownership and `Bound`. `Bound` is the git-visible files (`gitx
   ListFiles`) minus `exclude:`, whose first-matching binding or override
   is this runner. It yields `[]Unit{ID, Kind, Lowering, Artifact, Runner,
   Group, Resources, BatchNo, Timeout}`. For `Resources`, the runner's
   `needs` ∪ the file-level needs ∪ the member needs, sorted and
   deduplicated; variants inherit from their base unit. `BatchNo` is true
   when any of these holds:
   - the runner says `batch: false`;
   - `testmap:batch no` is set (member over file level);
   - **the effective `timeouts` is `none`** (D5: an engine-bounded unit is a
     singleton).

   More validations:
   - `batch_timeout_s` is required iff `timeouts: batch`;
   - every timeout is > 0;
   - `batch_timeout_s` and `timeout_s` are ≤ the effective
     `max_invocation_s`; a larger value is refused, never silently clipped.
5. **`lister.go`** — `Lister{}` implements `registry.UnitLister` over
   `Load`. Absent `runners.yaml` gives the D8 error. Every load error is
   returned and becomes `INPUT_ERROR:lister`.
6. **`group.go`** — the canonical grouping function:
   - `type WaveClass string` (`unit` | `broad`);
   - `type Key struct{Runner, Group string; Resources []string; Wave
     WaveClass; Batch string}`;
   - `KeyOf(u Unit, wave WaveClass) Key`: batch identity `""` is shared,
     `u.ID.String()` when `BatchNo`; an empty wave means `unit`;
   - `Key.String()` is a compact JSON array, line-safe;
   - `Group(units []Unit, wave func(registry.ID) WaveClass) []Invocation`
     is pure, its output sorted by key string then id, and independent of
     input order.
7. **`plan.go`** — the seams:
   - `Invocation{Index, Key, Runner, Units, Handle}`;
   - `Executor interface{ Execute(ctx, []Invocation, func(ctx, *Invocation)
     Outcome) ([]Outcome, error) }`, `RegisterExecutor(e)` (M3.3) and
     `RegisterWaveClassifier(f)` (M3.3 / M2.5);
   - `serialExecutor`, which first refuses when **any** invocation has
     non-empty `Key.Resources`. The error is `RUN_ERROR:scheduler-unavailable|<group>`,
     exit 3, and nothing runs. Otherwise it calls the callback in order.
8. **`timeout.go`** — the Timeout model as pure functions, testable
   without processes:
   - `Deadline(mode, units, batchTimeout, maxInvocation) time.Duration`;
   - `AttributeKill(mode, expected []ID, started, reported set)
     map[ID]Status`, which implements the last column of the table;
   - `CheckEnforced(mode, unit timeout, result) error`, for
     `timeout_not_enforced`.

   `TimeoutSlack` is a var (2 s).
9. **`results.go`** — `ValidateRows(data []byte, killed bool, m Manifest,
   d Describe, registered set) (valid []Row, perID map[ID]protocolErr,
   errs []string, emitted bool)`. It parses and validates every complete line (*Row
   validation*) and applies the truncated-final-line exception only when
   `killed`. `CheckEnforced` runs here too, for `per_unit`
   (`timeout_not_enforced`). Pure, so it can be table-tested.
10. **`outcome.go`** — `Outcome(end EndState{Exit int; Killed bool;
    Bound string; SweepErr error}, valid, perID, errs, m) (results, Record
    fields)`. It implements the *Invocation outcome table* in a fixed
    order:
    1. Protocol-invalid expected ids → `error`.
    2. Classify the end state:
       - a sweep error → mechanism;
       - killed → timeout;
       - exit 75 with **nothing emitted and no protocol errors** → refused
         (`ValidateRows` also returns an `emitted bool`, true for any
         non-whitespace byte); exit 75 with anything emitted →
         `exit_mismatch`;
       - otherwise the exit / rows rows of the table.
    3. Only then, synthesize outcomes for the still-unreported valid
       expected ids: `AttributeKill`, `refused` or `missing`.
    4. Pick the primary cause by precedence, and fill `timed_out` and
       `protocol_errors`.

    Pure, table-tested.
11. **`invoke.go`** — the per-invocation callback, in this order:
    1. Write the manifest, with `timeouts` and `deadline_s`.
    2. Capture HEAD (`rev-parse --verify -q HEAD`, empty when unborn) and
       `ModifiedPaths`.
    3. `invoke(...)` under `Deadline(...)`, giving `killed` and `sweepErr`.
       The sweep has already run.
    4. Capture HEAD / modified again.
    5. `ValidateRows` (both paths), then parse `runner.json`.
    6. `Outcome(...)`.
    7. Write `record.json`.

    `Result{ID, Status, DurationMS, Parent, Child bool, Started bool,
    Message, Invocation}`. Statuses are as in *Contract shapes*.
12. **`run.go`** (package) — `Run(ctx, root, Options{All bool; IDs []string;
   RunID string}) (*RunReport, error)`:
   1. Load the repository.
   2. Select. `--all` takes every owned unit except those of runners with
      `subsumed_by`, so the suite runs once. Explicit ids must be owned
      units, else `RUN_ERROR:unknown-id|<id>` (exit 3).
      **Before anything runs**, every runner omitted by `--all` must have
      its chain's terminal suite runner contribute **at least one selected
      unit** to this run. Otherwise `RUN_ERROR:subsumption|<runner>|terminal
      <suite> selects no unit` (exit 3). An omitted runner's tests are never
      silently dropped behind a suite that does not run (D13).
   3. Group, then execute through the registered or serial executor.
   4. Call the post-run hooks: `RegisterPostRunHook(name, func(ctx,
      RunReport) error)`, in registration order, each once (D9).
   `RunReport{RunID, Root, Dir, Invocations []Record, Results []Result,
   Refused bool}`.
13. **`internal/gitx/status.go`** — `(Repo).ModifiedPaths(ctx) ([]string,
    error)` (D2): sorted, deduplicated, rename gives both paths, any stderr
    is an error. Plus `(Repo).Head(ctx) (string, error)`, empty on an unborn
    HEAD and never an error for that case.
14. **`cmd/ait-testmap/run.go`** — `runRun`:
    `run [--all] [--run-id <id>] [--json] [<id>...]`. `runExits = {0,1,2,3,64,75}`.
    - Lines (Dev 12 homes them here):
      - `RUN:<run-id>`;
      - per invocation `INVOCATION:<n>|<runner>|<units_expected>|<group>`;
      - per result `UNIT:<id>|<status>|<duration_ms>|top|` or
        `…|child|<parent>`;
      - per cause `MECHANISM:<n>|<cause>|<detail>`;
      - a final `RUN_RESULT:<pass|fail|nothing|refused|error>|<passed>|<failed>|<skipped>|<mechanism>`;
      - on stderr, `RUN_ERROR:<class>|<detail>` and `RUN_HOOK_ERROR:`.
    - Exit precedence: 3 > 75 > 1 > 0. Exit 2 when no unit was selected.
      Neither `--all` nor ids is a usage error (64). `--json` emits the
      `RunReport`.
    - `verbs.go`: replace `stub("run")` with `{Name: "run", Run: runRun,
      Exits: runExits}`.
15. **Named extensions:**
    - `scancheck.go` `testmapInputs()` gains `Lister: runner.Lister{}`.
    - `registry/inputs.go` `UnitAnnotation` gains `Runner string`,
      `Batch string` (`""|yes|no`) and `Needs []string`.
    - `annot/source.go` `toRegistry` fills them from `u.Runner`, `u.Batch`
      and `u.Needs`, flattening the args.
16. **Docs:**
    - `goengines/README.md` Interfaces rows for `describe`, `list`, the
      runner invocation, the manifest, results, `runner.json`, the record,
      `runners.yaml` and resolution, the grouping function, the executor,
      the hook and `run`;
    - an update to the `scan` row's "until M3.1 lands" text;
    - the proposal edits:
      - the D1 line;
      - the D5 timeout-model paragraph, with cleanup ownership;
      - `timeouts:` added to the component's `describe` field list;
      - one sentence of D13 subsumption validation.

### Post-phase (risk mitigations)

1. [provenance_mutant_red_proof] Run three isolated, uncommitted mutants
   against the provenance tests:
   - drop `--untracked-files=all`;
   - drop the end-of-invocation capture;
   - treat rename / deletion records as skipped.

   Confirm each makes `TestRecordProvenance*` fail, then restore and
   confirm green. Record the outcome in Final Implementation Notes.
2. [interface_shape_pins] Every shape in *Contract shapes* is pinned by a
   named test and listed in the README Interfaces table with that test
   name. The downstream children consume these shapes, so drift must fail
   a test, not a reviewer's memory.
3. Send the §0.4 notes with `./ait note … --from 1854_1`, hedged to the
   implementation commit.

## Verification

All tests live under `goengines/internal/testmap/runner/` (fixture repos via
`fixture.New`, runners as bash scripts in `aitestmap/runners/`,
`.aitask-testmap/` in the fixture's `.gitignore`), unless noted.

- `TestDescribeGoldens` checks each field. `TestDescribeRefusesUnknown`
  covers `axis`, `token_format` and `bogus`, and
  `TestDescribeExtensionKey` checks registered-key acceptance.
- `TestListParse` covers member / variant ids and the artifact column.
  `TestListMalformed` is table-driven, one case per malformed rule, and runs
  through `registry.Scan` with `Lister{}` to see `INPUT_ERROR:lister|…`.
- `TestBindingsFirstMatch`, `TestPerTestOverride` (file-level and member
  `testmap:runner`), `TestShadowByName` (resolution record reason) and
  `TestRepositoryRefusals` cover:
  - an unregistered builtin;
  - `command:` without `builtin:`;
  - `fallback_command` on a non-suite runner;
  - `subsumed_by` naming a non-full runner;
  - an unknown yaml key;
  - `CONTRACT_MISMATCH`;
  - an absent `runners.yaml` (D8).
- `TestGroupingKey` checks that each key component splits invocations.
  `TestGroupingBatchNoSingletons` checks that two `batch: no` units with
  identical fields give two invocations. `TestGroupingWaveClass` checks
  that `unit` vs `broad` gives two invocations and that no kind data means
  `unit`. `TestGroupingDeterministic` permutes the input.
- `TestRunPassFail` covers exits 0 and 1 and top / child marking.
  `TestRunReconciliation` covers zero reported, an unregistered row, an
  unexpected id, a missing id and an exit contradiction, each a cause.
  `TestRunRunnerExit75` gives 75, and `TestRunOutOfContractExit` gives 3.
- **Exit / status table (D14).** `TestOutcomeTable` is a pure table test,
  one case per row of the *Invocation outcome table*, asserting unit
  statuses, `cause` / `cause_detail`, `timed_out` and `protocol_errors`
  together. Then `TestRunExitOutcomes` goes through the real `Run` with
  fixture runners, asserting rows, record cause **and** final run exit
  together for these cases:
  - **refusal without results**: runner exit 75 with no rows gives units
    `refused`, no `missing`, empty cause, run exit 75;
  - refusal with valid rows gives `exit_mismatch`, exit 1;
  - **exit 75 with only a foreign-id row** gives every expected unit
    `missing`, cause `reconciliation/exit_mismatch`, `protocol_errors`
    holding `unexpected_id:<id>`, `refused: false` and run exit **1**
    (not 75);
  - **exit 75 with only a malformed line** (newline-terminated garbage, and
    separately an unterminated final line) gives the same assertions with
    `malformed` in `protocol_errors`;
  - an invariant check across every case: no invocation record has both
    `refused: true` and a non-empty `cause`;
  - **pass + skip** gives exit 0 with an empty cause;
  - **all skipped** gives exit 2, `RUN_RESULT:nothing`;
  - **nothing ran**: runner exit 2 with no rows gives `zero_reported`,
    exit 1;
  - exit 0 with a `fail` row gives `exit_mismatch`;
  - exit 1 with all `pass` gives `exit_mismatch`.
- **Killed-path validation (D14).** `TestKilledRunValidatesRows`: a runner
  writes a duplicate result for unit A, a foreign-id row and a valid pass
  for unit B, then hangs past its deadline. The engine kills it, and then:
  - A is `error` (protocol), B is `pass`, and the unstarted C is
    `not_started`;
  - `protocol_errors` holds `duplicate` and `unexpected_id`, and
    `timed_out` is set;
  - the primary cause is `reconciliation`, and the run exits 1.

  A companion case checks that after a kill an unterminated final line is
  ignored, while a newline-terminated malformed line is a protocol error.
  The same malformed line after a normal exit is also a protocol error.
- **Subsumption (D13).** `TestSubsumptionRefusals` refuses at load:
  - a self-reference;
  - a mutual cycle of two `full: true` runners;
  - a 3-cycle;
  - a chain ending at a non-full runner.

  `TestSubsumptionCycleWithPassingRunner` pins the user-visible failure: a
  cyclic configuration plus an unrelated passing runner makes
  `run --all` / `check` exit 3 naming the cycle, **never** exit 0 from
  the passing runner alone. `TestSubsumptionTerminalSelectsNothing`: a
  valid chain whose terminal suite lists no unit (or whose unit is
  `exclude:`d) gives `RUN_ERROR:subsumption|…`, exit 3, and no runner
  executed. `TestRunAllSubsumed` remains the positive case.
- **Timeout enforcement and cleanup.** The fixture runners are bash scripts
  in which each "unit" is a `sleep`. Each test bounds its own wall-clock
  time, so a broken kill fails rather than hangs.
  - Pure unit tests:
    - `TestTimeoutDeadline` checks `Deadline` for each mode, including
      `min` with `max_invocation_s`;
    - `TestAttributeKill` is a table over mode × {started, unstarted,
      reported} × {start rows present / absent} → `timeout` /
      `not_started` / `batch_timeout`;
    - `TestCheckEnforced` covers the slack edge.
  - `TestTimeoutPerUnitRunnerEnforced`: a `per_unit` runner kills its own
    over-time unit and reports `timeout`. The next unit in the same
    invocation still passes, and the invocation has no cause.
  - `TestTimeoutPerUnitNotEnforced`: a `per_unit` runner reports `pass`
    with `duration_ms` over the bound, giving `timeout_not_enforced`
    reconciliation.
  - `TestTimeoutInvocationMax`: a `per_unit` runner hangs on unit 2 of 3
    past `max_invocation_s`. Unit 1 keeps `pass`, unit 2 (started) gets
    `timeout`, unit 3 gets `not_started`, and the cause is
    `timeout/invocation_max`.
  - `TestTimeoutBatchBounded` covers a `batch` runner killed at
    `batch_timeout_s` in two cases:
    - with start rows: started → `timeout`, unstarted → `not_started`;
    - without start rows: every unreported unit → `batch_timeout`.

    In both cases reported results are kept and the cause is
    `timeout/batch`.
  - `TestTimeoutNoneSingletons`: a `timeouts: none` runner's two units
    form two invocations (also checked through the grouping function). The
    hanging one is killed at its own `timeout_s` → `timeout` with cause
    `timeout/unit`, and the other passes in its own invocation.
  - **Cleanup ownership.** Each case writes the pids it spawns to files.
    "Gone" is checked **immediately** after `Run` returns, with no poll: the
    pid is absent, or `/proc/<pid>/stat` shows state `Z`.
    - `TestCleanupSeparateTestGroupOnInvocationTimeout`: a `per_unit`
      fixture runner starts its unit in a **separate process group**
      (`set -m; sh -c 'sleep 300 & echo $! > desc.pid; exec sleep 300' &`,
      then `echo $! > unit.pid`). The unit and its descendant are verified
      to be in a different pgid from the runner, and in the runner's
      session. The engine's `max_invocation_s` fires while both are alive.
      Both the unit and its descendant must be gone when `Run` returns, and
      the record has `timed_out: invocation_max`.
    - **Red proof** of that test: with an isolated, uncommitted mutant that
      replaces the session sweep with a runner-group-only kill, the test
      fails because the unit and its descendant survive. Recorded in Final
      Implementation Notes.
    - `TestCleanupAfterNormalExit`: a runner that leaves a backgrounded
      `sleep 300` (same group, and separately in its own group) and exits 0.
      The leftovers are gone when `Run` returns.
    - `TestCleanupEveryKillPath`: the same assertion for the `none`
      (unit), `batch` and `per_unit` (`invocation_max`) kills above.
    - `TestSweepEnumeration` (linux): `sessionProcs` finds a session's
      members, including a zombie, which is reported as gone, and skips
      other sessions.
    - The darwin path compiles under `GOOS=darwin go vet ./...`.
  - `TestTimeoutConfigRefusals` refuses three configs:
    - `timeouts: batch` without `batch_timeout_s`;
    - `batch_timeout_s` on a non-batch runner;
    - `timeout_s` > `max_invocation_s`.
  - `TestTimeoutNotStartedVsMissing` checks that a runner exiting normally
    without a result gives `missing` (reconciliation), never
    `not_started`, which is reserved for engine kills.
- `TestRunAllSubsumed` uses a marker-file count to check the suite runs
  once and the subsumed runner never runs. `TestRunFullChildren` checks
  child rows under their parent and their refusal without `full`.
  `TestSerialPlanRefusesResources` checks exit 3 with no runner executed.
- `TestPostRunHookOrder` checks two subscribers fire once each, in
  registration order, and that a failing first one still lets the second
  run, with exit 3.
- **Provenance, red-proved.** `TestRecordProvenance` builds a fixture with a
  staged deletion, an unstaged deletion, an untracked file and a modified
  tracked file, and checks all four are in `modified`. Its negative control
  is a clean tree, which gives an empty `modified`.
  `TestRecordHeadMoved` has the runner commit mid-run, so `head_start` ≠
  `head_end`. `TestRecordMechanismCause` checks a mechanism failure carries
  its `cause`. Mutants are covered by Post-phase step 1.
- `gitx`: `TestModifiedPaths` covers each status shape, renames, unborn
  HEAD, and that `.git/index.lock` is never created.
- `annot`: `TestSourceCarriesRunnerBatchNeeds`.
- `cmd/ait-testmap` has these tests:
  - `TestRunThroughBinary`: the command-level `call("run", "--all")` on a
    fixture repo, checking the line shapes and exit;
  - `TestScanCheckRealLister`: production `testmapInputs()` on a fixture
    repo with `runners.yaml`, no `INPUT_UNAVAILABLE`;
  - `TestScanCheckInputUnavailable` updated to the D8 line;
  - `TestStubsExit64` without `run`.
- `cd goengines && go vet ./... && go test ./...` (= `ait engine test`) is
  green, including the Invariants 4–5 tripwire in `guards_test.go`.
- `shellcheck` does not apply (no shell scripts shipped; fixture scripts
  live in Go test strings).

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9: archival on the
current branch, no merge. Commit code as `feature: … (t1854_1)` and the plan
via `./ait git`.

## Risk

### Code-health risk: medium
- A large new package (~2k lines with tests) defines contracts that four
  later children consume. A shape that is awkward to extend would ripple
  into M3.2 / M3.3 / M3.4 / M2.4 · severity: medium · → mitigation: inline post-phase interface_shape_pins
- Process handling (timeouts, cleanup of per-test process groups, partial
  `results.jsonl` after a kill) is easy to get subtly wrong (zombies, a
  hung wait on leaked pipes, a separate-group test surviving the runner's
  kill, misattributing a killed unit) · severity: medium · → mitigation:
  the engine owns the runner's whole **session** (`Setsid` plus a sweep on
  every exit path); the Timeout model, row validation and the outcome table
  are pure functions with table tests;
  `TestCleanupSeparateTestGroupOnInvocationTimeout` with its red-proof
  mutant. Residual: a test that calls `setsid` itself (stated, forbidden by
  the contract)
- Process enumeration differs per OS (`/proc` vs `ps` + `Getsid`), and the
  darwin path cannot be exercised on this host · severity: medium · →
  mitigation: a failed enumeration is `cleanup_unverified` (exit 3), never
  a silent pass; the darwin build is vetted. `goengines-check.yml` runs
  tests on `ubuntu-latest` only, so the darwin sweep behaviour stays
  **unverified at runtime**. That is stated in Final Implementation Notes
  and offered as an "after" follow-up: a macOS job, or a manual check on a
  Mac.
- Wiring the real lister changes production `scan` / `check` from
  `INPUT_UNAVAILABLE` to real behaviour. No repository has `aitestmap/` yet,
  so blast radius is low · severity: low · → mitigation: TBD (none needed)

### Goal-achievement risk: medium
- The proposal leaves every wire format open (D3–D8). A wrong guess
  (`group_by` vocabulary, describe overrides, the kind column) could force
  rework when M3.2's real builtins land · severity: medium · → mitigation: inline post-phase interface_shape_pins; downstream notes (Post-phase step 3)
- A runner could declare `per_unit` and not honour it, so a hung unit would
  be bounded only by `max_invocation_s` · severity: medium · → mitigation:
  `CheckEnforced` turns an over-bound result into a reconciliation failure,
  and the invocation ceiling still bounds a hang; M3.2 proves each
  builtin's mode with its own tests (note)
- The provenance capture is the correctness basis of M3.4's anchors (Dev 7).
  A missed status shape would silently anchor a dirty tree · severity:
  medium · → mitigation: inline post-phase provenance_mutant_red_proof

### Planned mitigations
- timing: post-phase | name: provenance_mutant_red_proof | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: provenance capture miss (goal-achievement) | desc: isolated mutants prove each provenance status class is load-bearing in TestRecordProvenance*
- timing: post-phase | name: interface_shape_pins | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: contract-shape drift / wrong-shape rework (code-health + goal-achievement) | desc: each contract shape pinned by a named test and a README Interfaces row
