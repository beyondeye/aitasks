# goengines — the framework's Go executables

One Go module (`github.com/beyondeye/aitasks/goengines`) for every Go
executable the framework distributes. Framework repository only: the release
tarball does not include it; users receive prebuilt binaries.

Specification: `aidocs/testing_engine/n014_explorer_006_proposal.md`
(*Go engine and CLI (M1.2)*, *Engine binary identity and budget (M1.2)*).

## Layout

| path | what |
|---|---|
| `cmd/<name>/` | one executable each; the release build ships every `cmd/*` |
| `cmd/ait-testmap/` | the test map engine: the verb table (`verbs.go`) and `version` |
| `internal/lineproto` | line-protocol stdout, `--json`, exit codes, per-verb exit contracts (shared) |
| `internal/platform` | asset suffix, pool cap 8, `flock`, the per-user cache root (shared) |
| `internal/gitx` | read-only git: exec with a scrubbed env, blob digests, `merge-base --is-ancestor`, `ls-tree` (shared) |
| `internal/testmap/` | testmap root: registry contract, `CONTRACT_MISMATCH`, cache dir; every testmap package goes under `internal/testmap/<pkg>` |
| `internal/testmap/fixture` | the fixture harness: git repositories in `t.TempDir()` with synthetic `(t<id>)` histories |
| `internal/benchgate`, `internal/tools/benchgate` | the 2× benchmark gate (a tool under `internal/`, so it is never shipped) |
| `bench/baseline.txt` | committed benchmark baselines |

## Build, test, bench

```bash
cd goengines
test -z "$(gofmt -l .)" && go vet ./... && go test ./...      # -short skips the build-a-binary tests
go run ./internal/tools/benchgate -baseline bench/baseline.txt  # the gate (full mode)
go run ./internal/tools/benchgate -baseline bench/baseline.txt -partial -- \
    go test -run '^$' -bench BlobDigest ./internal/gitx          # a developer subset, never the gate
go build -ldflags "-X main.version=<V> -X main.commit=<sha>" -o ait-testmap ./cmd/ait-testmap
```

`go.mod` pins `go 1.26.0` and `toolchain go1.27.1`; with `GOTOOLCHAIN=auto` an
older local Go fetches the pinned toolchain once.

### Host normalization

Baselines are one host's numbers, so the gate normalizes for host speed
instead of comparing raw ns/op, per kind of work. Each baseline line belongs to
a calibration class, and each class has a fixed-work calibration benchmark
recorded in the baseline like any other line:

| class | calibration | for |
|---|---|---|
| `cpu` (default) | `internal/benchgate.BenchmarkCalibrate` — CPU-bound, allocation-free, no I/O | in-process work |
| `spawn` (`cal=spawn`) | `internal/benchgate.BenchmarkCalibrateSpawn` — one `git --version` fork/exec | benchmarks dominated by starting git (`BenchmarkLsTree`) |
| `sha1` (`cal=sha1`) | `internal/benchgate.BenchmarkCalibrateHash` — SHA-1 over a fixed 64 KiB buffer | benchmarks dominated by SHA-1 hashing (`BenchmarkBlobDigest`) |

Every baseline is scaled by `current / recorded` calibration of its class, and
the scaled ratio fails above `benchgate.Threshold` (1.6) — below the 2× rule
(`Factor`) it enforces, because normalization is approximate (measurements
below). `budget=` values (absolute latency targets) are never scaled. The full
gate fails when a class in use lacks its calibration on either side, or when a
scale is outside 0.25–4 (the calibration itself is then suspect). A new
benchmark declares the class of its dominant cost: process start-up,
hardware-accelerated hashing and general CPU work do not change speed together
from one CPU to the next (SHA-1 relative to the `cpu` calibration differs
~1.9× between this host's P- and E-cores).

Recording and checking must run under comparable conditions. The default
producer runs packages serially (`go test -p 1`), so a calibration never
overlaps the benchmarks it scales; at a fixed `GOMAXPROCS` (`-cpu 1`), whatever
the host's core count; and three times (`-count 3`), keeping each benchmark's
fastest run — a single sample on a loaded host skews a baseline or a scale
enough to hide a 2× regression. A custom producer for the gate or for
`-update` must keep all three. On a hybrid P/E-core host, pin both the
recording and a local check to one core type (`taskset -c <P-cores>`):
unpinned, the scheduler can measure a calibration on one core type and a
benchmark on the other.

Why not let CI record its own baseline: hosted runners change machine from job
to job, so a CI-recorded baseline has the same portability problem, and it
would have to be committed from CI. One committed, calibrated file serves
developer hosts and CI alike.

**Measured basis for the threshold — one host, not a portability proof.** The
baseline was recorded pinned to one P-core of an Intel Core Ultra 9 275HX
(hybrid P/E). The gate was then run under six conditions standing in for other
hosts — one P-core, four P-cores, one E-core, four E-cores, a P-core at a 33%
CPU quota and an E-core at a 50% quota (raw slowdowns up to ~3.7×) — three
healthy runs each, plus one run per condition with every baseline divided by
2.1 (a seeded just-over-2× regression). Scaled ratios:

| benchmark (class) | healthy (18 runs) | seeded 2.1× (6 runs) |
|---|---|---|
| `DispatchVersion` (cpu) | 0.86–1.17 | 1.94–2.36 |
| `BlobDigest` (sha1) | 0.77–1.06 | 1.98–2.17 |
| `LsTree` (spawn) | 0.82–0.96 | 1.72–2.12 |

Judged at 2.0, 6 of the 18 seeded regressions passed (`LsTree` 4 of 6); 1.6
separates every sample, 0.43 above the highest healthy ratio but only 0.12
below the lowest regression. One healthy run at the 33% quota failed closed on
a `cpu` scale of 4.18 (over the 4.0 bound). Before the classes existed, `cpu`
scaling alone put `BlobDigest` at 0.56–0.59 on E-cores and `LsTree` at
0.72–0.83 on a slowed core, which would have hidden a 2.1× regression of
either. Residual bias of up to ±15% per benchmark remains (`LsTree` runs
consistently low).

**The gate is not yet portable. CI rollout rule:** the CI bench step starts
advisory (`continue-on-error`, not a required check) and becomes required only
after it has been validated on the hosted runners: ≥5 healthy and ≥2
seeded-regression samples (every baseline divided by 2.1), each a separate
fresh workflow run (a fresh runner VM, spread over ≥2 days), each recording the
CPU model, `nproc`, every `BENCH_SCALE:` line and every scaled ratio. Promote
only if, for every benchmark, every healthy run passes with a scaled ratio ≤
1.3 and plausible scales, and every seeded regression fails (scaled > 1.6);
otherwise it stays advisory and the cause (a mis-classed benchmark, a missing
calibration class, a threshold that does not separate) becomes a task. If all samples ran on one CPU
model, say so here, and demote the step to advisory on the first unexplained
bench failure on a new CPU model.

## Rules for engine submodules

- **Replace your own stub row only.** Every verb is registered in
  `cmd/ait-testmap/verbs.go`; a submodule swaps `stub("<verb>")` for
  `{Name, Run, Exits}` and touches no other row. `Exits` is the verb's exit
  contract: a code outside it becomes exit 3 with `EXIT_CONTRACT_VIOLATION:`.
- **Packages go under `internal/testmap/<pkg>`**; `gitx`, `platform` and
  `lineproto` stay shared across executables.
- **Dependencies:** only `gopkg.in/yaml.v3`, `github.com/bmatcuk/doublestar/v4`,
  `golang.org/x/sync`, each added by its first importer (`guards_test.go`).
- **Invariants 4–5:** the engine never writes `aitasks/`, `aiplans/`,
  `.aitask-data/`, a gate ledger, `project_config.yaml`, `gates.yaml`, a
  profile or `CLAUDE.md`, never invokes an `aitask_*.sh` script, never
  commits and never launches a code agent. `guards_test.go` is a lexical
  tripwire for it; a legitimate look-alike literal is exempted on its own
  line with `// invariant5-ok: <reason>` — there is no file allowlist.
- **Benchmarks:** add one per budget, then record it with `-update`. Deleting or
  renaming a benchmark means editing its baseline line in the same change,
  because the full gate fails on `BENCH_MISSING`. Never change a
  calibration benchmark's work without re-recording the whole baseline.

## Interfaces

Shapes other tasks consume, each pinned by the named test.

| interface | shape | pinned by |
|---|---|---|
| `version` (text) | `VERSION:<v>` `COMMIT:<sha>` `CONTRACT:<n>` `ENGINE:<abs path>`, one per line, exit 0 | `TestVersionText` |
| `version --json` | `{"version":…,"commit":…,"contract":<int>,"engine":…}` + newline | `TestVersionJSON` |
| build identity | `-X main.version=<V>` / `-X main.commit=<sha>`; unset → `devel` / `unknown` (matches no shim tier). The contract is the source constant `testmap.Contract`, not an ldflag | `TestLdflagsWiring`, `TestVersionText` |
| stub verb | stderr `NOT_IMPLEMENTED:<verb>` (`onboard <sub>` for sub-verbs), exit 64, no stdout | `TestStubsExit64` |
| unknown verb / usage | stderr `UNKNOWN_VERB:<verb>` then `USAGE:<msg>`; bare usage `USAGE:<msg>`; exit 64 | `TestUnknownAndUsage` |
| verb table | the proposal's list, exactly; each row has `Run` xor `Sub` | `TestVerbTableMatchesProposal` |
| exit codes | 0 ok · 1 fail · 2 nothing ran · 3 framework · 64 usage · 75 refused; out-of-contract → 3 + `EXIT_CONTRACT_VIOLATION:<verb>\|<code>` | `TestEnforce`, `TestExitContractEnforced` |
| line protocol | `CLASS:f1\|f2`; a field with `\|` or a line break is refused, never emitted | `TestLine`, `TestLineRefusesUnsafe` |
| `CONTRACT_MISMATCH` | `CONTRACT_MISMATCH:<path>\|<file contract>\|<engine contract>`, exit 3; older/absent contract accepted. `contract:` must be a non-negative integer scalar in a single mapping document — a float, null, string, repeated key or second document is an error, never a pass. A path that cannot travel in a line makes `Line()` return an error | `TestCheckContract`, `TestCheckContractErrors`, `TestContractMismatchLineRefusesUnsafePath` |
| cache root | `${XDG_CACHE_HOME:-$HOME/.cache}/aitasks/testmap` on every OS (relative XDG ignored; no absolute HOME → error) | `TestCacheRoot`, `TestCacheDir` |
| fixture API | `fixture.New(t, [SHA256()])`, `Write`, `Remove`, `Commit(t, task, type, desc)` → `<type>: <desc> (t<task>)`, `History`, `Run`; fixed dates and identity, the caller's global/system git config cut off → identical ids every run, whatever the environment | `TestHistory`, `TestDeterministic`, `TestIsolatedFromCallerGitConfig` |
| baseline file | `<pkg>.<Benchmark> <ns/op> [budget=<duration>] [cal=cpu\|spawn\|sha1]`, `#` comments; ns/op finite and > 0, written at full precision; unknown, empty or repeated fields are errors. The reserved lines `benchgate.Calibration` / `CalibrationSpawn` / `CalibrationHash` are the per-class host-speed references and take no `cal=` | `TestRewrite`, `TestRewriteKeepsPrecision`, `TestParseBaselineErrors` |
| benchgate | first line `BENCH_MODE:full\|partial`; then one host-scale line per class in use (`cpu` always, then any other class a baseline line names), sorted: `BENCH_SCALE:<class>\|<scale>\|<cur cal>\|<base cal>`, `BENCH_SCALE_IMPLAUSIBLE:<class>\|<scale>\|<cur cal>\|<base cal>` (outside 0.25–4, fails in both modes), `BENCH_CALIBRATION_MISSING:<class>\|baseline\|current` (full, fails) or `BENCH_UNSCALED:<class>\|baseline\|current` (partial); then `BENCH_OK:` `BENCH_REGRESSION:<n>\|<cur>\|<base>\|<ratio>` (`<base>` as recorded, `<ratio>` = cur / (base × its class's scale), failing above `Threshold` 1.6) `BENCH_OVER_BUDGET:` (never scaled) `BENCH_NEW:` `BENCH_MISSING:` `BENCH_EMPTY:` (nothing measured besides the calibrations) `BENCH_INVALID:<n>\|<value>` `BENCH_PRODUCER_FAILED:<code>` `BENCH_UPDATED:`; exit 0 / 1 / 64. Full fails on missing, empty or producer failure; it runs the producer itself (no pipe), serially, at GOMAXPROCS 1 and fastest-of-three (`go test -p 1 -cpu 1 … -count 3`). `-update` refuses (exit 1, file untouched) a run missing a calibration the rewritten file needs, or with nothing but calibrations | `TestCompareThreshold`, `TestGateMissingBaselineBench`, `TestGateEmpty`, `TestGateProducerFailure`, `TestSlowedFixtureFailsTwoX`, `TestCalibrationScalesSlowHost`, `TestCalibrationCatchesRegression`, `TestCalibrationFastHostUnmasks`, `TestCalibrationMissing`, `TestCalibrationImplausible`, `TestBudgetNotScaled`, `TestSpawnClassScalesSeparately`, `TestSpawnCalibrationRequiredOnlyWhenUsed`, `TestCalibrationsTable`, `TestUpdateRefusesUnjudgeableRun`, `TestDefaultProducerSerial` |
