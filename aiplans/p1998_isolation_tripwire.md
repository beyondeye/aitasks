---
Task: t1998_isolation_tripwire.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1998 — Isolation tripwire for the runner package's hang guard

## Context

t1985 put every process-starting test of `goengines/internal/testmap/runner`
under a hang watchdog: each such test begins with

```go
if !isolated(t, hangLimit) {
	return
}
```

and its body then re-runs in a subprocess with its own deadline
(`watchdog_unix_test.go`, `watchdog_linux_test.go`). Nothing enforces the
convention, so a new test that drives `Run` can omit the guard and hang the
suite again. This task adds a source tripwire, in the style of
`TestInvariant5Tripwire` / `TestInvariant5TripwireCatches`
(`goengines/guards_test.go`), that fails such a test.

Survey of the tree as it stands (checked during planning, matches t1985):
33 guarded tests (provenance 3, timeout_run 6, cleanup_linux 5, run 13,
list 1, repo 5); 20 pure unguarded tests (outcome 6, group 4, list 2,
describe 6, repo 2) plus `TestChildRunPattern` and `TestScanOutput`; 2
controls that start processes unguarded (`TestIsolationControls`,
`TestReapMarkedUncertainty`). `TestScanOutput` is a pure test that a
concurrent session added (t1993, `cbfc74fed`) while this plan was being
written; that commit left the `watchdog_unix_test.go` header sentence edited
below unchanged. All 30 files are `package runner` (no external test
package).

**Commit scope.** Other sessions are editing this checkout concurrently, so
commit by name exactly the ten task-owned paths, and nothing else:

1. `goengines/internal/testmap/runner/isolation_tripwire_test.go` (new)
2. `goengines/internal/testmap/runner/watchdog_unix_test.go`
3. `goengines/ci/preflight.sh` (new, mode 100755)
4. `.github/workflows/goengines-check.yml`
5. `.github/workflows/release.yml`
6. `.aitask-scripts/aitask_engine.sh`
7. `tests/test_release_workflow_goengines.py`
8. `tests/test_install_engine_binary.sh`
9. `goengines/README.md`
10. `aidocs/framework/go_engine.md`

Before committing, run `git diff` on each of the eight pre-existing paths and
confirm that every hunk is this task's. `watchdog_unix_test.go` in particular
was just changed by t1993. If a path carries a foreign hunk, stop and ask
rather than committing someone else's work. Unrelated dirty files, such as
the `deps/` changes now in the tree, are left out.

## Approach

A name-based reachability analysis over `go/ast` (standard library only, so
the module's dependency allowlist is untouched). Type-checking with `go/types`
is ruled out: the package's build-tagged variants (`reapMarked` in
`watchdog_linux_test.go` and `watchdog_other_test.go`, `sessionProcs` in three
`proc_*.go` files) collide when every file is checked together, and importing
the dependencies from source would mean shelling out to `go list`.

- **Parse every `.go` file in the package directory**, test and non-test,
  ignoring build constraints. That way a Linux-only test is checked on any
  host, and a new package-level production function that calls a starter is
  followed without editing the starter list. A file whose package clause is
  not `runner` fails the test, because an external test package would
  otherwise escape the check unseen.
- **Graph nodes** are the package-level functions (no receiver) and the
  package-level variables, whose initializers are walked. Declarations that
  share a name across build-tagged files are unioned.
- **References** are every identifier in a body that could name a
  package-level declaration, not just call targets. That covers function
  values such as `[]func(...){batchRepo}` in table tests, calls inside
  `t.Run` closures, and calls through a package variable. Four kinds of
  identifier are excluded: a selector's `.Sel` (so `t.Run` is not `Run`),
  struct-literal keys (`spec{Run: …}`), field and parameter names, and labels.
  A selector whose `X` is an import name of that file resolves to
  `<import path>.<Sel>`, which keeps renamed imports correct.
- **Starters** are the seed set:
  - local `Run`, `Load` and `sweepSession`. `Run` reaches processes through
    the `Executor` interface, `Load` through `(*Runner).call` and
    `gitx.Repo{}.ListFiles`, and neither path is visible to name resolution.
    `sweepSession` is a hang hazard without starting anything.
  - `os/exec.Command`, `os/exec.CommandContext`, `os.StartProcess`,
    `syscall.ForkExec` and `syscall.StartProcess`.
  - `registry.Scan`, `registry.Check` and `fixture.New`.
  - every reference into `internal/gitx`, whose only job is to run git; this
    also catches `gitx.Repo{…}.Run`.

  `execRunner`, `startSession`, `runAll`, `timedRun`, `newRepo`, `batchRepo`,
  `threeRepo`, `provRepo` and similar helpers are not listed. The traversal
  derives them, and the "guarded but unseen" check below proves it does on
  the real tree.
- **`isolated` is excluded from the graph.** It reaches `exec.Command`
  through `runChild`, so counting it would make every guarded test look
  process-starting merely because it carries the guard. `runChild` itself
  still counts.
- A fixpoint over the sorted node names records, for each node, the reference
  it reaches a starter through. That gives every failure a witness chain,
  e.g. `TestX → batchRepo → newRepo → fixture.New`.

**Per top-level test.** A test is a `Test*` function with no receiver, one
`*testing.T` parameter, and a name that does not continue in lowercase.
`TestMain` is skipped because of its parameter type. The guard is matched
exactly: `if !isolated(<t>, <any>) { return }` as the first statement, with no
init, no else, and a body that is a bare `return`. `<t>` must be the test's own
parameter name. The test fails on any of these findings:

1. **Unguarded.** The test reaches a starter, its first statement is not the
   guard, and it is not allowlisted. The message gives the witness chain and
   the guard to add.
2. **Guarded but unseen.** The test is guarded, but the analysis sees no
   process start. Either a path the test takes is missing from the starters,
   or the guard is unneeded. This keeps the seed list honest and is what
   proves that today's 33 guarded tests are all classified as
   process-starting.
3. **Stale allowlist.** An `isolationAllow` entry names no test, or names a
   test the analysis sees as pure.
4. **Stale starter.** A local starter names no package-level declaration.
   This check runs on the real tree only, because the synthetic control
   declares its own starters.

Calls through methods, interfaces and function-typed fields are not
followed. The file's header comment states this residual, as `guards_test.go`
does for Invariant 5.

## Steps

1. **New file `goengines/internal/testmap/runner/isolation_tripwire_test.go`**
   (package `runner`, no build tag):
   - The header comment covers what the tripwire enforces, why it is lexical,
     and the residual named above.
   - `localStarters` and `importStarters`. The latter is keyed by
     `<import path>.<name>`, and `<path>.*` covers a whole package. The
     module path prefix is `github.com/beyondeye/aitasks/goengines`.
   - `isolationAllow map[string]string`, with a reason for each entry:
     - `TestIsolationControls`: the watchdog's own negative controls; they
       launch `runChild` themselves and must observe the HANG/LEAK report it
       produces.
     - `TestReapMarkedUncertainty`: it drives `reapMarked` against processes
       it starts; isolating it would put it under the cleanup it tests.
   - `parseRunnerPkg(fset, srcs map[string][]byte) ([]*ast.File, error)`.
     It rejects a package clause other than `runner`.
   - `refsOf(node, imports)` returns the local names and the matched import
     starter, using the exclusions above.
   - `classifyTests(files) (tests []tripTest, declared map[string]bool)`.
     `tripTest` holds the name, position, decl, guarded, starts and via-chain.
   - `isGuard(stmt, param) bool` and `isTestFunc(fd) (param string, ok bool)`.
   - `isolationFindings(tests, allow) []tripFinding`, where `tripFinding`
     holds the test name and the message. Findings are sorted.
   - **`TestIsolationTripwire`** runs on the real tree:
     - It reads `os.ReadDir(".")` and parses every `*.go` file.
     - It reports the findings and the stale starters.
     - It logs the survey: guarded / pure / allowlisted counts.
     - Two vacuity guards apply: at least one guarded test must be found,
       and `TestIsolationTripwire` itself must appear among the tests, which
       proves the directory was read.
   - **`TestIsolationTripwireCatches`** holds the negative controls:
     - **Synthetic package.** It is two files, so that cross-file helpers are
       covered. One file declares its own `Run`, `runAll`, helpers and an
       `isolated` that calls `exec.Command`; the other file holds the tests.
       The control asserts the *exact* flagged name set:
       - These must be flagged:
         - `runAll` called directly
         - `runAll` reached through a two-level helper chain
         - the guard present but not the first statement
         - `runAll` inside a `t.Run` closure
         - `runAll` passed as a function value in a table
         - `exec.Command` through a renamed `os/exec` import
         - a call through a package variable aliasing `exec.Command`
         - `fixture.New`
         - `gitx.Repo{}.Run`
         - the positive guard form `if isolated(t, …) { … }`
         - a properly guarded test with no process start (finding 2; this
           also proves that `isolated` is excluded)
         - the stale allowlist cases: a missing name, and a pure test listed
       - These must not be flagged:
         - a properly guarded process-starting test
         - an allowlisted unguarded one
         - a pure test carrying the look-alikes `t.Run("Run", …)`,
           `spec{Run: "x"}` and a `Run:` label
     - **Red proof on the real tree.** For every guarded test, drop its first
       statement in memory, re-classify, and assert that the findings are the
       unmutated tree's findings plus exactly that test. The count must be
       greater than zero.
2. **`goengines/internal/testmap/runner/watchdog_unix_test.go` header.** The
   header currently says "TestIsolationControls and TestReapMarkedUncertainty
   start processes but are not isolated: they are the watchdog's own
   controls." Add one sentence after it: `isolation_tripwire_test.go` fails a
   test that reaches a process start without the guard as its first
   statement, these two are its allowlist, and `ci/preflight.sh` runs it
   before the suite.

### Execution order: the tripwire runs before the suite (review concern, blocking)

Inside `go test ./...` the tripwire is just another test. Go runs a
package's tests in filename order, so the tests in `cleanup_linux_test.go`,
`describe_test.go`, `group_test.go` and `harness_test.go` run before
`isolation_tripwire_test.go`. Without `-failfast`, a tripwire failure also
does not stop a later test from hanging. Three entry points run the suite
directly:

- `.github/workflows/goengines-check.yml:75`
- `.github/workflows/release.yml:49`
- `.aitask-scripts/aitask_engine.sh:134` (`cmd_test`)

The fix is a preflight that runs the tripwire **alone** and lets the suite
start only when it passes. It goes through one script, so the `-run` pattern
lives in one place rather than in three entry points (the 3+-files
single-source rule).

3. **New `goengines/ci/preflight.sh`** (executable; its style follows
   `ci/benchci.sh`):
   - The header lists each caller and explains why the tripwire runs alone
     first.
   - It runs `set -euo pipefail`, then `cd "$(dirname "${BASH_SOURCE[0]}")/.."`,
     then
     `go test -count=1 -run '^TestIsolationTripwire(Catches)?$' ./internal/testmap/runner/`.
   - `Catches` is included because a passing tripwire means nothing unless it
     can still catch. The real-tree mutant assertion compares against the
     *unmutated* findings (baseline plus that one test), so a pre-existing
     violation reports once, in `TestIsolationTripwire`, and is not
     duplicated 33 times.
   - The path is under `goengines/**`, so the check workflow's trigger paths
     already cover it.
4. **Both workflows.** Add a step `- name: Hang-guard preflight` with
   `run: ./ci/preflight.sh` between `go vet` and `go test`, in
   `goengines-check.yml` (`check` job) and `release.yml` (`goengines` job). A
   failing step stops the job, so the suite never starts.
5. **`.aitask-scripts/aitask_engine.sh`.** `cmd_test` becomes `go vet ./...`,
   then `"$GOENGINES/ci/preflight.sh"`, then `go test ./... "$@"`. `set -e`
   stops the run on a preflight failure. User args are not forwarded to the
   preflight, because a `-run` would conflict with its own. The header line
   for `test [args]` is updated to match.
6. **Pin the order** so that a later edit cannot silently drop the preflight:
   - `tests/test_release_workflow_goengines.py` gets one helper, used by a new
     `test_preflight_precedes_the_suite` in both `ReleaseWorkflow`
     (`goengines` job) and the check-workflow class (`check` job). The helper
     asserts exactly one step runs `./ci/preflight.sh` and that its index is
     below that of the first step running `go test ./...`.
   - `tests/test_install_engine_binary.sh` gets a new E7 case: the real
     `aitask_engine.sh test` with `go` stubbed on `PATH`.
     - Setup: a scratch framework tree holding a copy of `$T/.aitask-scripts`,
       `goengines/build.sh` (needed by `require_source`) and the real
       `goengines/ci/preflight.sh` (`cp -p`).
     - The stub logs `$PWD|$*` and fails when its args name the tripwire and a
       fail flag is set.
     - E7a: the log is `vet ./...`, then the preflight `test -count=1 -run …
       ./internal/testmap/runner/`, then `test ./... -short`, all in
       `goengines/`, exit 0.
     - E7b: a failing preflight gives a non-zero exit, and no `test ./...`
       line is logged.
   - Red first: run both new checks before editing the workflows and
     `aitask_engine.sh`, and confirm they fail; then make the edits.
7. **Docs (current state only).**
   - `goengines/README.md:31`: the build/test line becomes `… && go vet ./... && ./ci/preflight.sh && go test ./...`.
   - `aidocs/framework/go_engine.md` lines 100 and 123: name the preflight
     step and its reason in the `goengines` job and in check step 1.

## Verification

Run from `goengines/`:

- `gofmt -l internal/testmap/runner/` prints nothing.
- `go vet ./internal/testmap/runner/` is clean.
- `go test -count=1 -run 'TestIsolationTripwire' -v ./internal/testmap/runner/`
  passes. The survey should log 33 guarded tests, 24 pure ones (20 +
  `TestChildRunPattern` + `TestScanOutput` + the two new tripwire tests) and
  2 allowlisted ones.
- **Red proof on disk, recorded verbatim in Final Implementation Notes:**
  1. Remove the 3-line guard from `TestRunPassFail` in `run_test.go` with the
     Edit tool.
  2. Run `go test -count=1 -run '^TestIsolationTripwire$' ./internal/testmap/runner/`.
     It must FAIL, naming `TestRunPassFail` with its witness chain.
  3. Restore the lines with the Edit tool. Do not use `git restore`.
  4. Re-run the test (it passes), and check that `git diff --stat -- internal/testmap/runner/run_test.go`
     is empty.
- `./ci/preflight.sh` exits 0 on the clean tree.
- During the on-disk red proof, `./ci/preflight.sh` fails within seconds,
  without running the rest of the suite.
- `python3 tests/test_release_workflow_goengines.py` and
  `bash tests/test_install_engine_binary.sh` both pass. They are red before
  steps 4 and 5 are applied (the new E7 and preflight-order cases fail).
- `shellcheck goengines/ci/preflight.sh .aitask-scripts/aitask_engine.sh` is
  clean.
- The full package `go test -count=1 ./internal/testmap/runner/` passes.
- `go test -count=1 -run 'TestInvariant5|TestDependencyAllowlist' .` (module
  guards) passes.

## Risk

### Code-health risk: low
None identified.
- The Go side is test-only and additive: one new `_test.go` file using only
  the standard library, plus one comment sentence.
- The preflight adds one step to each of two CI jobs and to
  `ait engine test`. It is a one-line script, and its ordering is pinned by
  the workflow test and by E7.
- Name-based false positives fail visibly, and the witness chain names the
  reference that caused them.

### Goal-achievement risk: low
- Lexical residual: a future test that starts a process *only* through a method call, an interface or a func-typed field (e.g. `Lister{}.List`, `(*Runner).call` on a value not obtained from a seeded helper) is not seen, so it is not flagged; the starter list covers today's entry points (`Run`, `Load`, scans, `fixture.New`, gitx, exec), and the guarded-but-unseen check catches starter rot only for tests that are guarded · severity: low · → mitigation: none: accepted by the user at planning; documented in the tripwire's header comment, coverage checks retained

## Step 9 (Post-Implementation)

This runs on the current branch (profile `fast`). Commit the code as
`test: … (t1998)` with `git commit -F - -- <the ten paths above>`, then commit
the plan via `aitask_task_commit.sh`, then archive with
`aitask_archive.sh 1998`.
