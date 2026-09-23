---
Task: t1852_2_m1_2_engine_skeleton.md
Parent Task: aitasks/t1852_testmap_m1_engine_foundation_and_distribution.md
Sibling Tasks: aitasks/t1852/t1852_1_*.md, aitasks/t1852/t1852_3_*.md, aitasks/t1852/t1852_4_*.md, aitasks/t1852/t1852_5_*.md, aitasks/t1852/t1852_6_*.md
Archived Sibling Plans: aiplans/archived/p1852/p1852_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-09-23 17:24
---

# Plan: t1852_2 — M1.2 Engine skeleton

## Context

Parent goal: M1 — Engine foundation and distribution (`ait-testmap` as a
buildable, installable, resolvable binary). This is **M1.2 Engine skeleton**,
wave **A**, no providers: the root Go module that every engine submodule of
M2–M8 adds a package to, the shared `lineproto` / `platform` / `gitx`
packages, the stub verb table, and the fixture and bench harnesses every
engine test uses. Nothing project-specific ships yet.

Authoritative spec: `aidocs/testing_engine/n014_explorer_006_proposal.md` —
Module Map `#### M1` row M1.2 (line 680), *Go engine and CLI (M1.2)* incl.
*Path convention* (1927–1962), *Engine binary identity and budget (M1.2)*
(1964–1989), *Invariants* 4–5 (104–140), *Process map* (286–340),
*Line-protocol index* (436–456), *Run Surface → Output and exit contract*
(1640–1667), *Assumptions → M1* (3165–3222), *Tradeoffs → M1* (3633–3669).
Parent plan: `aiplans/p1852_testmap_m1_engine_foundation_and_distribution.md`
(Deviations 3 and 6).

## Owned files / provides / consumes

- **Owns:** `goengines/**` except the later packages. Every file below is new
  and inside `goengines/`; no existing file is touched.
- **Provides:** module `github.com/beyondeye/aitasks/goengines`; the binary
  `cmd/ait-testmap` with its verb table; `internal/{lineproto,platform,gitx}`;
  `internal/testmap` (package root: engine contract + `CONTRACT_MISMATCH`);
  `internal/testmap/fixture` (synthetic `(t<id>)` histories);
  `internal/benchgate` + `internal/tools/benchgate` (2× rule, committed baselines).
- **Consumes:** nothing.
- **Named extensions into this child's files:** each later engine submodule
  replaces exactly one row of the verb table (`cmd/ait-testmap/verbs.go`),
  adds its package under `internal/testmap/<pkg>`, adds its fixtures through
  the `fixture` API, and adds its benches + baseline lines to
  `goengines/bench/baseline.txt`.

## Step 0 — Reality check (executed 2026-09-23, main @ a9b93ff98)

| # | item | proposal says | coarse plan says | repository has | decision |
|---|---|---|---|---|---|
| 1 | `goengines/` | new | new | **absent**; only Go file is `website/go.mod` (Hugo) | build as specified |
| 2 | Go toolchain | Go 1.26, pinned toolchain | ≥1.26, decide here | host go1.27.0 (mise, `GOTOOLCHAIN=auto`); current stable **go1.27.1** (go.dev, 2026-08-28) | `go 1.26.0` (minimum; also what `x/sync v0.23.0` requires) + `toolchain go1.27.1`. Host auto-fetches 1.27.1 once via `GOTOOLCHAIN=auto`; M1.3's `setup-go` reads `go-version-file` |
| 3 | deps | yaml.v3, doublestar/v4, x/sync **only** | same | latest: yaml.v3 v3.0.1, doublestar v4.10.2, x/sync v0.23.0 | read "only" as an **allowlist**, not a mandatory set: `go mod tidy` drops unimported requires. M1.2 imports **yaml.v3** (contract reader) and **x/sync** (`errgroup` pool, cap 8); **doublestar arrives with its first importer** (M2.1 `exclude:` globs). A test pins go.mod requires ⊆ allowlist |
| 4 | contract embedding | `-X version/commit/contract` | same | — | **version, commit via `-X main.version` / `-X main.commit`**; the contract is the **source constant** `testmap.Contract = 1`. The refusal logic depends on it, and an ldflag would let a build claim a compatibility it does not implement. `version` still prints it (it is embedded, just not overridable). Note to t1852_3 |
| 5 | `version --json` "prints `ENGINE:<path>`" | literal | same | — | JSON cannot contain the bare line `ENGINE:`. Decision: text `version` is line protocol `VERSION:` / `COMMIT:` / `CONTRACT:` / `ENGINE:<abs path>`; `version --json` is one object `{"version","commit","contract","engine"}`. `ENGINE:` stays a line class of the text form (as the Line-protocol index lists it). Notes to t1852_4, t1852_5 (their greps: `^VERSION:` in text, `"version":"<V>"` in JSON) |
| 6 | stub exit | every non-`version` verb exits 64 | same | — | stub prints `NOT_IMPLEMENTED:<verb>` on stderr, exit 64; unknown verb/sub-verb `UNKNOWN_VERB:<verb>` stderr, exit 64; no verb → usage on stderr, exit 64 |
| 7 | default build identity | — | — | — | unset ldflags → `version=devel`, `commit=unknown`: matches neither shim tier (`== VERSION`, `<V>-dev+<sha>`), so a bare `go build` binary fails the handshake closed |
| 8 | fixture harness location | "`testmap/internal/fixtures` or equivalent" | same | — | `goengines/internal/testmap/fixture` (a normal package so every testmap package's tests import it; already unreachable outside the module) |
| 9 | bench tool | 2× rule, `goengines-check.yml` runs it | same | — | library `internal/benchgate` + runner `internal/tools/benchgate` (package main **under internal/**, so M1.3's `build.sh` loop over `cmd/*` never ships it); `go run ./internal/tools/benchgate` |
| 9b | bench gate completeness | 2× rule against committed baselines | same | — | full mode fails on a missing baseline bench and on an empty set; the tool runs `go test` itself so a producer failure cannot be masked by a pipe; `-partial` is the explicitly separate developer mode |
| 9c | dependency cache root | `${XDG_CACHE_HOME:-~/.cache}/aitasks/testmap/` (lines 428, 2170) | — | Go's `os.UserCacheDir` = `~/Library/Caches` on Darwin, ignores XDG there | `platform.CacheRoot()` implements the proposal's expression on every OS; `testmap.CacheDir()` appends `testmap` |
| 10 | pool cap 8 | engine-wide | "constant in lineproto" | — | lives in `internal/platform` (host resources), not lineproto: `PoolCap = 8`, `Workers(n)`, `NewGroup(ctx, n)` |
| 11 | build output ignore | — | check `.gitignore` | root `.gitignore` has no Go rules | `goengines/.gitignore` with `/ait-testmap` (owned file; root `.gitignore` untouched) |
| 12 | tarball | excluded | same | `release.yml:87-90` tars an explicit path list, no `goengines/` | nothing to do |
| 13 | M2/M3 first children | consume the harnesses | — | t1853–t1861 have **no children yet** | notes go to the parents t1853 and t1854 (their coarse pass reads them) |

**Ownership re-confirmed:** every file is new under `goengines/`.

**Notes owed (post-approval, hedged: code uncommitted at note time):**
- t1852_3 — rows 2, 4, 9: ldflags are `-X main.version=<V> -X main.commit=<sha>`
  for every `cmd/*` (no contract flag); bench gate command
  `go run ./internal/tools/benchgate -baseline bench/baseline.txt` (runs the
  producer itself — no pipe; full mode is the gate, `-partial` never is);
  baselines are dev-host numbers — CI normalization is the spawned
  `bench_host_normalization` task.
- t1852_4 — rows 5, 6, 7: exact `version` text / JSON shape; stub vs unknown-verb stderr lines; `devel` default.
- t1852_5 — rows 5, 7: the self-check reads `"version":"<V>"` from `--json` (or `^VERSION:<V>$` from text); `ait engine build` must pass `-X main.version=<V>-dev+<sha>`.
- t1853, t1854 — the harness APIs (fixture, benchgate baseline format, verb-table row replacement, `testmap.CheckContract`).

## Implementation steps

1. **Module.** `goengines/go.mod`: `module github.com/beyondeye/aitasks/goengines`,
   `go 1.26.0`, `toolchain go1.27.1`; `go get gopkg.in/yaml.v3@v3.0.1 golang.org/x/sync@v0.23.0`,
   `go mod tidy` → `go.sum`. `goengines/.gitignore`: `/ait-testmap`.
   A short `goengines/README.md` (layout, how to
   build/test/bench, the verb-table extension rule, Invariant 5).

2. **`internal/lineproto`** (`lineproto.go`, `exit.go`, tests):
   - `Writer{out io.Writer, JSON bool}`; `Line(class string, fields ...string) error`
     prints `CLASS:f1|f2|…`; a field containing `|`, `\n` or `\r` returns
     `ErrUnsafeField` (never silently corrupts a bash `IFS='|'` parse);
     `Emit(v any) error` writes one JSON document (`encoding/json`, trailing newline).
   - Exit codes from the Run Surface table: `ExitOK 0`, `ExitFail 1`,
     `ExitNothingRan 2`, `ExitFramework 3`, `ExitUsage 64`, `ExitRefused 75`.
   - `ExitContract []int` + `Allows(code)`; `Enforce(verb string, c ExitContract, code int, stderr) int`
     — a code outside the verb's declared set prints
     `EXIT_CONTRACT_VIOLATION:<verb>|<code>` on stderr and returns 3 (fail closed).
   - `Usage(stderr, msg) int` → prints `USAGE:<msg>`, returns 64.

3. **`internal/platform`** (`platform.go`, `lock_unix.go`, tests):
   `OS()`/`Arch()`/`AssetSuffix()` (`<os>_<arch>`, matching the release asset
   `ait-testmap_<V>_<os>_<arch>`); `PoolCap = 8`, `Workers(requested int) int`
   (≤0 → `runtime.NumCPU()`, clamped to [1, 8]), `NewGroup(ctx, n)` → `errgroup`
   with `SetLimit(Workers(n))`; `Lock(path) (unlock func() error, err)` via
   `syscall.Flock(LOCK_EX)` (unix build tag — matrix is linux/darwin);
   `CacheRoot() (string, error)` = `${XDG_CACHE_HOME:-$HOME/.cache}/aitasks` on
   **every** OS — deliberately **not** `os.UserCacheDir()`, which uses
   `~/Library/Caches` and ignores `XDG_CACHE_HOME` on Darwin and would not
   match the proposal's pinned location (lines 428, 2170:
   `${XDG_CACHE_HOME:-~/.cache}/aitasks/testmap/deps/<blob-sha1>.json`). Per the
   XDG spec a relative `XDG_CACHE_HOME` is ignored; empty `HOME` with no XDG →
   error (never a cwd-relative cache). Implemented as a pure
   `cacheRoot(getenv func(string) string)` behind the exported wrapper.
   `testmap.CacheDir()` (step 5) = `CacheRoot()/testmap` — the root M2.3 appends
   `deps/<blob>.json` to.
   Tests: clamp table, errgroup never exceeds 8 concurrent (atomic high-water
   with 50 goroutines), lock excludes a second locker (second `Flock` with
   `LOCK_NB` gets `EWOULDBLOCK`); cache-root table run for both a linux and a
   darwin label (the function has no OS branch, and the test asserts that):
   absolute `XDG_CACHE_HOME` wins, relative/empty XDG → `$HOME/.cache/aitasks`,
   no XDG + no HOME → error; `testmap.CacheDir()` ends in `/aitasks/testmap`.

4. **`internal/gitx`** (`gitx.go`, `blob.go`, `lstree.go`, tests using the fixture):
   - `Repo{Dir string}`; `Run(ctx, args...) ([]byte, error)` — `exec.CommandContext("git", "-C", dir, …)`,
     scrubbed env (drop `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`,
     `GIT_OBJECT_DIRECTORY`, `GIT_CEILING_DIRECTORIES`…; set `LC_ALL=C`,
     `GIT_TERMINAL_PROMPT=0`); errors carry stderr + exit code.
   - `ObjectFormat(ctx)` (`rev-parse --show-object-format`, default sha1);
     `BlobDigest(data []byte, format string) string` — pure Go `"blob <n>\0"+data`
     under sha1/sha256 (no exec on the hot path).
   - `IsAncestor(ctx, a, b) (bool, error)` — `merge-base --is-ancestor`: exit 0
     true, 1 false, anything else error.
   - `LsTree(ctx, rev string, paths ...string) ([]TreeEntry, error)` —
     `ls-tree -r -z --full-tree`, parsed `<mode> <type> <oid>\t<path>\0`;
     `TreeEntry{Mode, Type, OID, Path}`.
   - `RevParse(ctx, rev)`. **No write verbs** (Invariant 5: the engine never commits).
   Tests: `BlobDigest` equals `git hash-object` for text, empty, binary data,
   and on a `--object-format=sha256` fixture; `IsAncestor` true/false/bad-rev
   error; `LsTree` with a path containing spaces and a nested dir; env scrub
   (`GIT_DIR=/nonexistent` in the test env does not leak).

5. **`internal/testmap`** (package root — `contract.go`, test):
   `const Contract = 1`; `ReadContract(data []byte) (int, bool, error)` (yaml.v3,
   top-level `contract:` only; absent → `false`); `CheckContract(path string, data []byte) error`
   → `*ContractMismatchError{Path, File, Engine}` when the file's contract >
   `Contract`, whose `Line()` is `CONTRACT_MISMATCH:<path>|<file>|<engine>` and
   whose exit is 3 (Run Surface table). Older or absent contract passes (fields
   are additive). Also `CacheDir() (string, error)` = `platform.CacheRoot()/testmap`. Tests: newer refused, equal / older / absent pass, malformed
   YAML error, non-integer `contract:` error.

6. **`internal/testmap/fixture`** (`fixture.go`, test):
   ```go
   r := fixture.New(t)                       // git init -b main in t.TempDir(); fixed identity
   r.Write(t, "src/a.go", "…")                // mkdir -p + write
   sha := r.Commit(t, "12", "feature", "add a") // "feature: add a (t12)", git add -A
   r.History(t, []fixture.Commit{{Task: "12_3", Type: "bug", Desc: "…", Files: map[string]string{…}}})
   r.Git(t, args...)                          // escape hatch, via gitx
   ```
   Deterministic: `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE` start at a fixed epoch and
   advance 60 s per commit, so SHAs are reproducible run to run; `New(t, fixture.SHA256())`
   option for the object-format case; `commit.gpgsign=false` and hooks off in the
   repo config. Tests: message grammar `<type>: <desc> (t<id>)` incl. child ids,
   two runs produce identical HEAD SHAs, `Files` with deletion (`""` value → `git rm`).

7. **`internal/benchgate`** + **`internal/tools/benchgate/main.go`**:
   - `ParseBench(r io.Reader) (map[string]float64, error)` — `go test -bench` lines
     `BenchmarkX-8  N  123 ns/op …`; the `-<procs>` suffix is stripped and each name
     is keyed by the preceding `pkg:` header → `<pkg>.<Bench>` (two packages may
     share a bench name).
   - Baseline file `goengines/bench/baseline.txt`: `<pkg>.<Bench> <ns/op> [budget=<duration>]`,
     `#` comments.
   - `Compare(cur, base, mode, factor=2)` → per bench: `BENCH_OK`,
     `BENCH_REGRESSION:<name>|<cur>|<base>|<ratio>` (cur > 2 × base),
     `BENCH_OVER_BUDGET:<name>|<cur>|<budget>` (absolute budget — the proposal's
     latency table lands here as later benches arrive), `BENCH_NEW:<name>`
     (measured, no baseline: reported, not failed — the author adds it with `-update`),
     `BENCH_MISSING:<name>` (baseline line with no measurement).
   - **Two modes, printed as the first line so they cannot be confused:**
     `BENCH_MODE:full` (default — **the gate**): any `BENCH_MISSING` **fails**, so
     deleting or renaming a benchmark cannot silently drop its baseline; the
     baseline line must be removed in the same change. `BENCH_MODE:partial`
     (`-partial`, for a developer running one package or `-bench` pattern):
     missing baselines are listed but do not fail; regressions and budgets still do.
     `-partial` is never the gate (M1.3 note).
   - **Empty measurement set fails in both modes** (`BENCH_EMPTY`, exit 1): a run
     that measured nothing proved nothing.
   - **The tool runs the producer itself — no pipe.** `benchgate -baseline F
     [-partial] [-update] [-- <producer argv>]`; default producer
     `go test -run ^$ -bench . -count 1 ./...` run in the module dir. Its stdout is
     parsed; a nonzero producer exit prints `BENCH_PRODUCER_FAILED:<code>` and the
     tool exits 1 whatever the parsed numbers say (there is no `| checker` for a
     missing `pipefail` to mask). `-update` refuses to write when the producer
     failed, the set is empty, or the mode is partial (a partial run would drop
     baselines), and preserves budgets and comments otherwise.
   - Exit: 0 pass, 1 regression / over-budget / missing (full) / empty / producer
     failure, 64 usage.
   - Tests: parser on captured output (procs suffix, multiple packages, `-benchmem`
     columns); 1.9× passes, 2.1× fails; budget. **Through the shipped command
     interface** (`run(args, stdout, stderr)` of the tool's `main` package, with a
     fake producer passed after `--` as `sh -c 'printf …; exit N'`): full mode +
     one baseline bench not measured → exit 1 `BENCH_MISSING`; same input with
     `-partial` → exit 0, first line `BENCH_MODE:partial`; producer prints nothing
     → exit 1 `BENCH_EMPTY` (both modes); producer prints a clean passing set but
     exits 2 → exit 1 `BENCH_PRODUCER_FAILED:2`; `-update` after a failed producer
     leaves the baseline file byte-identical; `-update -partial` refused (64). One
     test builds the tool binary (skipped under `-short`) and runs the missing-bench
     case to cover `main` wiring; **the slowed-fixture acceptance**:
     `testing.Benchmark` over a `time.Sleep(1ms)` fixture sets the baseline, the
     same fixture re-measured passes, a `Sleep(3ms)` "slowed" fixture fails the 2× rule
     (sleep-based, so ratio ≈3 and robust against machine noise).
   - Benches shipped now (baseline lines committed from this host): `gitx`
     `BenchmarkBlobDigest` (64 KiB), `BenchmarkLsTree` (fixture of 200 files),
     `cmd/ait-testmap` `BenchmarkDispatchVersion`.

8. **`cmd/ait-testmap`** (`main.go`, `verbs.go`, `version.go`, tests):
   - `var version = "devel"`, `var commit = "unknown"` (ldflags `-X main.version`, `-X main.commit`).
   - `main()` → `os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))`; `run` is the tested
     entry point.
   - `verbs.go`: one table, `[]verb{Name, Run, Exits lineproto.ExitContract, Sub []verb}`;
     `version` live, every other verb `stub` (exit set `{64}`): `test select schedule run
     scan check stale annotate verify explain axes areas classify costs score attribute
     readiness brief runner` and `onboard` with sub-verbs `detect inventory seed review
     classify adopt reject scaffold status finish`. `runner <name>` takes any name.
     Each verb parses its own flags with stdlib `flag.NewFlagSet(name, ContinueOnError)`;
     a flag error → 64. Dispatcher routes through `lineproto.Enforce`.
   - `version [--json]`: line protocol `VERSION:` `COMMIT:` `CONTRACT:` `ENGINE:<path>`
     (`os.Executable` + `filepath.EvalSymlinks`), or the JSON object.
   - Tests: every table verb (and every onboard sub-verb, and `runner foo`) exits 64
     with `NOT_IMPLEMENTED:`; unknown verb / `onboard bogus` / no args → 64; the table
     equals the proposal's verb list exactly (guards additions/removals); `version` text
     and JSON shapes; a `go build -ldflags "-X main.version=9.9.9 -X main.commit=abc"`
     test (skipped under `-short`) execs the binary and checks both values — pins the
     ldflag variable names M1.3 relies on.

9. **Guards** (`goengines/guards_test.go`, package-level test in module root, `package goengines_test`):
   - go.mod requires ⊆ {yaml.v3, doublestar/v4, x/sync} (direct and indirect).
   - Invariant 5 lexical guard over non-`_test.go` sources outside `fixture`:
     no `"commit"` / `"push"` / `"add"` git argument literals, no `aitask_` + `.sh`
     string, no `claude` / `codex` / `opencode` exec, no literal `aitasks/` /
     `aiplans/` / `.aitask-data` / `CLAUDE.md` / `gates.yaml` / `project_config.yaml`
     paths. With a **negative control**: the matcher is run on an in-test snippet
     containing each forbidden form and must flag every one (a guard that matches
     nothing proves nothing). Heuristic by nature — documented as a tripwire, the
     invariant itself is enforced by review.

10. **Green**: `cd goengines && test -z "$(gofmt -l .)" && go vet ./... && go test ./... && go run ./internal/tools/benchgate -baseline bench/baseline.txt`.

### Post-phase (risk mitigations)

1. [interface_contract_readme] Add an `## Interfaces` section to
   `goengines/README.md`: one row per shape a downstream task consumes —
   `version` text lines and `--json` keys, the `-X main.version` /
   `-X main.commit` names and the `devel`/`unknown` defaults, the stub
   (`NOT_IMPLEMENTED:`) / unknown-verb (`UNKNOWN_VERB:`) / usage (`USAGE:`)
   stderr lines and their exit 64, the exit-code table, the verb-table row
   shape and the "replace one row" rule, the `fixture` API, the
   `bench/baseline.txt` format and benchgate output lines, and
   `CONTRACT_MISMATCH:<path>|<file>|<engine>`, the benchgate modes/lines/exit
   codes, and the cache root `${XDG_CACHE_HOME:-$HOME/.cache}/aitasks/testmap` — each naming the test that
   pins it (`TestVersionText`, `TestStubsExit64`, `TestLdflagsWiring`, …).
   Verify: every test named in the table exists (`grep -c` per name in
   `goengines/**/*_test.go` ≥ 1). The downstream notes cite this section.

## Verification

- `cd goengines && gofmt -l .` prints nothing; `go vet ./...` and `go test ./...` green.
- `go build -o /tmp/ait-testmap ./cmd/ait-testmap && /tmp/ait-testmap version` →
  `VERSION:devel` / `COMMIT:unknown` / `CONTRACT:1` / `ENGINE:/tmp/ait-testmap`;
  `version --json` → the JSON object; with `-ldflags "-X main.version=0.35.1 -X main.commit=$(git rev-parse --short HEAD)"`
  the values change.
- `/tmp/ait-testmap select; echo $?` → `NOT_IMPLEMENTED:select`, 64; `/tmp/ait-testmap bogus` → 64.
- `go run ./internal/tools/benchgate -baseline bench/baseline.txt` → first line `BENCH_MODE:full`, exit 0; the benchgate tests cover slowed fixture (2× fail), missing baseline bench, empty set and producer failure through the tool's command interface.
- `CacheRoot` tests pass for the explicit-XDG and HOME-fallback cases.
- `git status` shows only `goengines/**` added.

## Step 9 reference

Archival and cleanup follow the shared `task-workflow` Step 9. Current-branch
profile: no worktree, no merge. Commit: `feature: Add the goengines Go module and the ait-testmap engine skeleton (t1852_2)`.

## Risk

### Code-health risk: low
- Lexical Invariant-5 guard can false-positive on a legitimate later string (e.g. a runner named `add`) and push a later submodule to weaken it · severity: low · → mitigation: none (tripwire documented as heuristic; negative control keeps it honest)
- `toolchain go1.27.1` makes every Go invocation on a host with only 1.27.0 auto-fetch the toolchain once (network) · severity: low · → mitigation: none (one-time, standard Go behaviour)

### Goal-achievement risk: medium
- The interface decisions made here (version text/JSON shape, contract as a source constant, `-X main.*` names, stub/unknown stderr lines, verb-table row shape, fixture and baseline formats) are consumed by t1852_3/4/5 and the M2–M8 children; a shape they cannot use forces rework across siblings · severity: low (residual — addressed by inline post-phase interface_contract_readme and the downstream notes) · → mitigation: inline post-phase interface_contract_readme
- Bench baselines are recorded on this dev host; M1.3 wires the 2× rule into CI, where a different machine can fail (or mask) the ratio · severity: medium · → mitigation: bench_host_normalization

### Planned mitigations
- timing: post-phase | name: interface_contract_readme | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: interface decisions consumed by t1852_3/4/5 and M2–M8 | desc: README Interfaces section listing every consumed shape with the test that pins it
- timing: after | name: bench_host_normalization | type: enhancement | priority: medium | effort: medium | inline_risk: low | added_complexity: medium | addresses: bench baselines recorded on the dev host vs CI | desc: benchgate calibration benchmark normalizing baseline ratios across hosts before the 2x rule
