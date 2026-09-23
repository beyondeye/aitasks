---
priority: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [testmap, go_engine, testing, test_infrastructure]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
created_at: 2026-09-22 17:27
updated_at: 2026-09-23 16:57
---

## Context

Child **M1.2 — Engine skeleton** of t1852 (test map feature, module M1 —
Engine foundation and distribution). Wave **A**. This is the root of the whole
feature: the Go module every engine submodule of M2–M8 adds a package to, and
the fixture and bench harnesses every engine test uses. It has **no providers**.

Authoritative specification: `aidocs/testing_engine/n014_explorer_006_proposal.md`
— Module Map `#### M1` row M1.2, components *Go engine and CLI (M1.2)*
(including its **Path convention** paragraph) and *Engine binary identity and
budget (M1.2)*, *Architecture → The process boundary / Process map*, the
*Invariants every module honours* (Invariant 5 binds every engine package),
*Assumptions → Engine, distribution and install (M1)*
(`assumption_engine_latency_targets`), *Tradeoffs → Engine and distribution
(M1)*. The parent plan
`aiplans/p1852_testmap_m1_engine_foundation_and_distribution.md` records the
decomposition, reality anchors and deviations.

**Coarse plan only.** The child plan `aiplans/p1852/p1852_2_m1_2_engine_skeleton.md`
records what the proposal fixes for M1.2. It does not design internals; its
**Step 0 — Reality check** (mandatory, before any code, outcome recorded in
the plan) re-verifies the anchors: no `goengines/` exists, no Go in CI, Go on
the dev host (go1.27.0 via mise on 2026-09-22).

## Scope (from the proposal, with the goengines/ layout decided at the parent pass)

- **Layout (proposal *Path convention*):** one Go module at `goengines/`
  (module path `github.com/beyondeye/aitasks/goengines`) shared by every Go
  executable the framework distributes. `goengines/cmd/ait-testmap/` is the
  first executable. Cross-executable packages at `goengines/internal/`:
  `gitx` (git exec, blob digests, `merge-base --is-ancestor`, `ls-tree`),
  `platform`, `lineproto` (line-protocol stdout, `--json`, per-verb
  exit-contract helpers). Every testmap-specific package lives under
  `goengines/internal/testmap/<pkg>` — M1.2 creates that root (with the
  fixture harness); later submodules add `registry`, `annot`, `deps`, `axes`,
  `changesurface`, `selectr`, `sched`, `runner`, `cost`, `feedback`, `stale`,
  `seed`, `onboard`, `brief`.
- `go.mod`: Go ≥ 1.26 with a pinned `toolchain` (decide the exact line at the
  reality check); dependencies **only** `gopkg.in/yaml.v3`,
  `github.com/bmatcuk/doublestar/v4`, `golang.org/x/sync`.
- Verb table (stdlib `flag`): `version` live; every other verb — `test`,
  `select`, `schedule`, `run`, `scan`, `check`, `stale`, `annotate`
  (+ `--author`), `verify`, `explain`, `axes`, `areas`, `classify`, `costs`
  (+ `--gate-timeout`), `score`, `attribute`, `readiness`, `brief`, `onboard
  {detect, inventory, seed, review, classify, adopt, reject, scaffold, status,
  finish}`, `runner <name>` — registered as a **stub exiting 64**; each later
  engine submodule replaces only its own stub.
- Build identity: `-X` ldflags for version, commit and contract;
  `version --json` prints `ENGINE:<path>`; the `CONTRACT_MISMATCH` helper
  (a newer `contract:` in any registry file is refused); pool cap 8;
  `CGO_ENABLED=0`, `-trimpath -buildvcs=false -ldflags "-s -w …"` (the
  matrix script itself is M1.3's).
- Invariant 5: the engine never writes `aitasks/`, `aiplans/`,
  `.aitask-data/`, a gate ledger, `project_config.yaml`, `gates.yaml`, a
  profile or `CLAUDE.md`; never invokes `aitask_*.sh`; never commits; never
  launches a code agent.
- Harnesses: fixture repositories in `t.TempDir()` carrying synthetic
  `(t<id>)` commit histories (later submodules add one fixture per detect
  shape / opaque-scanner branch / verdict branch / packet language); the
  `go test -bench` harness with the **2× regression rule** against committed
  baselines (budgets listed under *Engine binary identity and budget*).

## Key files to modify

- `goengines/go.mod`, `goengines/go.sum` — new.
- `goengines/cmd/ait-testmap/main.go` — new (verb table, `version`).
- `goengines/internal/lineproto/`, `goengines/internal/platform/`,
  `goengines/internal/gitx/` — new shared packages with tests.
- `goengines/internal/testmap/` — the package root plus the fixture harness
  (`testmap/internal/fixtures` or equivalent — name decided at the reality
  check) and the bench harness.
- Owns `goengines/**` except the later packages.

## Reference files for patterns

- No Go code exists in the framework yet; `website/go.mod` is Hugo's and is
  not a pattern. Follow the proposal's *Go engine and CLI* text and
  `aidocs/framework/testing_conventions.md` for the bench-harness test design.
- `tests/run_all_python_tests.sh` and CLAUDE.md "Testing" for how test lanes
  are documented; the Go suite is run by M1.3's `goengines-check.yml` and by
  `ait engine test` (M1.5).

## Provides / consumes

- **Provides:** the binary and module every engine submodule of M2–M8 adds a
  package to; the fixture and bench harnesses; the shared `lineproto`,
  `platform`, `gitx` packages; the stub verb table.
- **Consumes:** nothing.
- **Named extensions into this child's files:** every later engine submodule
  replaces its own stub verb and adds its package under `internal/testmap/`.

## Implementation plan (coarse)

1. Step 0 — Reality check (see the child plan).
2. Module skeleton, `cmd/ait-testmap`, verb table with `version` live and
   every other verb an exit-64 stub.
3. `lineproto` (lines, `--json`, exit contracts, `CONTRACT_MISMATCH`),
   `platform`, `gitx` with unit tests.
4. Fixture harness (synthetic `(t<id>)` histories in `t.TempDir()`) and the
   bench harness with the 2× rule and committed baselines.
5. `go vet`, `gofmt`, `go test ./...` green locally.

## Verification

- `cd goengines && go vet ./... && go test ./...` green.
- `go build -o /tmp/ait-testmap ./cmd/ait-testmap && /tmp/ait-testmap version`
  prints version/commit/contract; `version --json` contains `ENGINE:`.
- Every stub verb exits 64; an unknown verb exits per the exit contract.
- A bench with an artificially slowed fixture fails the 2× rule.
