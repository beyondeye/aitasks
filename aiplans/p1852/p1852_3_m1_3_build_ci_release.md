---
Task: t1852_3_m1_3_build_ci_release.md
Parent Task: aitasks/t1852_testmap_m1_engine_foundation_and_distribution.md
Sibling Tasks: aitasks/t1852/t1852_1_*.md, aitasks/t1852/t1852_2_*.md, aitasks/t1852/t1852_4_*.md, aitasks/t1852/t1852_5_*.md, aitasks/t1852/t1852_6_*.md
Archived Sibling Plans: aiplans/archived/p1852/p1852_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-09-25 10:56
---

# Plan: t1852_3 — M1.3 Build, CI and release

## Context

This is child M1.3 of t1852, test map module M1, wave B. It turns the `goengines/` Go module that M1.2 landed into:

- a single build command, `goengines/build.sh`;
- a CI check, `goengines-check.yml`;
- a `goengines` job in `release.yml` that attaches
  `ait-testmap_<V>_{linux,darwin}_{amd64,arm64}` and
  `ait-testmap_<V>_SHA256SUMS.txt` to every release. M1.5's
  `install_engine_binary()` and `ait engine build|cross` consume these.

It also writes the build half of `aidocs/framework/go_engine.md`.

Spec: `aidocs/testing_engine/n014_explorer_006_proposal.md`, specifically:

- the Module Map `#### M1` row M1.3;
- *Binary distribution (M1.3, M1.4)*;
- the M1 assumptions `assumption_go_toolchain_available`, `assumption_go_toolchain_ci_and_dev_only` and `assumption_platform_matrix_sufficient`;
- the M1 tradeoffs `tradeoff_compiled_component_cost` and `tradeoff_two_toolchains`.

The parent plan's deviation 6 covers the `goengines/` layout.

## Step 0 — Reality check (executed during verify-mode planning)

Inspected on `main` at `2d3376466`:

- M1.2 = **t1852_2, commit `33012bff7`**, amended by **t1872, commit `2d3376466`**, which added host-normalized bench calibration.
- Module `github.com/beyondeye/aitasks/goengines`. `go.mod` pins `go 1.26.0` and `toolchain go1.27.1`.
- The only executable is `cmd/ait-testmap`. The benchgate tool lives under `internal/tools/`, so it is never shipped.
- Build identity variables are `main.version` (default `devel`) and `main.commit` (default `unknown`), pinned by `TestLdflagsWiring`. That test already builds with `-trimpath -buildvcs=false -s -w`.
- `platform.AssetSuffix()` returns `<os>_<arch>`.
- `release.yml` runs `plan → release → packaging`. `release` has `needs: plan`, the VERSION guard at lines 30–37, the tarball's explicit path list with no `goengines/`, and two `softprops/action-gh-release@v3` steps with `files:` lists (lines 119–135).
- `hugo.yml` sets up Go with `actions/setup-go@v5` and `go-version-file: website/go.mod`.
- `.aitask-scripts/VERSION` = `0.35.1`, and it is still the version source.

| # | Proposal / coarse plan says | Repository has | Decision |
|---|---|---|---|
| 1 | ldflags `-X version/commit/contract` | only `-X main.version` / `-X main.commit`; the contract is the source constant `testmap.Contract` (t1852_2 decision, sent by note) | **adapt**: build.sh sets version and commit only; `go_engine.md` says why. The proposal is already superseded by the M1.2 record, so no proposal edit |
| 2 | "the 2× bench rule" in goengines-check.yml | since t1872, the gate is host-scaled (threshold 1.6) and **not yet portable**; the README requires the CI step to start advisory, and t1878 validates it | **adapt**: the bench job is `continue-on-error: true` and writes CPU model, nproc, a per-benchmark **scaled-ratio table** and the raw gate output to the job summary. The gate's `BENCH_OK` line has no ratio (`benchgate.go:336`), so `goengines/ci/benchci.sh summary` recomputes `cur / (base × class scale)` for every benchmark (step 3b). It also gets a `workflow_dispatch` input `seed_regression` that divides every non-calibration baseline by 2.1 inside the job, which is the sample t1878 must collect. t1878 can then gather samples without editing the workflow |
| 3 | CI "records its own baselines?" (open question) | t1872 decided: CI uses the committed, calibrated baseline | adapt (nothing to record in CI) |
| 4 | triggers "on `goengines/**`" | a workflow edit would otherwise never exercise itself | **adapt**: the paths also include this workflow, `release.yml` and the three committed guard tests, and `check` runs those tests. Without that, a `release.yml`-only edit would bypass the structure guard (user review) |
| 5 | build.sh has only `all` | M1.5's `ait engine build` needs a host build with a `<V>-dev+<sha>` version; `--engine-from-source` needs off-matrix hosts | **adapt**: build.sh gains `host` (the default) / `<os>_<arch>` targets, `--version`, `--commit` and `--out`, plus `BUILT:`/`SUMS:` stdout lines. `all` keeps the proposal's exact asset names |
| 6 | "`.sha256` sidecar short-circuit" (M1.5) | nothing in M1.3's contract produces a sidecar | read as installer-side (M1.5 writes it beside the installed binary); no release asset. Note to t1852_5 |
| 7 | build output location unspecified | `goengines/.gitignore` ignores only `/ait-testmap` | **adapt**: default `--out goengines/dist/`, adding `/dist/` to `goengines/.gitignore`. This is a one-line extension of M1.2's file (M1.2 is archived, so there is no concurrent owner) |
| 8 | setup-go reads go.mod | whether setup-go@v5 honours the `toolchain` line is not guaranteed | **adapt**: workflow-level `GOTOOLCHAIN: auto`, so Go switches to 1.27.1 whatever setup-go installed. Each job logs `go version` from `goengines/`. `gofmt` is invoked as `"$(go env GOROOT)/bin/gofmt"`, so it is the switched toolchain's |

Notes to send, which affect downstream siblings:

- **t1852_5**: the build.sh CLI and output lines, the dist dir, the sums format, and the sidecar reading. Also that `go_engine.md` exists, so the `CLAUDE.md` Engine block can point to it.
- **t1878**: the bench job name, the `seed_regression` dispatch input, and the summary's scaled-ratio table, including how `n/a` rows arise. The ratio calculation ships here, so t1878 only collects and judges.

Owned files, re-confirmed: `goengines/build.sh`, `goengines-check.yml`, the `release.yml` job and the `needs:` edit, and `go_engine.md`. Also the new `goengines/ci/benchci.sh`, the new tests `tests/test_goengines_build.sh`, `tests/test_goengines_benchci.sh` and `tests/test_release_workflow_goengines.py`, plus the `/dist/` line in `goengines/.gitignore` (item 7).

## Implementation steps

### 1. `goengines/build.sh` (new, executable)

Standalone; it sources no framework lib, because goengines is self-contained. It starts with `#!/usr/bin/env bash` and `set -euo pipefail`, then `cd` to its own directory, which is the module root.

```
Usage: goengines/build.sh [--version V] [--commit SHA] [--out DIR] [TARGET...]
  TARGET  all          the release matrix linux_amd64 linux_arm64 darwin_amd64 darwin_arm64,
                       plus <name>_<V>_SHA256SUMS.txt per cmd
          host         this machine's $(go env GOOS)_$(go env GOARCH)   (default)
          <os>_<arch>  any Go-supported pair (off-matrix hosts build from source)
  --version  default: contents of ../.aitask-scripts/VERSION
  --commit   default: git rev-parse HEAD, else "unknown"
  --out      default: goengines/dist (created); a relative path resolves from the caller's cwd
```

- **Validation.** Exit 2 with a `USAGE:` line on stderr for:
  - a version that does not match `^[A-Za-z0-9._+-]+$`, because it feeds a filename and `-ldflags`;
  - a commit that does not match `^[A-Za-z0-9]+$`;
  - a target that does not match `^(all|host|[a-z0-9]+_[a-z0-9]+)$`;
  - an unknown option.

  An empty VERSION file dies with exit 1.
- **Resolve `--out` before `cd`.** Use `mkdir -p` then `cd && pwd`.
- **cmds** = each `cmd/*/` directory that contains a `.go` file, sorted.
- **Per target and cmd:**

  ```
  CGO_ENABLED=0 GOOS=$os GOARCH=$arch go build -trimpath -buildvcs=false \
    -ldflags "-s -w -X main.version=$V -X main.commit=$C" \
    -o "$out/${name}_${V}_${os}_${arch}" "./cmd/$name"
  ```

  After each build, print `BUILT:<abs path>` on stdout. Progress and `go version` go to stderr.
- **For `all`:** for each cmd, write `${name}_${V}_SHA256SUMS.txt` in `$out`. It holds exactly the four files of this run, in sorted order and in `<hex>  <basename>` format, so `sha256sum -c` works in `$out`.
  - Hashing uses `sha256sum`, falling back to `shasum -a 256`. This is the same order as `artifact_sha256` in `.aitask-scripts/lib/artifact_utils.sh`, which cannot be sourced here because of the standalone rule.
  - The file is written through a temp file in `$out` and then `mv`'d into place.
  - Print `SUMS:<abs path>`.
  - `all` combined with other targets is a usage error.
- **Stale files.** The script deletes nothing in `$out`. Releases build from a fresh CI checkout, and the sums file names only this run's binaries.

### 2. `goengines/.gitignore`

Add `/dist/`.

### 3. `.github/workflows/goengines-check.yml` (new)

- **Triggers:** `push` and `pull_request`, plus `workflow_dispatch` with input `seed_regression` (boolean, default false). Both push and PR use the same `paths:` list:

  ```
  goengines/**
  .github/workflows/goengines-check.yml
  .github/workflows/release.yml
  tests/test_goengines_build.sh
  tests/test_goengines_benchci.sh
  tests/test_release_workflow_goengines.py
  ```

  The last four entries are there so the committed guards also run when the workflows or the guards themselves change. This addresses the user's review concern: without them, a `release.yml`-only edit could bypass the structure test.
- **Permissions:** `contents: read`.
- **Workflow env:** `GOTOOLCHAIN: auto`.
- **Every job** runs `actions/checkout@v6` and then `actions/setup-go@v5` with `go-version-file: goengines/go.mod` and `cache-dependency-path: goengines/go.sum`. Steps default to `working-directory: goengines`.
- **Job `check`**, in order:
  1. Log `go version`.
  2. gofmt: `test -z "$("$(go env GOROOT)/bin/gofmt" -l .)"`, printing the offending files on failure.
  3. `go vet ./...`
  4. `go test ./...`
  5. `./build.sh all --out "$RUNNER_TEMP/dist"`, then `cd "$RUNNER_TEMP/dist" && sha256sum -c ait-testmap_*_SHA256SUMS.txt`. This is a cross-build smoke test, so a broken matrix fails before a tag, not at release time.
  6. The repository-side guards run from the repo root:
     - `actions/setup-python@v5` (3.12), then `python -m pip install pyyaml`, then `python -m unittest tests/test_release_workflow_goengines.py`;
     - `bash tests/test_goengines_build.sh`;
     - `bash tests/test_goengines_benchci.sh`.
- **Job `bench`**, with `continue-on-error: true`. A comment says this is advisory until t1878 meets the README's promotion criteria.
  1. Prepare the baseline:
     - with `inputs.seed_regression`: `./ci/benchci.sh seed bench/baseline.txt "$RUNNER_TEMP/baseline.txt"`;
     - otherwise: copy `bench/baseline.txt` to the same path.
  2. Run `go run ./internal/tools/benchgate -baseline "$RUNNER_TEMP/baseline.txt" 2>&1 | tee "$RUNNER_TEMP/bench.out"` with `set -o pipefail`. The gate runs its own producer; nothing is piped into it.
  3. An `if: always()` summary step appends the following to `$GITHUB_STEP_SUMMARY`:
     - the mode (healthy or seeded);
     - the CPU model from `/proc/cpuinfo`;
     - `nproc`;
     - `./ci/benchci.sh summary "$RUNNER_TEMP/baseline.txt" "$RUNNER_TEMP/bench.out"`, which is the per-benchmark scaled-ratio table (step 3b);
     - a fenced block with the raw gate output.

### 3b. `goengines/ci/benchci.sh` (new; CI helper, never shipped: build.sh builds only `cmd/*`)

It exists because the gate's `BENCH_OK:<n>|<cur>|<base>` line carries no ratio (`internal/benchgate/benchgate.go:336`), and t1878's promotion rule needs every benchmark's **scaled** ratio, healthy and seeded alike. Bash with awk, `set -euo pipefail`. Two subcommands:

- **`seed <in> <out>`**:
  - copies comment lines verbatim;
  - for every data line whose name is not `internal/benchgate.BenchmarkCalibrate*`, divides field 2 by 2.1 (`%.6f`, which stays finite and > 0) and keeps the trailing `budget=`/`cal=` fields;
  - leaves calibration lines untouched.
- **`summary <baseline-used> <gate-output>`** prints one markdown table with the columns `benchmark | class | current ns/op | baseline ns/op | scale | scaled ratio | verdict`.
  - **Inputs:**
    - class comes from the baseline's `cal=` field (default `cpu`);
    - baseline ns/op comes from the baseline file, so a row can still be built when the gate emitted only `BENCH_OVER_BUDGET` (which carries the budget, not the baseline);
    - current ns/op is field 2 of the gate's `BENCH_OK` / `BENCH_REGRESSION` / `BENCH_OVER_BUDGET` / `BENCH_NEW` line for that name;
    - scale is **recomputed** from the scale line's unrounded fields: `BENCH_SCALE:<class>|<rounded>|<cur cal>|<base cal>` gives `scale = <cur cal> / <base cal>`. The printed `<rounded>` field is `%.3f` (`benchgate.go:366`) while the gate's verdict uses the full-precision `c / b.NsOp`. Near t1878's 1.3 limit, a scale of 0.2504 printed as 0.250 turns a true 1.299 into 1.301 (user review). Both calibration fields are `fmtNs` = `FormatFloat(…, 'f', -1, 64)`, which round-trips exactly, and awk's doubles do the same `c / b` then `cur / (base × s)` operations as `benchgate.go:324`, so the summary reproduces the gate's value.
  - **Ratio** = `cur / (base × scale)`, printed `%.6f`, because any 2–3 decimal display re-creates a rounding ambiguity at the limit. The helper reports the number and does not judge it against 1.3; t1878 judges.
  - **Verdict:** `ok` / `regression` / `over-budget`, from the gate's own line.
  - **`n/a` ratios.** The ratio is `n/a` when:
    - the class has no trustworthy scale (`BENCH_SCALE_IMPLAUSIBLE`, `BENCH_CALIBRATION_MISSING` or `BENCH_UNSCALED` for it; the gate falls back to scale 1 there, which says nothing about the host);
    - the benchmark is `BENCH_MISSING` (verdict `missing`);
    - the benchmark is `BENCH_NEW` (verdict `new`, no baseline).
  - **Scale lines.** The table is followed by the `BENCH_SCALE*` lines verbatim.
  - **Exit status** is 0 whenever it can read both files. An unreadable file prints a note and still exits 0, because the summary must never mask or replace the gate's verdict.

### 3c. `tests/test_goengines_benchci.sh` (new)

Uses a fixture baseline and a fixture gate output, both in `mktemp -d` and covering all three classes. Cases:

1. `seed` divides only non-calibration lines, keeps `cal=`/`budget=` and comments, and the result parses as floats.
2. `summary` gives the expected ratio for a `BENCH_OK` row, where cur, base and scale are chosen so the ratio is exact, e.g. 1.250.
3. `summary` gives the expected ratio for a `BENCH_OVER_BUDGET`-only row, using the baseline taken from the baseline file.
4. For a `BENCH_REGRESSION` row, the ratio agrees at 2 decimal places with the ratio the gate itself printed.
4b. **Boundary case near 1.3.** The fixture scale line is `BENCH_SCALE:cpu|0.250|250400|1000000` (true scale 0.2504), with a `BENCH_OK` row whose cur/base give a true ratio of 1.299. The summary must print `1.299000`, not the 1.301 the rounded scale would give. Negative control: a scratch copy of `benchci.sh` patched to use field 2 prints `1.301…`, and the assertion fails on it. The copy lives under `mktemp -d`; the real script is never edited.
5. A class under `BENCH_SCALE_IMPLAUSIBLE` produces `n/a`.
6. `BENCH_MISSING` and `BENCH_NEW` produce `n/a` rows.
7. An unreadable input exits 0.

### 4. `.github/workflows/release.yml`

- **New job `goengines`:**
  - `needs: plan`, `runs-on: ubuntu-latest`, `env: GOTOOLCHAIN: auto`.
  - Steps: checkout@v6, then setup-go@v5 (same `with:` as step 3), then `go version`, `go vet ./...`, `go test ./...`, `./build.sh all` (default `--out dist`), and `sha256sum -c` in `goengines/dist`.
  - Then `actions/upload-artifact@v4` with `name: goengines-dist`, `path: goengines/dist/` and `if-no-files-found: error`.
- **`release`:**
  - `needs: plan` becomes `needs: [plan, goengines]`.
  - After checkout, add `actions/download-artifact@v4` with `name: goengines-dist` and `path: goengines/dist`.
  - Both `action-gh-release` steps add `goengines/dist/*` to `files:` and set `fail_on_unmatched_files: true`, so a release without engine assets fails loudly instead of silently shipping none.
  - The VERSION guard, the tarball list and `packaging` stay byte-identical.
  - Leave `release-packaging.yml` untouched.

### 5. `aidocs/framework/go_engine.md` (new; build half)

Current-state prose. Sections:

- **Toolchain:** go.mod pins, `GOTOOLCHAIN=auto`, Go is build-time only.
- **Building:**
  - `build.sh` usage and targets;
  - the `BUILT:`/`SUMS:` lines;
  - `dist/`;
  - a host dev build with `--version <V>-dev+<sha>`.
- **Build identity:**
  - the two `-X` names and their defaults;
  - why the contract is a source constant;
  - `-trimpath -buildvcs=false -s -w` and `CGO_ENABLED=0`.
- **Release matrix and assets:** names, the sums format, how to verify.
- **CI (`goengines-check.yml`):** the jobs, the advisory bench rule with a pointer to `goengines/README.md` *Host normalization*, `seed_regression`, the `benchci.sh summary` ratio table (columns, the `n/a` cases), and the committed guards `check` runs with their trigger paths.
- **Release job wiring:** needs, the artifact hand-off, both release steps, and the fact that the tarball excludes `goengines/`.
- **Engine internals:** a placeholder heading saying the engine half is documented by M9.4, with a pointer to `goengines/README.md` for the interfaces.

### 6. `tests/test_goengines_build.sh` (new)

- Sources `tests/lib/asserts.sh`.
- Skips (PASS, exit 0 with a `SKIP:` line) when `go` is absent.
- Uses `mktemp -d` and a trap cleanup.

Cases:

1. **Host build.** `--version 9.9.9-test --commit abc123 --out $tmp/h` prints one `BUILT:` line. The file is `ait-testmap_9.9.9-test_<goos>_<goarch>`, and `version --json` reports version `9.9.9-test` and commit `abc123`.
2. **Default version.** With no `--version`, the filename carries the contents of `.aitask-scripts/VERSION`.
3. **`all`.**
   - Produces exactly four binaries and a sums file with four lines, and `sha256sum -c` passes.
   - `go version -m` on each binary shows its `GOOS`/`GOARCH`, `CGO_ENABLED=0` and `-trimpath=true`, and no `vcs.revision`.
   - No `benchgate` file is present.
4. **Usage errors.** A bad version (`1 0`), a bad target (`Linux-amd64`), `all host` and an unknown option each exit 2 and create no output.

### Post-phase (risk mitigations)

1. [release_workflow_structure_test] Add `tests/test_release_workflow_goengines.py` (unittest style, PyYAML, reading the two workflow files from the repo root). It asserts:
   - `jobs.release.needs == ['plan', 'goengines']`;
   - `jobs.goengines` has an `actions/upload-artifact` step named `goengines-dist` with `if-no-files-found: error`, and `jobs.release` has an `actions/download-artifact` step for `goengines-dist` into `goengines/dist`;
   - each of the two `softprops/action-gh-release` steps has `goengines/dist/*` in `files` and `fail_on_unmatched_files: true`, and still carries the tarball and `packaging/shim/ait`;
   - the `Verify VERSION file matches tag` step is still present in `release` and runs before the gh-release steps;
   - `jobs.packaging.needs == ['plan', 'release']`;
   - `goengines-check.yml`'s push and PR `paths` each equal the six-entry list of step 3, including `.github/workflows/release.yml` and this test file, so the guard runs whenever what it guards changes;
   - `jobs.check` runs this test file, `tests/test_goengines_build.sh` and `tests/test_goengines_benchci.sh`, checked by the text of its `run:` steps;
   - `jobs.bench.continue-on-error` is true and `jobs.check` has no `continue-on-error`.

   The YAML key `on` parses as `True` in PyYAML, so read `wf.get('on', wf.get(True))`. As a negative control, confirm it fails on a scratch copy of `release.yml` with `needs: plan`. The test takes the workflow directory from an env override (`AIT_WORKFLOWS_DIR`), so the control does not touch the real file.

## Verification

- `bash tests/test_goengines_build.sh`, which covers the task's "four binaries + sums; `sha256sum -c` passes".
- `goengines/build.sh all` from the repo root, then an `ls goengines/dist`, then `git status` shows `dist/` is ignored.
- Workflow checks:
  - Run `actionlint` on both workflows (installed to the scratchpad via `go install`); if that is unavailable, fall back to a PyYAML parse.
  - A PyYAML assertion script covering:
    - `release.needs == ['plan','goengines']`;
    - both release steps' `files` contain `goengines/dist/*`;
    - the VERSION guard step and the `packaging` job are unchanged against `git show HEAD:.github/workflows/release.yml`;
    - the `goengines-check` paths equal the six-entry list, and the guards run in `check`. This part is now the committed test from the post-phase;
    - the bench job has `continue-on-error: true`.
- Replay the gofmt step locally on a scratch copy of `goengines/` with an injected mis-formatted file, and check that it fails. This covers "a gofmt violation fails it" without pushing.
- Run the real gate on a seeded baseline: `./ci/benchci.sh seed bench/baseline.txt $tmp/seeded`, then `go run ./internal/tools/benchgate -baseline $tmp/seeded`. It should report `BENCH_REGRESSION` and exit 1, which shows the seeding produces a parseable baseline. Then run `benchci.sh summary` on that real output: every non-calibration row gets a numeric ratio, and each regression row agrees at 2 decimal places with the gate's printed ratio. For every class, also check that `scale` recomputed from fields 3/4, rounded to 3 decimal places, equals the gate's printed field 2. Repeat on a healthy run: every row is `ok` with a numeric ratio. Both runs use real benchgate output, not fixtures only.
- `bash tests/test_goengines_benchci.sh`, `python3 -m unittest tests/test_release_workflow_goengines.py`.
- `shellcheck goengines/build.sh goengines/ci/benchci.sh tests/test_goengines_build.sh tests/test_goengines_benchci.sh`.

## Risk

### Code-health risk: medium
- `release.yml` is on every release's critical path. `release` now waits on `goengines`, so a failing `go test` or cross-build blocks all framework releases. This is the intended `tradeoff_compiled_component_cost`, but it enlarges the release's failure surface. `goengines-check.yml` runs the same vet, test and cross-build on every `goengines/**` push, so a breakage surfaces before a tag · severity: medium · → mitigation: none (by design; early detection via goengines-check)
- The static structure of the workflows (needs, asset globs, advisory bench) is only checked once by a throwaway script. A later `release.yml` edit could silently drop the engine assets or the `needs:` edge · severity: low (residual — addressed by inline post-phase release_workflow_structure_test) · → mitigation: inline post-phase release_workflow_structure_test

### Goal-achievement risk: medium
- The release wiring cannot be exercised end to end before a real `v*` tag: the artifact hand-off between jobs, the `goengines/dist/*` glob in both release steps, `fail_on_unmatched_files`, and setup-go's toolchain behaviour on the runner. If any of these is wrong, the assets M1.5 fetches are missing from the next release · severity: medium · → mitigation: first_release_engine_assets_check
- The bench job's portability on hosted runners is unproven. This is covered by design: the job is advisory, and t1878 owns the validation. The per-benchmark scaled ratios t1878 judges are produced here by `benchci.sh summary`, which recomputes the gate's formula outside the gate. A drift between the two formulas would mislead promotion; the summary test's regression-row cross-check and the live seeded replay pin the agreement · severity: low · → mitigation: none (t1878 exists; agreement pinned by test)

### Planned mitigations
- timing: post-phase | name: release_workflow_structure_test | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: later workflow edits silently dropping engine assets / the needs edge | desc: committed PyYAML structure test for release.yml and goengines-check.yml
- timing: after | name: first_release_engine_assets_check | type: manual_verification | priority: medium | effort: low | inline_risk: high | added_complexity: low | addresses: release wiring unverifiable before a real tag | desc: on the next v* release confirm the 4 ait-testmap binaries + SHA256SUMS are attached, sha256sum -c passes, a linux binary's version --json echoes <V>, and packaging still ran

## Step 9 reference

Archival and cleanup follow the shared task-workflow Step 9. Current-branch profile: no worktree, no merge.

## Post-Review Changes

### Change Request 1 (2026-09-25 11:40)
- **Requested by user:** `build.sh` treated an explicitly empty `--version` / `--commit` / `--out` as omitted (the defaults were chosen by empty-string checks), so `--version '' --commit ''` exited 0 with a repo-stamped build. The VERSION reader's `tr -d '[:space:]'` turned a malformed `1 2` into `12`.
- **Changes made:**
  - `build.sh` records whether each option was given (`*_set`). An explicit empty value, or an option with no value, is a usage error (exit 2).
  - VERSION is read with `$(<file)`, stripping only the trailing newline and one CR. Empty or malformed content dies with exit 1, naming the content.
  - `--help` range extended to the new header.
  - Tests: four refusals (empty `--version`, `--commit`, `--out`, and `--version` with no value), plus a fake-tree VERSION probe covering `1 2` (refused as malformed), CRLF (accepted) and empty (refused). The suite is now 52 checks.
  - `go_engine.md` exit-status list updated.
- **Files affected:** `goengines/build.sh`, `tests/test_goengines_build.sh`, `aidocs/framework/go_engine.md`

## Final Implementation Notes
- **Actual work done:** Implemented every plan step as written:
  - `goengines/build.sh` (host / `<os>_<arch>` / `all`, `BUILT:`/`SUMS:` lines);
  - the `/dist/` gitignore line;
  - `goengines/ci/benchci.sh` (`seed`, `summary`);
  - `.github/workflows/goengines-check.yml` (a required `check` and an advisory `bench`);
  - the `goengines` job plus the `release` edits in `release.yml`;
  - the build half of `aidocs/framework/go_engine.md`;
  - three tests: `tests/test_goengines_build.sh` (52 checks), `tests/test_goengines_benchci.sh` (28) and `tests/test_release_workflow_goengines.py` (9, the inline post-phase mitigation `release_workflow_structure_test`).
- **Deviations from plan:**
  - The sums file is written through a dot-prefixed temp in `$out` and then renamed, as planned.
  - The planned PyYAML throwaway assertion script was not written separately: the committed structure test covers it.
  - Otherwise none beyond Change Request 1 (strict empty-option and VERSION handling).
- **Issues encountered:**
  - `awk -v` processes escapes, so `\.` in the calibration regex warned. It became `[.]`.
  - The structure test first split `files:` on whitespace, which broke `${{ github.ref_name }}` apart. It now splits on lines.
  - The live healthy gate on this unpinned, loaded host scaled `BlobDigest` (sha1 class) at 0.52. The gate still passed, but this is the kind of evidence t1878 collects on runners.
- **Key decisions:**
  - Workflow-level `GOTOOLCHAIN: auto`, and `gofmt` taken from `$(go env GOROOT)`, so both follow the pinned 1.27.1 toolchain. Locally that resolved to `toolchain@v0.0.1-go1.27.1`.
  - `fail_on_unmatched_files: true` on both release steps.
  - The benchci summary rebuilds each class scale from the scale line's unrounded fields 3 and 4 (field 2 is `%.3f`). It prints ratios at 6 decimal places and never judges them.
  - `workflow_dispatch` with `seed_regression`, so t1878 can collect samples without editing the workflow.
- **Verification:**
  - Local `build.sh all`: four binaries plus the sums file, and `sha256sum -c` passes.
  - Live gate: seeded (exit 1, three `BENCH_REGRESSION`) and healthy (exit 0). The summary's ratios agree with the gate's printed ones at 2 decimal places, and the recomputed scales round to the printed ones.
  - The structure test's negative controls (drop `needs: goengines`, drop the `release.yml` trigger path, drop one asset glob) each fail exactly the targeted test.
  - The benchci boundary control (field-2 scale) yields 1.301078 instead of 1.299000.
  - gofmt step replay: clean gives rc 0, an injected violation gives rc 1.
  - actionlint 1.7.12 is clean on `goengines-check.yml`.
  - `shellcheck -x` and the cd-guard lint are clean.
- **Upstream defects identified:** None. The three actionlint `SC2086` info findings in `release.yml`'s existing "Extract changelog" step (unquoted `$GITHUB_OUTPUT`) are pre-existing style/lint items, not defects.
- **Notes for sibling tasks:**
  - **t1852_5, `build.sh` CLI:**
    - `goengines/build.sh [--version V] [--commit SHA] [--out DIR] [all|host|<os>_<arch>...]`. The default target is `host` and the default out is `goengines/dist/`.
    - stdout carries `BUILT:<abs>` per binary and `SUMS:<abs>` per sums file (only with `all`).
    - Exit codes: 1 for a build failure or a bad VERSION file, 2 for usage, including explicit empty values.
    - For the dev slot, `ait engine build` passes `--version "<V>-dev+<sha>"` and `--out`.
  - **t1852_5, assets:** release assets are `ait-testmap_<V>_<os>_<arch>` plus `ait-testmap_<V>_SHA256SUMS.txt` in `<hex>  <basename>` format.
  - **t1852_5, other:** there is no `.sha256` sidecar asset; the sidecar is installer-side. `go_engine.md` exists for the `CLAUDE.md` Engine block to point at.
  - **t1878:** the `bench` job in `goengines-check.yml`, dispatch input `seed_regression`, and a summary table with columns `benchmark|class|current|baseline|scale|scaled ratio|verdict`.
