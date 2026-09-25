---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: [t1852_2]
issue_type: feature
status: Done
labels: [testmap, go_engine, release_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1882]
assigned_to: dario-e@beyond-eye.com
anchor: 1852
implemented_with: claudecode/opus5_5
created_at: 2026-09-22 17:27
updated_at: 2026-09-25 11:48
completed_at: 2026-09-25 11:48
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1852_2** id=2026-09-24T06:18:15Z.ad6b23be383bb3acc9808247 from=t1852_2 from_verified=yes at=2026-09-24T06:18:15Z base=33012bff731972003d827cd6b152419d11ab9353 base_branch=main dirty=yes host=omg16
>
> | M1.2 landed in commit 33012bff7 (goengines/). Things your build/CI/release work consumes; the exact shapes are in goengines/README.md "## Interfaces", each pinned by a named test:
> | - Build identity ldflags for every cmd/*: `-X main.version=<V> -X main.commit=<sha>` only. There is NO contract ldflag: the contract is the source constant testmap.Contract (a deliberate deviation from the proposal's "-X version/commit/contract" — an ldflag would let a build claim compatibility it doesn't implement). TestLdflagsWiring pins the variable names.
> | - go.mod: `go 1.26.0`, `toolchain go1.27.1` — setup-go with go-version-file: goengines/go.mod.
> | - Bench gate: `cd goengines && go run ./internal/tools/benchgate -baseline bench/baseline.txt`. It runs `go test -run ^$ -bench . -count 1 ./...` itself; don't pipe go test into it. Full mode (the default) is the gate and fails on regression >2x, budget, a missing baseline bench, an empty set or a producer failure; `-partial` is a developer mode and must never be the gate. The tool lives under internal/tools/, so a build.sh loop over cmd/* never ships it.
> | - Baselines are one dev host's numbers; normalizing them across hosts is t1872 (bench_host_normalization). Decide there, together with t1872, whether CI records its own baselines or uses calibration.
> | - Also check in CI: `test -z "$(gofmt -l .)"`, `go vet ./...`, `go test ./...` (tests that build binaries skip under -short).

> **✉ note:t1872** id=2026-09-24T12:44:47Z.5615671a3aabcb305a03570a from=t1872 from_verified=yes at=2026-09-24T12:44:47Z base=2d3376466a74df46d3f195779e988e4e6bffb014 base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1872 (bench host normalization), tree-relative to commit 2d3376466. The goengines benchgate is host-normalized but NOT yet proven portable.
> | 
> | For goengines-check.yml:
> | 1. Run the gate with its default producer: `cd goengines && go run ./internal/tools/benchgate -baseline bench/baseline.txt`. It runs `go test -p 1 -cpu 1 -run ^$ -bench . -count 3 ./...` itself; a custom producer must keep -p 1, -cpu 1 and -count 3.
> | 2. The bench step should start ADVISORY (`continue-on-error: true`, not a required check). It becomes required only after t1878 (bench_calibration_ci_validation, depends on t1852_3) meets the promotion criteria in goengines/README.md "Host normalization".
> | 3. Suggest writing CPU model (/proc/cpuinfo), nproc, every BENCH_SCALE: line and all benchmark lines to the job summary, so t1878 can collect samples from fresh runner VMs.
> | 4. Protocol lines added: BENCH_SCALE:<class>|<scale>|<cur>|<base>, BENCH_SCALE_IMPLAUSIBLE:<class>|..., BENCH_CALIBRATION_MISSING:<class>|<side>, BENCH_UNSCALED:<class>|<side>. Scaled ratios fail above benchgate.Threshold = 1.6 (the 2x rule judged with margin).
> | 
> | Decision your task body asked to make together with t1872: CI uses the committed, calibrated baseline; it does NOT record its own (hosted runners change machine per job). Rationale and single-host measurements are in the README.

> **👁 note:read** id=2026-09-24T18:58:47Z.cfdaa262d518358a9cd48ad8 by=t1852_3 at=2026-09-24T18:58:47Z mode=explicit ids=2026-09-24T06:18:15Z.ad6b23be383bb3acc9808247,2026-09-24T12:44:47Z.5615671a3aabcb305a03570a

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-25T08:02:27Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-25T08:44:26Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-09-25T08:48:16Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:5b281a24a25568c0

> **✅ gate:risk_evaluated** run=2026-09-25T08:48:16Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1852_3/risk_evaluated_2026-09-25T08:48:16Z-risk_evaluated-a1.log`
