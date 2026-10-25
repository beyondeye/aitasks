---
Task: t2131_3_modules_table_and_core_providers.md
Parent Task: aitasks/t2131_testmap_code_modules_tier.md
Sibling Tasks: aitasks/t2131/t2131_2_*.md, aitasks/t2131/t2131_4_*.md … aitasks/t2131/t2131_12_*.md
Archived Sibling Plans: aiplans/archived/p2131/p2131_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-25 09:03
---

# Plan: t2131_3 — Modules table, codemap and Gradle providers, `modules` verb

## Context

Child 3 of t2131 (the test-map code-module tier), work package **M2.7 — Code
modules**. It lands the flat **modules table** (`aitestmap/registry/_modules.yaml`
plus the hand `modules:` block), path → module ownership, the codemap and
Gradle providers, module → module `deps:` evidence, the `modules` verb, and the
`MODULE_CONFLICT` / `MODULES_DRIFT` check rules. Go/Python providers are
t2131_4, membership t2131_5, reach t2131_6. The contract is the proposal's
component *Code modules* (`aidocs/testing_engine/n014_explorer_006_proposal.md`
3050-3283, schema row 444, verb list 2123-2131, landed by t2131_1).
Automation-first: no human step; agent rows keep `by:`.

## Step 0 — Reality check (verified 2026-10-25, main @ f50f4ac3a)

| anchor | state |
|---|---|
| `registry/scoped.go` | areas/scopes hand tables + `_scoped.yaml` loader at 404-412 (`init`), `checkAreaName` 334-342, `WithGenerated` 172-185 — as planned |
| `registry/scan.go` | `generatedDrift` 196-208, drift-gated writes 217-287 — as planned |
| `registry/areas_import.go` | `ReadCodemap` 79-126 decodes `codemapDoc`, flattens, requires unique names — reused only for its decoder; `areas --import-codemap` unchanged |
| `deps/graph.go` | `Modules()` / `ModuleOf()` / `within` 119-155; root project `:` has `Dir ""` |
| `deps/gradle.go` | `m.Deps = allNames()` at 272; dynamic surfaces as `Problem{Reason: "gradle-dynamic: …"}` on the settings or build file. **The build-file loop (204-209) also creates a record for every build-file directory no settings file includes** (`examples/demo/build.gradle.kts`), and `GradleModule` carries no provenance — so `g.Modules()` is *not* "the included projects" |
| file universe | `buildUniverse` (`deps/scan.go:69-94`) keeps every git-visible file minus `exclude:`, missing files and anything reached through a symlink or not regular; **`rawPhase` (229-241) then drops every file with no scanner kind**, and `Graph.Files()` lists only the scanned ones — JSON, Markdown, config and unsupported sources are absent. The full universe is not exposed |
| root validation | `checkPath` (`registry/id.go:99`) accepts `:` and glob metacharacters, so it cannot stand in for the module-name rule on a root |
| `axes/axes.go:352-376` | a package above `registry` registering into it from `init` — the pattern for the inference hook below |
| `cmd/ait-testmap/main_test.go` | `proposalVerbs` lacks `modules`; proposal places it after `runner`, before `version` (`policy` is M8.4's, not in the table yet) |
| `check` | never scans `deps` today; CLI tests run `check` in **non-git** temp dirs (`repo(t)`), and `deps.Scan` needs git — so drift must not scan unconditionally |
| import direction | `registry` needs no `deps` import: ownership is pure path arithmetic over the table; the live re-inference reaches `check` through a hook the `modules` package registers |
| budgets | `BenchmarkCheck` 21.8 ms, `deps.BenchmarkScanWarm` 116 ms (budget 300 ms for `check`) |

Still to measure at implementation start (step 1): `check` + `MODULES_DRIFT`
on an aitasks-shaped fixture with a codemap and Gradle projects, and provider
overlap on the combined fixture.

## Decisions this child fixes (written into the proposal in step 9)

1. **Drift is judged only for a declared table.** `MODULES_DRIFT` and
   `MODULE_CONFLICT` run the live inference only when the registry declares a
   modules table — a committed `_modules.yaml` (even empty) or a hand
   `modules:` block. A repository that never opted in has no table to drift;
   its consumers see every path unmapped and fall back to full. This keeps
   `check` unchanged (and git-free) for every registry without a table.
2. **`deps:` are a function of the persisted rows only** (generated + agent),
   never of hand modules, so a hand edit never drifts the generated file. Hand
   overrides apply at load.
3. **A hand module declaration accepts only `paths`.** Any other key in
   `{<name>: {…}}` (`submodules:`, `children:` included) is `REGISTRY_INVALID`.
4. **`--explain` of an unmapped path** prints `MODULE_OF:<path>||unmapped`.
5. **`deps:` are shown only in `--json`** (no new line class).
6. **Equal roots within one subtree provider** tie-break to the smallest name
   (their path sets are identical, so no conflict line).
7. **Two inputs, never conflated.** Ownership, effective-table membership,
   `members_n` / `unmapped_n`, conflicts and the hand-overlap refusal are
   computed over the **complete file universe** (`Graph.Universe()`, new: the
   same filtered list the scan starts from, unscanned kinds included).
   Dependency facts (`Facts`) are a separate input used only for `deps:`.
8. **Gradle modules are declared projects only.** A record that exists only
   because a build file sits in a directory no settings file includes is no
   module (its files stay unmapped). Provenance comes from a new
   `GradleModule.Declared` set in the settings loop (the settings directory's
   own project and every `include`).
9. **A root is validated by the directory rule, independently of the module
   name.** Every subtree and package root must pass `NativeID` (each component
   passes the area-name rule and holds no `:`) — so a valid Gradle path with a
   `projectDir` like `odd:dir` is `MODULE_REFUSED:gradle|odd:dir|unnameable`.
   One function serves the loader and the providers.

## Implementation steps

### Pre-phase (risk mitigations)
1. [characterize_check_without_table] Before editing `registry/check.go`, add
   `cmd/ait-testmap/modules_characterize_test.go`: pin the exact stdout,
   stderr and exit code of `check` and `check --json` on (a) the `repo(t)` +
   `fakes()` fixture (non-git dir, no modules table) and (b) a `fixture.New`
   git repository carrying a codemap with nested entries and a
   `settings.gradle.kts` but no `_modules.yaml` and no hand `modules:` block,
   recording the expected strings from the current engine. Also assert, with
   a counting hook registered for the test, that the module inference is
   never called in either case. The file stays green, unchanged, after
   steps 2–5.

### 1. Measure (Step 0 completion)
- Add `internal/testmap/modules/bench_test.go`:
  `BenchmarkCheckModulesDrift` — an aitasks-shaped git fixture (≈600 sources,
  ≈420 tests, a codemap with nested entries, a `settings.gradle.kts` with a few
  projects, a committed `_modules.yaml`) running `registry.Check` warm with the
  modules package linked. Budget 300 ms.
- Overlap measurement on the combined fixture: count, per provider pair, the
  paths both claim (from `Resolve`'s claimant sets over `Universe()`).
- If over budget: move `MODULES_DRIFT` / `MODULE_CONFLICT` out of `check`
  (consumers only, `modules --scan` still reports both), and record that in the
  proposal instead of decision 1. Record the measurement and overlap counts in
  this plan.

### 1b. `deps`: expose the universe and Gradle provenance (additive)
- `deps/graph.go` / `deps/scan.go`: `Graph.universe` set from `u.list` in
  `Scan`; `(*Graph).Universe() []string` (sorted copy). `Files()` is
  unchanged.
- `deps/deps.go` / `deps/gradle.go`: `GradleModule.Declared bool`
  (`json:"declared,omitempty"`), set to true on the module the settings loop
  creates or returns for the settings directory and for every `include`;
  build-file-only records stay false. No cache schema change (modules are
  built in memory each scan).
- Tests in `deps`: `TestUniverseIncludesUnscannedFiles` (a `.json`, a `.md`
  and an unsupported source are in `Universe()` and absent from `Files()`; an
  excluded file, a symlinked file and a non-regular file are in neither);
  `TestGradleDeclaredProvenance` (settings `include(":app")` plus an unlisted
  `examples/demo/build.gradle.kts`: `:app` and `:` declared, `:examples:demo`
  not).

### 2. Registry: table, loader, renderer, lookup — `registry/modules.go` (new)
- Constants: `ModulesPath = RegistryDir + "/_modules.yaml"`, `ModulesHeader =
  "# Generated by ait-testmap modules --scan --apply. Do not edit: re-run the scan.\n"`,
  providers `ProviderHand|Agent|Codemap|Gradle|Go|Python`
  (`hand`, `agent`, `codemap`, `gradle`, `go`, `python`) with `ProviderRank`
  (1, 2, 3, 4, 5, 5) and kinds (glob / subtree / package), reserved prefixes
  `codemap:`, `gradle:`, `go:`, `py:`.
- Generated doc (decoded with `KnownFields(true)`):
  ```go
  type ModulesDoc struct {
      Contract int         `yaml:"contract"`
      Modules  []ModuleRow `yaml:"modules,omitempty"`
  }
  type ModuleRow struct {
      Name     string      `yaml:"name"`
      Provider string      `yaml:"provider"`
      By       string      `yaml:"by,omitempty"`
      Root     string      `yaml:"root,omitempty"`
      Paths    []string    `yaml:"paths,omitempty,flow"`
      Gradle   string      `yaml:"gradle,omitempty"`
      Evidence []string    `yaml:"evidence,omitempty,flow"`
      Deps     []ModuleDep `yaml:"deps,omitempty"`
  }
  type ModuleDep struct {
      Module   string      `yaml:"module"`
      Evidence DepEvidence `yaml:"evidence,flow"`
  }
  type DepEvidence struct{ From, To string } // yaml from / to
  ```
  `RenderModules(doc)` = `Render(ModulesHeader, doc)`.
- Name rule helpers: `checkModuleName` (= `checkAreaName` + no reserved prefix,
  for hand/agent names); `NativeID(dir) (string, bool)` (`""`→`.`; components
  joined by `:`; false when a component contains `:` or fails `checkAreaName`)
  and `GeneratedName(provider, root, gradle)` — shared with the providers so
  load-time validation and inference use one rule. `ValidRoot(provider, root)`
  = structural `checkPath` **and** `NativeID` ok (`.` only for go/python),
  applied to every subtree/package root regardless of how the name is formed
  (the Gradle name comes from the Gradle path, its root from `projectDir`).
- Row validation (`validateModuleRow`, used by the loader **and** by the
  providers before anything is written, as `BuildScoped` does): provider in the
  enum; `agent` → name passes `checkModuleName`, `by` = `agent:<non-empty>`,
  ≥1 `paths` each `checkScopeGlob`, no `root`/`gradle`; subtree/package
  providers → `ValidRoot(provider, root)`, name == `GeneratedName(...)`, no
  `paths`/`by`; gradle name segments pass the area-name rule; `gradle` requires
  `gradle: ":<a>[:<b>…]"`; deps name modules of the same file, evidence paths
  pass `checkPath`; duplicate names refused.
- Loader: `init()` → `RegisterFile("_modules.yaml", loadModulesFile)` and
  `RegisterHandTable("modules", loadModulesTable)`. The hand decoder walks the
  mapping node: each value must be a mapping whose only key is `paths`
  (scalar or list, ≥1 glob, `checkScopeGlob`); name `checkModuleName`; globs
  unioned per name across hand files with the declaring files kept (like
  `addArea`).
- `Modules` (in `reg.Ext["modules"]`, `ModulesOf(reg)` never nil):
  `Committed bool`, `Doc()` (the persisted doc), `Hand()`, `Declared()`
  (committed file or ≥1 hand module), `WithGenerated(doc)` (keeps hand,
  replaces rows — the live view), `WithoutHand()`.
- `OwnerOf(path) (name string, err error)` — universe-free, for t2131_5/6/10:
  hand globs (two hand modules matching → `*InvalidError`), else agent globs
  (two → `*InvalidError` on `ModulesPath`), else the deepest codemap root,
  else the deepest Gradle root, else a package row whose `root` is the path's
  directory and whose extension matches (`*.go`; `*.py`/`*.pyi`) — the package
  arm is implemented now so t2131_4 adds only providers. An agent row whose
  name a hand module takes is dropped before lookup.
- `Resolve(files []string) (*Resolution, error)`:
  `Resolution{Modules []EffectiveModule (name-sorted, ≥1 member), Owner
  map[string]string, Unmapped int, Conflicts []Conflict}`. Per path: every
  claimant (provider-local claim: a subtree row claims only paths no deeper
  same-provider root covers), owner = best rank. Conflict pairs aggregate
  `(owner, other claimant)` per path → `Conflict{Winner, WinnerProvider,
  Loser, LoserProvider, Paths, First}`, dropped when the two provider-local
  claimed sets are identical; plus one per hand/agent name collision
  (paths = the agent row's matches). Sorted by (winner, loser).

### 3. Registry: check rules — `registry/rules_modules.go` (new)
- Hook: `type LiveModules struct{ Doc ModulesDoc; Files []string }` (`Files` =
  the complete universe, decision 7),
  `type ModuleInference func(ctx context.Context, root string, reg *Registry) (*LiveModules, error)`,
  `RegisterModuleInference(f)`.
- `check.go`: add an unexported `ctx` to `CheckContext` (set in `Check`), a
  per-run memo of the live inference, and pass a rule's `*InvalidError`
  through like `*InputError` (a hand overlap prints `REGISTRY_INVALID`, exit 3).
- `MODULES_DRIFT:aitestmap/registry/_modules.yaml` (StrictPastBootstrap, like
  `SCAN_DRIFT`): `RenderModules(live.Doc)` vs the committed bytes through
  `generatedDrift`. `MODULE_CONFLICT:<winner>@<p>|<loser>@<p>|<paths_n>|<first>`
  (Info) from `ModulesOf(reg).WithGenerated(live.Doc).Resolve(live.Files)`.
- Both no-ops unless `Declared()`; declared with no hook registered →
  `CheckError{Rule: "MODULES_DRIFT"}` (fail closed).

### 4. The `modules` package — `internal/testmap/modules/` (new)
- `modules.go`: the driver.
  ```go
  type Refusal struct{ Provider, Root, Reason string } // unnameable | repository_root
  type Input struct{ Root string; Reg *registry.Registry; Graph *deps.Graph }
  type Provider struct{ Name string; Rows func(Input) ([]registry.ModuleRow, []Refusal, error) }
  func RegisterProvider(p Provider)                         // t2131_4 adds go / python
  type Result struct{ Doc registry.ModulesDoc; Refused []Refusal; Files []string /* g.Universe() */; Graph *deps.Graph }
  func Infer(in Input) (*Result, error)                      // providers + carried agent rows + deps
  func Scan(ctx context.Context, root string, reg *registry.Registry) (*Result, error) // deps.Scan(Config) + Infer
  ```
  `agent` rows are copied verbatim from `ModulesOf(reg).Doc()`. Every row passes
  `validateModuleRow` (exported as `registry.ValidateModuleRow`). Rows sorted by
  name; refusals by (provider rank, root). `init()` registers `Scan` as the
  registry's `ModuleInference`.
- `codemap.go`: reads `aitasks/metadata/code_areas.yaml` through a new
  `registry.ReadCodemapEntries(root) ([]CodemapEntry{Name, Path}, error)` that
  shares `ReadCodemap`'s decoder (absent → no rows; malformed / version ≠ 1 /
  a structurally invalid path / a name with `|` or a control char →
  `INPUT_ERROR:code_areas`). Every entry at any depth → `codemap:<NativeID>`,
  root = path without the trailing `/`; entries sharing a path merge into one
  row; evidence `entry:<name>…`; root `""`/`.` →
  `MODULE_REFUSED:codemap|.|repository_root`; `a:b/` or a name-rule failure →
  `MODULE_REFUSED:codemap|a:b|unnameable`.
- `gradle.go`: every `g.Modules()` project with `Declared` (decision 8;
  build-file-only records are skipped, their files unmapped); `Dir == ""`
  (root `:` and any project moved to the root) →
  `MODULE_REFUSED:gradle|.|repository_root`; a project segment failing the
  name rule, or `!ValidRoot(gradle, Dir)` (e.g. `odd:dir`) →
  `MODULE_REFUSED:gradle|<Dir>|unnameable`. Row: `gradle:<path without
  leading :>`, root = `Dir` (so a `projectDir` override is honoured),
  `gradle: <Gradle path>`, evidence `settings:<deepest settings file whose
  directory contains Dir>`, `build:<BuildFile>` (only when the build file lies
  under `Dir` — see the upstream note below), and `gradle-dynamic` when that
  build or settings file has a `gradle-dynamic:` problem. No folding, no
  expansion.
- `deps.go`: resolve the persisted rows (`WithoutHand`) over `g.Universe()`; for
  every edge of every file owned by generated row A whose target is owned by
  B ≠ A, keep the smallest `(from, to)` pair per (A, B); sorted by module.
- `bench_test.go` from step 1.

### 5. The `modules` verb — `cmd/ait-testmap/modules.go` (new)
- `modules [--list] [--json]` (default): committed effective table over the
  complete universe (`deps.Scan` → `Universe()`) → `MODULE:<name>|<provider>|<root or globs,…>|<members_n>|<evidence,…>`
  per effective module, then `MODULES:<n>|<unmapped_n>|<provider>=<n>,…`
  (providers with ≥1 module, rank order).
- `modules --explain <path> [--json]`: `MODULE_OF:<path>|<name>|path`, or
  `MODULE_OF:<path>||unmapped`; no scan (`OwnerOf` only). Invalid path → 64.
- `modules --scan [--apply] [--json]`: `MODULE_REFUSED:` lines,
  `MODULE_CONFLICT:` lines, `MODULE:` lines and `MODULES:` for the live table,
  then `WROTE:aitestmap/registry/_modules.yaml` (applied and changed) or
  `MODULES_DRIFT:aitestmap/registry/_modules.yaml` (dry run, would change).
  Write only when changed (`generatedDrift` + `WriteFile`); a `REGISTRY_INVALID`
  from `Resolve` writes nothing.
- `--json` emits the full rows (deps included). Exits `0 · 2 (TESTMAP_ABSENT) ·
  3 · 64`; `--apply` only with `--scan`; the three modes are exclusive.
- `verbs.go`: insert `{Name: "modules", Run: runModules, Exits: modulesExits}`
  between `runner` and `version`.

### 6. Tests
- `registry/modules_test.go`: `testdata/modules/_modules.yaml` load → render
  golden (byte-identical); refusals table (unknown field, bad provider, name ≠
  generated name, agent without `by:`, reserved prefix on a hand name and an
  agent name, `submodules:` / `children:` / any non-`paths` key in a hand
  decl, glob metacharacter in a name, duplicate names, a `deps` naming an
  unknown module); a `provider: agent` row loads; ownership table (hand >
  agent > codemap > Gradle; deepest root; equal roots; package arm; refinement
  `api` over `services/api/public/**` reported once; identical sets not
  reported; a zero-member module absent; hand/agent name collision; two hand
  modules on one path → `REGISTRY_INVALID`).
- `registry/rules_modules_test.go`: with a fake hook — undeclared → hook not
  called; `MODULES_DRIFT` **negative control** (fresh table: no line; one
  changed row: the line; red if the comparison is removed); `MODULE_CONFLICT`
  Info; declared without a hook → `CHECK_ERROR`.
- `modules/*_test.go` (git fixtures, private `XDG_CACHE_HOME`): codemap with
  duplicate entry names across parents (`a/tests/`, `b/tests/` →
  `codemap:a:tests`, `codemap:b:tests`); root entry refused; `a/b`→`codemap:a:b`,
  `a.b`→`codemap:a.b`, `a:b` refused; malformed codemap; Gradle `projectDir`
  override; `gradle-dynamic` flagged; root `:` refused
  (`MODULE_REFUSED:gradle|.|repository_root`); worked example 4
  (`services/payments/api/src/A.kt` owned by `gradle:services:payments:api`,
  `gradle:services` never by nesting, root `build.gradle.kts` unmapped);
  combined codemap + Gradle + hand fixture (precedence + `MODULE_CONFLICT`);
  `deps:` evidence pair; **unscanned files** — a codemap entry and a hand
  module containing only `config.json` / `README.md` / an unsupported source
  are effective with the right `members_n` and `unmapped_n`; **Gradle
  provenance** — settings `include(":app")` plus an unlisted
  `examples/demo/build.gradle.kts`: `gradle:app` exists, no
  `gradle:examples:demo`, `examples/demo/**` unmapped; **root validation** —
  `include(":api")` with `project(":api").projectDir = file("odd:dir")` →
  `MODULE_REFUSED:gradle|odd:dir|unnameable` and no `gradle:api`; the loader
  refuses a hand-edited `_modules.yaml` row with that root.
- `cmd/ait-testmap/modules_test.go`: exact-line tests for `--list`,
  `--explain` (owned / unmapped / invalid), `--scan`, `--scan --apply`
  (`WROTE:` then a re-run with no write and no drift), usage, absent registry;
  `check` printing `MODULES_DRIFT` after a codemap edit and not before;
  **hand overlap on an unscanned file only** — two hand modules whose globs
  meet only on `conf/app.json`: `--explain conf/app.json`, `--list`,
  `--scan --apply` and `check` all exit 3 with the same `REGISTRY_INVALID`
  line, and `_modules.yaml` is not written; and list/explain consistency — for
  every path of a mixed fixture, `--explain`'s owner is the module whose
  `members_n` counts it.
- `main_test.go`: `proposalVerbs` gains `modules` (after `runner`);
  `TestStubsExit64`'s implemented list gains `modules`.
- `bench/baseline.txt`: the new benchmark line with `budget=300ms`.

**Upstream defect to record (not fixed here):** `deps/gradle.go:204-209` —
a build file whose directory maps by `moduleNameOf` onto an existing project
name with a different `projectDir` (e.g. `include(":api")` moved to
`services/api` plus a stray `api/build.gradle.kts`) is attached to that
project as its `BuildFile` through `addModule`'s by-name return. The provider
guards its `build:` evidence; the misattribution itself (which also feeds
`sourceEdges`) goes to the Final Implementation Notes for a follow-up.

### 7. README (`goengines/README.md`)
- Layout row `internal/testmap/modules` (above `deps`: providers, inference,
  `deps:` evidence, the check hook); the registry row mentions the modules
  table.
- The "dependency graph" row gains `Universe()` and `GradleModule.Declared`.
- Interface rows: "modules table (M2.7)" (schema, hand block, names, rank,
  ownership, `OwnerOf` / `Resolve`), "M2.7 check rules", "`modules`" verb —
  each with its test names.

### 8. Gates
`cd goengines && test -z "$(gofmt -l .)" && go vet ./... && ./ci/preflight.sh && go test ./...`;
the benchmark gate run for the new line.

### 9. Proposal amendment
In component *Code modules*: decisions 1–9 above (one short paragraph each
where they refine the text — drift gating, `deps:` scope, strict hand decl,
the unmapped `MODULE_OF:` form, `deps:` in `--json`, equal-root tie-break),
plus the measured budget if it moved drift out of `check`. Then send advisory
notes (`/aitask-note`) to t2131_4, t2131_5, t2131_6 and t2131_10 naming the
APIs they consume (`ModulesOf`, `OwnerOf`, `Resolve`, `RegisterProvider`,
`modules.Scan` drift) and decisions 1–2.

## Verification

`ait engine test` green, plus every item in step 6; `modules --scan --apply`
is idempotent (second run: no `WROTE:`, no drift); `check` output is
byte-identical for every existing CLI fixture (no table declared).

## Risk

### Code-health risk: low
- `check.go` is shared by every check rule; the new `ctx` field, the inference memo and the `*InvalidError` passthrough could change `check` output or exit codes for registries that declare no modules table (the CLI fixtures run in non-git dirs, where a stray `deps.Scan` fails) · severity: low (residual — addressed by inline pre-phase characterize_check_without_table) · → mitigation: inline pre-phase characterize_check_without_table
- Step 1b edits `deps` (a field on `Graph`, a field on `GradleModule`); both are additive and the existing `deps` suite runs unchanged, but `GradleModule` is compared in kotlin/gradle tests · severity: low · → mitigation: none (new deps tests pin both, and the suite gates the change)
- `deps:` evidence makes `_modules.yaml` change on ordinary cross-module import edits, so `MODULES_DRIFT` fires often on active repos · severity: low · → mitigation: none (the proposal's schema persists `deps:`; drift is StrictPastBootstrap)

### Goal-achievement risk: medium
- `check` + live inference may not fit the 300 ms budget; the fallback moves drift detection to the consumers, which changes what t2131_6 must do · severity: medium · → mitigation: none (step 1 measures first and the fallback is planned)
- Decisions 1–9 refine the proposal; a sibling (t2131_5/6/10) planned against the unrefined text could assume otherwise · severity: medium · → mitigation: none (step 9 amends the proposal and notes the siblings)

### Planned mitigations
- timing: pre-phase | name: characterize_check_without_table | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — shared check.go edits changing check for registries without a modules table | desc: pin check / check --json output and exit on table-less fixtures (non-git and git with codemap + Gradle) and assert the inference hook is never called

## Step 9 reference

Shared post-implementation (current branch, no merge); commit
`feature: Add the code modules table, codemap and Gradle providers and the modules verb (t2131_3)`.

## Post-Review Changes

### Change Request 1 (2026-10-25 11:40)
- **Requested by user:** six review findings, all verified and fixed —
  (1) `--scan --apply` wrote `_modules.yaml` before its output lines were
  validated (a refused root `a|b` made the run exit 3 *after* the write);
  (2) carried agent rows' `deps:` pointing at a since-removed/renamed module
  aborted regeneration; (3) `--list` ran the live providers, so a broken
  current codemap hid a valid committed table; (4) Gradle `settings:` evidence
  and the settings-derived `gradle-dynamic` flag came from the nearest
  settings file, not the declaring one; (5) `Modules.Doc()` cloned only the
  outer slice, so editing the snapshot mutated the loaded table and its
  ownership index; (6) the budget benchmark ran `check` with empty inputs, so
  133 ms did not validate the combined budget.
- **Changes made:** (1) `formatLines` split from `printLines`; `modules --scan`
  renders its whole text/JSON output first, then writes, then prints; (2) agent
  rows keep `paths`/`by`/`evidence`, their `deps:` are cleared and recomputed
  like every row's; (3) new `deps.Universe(ctx, root, cfg)` (the scan's file
  set, no scanning) feeds `--list`; (4) `GradleModule.Settings` records the
  declaring settings file, used for evidence and the dynamic flag
  (`deepestSettings` removed); (5) `cloneDoc` deep-copies rows in `Doc()`,
  `WithGenerated`, `ModulesFromDoc`; (6) the benchmark now carries ≈660
  annotated tests with covers, member variants with artifacts, two hand files
  (owns/rules/edges/waivers) and a persisted `_scanned.yaml`, asserted
  non-empty. Re-measured pinned: **≈ 220 ms** (budget 300; ≈ 33 ms without a
  declared table; Infer + addDeps ≈ 4 % of the profile, the warm deps scan
  dominates). Baseline updated; proposal and README follow. Each fix has a
  regression test, red-proved by a mutant: `TestModulesDocIsADeepCopy`,
  `TestGradleEvidenceNamesTheDeclaringSettings`, `TestAgentRowsCarriedOver`
  (kept / removed / renamed), `TestModulesScanApplyWritesNothingOnUnrenderableOutput`,
  `TestModulesListSurvivesABrokenCodemap`, the `deps.Universe` equality check.
- **Files affected:** `cmd/ait-testmap/{modules.go,scancheck.go,modules_test.go}`,
  `internal/testmap/deps/{deps.go,gradle.go,scan.go,gradle_test.go,scan_test.go}`,
  `internal/testmap/modules/{modules.go,deps.go,gradle.go,modules_test.go,bench_test.go}`,
  `internal/testmap/registry/{modules.go,modules_test.go}`, `bench/baseline.txt`,
  `goengines/README.md`, the proposal's *Code modules* component.

## Final Implementation Notes
- **Actual work done:** every plan step landed. Pre-phase
  `characterize_check_without_table` (`cmd/ait-testmap/modules_characterize_test.go`,
  green before and after, red with the `Declared()` gate removed). Step 1b:
  `deps.Graph.Universe()`, `deps.Universe(ctx, root, cfg)`,
  `GradleModule.Declared` / `.Settings`. Step 2: `registry/modules.go` — schema,
  strict loader, renderer, hand `modules:` block (`paths` only), `NativeID` /
  `ValidRoot` / `GeneratedName` / `ValidateModuleRow` / `ValidateModulesDoc`,
  `ModulesOf` (`Declared`, `Doc` deep copy, `Hand`, `WithGenerated`,
  `WithoutHand`, `ModulesFromDoc`), `OwnerOf`, `Resolve`, `ModulesDrift`, the
  package-kind ownership arm for t2131_4. `registry.ReadCodemapEntries` shares
  `ReadCodemap`'s decoder (`areas --import-codemap` unchanged). Step 3:
  `registry/rules_modules.go` (`RegisterModuleInference`, `MODULES_DRIFT`,
  `MODULE_CONFLICT`, once-per-run memo) and `check.go` (`ctx`, memo,
  `*InvalidError` passthrough). Step 4: `internal/testmap/modules`
  (`Infer`, `Scan`, `RegisterProvider`, codemap + Gradle providers,
  `MODULE_REFUSED`, `deps:` evidence, the inference hook). Step 5: verb
  `modules --list | --explain <path> | --scan [--apply]` with `--json`. Steps
  6-9: tests, baseline line, README rows, proposal amendment.
- **Measurements (Step 0 completion):** `check --strict` with the live
  inference on the aitasks shape with a populated registry ≈ 220 ms pinned to
  one P-core (budget 300; ≈ 33 ms on the same tree without a declared table;
  `Infer` + `addDeps` ≈ 4 % of the profile, the warm deps scan dominates) →
  detection stays in `check` (decision 1 holds). Provider overlap on the
  benchmark fixture: 2372 files, 52 modules, 6 unmapped, 0 conflicts (codemap
  and Gradle disjoint there); the combined test fixture exercises the
  overlapping cases.
- **Deviations from plan:** (a) the aitasks-shape generator moved from the
  deps bench into `fixture.AitasksShape` so the deps and modules benchmarks
  share it (deps bench unchanged in behaviour); (b) `TestUniverseIncludesUnscannedFiles`
  covers excluded, deleted and symlink-reached files but no FIFO — git never
  lists one; (c) `formatLines` was split out of `printLines` in `scancheck.go`
  for the write-after-render order; (d) agent rows' `deps:` are recomputed
  (review finding), so "carried over unchanged" now means `paths` / `by` /
  `evidence` — proposal amended; (e) review round 1 (Post-Review Changes
  above) added `deps.Universe`, `GradleModule.Settings` and a realistic
  benchmark workload.
- **Issues encountered:** `main` advanced mid-session (t1854_6 implemented
  `runner`), so the verb-table edits were re-applied on the new rows; no
  overlap. Two expectation slips in tests were mine (identical-root pairs are
  correctly not conflicts; universe counts).
- **Key decisions:** decisions 1-9 of this plan, all recorded in the proposal's
  *Code modules* component: drift judged only for a declared table; `deps:`
  over persisted rows only; hand declarations carry `paths` only; unmapped
  `MODULE_OF:<path>||unmapped`; `deps:` in `--json` only; equal-root
  tie-break by name; ownership over the complete universe; Gradle modules are
  declared projects only; roots validated by the directory rule independently
  of the name. `MODULES_DRIFT` registers before `MODULE_CONFLICT`, so it prints
  first.
- **Upstream defects identified:**
  - `goengines/internal/testmap/deps/gradle.go:209-215 — a build file whose directory maps by moduleNameOf onto an existing project name with a different projectDir (include(":api") moved to services/api plus a stray api/build.gradle.kts) is attached to that project as its BuildFile via addModule's by-name return, which also feeds sourceEdges; the modules provider guards its build: evidence`
- **Notes for sibling tasks:**
  - **t2131_4 (Go/Python):** register with `modules.RegisterProvider`; the
    registry already owns package-kind ownership (`*.go`; `*.py`/`*.pyi` directly
    in `root`, `go:.` / `py:.` allowed) and validates `go:` / `py:` names via
    `GeneratedName` — the provider only builds rows (each passes
    `registry.ValidateModuleRow`).
  - **t2131_5 (membership):** use `registry.ModulesOf(reg).OwnerOf(path)` for
    covered-source modules and `Resolve(deps.Universe(...))` for effective
    tables; `--explain` currently refuses a test id (`checkPath` → usage) —
    widen it there. Hand overlap is an `*InvalidError` from both calls.
  - **t2131_6 (reach):** the live table and drift come from `modules.Scan` +
    `registry.ModulesDrift`; ownership must be judged over the full universe,
    never `Graph.Files()`. A registry with no declared table has every path
    unmapped (→ full).
  - **t2131_10 (grouping):** `OwnerOf` is universe-free and cheap; `gradle:`
    rows carry the Gradle path in `ModuleRow.Gradle` for `{module}`.
  - Tests that run `check` with a declared table need a git repository (the
    inference scans); the CLI helper `modulesRepo` in
    `cmd/ait-testmap/modules_test.go` sets one up with a private cache and fake
    inputs.
