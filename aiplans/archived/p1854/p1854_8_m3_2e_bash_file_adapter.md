---
Task: t1854_8_m3_2e_bash_file_adapter.md
Parent Task: aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md
Sibling Tasks: aitasks/t1854/t1854_1_*.md, aitasks/t1854/t1854_2_*.md, aitasks/t1854/t1854_3_*.md, aitasks/t1854/t1854_4_*.md, aitasks/t1854/t1854_5_*.md, aitasks/t1854/t1854_6_*.md, aitasks/t1854/t1854_7_*.md, aitasks/t1854/t1854_9_*.md, aitasks/t1854/t1854_10_*.md, aitasks/t1854/t1854_11_*.md, aitasks/t1854/t1854_12_*.md, aitasks/t1854/t1854_13_*.md, aitasks/t1854/t1854_14_*.md
Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-25 12:20
---

# Plan: t1854_8 — M3.2e bash-file adapter

## Context

Child **M3.2e** of t1854. This task adds the first production builtin runner,
`bash-file`, which is what M10.1 (t1861) uses for the aitasks repository's
`tests/test_*.sh`. It builds on the t1854_6 scaffold (`runner/builtin`:
`Register`, `Env.Supervise`, `Results`, `SplitCommand`), the t1854_7 recursion
guard and the t1854_5 hang guard. The task body is authoritative for the shared
G1–G10 guarantees and the acceptance criteria. This plan replaces the coarse
plan written at the 2026-10-21 re-decomposition.

Automation-first: no step makes a human action a precondition.

## Step 0 — Reality check (done 2026-10-25 at main `eb6baa4c9`)

| # | task body says | repository has | decision |
|---|---|---|---|
| 1 | register with `runner.RegisterBuiltin(name)` | `builtin.Register(builtin.Adapter{Name, Describe, List, Run})`, which calls `runner.RegisterBuiltin` | use `builtin.Register` |
| 2 | the `runner` verb is still a stub; `TestStubsExit64` expects `NOT_IMPLEMENTED:runner` | `cmd/ait-testmap/builtin.go` → `builtin.Main`. `cmd/.../main_test.go TestRunnerVerb` asserts `builtin.Registered()` is **empty** ("M3.2c registers none") | update `TestRunnerVerb`: Linux registers `[bash-file]`, other platforms register none |
| 3 | cleanup is a session sweep, and `setsid()` escapes it | per-start dedicated supervisor (`procsup`, subreaper of its own subtree, ECHILD-proven); `Env.Supervise` → `procsup.Run` | each unit runs as one `Env.Supervise` call, so cleanup after every unit is `procsup.Run`'s proof; `Cleanup` / `SupervisorDied` / `StartErr` / `Containment != supervisor` is a mechanism failure |
| 4 | the hang guard is unexported `isolated` in runner | `hangguard.Isolated(t, limit)`. `tripwirePackages` already has `{internal/testmap/runner/builtin, localStarters: [Main]}` | no tripwire entry needed; every process-starting test begins with `hangguard.Isolated(t, hangLimit)`. Tests that start no process must not reference the adapter value, which reaches `gitx`, a starter |
| 5 | G8/G8a copy in the body (cgroup leaf) | revised: dedicated supervisors; cgroup hardening deferred | follow the revision; nothing to change here |
| 6 | "a package-level tripwire test enforces no direct exec" | no such tripwire exists for adapter files | new lexical tripwire over the package's adapter files (step 4 below) |
| 7 | the aitasks bash tests run as `bash tests/test_x.sh` from the root | verified: 455 `tests/test_*.sh`, each `# Run: bash tests/test_x.sh`, plus **`tests/lib/test_scaffold.sh` (a helper, not a test)** that the default bind `**/test_*.sh` would match | the adapter keeps the default the criteria name. Final Notes and a note to t1861 (M10.1): the aitasks entry should bind `tests/test_*.sh` |
| 8 | "the rule is stated in the `describe` docs" | describe is one YAML document; comments are allowed | describe emits YAML comments stating the inventory rule, what a pass proves, the supported configuration and the logs |
| 9 | inventory = git-visible files | `gitx.ListFiles` runs git with a direct `exec.Command`, outside any supervisor | the adapter runs `git ls-files -z --cached --others --exclude-standard` through `Env.Supervise`, so the inventory step is contained and carries the recursion marker. It keeps gitx's rules: environment from `gitx.Env()` (a pure function), and any stderr output fails the listing |
| 10 | real-tool tests run in CI with `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1` | neither `goengines-check.yml` nor `release.yml` sets it (only `recursion_test.go` reads it; python3 is on ubuntu-latest) | set it on the `go test` step of both workflows, in a separate non-engine commit. t1854_9 owns a pytest edit in `goengines-check.yml`: send it a note |
| 11 | "not registered for production without an integration environment"; darwin pending | darwin has no containment (Main would refuse anyway) | register only on Linux (`bashfile_linux.go` `init`), so on darwin `builtin: bash-file` stays unresolved, i.e. pending |
| 12 | (scaffold doc) "No production adapter is registered by this package" | builtin.go package doc + README rows 27 / 195 say so | named extension: update those three sentences |

Touched files outside `builtin/bashfile*.go`, each a named extension of its
owner:
- `builtin/main_test.go` (t1854_6): two lines in `TestMain` for the
  `__nested_engine` dispatch;
- `builtin/builtin.go`: package doc sentence;
- `cmd/ait-testmap/main_test.go`: the registration assertion;
- `goengines/README.md`;
- the two workflow `env` lines.

### Plan review (2026-10-25): three findings, each verified and adopted

1. **Script argument boundary (blocking).**
   - Appending the bare cwd-relative path lets an option-shaped file name (`--version`, `-tests/…`) be parsed by bash as options. Verified on bash 5.3: `bash --version` exits 0 without running the file; `bash ./--version` exits 7; `bash -tests/test_a.sh` gives `invalid option`.
   - → The operand is `./<path>`, covered by test 13 and mutant (l).
2. **Recursion mutation proof.**
   - `runner/recursion.go` checks context → marker → `ancestor:<pid>`, so dropping the environment would still be refused, through ancestry. The planned mutant would not go red, and clearing the whole environment would also break unrelated test helpers.
   - → Tests 8 and 9 assert `VIA:marker` exactly. Mutants (i) and (i2) filter only `AIT_TESTMAP_ACTIVE`.
3. **Inventory failure proofs.**
   - No planned fixture produced exit-0 stderr or a capped inventory. The recursion shim's non-zero exit is caught by the exit check alone.
   - → Test 14 adds a real git warning (unreadable untracked directory: verified, exit 0 plus a warning) and a deterministic shim warning. Test 15 adds a truncated inventory through `bashFileListMax`. Mutants (c) and (d) are checked against those tests.
4. **Warning test attribution (second review).**
   - `runner.Load` later runs `annot.Source.Annotations` and `gitx.ListFiles(root)`, both of which reject git stderr. So a repository-wide warning fails `Load` whether or not the adapter checks stderr. Verified in `repo.go loadGuarded`.
   - → The real-git variant calls `bashFileList` in-process. The engine variant's warning is confined to the adapter's own `ls-files`, and the assertion requires the `RUNNER_PROTOCOL:<runner>|list|` origin.

No goengines test reads data from outside `goengines/`, which matters for the
aitasks_go migration.

## Implementation steps

### 1. `goengines/internal/testmap/runner/builtin/bashfile.go` (`//go:build unix`)

- `const bashFileName = "bash-file"`, `bashFileDefaultBind = "**/test_*.sh"`,
  `bashFileGrace = time.Second`.
- `bashFileAdapter() Adapter` returns `{Name, Describe: bashFileDescribe, List: bashFileList, Run: bashFileRun}`.
- `bashFileDescribe(*Env) ([]byte, error)` emits the YAML comment block, then:
  ```yaml
  unit: file
  accounting: unit
  discovery: inventory
  timeouts: per_unit
  ```
  The comments state:
  - **inventory:** one unit per git-visible regular file under the runner `cwd` whose root-relative path matches the entry's `bind:` (default `**/test_*.sh`). There is no case accounting.
  - **run:** `<command|bash> ./<cwd-relative path>` in the cwd. The `./` keeps an option-shaped name an operand. Exit 0 → pass; non-zero (or a signal) → fail; over `timeout_s` → timeout.
  - **pass proves** the script exited 0 within its bound under that interpreter. It proves no assertion count and no coverage.
  - **supported:** GNU bash ≥ 4.4 on Linux; darwin and bash 3.2 are pending.
  - **logs:** `unit-<n>.stdout` / `.stderr` in the invocation's report directory.
- `bashFileList(ctx, e, w)`:
  1. `en, err := e.Entry()`. The cwd is `en.Cwd` (`""`/`.` → root); `dir := filepath.Join(e.Root, cwd)`. The bind is `en.Bind`, or `[bashFileDefaultBind]` when empty.
  2. Temp dir (`os.MkdirTemp`, removed on return) for `ls.out` / `ls.err`.
  3. `rr := e.Supervise(ctx, procsup.RunSpec{Path: "git", Args: [ls-files -z --cached --others --exclude-standard], Dir: dir, Env: gitx.Env(), Stdout, Stderr, Timeout: DiscoveryBound(), Grace: bashFileGrace, OutputMax: bashFileListMax})`. `var bashFileListMax int64 = procsup.DefaultOutputMax` is a package variable so a test can force truncation.
  4. Fail with an error, never a partial list, on any of: `StartErr`, `Cleanup`, `SupervisorDied`, `TimedOut`, `Cancelled`, `OutputErr`, `Truncated`, `Exit != 0`, or non-empty stderr. The error message carries the first stderr line, which is how a nested refusal surfaces.
  5. Split the stdout on NUL, then sort and compact. For each cwd-relative path `p`:
     - `rel := path.Join(cwd, p)`;
     - skip unless `doublestar.Match(g, rel)` for some bind glob;
     - skip unless `os.Lstat(filepath.Join(dir, p))` is a regular file (deleted tracked files, symlinks and submodule gitlinks are skipped: a bound file that is skipped surfaces as the engine's UNREGISTERED);
     - `registry.ParseID(rel)` and a control-character check on `p` → otherwise return an error naming the path, fail-closed;
     - write `rel\tfile\t<p>\n`. The lowering is the cwd-relative path to execute.
- `bashFileRun(ctx, e, m, res) int`:
  1. Interpreter `argv`: `SplitCommand(e.Command)` when `e.Command != ""`, else `["bash"]`. An error → stderr `BASHFILE_ERROR:command:<detail>`, return 64.
  2. `e.Entry()` → the cwd and dir as in List. An error → return 3. `m.ReportDir == ""` → return 3.
  3. Exit is 2 if there are no units.
  4. For each unit `i, u`:
     - Validate `u.Lowering`: `registry.CheckPath`, and `path.Join(cwd, u.Lowering) == u.ID`. Also check `u.TimeoutS > 0`. On a mismatch write `Row(u.ID, error, 0, "protocol:<detail>")` and continue (failing).
     - `res.Start(u.ID)`, then `t0 := time.Now()`.
     - **Script operand = `"./" + u.Lowering`**, never the bare path. A cwd-relative path may start with `-` (`registry.CheckPath` allows it; a custom bind can select a root file `--version`, and the default one `-tests/test_a.sh`). Bash would read those as options: verified, `bash --version` exits 0 without running the file and `bash ./--version` exits 7. `./` is interpreter-agnostic, unlike `--`. The script's `$0` is then `./tests/test_x.sh`, which `dirname "$0"` resolves the same way.
     - `rr := e.Supervise(ctx, RunSpec{Path: argv[0], Args: argv[1:]+["./"+u.Lowering], Dir: dir, Stdout: <ReportDir>/unit-%04d.stdout, Stderr: …stderr, Timeout: seconds(u.TimeoutS), Grace: bashFileGrace})`.
     - Mechanism: `StartErr != nil`, `Cleanup != nil`, `SupervisorDied`, `Cancelled`, or `Containment != procsup.Supervisor` → print `BASHFILE_ERROR:<unit>|<detail>` on stderr and **return 3 at once**. The rows already written stand; the engine marks the rest missing / mechanism.
     - Status:
       - `TimedOut` → `timeout`, message `timeout after <timeout_s>s`;
       - `Exit == 0` → `pass`;
       - `Signal != ""` → `fail`, message `signal <sig>`;
       - otherwise → `fail`, message `exit <n>`.
       - If `OutputErr` or `Truncated`, append `; log incomplete: …` or `; log truncated`. The verdict stays the exit: the log is not the evidence.
     - `res.Row(u.ID, status, ms, msg)`; a write error → return 3.
  5. Return 0 if every row is `pass`, else 1 (`lineproto.ExitOK` / `ExitFail`).
- Environment: the script inherits the builtin's environment (`Env: nil`): `AIT_TESTMAP_ROOT` / `RUNNER` / `RUN_ID` / `REPORT_DIR` and, essentially, `AIT_TESTMAP_ACTIVE` (G9). Stdin is `/dev/null` (the procsup launch).

### 2. `bashfile_linux.go` (`//go:build linux`)

`func init() { Register(bashFileAdapter()) }`. This is the only production registration, and it is Linux only.

### 3. Scaffold, cmd and doc touch-ups (named extensions)

- `builtin.go` package doc: "Production adapters register themselves from their own files in this package (bash-file: bashfile_linux.go)."
- `builtin/main_test.go` `TestMain`: after `procsup.MaybeSupervise()`, add `if len(os.Args) == 3 && os.Args[1] == nestedEngineArg { os.Exit(nestedEngine(os.Args[2])) }`. `nestedEngineArg` and `nestedEngine` live in `bashfile_linux_test.go`, modelled on `runner/recursion_main_test.go`: `check` → `runner.Load`, `run` → `runner.Run(All)`. They print the `RecursionError.Line()` / `NESTED_OK:<exit>` / `NESTED_ERROR:…` on stderr.
- `cmd/ait-testmap/main_test.go TestRunnerVerb`: `want := []string{}`; on `runtime.GOOS == "linux"`, `want = []string{"bash-file"}`. Assert `slices.Equal(builtin.Registered(), want)`. Add `runner bash-file describe` exit 0 on Linux, containing `accounting: unit`.

### 4. `bashfile_tripwire_test.go`: no-direct-exec tripwire (pure, unguarded)

- `TestAdapterFilesNoDirectExec`: `go/parser` over every non-test `.go` file of the package except the scaffold (`builtin.go`, `env.go`, `results.go`, `split.go`). The scaffold list is explicit, so future adapter files (pytest*, gotest*, …) are covered automatically. A finding is any of:
  - an import of `os/exec`;
  - a selector `os.StartProcess`, `syscall.{ForkExec,StartProcess,Exec}`, `procsup.{Start,Run}`;
  - any `gitx.<X>` except `gitx.Env`.

  The only way to run a tool is `e.Supervise`.
- `TestAdapterTripwireCatches`: the checker run on inline sources for each forbidden form → reported; a source using only `e.Supervise` and `gitx.Env` → clean.

### 5. `bashfile_linux_test.go`: real-tool tests (each `hangguard.Isolated(t, hangLimit)`)

Helper `requireBash(t)`:
- `exec.LookPath("bash")`;
- `BASH_VERSINFO` ≥ 4.4 and a GNU banner;
- `setsid` on PATH.

Otherwise `t.Skip` (pending), or `t.Fatal` under `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1`. Fixtures use `newRepo` (existing) with `builtin: bash-file` entries. Scripts record pids into `$AIT_TEST_STATE`.

1. `TestBashFileDescribe` (pure, unguarded: calls `bashFileDescribe` only). `runner.ParseDescribe` + `Validate` give unit / inventory / per_unit, and the comments carry the rule text.
2. `TestBashFileInventory`. The fixture holds:
   - tracked `tests/test_a.sh`;
   - untracked `tests/test_u.sh` (git-visible);
   - gitignored `tests/test_ign.sh`;
   - tracked-then-deleted `tests/test_gone.sh`;
   - `tests/helper.sh`;
   - `sub/tests/test_s.sh`;
   - a symlink `tests/test_link.sh`.

   `runner.Load` units = exactly `tests/test_a.sh`, `tests/test_u.sh`, `sub/tests/test_s.sh`, each with lowering = cwd-relative path. A second entry with `cwd: sub` lists `sub/tests/test_s.sh` with lowering `tests/test_s.sh` and runs it from `sub`.
3. `TestBashFilePassFail`: exit 0 → pass; `exit 3` → fail `exit 3`; `kill -SEGV $$` → fail `signal …`; run exit 1, accounting unit, containment supervisor; a `unit-0000.stdout` log exists with the script's output.
4. `TestBashFileTimeoutKillsBackgroundChild`: timeout entry `timeout_s: 1`. The script runs `sleep 300 & echo $! > bg.pid; wait`.
   - The unit is `timeout`. The bg pid is dead when Run returns.
   - The next unit in the same invocation still ran (pass): the runner goes on.
5. `TestBashFileOwnProcessGroupAndSetsid`: one invocation, three units in order:
   - `test_1_pgrp.sh`: `set -m; sleep 300 & echo $! > pg.pid`, then a check that the pgid ≠ the script's, exit 0;
   - `test_2_setsid.sh`: `setsid sleep 300 & …`, or `setsid -f`, writing the daemon pid;
   - `test_3_check.sh`: passes only if both earlier pids are gone (`! kill -0`). This proves cleanup after **every** unit, inside the batch.

   Go also asserts both pids are dead after Run.
6. `TestBashFileStrictMode`:
   - `set -euo pipefail; false | true; exit 0` → fail (`exit 1`);
   - `set -euo pipefail; echo "$UNSET"` → fail;
   - a strict-mode script that succeeds → pass. Proves bash, not sh, semantics.
7. `TestBashFileBatchNoAndBindOwnership`:
   - Two bash-file runners: `slow` with bind `tests/slow/**/test_*.sh`, listed first, and `all` with bind `**/test_*.sh`. `tests/slow/test_x.sh` is owned by `slow`, `tests/test_y.sh` by `all` (both list `test_x`; first matching bind wins).
   - `tests/test_b1.sh` carries `# testmap:batch no`. The RunReport shows `test_b1` alone in its invocation, while `test_y` and `test_b2` share one.
8. `TestBashFileRecursionThroughExecution`:
   - `tests/test_nest_self.sh` runs `cd "$AIT_TESTMAP_ROOT" && "$AIT_TEST_ENGINE" __nested_engine run`. The unit fails `exit <n>`, and its `.stderr` log contains `RUN_ERROR:recursion|` **and exactly `VIA:marker`**. The guard checks context → marker → ancestry, and its ancestry backstop would still refuse a nested entry whose marker was lost (`VIA:ancestor:<pid>`). Asserting the detector is what proves the adapter passes the marker on, rather than relying on the fallback.
   - `tests/test_nest_other.sh` runs the same against a second fixture repository (one passing bash-file test) → pass, with `NESTED_OK:0` in its log.
9. `TestBashFileRecursionThroughDiscovery`:
   - A `git` shim directory is prepended to PATH; the real git path is passed in env. The shim acts only when `$AIT_TESTMAP_RUNNER` is set, `$1 = ls-files` and `$AIT_TEST_SHIM_NEST` is set. It then runs `__nested_engine check` in that directory (disarmed), forwards a failure's stderr and exit, and otherwise `exec`s the real git.
   - Armed at the same repo: `runner.Load` fails with an error containing `RUN_ERROR:recursion|`. The shim's own log (`$AIT_TEST_STATE/discovery.err`, written before forwarding) holds exactly `VIA:marker`, which proves `gitx.Env()` carries the marker into the inventory step.
   - Armed at the second fixture: Load succeeds and the shim logged `NESTED_OK:0`.
10. `TestBashFileCommandOverride`: `command: bash --norc -e` → the argv is used (a script relying on `-e` from the interpreter fails at `false`). `command: bash;x` → the run exits 64 and the invocation is mechanism.
11. `TestBashFileContainmentUnavailable`: under `procsup.SetUnavailableForTesting()`, `Main([bash-file describe])` → exit 3, `CONTAINMENT_UNAVAILABLE:linux`.
12. `TestBashFileAitasksShape` (real repository shape, read-only): build a fixture mimicking `tests/test_claim_id.sh`'s header (`#!/usr/bin/env bash`, `set -e`, sourcing `tests/lib/asserts.sh`-like lib via `$(dirname "$0")`). It runs from the root as `bash tests/test_x.sh` → pass. This proves the cwd-relative invocation resolves `dirname "$0"` as the aitasks tests expect.

13. `TestBashFileOptionShapedPaths`: a root file `--version` (bind `--version`) containing `exit 7`, and `-tests/test_a.sh` (default bind) containing `exit 5`. Both units are `fail` with `exit 7` / `exit 5`, and each wrote a marker file proving its body executed. A unit cannot pass without its script running.
14. `TestBashFileInventoryWarningFailsClosed`: inventory runs that exit 0 but print on stderr must fail the listing. Both variants are **scoped to the adapter**: `runner.Load` cannot serve as the oracle, because after the runners load, `loadGuarded` calls `annot.Source{}.Annotations` and `gitx.ListFiles(root)`. Both reject any git stderr independently, so with the adapter's check removed a whole-repository warning would still fail `Load`.
    - **real git, in-process:** an untracked directory under the cwd made unreadable (`chmod 000`, restored in cleanup); verified, `git ls-files … --others` prints `warning: could not open directory` and exits 0. The test calls `bashFileList(ctx, &Env{Root, Runner}, &buf)` directly and asserts it returns an error carrying the warning and writes no rows. No engine git call is involved. Skipped only when euid is 0, where permissions do not apply, and the skip names that reason.
    - **deterministic, through the engine:** the git shim (step 9's) in `warn` mode prints `warning: synthetic` on stderr, then `exec`s the real git (exit 0). It fires only for a runner process's own `ls-files` (`$AIT_TESTMAP_RUNNER` set, `$1 = ls-files`). The engine's `gitx` calls run `git -C …` from a process without that variable, so they never see the warning. `runner.Load` must fail with an error from the adapter's list operation specifically: `RUNNER_PROTOCOL:<runner>|list|…` containing `warning: synthetic`. Runs everywhere, root included.
15. `TestBashFileInventoryTruncatedFailsClosed`: in-process, `bashFileList(ctx, &Env{Root, Runner}, &buf)` on a fixture with several tests, with `bashFileListMax` set to 8 bytes (restored in `t.Cleanup`). The call returns an error naming truncation and writes no rows.

### 6. README (`goengines/README.md`)

- Layout row 27 and Interfaces row 195: drop "no production adapter is registered" and name the `bash-file` registration (Linux).
- New Interfaces row **`bash-file` builtin (M3.2e)** covering:
  - the classes;
  - the inventory rule;
  - the run line;
  - the status mapping;
  - what a pass proves;
  - the mechanism exits;
  - the logs;
  - what it reads;
  - the supported configuration (GNU bash ≥ 4.4, Linux; darwin and bash 3.2 pending; CI `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1`).

  It also lists the test names.
- A row for the adapter-file no-exec tripwire.

### 7. CI (separate, non-engine commit)

`env: AIT_TESTMAP_REQUIRE_REAL_TOOLS: '1'` on the `go test` step in `.github/workflows/goengines-check.yml` (job `check`) and `release.yml` (job `goengines`). Then run `python -m unittest tests/test_release_workflow_goengines.py` locally (the structure guard).

### 8. Red proofs

Isolated textual mutants, each restored byte-identical (sha256), all expected red:
- (a) no bind filter;
- (b) no regular-file check;
- (c) ls-files stderr ignored → red in both adapter-scoped variants of test 14. Git exits 0 there, so the exit check cannot mask it. The in-process variant has no engine git call. The engine variant's warning reaches only the adapter's `ls-files`, so with the check removed `Load` succeeds. The recursion shim's non-zero exit does not count as this proof;
- (d) Truncated ignored in List → red in test 15;
- (e) `TimedOut` → fail;
- (f) non-zero → pass;
- (g) lowering/id check removed (via a unit test calling `bashFileRun` with a forged manifest);
- (h) `exec.Command` added to bashfile.go (tripwire);
- (i) only `AIT_TESTMAP_ACTIVE` filtered out of the script's environment (everything else kept, so no unrelated failure) → the nested entry is still refused, but `VIA:ancestor:<pid>`, so test 8's `VIA:marker` assertion goes red;
- (i2) the same filter on the inventory's `gitx.Env()` → test 9's `VIA:marker` goes red;
- (l) script operand without `./` → test 13 goes red (`--version` passes without executing; `-tests/…` is rejected as an option);
- (j) `Grace` 0 plus `Timeout` dropped (the timeout test hangs to the hang guard);
- (k) `init` registration removed (cmd TestRunnerVerb).

### 9. Verify

- `./ait engine test` green;
- `GOOS=darwin go vet ./...`;
- release matrix cross-build `./build.sh all`;
- `go test -race -count=3 ./internal/testmap/runner/builtin/`;
- real-binary end-to-end: build `ait-testmap`, run `ait-testmap run --all` on a scratch fixture with a `bash-file` entry → pass/fail rows, `containment: supervisor`.

### Post-phase (risk mitigations)

1. [stress_bashfile_tests_under_load] Run `go test -count=10 ./internal/testmap/runner/builtin/` while a concurrent `go test -p 8 ./...` loads the host.
   - Record the pass count in the Final Notes.
   - Fix any failure before review by replacing a sleep- or poll-based wait with an event wait, or by widening a bound with a stated reason. Never by skipping the test.
   - Repeat until 10/10 pass under load.

## What the adapter reads (for t2082 — repeated in Final Notes)

- **Command line:** `<command: split by SplitCommand | bash> ./<cwd-relative path>`.
- **Cwd:** the entry's `cwd` (default the root).
- **Inventory:** `git ls-files -z --cached --others --exclude-standard` in the cwd, with the `gitx.Env()` environment.
- **Config:** `runners.yaml` (`cwd`, `bind`, `command`). There are no tool config flags. The script itself, and whatever it sources, are opaque to the engine.

## Verification (= acceptance criteria)

As listed in the task body. Each one maps to a test in step 5, or to the tripwire in step 4.

## Risk

### Code-health risk: medium
- Process-heavy real-tool tests (nested engines up to 4 levels, 1 s timeouts, pid-liveness checks) may flake under CI or local parallel load · severity: medium (residual — addressed by inline post-phase stress_bashfile_tests_under_load) · → mitigation: inline post-phase stress_bashfile_tests_under_load
- `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1` in CI turns a missing tool (bash ≥ 4.4, setsid, python3) on the runner image into a hard failure · severity: low · → mitigation: none (intended G10 behaviour; ubuntu-latest has all three)

### Goal-achievement risk: low
- None identified.

### Planned mitigations
- timing: post-phase | name: stress_bashfile_tests_under_load | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health flakiness of the real-tool tests | desc: run the builtin package tests 10× under concurrent full-suite load and fix any flake with event waits

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9: archival on the
current branch, with no merge.

## Final Implementation Notes
- **Actual work done:**
  - `runner/builtin/bashfile.go` (unix): the `bash-file` adapter.
    - Describe: unit / inventory / per_unit, with the rules as YAML comments.
    - List: supervised `git ls-files` inventory, bind filter, regular files only, fail-closed on any stderr, non-zero exit, timeout or truncation.
    - Run: `<command|bash> ./<lowering>` per unit under `timeout_s`, start + result rows, per-unit logs, exit 3 on unproven containment.
  - `bashfile_linux.go`: Linux-only `init` registration.
  - `bashfile_tripwire_test.go`: the adapter-file no-direct-exec tripwire, generic over every non-scaffold file of the package.
  - `bashfile_linux_test.go`: 17 tests. 15 are real-tool tests (`hangguard.Isolated`, `requireBash`), plus the pure `TestBashFileDescribe`, `TestBashFileUnitCheck` and `TestBashFileRunRefusesForgedUnit`.
  - Named extensions:
    - `builtin.go` package doc;
    - `main_test.go` `__nested_engine` dispatch;
    - `cmd/ait-testmap/main_test.go` `TestRunnerVerb` (Linux registers `[bash-file]`, plus `runner bash-file describe`);
    - `goengines/README.md` (rows 119 and `runner <name>`, plus the new `bash-file` builtin and adapter-file tripwire rows);
    - `AIT_TESTMAP_REQUIRE_REAL_TOOLS: '1'` on the legacy-mode `go test` step of `goengines-check.yml` and `release.yml`.
- **Deviations from plan:**
  - Bash-file tests use their own `bashHangLimit = 120s`. Under `-race` on a loaded host, `TestBashFileInventory` measured 28.3 s against the package's 30 s `hangLimit`, because each test chains two or three supervised engine loads of the race-instrumented binary. A hang still fails at that bound.
  - `bashEntry` omits its default `timeout_s` when an extra line sets one (duplicate YAML key).
- **Issues encountered:**
  - `go test -race -count=3` exceeded go test's default 10 min timeout. It was not failing: the race pass alone takes ~212 s on a loaded box. Rerun with `-timeout 45m`.
  - The other session's t2138 (two-mode CI) held uncommitted hunks in `goengines/README.md` and both workflows. Per the shared-file gate, those files were edited only after t2138 committed `309e0b8c6`.
- **Key decisions:**
  - The inventory runs git through `Env.Supervise`, not `gitx.ListFiles`, so discovery is contained and carries the recursion marker. gitx's stderr rule is kept.
  - The script operand is `./<path>`: verified on bash 5.3, `bash --version` exits 0 without running a file named `--version`.
  - Registration is Linux only (G10: no integration environment elsewhere), so darwin's `builtin: bash-file` is unresolved, i.e. pending.
  - The log is never the evidence. A lost or truncated log only annotates the message.
- **What the adapter reads (for t2082):**
  - **Command line:** `<command: split by SplitCommand | bash> ./<cwd-relative path>`.
  - **Cwd:** the entry's `cwd` (default the root).
  - **Inventory:** `git ls-files -z --cached --others --exclude-standard` in the cwd, with the `gitx.Env()` environment, so git's index and ignore rules are inputs.
  - **Config:** `runners.yaml` `cwd`, `bind`, `command`. There are no tool config flags. Script contents and whatever they source are opaque.
- **Red proofs:** 13 isolated mutants, each applied to a scratch copy of `goengines/` (never the shared tree), sha256-restored, the copy diffed identical afterwards. All red:
  - (a) no bind filter;
  - (b) no regular-file check (`fi == nil` form, so it is not a compile-error "red");
  - (c) ls-files stderr ignored → both adapter-scoped warning variants;
  - (d) Truncated ignored;
  - (e) timeout → fail;
  - (f) non-zero → pass;
  - (g) lowering check removed;
  - (h) `os/exec` imported (tripwire);
  - (m) the dot-import refusal disabled → `TestAdapterTripwireCatches` (`dot syscall`, `dot os`, `dot innocuous` not caught; see Post-Review Changes);
  - (i) `AIT_TESTMAP_ACTIVE` filtered from the script env → `VIA:ancestor:<pid>`, so the `VIA:marker` assertion fails;
  - (i2) the same filter on the inventory env;
  - (j) no per-unit timeout → HANG at the hang guard;
  - (l) operand without `./` → `--version` passes unrun;
  - (k) registration removed → `TestRunnerVerb`.
- **Verification:**
  - `./ait engine test` rc 0 (re-run on the final tree, after the README and CI edits);
  - `GOOS=darwin go vet ./...` ok;
  - `./build.sh all` with sha256 ok;
  - builtin package green with `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1`, no skips;
  - `-race -count=1` green (212 s); `-race -count=3 -timeout 45m` green (634 s, 0 `DATA RACE`);
  - `python -m unittest tests/test_release_workflow_goengines.py` OK (22 tests);
  - real-binary end-to-end: `ait-testmap run --all` on a scratch repository (`tests/test_ok.sh`, and `tests/test_bad.sh` leaving a `setsid` daemon, exit 4). Result `UNIT … fail`, `UNIT … pass`, `RUN_ACCOUNTING:2|0|2|0|0`, rc 1, `containment: supervisor`, the daemon gone, `unit-000{0,1}.std{out,err}` logs present.
- **Post-phase [stress_bashfile_tests_under_load]:** `go test -count=10` of the builtin package while a full `go test -count=1 -p 8 ./...` ran concurrently gave **10/10 pass** (stress rc 0, load rc 0). No flake fixes were needed beyond the `bashHangLimit` bound above.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - The adapter-file tripwire covers every new non-test file in `runner/builtin` automatically. Run tools only through `e.Supervise`; `gitx.Env()` is the one allowed gitx name.
  - `TestRunnerVerb` pins the registered set: add your adapter to `want` (under its platform condition) when you register it.
  - `main_test.go` now dispatches `__nested_engine check|run` (in `bashfile_linux_test.go`), so recursion tests can reuse it. Assert `VIA:marker`, not just `RUN_ERROR:recursion`: the ancestry backstop also refuses a nested entry whose marker was dropped.
  - Do not use `runner.Load` as the oracle for an adapter's own git-stderr handling: `loadGuarded` re-runs `annot` / `gitx.ListFiles`, which reject stderr themselves. Call the adapter's list in-process, or confine the fault to the adapter's own call.
  - Real-tool tests that chain engine loads need a hang limit above the package's 30 s under `-race`.
  - CI now sets `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1` on the legacy-mode `go test` steps. A tool your real-tool tests need must be on ubuntu-latest, or installed by the workflow (t1854_9: pytest).
  - For M10.1 (t1861): bind the aitasks entry to `tests/test_*.sh`. The default `**/test_*.sh` also matches the helper `tests/lib/test_scaffold.sh`.

## Post-Review Changes

### Change Request 1 (2026-10-25 11:20)
- **Requested by user:** the adapter-file tripwire missed dot imports. `directExecFindings` recorded `local["."]` but examined only `ast.SelectorExpr`, so `import . "syscall"` + `ForkExec(…)` and `import . "os"` + `StartProcess` produced zero findings (verified CONFIRMED by the reviewer). Requested: reject dot imports, following the hang-guard parser's rule, and cover it.
- **Changes made:**
  - `directExecFindings` refuses every dot import, whatever the package, with `dot import of <path>, which the tripwire cannot resolve: import it by name`. This mirrors `hangguard/tripwire_test.go`, which refuses dot imports outright.
  - `TestAdapterTripwireCatches` gains `dot syscall`, `dot os` and `dot innocuous`.
  - The README adapter-file tripwire row states the rule.
  - Red proof (m): on the scratch copy, the refusal disabled → all three cases "not caught", which is the reported gap; the copy is restored and diffed identical.
- **Files affected:** `goengines/internal/testmap/runner/builtin/bashfile_tripwire_test.go`, `goengines/README.md`.
