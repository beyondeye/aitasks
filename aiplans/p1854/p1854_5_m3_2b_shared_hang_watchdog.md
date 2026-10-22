---
Task: t1854_5_m3_2b_shared_hang_watchdog.md
Parent Task: aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md
Sibling Tasks: aitasks/t1854/t1854_1_*.md, aitasks/t1854/t1854_2_*.md, aitasks/t1854/t1854_3_*.md, aitasks/t1854/t1854_4_*.md, aitasks/t1854/t1854_6_*.md, aitasks/t1854/t1854_7_*.md, aitasks/t1854/t1854_8_*.md, aitasks/t1854/t1854_9_*.md, aitasks/t1854/t1854_10_*.md, aitasks/t1854/t1854_11_*.md, aitasks/t1854/t1854_12_*.md, aitasks/t1854/t1854_13_*.md, aitasks/t1854/t1854_14_*.md
Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-22 14:58
---

# Plan: t1854_5 — M3.2b Shared hang watchdog

## Context

The t1985 hang watchdog (`isolated`, `runChild`, `reapMarked`, bounded output
scanning) and the t1998 source tripwire are unexported `_test.go` code in package
`goengines/internal/testmap/runner`. Every new process-starting M3.2 package (the
t1854_6 foundation, t1854_3's scheduler, every adapter) sits outside both. This
task moves the watchdog to a shared, test-only package
`goengines/internal/testsupport/hangguard`. It also generalizes the tripwire to a
declared list of packages, **without changing runner's behaviour**. Work is on
the current branch (profile `fast`). The task body is authoritative for G1–G10
and the acceptance criteria.

## Step 0 — Reality check (verified 2026-10-22 at `6dc5b76a4`)

**As landed.**
- `runner/watchdog_unix_test.go` (595 lines, `//go:build unix`) holds:
  - constants `isolateEnv="AIT_RUNNER_TEST_ISOLATE"`, `hangLimit=20s`, `quitGrace`, `reapBound`, `outputCap`, `readChunk`;
  - `errNoEnumeration`, `isolated`, `childSettings`, `parentSettings`, `flagValue`, `(childSettings).args`;
  - `childRunPattern`, `splitRunPattern`, `rewrite`, `isSpace`, `childRun`, `runChild`, `scanOutput`, `(childRun).problems`;
  - tests `TestChildRunPattern`, `TestScanOutput` (with `xs`).
- `watchdog_linux_test.go` (783 lines) holds:
  - the seams `wdReadEnviron`, `wdReadStat`, `wdKill`, plus `wdGone`, `confirmDelay`, `wdProcExists`;
  - `markedProc`, `uncertainProc`, `scanMarked`, `hasEntry`, `parseWdStat`, `reapMarked`;
  - the control-only `controlEnv="AIT_RUNNER_TEST_CONTROL"`, `noisyBytes`, `procLive`, `sessionOf`, `readLines`, `appendLine`, `spawnEscaped`, `recordSubtests`, `controlFixture`;
  - tests `TestIsolationControls` and `TestReapMarkedUncertainty`, which use `readPid` from `harness_test.go`.
- `watchdog_other_test.go` is the `unix && !linux` `reapMarked` stub.
- `isolation_tripwire_test.go` (672 lines) holds:
  - `modPath`, `localStarters{Run,Load,sweepSession}`, `importStarters`, `isolationAllow{TestIsolationControls,TestReapMarkedUncertainty}`, `guardName="isolated"`;
  - `parseRunnerPkg` (hard-codes package `runner`), `importNames`, `isImportStarter`, `refsOf`, `isTestFunc`, `isGuard` (local ident only), `classifyTests` (reads the global starter lists), `isolationFindings`, `findingKeys`, `runnerSources` (reads `.`);
  - `TestIsolationTripwire` (whose vacuity check needs ≥1 guarded test and that it finds itself) and `TestIsolationTripwireCatches` (synthetic shapes plus a red proof that drops each guard on the real tree).
- **Outside those files:** about 50 runner tests use `if !isolated(t, hangLimit)`. None of the moved identifiers is referenced anywhere else in `runner` (grep checked). `readPid` stays in runner, because `cleanup_linux_test.go` uses it.
- **Preflight callers:** `ci/preflight.sh` runs `go test -count=1 -run '^TestIsolationTripwire(Catches)?$' ./internal/testmap/runner/`. Its callers are `goengines-check.yml`, `release.yml` (both just call `./ci/preflight.sh`) and `aitask_engine.sh cmd_test`. **`tests/test_install_engine_binary.sh` E7 pins that exact command line.**
- **Non-test code using `testing`:** `internal/testmap/fixture/fixture.go` already imports `testing` outside a test file. `flag.Lookup("test.*")` works from a non-test package, because only test binaries link it. So the controls can run from a non-test package.

**Task body says / repository has / decision.**

| # | task body / plan | repository | decision |
|---|---|---|---|
| D1 | runner keeps a one-line `isolated(t, limit)` wrapper | Go needs `t.Helper()` so that reports point at the guard line | wrapper body `t.Helper(); return hangguard.Isolated(t, limit)`, which is one logical line. `hangLimit` (20 s, with its comment about the `sleep 30` fixtures) stays in runner: each package picks its own limit |
| D2 | controls pass "from their new home" | the controls re-exec `os.Executable()` with `-test.run=^TestIsolationControls$`, so they must be tests **of** hangguard | the controls move to hangguard's own internal `_test.go` files (package `hangguard`), reaching the unexported `runChild`, `reapMarked` and seams directly. A ~10-line `readPid` copy goes with them |
| D3 | "no behaviour change" | the env names say `RUNNER`, which misleads once adapters use the guard | rename them to `AIT_HANGGUARD_ISOLATE` / `AIT_HANGGUARD_CONTROL`. No production code reads either (grep checked); only the debugging recipe changes, and the package doc is updated. Report texts (`HANG:`, `LEAK:`, `isolated: …`) stay byte-identical |
| D4 | where the package list lives | the tripwire's starter and allow lists are Go data | **`tripwirePackages` in `hangguard/tripwire_test.go`**, one struct per package: `{dir, name, localStarters, allow}`. Preflight runs that one test package, so a new package opts in with one entry, and `preflight.sh`, the workflows and `ait engine test` need no further change |
| D5 | the guard form | runner uses a local `isolated`; new packages will call `hangguard.Isolated` directly | `isGuard` accepts both forms: the local ident `isolated`, and `<import>.Isolated` where the import **path** is hangguard (so a renamed import counts). Neither reference ever counts as a process start |
| D6 | each entry has "its own local starters" | another package calling `runner.Run` would not be seen | each entry's import starters = the global `importStarters` plus every *other* entry's `localStarters`, qualified by that entry's import path. So once `runner` is listed, `runner.Run` and `runner.Load` count in every other listed package |
| D7 | vacuity check | `self` meant "this test is in runner" | per entry: the directory parses with ≥1 file of the declared package, ≥1 test is guarded or allowlisted, and every `localStarters` name is declared. Globally, `TestIsolationTripwire` must be found in the hangguard entry |
| D8 | "a guard test asserts that no non-test file imports it" | — | `TestIsolationTripwireImports` in hangguard walks the module and flags (a) a non-test `.go` file importing hangguard, and (b) a `_test.go` file importing hangguard from a directory not in `tripwirePackages` (completeness: a package using the guard cannot escape the tripwire). It skips `testdata`, `vendor` and `.`/`_` directories, as the go tool does. Preflight runs it too |
| D9 | proof package | t1854_6 has not landed | a test-only fixture package, `hangguard/tripfixture`, listed as the third entry (D10) |
| D10 | hangguard itself | its controls start processes, unguarded by design | hangguard is a list entry with `allow` = the two controls (carried over verbatim from `isolationAllow`), so stale-allow detection and new-unguarded-test detection still cover it. Runner's `allow` becomes empty |
| D11 | ownership | E7 in `tests/test_install_engine_binary.sh` pins preflight's command | updated as a named extension of preflight. `aidocs/framework/go_engine.md` (the preflight description) and `goengines/README.md` (Layout, Rules, Interfaces rows) are this task's doc touchpoints. The proposal row for M3.2b already matches; no edit |
| D12 | sibling facts | t1854_3 and t1854_6–14 carry "`isolated` … unexported test code in package runner; the tripwire parses only runner" | after the commit, send each one an `/aitask-note` naming the API, the opt-in entry and the commit SHA |

## Implementation

### Pre-phase (risk mitigations)

1. [tripwire_baseline] Before any edit, collect a per-test classification of runner from the **old** tripwire. The working tree is never edited for this.
   - **Module-preserving copy.** `internal/...` imports resolve only inside the `github.com/beyondeye/aitasks/goengines` module, so a lone runner directory cannot compile. Export the whole module from HEAD, keeping its layout and `go.mod`: `git archive HEAD goengines | tar -x -C <scratchpad>/before/`.
   - **The dump.** In that copy only, add to `TestIsolationTripwire` a loop that writes one line per test to the file named by `AIT_TRIPWIRE_DUMP`, in the format `<name>|guarded=<bool>|allowed=<bool>|via=<a→b→…>`, sorted.
   - **The run.** `cd <scratchpad>/before/goengines && AIT_TRIPWIRE_DUMP=<scratchpad>/tripwire_baseline.txt go test -count=1 -run '^TestIsolationTripwire$' ./internal/testmap/runner/`. Also save the `-v` summary line ("N guarded, M pure, K allowlisted").
   - **After step 4**, produce the same dump from the **new** tripwire the same way: a copy of the post-change module tree (`rsync` of `goengines/` into `<scratchpad>/after/`, since the change is not committed yet), with the same temporary loop, restricted to the runner entry. Then `diff` the two dumps.
   - **Allowed difference.** Only the six rows for the tests that left runner may differ: `TestIsolationControls`, `TestReapMarkedUncertainty`, `TestChildRunPattern`, `TestScanOutput`, `TestIsolationTripwire` and `TestIsolationTripwireCatches`. Any other changed row stops the work. As a sanity check, the baseline must hold a non-zero guarded count, so the dump is not vacuous.

### 1. New package `goengines/internal/testsupport/hangguard/` (non-test code)

- `hangguard.go` (`//go:build unix`): the package doc (the t1985 rationale, generalized: "a process-starting test of any package"; the residuals; the controls; the debug recipe `AIT_HANGGUARD_ISOLATE='TestX|debug' go test -run '^TestX$' ./<pkg>/`; "imported only from `_test.go` files, enforced by `TestIsolationTripwireImports`"). It contains everything from `watchdog_unix_test.go` except the two tests and `xs`, moved verbatim, with these changes:
  - `isolated` becomes the exported `Isolated(t *testing.T, limit time.Duration) bool`;
  - `isolateEnv` becomes `"AIT_HANGGUARD_ISOLATE"`;
  - `hangLimit` is dropped (D1).
- `reap_linux.go`: the seams, `wdGone`, `confirmDelay`, `wdProcExists`, `markedProc`, `uncertainProc`, `scanMarked`, `hasEntry`, `parseWdStat` and `reapMarked`, verbatim.
- `reap_other.go` (`//go:build unix && !linux`): the stub, verbatim.

### 2. hangguard tests

- `hangguard_unix_test.go` (`//go:build unix`): `TestChildRunPattern`, `xs` and `TestScanOutput`, verbatim.
- `controls_linux_test.go`: the control helpers and `TestIsolationControls` / `TestReapMarkedUncertainty`, verbatim, with these changes:
  - `controlEnv` becomes `"AIT_HANGGUARD_CONTROL"`;
  - a local `const hangLimit = 20 * time.Second` is added for the controls;
  - the guarded fixture mode calls `Isolated(t, hangLimit)`;
  - a `readPid` copy is added.
- `tripwire_test.go` (no build tag): the t1998 tripwire, generalized.
  - `type tripPackage struct{ dir, name string; localStarters []string; allow map[string]string }` and `var tripwirePackages = []tripPackage{runner, hangguard, tripfixture}`.
  - `parsePkg(fset, name, srcs)` replaces `parseRunnerPkg` (it refuses a file of another package and a dot import).
  - `isGuard(s, param, imports)` accepts the D5 forms.
  - `classifyTests(fset, files, localStarters, importStarters)` and `isolationFindings(tests, allow)`.
  - `startersFor(entry)` implements D6.
  - `moduleRoot(t)` walks up to `go.mod` and checks its `module` line equals `modPath`; `packageSources(t, dir)` reads the entry's directory.
  - The unguarded-finding message names both guard forms and points at `tripwirePackages`.
  - Tests:
    - `TestIsolationTripwire`: every entry, findings plus D7.
    - `TestIsolationTripwireCatches`: the existing synthetic shapes, verbatim, plus:
      - a guard through `hangguard.Isolated`, and through a renamed `hg` import → clean;
      - `<other pkg>.Isolated` → unguarded;
      - a cross-package `runner.Run` from a synthetic `package other` with the derived starters → unguarded, and without runner's entry → no finding;
      - for **every** entry, **every** guarded test: guard dropped → base + `:unguarded`; body reduced to the guard → base + `:unseen`;
      - for `tripfixture`: removing `startAll` from its starters → base + `TestGuardedLocalStarter:unseen`.
    - `TestIsolationTripwireImports`: the D8 walk over the real module, plus a pure `importFindings(files, listed)` checked against synthetic files: a non-test import, a renamed import, a test import in an unlisted dir → each flagged; a listed test import → clean.

### 3. Fixture package `hangguard/tripfixture/` (test-only)

`fixture_test.go` (`//go:build unix`, package `tripfixture`):
- `startAll(cs []*exec.Cmd) error` (start and wait through methods, so the tripwire cannot see it: it is the entry's local starter);
- `TestGuardedCommand`: `if !hangguard.Isolated(t, limit) { return }`, then `exec.Command("/bin/sh", "-c", "exit 0").Run()`;
- `TestGuardedLocalStarter`: guarded, then `startAll([]*exec.Cmd{{Path: "/bin/sh", Args: []string{"sh", "-c", "exit 0"}}})`.

Both really run under `go test ./...` as an end-to-end consumer check of `Isolated` from another package.

### 4. runner reduced

- Delete `watchdog_linux_test.go`, `watchdog_other_test.go` and `isolation_tripwire_test.go`.
- `watchdog_unix_test.go` becomes: `//go:build unix`, a short comment (the guard lives in hangguard; runner is a `tripwirePackages` entry), `const hangLimit = 20 * time.Second` with its original comment, and the `isolated` wrapper.

### 5. Preflight, pin test, docs

- `ci/preflight.sh`: `go test -count=1 -run '^TestIsolationTripwire(Catches|Imports)?$' ./internal/testsupport/hangguard/`. The header comment is updated to say that it covers every `tripwirePackages` entry and how a package opts in.
- `tests/test_install_engine_binary.sh` E7: update the `want` line to the new command. The stub's `*TestIsolationTripwire*` match still holds.
- `aidocs/framework/go_engine.md` (check job, step 1): the preflight runs the hangguard tripwire over every listed package.
- `goengines/README.md`:
  - a Layout row for `internal/testsupport/hangguard` (with `tripfixture`);
  - a Rules bullet: process-starting tests begin with the guard, and the package gets one `tripwirePackages` entry; test-support packages live under `internal/testsupport/` and are never imported by non-test code;
  - an Interfaces row "hang guard (M3.2b)": `hangguard.Isolated(t, limit) bool` as the first statement; `HANG:<test>|<limit>`, `LEAK:<test>|<pids>`; the entry shape; pinned by `TestIsolationControls`, `TestIsolationTripwire`, `TestIsolationTripwireCatches` and `TestIsolationTripwireImports`.

### 6. Red proofs on disk (isolated mutants, each restored byte-identical and checked with `cmp` against a saved copy)

1. Drop the guard in `tripfixture`'s `TestGuardedCommand` → `ci/preflight.sh` fails naming it `unguarded`.
2. Reduce `TestGuardedLocalStarter` to its guard → `unseen`.
3. Add `import _ ".../hangguard"` to a non-test runner file → `TestIsolationTripwireImports` fails.
4. Remove runner from `tripwirePackages` → the Imports completeness check fails for runner.
5. Point `isGuard`'s selector match at the wrong name → the real-tree tripwire flags `tripfixture`'s tests.

### Post-phase (risk mitigations)

1. [move_diff_audit] For each moved file, check what changed:
   - Take the old version (`git show HEAD:goengines/internal/testmap/runner/<f>`) and apply the planned renames with one `sed` script: `package runner`→`package hangguard`, `isolated(`→`Isolated(`, `AIT_RUNNER_TEST_ISOLATE`→`AIT_HANGGUARD_ISOLATE`, `AIT_RUNNER_TEST_CONTROL`→`AIT_HANGGUARD_CONTROL`.
   - `diff` the result against the concatenation of its new homes, with the test/non-test split undone by sorting top-level declarations.
   - The residual diff may hold only the D1/D2 edits: the doc-comment rewrite, the dropped `hangLimit`, the added `readPid`, the controls' local `hangLimit`, and the build tags.
   - For the tripwire, the residual is reviewed hunk by hunk against the D4–D8 list. Record the residual-diff summary in the plan's Final Notes.

## Verification (= the acceptance criteria)

- `cd goengines && test -z "$(gofmt -l .)" && go vet ./... && ./ci/preflight.sh && go test ./...`.
- `go test -count=1 -v -run 'TestIsolationControls|TestReapMarkedUncertainty|TestChildRunPattern|TestScanOutput' ./internal/testsupport/hangguard/`: `HANG` and `LEAK` controls green from the new home.
- `go test -count=1 ./internal/testmap/runner/`: every runner test still guarded (the tripwire reports the guarded count for runner, unchanged from before the move) and passing.
- `ait engine test` green; `bash tests/test_install_engine_binary.sh` green (E7).
- Cross-build sanity: `GOOS=darwin go vet ./internal/testsupport/... ./internal/testmap/runner/` (the `reap_other.go` path compiles).
- The step 6 red proofs above.
- Both workflows run only `./ci/preflight.sh`, which is unchanged in interface, so they stay green with the local run.

## Risk

### Code-health risk: low
- The ~2000-line move could silently alter the watchdog (a dropped line, a changed constant or message) under the guise of "verbatim". The guard ~50 runner tests depend on would then change behaviour while still compiling · severity: low (residual — addressed by inline post-phase move_diff_audit) · → mitigation: inline post-phase move_diff_audit
- Generalizing the tripwire (per-entry starters, derived import starters, two guard forms, the new vacuity rule) could quietly weaken runner's coverage: a test that was `unguarded` before now classified pure or guarded · severity: low (residual — addressed by inline pre-phase tripwire_baseline) · → mitigation: inline pre-phase tripwire_baseline
- The D3 env rename (`AIT_RUNNER_TEST_*` → `AIT_HANGGUARD_*`) is a deliberate deviation from a literal "no change". No code reads the names, but the debug recipe changes · severity: low · → mitigation: none (documented in D3)

### Goal-achievement risk: low
- The non-Linux path (`reap_other.go`) is only compiled locally, not run (CI is Linux) · severity: low · → mitigation: none (the `GOOS=darwin go vet` check in Verification)

### Planned mitigations
- timing: pre-phase | name: tripwire_baseline | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: tripwire generalization weakening runner coverage | desc: per-test classification baseline of runner before the move, diffed after
- timing: post-phase | name: move_diff_audit | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: silent alteration during the verbatim move | desc: rename-normalized diff of every moved file against its new home

## Post-implementation

Step 8 review, commit (`refactor: … (t1854_5)`), then the D12 notes citing the commit SHA, then Step 9 archival on the current branch (no merge).
