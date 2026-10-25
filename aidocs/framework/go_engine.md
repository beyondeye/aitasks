# Go engines: build, CI and release

The framework's Go executables live in one module, `goengines/`
(`github.com/beyondeye/aitasks/goengines`), one executable per
`goengines/cmd/<name>/`. Today that is `ait-testmap`, the test map engine.
This document covers how they are built, checked and released. The module's
layout, the rules for engine submodules and every consumed interface shape are
in `goengines/README.md`.

**Two modes, one signal.** Whether `goengines/EXPORT.txt` exists decides how
the tree is validated. In **legacy mode** (no `EXPORT.txt`), the tree is
developed here and the test suite is the validation. In **export mode**, the
tree is a generated export from the private `aitasks_go` repository, whose
tests ran there, and the export integrity checks are the validation. Each
section below names the mode it applies to; *Export mode* has the details.
The policy, the record format and the emergency-fix protocol are in
`goengines/README.md` (*Source of truth*).

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

- **`goengines`** (`needs: plan`), in order:
  - setup-go from `goengines/go.mod`;
  - `Detect goengines mode` (`goengines_integrity.sh mode`, never skipped; a
    failed detection fails the job);
  - `go vet`;
  - the hang-guard preflight (`./ci/preflight.sh`, see the `check` job below)
    and `go test`, both with `if: steps.mode.outputs.mode != 'export'`, so
    they are skipped only on a positive export answer;
  - the export integrity `check` (required; it reports legacy and passes in
    legacy mode) and the `drift` report (`continue-on-error`);
  - `./build.sh all`, then `sha256sum -c` over **every** `*_SHA256SUMS.txt`
    (one per executable; none at all fails the step);
  - upload of `goengines/dist/` as the `goengines-dist` artifact
    (`if-no-files-found: error`).
- **`release`** (`needs: [plan, goengines]`) — downloads `goengines-dist` into
  `goengines/dist`, runs the unchanged VERSION-matches-tag guard, and attaches
  `goengines/dist/*` in **both** `softprops/action-gh-release` steps (with and
  without a changelog section) with `fail_on_unmatched_files: true`, so a
  release that lost its engine assets fails instead of publishing without them.
- **`packaging`** and `release-packaging.yml` are untouched; the nfpm package
  stays `arch: all`.

A failing `go test` (legacy), a failing integrity check (export) or a failing
cross-build therefore blocks the release. The same checks run on every push that
touches `goengines/`, so a breakage surfaces before a tag. `main` has no branch
protection, so "required" here means that the release depends on it. If
protection is ever added, mark `check` and `export-integrity` as required: a
skipped job counts as passing, and each mode skips one of them.

## CI: `.github/workflows/goengines-check.yml`

Triggers on `workflow_dispatch`, and on any push or pull request that touches
one of:

- `goengines/**`;
- the workflow itself, or `.github/workflows/release.yml`;
- the integrity script (`.github/scripts/**`);
- the t1954 research corpus
  (`aidocs/testing_engine/t1954_parser_research/corpus/**`);
- the five guard tests below.

**`mode`** runs `goengines_integrity.sh mode` and exposes the result as the job
output `mode`. **`check`** and **`bench`** carry `needs: mode` and
`if: ${{ !cancelled() && needs.mode.outputs.mode != 'export' }}`. They are
therefore skipped only on a positive export answer. If the mode job fails, its
output is empty and both run in full.

**`check`** (required, legacy mode):

1. gofmt (fails listing the unformatted files), `go vet ./...`, the hang-guard
   preflight `./ci/preflight.sh`, then `go test ./...`. The preflight runs the
   hang-guard tripwire (`internal/testsupport/hangguard`) alone, over every
   package its `tripwirePackages` list names: inside `go test ./...` it would run
   in package order, after tests that could already hang, so a process-starting
   test that omits the hang guard fails here in seconds and the suite never
   starts. It also fails a package that imports the guard without a list entry,
   and a non-test file that imports it at all; a new package opts in with one
   entry. `ait engine test` runs the same sequence in legacy mode (see *Export mode* for the other).
2. `./build.sh all` into a scratch directory, then `sha256sum -c` over every
   per-executable sums file. This cross-compiles the release matrix on every
   change.
3. The repository-side guards:
   - `tests/test_release_workflow_goengines.py` — the release wiring above
     (`needs`, the artifact hand-off, both release steps' `files`, the VERSION
     guard's position, `packaging`), this workflow's own trigger paths and
     advisory split, the two-mode gating (the exact fail-closed `if:`
     conditions, the mode step before the preflight, the integrity check that
     is never skippable and the drift report that never blocks, each with
     negative controls), the per-executable sums loop, and in both workflows
     the hang-guard preflight's position before `go test ./...`. It is why `release.yml` is among the trigger paths: an edit
     to it alone still runs the guard.
   - `tests/test_goengines_build.sh` — asset names, build identity, the matrix
     and one sums file per executable, for however many `cmd/*` programs the
     tree holds, plus a two-program fixture; usage refusals.
   - `tests/test_goengines_export_integrity.sh` — the integrity script over
     fixture trees: mode detection, legacy no-ops, acceptance of the
     provenance labels, every refusal (including violations that exist only on
     a non-host release platform) and drift reporting.
   - `tests/test_goengines_benchci.sh` — the bench helper below.
   - `tests/test_annot_conformance_corpus_sync.sh` — the `annot` conformance
     fixtures (`goengines/internal/testmap/annot/testdata/conformance/`) are
     exact copies of the bash, Python, Go and Kotlin fixtures of the research
     corpus: the same file lists, bytes and executable bits. The Go conformance
     test never reads `aidocs/`, so this step is what fails when a research
     fixture has not been copied; the refresh commands are in the header of
     `conformance_test.go`.

**`export-integrity`** (always runs, never advisory). It sets up Go, detects
the mode, runs `goengines_integrity.sh check` (the required export validation;
in legacy mode it reports legacy and passes) and `drift` (`continue-on-error`).
Then, only in export mode, it runs the guards over public files that outlive
the cutover: the release-workflow guard, `test_goengines_build.sh` and
`test_goengines_export_integrity.sh`. In legacy mode the `check` job runs
these.

**`bench`** (`continue-on-error: true`, **advisory**, legacy mode): runs the benchmark gate,
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

## Export mode

Export mode starts when `goengines/EXPORT.txt` exists. The aitasks_go exporter
writes that file, and the bootstrap export (the testmap cutover) creates it in
the same commit that replaces the source. The format is defined in
`goengines/README.md` (*`EXPORT.txt` (format 1)*). In this mode the tree holds
no tests, `testdata/`, `bench/` or `ci/`.

`.github/scripts/goengines_integrity.sh <mode|check|drift> [--dir <goengines>]`
holds the checks. It lives outside `goengines/`, because that tree may hold
only exported files plus `README.md` and `.gitignore`. Its header pins its
output shapes. `check` runs every Go command in a scratch copy, so the
checkout is never modified. Every Go command also runs under one isolated
environment, which keeps any inherited `GOWORK`, `GOFLAGS`
(`-modfile=…`) or proxy setting from steering one check and not another:

- `GOENV=off`, because go treats an empty variable as unset and would fall
  back to the user's `go env -w` file;
- `GOFLAGS=` cleared before any per-call value;
- `GOWORK=off`;
- no `GOPRIVATE` / `GONOPROXY` / `GONOSUMDB`;
- the public proxy only.

The checks, in order:

1. **`record`** — `EXPORT.txt` is a valid format-1 record.
2. **`matrix`** — the release targets are read from `build.sh`'s
   `readonly MATRIX=(…)` line. The checks below run per target with the
   release build settings (`CGO_ENABLED=0`, `GOOS` / `GOARCH`, no tags),
   because `go list` and `go build` see only one platform's files: a
   `_darwin.go` file is invisible to a check run on Linux.
3. **`gofmt`**.
4. **`private-deps`** — no `github.com/beyondeye/aitasks_go` module in any of:
   - a `go.mod` `require` or `replace`;
   - `go.sum`;
   - `go list -m all`;
   - any package's import list, on each target.

   A local `replace` must stay inside the tree. That rule is lexical and
   conservative: no absolute path and no `..` segment. Every check is
   structural, so the provenance labels pass: the generated header,
   `EXPORT.txt`, the commit trailers and `SourceCommit`. When anything up to
   this point has failed, `check` stops, because the remaining checks reach
   the module proxy.
5. **`independent-build`** — runs under `GOWORK=off GOFLAGS=-mod=mod
   GOPRIVATE= GONOPROXY= GONOSUMDB= GOPROXY=https://proxy.golang.org`.
   `go mod tidy -diff` must be clean, `go build ./...` must pass on each
   target, and `go vet ./...` must pass.
6. **`closure`** — on each target, the non-std closure of `cmd/ait-testmap`
   (required), and of `cmd/ait-monitord` when present, stays inside the main
   module and the allowlist (`gopkg.in/yaml.v3`, `bmatcuk/doublestar/v4`,
   `golang.org/x/sync`). It also contains no main-module `tui/` package.
   While `guards_test.go` exists, the allowlist is pinned equal to its
   `allowedDeps`.

`drift` hashes every `file:` entry, and reports modified, missing and
unlisted files (`README.md`, `.gitignore` and gitignored files excepted). It
always exits 0, and under Actions it emits `::warning` annotations. A drifted
file is an emergency public fix that has not yet been returned to aitasks_go.
The protocol is in `goengines/README.md` (*Emergency fixes*).

`ait engine test` follows the same signal. In export mode it runs `check` and
then `drift` in place of vet, the preflight and the suite, and it warns that
any go-test arguments are ignored.

## Engine internals

The engine half of this document — packages, verbs, the line protocol and
extension points — is written with the documentation module of the test map
work. Until then the interface shapes and the rules for engine submodules are in
`goengines/README.md`.
