---
Task: t1853_4_m2_4_axes_and_variants.md
Parent Task: aitasks/t1853_testmap_m2_registry_and_map_model.md
Sibling Tasks: aitasks/t1853/t1853_1_*.md, aitasks/t1853/t1853_2_*.md, aitasks/t1853/t1853_3_*.md, aitasks/t1853/t1853_5_*.md, aitasks/t1853/t1853_6_*.md
Archived Sibling Plans: aiplans/archived/p1853/p1853_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-21 11:38
---

# Plan: t1853_4 — M2.4 Axes and variants

## Context

M2.4 adds variant axes to the test map. A project whose tests form a product
of facets (thinking_app: screens × locale × direction × geometry) declares the
axis in `aitestmap/axes.yaml`. A runner's `describe` names the axis its variants
live on. `scan` persists the variants. Library code joins changed paths to facet
values, so M4.1's selector can pick only the variants a change reaches. `check`
gains three axis rules, and `ait-testmap axes` gets its `--list`, `--check` and
`--explain` modes.

Both providers have landed: M2.1 (registry core, `0d04347ab`) and M3.1 (runner
contract, `3d1a2b628`). M2.2 (`f096db065`) already parses `testmap:axis`, and
M2.5 (`6f6d1ed79`) and M2.6 have extended the same shared files.

**Automation-first.** No verb, load rule or check rule here makes a human
action a precondition. Axis *declaration* stays the maintainer's (M6.4 / M10).
This child ships only the data, the library and the verbs.

## Step 0 — Reality check (recorded)

Read: proposal (M2 cut `3bc0de8ac`): Module Map row M2.4; *Variant axes*;
*Axis resolver verbs*; *Vocabulary → Axis and variant*; *Registry loader*;
*Enumeration and reconciliation*; Invariant 1; the axis assumptions and
tradeoffs. Parent plan Deviations 3 and 5. `goengines/README.md`. The notes
from t1853_1, t1853_2, t1854_1 and t1853_5 (advisory input, each re-verified
against the tree below).

| # | proposal / coarse plan says | repository has (HEAD `f0d1e5712`) | decision |
|---|---|---|---|
| R1 | M3.1 `describe` refuses `axis:` / `token_format:` until M2.4 lands | `runner.RegisterDescribeKey` (describe.go) puts raw `yaml.Node` values in `Describe.Ext`, and they survive `Merge`. `TestDescribeRefusesUnknown` / `TestDescribeExtensionKey` pin the pre-M2.4 state | adapt: register both keys in a new M2.4-owned file `runner/axis.go`, validate them from `Validate()` through `axes`, and update the two M3.1 tests that pinned "until M2.4" |
| R2 | the loader merges `axes.yaml` | `registry.Load` reads only `config.yaml` + `registry/*.yaml`; `RegisterPostLoad` exists (M2.6 uses it for `onboard.yaml`) | adapt: `axes` registers a post-loader that reads `aitestmap/axes.yaml` into `reg.Ext["axes"]` |
| R3 | rules register into M2.1's `check` | `RegisterRule(CheckRule{Name, Patterns, Run})`; rules run in registration order; `Patterns` share one `MatchFiles` pass | adapt: register the three rules from `axes` `init()` |
| R4 | `_scanned.yaml` rows `{test, line?, variants?, covers?}`; `select` reads the committed table and never runs a runner | `ScannedRow{Test, Line, Variants, Covers}`, decoded with `KnownFields(true)`. `registry.Listing` carries no axis, so the runner→axis association is lost at scan time, and so are `testmap:axis` claims | **revise the proposal**: rows gain `axis?` (the owning runner's describe axis, on a row with variants) and `facets?` (the unit's `testmap:axis` claims). Without them the selector cannot place a variant or a claimed plain unit from committed state. Both are `omitempty`, so every existing registry's bytes are unchanged (the characterization test pins this) |
| R5 | `testmap:axis <axis>.<facet>=<value>` is parsed | `annot.Unit.Axes []KeyVal` (shape only, `axisRe`); `registry.UnitAnnotation` has no axis field (t1853_2 note) | adapt: add `UnitAnnotation.Axes []string` and fill it in `annot/source.go` `toRegistry` next to the M2.5 keys |
| R6 | `UNCOVERED_VALUE:<axis>\|<value>` (fails `--strict` past bootstrap); `DEAD_AXIS_SOURCE`, `UNKNOWN_VARIANT` named with no format or severity | — | **revise the proposal**: define the formats and severities (step 5) |
| R7 | `token_format` named, never defined | — | **revise the proposal**: a template over `{id}` `{base}` `{path}` `{member}` `{variant}`, default `{id}`, with a render API for M4.1's `--format tokens` |
| R8 | "observed axis sources merged widen-only" | `registry/observed.yaml` is a reserved, refused file name. Its writer (`attribute`, M4.4) and its schema do not exist | adapt: ship the widen-only merge as library API (`(*Table).Widen`), proven by a superset test. The `observed.yaml` loader stays with its owner M4.4, which calls `Widen`. Note to t1855; one proposal sentence |
| R9 | `--axis <axis>.<facet>=<v>` "forces a facet"; it is a selector "cut knob" | M4.1 is undecomposed (t1855 has no children or plan) | adapt: library `ParseForce` / `ResolveForce` / `Admits` (a cut: keeps only what provably carries the forced value). M4.1 parses the flag. Note to t1855 |
| R10 | the `axes` verb row | `stub("axes")` in `verbs.go`; `TestStubsExit64` lists the implemented verbs | replace that row only; add `axes` to the test's implemented list |
| R11 | variant-bearing units are unit kind | M2.5 refuses them as broad (t1853_5 note) | none: `@variant` ids are always unit kind |
| R12 | the `axes` package is read by registry, selector, runner and cost | `runner` imports `registry` and `annot` | import graph `axes → registry`, `runner → axes`; `registry` never imports `axes` (no cycle). Every binary that links `runner` therefore links the axis loader and rules |

**Ownership (Step 0.6).** These files are owned by M2.4 or are its named
extensions:
- **New:** `internal/testmap/axes/**`, `runner/axis.go`, `cmd/ait-testmap/axes.go`, `cmd/ait-testmap/axes_test.go`.
- **One-line or one-field additions:** `registry/inputs.go` (`Listing.Axis`, `UnitAnnotation.Axes`, readInputs validation), `registry/scan.go` (`ScannedRow.Axis`/`Facets`, BuildScanned), `registry/check.go` (`CheckOptions.Rules`), `annot/source.go` (`toRegistry`), `runner/describe.go` (one `Validate` call), `runner/repo.go` (`Listings` sets `Axis`), `verbs.go` (the `axes` row).
- **Docs:** the proposal and `goengines/README.md`.

**Downstream notes (Step 0.5, sent post-implementation with the landing SHA):**
- **t1855.** For M4.1: the deferred source-value policy question (plain-unit-only source values vs typo detection vs `--axis` filters); the library API; `axis` / `facets` on `_scanned`; `Token`; `--axis` as a cut. For M4.3: variants by id. For M4.4: `Widen` and the `observed.yaml` ownership.
- **t1856.** For M5.2: the `AXES:` brief data lives in `axes.Of(reg)` plus `_scanned` `axis`.
- **t1857.** For M6.4: the `scaffold --axes` target schema.

## Design

### `axes.yaml` (strict)

```yaml
contract: 1
axes:
  - name: matrix
    facets: [locale, direction, geometry]
    values:                       # variant value -> one v per declared facet
      ru-ltr-phone: {locale: ru, direction: ltr, geometry: phone}
    sources:                      # facet -> v -> globs (optional)
      locale:
        ru: ["app/src/main/res/values-ru/**"]
```

Load refusals are `REGISTRY_INVALID:aitestmap/axes.yaml|<reason>`, exit 3:
- an unknown key, a repeated axis name, an empty `facets` / `values`, or a repeated facet;
- a value that misses a facet or names an undeclared one;
- a `sources` key that is not a facet of the axis, or a source `v` that no value carries (this catches a misspelt source value);
- an empty or invalid glob;
- an axis or facet name outside `[^.=\s|#@/]+` (no control characters);
- a facet `v` outside annot's `[^=\s|#@]+`, so every declared `v` can be written as `testmap:axis`;
- a value name that is not a valid variant fragment (`registry.ID{Path:"x",Variant:v}.Valid()`).

A newer contract is `CONTRACT_MISMATCH` (via `testmap.CheckContract`). An absent
file is an empty table (`Declared()==false`).

**Facet values.** A facet's valid `v` is one that some declared value carries.
Load, claim validation, `ResolveForce` and `Widen` all use this one rule.

**Deferred (not decided here).** Whether a source `v` used only by plain units
that claim `f=v` (with no variant carrying it) should be accepted is still open.
It must be weighed together with typo detection for source values and with which
`--axis` filters are accepted, so it is deferred to M4.1's design and raised in
the t1855 note. Until then the strict rule above holds.

### Library API (`internal/testmap/axes`)

- `Table` / `Axis{Name, Facets, Values map[value]map[facet]v, Sources map[facet]map[v][]Source}`, where `Source{Glob, Origin hand|observed}`. Also `Of(reg) *Table`, `(*Table).Axis(name)` and `Declared()`.
- `ParseClaim("a.f=v") (Claim, error)` is the one claim grammar, pinned against annot's `axisRe` by a differential test.
- **Facet join.** `(*Table).Join(paths []string) []Hit`, where `Hit{Axis, Facet, Value(v), Glob, Origin, Path}`. It uses `doublestar.Match` (a pattern-level match, so deleted paths still join). Results are sorted and deterministic.
- **Variant expansion.** `(*Table).Select(rows []registry.ScannedRow, hits []Hit) []Placed` — a method, because which variant carries `f=v` is `Table.Values` and is in neither argument, where `Placed{ID, Axis, Facet, FacetValue, Path, Glob, Undeclared bool}` and `Reason()` = `axis(<a>.<f>=<v>) <- <path>`. A hit on axis A places:
  - every variant of an A row whose declared value carries f=v;
  - every A variant whose value A does not declare (`Undeclared`; widening, so a missing declaration never under-selects — Invariant 1);
  - every plain (variant-free) row whose own or file-level `facets` claim carries A.f=v.

  Pinned by `TestSelectReadsTableValues`: two loadable tables swap `locale=ru` / `locale=en`
  between opaque values `v1` / `v2`. With identical rows and an identical `locale=ru` hit,
  `Select` returns `…@v1` under one table and `…@v2` under the other.
- `Expand(rows, unit registry.ID) []registry.ID` returns every variant of a unit reached by an edge, dep, rule or test-dep, or the unit itself when it has no variants.
- **Caller obligation (documented in the package doc and the README row, not implemented here — M4.1's walk owns it).** `Select` is an *additional* channel. A selector must take the union of `Select(Join(changed))` and `Expand` of every unit its edge / dep / rule / test-dep walk reaches, and must never intersect the two. That union is what makes Invariant 1 and `assumption_axis_membership_declarable` hold: a source with no axis hit still reaches every variant of the units it covers. `TestEdgeWithoutAxisHitKeepsAllVariants` pins the composition, using a fixture that composes the two exported calls the way the obligation states.
- **Forced facet.** `ParseForce(s)`, then `(*Table).ResolveForce(f)`, which returns a `*ForceError{Force, Reason axis|facet|value}` (value = carried by no declared value). `(*Table).Admits(forces, rows, id) bool` is a cut — a method for the same reason as `Select`:
  - a variant on a forced axis survives only when its declared value carries every forced facet value (an undeclared value is cut);
  - a claimed plain unit survives only when it claims a matching value;
  - other axes and unclaimed units pass.
- **Widen-only merge.** `(*Table).Widen(obs []ObservedSource) (rejected []ObservedSource)`. It unions observed globs into existing `(axis, facet, v)` cells as `Origin observed`. It never removes a glob and never touches `values`, and it rejects an undeclared axis or facet, a `v` no declared value carries, or a bad glob.
- **Tokens.** `ParseTokenFormat(s)` accepts literal text plus `{id}` `{base}` `{path}` `{member}` `{variant}`; it refuses an unknown or unbalanced brace and control characters. `RenderToken(f, id)` renders a unit id; the default format is `{id}`.
- **Runner declaration.** `ParseRunnerDecl(ext map[string]yaml.Node) (RunnerDecl{Axis, TokenFormat}, error)` takes scalars only and validates the shape.

### Check rules (registered from `axes` `init()`, after every registry rule)

| line | when | severity |
|---|---|---|
| `DEAD_AXIS_SOURCE:<axis>\|<facet>\|<v>\|<glob>` | a hand source glob matches no existing file (shared `MatchFiles` pass via `Patterns`; `exclude:` applies) | Always (as `DEAD_SCOPE`) |
| `UNKNOWN_VARIANT:<id>\|<axis>\|undeclared-axis\|undeclared-value` | a scanned row whose runner names an axis that `axes.yaml` does not declare, or a variant value the axis does not declare (one line per variant id) | StrictPastBootstrap |
| `UNKNOWN_VARIANT:<unit>\|<a>.<f>=<v>\|claim-undeclared-axis\|claim-undeclared-facet\|claim-undeclared-value` | a `testmap:axis` claim the table cannot place (`claim-undeclared-value` = no declared value carries `f=v`) | StrictPastBootstrap |
| `UNCOVERED_VALUE:<axis>\|<value>` | a declared value that no scanned row on that axis lists | StrictPastBootstrap (proposal) |

Rules read `c.Scanned`, which is what `scan --apply` would write, so exclusions
match `scan`. A runner that lists variants **without** an `axis:` is not judged:
its variants have no axis, are selected only with their unit (widening), and
existing registries see no new finding. A malformed persisted `axis` / `facets`
fails the axes post-loader as `REGISTRY_INVALID`.

### `axes` verb (`cmd/ait-testmap/axes.go`)

`axes [--list] [--json] | axes --check [--strict] [--json] | axes --explain <path> [--json]`. Exit contract 0 · 1 · 2 · 3 · 64.

- **`--list`** (the default) reads the live inputs through `registry.ReadInputs` and `BuildScanned`, as `check` does. It prints:
  - `AXIS_DECL:<axis>|<facets csv>|<values>|<variants>` per axis (sorted);
  - `AXIS_VALUE:<axis>|<value>|<f=v csv in facet order>|<variants listed>` per value;
  - then `AXIS_DECLS:<n>`.

  With `--json` it prints `{"axes":[{name, facets, values:[{value, facets, variants}], variants}]}`.
- **`--check`** runs `registry.Check` with `CheckOptions{Rules: axes.RuleNames}`: the axis findings, then `CHECK:<pass|fail>|<findings>|<failing>`, with no summary lines. Exit 1 iff a finding fails; `--json` prints the `CheckResult`.
- **`--explain <path>`** needs a valid id path (else usage, 64) but not an existing file. For each axis (sorted), and each facet in declared order, it prints `AXIS:<axis>.<facet>|<v>|<glob>` per matching source (hand, then observed), or `AXIS:<axis>.<facet>|-|no-source` / `|-|no-match`. `-` means no axis hit, which selects every variant. `--json` prints `{"path", "hits":[{axis, facet, value, why}]}`.
- **Error and absence lines.** `TESTMAP_ABSENT` gives exit 2. An absent `axes.yaml` gives `AXES_ABSENT:aitestmap/axes.yaml` on stderr, exit 2, for `--list` and `--explain`; `--check` still runs, because a runner can name an undeclared axis. Load and input errors go through `reportError`, exit 3.

## Implementation steps

### Pre-phase (risk mitigations)

1. [baseline_engine_suite] Before any edit, on the clean HEAD, run
   `./ait engine test` (with `set -o pipefail` if piped) and record its exit
   status, plus the name of every failing
   package or test, in this plan's Final Implementation Notes. A failure that
   was already there is reported as pre-existing, never fixed or blamed on this
   change. Do not stash and do not restore files to get the baseline.

### Main steps

1. **`internal/testmap/axes/axes.go`** — the types, `parse` (strict YAML node walk, refusals above), the name and claim grammar, `Of`, and `init()` → `registry.RegisterPostLoad(load)`.
   - The post-loader reads `<root>/aitestmap/axes.yaml` (absent means empty), runs the contract check, and parses into `reg.Ext["axes"]`.
   - It then validates every `reg.Units` `Axis` / `Facets` against the grammar.
2. **`axes/join.go`** — `Join`, `Select`, `Expand`, `ParseForce`, `ResolveForce`, `Admits` and `Widen`. **`axes/token.go`** — the token format and `ParseRunnerDecl`.
3. **Registry named extensions:**
   - **`inputs.go`.** `Listing.Axis string` (the runner's describe `axis:`, M2.4) and `UnitAnnotation.Axes []string` (`testmap:axis` claims). `readInputs` refuses three things: an `Axis` that fails `checkChars` or contains `.` / `=`; a claim with `checkChars` problems; and two listings giving one base unit variants with different axes (`INPUT_ERROR:lister|…`, fail closed).
   - **`scan.go`.** `ScannedRow.Axis` `yaml:"axis,omitempty"` (between `line` and `variants`) and `Facets []string` `yaml:"facets,omitempty,flow"`. `BuildScanned` records the owning listing's `Axis` on rows with variants and the sorted, deduplicated claims per block. It creates a row for a file-level block carrying claims, the same way it does for covers.
   - **`check.go`.** `CheckOptions.Rules []string`: when set, only the named rules run (patterns too), and an unknown name is a `CheckError`.
4. **`annot/source.go` `toRegistry`** — `ua.Axes = append(ua.Axes, a.Args[0])` for each `u.Axes`, beside the M2.5 keys.
5. **Runner named extension:**
   - **`runner/axis.go`.** `init()` registers `axis` and `token_format`. `Describe.Axis()` / `TokenFormat()` accessors read the validated `Ext`.
   - **`describe.go`.** `Validate()` calls `axes.ParseRunnerDecl(d.Ext)`.
   - **`repo.go`.** `Listings()` sets `l.Axis`.
   - **`describe_test.go`.** `TestDescribeRefusesUnknown` keeps `bogus` and drops the two now-owned keys. `TestDescribeExtensionKey` uses a test-only key. A new test covers valid and invalid `axis` / `token_format`, including via a `runners.yaml` override.
6. **`axes/rules.go`** — the three rules from the table, exported `RuleNames`.
7. **`cmd/ait-testmap/axes.go`** — `runAxes`, `axesExits`. Replace `stub("axes")` in `verbs.go` and add `"axes"` to `TestStubsExit64`'s implemented list.
8. **Docs.**
   - **The proposal:** `_scanned.yaml` row schema (+`axis?`, `facets?`); the *Variant axes* text (token_format template, `--axis` as a cut, widen-only API with the `observed.yaml` loader at M4.4, no-axis variants unjudged); the *Axis resolver verbs* lines (`AXIS_DECL`, `AXIS_VALUE`, `AXIS_DECLS`, `AXES_ABSENT`, the `--check` scope); the severity table rows for the three rules; and the line-protocol index row.
   - **`goengines/README.md`** Interfaces rows: axes table and loader, axes library, axis check rules, `axes` verb, the `describe` `axis` / `token_format` row (replacing "until M2.4"), and `_scanned` `axis` / `facets`. Each is pinned by a named test.
9. Run `ait engine test` (`go vet` + `go test ./...`). Commit code and docs together: `feature: Add test-map variant axes and the axes verb (t1853_4)`. Then send the three notes.

### Post-phase (risk mitigations)

1. [undeclared_never_underselects] Add `axes/widen_property_test.go`, a
   deterministic, seeded property test. Its two parts are kept apart, and only
   part B speaks for the accepted-input path.

   **A — synthetic unit property (in-memory `Table`, not proof of the loader path).**
   It runs over generated tables (2 axes, 2–3 facets, 3–6 values, sources with
   `*` / `**` globs), scanned rows (variant rows on each axis including
   undeclared values, plain rows with member and file-level claims) and a path
   corpus. It asserts:
   - (a) deleting any one value declaration never shrinks
     `t.Select(rows, t.Join(paths))` as a set of ids (the deleted value's
     variants move to `Undeclared`);
   - (b) `Widen` with any batch of observed sources never shrinks `Join` hits
     or `Select` ids;
   - (c) a rejected observed source leaves the table deep-equal to before.

   **B — accepted-input round trip.** Each generated declaration is rendered to
   `axes.yaml` bytes and loaded through the real `parse`. The value deletion is
   applied to the YAML and re-loaded:
   - a loadable result must satisfy (a) against the loaded tables;
   - a refused result must be refused only for one of the two reasons a
     deletion can produce: the axis's last value (`empty values`), or a source
     `v` that the deleted value alone carried (orphan source). The test
     asserts `REGISTRY_INVALID` and that reason. That is fail-closed, never a
     silent narrowing.

   **Selection is not proved by `Join` alone.** The edge-composition claim
   (no axis hit ⇒ an edge-reached unit keeps every variant) is covered by
   `TestEdgeWithoutAxisHitKeepsAllVariants` and by the documented caller
   obligation, not by this property.

   **Red proof.** In a scratch copy, drop the `Undeclared` branch from `Select`
   and confirm (a) fails in both A and B. Record that red run in the Final
   Implementation Notes and do not commit the mutant. The test lands in the
   step-9 commit and runs before it.

## Verification

- **axes unit tests:**
  - parse golden and every refusal; `CONTRACT_MISMATCH`;
  - `Join` (deleted path still joins, multiple values of one facet, sorted);
  - `Select`: declared values, `Undeclared` widening, file-level and member claims, plain rows only; `TestSelectReadsTableValues` (the swapped-table example: identical rows and hit, different ids); `TestLoadRefusesOrphanSourceValue` (a misspelt source `v` is `REGISTRY_INVALID`);
  - `TestEdgeWithoutAxisHitKeepsAllVariants`: a source covered by an ordinary edge with no axis hit keeps every variant of the unit through `Expand`, composed per the caller obligation;
  - `Expand`; `ParseForce` / `ResolveForce` errors per reason; `Admits` cut cases;
  - `Widen`: hand globs are kept and values are unchanged; rejections; a superset property where hits(after) ⊇ hits(before) over a path corpus;
  - token parse and render, plus refusals;
  - `ParseClaim` ⇔ annot `axisRe` differential over a pinned corpus.
- **registry tests:** a `BuildScanned` golden with `axis` / `facets`; a claims-only file row; the axis-conflict and bad-claim `INPUT_ERROR`; `CheckOptions.Rules` filters rules and refuses unknown names. The existing characterization (`TestCharacterizeScanCheckWithoutScoped`) stays byte-identical.
- **runner tests:** the describe extension accepts and refuses correctly; an override in `runners.yaml` is validated; `Listings` carries `Axis`.
- **cmd tests:**
  - `axes --list` counts with a fake lister plus `axes.yaml`;
  - `axes --check` produces each of the three rules and a passing case, with `--strict` past bootstrap flipping the severity of `UNKNOWN_VARIANT` / `UNCOVERED_VALUE`;
  - `DEAD_AXIS_SOURCE` fails always, and full `check` includes the axis findings;
  - `--explain` prints `AXIS:` lines with a glob, `-|no-source` and `-|no-match`;
  - `AXES_ABSENT` exits 2, `TESTMAP_ABSENT` exits 2, a bad registry exits 3, and usage errors exit 64; the JSON shapes;
  - one end-to-end run with a real script runner whose `describe` declares `axis:`, so `scan --apply` writes `axis:` to `_scanned.yaml`.
- `ait engine test` is green, including the Invariants 4–5 tripwire in `goengines/guards_test.go`. No path requires a human action.

## Risk

### Code-health risk: low
- Additive edits to M2.1 / M3.1 shared files (`inputs.go`, `scan.go`, `check.go`, `describe.go`, `repo.go`) could shift existing `scan` / `check` output or break a pinned test without the change being noticed · severity: low (residual — addressed by inline pre-phase baseline_engine_suite and the existing characterization test) · → mitigation: inline pre-phase baseline_engine_suite
- The axis loader and rules activate through `init()` in a package linked transitively via `runner`, which is implicit coupling: a binary without `runner` silently has no axis rules · severity: low · → mitigation: none (the cmd tests exercise the real wiring; documented in README)

### Goal-achievement risk: medium
- The proposal leaves `UNKNOWN_VARIANT`'s format, `token_format` and the `--axis` semantics undefined. The decisions here (and the persisted `axis` / `facets` schema) may not fit M4.1's selector once it is designed · severity: medium · → mitigation: none (proposal edit + note to t1855 hedge it; M4.1 can revise through protocol §1)
- The widening argument (an undeclared value or claim never under-selects, Invariant 1) is reasoned rather than proven by a test · severity: low (residual — addressed by inline post-phase undeclared_never_underselects) · → mitigation: inline post-phase undeclared_never_underselects

### Planned mitigations
- timing: pre-phase | name: baseline_engine_suite | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — shared-file edits shifting existing scan/check output | desc: run ait engine test on the clean HEAD before edits and record pre-existing failures
- timing: post-phase | name: undeclared_never_underselects | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — the widening argument (Invariant 1) unproven | desc: seeded property test that removing declarations or widening never shrinks Select/Join, red-proved by a scratch mutant

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9 (current branch,
archival, no merge).
