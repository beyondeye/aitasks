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

## Final Implementation Notes

- **Actual work done:** everything in Steps 1–7 of the plan, across the ten
  paths listed under **Commit scope**:
  - `isolation_tripwire_test.go` holds the analyzer, `TestIsolationTripwire`
    (real tree) and `TestIsolationTripwireCatches` (synthetic control plus a
    real-tree red proof per guarded test).
  - `watchdog_unix_test.go` gets one header sentence.
  - `goengines/ci/preflight.sh` runs
    `go test -count=1 -run '^TestIsolationTripwire(Catches)?$' ./internal/testmap/runner/`.
  - A "Hang-guard preflight" step sits between `go vet` and `go test` in
    `goengines-check.yml` (`check`) and `release.yml` (`goengines`).
  - `cmd_test` in `aitask_engine.sh` runs `go vet`, then the preflight, then
    `go test ./... "$@"`.
  - Ordering pins:
    - `test_preflight_precedes_the_suite` in both classes of
      `tests/test_release_workflow_goengines.py`. It checks that exactly one
      preflight step exists and runs before the first `go test ./...` step,
      that the preflight step has no `continue-on-error`, and that the suite
      step has no `if:`.
    - E7 in `tests/test_install_engine_binary.sh`: the real engine script
      with a stub `go`. When every step passes, the log shows the order
      vet → preflight → `test ./... -short`. When the preflight fails, the
      exit is non-zero and no `test ./...` line appears.
  - Docs: `goengines/README.md` and `aidocs/framework/go_engine.md`.
- **Deviations from plan:**
  - The guard is excluded once, in `firstReach`, instead of twice. The
    drafted code also dropped `isolated` from the node graph in `add()`.
    Mutant 2 below showed that each exclusion hid the other's removal from the
    synthetic control. One exclusion is enough, and that one is now pinned.
  - The checks shown in the plan as `go test … -v` were run without `-v`;
    the survey line was read from the `-v` run.
- **Issues encountered:**
  - A concurrent session landed t1993 (`cbfc74fed`, `TestScanOutput` plus
    the watchdog's bounded output reads) during planning. The tripwire
    classifies `TestScanOutput` as pure, and the header sentence was
    unaffected.
  - Two review rounds at plan approval added the preflight (execution order)
    and the ten-path commit scope.
- **Key decisions:**
  - The analysis is name-based `go/ast`, standard library only. Selector
    names, struct-literal keys, field names and labels are excluded.
  - Import selectors resolve by path.
  - The starters are local `Run`, `Load` and `sweepSession`; exec, os and
    syscall process starts; `registry.Scan`/`Check`; `fixture.New`; and all
    of `gitx`.
  - The "guarded but unseen" finding keeps the starter list honest.
  - The real-tree mutant compares against baseline findings plus one test,
    so a pre-existing violation reports once.
  - The user accepted the lexical residual (methods, interfaces and
    func-typed fields are not followed) with no follow-up task.
- **Upstream defects identified:** None
- **Verification evidence (survey):** `go test -count=1 -run 'TestIsolationTripwire' -v ./internal/testmap/runner/`
  logged `33 guarded, 24 pure, 2 allowlisted tests` and passed.
- **Analyzer mutants (scratch module, repo file untouched):** each was
  applied with `sed` to a copy of `isolation_tripwire_test.go` in its own
  module, running `TestIsolationTripwireCatches`. The table shows the
  difference against the expected flagged set:

  | mutant | result |
  |---|---|
  | selector `.Sel` counted | extra `TestPure:unguarded` |
  | guard reference counted (`firstReach` exclusion removed) | missing `TestGuardedPure:unseen` |
  | guard not tied to the test parameter | `TestGuardWrongT` no longer flagged |
  | struct-literal keys counted | extra `TestPure:unguarded` |
  | labels counted | extra `TestPure:unguarded` |
  | guard accepted anywhere in the body | missing `TestGuardNotFirst:unguarded` |
  | import starters ignored | missing `TestFixture`, `TestGitx`, `TestPkgVar`, `TestRenamedImport` |

  The unmutated copy passes the synthetic part. Its only failure is the
  expected "red proof is vacuous", because the scratch module holds no
  guarded tests.
- **Red proof on disk (verbatim).** The 3-line guard was removed from
  `TestRunPassFail` in `run_test.go` with the Edit tool, then:

  ```
  $ ./ci/preflight.sh   # guard removed from TestRunPassFail
  --- FAIL: TestIsolationTripwire (0.01s)
      isolation_tripwire_test.go:420: run_test.go:30:1: TestRunPassFail starts a process (TestRunPassFail → batchRepo → newRepo → github.com/beyondeye/aitasks/goengines/internal/testmap/fixture.New) but does not begin with the hang guard
          	if !isolated(t, hangLimit) {
          		return
          	}
          (or, for one of the watchdog's own controls, an isolationAllow entry with its reason)
      isolation_tripwire_test.go:444: 32 guarded, 24 pure, 2 allowlisted tests
  FAIL
  FAIL	github.com/beyondeye/aitasks/goengines/internal/testmap/runner	0.095s
  FAIL
  rc=1
  ```

  Through the real entry point, `./ait engine test -count=1` printed the
  same `TestRunPassFail` failure and exited 1 after 1 s. No other package
  printed `ok`, which confirms the suite never started. The guard was then
  restored with the Edit tool. `git diff --stat -- goengines/internal/testmap/runner/run_test.go`
  was empty, and `./ci/preflight.sh` passed again.
- **Order pins, red first:** before the workflow and `aitask_engine.sh`
  edits, both `test_preflight_precedes_the_suite` cases failed
  (`0 != 1 : exactly one step runs ./ci/preflight.sh`), and E7 failed 4 of
  its 5 assertions (`Results: 218 passed, 4 failed, 222 total`). After the
  edits, the Python test reports `Ran 11 tests … OK` and the engine test
  reports `222 passed, 0 failed`.
- **Lint and module guards:**
  - `shellcheck goengines/ci/preflight.sh` is clean.
  - `shellcheck -x aitask_engine.sh` is clean. Without `-x` the only output
    is the three pre-existing SC1091 info lines for its `source`s.
  - `gofmt -l .` prints nothing.
  - `go vet ./...` is OK.
  - `go test -count=1 -run 'TestInvariant5|TestDependencyAllowlist' .`
    reports `ok`.
- **Full package:** `go test -count=1 ./internal/testmap/runner/` →
  `ok … 15.954s`.

## Post-Review Changes

### Change Request 1 (2026-10-15 23:20)
- **Requested by user:** two blocking review findings, both confirmed. First,
  `isTestFunc` matched the parameter's selector name `testing` literally, so
  `import tt "testing"` with `func TestAlias(t *tt.T)` escaped discovery.
  Second, `importNames` dropped dot imports, so `. "os/exec"` plus a bare
  `Command(...)` was missed.
- **Changes made:**
  - `isTestFunc(fd, imports)` now resolves the parameter's package through
    the file's import map; the `X` must map to the path `testing`.
  - `parseRunnerPkg` refuses any dot import with an error ("dot import of …,
    which the tripwire cannot resolve: import it by name"). It fails closed
    because both starters (`Command`) and the parameter type (`*T`) would
    arrive unqualified. The real tree has no dot imports.
  - New controls:
    - `alias_test.go`: `TestAlias` with `tt "testing"` must be flagged as
      unguarded, and `TestAliasGuarded` must not be.
    - `decoy_test.go`: `TestDecoy` imports `example.com/notesting` under the
      name `testing`, so it is not a test and must not be flagged.
    - Dot imports of `os/exec` and of `testing` are both refused.
  - Mutants, each caught:
    - matching the literal name `testing`: `TestAlias` goes unflagged and
      `TestDecoy` gets flagged;
    - accepting any `*X.T`: `TestDecoy` gets flagged;
    - removing the dot-import refusal: both dot-import cases return `err <nil>`.
  - Re-verified: the survey still reads `33 guarded, 24 pure, 2 allowlisted`,
    `./ci/preflight.sh` passes, the full runner package passes (`ok … 16.023s`),
    and gofmt and vet are clean.
- **Files affected:** `goengines/internal/testmap/runner/isolation_tripwire_test.go`

### Change Request 2 (2026-10-15 23:45)
- **Requested by user:** two review findings, both confirmed.
  - Blocking: `isTestFunc` still required a selector parameter type, so
    `type T = testing.T` with `func TestTypeAlias(t *T)` was skipped.
  - Low priority, offered as a follow-up but done inline because the effort
    was low: `assert_preflight_precedes_suite` accepted an `if: false` on the
    preflight step.
- **Changes made:**
  - `isTestFunc` now mirrors go test's own discovery rule
    (`cmd/go/internal/load` `isTestFunc`): a Test name and one parameter of
    type `*T` or `*<anything>.T`. In a package that compiles, that parameter
    is `testing.T`, whether through a renamed import or a type alias, so
    nothing go test runs is left unclassified. This replaces Change Request
    1's import-map resolution, which it subsumes.
  - The `decoy_test.go` control is removed, because go test treats `*x.T` as
    a test whatever `x` names. Its replacement is `typealias_test.go`:
    `TestTypeAlias(t *T)` with `type T = testing.T` must be flagged, and
    `TestNotATest(m *testing.M)` must not be.
  - The dot-import refusal is kept for starters.
  - The workflow guard now also asserts that the preflight step has no `if:`.
    A new `PreflightOrderControls` class covers the wired order passing and
    seven bypass shapes being rejected: no preflight, preflight after the
    suite, two preflights, no suite, a skipped preflight, a tolerated
    preflight failure, and a suite run after a failure.
- **Evidence:**
  - Mutants:
    - the selector-only rule is caught (`TestTypeAlias` unflagged);
    - ignoring `T` is caught (`TestNotATest` flagged);
    - the py guard without the preflight `if:` check is caught (the "skipped
      preflight" bypass subtest fails).
  - The reviewer's scenario (`if: false` added to scratch copies of both
    workflows via `AIT_WORKFLOWS_DIR`) now fails both
    `test_preflight_precedes_the_suite` cases.
  - Re-verified:
    - the survey still reads `33 guarded, 24 pure, 2 allowlisted`;
    - the Python guard reports `Ran 13 tests … OK`;
    - the preflight passes;
    - the full runner package passes (`ok … 15.448s`);
    - `gofmt -l .` prints nothing.
- **Files affected:** `goengines/internal/testmap/runner/isolation_tripwire_test.go`, `tests/test_release_workflow_goengines.py`
