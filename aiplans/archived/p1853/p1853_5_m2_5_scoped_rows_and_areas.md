---
Task: t1853_5_m2_5_scoped_rows_and_areas.md
Parent Task: aitasks/t1853_testmap_m2_registry_and_map_model.md
Sibling Tasks: aitasks/t1853/t1853_1_*.md, aitasks/t1853/t1853_2_*.md, aitasks/t1853/t1853_3_*.md, aitasks/t1853/t1853_4_*.md, aitasks/t1853/t1853_6_*.md
Archived Sibling Plans: aiplans/archived/p1853/p1853_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-18 12:34
---

# Plan: t1853_5 — M2.5 Scoped rows and areas (verified 2026-10-18)

## Context

M2 (t1853) builds the test-map registry. M2.5 adds **broad tests** (integration / e2e /
device) as *scoped rows* — tests associated with areas, scope globs and trigger globs
instead of per-file `covers` edges — plus the areas table, the kind vocabulary, two
check rules, the distance-1 scoped join M4.1 will call, and the `areas` and
`classify --suggest` verbs. Wave B; provider M2.1 (landed). Current branch, no worktree
(profile `fast`). Automation-first: no path here requires a human action;
`classify --suggest` only suggests (kind changes stay a person's, applied by M6.4).

## Step 0 — Reality check (EXECUTED 2026-10-18, HEAD ec8272998)

**Providers on main:**

| provider | landed | what the repository has |
|---|---|---|
| M2.1 registry core | t1853_1 `0d04347ab` | `registry.Load`; `RegisterFile` / `RegisterHandTable` / `RegisterRule`; `Registry.Ext map[string]any`; reserved files `_scoped.yaml`, `areas.yaml` and hand keys `scopes`, `areas` refused until registered (registration wins: loaders are consulted first — no `load.go` edit needed); `CheckContext{Root, Reg, Anns, Lists, Scanned, MemberDrift, Today, Match}`; `MatchFiles` (strict GlobWalk, exclude-aware); `Render` / `WriteFile`; `Scan` writes only `_scanned.yaml`; `Check` wraps every rule error as `CheckError` |
| M2.2 grammar | t1853_2 `f096db065` | `annot.Unit` parses `Kind`/`Reviewed` (single) and `Areas`/`Scopes`/`Triggers`/`Reads`/`Needs` ([]KeyVal with lines); kind is a bare word, `reads`-in-helpers not enforced — both M2.5's; `toRegistry` (`annot/source.go`) is the extension point |
| M3.1 runner | t1854_1 `3d1a2b628` | `UnitAnnotation.Runner/Batch/Needs` filled in `toRegistry`; `runner.RegisterWaveClassifier` (registered by M3.3, panics on a second registration — M2.5 must NOT register it); `ListedUnit.Kind` is the granularity vocabulary `file\|class\|method\|variant\|suite`, never a test kind |
| M2.3 deps | t1853_3 | `deps.Scan(ctx, root, Options{Config})` → `*Graph` with `Facts`, `Closure`; helper test = `cfg.HelperRoots` glob match (`g.helper = o.Config.HelperRoots`); `deps` imports `registry` |
| `code_areas.yaml` | — | absent in this repo; shape from `seed/code_areas.yaml`: `{version: 1, areas: [{name, path: <dir>/, description, children: [...]}]}` |

**Differences** (*proposal says / coarse plan says / repository has → decision*):

| # | proposal | coarse plan | repository / lineage | decision |
|---|---|---|---|---|
| R1 | names `DEAD_SCOPE`, `KIND_MISMATCH\|CONVERT_TO_SUITE`, the `_scoped.yaml` field list, `areas.yaml`, `areas` verb — defines none | same | brainstorm lineage (crew-brainstorm-1812 n001–n008) defines them; M2.1 took its schemas from the same lineage (D1) | **Adapt from lineage**, record the definitions in the proposal component (proposal edit). DEAD_SCOPE: undeclared area / empty area glob / empty scope glob, fails always (n002:684, n003:534). KIND_MISMATCH:`<test>\|<n>\|CONVERT_TO_SUITE`, unit kind with > `unit_covers_max` covers, warning, fails under `--strict` (n003:536, 1347) |
| R2 | `_scoped.yaml` row has `reads_from` | same | `deps` imports `registry` → `registry.Scan` cannot compute closures; reads apply to *unit* tests too (n005:436), so the selector walks closures anyway; a persisted `reads_from` would SCAN_DRIFT on any unrelated import edit | **Revise proposal**: `_scoped.yaml` persists a `reads:` helper table `{helper, globs, line}`; `reads_from` is computed at join time from a caller-supplied closure and returned on each hit. Note to M4.1 (t1855) and M3.4 (t1854_4) |
| R3 | `owns:` by area name | same | lineage: "owns: lists globs and area names" with no syntax (n003:217) | **Adapt**: an `owns:` entry that equals a declared area name owns that area for `scopes:` rows; area names are validated to contain no glob metacharacter, `/`, `#`, `@`, `\|` or whitespace. Violation reuses `OWNS_VIOLATION:<file>\|scopes\|<area or path>` |
| R4 | `areas` flags unspecified | — | lineage names `--import-codemap`, `--list`, `--check`, defines only import (`<path>/**`, n003:510) | **Adapt**: `areas [--list] [--json]` and `areas --import-codemap [--apply] [--json]`; `--check` dropped (it would duplicate `check`'s DEAD_SCOPE) |
| R5 | `classify --suggest` areas "intersected with code_areas.yaml" | — | `code_areas.yaml` is imported into the areas table | **Adapt**: suggested areas come from the registry areas table (codemap-imported + hand) matching the test's closure subjects |
| R6 | M2.5 owns "verbs `areas`, `classify --suggest`" (no package) | — | M6.4's `onboard classify` must *wrap* classify, and package `main` is not importable; `registry` cannot import `deps` | **Adapt + proposal edit**: new package `goengines/internal/testmap/classify` (single owner M2.5) holds the suggest engine and the signal-extension registry M6.4 uses for p95 |
| R7 | scoped-key refusals | — | lineage n003:531: unit test carrying area/scope/trigger fails; broad row without any fails; `reads` only in files no runner lists (n005:308); variant-bearing units are unit kind (proposal) | **Adapt**: refused while building the scoped table, as `INPUT_ERROR:annotations\|<path>:<line>: <reason>` (exit 3) in both `scan` and `check`, like a grammar refusal; `Check` passes an `*InputError` through unwrapped (one-line named extension of M2.1's `check.go`) |

**Ownership (step 6):** every new file is M2.5's (`registry/scoped*.go`, `registry/rules_scoped.go`, `registry/areas_import.go`, `internal/testmap/classify/**`, `cmd/ait-testmap/{areas,classify}.go`). Named extensions: M2.1's `scan.go` (write `_scoped.yaml`), `check.go` (InputError passthrough), `inputs.go` (`UnitAnnotation` fields); M2.2's `annot/source.go` `toRegistry`; the `areas`/`classify` rows in `verbs.go` and their stub-test exemption in `main_test.go`. No sibling is in flight on these files (t1853_4/_6 Ready, t1853_7 Postponed); an unrelated concurrent session has frozenagent edits — commits name only this task's paths.

## Implementation

### Pre-phase (risk mitigations)

1. [characterize_scan_check_without_scoped] Before editing `scan.go` / `check.go` / `scancheck.go`, add `cmd/ait-testmap/scancheck_characterize_test.go`: on a repo with annotations and declared edges but **no** scoped keys, pin byte-exact stdout/stderr and exit codes of `scan`, `scan --apply`, `check`, `check --strict` and `scan --json`, plus the bytes of the written `_scanned.yaml` and the absence of `_scoped.yaml`. Run it green on the unmodified tree first; it must stay green unchanged after steps 5–6 (only the `--json` object may gain the new `scoped`/`reads` keys — assert those explicitly as additions).

1. **Kind vocabulary + table types** — `goengines/internal/testmap/registry/scoped.go`:
   - `Kinds = unit, integration, e2e, device`; `KindRank(k) int` (unit 0 < integration 1 < e2e 2 < device 3); `IsBroad(k)`; `ValidKind(k)`.
   - `Area{Name; Globs []string; Files []string}`; `ScopedRow{Test ID; Kind, Runner string; Areas, Globs, Triggers, Needs []string; ReviewedAt string; Line int; File string}`; `ReadsRow{Helper string; Globs []string; Line int; File string}`; `Scoped{Areas map[string]*Area; Rows []ScopedRow; Reads []ReadsRow}`.
   - `ScopedOf(reg) *Scoped` (never nil; stored at `reg.Ext["scoped"]`), `(*Scoped).Effective() []EffectiveRow` (step 4b), `(*Scoped).KindOf(id) string` (the **effective** row of id, else of `id.Base()`, else of the file-level id `{Path}`, else `unit` — the input M3.3's wave classifier maps; the fallback is sound only because step 4 refuses a member kind that differs from a broad file-level kind, so no explicit override is ever lost by persisting broad rows only), `(*Scoped).DigestExempt(id) bool` (true for a scoped row: never digest-stale; its fixture-pin `covers` stay ordinary stamped edges in `_scanned.yaml`), `(*Registry).AreaOwner(name)` (exactly one hand file whose `owns:` lists the name, else `ErrNoOwner`/`ErrAmbiguousOwner`, mirroring `OwnerOf`).
2. **Loaders** (same file, `init()`):
   - `RegisterFile("areas.yaml")` and `RegisterHandTable("areas")`: `areas: {<name>: {paths: [<glob>…]}}`; name validated (R3), each glob non-empty, no whitespace/`|`, `doublestar.ValidatePattern`; one merge rule = union of globs per name, files recorded.
   - `RegisterHandTable("scopes")`: rows `{test, kind, areas?, globs?, triggers?, reviewed_at?}` — **no `runner` / `needs`**: those are per-test keys owned by the test's annotations and the runner bindings, so a hand row can never disagree with them (an unknown row field is ignored, per the additive contract); kind must be broad; ≥1 of areas/globs/triggers; `ParseID` for test, and a test id carrying an `@<variant>` fragment is refused (`REGISTRY_INVALID`, exactly like `_scanned.yaml` refuses a variant unit); dates `YYYY-MM-DD`.
   - `RegisterFile("_scoped.yaml")`: generated doc, `KnownFields(true)`, same row validation; `reads:` rows `{helper, globs, line}`.
   - `ScopedDoc{Contract int; Scopes []ScopedDocRow; Reads []ReadsDocRow}` (yaml tags `scopes`, `reads`; flow lists; omitempty), `ScopedPath = RegistryDir + "/_scoped.yaml"`.
3. **Annotation → registry** — `registry/inputs.go`: add to `UnitAnnotation` (json omitempty) `Kind, Reviewed string; Areas, Scopes, Triggers, Reads []string; ScopedLine, ReadsLine int`. `annot/source.go` `toRegistry`: fill them (args flattened in file order; `ScopedLine` = the first of the block's kind/area/scope/trigger/reviewed lines; `ReadsLine` = first reads line).
4. **`BuildScoped(cfg, anns, lists) (ScopedDoc, error)`** — `registry/scoped.go`, pure and sorted (rows by test, reads by helper). Effective kind of a block = its own `kind`, else the file-level block's, else `unit`. Emits a row for every block whose effective kind is broad and that carries area/scope/trigger lines; `runner`/`needs` from the block (file-level inherited). Refusals (`*InputError{Input: annotations}`, message `<path>:<line>: <reason>`): unknown kind; **a member block whose own `kind` differs from a broad file-level kind** (mixed-kind files are refused — the file-level row selects the whole file, so a member in another wave is incoherent; a member restating the same kind is allowed); area/scope/trigger on a unit-kind block; a block with its own broad `kind` and no area/scope/trigger of its own unless it inherits the same kind from a file-level row that has them; `reads` in a file some runner lists; `reads` in the same block as a broad kind; a listed variant unit whose effective kind (own row, else base, else file-level) is broad. `exclude:`d files skipped.
4b. **Effective rows (merge + conflict policy)** — `registry/scoped.go`, computed at load time and by the check rules over the live rows: one `EffectiveRow{Test, Kind, Runner, Areas, Globs, Triggers, Needs, ReviewedAt, Line, Sources []string /* files */, Conflict []KindDecl}` per test id, from every generated (`_scoped.yaml` or live annotation) and hand (`scopes:`) row naming it, in file-name order:
   - areas, globs, triggers: sorted, deduplicated union (the one merge rule);
   - runner, needs, line: from the generated row only (hand rows carry none), so they can never conflict; a test has at most one generated row by construction (one per block id);
   - reviewed_at: the latest date;
   - kind: rows must agree. On disagreement the effective kind is the **lowest-ranked** declared kind (it ranks first and is budget-cut last, so a conflict fails toward running more — Invariant 1) and `Conflict` records every `(kind, file)`; `check` reports it (step 6). Generated-vs-hand, hand-vs-hand and agreeing rows all go through this one function, and `KindOf`, `Join` and `DigestExempt` read only effective rows, so every consumer sees one kind per test.
5. **`scan` writes `_scoped.yaml`** — `registry/scan.go`: `Scan` builds both docs before writing anything; a `BuildScoped` error returns before any write; a generalized `generatedDrift(root, path, empty, rendered)` (absent file == empty doc) replaces `scannedDrift`'s body; `--apply` writes each changed file (member drift still refuses both writes); `ScanResult` gains `Scoped, Reads int` (json) and `Changed` covers both; the dry-run `SCAN_DRIFT:` line is printed per drifting path (`cmd/.../scancheck.go` loops over `res.Drift []string` instead of the single path). `SCAN:` line unchanged.
6. **Check integration** — `registry/check.go`: an `*InputError` from a rule is returned unwrapped. `registry/rules_scoped.go` registers (after M2.1's rules):
   - `DEAD_SCOPE` (Always): `DEAD_SCOPE:<file>|areas|<name>|<glob>` an area glob matching no existing file; `DEAD_SCOPE:<test>|area|<name>|undeclared`; `DEAD_SCOPE:<test>|scope|<glob>|empty`. Live rows = `BuildScoped(c.Anns, c.Lists)` ∪ hand `scopes:` rows; globs gathered through `Patterns` so they share the run's one `MatchFiles`.
   - `KIND_MISMATCH` (StrictPastBootstrap): `KIND_MISMATCH:<test>|<n>|CONVERT_TO_SUITE` for an id of effective kind unit with n > `unit_covers_max` distinct covered sources (live annotation edges + declared edges); broad rows never.
   - `OWNS_VIOLATION` for `scopes:` rows (Always): `<file>|scopes|<area>` (area not listed in `owns:`) and `<file>|scopes|<path>` (an existing file a row's scope/trigger glob matches that no `owns:` glob matches).
   - `SCOPE_CONFLICT:<test>|kind|<kind>@<file>,<kind>@<file>…` (Always): effective rows whose sources declare different kinds (generated file named `aitestmap/registry/_scoped.yaml`, hand rows by their file).
   - `SCOPE_INVALID:<test>|<file>|variant-bearing` (Always): a listed unit with a `@variant` whose effective kind is broad through a **hand** row (the annotation-only case is already refused by step 4; this covers hand rows naming a base id or file whose listed units carry variants).
   - `SCAN_DRIFT:aitestmap/registry/_scoped.yaml` (StrictPastBootstrap), by the same comparison as step 5.
7. **Scoped join** — `registry/scoped_join.go`: `type ClosureFunc func(test string) ([]string, error)`; `(*Scoped).Join(changed []string, units []ID, closure ClosureFunc) ([]JoinHit, error)` over **effective rows** (one kind per test, equal to `KindOf`) → `JoinHit{Test ID; Kind; Distance (=1); Via (area|scope|trigger|reads); Ref (area name / glob / helper); Path (changed path); BudgetExempt (trigger, reads)}`; scoped rows match area globs ∪ scope globs ∪ triggers; every given unit and every scoped row also inherits the globs of each `reads` helper in its closure (`Via=reads, Ref=<helper>` = the join-time `reads_from`). `closure == nil` with reads rows present → error (fail closed); rows sorted by (KindRank, test, via, ref, path). Ranking by cost, the budget and `DEFERRED` stay M4.1's.
8. **`areas` verb** — `registry/areas_import.go` + `cmd/ait-testmap/areas.go`; `verbs.go` row `{Name: "areas", Run: runAreas, Exits: {0,2,3,64}}`:
   - `areas [--list] [--json]`: `AREA:<name>|<globs>|<files>|<rows>` (glob count, existing files matched via `MatchFiles`, scoped rows naming it), then `AREAS:<n>`.
   - `areas --import-codemap [--apply] [--json]`: read `aitasks/metadata/code_areas.yaml` (the literal carries `// invariant5-ok: read-only input`; never runs the script); `version` must be 1; flatten `children`; each `{name, path}` → `<path without trailing />/**`; duplicate / invalid name or path → `INPUT_ERROR:code_areas|<detail>` exit 3; absent → `CODEMAP_ABSENT:<path>` exit 2. Per area: `AREA_IMPORT:<name>|<glob>|added|kept|differs` (an existing name is never overwritten — `differs` reports a hand edit and keeps it). `--apply` writes `registry/areas.yaml` only when an area is added: fresh render when absent; otherwise a `yaml.Node` append under `areas:` so hand comments survive; prints `WROTE:<path>`.
9. **`classify --suggest`** — package `goengines/internal/testmap/classify` + `cmd/ait-testmap/classify.go`; `verbs.go` row `{Name: "classify", Run: runClassify, Exits: {0,2,3,64}}`; usage without `--suggest` → 64.
   - `classify --suggest [--json] [<test>…]`; no args = every annotated or listed test file (`testmapInputs()`); one `deps.Scan` per run.
   - Signals, a registered extensible list `RegisterSignal(name, fn)` (M6.4 adds p95): `convention:<pattern>` (`**/androidTest/**`, `**/androidDeviceTest/**` → device; `**/*_live.py`, `**/*_integration.*`, `**/parity/**` → integration); `resource:<name>` from the file text (`tmux`, `App.run_test`/`run_test(` → `textual-run-test`, `install.sh --dir` → `install-dir`, `git init|clone|worktree|commit` → `git-repo`, `adb `/`emulator` → `emulator` (device), `docker` → `docker`, `curl `/`wget `/`requests.` → `network`) and `resource:needs:<name>` from `testmap:needs`; `fanout:<n>` when the non-helper subjects (direct deps, helpers walked one level — `Suggest`'s rule) exceed `unit_covers_max`.
   - `CLASSIFY:<test>|<kind>|<reason>`: kind = highest-ranked signal; reason = signal tokens joined by `;`, plus `areas:<a>,<b>` for areas whose globs match a closure subject (R5); printed only when the suggestion outranks the test's current effective kind. Writes nothing; exit 0.
10. **Docs / contract** — `goengines/README.md` `## Interfaces`: an M2.5 entry (tables, `ScopedOf`, `KindOf`, `DigestExempt`, `Join`, `classify.RegisterSignal`). Proposal (`aidocs/testing_engine/n014_explorer_006_proposal.md`, path-scoped `documentation:` commit): definitions paragraph in *Scoped-row registry and areas* (R1–R5, R7), `reads` table replacing persisted `reads_from` (R2), M2.5 Module Map owns cell + `internal/classify` (R6), line-protocol index gains `AREA:` `AREAS:` `AREA_IMPORT:` `CODEMAP_ABSENT:` `SCOPE_CONFLICT:` `SCOPE_INVALID:` and the `DEAD_SCOPE` / `KIND_MISMATCH` field shapes; the component paragraph states the mixed-kind refusal and the effective-row merge / conflict policy (lowest-ranked kind, reported).
11. **Notes** (`/aitask-note`, hedged, citing the landed SHA): t1854_3 (M3.3 — register the wave classifier over `ScopedOf(reg).KindOf`), t1854_4 (M3.4 — `Scoped.Reads` is the helpers' `reads` table), t1855 (M4.1/M4.2 — `Join` API and join-time `reads_from`, `KindRank`, `DigestExempt`), t1857 (M6.4 — `classify` package, `RegisterSignal`), t1853_4 (M2.4 — the `UnitAnnotation` fields and `toRegistry` lines added next to its future axis fields).

### Post-phase (risk mitigations)

1. [e2e_real_inputs_fixture] Add `cmd/ait-testmap/scoped_e2e_test.go`: a `fixture.New` repo with a `runners.yaml` binding (real `runner.Lister`) and the real `annot.Source`, containing a file-level `kind integration` + `area board` bash test, a member-level `scope`/`trigger` python test, a helper under `tests/lib/` with `testmap:reads`, a 9-covers unit test, and `aitasks/metadata/code_areas.yaml` with a child area. Drive the real verb table: `areas --import-codemap --apply` → `WROTE:`; `scan --apply` → `_scoped.yaml` equals a testdata golden; `check` → exactly the expected `KIND_MISMATCH` line and no DEAD_SCOPE; deleting the area's directory → `DEAD_SCOPE` + exit 1; `classify --suggest` → the expected `CLASSIFY:` lines; finally a `reads` line moved into a listed test → `INPUT_ERROR:annotations|…` exit 3 for both `scan` and `check`.

## Verification

- `registry/scoped_test.go`: golden for `_scoped.yaml` render (testdata), merge golden for `areas.yaml` + two hand files' `areas:` and `scopes:` blocks; every R7 refusal with its `<path>:<line>`, including the mixed-kind member (`kind unit` and `kind e2e` under a file-level `kind integration`) and a same-kind restatement accepted; **round trip** `BuildScoped` → `scan --apply` → `Load` → `KindOf` for the file id, a member with its own row, a member inheriting the file row, and an unannotated member of a unit file (each equals the kind computed from the annotations before persistence); `DigestExempt` true for scoped rows, false for units; `AreaOwner` none/one/many.
- Effective rows: generated + hand agreeing (areas/globs/triggers unioned, runner/needs from the generated row, latest reviewed_at); generated + hand disagreeing kind; hand + hand disagreeing kind across two files — each: effective kind = lowest-ranked, `KindOf` equals every `Join` hit's kind for that test, `SCOPE_CONFLICT` listed with both sources. Hand loader refuses a variant id (`REGISTRY_INVALID`) and ignores a `runner:` field; `SCOPE_INVALID` for a hand row on a base id and on a file whose listed units carry variants; none for a hand row on a unit without variants.
- `registry/rules_scoped_test.go` (against `cleanRepo` as the negative control): each DEAD_SCOPE shape; KIND_MISMATCH at `unit_covers_max` (none) and +1 (warning; fails only under `--strict` past bootstrap); a broad row with 20 covers → none; scopes OWNS_VIOLATION both shapes; `_scoped.yaml` SCAN_DRIFT; an annotation refusal → `INPUT_ERROR`, not `CHECK_ERROR`.
- `registry/scan_test.go`: `--apply` writes `_scoped.yaml` + `_scanned.yaml`; no scoped data → no `_scoped.yaml`; a refusal writes neither file.
- `registry/scoped_join_test.go`: area / scope / trigger / reads hits with BudgetExempt; reads inheritance by a unit test via the closure; nil closure with reads → error; sort order.
- `registry/areas_import_test.go` + `cmd/ait-testmap/areas_test.go`: import from a fixture `code_areas.yaml` with children; `kept`/`differs`; comment preserved on append; `CODEMAP_ABSENT` exit 2; duplicate name exit 3; `--list` counts.
- `classify/classify_test.go` + `cmd/ait-testmap/classify_test.go`: one `CLASSIFY:` line per shipped signal, `fanout:<n>` at `unit_covers_max`+1, an already-broad test not re-suggested, a registered extra signal is consulted.
- `annot/source_test.go`: `toRegistry` fills the new fields.
- `main_test.go`: `TestStubsExit64` exempts `areas`, `classify`.
- Whole module: `ait engine test` (go vet + go test over `goengines/`) green, including the Invariant 4–5 tripwire in `goengines/guards_test.go` and the dependency allowlist (no new module).
- No path here requires a human action (automation-first).

## Risk

### Code-health risk: medium
- The extension edits M2.1's shared `Scan` / `Check` paths and the scan verb's drift printing; a regression would change `scan`/`check` output for every current user · severity: low (residual — addressed by inline pre-phase characterize_scan_check_without_scoped) · → mitigation: inline pre-phase characterize_scan_check_without_scoped

### Goal-achievement risk: medium
- DEAD_SCOPE / KIND_MISMATCH shapes, the row schemas and the join-time `reads_from` are adapted from the brainstorm lineage because the proposal leaves them undefined; consumers (M3.3, M4.1, M6.4) may need a different shape — bounded by recording the definitions in the proposal and notes to each consumer (step 11) · severity: medium · → mitigation: none (proposal edit + notes)
- Unit tests over in-memory fake inputs could hide gaps in the real `annot.Source` / runner-lister wiring (`toRegistry`, `testmapInputs`) · severity: low (residual — addressed by inline post-phase e2e_real_inputs_fixture) · → mitigation: inline post-phase e2e_real_inputs_fixture

### Planned mitigations
- timing: pre-phase | name: characterize_scan_check_without_scoped | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — M2.1 scan/check regression | desc: pin byte-exact scan/check output on a repo without scoped data before editing the shared paths
- timing: post-phase | name: e2e_real_inputs_fixture | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal — fake inputs hide wiring gaps | desc: drive areas/scan/check/classify through the real verb table, annotation source and lister on a fixture repo

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9 (archival; current branch, no merge).

## Final Implementation Notes

- **Actual work done:** every planned step landed, plus both inline risk phases.
  - `registry/scoped.go`: the kind vocabulary, the areas / `scopes:` / `_scoped.yaml` / reads tables and their loaders, `BuildScoped`, effective rows, `KindOf`, `DigestExempt`, `AreaOwner`, `ReadsHelper`.
  - `registry/rules_scoped.go`: DEAD_SCOPE, KIND_MISMATCH, OWNS_VIOLATION (scopes), SCOPE_CONFLICT, SCOPE_INVALID, the `_scoped.yaml` SCAN_DRIFT, and a per-run memo of the live view.
  - `registry/scoped_join.go`: `Join`, with `reads_from` computed at join time.
  - `registry/areas_import.go`: `ReadCodemap`, `ImportCodemap` (fresh render, or a `yaml.Node` append that keeps comments) and `ListAreas`.
  - New package `internal/testmap/classify`: the `Suggest` engine, `Subjects`, `RegisterSignal`, the built-in convention / resource / fanout signals.
  - Verbs `areas` and `classify` in `verbs.go`.
  - Named extensions: `Scan` writes `_scoped.yaml` and reports drift per file; `Check` passes an `*InputError` through; `UnitAnnotation` gains the scoped fields; `ReadInputs` is exported; `annot` `toRegistry` fills the fields; `annot.ReadFileNoFollow` is exported; UNREGISTERED exempts reads helpers and includes hand `scopes:` tests.
  - Docs: the goengines README layout and interfaces rows; the proposal (Module Map owns cell, a component definitions paragraph, the line-protocol index).
- **Deviations from plan** (each found in review, each with a red-proved regression test):
  1. `BuildScoped` runs the loader's own row validation on every generated row, so `_scoped.yaml` always loads and a bad annotation is refused before anything is written.
  2. `classify` eligibility is one rule for default and named targets:
     - excluded files and reads helpers are left out of the default universe, refused when named;
     - variant-bearing files are never suggested a broad kind;
     - a file-kind proposal that contradicts an explicit member kind is suppressed;
     - targets are read without following links.
  3. UNREGISTERED: reads helpers are exempt (found while building the e2e fixture), and hand `scopes:` tests are candidates.
  4. The e2e `_scoped.yaml` comparison is an inline expected string, not a testdata golden.
- **Issues encountered:**
  - M2.1's `load_test.go` pinned `_scoped.yaml`, `areas.yaml` and the `scopes` / `areas` keys as refused until registered; those cases were removed, with a comment pointing to `scoped_test.go`.
  - `annot/source_test.go` pinned that `kind` did not reach the registry; its expected value was updated.
  - Rule output order follows registration order (DEAD_SCOPE before KIND_MISMATCH).
- **Key decisions:**
  - Kind conflicts across rows read as the lowest-ranked kind (fail toward running more) and are reported.
  - Mixed-kind files are refused, so persisting broad rows only cannot lose an explicit member override.
  - Hand rows carry no runner / needs.
  - An area name carries no glob metacharacter, so `owns:` can list it unambiguously.
  - `areas --check` is dropped (it would duplicate `check`).
  - M2.5 does not register the wave classifier (M3.3 does; a second registration panics).
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - M2.4 (t1853_4): `UnitAnnotation` gained `Kind`, `Areas`, `Scopes`, `Triggers`, `Reviewed`, `Reads`, `ScopedLine` and `ReadsLine`, filled in `annot/source.go` `toRegistry`; add the axis fields alongside. `registry.ReadInputs` is exported for verbs outside the package.
  - M2.6 (t1853_6): rules register from `init()` in their own files and run in registration order. `Check` passes an `*InputError` from a rule through as INPUT_ERROR. A per-run memo can live on an unexported `CheckContext` field.
  - The `_scoped.yaml` golden is at `registry/testdata/scoped/`; `-update` rewrites the registry goldens.
