---
Task: t1852_2_m1_2_engine_skeleton.md
Parent Task: aitasks/t1852_testmap_m1_engine_foundation_and_distribution.md
Sibling Tasks: aitasks/t1852/t1852_1_*.md, aitasks/t1852/t1852_3_*.md, aitasks/t1852/t1852_4_*.md, aitasks/t1852/t1852_5_*.md, aitasks/t1852/t1852_6_*.md
Archived Sibling Plans: aiplans/archived/p1852/p1852_*_*.md
Base branch: main
Output branch: main
---

# Coarse plan: t1852_2 — M1.2 Engine skeleton

## Context

Parent goal: M1 — Engine foundation and distribution. This submodule is
**M1.2 Engine skeleton**, wave **A**, no providers — the root of the whole
feature: the Go module every engine submodule of M2–M8 adds a package to,
and the fixture and bench harnesses every engine test uses.

This coarse plan records what the proposal fixes for M1.2. It does not design internals against providers that do not exist yet;
the Reality check below does that when this child is picked.

## Proposal reading list

`aidocs/testing_engine/n014_explorer_006_proposal.md`:
- *Module Map* → `#### M1` row **M1.2**; *How to read it*; *Cross-module
  interfaces*; *Suggested implementation order* (wave A).
- *Components* → *Go engine and CLI (M1.2)* including its **Path convention**
  paragraph; *Engine binary identity and budget (M1.2)*.
- *Overview* → *Invariants every module honours* (Invariant 4 and 5).
- *Architecture* → *The process boundary*, *Process map*, *Where state lives*,
  *Line-protocol index* (the `ENGINE:` / `CONTRACT_MISMATCH` family).
- *Assumptions* → *Engine, distribution and install (M1)*:
  `assumption_engine_latency_targets`, `assumption_one_engine_per_framework_version`.
- *Tradeoffs* → *Engine and distribution (M1)*, *Implementation organization*
  (`tradeoff_module_boundaries_cut_across_packages`).
- Framework rules: `aidocs/framework/testing_conventions.md` (bench harness
  design), CLAUDE.md "Testing".
- Parent plan: `aiplans/p1852_testmap_m1_engine_foundation_and_distribution.md`
  (deviations 3 and 6 — toolchain line, `goengines/` layout).

## Owned files / provides / consumes

- **Owns:** `goengines/**` except the later packages; `goengines/go.mod`.
- **Provides:** the binary and module every engine submodule adds a package
  to; the shared `goengines/internal/{gitx,platform,lineproto}` packages; the
  stub verb table (every verb registered, exit 64 until its submodule lands);
  the `t.TempDir()` fixture harness with synthetic `(t<id>)` histories; the
  `go test -bench` harness with the 2× regression rule.
- **Consumes:** nothing.
- **Named extensions into this child's files:** every later engine submodule
  replaces only its own stub and adds its package under
  `goengines/internal/testmap/<pkg>` (`registry`, `annot`, `deps`, `axes`,
  `changesurface`, `selectr`, `sched`, `runner`, `cost`, `feedback`, `stale`,
  `seed`, `onboard`, `brief`); each adds the fixtures it needs.

## Step 0 — Reality check (MANDATORY, before any code; record the outcome here)

1. Re-read the proposal rows above and the parent plan's *Repository reality
   anchors* table (no `goengines/`, no Go in CI, go1.27.0 on the dev host on
   2026-09-22, VERSION 0.35.1). Those anchors are claims, not facts, by the
   time this child is picked.
2. Inspect the actual current state on the merge target: any Go code in the
   repository; the installed Go toolchain and the current stable Go release;
   the latest versions of `gopkg.in/yaml.v3`, `bmatcuk/doublestar/v4`,
   `golang.org/x/sync`; `.gitignore` for Go build artifacts.
3. Tabulate every difference: *proposal says / coarse plan says / repository has*.
4. Decide per difference: adapt; revise this plan; or revise the proposal
   (the `go`/`toolchain` directive values are a plan decision — ≥ 1.26). Record
   the decision and reason.
5. Send `/aitask-note` to every downstream child a difference breaks (t1852_3
   consumes the module layout and test entrypoints; t1852_4 the `version
   --json` shape; M2/M3 parents' first children consume the harnesses).
6. Re-confirm every file touched is owned here.

**Outcome:** _(to be recorded when executed)_

## Implementation steps (coarse)

1. `goengines/go.mod` (module `github.com/beyondeye/aitasks/goengines`, pinned
   toolchain, the three dependencies only) and `go.sum`.
2. `goengines/cmd/ait-testmap/main.go`: stdlib `flag` verb table — `version`
   live (prints version / commit / contract from `-X` ldflags vars;
   `version --json` prints `ENGINE:<path>`); every other verb of the table
   (`test select schedule run scan check stale annotate verify explain axes
   areas classify costs score attribute readiness brief onboard{detect
   inventory seed review classify adopt reject scaffold status finish}
   runner`) registered as a stub exiting 64.
3. Shared packages with unit tests: `internal/lineproto` (line-protocol
   stdout, `--json`, per-verb exit contracts, the `CONTRACT_MISMATCH` helper
   refusing a newer `contract:` field, pool cap 8 constant);
   `internal/platform`; `internal/gitx` (git exec via `os/exec`, blob
   digests, `merge-base --is-ancestor`, `ls-tree`).
4. `goengines/internal/testmap/` root: the fixture harness (repositories in
   `t.TempDir()` with synthetic `(t<id>)` commit histories) and the bench
   harness with the 2× regression rule against committed baselines.
5. `gofmt`, `go vet ./...`, `go test ./...` green; Invariant 5 respected
   (no writes outside `aitestmap/` / `.aitask-testmap/` / XDG cache; no
   `aitask_*.sh` invocation; no agent launch).

## Verification / acceptance

- `cd goengines && go vet ./... && go test ./...` green.
- `go build ./cmd/ait-testmap && ./ait-testmap version` prints
  version/commit/contract; `version --json` contains `ENGINE:<path>`.
- Every stub verb exits 64; `CONTRACT_MISMATCH` is exercised by a test.
- A fixture builds a synthetic `(t<id>)` history in `t.TempDir()`; a bench
  with a deliberately slowed fixture fails the 2× rule.

## Step 9 reference

Archival and cleanup follow the shared `task-workflow` Step 9. Current-branch
profile: no worktree, no merge.
