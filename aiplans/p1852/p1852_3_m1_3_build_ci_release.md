---
Task: t1852_3_m1_3_build_ci_release.md
Parent Task: aitasks/t1852_testmap_m1_engine_foundation_and_distribution.md
Sibling Tasks: aitasks/t1852/t1852_1_*.md, aitasks/t1852/t1852_2_*.md, aitasks/t1852/t1852_4_*.md, aitasks/t1852/t1852_5_*.md, aitasks/t1852/t1852_6_*.md
Archived Sibling Plans: aiplans/archived/p1852/p1852_*_*.md
Base branch: main
Output branch: main
---

# Coarse plan: t1852_3 — M1.3 Build, CI and release

## Context

Parent goal: M1 — Engine foundation and distribution. This submodule is
**M1.3 Build, CI and release**, wave **B**. It turns the M1.2 module into
release assets that M1.5's installer fetches. Provider: **M1.2 (t1852_2)**.

This coarse plan records what the proposal fixes for M1.3. It does not design internals against providers that do not exist yet;
the Reality check below does that when this child is picked.

## Proposal reading list

`aidocs/testing_engine/n014_explorer_006_proposal.md`:
- *Module Map* → `#### M1` row **M1.3**; *Cross-module interfaces*;
  *Suggested implementation order* (wave B).
- *Components* → *Binary distribution (M1.3, M1.4)*; *Go engine and CLI
  (M1.2)* (build flags, Path convention).
- *Assumptions* → `assumption_go_toolchain_available`,
  `assumption_go_toolchain_ci_and_dev_only`, `assumption_platform_matrix_sufficient`.
- *Tradeoffs* → `tradeoff_compiled_component_cost`, `tradeoff_two_toolchains`.
- Framework rules: `aidocs/framework/shell_conventions.md` (for `build.sh`).
- Parent plan: `aiplans/p1852_testmap_m1_engine_foundation_and_distribution.md`
  (reality anchors on `release.yml`, deviation 6).

## Owned files / provides / consumes

- **Owns:** `goengines/build.sh`; `.github/workflows/goengines-check.yml`;
  the `goengines` job and the `release needs: [plan, goengines]` edit in
  `.github/workflows/release.yml`; `aidocs/framework/go_engine.md` (build
  half — the engine half is M9.4's).
- **Provides:** release assets `ait-testmap_<V>_{linux,darwin}_{amd64,arm64}`
  and `ait-testmap_<V>_SHA256SUMS.txt` attached to every release.
- **Consumes:** M1.2 (t1852_2) — the module, its tests and benches.

## Step 0 — Reality check (MANDATORY, before any code; record the outcome here)

1. Re-read the proposal rows above and the parent plan's anchors.
2. Inspect the actual current state on the merge target: the `goengines/`
   tree M1.2 landed (name its task and commit) — module path, `cmd/*`
   entries, how `-X` variables are named; the current `release.yml` job
   graph and `action-gh-release` steps; `hugo.yml`'s `setup-go` step;
   whether `.aitask-scripts/VERSION` is still the version source.
3. Tabulate every difference: *proposal says / coarse plan says / repository has*.
4. Decide per difference: adapt; revise this plan; or revise the proposal.
   Record the decision and reason.
5. Send `/aitask-note` to every downstream child a difference breaks
   (t1852_5 consumes the asset names and the sums file).
6. Re-confirm every file touched is owned here.

**Outcome:** _(to be recorded when executed)_

## Implementation steps (coarse)

1. `goengines/build.sh`: `set -euo pipefail`; builds every `goengines/cmd/*`
   for the `linux,darwin × amd64,arm64` matrix with `CGO_ENABLED=0`,
   `-trimpath -buildvcs=false -ldflags "-s -w -X …version -X …commit -X
   …contract"`; `build.sh all` writes the four binaries and
   `ait-testmap_<V>_SHA256SUMS.txt`, `<V>` read from `.aitask-scripts/VERSION`.
2. `.github/workflows/goengines-check.yml`: on push / PR touching
   `goengines/**` — gofmt check, `go vet`, `go test`, the 2× bench rule.
3. `release.yml`: add the `goengines` job (`actions/setup-go` with
   `go-version-file: goengines/go.mod`, vet, test, `build.sh all`, upload
   artifact); `release` gains `needs: [plan, goengines]` and both
   `action-gh-release` steps list the assets. VERSION guard,
   `release-packaging.yml`, nfpm `arch: all` untouched; the tarball's explicit
   path list already excludes `goengines/`.
4. `aidocs/framework/go_engine.md` — build half: toolchain, matrix, ldflags,
   CI, release assets, how to build locally.

## Verification / acceptance

- `goengines/build.sh all` locally → four binaries + sums; `sha256sum -c` passes.
- `goengines-check.yml` triggers only on `goengines/**`; a gofmt violation
  fails it.
- `release.yml` is valid YAML; `release.needs` is `[plan, goengines]`; both
  release steps carry the engine assets; VERSION guard and `packaging`
  untouched.

## Step 9 reference

Archival and cleanup follow the shared `task-workflow` Step 9. Current-branch
profile: no worktree, no merge.
