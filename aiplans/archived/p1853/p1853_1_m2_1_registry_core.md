---
Task: t1853_1_m2_1_registry_core.md
Parent Task: aitasks/t1853_testmap_m2_registry_and_map_model.md
Sibling Tasks: aitasks/t1853/t1853_2_*.md, aitasks/t1853/t1853_3_*.md, aitasks/t1853/t1853_4_*.md, aitasks/t1853/t1853_5_*.md, aitasks/t1853/t1853_6_*.md
Archived Sibling Plans: aiplans/archived/p1853/p1853_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-11 23:41
---

# Plan: t1853_1 — M2.1 Registry core

## Context

Parent goal: M2 — Registry and map model (everything that reads and writes
`aitestmap/` without running a test). This is **M2.1 Registry core**, wave
**A**. It covers the loaded registry that every other engine package reads,
plus the `scan` and `check` verbs. Provider: M1.2 (`t1852_2`, `33012bff7`,
archived, so it is not in `depends:`).

This coarse plan records what the proposal fixes for M2.1. It does not design
internals against providers that do not exist yet; the Reality check below
does that when this child is picked. **This verify pass executed the Reality
check (2026-10-11) and expanded the coarse steps into the detailed design
below.**

**Automation-first (user directive, 2026-10-11).** Human review belonged to an
older design. No verb, load rule or check rule shipped here may make a human
action a precondition of any path. `by: human:<email>` is an optional recorded
value, never a gate. A human-only step met in the proposal is reported to its
owning parent (note), never encoded here.

## Proposal reading list

`aidocs/testing_engine/n014_explorer_006_proposal.md` (M2 cut fixed in
`3bc0de8ac`):
- Module Map `#### M2` row M2.1
- *Registry loader and writer (M2.1 core)*
- *Enumeration and reconciliation (M2.1)*
- *Engine binary identity and budget*
- *Architecture → The registry directory, Where state lives, Line-protocol
  index*
- *Invariants*
- *Assumptions → The map and freshness*, *Variants, broad tests and runners*
- *Tradeoffs → Map and registry structure*

Also: the parent plan's Deviations and `goengines/README.md`. The brainstorm
lineage `.aitask-crews/crew-brainstorm-1812/br_proposals/n000–n013` is a
secondary source for schemas the final proposal only names.

## Owned files / provides / consumes

- **Owns:**
  - `goengines/internal/testmap/registry/**` (new)
  - the `scan` and `check` rows in `goengines/cmd/ait-testmap/verbs.go`
  - a new `goengines/cmd/ait-testmap/scancheck.go` (the verb glue and the
    input-wiring point)
  - the new `scan` / `check` lines in `goengines/bench/baseline.txt`
- **Provides:**
  - the loaded registry and id grammar
  - `check` and its rule-registration point
  - the table and file registration points for M2.4 / M2.5 / M2.6
  - two injection interfaces, `AnnotationSource` (M2.2) and `UnitLister`
    (M3.1)
- **Consumes (M1.2 only):**
  - `testmap.CheckContract` / `ContractMismatchError`
  - `lineproto` (`Format`, `Writer`, `Usage`, exit codes)
  - `fixture.New`
  - `benchgate`
  - `guards_test.go`

## Step 0 — Reality check (EXECUTED 2026-10-11, main @ 3bc0de8ac)

### 1. Sources re-read

- The M2.1 Module Map row
- *Registry loader and writer*, *Enumeration and reconciliation*,
  *Engine binary identity and budget*
- The *Cross-module interfaces* rows "the loaded registry" (M2.1/M2.6 →
  every package) and "the runner contract" (M3.1)

### 2. Providers as they exist now

| provider | landed by | state in tree |
|---|---|---|
| verb table | t1852_2 `33012bff7` | `verbs.go`: `stub("scan")`, `stub("check")` exit 64; row shape `{Name, Run func(env, []string) int, Exits lineproto.ExitContract}`; `env` = `{stdout, stderr}` only (no cwd/root) |
| `lineproto` | t1852_2 | `Format/Line` refuse `|` and line breaks; `Writer{JSON}` + `Emit`; `ExitOK 0 / Fail 1 / NothingRan 2 / Framework 3 / Usage 64 / Refused 75`; `Enforce` maps out-of-contract → 3 |
| `testmap.CheckContract(path, data)` | t1852_2 | strict: one mapping doc, integer `contract:`, merge keys resolved; `*ContractMismatchError.Line()` = `CONTRACT_MISMATCH:<path>\|<file>\|<engine>`, `ExitCode()` 3 |
| `fixture` | t1852_2 | `fixture.New(t)` git repo in `t.TempDir()`, `Write/Remove/Commit` |
| `guards_test.go` | t1852_2 | dependency allowlist (`yaml.v3`, `doublestar/v4`, `x/sync`); Invariant 4–5 lexical tripwire; fixture dir exempt |
| `benchgate` | t1852_2, t1872 `2d3376466` | `-update` needs a **full** run (rejects `-partial -update`), so it re-records every line; record pinned `taskset -c 0` |
| `TestStubsExit64` | t1852_2 | iterates **every** non-`version` verb expecting 64; this test must skip `scan`/`check` once they are real |
| `doublestar/v4` | — | **not** in `go.mod`; v4.10.0 in the local module cache; M2.1 is its first importer |
| M2.2 annotation scanner | — | not landed (t1853_2 Ready, depends on t1853_1) |
| M3.1 runner repository | — | not landed (t1854 not decomposed) |
| `aitestmap/` | — | no repository has one |

### 3. Differences (proposal / coarse plan / repository)

| # | proposal says | coarse plan says | repository has | decision |
|---|---|---|---|---|
| D1 | hand-file schema, row schemas and "one merge rule" are named, never spelled out | "loader + one merge rule" | nothing | **Adapt.** Take them from the brainstorm lineage (n000 §registry, n003 merge rule, n006 `_scanned` rows), which the final proposal never contradicts: hand files `{contract, owns, edges, rules, waivers}` (`scopes`/`areas` reserved for M2.5); rules `{name, when, select, implies, escalate, distance}`; waivers `{path, reason, until}`; the merge is a **union** of every file's rows; `owns:` globs over **source** paths. Recorded in the proposal (step 11) |
| D2 | `check` "reports drift" of `_scanned.yaml`, names no line; merge-rule violations "fail check" in the lineage with no line classes; no `check` summary line; nothing for `scan` dry run | — | — | **Revise proposal (additive lines).** New classes: `REGISTRY_INVALID:<path>\|<reason>` (3), `INPUT_UNAVAILABLE:<input>`, `INPUT_ERROR:<input>\|<detail>`, `CHECK_ERROR:<rule>\|<detail>` (stderr, 3), `OWNS_VIOLATION:<file>\|<table>\|<path>`, `DUPLICATE_RULE:<name>\|<file>\|<file>`, `WAIVER_EXPIRED:<path>\|<until>\|<file>` (info; an expired waiver stops waiving), `SCAN_DRIFT:<path>`, `SCAN:<units>\|<edges>\|<variants>`, final `CHECK:<pass\|fail>\|<findings>\|<failing>`; `WROTE:<path>` and `TESTMAP_ABSENT:` reused as defined |
| D3 | `scan`/`check` read two injected inputs | same | `env` carries no root; no providers exist | **Adapt.** Interfaces live in `registry`; production wiring is one function in `cmd/ait-testmap/scancheck.go` that M2.2 / M3.1 edit as named extensions. A nil input → `INPUT_UNAVAILABLE:<input>`, exit 3 (Invariant 8: a declared check errors, never silently passes). The repo root is the process cwd (`ait` cds to the root; tests use `t.Chdir`) |
| D4 | `UNANNOTATED_MEMBER` = listed member with no block | — | — | **Adapt.** Only for files that opted into members (≥1 `testmap:unit` block). Otherwise every pytest/gradle file listed at method granularity would fail at level 0 |
| D5 | strictness: rotted paths always fail; structural rows fail under `--strict` past `bootstrap_until` | — | — | **Adapt.** Always fail: `STALE_PATH`, `UNANNOTATED_MEMBER`, `DEAD_MEMBER` ("both fail-closed"), `OWNS_VIOLATION`, `DUPLICATE_RULE`; `UNSTAMPED` emitted only under `require_stamp` past bootstrap and then fails. Strict-past-bootstrap: `UNREGISTERED`, `UNMAPPED_ARTIFACT`, `SCAN_DRIFT`. Info: `WAIVER_EXPIRED`. An absent `bootstrap_until` = no bootstrap window (fails toward reporting more) |
| D6 | `variants:` list per member (final) vs `{axis, values}` (n006) | list | — | **Follow the final proposal:** `variants: [v…]`; axis association is M2.4's |
| D7 | `STALE_PATH` in the `stale` report has `\|deleted\|<culprits>` | — | — | **Adapt.** `check` emits `STALE_PATH:<test>\|<source>` (no history in M2.1); M4.2 extends fields additively |
| D8 | — | "record baselines with -update" | `-update` re-records every line | **Adapt.** Re-record the whole file pinned `taskset -c 0` per the README; the diff will show existing lines re-measured |
| D9 | — | — | `TestStubsExit64` covers every verb | **Adapt.** Add `scan`, `check` to its skip list (the minimal edit; the verb-table test is unchanged) |
| D11 | — | — | doublestar v4.10.0 `GlobWalk` / `Glob` swallow I/O errors unless `WithFailOnIOErrors()` (verified in source); `git ls-files` exits 0 with only a stderr warning on an unreadable directory and `gitx.RunEnv` discards stderr on exit 0 (verified), and its `--cached` / `--exclude-standard` sets are not the existing files (review probes); a static-base `WalkDir` enters directories no pattern can match (`artifacts/*.json` would read `artifacts/cache/`), and nested-repo pruning is non-monotonic in the pattern spelling (review probes). `GlobWalk` touches the filesystem only through `fs.ReadDir` and `fs.Stat` (verified) | **Adapt (review findings, blocking).** The candidate universe is **strict `doublestar.GlobWalk`** of each declared pattern (a runner's `artifact_glob`, a rule's `when`, a waiver's `path`) with `WithFailOnIOErrors()`, `WithFilesOnly()`, `WithNoFollow()`, over an **exclude-aware view** of `os.DirFS(root)` (`walk.go`: a small `fs.FS` + `fs.ReadDirFS` + `fs.StatFS` wrapper). GlobWalk descends only directories the full pattern can match, so an unreadable irrelevant directory is never opened, while any I/O error in a relevant directory is returned. The view hides exactly two things: (a) paths `exclude:` removes — a file matching an `exclude:` glob, and a directory covered by an `exclude:` glob of the form `<P>/**` (`Match(<P>, dir)`), so an excluded unreadable directory is never read; and (b) entries named `.git`, which are repository metadata, never work-tree files (git refuses to track a `.git` path). There is **no nested-repository pruning**: a separate checkout under the tree is in scope unless `exclude:` names it. Semantics = **existing files**: a deleted tracked file is never a candidate; an ignored file is. A missing pattern base → no matches. Every inspection error propagates: `Rule.Run` returns `([]Finding, error)`, `Check` returns it, the verb prints `CHECK_ERROR:<rule>\|<detail>` on stderr and exits 3, and never prints `CHECK:` |
| D12 | `owns:` routes edges and rules by glob | — | glob-as-literal matching is not containment (owns `src/*` "matches" the literal `src/**`, which reaches `src/deep/x.go`; `src/[ab].go` does not match itself) | **Adapt (review finding, blocking).** Ownership is defined over **concrete paths**, never pattern-against-pattern: a declared edge's `covers` path is owned iff some `owns:` glob of its file matches it; a rule's `when` patterns and a waiver's `path` pattern are owned iff **every file of the current candidate universe they match** is matched by an `owns:` glob of their file. Policy: a pattern matching no file is not a violation (nothing escapes now); a future file is judged when it exists, on that run; an invalid pattern is `REGISTRY_INVALID` at load. Both counterexamples become tests |
| D10 | `config.yaml` "every key and default", canonical block for the added blocks only | — | — | **Adapt.** Core defaults from n006 (`unit_covers_max 8`, `suite_budget_s 600`, `broad_review_days 0`, `concurrency serial`, `broad_after_unit true`, `device_policy filter_by_resource`, `host_class` = hostname when empty, `flake_threshold 0.2`, `symbol_scanners []`, `require_stamp false`, `bootstrap_until` none). Added blocks use the canonical block's values. Project-specific example lists (`conventions`, `exclude`, `docs`) default empty. `run_gate_admission` = `{approved_by?: {who, at, statement}}` (thresholds moved to `readiness:`) |

### 4. Decisions

Recorded per row above.

### 5. Notes to downstream children

Sent after the interfaces exist (post-phase step 2), hedged as "as landed in
`<sha>`":
- t1853_2 (M2.2): implements `AnnotationSource`; wires it in
  `scancheck.go`; owns stamp parsing
- t1853_4 (M2.4), t1853_5 (M2.5), t1853_6 (M2.6): the table / file / rule
  registration points and the reserved names
- t1854 (M3 parent, not decomposed): the `UnitLister` shape M3.1 must
  provide
- t1859 (M8): the `check` exit / strictness table for M8.2's verifier

### 6. Ownership

Every touched file is M2.1-owned except three:
- `cmd/ait-testmap/main_test.go`: a one-line skip-list edit forced by
  replacing the stubs (D9)
- `goengines/go.mod` / `go.sum`: the allowlisted first import of
  doublestar, which the README assigns to its first importer
- `goengines/README.md` *Interfaces*: two additive rows documenting this
  child's shapes, in the table's existing role
- the proposal: an additive documentation edit, per protocol §1

## Design

### Package `goengines/internal/testmap/registry`

- **`id.go`** — `type ID struct{ Path, Member, Variant string }`,
  `ParseID(s) (ID, error)`, `(ID) String()`, `(ID) Base() ID` (variant
  dropped), `(ID) Unit() string`.
  - Grammar `<path>[#<member>][@<variant>]`.
  - `path`: non-empty, slash-separated, relative; no empty, `.` or `..`
    segment; no `\`; no `#`, `@`, `|`, whitespace or control characters.
  - `member` and `variant`: non-empty, no `#`, `@`, `/`, `|`, whitespace or
    control characters.
  - At most one of each fragment; `@` only after `#member` or the path.
  - Golden table test covering every valid and invalid form.
- **`config.go`** — `Config` struct with yaml tags.
  - Defaults per D10 plus the canonical blocks:
    - `completion{mode auto, full_run_every{tasks 5, selection_ratio_above 0.60, days 7}, deferred run, on_empty_selection skip, engine_absent error}`
    - `agent_review{enabled true, confidence 0.90, accept_min 0.85, calibration_min 30, batch 20, packet_lines 120, max_pairs_per_run 400, author true, measured_confidence *float}`
    - `readiness{20, 0, true, 3}`
    - `conventions [{test, source}]`
    - `helper_roots ["tests/lib/**","**/testing/**","**/testdata/**"]`
    - `helper_fanin 0.05`
    - `exclude []`, `docs []`, `notes ""`, `broad_threshold_s 60`
  - `LoadConfig(root)`: an absent file gives the defaults. The file is first
    run through `CheckContract`.
  - Validation, each failure reported as `*InvalidError`:
    - enums: `concurrency`, `completion.mode`, `deferred`,
      `on_empty_selection`, `engine_absent`
    - ratios in [0,1]; ints ≥ 0
    - `bootstrap_until` is `YYYY-MM-DD`
    - every glob passes `doublestar.ValidatePattern`
    - `notes` ≤ 10 lines
  - Unknown keys are ignored: the contract is additive and an older engine
    ignores newer fields.
  - Helpers: `(Config) Excluded(path) bool`,
    `(Config) PastBootstrap(today) bool`, `(Config) HostClass()`.
- **`errors.go`** — `InvalidError{Path, Reason}` with
  `Line()` → `REGISTRY_INVALID:<path>|<reason>` and `ExitCode()` 3.
  `ContractMismatchError` passes through unchanged.
- **`load.go`** — `Load(root) (*Registry, error)`.
  - Reads `aitestmap/config.yaml`, then every `aitestmap/registry/*.yaml`
    (non-recursive), sorted by name.
  - Each file goes through `CheckContract`, then is dispatched by name:
    - `_scanned.yaml` → the units/edges/variants decoder
    - other reserved names (`_scoped.yaml`, `areas.yaml`, `observed.yaml`,
      `seeded.yaml`, `adopted.yaml`) → a `fileLoaders` map
    - unregistered reserved names, or any other `_`-prefixed name →
      `REGISTRY_INVALID` "reserved file not supported by this engine"
    - anything else → hand file
  - Hand file:
    - top-level keys `contract`, `owns`, `edges`, `rules`, `waivers` plus a
      `handTables` map (M2.5 registers `scopes` / `areas`)
    - an unknown top-level key → `REGISTRY_INVALID`; unknown row fields are
      ignored (additive)
    - row validation: an edge needs `test` (id) and `covers` (scalar or
      list); a rule needs a `name`, a non-empty `when`, and one of
      `select`, `implies` or `escalate`, with `distance` ≥ 0 (default 1); a
      waiver needs `path` (glob allowed) and `reason`, `until` optional
  - **The merge rule:** every file's rows are appended to the same tables,
    and duplicate edges are a harmless union. Each row carries its `File`
    and `From` (`annotation` | `declared`).
  - `Registry{Config, Files []File{Path, Owns}, Edges []Edge{Test ID,
    Source, Line, StampedAt, StampedBlob, From, File}, Rules []Rule,
    Waivers []Waiver, Units []ScannedUnit{Test ID, Line, Variants}, ext
    map[string]any}`; `ext` is the slot for the M2.4–M2.6 tables.
  - `(Registry) OwnerOf(path) (file string, err)` routes writes. Exactly one
    hand file must own the path; zero → `ErrNoOwner`, several →
    `ErrAmbiguousOwner`.
  - `(Registry) Waived(path, today) bool` ignores expired waivers.
- **`write.go`** — `WriteYAML(path string, v any) (changed bool, err)`.
  - yaml.v3 `Encoder.SetIndent(2)` behind a fixed generated-file header.
  - Compares bytes with the file on disk: equal → no write. Otherwise writes
    a temp file in the same directory and renames it, mode 0644.
  - Callers pre-sort all slices.
- **`inputs.go`** — the two injected inputs.
  - `AnnotationSource.Annotations(ctx, root) ([]FileAnnotations, error)`.
    `FileAnnotations{Path; Units []UnitAnnotation{Member, Line, Covers
    []Cover{Source, Line, StampedAt, StampedBlob}}}`; the file-level unit
    has `Member == ""`.
  - `UnitLister.List(ctx, root) ([]Listing, error)`.
    `Listing{Runner; Bound []string` (files the runner's bindings match);
    `ArtifactGlobs []string; Units []ListedUnit{ID, Kind, Lowering,
    Artifact}}`.
  - `Inputs{Annotations AnnotationSource; Lister UnitLister}`.
  - `fixtureinputs_test.go` (test-only) gives in-memory implementations.
- **`scan.go`** — `BuildScanned(cfg, anns, lists) (doc ScannedDoc, drift
  []Finding)`.
  - Drops excluded paths from both inputs.
  - Rows are the union of:
    - annotated member units
    - file-level units carrying covers
    - listed base units carrying variants (sorted unique values)
  - Covers are sorted by `(source, line)`; rows by `Test.String()`.
  - Member drift (`UNANNOTATED_MEMBER` / `DEAD_MEMBER`) comes back as
    findings. `scan --apply` refuses on them and writes nothing ("refusing
    rather than guessing").
  - `Scan(root, inputs, apply)` → `ScanResult{Units, Edges, Variants,
    Changed, Wrote, Findings}`.
  - Writes `aitestmap/registry/_scanned.yaml` with
    `{contract: 1, units: […]}` only on change, creating `registry/` when
    `aitestmap/` exists.
- **`check.go`** — the rule framework.
  - `type Severity int` (`Always`, `StrictPastBootstrap`, `Info`).
  - `Finding{Rule, Fields, Severity}`.
  - `Rule{Name, Run func(*CheckContext) ([]Finding, error)}`; a `registerRule`
    called from `init` in each rule file, so M2.4 / M2.5 / M2.6 add files,
    never edit this one.
  - `CheckContext{Root, Reg, Anns, Lists, Scanned, Strict, Today, Match}`;
    `Match` is the result of ONE `MatchFiles` call per run over every
    declared pattern (D11), keyed by pattern, each list sorted.
  - **`walk.go`** — `MatchFiles(root string, patterns, exclude []string)
    (map[string][]string, error)`: one strict `GlobWalk` per pattern over
    the exclude-aware `fs.FS` view of D11 (no custom traversal). There is no
    seam to fake it; tests use real directories.
  - Error path: an enumeration failure, an input error, or a rule's
    non-nil error aborts `Check` with a `*CheckError{Rule, Err}`
    (`Line()` → `CHECK_ERROR:<rule>|<detail>`, exit 3). No partial findings
    and no `CHECK:` line are printed after an error.
  - `Check(root, inputs, opts) (CheckResult, error)`: load → inputs → build
    the scanned doc → run rules in registration order → sort findings within
    a rule → `Failing` from severity × (`Strict` && `PastBootstrap`).
  - Injectable clock: `var now = time.Now`.
- **`rules_core.go`** — the owned rules:
  - `STALE_PATH:<test>|<source>`: an annotation or declared edge whose
    source does not exist in the working tree (`os.Stat` → `ErrNotExist`, or
    a directory). Any other `Stat` error is returned as a rule error (exit 3),
    never read as present or absent
  - `UNSTAMPED:<test>|<source>`: only when `require_stamp` && past bootstrap
  - `UNANNOTATED_MEMBER:<id>` / `DEAD_MEMBER:<file>#<member>` per D4
  - `UNREGISTERED:<path>`: a candidate (an annotated file, a `Bound` file,
    or a declared edge's test) that no listing lists; excluded paths never
  - `UNMAPPED_ARTIFACT:<path>|<runner>`: a working-tree file matching one of
    a runner's `ArtifactGlobs` that no listed unit's `Artifact` claims;
    taken from `Match[glob]` (existing files only, D11); excluded paths
    never
  - `SCAN_DRIFT:aitestmap/registry/_scanned.yaml`: the built doc's bytes ≠
    the file (absent == empty doc)
  - `OWNS_VIOLATION:<file>|<table>|<path>` per D12, over concrete paths:
    a declared edge's `covers` path matched by no `owns:` glob of its file;
    for a rule's `when` pattern or a waiver's `path` pattern, each existing
    file in `Match[pattern]` that no `owns:` glob of its file matches (the
    reported `<path>` is that concrete file). A pattern matching no file is
    not a violation. A hand file with rows and no `owns:` violates on every
    concrete path its rows reach
  - `DUPLICATE_RULE:<name>|<file>|<file>`
  - `WAIVER_EXPIRED:<path>|<until>|<file>`: info
  - `CONTRACT_MISMATCH` stays the loader's exit-3 path, not a finding
- **`--json`** — `CheckResult` / `ScanResult` marshal to
  `{status, findings:[{rule, fields, fail}], failing}` /
  `{units, edges, variants, changed, wrote, findings}`.

### Verb glue `goengines/cmd/ait-testmap/scancheck.go`

- `var testmapInputs = func() registry.Inputs { return registry.Inputs{} }`.
  A doc comment names it as the M2.2 / M3.1 extension point.
- `runScan(e, args)`: flags `--apply`, `--json`; no positionals.
  - `aitestmap/` absent → `TESTMAP_ABSENT:aitestmap/`, exit 2
  - nil input → `INPUT_UNAVAILABLE:annotations|lister` on stderr, exit 3
  - load error → its line, exit 3
  - otherwise prints the findings, then
    `SCAN:<units>|<edges>|<variants>`, then `WROTE:<path>` (apply +
    changed) or `SCAN_DRIFT:<path>` (dry run + would change)
  - exit 1 on member drift, else 0
- `runCheck(e, args)`: flags `--strict`, `--json`. Same preamble; prints the
  findings (in registration order) and then `CHECK:<pass|fail>|<n>|<failing>`;
  exit 1 iff failing > 0. A `*CheckError` (or an input error,
  `INPUT_ERROR:<input>|<detail>`) prints its line on stderr and exits 3 with
  nothing on stdout; `scan` handles input errors the same way.
- Both verbs share a testable core `scanWith(e, args, inputs)` /
  `checkWith(...)`.
- Verb rows:
  `{Name: "scan", Run: runScan, Exits: {0,1,2,3,64}}` and the same for
  `check`.

## Implementation steps

1. `cd goengines && go get github.com/bmatcuk/doublestar/v4@v4.10.0` (from
   the module cache); confirm `TestDependencyAllowlist`.
2. `id.go` + `id_test.go` (golden valid/invalid table, `String` round trip,
   `Base`).
3. `errors.go`, `config.go` + `config_test.go`:
   - defaults golden
   - every enum / range / date / glob / notes error → `REGISTRY_INVALID`
   - unknown key ignored
   - newer `contract:` → `*ContractMismatchError`
4. `load.go` + `load_test.go`:
   - merge golden: two hand files plus `_scanned.yaml` → expected tables
   - duplicate edge union
   - reserved and unknown names / keys refused
   - per-file contract refusal
   - `OwnerOf` (one, none, ambiguous)
   - `Waived` (live / expired)
5. `write.go` + test: byte-identical second write reports `changed=false`
   and leaves the mtime untouched; sorted output; atomic rename.
6. `inputs.go`, `fixtureinputs_test.go`, `scan.go` + `scan_test.go`:
   - variants persisted via the fixture lister
   - excluded paths dropped
   - re-apply byte-identical
   - member drift refuses with nothing written
7. `check.go`, `rules_core.go` + `check_test.go`, one fixture per rule
   **with a negative control** (the clean fixture emits nothing):
   - `STALE_PATH`
   - `UNSTAMPED` (only under `require_stamp` past bootstrap; absent before)
   - `UNANNOTATED_MEMBER` (and none for a file without blocks)
   - `DEAD_MEMBER`
   - `UNREGISTERED` (and never for an `exclude:` path)
   - `UNMAPPED_ARTIFACT`
   - `SCAN_DRIFT`
   - `OWNS_VIOLATION`
   - `DUPLICATE_RULE`
   - `WAIVER_EXPIRED`
   - **ownership (D12)**: owns `src/*` + rule `when: [src/**]` with
     `src/deep/x.go` on disk → `OWNS_VIOLATION` naming `src/deep/x.go`;
     owns `src/[ab].go` + rule `when: [src/[ab].go]` with `src/a.go` →
     no violation; the same two cases for a waiver `path`; a `when`
     pattern matching no file → no violation; a declared edge `covers`
     outside `owns:` → violation
   - **walk semantics (D11)** in `walk_test.go` and through `check`, in a
     real `fixture.New` repo: a tracked artifact committed then deleted from
     disk is **not** reported; an existing **gitignored** file matching the
     runner's `artifact_glob` **is** reported `UNMAPPED_ARTIFACT`; an
     `exclude:`d file is not; **nested repository**: with
     `artifacts/vendor/.git` present, both `artifacts/**/*.json` and
     `artifacts/vendor/**/*.json` discover `artifacts/vendor/b.json`
     (monotonic), and `exclude: [artifacts/vendor/**]` removes it from both
   - **error propagation (D11), real filesystem, no fakes**: an unreadable
     (`0o000`) directory under an `artifact_glob` base, a `when` base and a
     waiver base → `MatchFiles` returns an error naming the directory;
     through `run()` `check` and `check --strict` exit 3, print
     `CHECK_ERROR:` on stderr and **no `CHECK:` line** (stdout empty). The
     same directory covered by `exclude: [<dir>/**]` → hidden, no error.
     **Shallow pattern, unreadable irrelevant descendant**: `artifact_glob:
     artifacts/*.json` with readable `artifacts/a.json` and an unreadable
     `artifacts/cache/` → no error, `a.json` reconciled (the cache is never
     opened); the same tree with `artifacts/**/*.json` → exit 3
     `CHECK_ERROR:` (the cache is relevant).
     A `Stat` permission error on a covered source → exit 3, not
     `STALE_PATH` and not pass. Permission cases `t.Skip` only when euid is
     0 (permissions not enforced), and restore modes in `t.Cleanup`. An
     annotation source / lister returning an error → `INPUT_ERROR:` exit 3
     for both verbs
   - plus the severity matrix: (strict on/off) × (before/past bootstrap) ×
     each severity
8. `cmd/ait-testmap/scancheck.go`; replace the two stub rows in `verbs.go`;
   add `scan` / `check` to `TestStubsExit64`'s skip list.
   `scancheck_test.go`, through `run()`, the real entry point:
   - `TESTMAP_ABSENT` exit 2
   - `INPUT_UNAVAILABLE` exit 3 with production wiring
   - `CONTRACT_MISMATCH` exit 3 for a newer `_scanned.yaml` / hand file /
     `config.yaml`
   - `REGISTRY_INVALID` exit 3
   - `check` pass (0) / fail (1) / `--strict` flip
   - `scan --apply` writes, then the re-run is byte-identical with no
     `WROTE:`
   - `--json` shapes
   - usage (64)

   Inputs are injected by temporarily swapping `testmapInputs`.
9. Benchmarks: `registry.BenchmarkScan` and `registry.BenchmarkCheck` on a
   generated **aitasks-shape** fixture (≈420 test files, ≈600 sources on
   disk, 1–3 covers each, ≈5 % member files with variants, one artifact glob
   over ≈300 files), built once in `b.TempDir()` with in-memory inputs, so the measured path includes the scoped `MatchFiles` walk. Then
   `taskset -c 0 go run ./internal/tools/benchgate -baseline bench/baseline.txt -update`,
   and add `budget=300ms` to both new lines.
10. `gofmt -l .` empty, `go vet ./...`, `go test ./...` (incl.
    `guards_test.go`), `go run ./internal/tools/benchgate -baseline bench/baseline.txt`
    (the full gate).
11. Proposal edit (documentation, path-scoped commit):
    - *Registry loader and writer* gains one paragraph fixing the hand-file
      schema, the union merge rule, `owns:` over source paths and the
      reserved file names
    - *Enumeration and reconciliation* gains the strictness table (D5) and
      the new line classes (D2)
    - the *Line-protocol index* check row lists them
    - `goengines/README.md` *Interfaces* gains `scan` and `check` rows
      pinned by their tests

### Post-phase (risk mitigations)

1. [command_level_injection_proof] In `scancheck_test.go`, drive `scan` and
   `check` through `run()` with fake providers swapped into `testmapInputs`.
   Assert that a fake annotation source's covers and a fake lister's variants
   reach `_scanned.yaml`, and that removing a provider flips to
   `INPUT_UNAVAILABLE` exit 3. This proves the M2.2 / M3.1 plug point at
   command level, not only at API level.
2. [interface_notes_downstream] After the commit, send hedged
   `./ait note` messages (citing the commit sha):
   - t1853_2: `AnnotationSource`, the `testmapInputs` wiring, stamp fields
   - t1853_4, t1853_5, t1853_6: the registration points and reserved names
   - t1854: the `UnitLister` / `Listing` shape for M3.1
   - t1859: the `check` exit and strictness table for M8.2
   Note that no human step was met that needs reporting.

## Verification

- `ait engine test` (`go vet` + `go test` over `goengines/`) green; `gofmt`
  clean; the Invariants 4–5 tripwire and the dependency allowlist pass.
- Golden tests for the core merges and the id grammar (member and variant
  fragments).
- One fixture per owned check rule, each with a negative control, and the
  severity matrix.
- Ownership is judged over concrete matched paths: the `src/**`-escapes and
  `src/[ab].go`-self cases both behave correctly (D12).
- A failed inspection can never yield `CHECK:pass`: a real unreadable
  directory under a declared pattern, a `Stat` failure and an input error all
  exit 3 with no `CHECK:` line (D11); every `GlobWalk` passes
  `WithFailOnIOErrors()`, and no git inventory is used for the universe.
- The universe is existing files reached by the declared patterns: a
  deleted tracked artifact is not reported, an existing ignored artifact is,
  a nested repository's files are found by broad and narrow patterns alike,
  and only `exclude:` removes files (`.git` metadata is never a work-tree
  file). A shallow pattern never opens an irrelevant unreadable descendant.
- A newer `contract:` in any registry file → `CONTRACT_MISMATCH` exit 3.
- Re-`scan --apply` with no change is byte-identical and prints no `WROTE:`.
- `exclude:` paths are never listed and never `UNREGISTERED`.
- `scan --apply` persists `variants:` via a fixture lister;
  `UNMAPPED_ARTIFACT` via a fixture `artifact_glob:`.
- Bench `scan` / `check` < 300 ms on the aitasks shape, baseline recorded; the
  full benchgate passes.
- No path shipped here requires a human action (automation-first): no verb
  waits on a person, and `by:` is untouched here.

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9 (archival on the
current branch, no merge).

## Risk

### Code-health risk: medium
- The new line classes (`REGISTRY_INVALID`, `INPUT_UNAVAILABLE`, `OWNS_VIOLATION`, `DUPLICATE_RULE`, `WAIVER_EXPIRED`, `SCAN_DRIFT`, `SCAN`, `CHECK`) become a protocol later modules parse; an ill-fitting shape costs rework downstream · severity: medium · → mitigation: plan step 11 (proposal + README Interfaces record them; additive-only extension rule)
- `benchgate -update` re-records every existing baseline line on this host; an unpinned recording would shift unrelated benchmarks' thresholds · severity: low · → mitigation: plan step 9 (pinned `taskset -c 0`, full gate re-run in step 10)

### Goal-achievement risk: medium
- (review findings, fixed in plan) A check that cannot read the tree, enumerates a universe other than the existing files, or misjudges ownership could print `CHECK:pass` on an unverified registry · severity: high before fix, low residual · → mitigation: plan D11/D12 design + their step-7 tests
- The two injection interfaces (`AnnotationSource`, `UnitLister`) are designed before M2.2 and M3.1 exist; a shape that does not fit them, or a plug point that only works at API level, would force those children to rework `scan` / `check` · severity: medium · → mitigation: inline post-phase command_level_injection_proof
- Registry schemas and the merge rule are taken from the brainstorm lineage because the final proposal only names them; M2.4–M2.6 and M4.1 (rules / waivers semantics) may assume otherwise · severity: medium · → mitigation: inline post-phase interface_notes_downstream
- The strictness classification (D5) may not match what M8.2's `testmap_check` verifier expects · severity: low · → mitigation: inline post-phase interface_notes_downstream

### Planned mitigations
- timing: post-phase | name: command_level_injection_proof | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — injection interfaces unproven at command level before M2.2/M3.1 exist | desc: drive scan/check through run() with fake providers swapped into testmapInputs; assert data reaches _scanned.yaml and a missing provider yields INPUT_UNAVAILABLE exit 3
- timing: post-phase | name: interface_notes_downstream | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — lineage-derived schemas / strictness table diverging from downstream assumptions | desc: hedged ./ait notes to t1853_2, t1853_4, t1853_5, t1853_6, t1854, t1859 naming the landed interfaces with the commit sha

## Post-Review Changes

### Change Request 1 (2026-10-12 08:40)
- **Requested by user:** three blocking review findings — (1) `checkUnmappedArtifact` counted artifact claims from units of `exclude:`d tests, so an excluded claimant hid a real `UNMAPPED_ARTIFACT`; (2) `excludeFS.Stat`/`ReadDir` followed a directory symlink in a glob's literal prefix (`WithNoFollow` only governs links the walk meets as entries), making the universe depend on the pattern's spelling and reach outside the repository; (3) a rule's `select:` member half (`tests/a.py#[`) was never validated.
- **Changes made:** each reproduced red first with a regression test, then fixed. (1) units whose test path is `exclude:`d claim nothing. (2) the view's `Stat` walks every component above the name with `fs.Lstat`: a hidden, symlinked or non-directory component makes the name absent, the name itself is described by `Lstat` (a link is a link), any other error is returned; `ReadDir` refuses a non-directory. Broad and narrow patterns through a symlinked directory now both match nothing. (3) `checkSelect` validates `<path glob>[#<member glob>]` — both halves well-formed globs, no `#`/`@`/`|`/whitespace, no `/` in the member — refusing with `REGISTRY_INVALID`. Benchmarks re-recorded (check ≈ 24 ms, scan ≈ 22 ms, budget 300 ms).
- **Files affected:** `goengines/internal/testmap/registry/{rules_core.go,walk.go,load.go,check_test.go,walk_test.go,load_test.go}`, `goengines/bench/baseline.txt`.

## Final Implementation Notes

- **Actual work done:**
  - New package `goengines/internal/testmap/registry`:
    - `id.go`: id grammar `ParseID` / `String` / `Base` / `Valid` / `CheckPath`
    - `config.go`: `Config` with every key and its default; `LoadConfig` / `ParseConfig`, validation, `Excluded`, `PastBootstrap`, `HostClass`
    - `errors.go`: `InvalidError` → `REGISTRY_INVALID`; `CheckError` → `CHECK_ERROR`
    - `load.go`: `Load`; hand files `{contract, owns, edges, rules, waivers}`; the union merge rule; reserved files and tables; `RegisterFile` / `RegisterHandTable`; `OwnerOf`; `Waived`
    - `write.go`: deterministic `Render`; atomic `WriteFile`, which writes only on change
    - `inputs.go`: `AnnotationSource`, `UnitLister`, `Inputs`; `INPUT_UNAVAILABLE` / `INPUT_ERROR`; validation of what providers return
    - `scan.go`: `BuildScanned` (rows, variants, member drift) and `Scan`
    - `walk.go`: `MatchFiles`, strict doublestar `GlobWalk` over an exclude-aware, no-follow `fs.FS` view
    - `check.go`: rule framework, `RegisterRule`, `Check`, severities
    - `rules_core.go`: the ten owned rules
  - Verb glue `cmd/ait-testmap/scancheck.go`, with the `testmapInputs` wiring point. The `scan` and `check` rows in `verbs.go` are now real.
  - Benchmarks `BenchmarkScan` / `BenchmarkCheck` (≈22 / 24 ms; `budget=300ms`).
  - Proposal: the registry file format, the merge rule, ownership and the `scan` / `check` contract with its severity table; the line-protocol index row.
  - README: *Layout* row, plus *Interfaces* rows for `scan` and `check`.
- **Deviations from plan:**
  - `Scan` / `Check` load the registry before checking inputs. So a broken registry reports `REGISTRY_INVALID` / `CONTRACT_MISMATCH` ahead of `INPUT_UNAVAILABLE`; both are exit 3.
  - `ScanResult` / `CheckResult` findings carry a `fail` flag, so `--json` consumers need no severity table.
  - The candidate universe changed twice during plan review, ending at D11: strict `GlobWalk`, no-follow, exclude-aware view, no git inventory.
- **Issues encountered:**
  - yaml.v3 quotes YAML 1.1 booleans such as `"y"` and digit-only blobs (`"0123456789"`). Goldens pin that. Unquoted dates decode into string fields fine.
  - `benchgate -update` always re-records every line (no partial update). The baseline file therefore shows re-measured existing lines, recorded with `taskset -c 0`.
  - Review round 1 found three real defects (see *Post-Review Changes*); each was red-proved and fixed.
- **Key decisions:**
  - `owns:` globs apply to **source** paths and are judged over concrete existing files, never one pattern against another.
  - An absent `bootstrap_until` means no bootstrap window.
  - An expired waiver is informational and stops waiving.
  - `UNANNOTATED_MEMBER` applies only to files with ≥ 1 `testmap:unit` block.
  - `SCAN_DRIFT` is structural: it fails under `--strict` past bootstrap.
  - A rule `select:` cannot name a variant.
  - `.git` entries are never part of the work tree; nested checkouts are in scope unless `exclude:` names them.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - **M2.2 (t1853_2):** implement `registry.AnnotationSource`. Stamps arrive parsed (`StampedAt`, `StampedBlob`); the file-level unit has `Member == ""` and comes first. Wire it by setting `Annotations` in `testmapInputs()` in `cmd/ait-testmap/scancheck.go`. Note that `readInputs` refuses invalid paths and members.
  - **M2.4 / M2.5 / M2.6:**
    - Add tables with `RegisterHandTable` (`scopes` / `areas` are reserved for M2.5) or `RegisterFile` (`_scoped.yaml`, `areas.yaml`, `observed.yaml`, `seeded.yaml`, `adopted.yaml` are reserved and refused until registered).
    - Keep loaded data in `Registry.Ext`.
    - Add rules with `RegisterRule` from an `init` in your own file. A rule that judges patterns declares them in `Patterns`, so it shares the run's single `MatchFiles` pass, and it returns an error, never a guess, when it cannot inspect.
  - **M3.1:** implement `registry.UnitLister`. `Listing{Runner, Bound, ArtifactGlobs, Units[{ID, Kind, Lowering, Artifact}]}`; `Bound` feeds `UNREGISTERED`.
  - **Tests:** use `t.Chdir` plus a swapped `testmapInputs` to drive the verbs through `run()`. `fixtureinputs_test.go` has in-memory fakes and `cleanRepo`.
