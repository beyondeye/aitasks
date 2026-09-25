# Go engines: build, CI and release

The framework's Go executables live in one module, `goengines/`
(`github.com/beyondeye/aitasks/goengines`), one executable per
`goengines/cmd/<name>/`. Today that is `ait-testmap`, the test map engine.
This document covers how they are built, checked and released. The module's
layout, the rules for engine submodules and every consumed interface shape are
in `goengines/README.md`.

Go is a **build-time dependency only**. Framework developers and release CI need
it; target-project users receive prebuilt binaries. `goengines/` is framework
repository only — the release tarball's explicit path list does not include it.

## Toolchain

`goengines/go.mod` pins `go 1.26.0` (the minimum) and `toolchain go1.27.1`. With
`GOTOOLCHAIN=auto` (Go's default, and set explicitly in both workflows) an older
local `go` fetches and switches to the pinned toolchain once. In CI,
`actions/setup-go` installs from `go-version-file: goengines/go.mod` and the
`auto` switch guarantees the pinned version whatever setup-go chose; each job
logs `go version`. `gofmt` is run as `"$(go env GOROOT)/bin/gofmt"` so it is the
switched toolchain's, not whichever `gofmt` is first on `PATH`.

## Building: `goengines/build.sh`

The single build and matrix command for every `cmd/*`:

```bash
goengines/build.sh [--version V] [--commit SHA] [--out DIR] [TARGET...]
```

| target | builds |
|---|---|
| `host` (default) | this machine's `$(go env GOOS)_$(go env GOARCH)` |
| `<os>_<arch>` | any pair Go supports — off-matrix hosts build from source this way |
| `all` | the release matrix `linux_amd64 linux_arm64 darwin_amd64 darwin_arm64`, plus a sums file per executable; cannot be combined with other targets |

| option | default |
|---|---|
| `--version` | the contents of `.aitask-scripts/VERSION` |
| `--commit` | `git rev-parse HEAD`, else `unknown` |
| `--out` | `goengines/dist/` (gitignored); a relative path resolves from the caller's working directory |

Every binary is named `<name>_<V>_<os>_<arch>`. stdout carries one
`BUILT:<absolute path>` line per binary and, for `all`, one
`SUMS:<absolute path>` line per sums file; progress and `go version` go to
stderr. Exit status:

- 0 built;
- 1 a build or checksum failure, or an unusable `VERSION` file (empty, or
  content outside `[A-Za-z0-9._+-]` — only the line ending is stripped, so
  `1 2` is refused, never joined into `12`);
- 2 usage: an option given with an empty value (`--version ''` is refused, never
  treated as "use the default"), a version outside `[A-Za-z0-9._+-]`, a commit
  outside `[A-Za-z0-9]`, a malformed target, `all` combined with another target,
  an unknown option.

The script never deletes anything in the output directory.

A developer build for the engine's dev slot passes its own identity, e.g.
`goengines/build.sh --version "<V>-dev+<sha>"`.

## Build identity

Every build uses:

```
CGO_ENABLED=0 go build -trimpath -buildvcs=false \
  -ldflags "-s -w -X main.version=<V> -X main.commit=<sha>"
```

- `main.version` / `main.commit` default to `devel` / `unknown` in an unstamped
  build, which matches no version the shim accepts. `TestLdflagsWiring` pins the
  variable names.
- The **engine contract is not an ldflag**. It is the source constant
  `testmap.Contract`: the contract-refusal logic depends on it, and an ldflag
  would let a build claim a compatibility it does not implement. `version` still
  prints it.
- `-trimpath -buildvcs=false` keep host paths and VCS stamps out of the binary;
  `CGO_ENABLED=0` makes every target a static cross-compile from one Linux
  runner.

## Release assets

`build.sh all` with the framework version `<V>` produces, per executable:

- `ait-testmap_<V>_linux_amd64`, `ait-testmap_<V>_linux_arm64`,
  `ait-testmap_<V>_darwin_amd64`, `ait-testmap_<V>_darwin_arm64`
- `ait-testmap_<V>_SHA256SUMS.txt` — exactly those four files, sorted, in
  `sha256sum` format (`<hex>  <basename>`)

Verify a download with `sha256sum -c ait-testmap_<V>_SHA256SUMS.txt` (or
`shasum -a 256 -c`) in the directory holding the files. `build.sh` hashes with
`sha256sum`, falling back to `shasum -a 256`.

## Release job wiring (`.github/workflows/release.yml`)

`plan → goengines → release → packaging`:

- **`goengines`** (`needs: plan`) — setup-go from `goengines/go.mod`, `go vet`,
  `go test`, `./build.sh all`, `sha256sum -c` over the result, and upload of
  `goengines/dist/` as the `goengines-dist` artifact (`if-no-files-found: error`).
- **`release`** (`needs: [plan, goengines]`) — downloads `goengines-dist` into
  `goengines/dist`, runs the unchanged VERSION-matches-tag guard, and attaches
  `goengines/dist/*` in **both** `softprops/action-gh-release` steps (with and
  without a changelog section) with `fail_on_unmatched_files: true`, so a
  release that lost its engine assets fails instead of publishing without them.
- **`packaging`** and `release-packaging.yml` are untouched; the nfpm package
  stays `arch: all`.

A failing `go test` or cross-build therefore blocks the release. The same checks
run on every push that touches `goengines/`, so a breakage surfaces before a tag.

## CI: `.github/workflows/goengines-check.yml`

Triggers on push and pull request touching any of `goengines/**`, the workflow
itself, `.github/workflows/release.yml` and the three guard tests below, and on
`workflow_dispatch`.

**`check`** (required):

1. gofmt (fails listing the unformatted files), `go vet ./...`, `go test ./...`.
2. `./build.sh all` into a scratch directory plus `sha256sum -c` — the release
   matrix, cross-compiled on every change.
3. The repository-side guards:
   - `tests/test_release_workflow_goengines.py` — the release wiring above
     (`needs`, the artifact hand-off, both release steps' `files`, the VERSION
     guard's position, `packaging`) and this workflow's own trigger paths and
     advisory split. It is why `release.yml` is among the trigger paths: an edit
     to it alone still runs the guard.
   - `tests/test_goengines_build.sh` — asset names, build identity, the matrix
     and its sums, usage refusals.
   - `tests/test_goengines_benchci.sh` — the bench helper below.

**`bench`** (`continue-on-error: true`, **advisory**): runs the benchmark gate,
`go run ./internal/tools/benchgate -baseline <baseline>` in full mode. The gate
is host-normalized but not yet proven portable across hosted runners; it becomes
a required check only when the promotion criteria in `goengines/README.md`
(*Host normalization*) are met. CI never records its own baseline — hosted
runners change machine per job — it judges against the committed, calibrated
`goengines/bench/baseline.txt`.

The `seed_regression` dispatch input benches against a seeded baseline instead:
every non-calibration line divided by 2.1, applied inside the job only
(`goengines/ci/benchci.sh seed`). A healthy runner must then fail every
benchmark — the seeded-regression sample the promotion criteria ask for.

Each bench run writes to its job summary: the mode, the CPU model, `nproc`, a
scaled-ratio table and the raw gate output.

### The scaled-ratio table (`goengines/ci/benchci.sh summary`)

The gate prints a ratio only on `BENCH_REGRESSION` lines; `BENCH_OK` carries
`<name>|<current>|<baseline>` and `BENCH_OVER_BUDGET` carries the budget, not the
baseline. The summary recomputes every benchmark's ratio exactly as the gate
does:

- `scale = <current cal> / <baseline cal>` from fields 3 and 4 of the class's
  `BENCH_SCALE:<class>|<rounded>|<current cal>|<baseline cal>` line. Field 2 is
  rounded to three decimals and is **not** used: near a threshold the rounding
  moves a ratio across it.
- `ratio = current / (baseline × scale)`, printed at six decimals. The baseline
  is read from the baseline file the gate used; the class from its `cal=` field
  (default `cpu`).

Columns: `benchmark | class | current ns/op | baseline ns/op | scale |
scaled ratio | verdict`, with the verdict from the gate's own line (`ok`,
`regression`, `over-budget`, `missing`, `new`; joined with `+` when a benchmark
has two). The ratio is `n/a` when the class has no trustworthy scale
(`BENCH_SCALE_IMPLAUSIBLE`, `BENCH_CALIBRATION_MISSING`, `BENCH_UNSCALED` — the
gate falls back to scale 1 there, which says nothing about the host), for a
`BENCH_MISSING` benchmark, and for a `BENCH_NEW` one (no baseline). The helper
never judges a ratio against a threshold and always exits 0 once its arguments
are well-formed, so the summary can never mask the gate's verdict.

## Engine internals

The engine half of this document — packages, verbs, the line protocol and
extension points — is written with the documentation module of the test map
work. Until then the interface shapes and the rules for engine submodules are in
`goengines/README.md`.
