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
  because the full gate fails on `BENCH_MISSING`.

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
| baseline file | `<pkg>.<Benchmark> <ns/op> [budget=<duration>]`, `#` comments; ns/op finite and > 0, written at full precision | `TestRewrite`, `TestRewriteKeepsPrecision`, `TestParseBaselineErrors` |
| benchgate | first line `BENCH_MODE:full\|partial`; `BENCH_OK:` `BENCH_REGRESSION:<n>\|<cur>\|<base>\|<ratio>` `BENCH_OVER_BUDGET:` `BENCH_NEW:` `BENCH_MISSING:` `BENCH_EMPTY:` `BENCH_INVALID:<n>\|<value>` `BENCH_PRODUCER_FAILED:<code>` `BENCH_UPDATED:`; exit 0 / 1 / 64. Full fails on missing, empty or producer failure; it runs the producer itself (no pipe) | `TestGateMissingBaselineBench`, `TestGateEmpty`, `TestGateProducerFailure`, `TestSlowedFixtureFailsTwoX` |
