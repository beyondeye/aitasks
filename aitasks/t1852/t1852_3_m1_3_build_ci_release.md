---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [testmap, go_engine, release_scripts]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-09-22 17:27
updated_at: 2026-09-22 17:27
---

## Context

Child **M1.3 — Build, CI and release** of t1852 (test map feature, module M1).
Wave **B**. Turns the M1.2 module into release assets the installer (M1.5)
fetches. **Provider:** M1.2 (`t1852_2`) — the `goengines/` module and its
tests must exist before this child is picked.

Authoritative specification: `aidocs/testing_engine/n014_explorer_006_proposal.md`
— Module Map `#### M1` row M1.3, component *Binary distribution (M1.3, M1.4)*,
*Assumptions → Engine, distribution and install (M1)*
(`assumption_go_toolchain_available`, `assumption_go_toolchain_ci_and_dev_only`,
`assumption_platform_matrix_sufficient`), *Tradeoffs → Engine and
distribution (M1)* (`tradeoff_compiled_component_cost`, `tradeoff_two_toolchains`).
Parent plan: `aiplans/p1852_testmap_m1_engine_foundation_and_distribution.md`.

**Coarse plan only.** The child plan `aiplans/p1852/p1852_3_m1_3_build_ci_release.md`
records what the proposal fixes for M1.3 and does not design internals; its
**Step 0 — Reality check** (mandatory, before any code, recorded in the plan)
inspects the actual `goengines/` tree M1.2 landed (name the task and commit),
the current `release.yml` job graph and `hugo.yml`'s `setup-go` step.

## Scope (from the proposal)

- `goengines/build.sh` — the single build and matrix command: builds every
  `goengines/cmd/*` for `linux,darwin × amd64,arm64`, `CGO_ENABLED=0`,
  `-trimpath -buildvcs=false -ldflags "-s -w -X version/commit/contract"`;
  `build.sh all` produces `ait-testmap_<V>_{linux,darwin}_{amd64,arm64}` and
  `ait-testmap_<V>_SHA256SUMS.txt` (`<V>` = `.aitask-scripts/VERSION`).
- `.github/workflows/goengines-check.yml` — gofmt, vet, test and the 2× bench
  rule on push / PR touching `goengines/**`.
- `release.yml` — a `goengines` job (`actions/setup-go` with
  `go-version-file: goengines/go.mod`, `go vet`, `go test`, `build.sh all`)
  whose assets are attached by **both** `action-gh-release` steps, with
  `release needs: [plan, goengines]`; the VERSION-matches-tag guard is
  unchanged; `release-packaging.yml` and nfpm `arch: all` are untouched; the
  tarball's explicit path list already excludes `goengines/`.
- `aidocs/framework/go_engine.md` — the **build half** (toolchain, matrix,
  ldflags, CI, release assets); the engine half is M9.4's.

## Key files to modify

- `goengines/build.sh` — new (owned).
- `.github/workflows/goengines-check.yml` — new (owned).
- `.github/workflows/release.yml` — the `goengines` job and the
  `release needs:` edit (owned edit).
- `aidocs/framework/go_engine.md` — new, build half (owned half).

## Reference files for patterns

- `.github/workflows/release.yml` (jobs `plan` → `release` → `packaging`,
  two `softprops/action-gh-release@v3` steps with `files:` lists).
- `.github/workflows/hugo.yml` lines 38–40 (`actions/setup-go@v5`,
  `go-version-file`).
- `.github/workflows/release-packaging.yml` for the checksum idiom
  (`sha256sum … | cut -d' ' -f1`).
- `aidocs/framework/shell_conventions.md` for `build.sh` (shebang,
  `set -euo pipefail`).

## Provides / consumes

- **Provides:** the release assets `ait-testmap_<V>_<os>_<arch>` + sums that
  M1.5's `install_engine_binary()` fetches by exact version.
- **Consumes:** M1.2 (`t1852_2`).

## Implementation plan (coarse)

1. Step 0 — Reality check.
2. `build.sh` with the matrix and `all`; local run yields the four binaries
   and the sums file.
3. `goengines-check.yml`; `release.yml` job + `needs:`; verify with
   `actionlint` or a dry read that both release steps list the assets.
4. `aidocs/framework/go_engine.md` build half.

## Verification

- `goengines/build.sh all` locally → four binaries + `SHA256SUMS.txt`;
  `sha256sum -c` passes.
- `goengines-check.yml` triggers only on `goengines/**`; a PR with a gofmt
  violation fails it.
- `release.yml` parses; `release` has `needs: [plan, goengines]`; both
  `action-gh-release` steps carry the engine assets; VERSION guard and
  `packaging` job untouched.
