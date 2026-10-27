---
Task: t1854_12_m3_2i_suite_aggregate_adapter.md
Parent Task: aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md
Sibling Tasks: aitasks/t1854/t1854_1_*.md, aitasks/t1854/t1854_2_*.md, aitasks/t1854/t1854_3_*.md, aitasks/t1854/t1854_4_*.md, aitasks/t1854/t1854_5_*.md, aitasks/t1854/t1854_6_*.md, aitasks/t1854/t1854_7_*.md, aitasks/t1854/t1854_8_*.md, aitasks/t1854/t1854_9_*.md, aitasks/t1854/t1854_10_*.md, aitasks/t1854/t1854_11_*.md, aitasks/t1854/t1854_13_*.md, aitasks/t1854/t1854_14_*.md
Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-27 07:46
---

# Plan: t1854_12 — M3.2i `suite` aggregate adapter

## Context

Child **M3.2i** of t1854 (wave 3). It adds the production builtin `suite`. The
builtin wraps any command as **one aggregate unit**. Examples: the
pre-onboarding `test_command` that t1857's `detect` snapshots into a
`full: true` suite runner, thinking_app's `verify-active`, and aitasks_go's
`go test ./...`. It provides the carrier that t1859_4 (M8.4
`fallback_command`), t1854_14, M6.1 `detect` and M10.5 build on.

It builds on:
- the t1854_6 scaffold (`runner/builtin`: `Register`, `Env.Supervise`,
  `Results`);
- the t1854_7 runtime recursion guard;
- the t1854_5 hang guard;
- the t1854_2 evidence contract (aggregate accounting, `cases:refused`, G7).

There is no per-test child evidence here: that is t1854_14. This plan replaces
the coarse plan from the 2026-10-21 re-decomposition, and the task body is
authoritative. Automation-first: no step makes a human action a precondition.

## Step 0 — Reality check (done 2026-10-26 at main `65c887ba9`)

| # | task body says | repository has | decision |
|---|---|---|---|
| 1 | register with `runner.RegisterBuiltin` | `builtin.Register(builtin.Adapter{…})`, Linux-only `init` files (`bashfile_linux.go`, `pytest_linux.go`) | `suite_linux.go` `init() { Register(suiteAdapter()) }`; elsewhere `builtin: suite` stays unresolved (pending, G10) |
| 2 | `runner` verb is a stub | `cmd/ait-testmap/main_test.go TestRunnerVerb` pins `[bash-file pytest]` on Linux | named extension: `[bash-file pytest suite]`, plus `runner suite describe` with `AIT_TESTMAP_COMMAND` set |
| 3 | run "as `sh -c` (the same trust as `test_command`)" | the framework runs `test_command` with **`bash -c`** (`.aitask-scripts/lib/gate_verifier_lib.sh:310`). `/bin/sh` is dash on ubuntu-latest (CI), bash here | **user decision (2026-10-26): `bash -c`**. A snapshotted `test_command` then keeps its semantics (`[[ ]]`, `pipefail`, `source`). The support claim becomes GNU bash ≥ 4.4 on Linux (`requireBash` is reused). Amend the task-body criterion (framework commit); note t1857 and t1859_4 |
| 4 | `command:` required; `describe` refuses without it | `Runner.command` sets `AIT_TESTMAP_COMMAND` for **every** builtin verb, describe included (`repo.go:142`) | `suiteDescribe` reads `e.Command`; empty → error `command: is required` |
| 5 | `SUITE_RECURSION:<runner>\|<word>` from describe | `Main`'s `BUILTIN_ERROR:<name>\|<verb>\|<detail>` runs `oneLine` over the detail, turning `\|` into a space. The engine surfaces only the **first** stderr line (`exitText`: `exit 3: <StderrFirst>`) | describe writes `SUITE_RECURSION:<runner>\|<word>` to stderr **itself, first**, then returns an error. The Load error is then `RUNNER_PROTOCOL:<runner>\|describe\|exit 3: SUITE_RECURSION:<runner>\|<word>`, intact |
| 6 | the `aitask_test.sh` literal carries `// invariant5-ok: named only to refuse it` | `goengines/guards_test.go` exempts a line by that regexp | as stated |
| 7 | `timeouts: none` (engine singleton) | `assign` sets `BatchNo` for `timeouts: none`; `Deadline` = min(`timeout_s`, `max_invocation_s`); on kill `AttributeKill(none)` → `timeout`. A runner-reported `timeout` under none is `timeout_not_per_unit` (`results.go`). Start rows are accepted in any mode | the adapter **never reports timeout**; the engine's kill (outer supervisor, grace 0) ends the builtin and the whole contained tree. Its own `Timeout` is a **backstop**: `DeadlineS + 10 s` (pytest's `pytestDeadlineSlack` precedent), so the engine always wins the race. If the backstop fires → mechanism (exit 3). A start row is written (harmless; records `Started`) |
| 8 | unit id `aitestmap/runners.yaml#<name>`, kind `suite`; "no member drift" | `ParseID` → `{Path: aitestmap/runners.yaml, Member: <name>}`. Runner names (`^[A-Za-z0-9][A-Za-z0-9._-]*$`) never hold `# @ \| /` or whitespace, so they are always valid fragments. `BuildScanned` flags member drift only for files with `testmap:unit` blocks, and `runners.yaml` has none. `annot` claims no YAML language | row `aitestmap/runners.yaml#<name>\tsuite\t<name>` (lowering = runner name). A defensive `registry.ParseID` round-trip check stays. A test asserts `BuildScanned` reports no findings |
| 9 | (unstated) ownership of that id | `ownerOf`: annotation > **first runner whose `bind:` matches the path** > sole lister; `assign` drops a unit whose owner does not list it **silently**, as it does an `exclude:`d path | fail closed at **list**, never a silently dropped suite: refuse when (a) the suite entry itself has `bind:` (meaningless for a suite: it would claim later runners' files and make every bound file UNREGISTERED), (b) another runner's `bind:` matches `aitestmap/runners.yaml`, or (c) `config.yaml` `exclude:` matches it. (a) and (b) come from `runner.LoadConfig`, (c) from `registry.LoadConfig`, both pure file reads |
| 10 | discovery-side recursion test (common criterion) | the suite's inventory is a pure read of `runners.yaml` / `config.yaml`, so List starts **no process**; `Load`-level nesting is t1854_7's guard (already tested) | no discovery-side nested call can exist. The test instead proves that `describe`/`list` (a whole `runner.Load`) **never execute** `command:` or `fallback_command:` (marker files absent). The execution-side recursion test is as specified |
| 11 | hang guard; tripwire | `tripwirePackages` already lists `internal/testmap/runner/builtin`; the adapter-file no-direct-exec tripwire (`bashfile_tripwire_test.go`) covers every non-scaffold file | no tripwire entry needed. Every process-starting test begins with `hangguard.Isolated(t, bashHangLimit)` |
| 12 | output "to a log in the invocation directory, never to the builtin's capped stdout" | engine caps runner stdout at 64 MiB (`exec_unix.go outputMax`, overflow = kill → mechanism); procsup caps each log at `DefaultOutputMax` = 64 MiB → `Truncated` | logs `unit-0000.stdout` / `.stderr` in `m.ReportDir` (the existing `unitLog` test helper reads them). A test writes past 64 MiB: the unit still passes with `log truncated`, and there is no mechanism cause, which proves the output never reached the builtin's stdout |
| 13 | `fallback_command:` stays M3.1's, only on `unit: suite`; not run here | `checkDescribed` enforces `unit: suite` | describe declares `unit: suite`; the adapter never reads `FallbackCommand`. A test proves it is never run |
| 14 | G7 children refused until t1854_14 | `Validate` refuses unregistered `children:`; `full: true` without children is valid (D6 override) | the adapter writes no child rows. Tests: a `full: true` suite with a `subsumed_by` bash-file runner → its units counted `unaccounted`; `children: junit` → `RUNNER_INVALID` |
| 15 | (unstated) the fixed classes must hold | **Plan review (2026-10-27), verified:** `loadRunner` merges `Entry.Overrides` into the adapter's describe **before** `Validate`, and `Validate` accepts any class combination but `cases` + `per_unit`. So `builtin: suite` + `accounting: unit` would report unit accounting. `cost/eligibility.go decide` keys its `opaque:aggregate` rejection on the **effective** `Describe.Accounting`, and its `u.Kind == "suite"` check comes only **after** the `len(rec.Modified) == 0 → clean` return, so that aggregate command **would anchor** on a clean tree. Separately, `timeouts: per_unit` (or `batch`) moves the engine deadline to `max_invocation_s` (or `batch_timeout_s`), while the adapter enforces no per-unit bound, so the command could run past `timeout_s` | the adapter enforces its **fixed contract**. An entry override of `unit`, `accounting`, `discovery` or `timeouts` to any value other than the adapter's own (`suite` / `aggregate` / `inventory` / `none`) is refused at **list**, so `runner.Load` fails before any unit exists (an override equal to the fixed value is redundant and accepted). `run` re-checks the manifest's effective `timeouts` / `accounting` (defence in depth: nothing is run). The other declarations were assessed key by key (table below); they stay overridable |
| 16 | aitasks_go note: keep engine commits separate; record data outside `goengines/` | no suite test reads outside `goengines/` | engine commit (`goengines/**`) and framework commit (task-body amendment) are separate |

### Override assessment (Step 0 #15): every describe key against the suite's contract

| key | overridable? | why |
|---|---|---|
| `unit` | **no** (fixed `suite`) | the list rows are kind `suite`, `fallback_command` is valid only on `unit: suite`, and eligibility's suite rule is the second line of defence |
| `accounting` | **no** (fixed `aggregate`) | `unit` would let the command anchor (eligibility above); `cases` would demand case identities the suite never lists, which is t1854_14's contract |
| `discovery` | **no** (fixed `inventory`) | the unit rule is an explicit inventory. `native` would claim a collector; `candidates` would print a false `DISCOVERY:` completeness warning |
| `timeouts` | **no** (fixed `none`) | the adapter enforces no per-unit bound (Step 0 #7). Under `per_unit` / `batch` the command could run past `timeout_s` |
| `full`, `children` | yes | D6: a generic suite cannot know them. `children` still needs a registered reporting contract (G7, `Validate`) |
| `needs` | yes | resources are the entry's to declare |
| `batch` | yes (no effect) | `timeouts: none` already forces a singleton (`assign`) |
| `group_by` | yes | one unit per runner. A regex that does not match the id path already fails `Load` (`GroupOf`) |
| `filter_scope` | yes | one unit, so a whole-run filter selects the same set; eligibility is already opaque |
| `artifact_glob` | yes | the list rows carry no artifact; the globs only feed the lister's UNREGISTERED inputs, as for any runner |
| `axis`, `token_format` (M2.4 ext) | yes | the suite lists no variants, so an axis has nothing to judge, as for any runner naming one |

Touched files outside `builtin/suite*.go`, each a named extension of its owner:
- `cmd/ait-testmap/main_test.go` (`TestRunnerVerb`);
- `builtin/builtin.go` package doc (registered adapters list);
- `goengines/README.md`;
- the task body (framework commit).

## Design

### `goengines/internal/testmap/runner/builtin/suite.go` (`//go:build unix`)

```go
const (
    suiteName  = "suite"
    suiteGrace = time.Second
    // suiteDeadlineSlack keeps the backstop past the engine's deadline: the
    // engine's kill must win, attributing `timeout` (timeouts: none).
    suiteDeadlineSlack = 10 * time.Second
)
```

- `suiteDescribeDoc` holds YAML comments, then `unit: suite`,
  `accounting: aggregate`, `discovery: inventory` and `timeouts: none`. The
  comments state:
  - the unit rule (one per runner entry, id `aitestmap/runners.yaml#<name>`,
    no `bind:`);
  - the run line (`bash -c <command:>` in the cwd, one supervised process,
    bounded by the engine as a singleton invocation);
  - the status mapping;
  - **a pass proves only that the command exited 0; no individual test result
    is ever inferred, and an aggregate never anchors**;
  - `fallback_command:` is carried, never run here;
  - `full: true` may be set by the entry, but child rows need a registered
    reporting contract (t1854_14), and the command must not write
    `cases.jsonl`;
  - the recursion diagnostic;
  - the logs;
  - supported: GNU bash ≥ 4.4 on Linux; darwin pending.
- `suiteAdapter() Adapter{Name: suiteName, Describe: suiteDescribe, List: suiteList, Run: suiteRun}`.
- `suiteCommand(e *Env) (string, error)` is shared by all three verbs:
  - `strings.TrimSpace(e.Command) == ""` → `errors.New("command: is required (the command the suite runs)")`;
  - `suiteRecursionWord(e.Command)` hit → `fmt.Fprintf(os.Stderr, "SUITE_RECURSION:%s|%s\n", e.Runner, word)`, then return error `suite recursion: <word>`.
- `suiteRecursionWord(cmd string) (string, bool)`, a pure function:
  - Tokenize: split on whitespace and the shell operators `; & | ( ) < > \``
    and `$(`; trim surrounding `'"` from each word; drop empty words.
  - Each word is matched by `path.Base`, and the original word is returned.
    Hits:
    - base `ait` followed by `test`;
    - base `ait` followed by `testmap` then `test` or `run`;
    - base `ait-testmap` followed by `test` or `run`;
    - base `aitask_test.sh` anywhere (`// invariant5-ok: named only to refuse it`).
  - It is a deliberately conservative early diagnostic: a false positive is a
    loud refusal, never a silent pass. The runtime guard is the protection.
- `suiteDescribe(e)`: `suiteCommand(e)`, then the doc.
- `suiteList(ctx, e, w)`:
  1. `suiteCommand(e)`.
  2. `cfg, err := runner.LoadConfig(e.Root)`, then find the entry named
     `e.Runner`. **Fixed contract first:** `suiteFixedOverride(en)` refuses
     an `en.OverrideKeys[k]` whose `en.Overrides` value differs from the
     adapter's own, for k in `unit` / `accounting` / `discovery` /
     `timeouts`. The fixed values come from one table, `suiteFixed`, which
     also generates the describe keys, so the two cannot drift. The error
     is `runners.yaml overrides <k>: <v>, but a suite's <k> is fixed at
     <fixed> (overridable: full, children, needs, batch, group_by,
     filter_scope, artifact_glob, axis, token_format)`. As a belt check,
     `e.Accounting` (the effective class the engine passes to list) must be
     `aggregate`. Then refuse with an error if:
     - the entry has `bind:` → `a suite runner takes no bind: (its one unit is aitestmap/runners.yaml#<name>)`;
     - another entry's `bind:` matches `runner.RunnersPath` (`doublestar.Match`) → `runner <other>'s bind: <g> matches aitestmap/runners.yaml and would own the suite unit`.
  3. `rcfg, err := registry.LoadConfig(e.Root)`; `rcfg.Excluded(runner.RunnersPath)` → `exclude: drops aitestmap/runners.yaml, so the suite unit would never run`.
  4. `id := runner.RunnersPath + "#" + e.Runner`, checked by `registry.ParseID(id)` with `String() == id`.
  5. Write `id\tsuite\t<e.Runner>\n`.
- `suiteRun(ctx, e, m, res) int`:
  1. `cmd, err := suiteCommand(e)`; an error → stderr `SUITE_ERROR:command:<detail>`, return 64 (`lineproto.ExitUsage`).
  2. `en, err := e.Entry()`. If err or `m.ReportDir == ""` → `SUITE_ERROR:setup:…`, return 3. `_, dir := entryCwd(e, en)` (reuses `inventory.go`).
  3. `len(m.Units) == 0` → return 2.
  4. Unit check (`suiteUnitCheck(e.Runner, m)`). Fail when the manifest's effective `m.Timeouts` is not `none` or `m.Accounting` is not `aggregate` (the fixed contract again, defence in depth behind List's refusal), there is more than one unit (`timeouts: none` is a singleton), the id is not `aitestmap/runners.yaml#<runner>`, or the lowering is not `<runner>`. On failure, write `Row(id, error, 0, "protocol:<detail>")` for **every** unit and return 1. Nothing is run.
  5. `res.Start(id)`; `t0 := time.Now()`.
  6. `rr := e.Supervise(ctx, procsup.RunSpec{Path: "bash", Args: []string{"-c", cmd}, Dir: dir, Stdout: <ReportDir>/unit-0000.stdout, Stderr: …stderr, Timeout: backstop, Grace: suiteGrace})`:
     - `Env` nil: the command inherits `AIT_TESTMAP_ROOT` / `RUNNER` / `RUN_ID` / `REPORT_DIR` / `ACTIVE` (G9 marker);
     - stdin is `/dev/null`;
     - `backstop` = `DeadlineS*s + suiteDeadlineSlack` when `DeadlineS > 0`, else 0.
  7. Mechanism: `StartErr`, `SupervisorDied`, `Cleanup`, `Cancelled`, `Containment != Supervisor`, or `TimedOut` (the backstop) → `SUITE_ERROR:<id>|<toolFailure detail>`, return 3. The engine marks the unit missing or timeout.
  8. Status:
     - `Exit == 0` → `pass`;
     - `Signal != ""` → `fail`, `signal <sig>`;
     - otherwise → `fail`, `exit <n>`.

     If `OutputErr` or `Truncated`, append `; log incomplete: …` or `; log truncated` (the bash-file wording). The log is never the evidence.
  9. `res.Row(id, status, ms, msg)`; a write error → 3. Return 0 on pass, else 1.

### `suite_linux.go` (`//go:build linux`)

`func init() { Register(suiteAdapter()) }`, with the G10 comment (GNU bash on Linux).

## Implementation steps

1. **Tests first for the refusals.** Write `suite_linux_test.go` (below), then
   `suite.go` + `suite_linux.go`, then make the tests green.
2. **Named extensions:**
   - `builtin.go` package doc: "bash-file (bashfile_linux.go), pytest (pytest_linux.go), suite (suite_linux.go)";
   - `cmd/ait-testmap/main_test.go TestRunnerVerb`: `want = []string{"bash-file", "pytest", "suite"}`, plus `t.Setenv("AIT_TESTMAP_COMMAND", "true")` → `runner suite describe` exit 0 containing `accounting: aggregate\n` and `discovery: inventory\n`, and with it empty → exit 3 `BUILTIN_ERROR:suite|describe|command: is required…`. Check first whether `call` runs in-process (`t.Setenv` reaches `Main`); if it spawns, pass the env through its mechanism.
3. **Tests**, in `goengines/internal/testmap/runner/builtin/suite_linux_test.go`. Every process-starting test begins with `hangguard.Isolated(t, bashHangLimit)` and calls `requireBash` (reused). Entries use a `suiteEntry(name, command string, extra ...string)` helper.
   1. `TestSuiteDescribe` (pure). It covers:
      - `Env{Command: "make test"}` → `ParseDescribe` + `Validate`: suite / aggregate / inventory / none;
      - the docs state `bash -c`, `exited 0`, `never inferred`, `aitestmap/runners.yaml#<name>`, `GNU bash >= 4.4 on linux`, `darwin … pending`, `unit-<n>.stdout`;
      - `Command: ""` and `"  "` → error naming `command:`.
   2. `TestSuiteRecursionWord` (pure table).
      - Hits:
        - `./ait test`;
        - `ait test --all`;
        - `/x/ait testmap run`;
        - `ait testmap test`;
        - `ait-testmap test`;
        - `../bin/ait-testmap run --all`;
        - `bash .aitask-scripts/aitask_test.sh`;
        - `make && ./ait test`;
        - `cd x;ait test`;
        - `(ait test)`;
        - `"./ait" test`;
        - `$(./ait test)`.

        Each returns the expected word.
      - Misses:
        - `go test ./...`;
        - `pytest -q`;
        - `./gradlew test`;
        - `ait testmap check`;
        - `ait-testmap scan`;
        - `./ait board`;
        - `bash tests/aitask_test.sh.bak`;
        - `waittest`.
   3. `TestSuiteRecursionDiagnostic`:
      - `Main([suite describe])` with `AIT_TESTMAP_COMMAND=./ait test` and `AIT_TESTMAP_RUNNER=full` → exit 3, first stderr line exactly `SUITE_RECURSION:full|./ait`;
      - through the engine, `runner.Load` → error containing `RUNNER_PROTOCOL:full|describe|exit 3: SUITE_RECURSION:full|./ait`.
   4. `TestSuiteInventory`. Two suite runners, `full` (with `fallback_command: touch "$AIT_TEST_STATE/fb"`) and `sub` (`cwd: sub`), each with a command that touches a marker. After `runner.Load`:
      - units are exactly `aitestmap/runners.yaml#full` and `…#sub`, kind `suite`, lowering = name, `BatchNo` true;
      - `registry.BuildScanned(rcfg, anns, repo.Listings())` returns no findings (no member drift);
      - **neither marker nor `fb` exists**: describe and list never run the command, and nothing runs the fallback (Step 0 #10, #13).
   5. `TestSuiteInventoryRefusals`. Each case → a `runner.Load` error naming the cause:
      - (a) the suite entry has `bind:`;
      - (b) a bash-file runner listed **before** it with `bind: ['aitestmap/**']`;
      - (c) `config.yaml` `exclude: ['aitestmap/**']`;
      - (d) no `command:` → `command: is required`.
   5b. `TestSuiteFixedContractOverrides` (engine-level, `runner.Load`).
      - **Refused**, each naming the key and its fixed value; no unit exists:
        - `accounting: unit`;
        - `accounting: cases`;
        - `timeouts: per_unit`;
        - `timeouts: batch` (with `batch_timeout_s: 5`, so the refusal is the adapter's, not `checkTimeouts`');
        - `unit: file`;
        - `discovery: native`;
        - `discovery: candidates`.
      - **Accepted**, each loading exactly one `kind suite` unit whose effective describe is still aggregate / inventory / none:
        - the redundant `accounting: aggregate` + `timeouts: none`;
        - `full: true`;
        - `needs: [gpu]`;
        - `batch: false`;
        - `group_by: dir`;
        - `filter_scope: whole_run`.
      - The refusal assertions check **that** Load fails and that the error names the key (`accounting`, `timeouts`, …), not which layer's wording produced it. So a mutant that leaves a case refused by another layer stays green for that case, and the mutation table below says which cases each mutant must turn red.
      - **Belt layer, in-process:** `suiteList(ctx, &Env{Root, Runner, Command, Accounting: "unit"}, &buf)` on a fixture whose entry has **no** override → refused naming the effective accounting, no rows. This is the only case where the belt check is the sole guard, so it gets its own case.
      - **Anchor regression check (separate; no mutant here claims to break it):** run the accepted `full: true` fixture on a **clean tree** (`runner.Run`), then `cost.Rows(ctx, rep)`. This is the exported entry point `cost/eligibility_test.go judgedIDs` uses; `cost` does not import `builtin`, so there is no cycle. The suite's `"row":"result"` line must have `anchor: false`, `anchor_reason: "opaque:aggregate"` and `accounting: "aggregate"`. It pins the end-to-end outcome the fixed contract protects. The eligibility rule it rests on is t1854_4's, and its mutants belong to that package.
   6. `TestSuitePassFail`. Runners `ok` (`echo out; echo err >&2; exit 0`), `bad` (`exit 3`) and `sig` (`kill -USR1 $$`) give:
      - pass, fail `exit 3`, fail `signal `;
      - each record has no cause, `Accounting aggregate`, `Discovery inventory`, `Containment supervisor`;
      - `rep.Accounting.Aggregate == 3`, `Cases == 0`, `Unit == 0`;
      - the `ok` logs are `out\n` / `err\n`.
   7. `TestSuiteBashSemantics`. Expected results:
      - `[[ 1 == 1 ]] && [ -n "$BASH_VERSION" ] && ! shopt -qo posix` → pass. Bash, not in POSIX mode: bash invoked as `sh` (this host's `/bin/sh`) sets `posix`, so the check discriminates here as well as on dash hosts;
      - `set -o pipefail; false | true` → fail `exit 1` (bash semantics; dash rejects `pipefail`).
   8. `TestSuiteRunsInCwd`. The `cwd: sub` runner writes `pwd -P` and passes; the value is `<repo>/sub`.
   9. `TestSuiteTimeoutKillsSetsidDescendant`. The entry has `timeout_s: 1`, and the command is `setsid sh -c 'echo $$ > "$AIT_TEST_STATE/sid.tmp"; mv … sid.pid; exec sleep 300' & sleep 300`. Expected:
      - status `timeout` (engine-attributed);
      - `Started` true;
      - the record shows a kill at bound `unit`;
      - the setsid daemon's pid is **not alive** when `Run` returns (contained: it reparents to the subreapers, and the engine's kill reaches it).
   10. `TestSuiteOutputPastCap`. The command is `head -c $((64*1024*1024 + 4096)) /dev/zero; echo tail >&2; exit 0`. Expected:
       - **pass** with message `log truncated`;
       - no cause (neither mechanism nor `output exceeds`);
       - the stdout log is exactly `procsup.DefaultOutputMax` bytes;
       - the stderr log is `tail\n`.
   11. `TestSuiteRecursionThroughExecution`:
       - `tests/hidden.sh` runs `cd "$AIT_TESTMAP_ROOT" && exec "$AIT_TEST_ENGINE" __nested_engine run`;
       - the `self` suite command is `bash tests/hidden.sh`, whose words name no front, so the diagnostic passes it;
       - result: `fail` `exit 3`, and the stderr log contains `RUN_ERROR:recursion|` and **exactly** the line `VIA:marker`;
       - the `other` suite command runs the same script against a second fixture repository (`AIT_TEST_OTHER`, one passing suite) → pass, log `NESTED_OK:0`.
   12. `TestSuiteFullWithoutChildren`:
       - `full` suite with `full: true` (`exit 0`), plus a bash-file runner `b` with `subsumed_by: full` and two tests. `run --all` → the suite passes, `rep.Accounting.Unaccounted == 2`, and there are no child rows;
       - a second fixture with `children: junit` → Load `RUNNER_INVALID` (not a registered reporting contract).
   13. `TestSuiteCasesFileRefused`. The command writes `{"unit":…}` to `$AIT_TESTMAP_REPORT_DIR/cases.jsonl` and exits 0. The unit is not `pass` (the invocation carries `cases:refused`): an aggregate cannot fake case evidence.
   14. `TestSuiteContainmentUnavailable`. With `AIT_TEST_PROCSUP_UNAVAILABLE=1`, `runner suite describe` → exit 3, `CONTAINMENT_UNAVAILABLE:linux` (mirrors `TestBashFileContainmentUnavailable`'s mechanics).
   15. `TestSuiteRunRefusesForgedUnit`, isolated. `suiteRun` in-process with a forged manifest (a report dir in `t.TempDir()`), with a marker command. Cases:
       - two units;
       - the wrong id (`…#other`);
       - the wrong lowering.

       Each gives one `error` row per unit, `protocol:` prefix, exit 1, and the marker is absent (nothing ran). The same holds for a single valid unit in a manifest whose `timeouts` is `per_unit` or whose `accounting` is `unit` (the run-side fixed-contract check).
4. **README** (`goengines/README.md`):
   - layout row 119 and the `runner <name>` row 341: add `suite` to the registered Linux adapters;
   - new Interfaces row **`suite` builtin (M3.2i)**: classes and the **fixed contract** (`unit` / `accounting` / `discovery` / `timeouts` overrides refused; the rest overridable), the unit rule and its three list refusals, the run line, the status mapping, what a pass proves (never test results, never an anchor), the mechanism exits (`SUITE_ERROR:`, 64 for `command:`), `SUITE_RECURSION:` (and that the runtime guard is the real protection), logs, `fallback_command` not run, `full` / children, the support claim, what it reads, and the test names.
5. **Task body amendment** (framework commit, `./.aitask-scripts/aitask_task_commit.sh`):
   - "**Run.** … as `sh -c`" → "`bash -c` (the shell the framework runs `test_command` with)";
   - add a line recording the three list refusals, the fixed-contract override refusal (Step 0 #15) and the decision in Step 0 #10.
6. **Red proofs.** Isolated mutants applied to a **scratch copy** of `goengines/` (never the shared tree), each sha256-restored, the copy diffed identical. All must go red at the named test:
   - (a) the empty-command check removed → `TestSuiteDescribe` / refusals (d);
   - (b) the recursion diagnostic disabled → `TestSuiteRecursionDiagnostic`;
   - (c) the diagnostic's stderr line moved after the error (oneLine path) → the `SUITE_RECURSION:full|./ait` exact match;
   - (d) the own-`bind:` refusal removed → refusals (a);
   - (e) the foreign-bind refusal removed → refusals (b);
   - (f) the exclude refusal removed → refusals (c);
   - (g) `"bash"` → `"sh"` → `TestSuiteBashSemantics`. Red here through the `shopt -qo posix` check: this host's `/bin/sh` is bash in POSIX mode, and there is no dash;
   - (h) stdout to `os.Stdout` instead of the log (OutputMax ignored) → `TestSuiteOutputPastCap` mechanism;
   - (i) `Truncated` ignored → message assertion;
   - (j) non-zero → pass;
   - (k) the backstop shortened to 0.5 s and `TimedOut` reported as status `timeout` → the engine records `timeout_not_per_unit` (a protocol error), so the timeout test goes red. This proves the test pins engine attribution, not an adapter-reported timeout;
   - (l) `AIT_TESTMAP_ACTIVE` filtered from the command env → `VIA:ancestor:<pid>` → red;
   - (m) the unit check removed → `TestSuiteRunRefusesForgedUnit`;
   - (n) `os/exec` imported in `suite.go` → adapter tripwire;
   - (o) registration removed → `TestRunnerVerb`;
   - (p) the invariant5 marker comment removed → `goengines/guards_test.go`;
   - Fixed-contract mutants. Each names the protecting layer it removes, the cases that must turn red, and the cases that must **stay green** because another layer still refuses them. A run that reddens only through changed diagnostic wording does not count as a proof:

     | mutant | layer removed | must go red | must stay green (why) |
     |---|---|---|---|
     | (q) `suiteFixedOverride` disabled | list: override keys | 5b `timeouts: per_unit`, `timeouts: batch`, `unit: file`, `discovery: native`, `discovery: candidates` (each **loads**) | 5b `accounting: unit` / `cases` (the belt check refuses them through the effective accounting), the in-process belt case, the anchor regression check (an aggregate fixture, unaffected) |
     | (q2) only the `timeouts` row of `suiteFixed` skipped | list: one key | 5b `timeouts: per_unit`, `timeouts: batch` | every other 5b case (each key is pinned on its own) |
     | (q3) belt check (`e.Accounting`) disabled | list: effective accounting | 5b in-process belt case | every engine-level 5b case (the override-key layer refuses them) |
     | (q4) (q) **and** (q3) together | both list layers for accounting | 5b `accounting: unit` / `cases` (each **loads**), plus everything (q) reddens | the anchor regression check (still an aggregate fixture; the bypass is shown by the loading cases, not by this check) |
     | (r) run-side manifest check removed | run | 15 `per_unit` / `unit` manifest cases (in-process `suiteRun`, the marker file **exists**: the command ran) | all 5b cases (Load-time layers intact) |

     The anchor regression check gets no mutant here. It guards the outcome, and its rule (`opaque:aggregate` before the clean-tree return) is t1854_4's, already red-proved by `TestEligibilityAggregateNeverAnchors`.
7. **Verify:**
   - `./ait engine test` green;
   - `./ci/preflight.sh`;
   - `GOOS=darwin go vet ./...`;
   - `./build.sh all`;
   - builtin + cmd with `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1`, no skips;
   - `go test -race -count=1 -timeout 45m ./internal/testmap/runner/builtin/`;
   - real-binary end-to-end: build `ait-testmap`, run on a scratch repo with a suite `bash -c 'exit 0'`, a failing one and one leaving a `setsid` daemon past `timeout_s: 1`. Expect `UNIT:aitestmap/runners.yaml#…|pass|…`, `RUN_ACCOUNTING:3|0|0|3|0`, `containment: supervisor`, and the daemon gone.

### Post-phase (risk mitigations)

1. [stress_suite_tests_under_load] Run `go test -count=10 ./internal/testmap/runner/builtin/` (with `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1`) while a concurrent `go test -count=1 -p 8 ./...` loads the host.
   - Record the pass count in the Final Notes.
   - Fix any failure before review by replacing a sleep- or poll-based wait with an event wait, or by widening a bound with a stated reason. Never by skipping the test.
   - Repeat until 10/10 pass under load.

## What the adapter reads (for t2082 — repeated in Final Notes)

- **Command line:** `bash -c <command:>`, the whole `command:` string as one argument (no splitting).
- **Cwd:** the entry's `cwd` (default the root).
- **Inventory:** no process. It reads `runners.yaml` (its own `command`, `cwd`, `bind` (refused), every other entry's `bind`) and `config.yaml` `exclude:`.
- **Environment:** inherited from the builtin (`AIT_TESTMAP_*`, including `REPORT_DIR` and `ACTIVE`); stdin `/dev/null`.
- **Config flags:** none passed. What the command reads is opaque to the engine. `runnerConfig`'s per-token `command:` inputs still apply, but an aggregate never anchors (`opaque:aggregate`).

## Notes to send after the commit (`./ait note`)

- **t1857** (M6 detect):
  - the suite command runs under `bash -c`, so snapshot `test_command` verbatim;
  - emit no `bind:` on the suite entry, and no `accounting` / `timeouts` / `unit` / `discovery` overrides (`full: true` and `needs:` are fine);
  - id `aitestmap/runners.yaml#<name>`;
  - `SUITE_RECURSION:` refuses a snapshotted `./ait test`;
  - `exclude:` and foreign binds over `aitestmap/runners.yaml` refuse the list.
- **t1859_4** (M8.4): the adapter never runs `fallback_command:`, the suite id, and the run under `bash -c`, so the fallback path should use the same shell.
- **t1854_14:**
  - logs are `unit-0000.std{out,err}`;
  - the command inherits `AIT_TESTMAP_REPORT_DIR`;
  - a `cases.jsonl` written there is refused under aggregate;
  - the suite writes no child rows.
- **t2082:** what it reads (above).

## Verification (= the task's acceptance criteria, as amended)

Every criterion maps to a test above:
- Classes: test 1.
- The unit and no drift: test 4.
- Run (`bash -c`, log, `timeouts: none`): tests 6–10.
- Result (exit only; aggregate never anchors): tests 6 and 13, test 5b (overrides cannot change the class; the separate anchor regression check: `cost.Rows` gives `opaque:aggregate` on a clean tree), plus t1854_4's `TestEligibilityAggregateNeverAnchors`.
- Recursion: diagnostic tests 2–3, runtime test 11; the discovery side is Step 0 #10 with test 4.
- `fallback_command`: test 4.
- Real-tool cases: pass/fail test 6, the timeout with `setsid` test 9, output past the cap test 10.
- Common criteria:
  - only through the foundation: the tripwire and `Env.Supervise`;
  - containment: test 14;
  - G10 support claim: describe docs, README, `requireBash` under `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1` in CI;
  - "what it reads": above;
  - `ait engine test` green.
- The `cases`-adapter criteria do not apply (aggregate).

## Risk

### Code-health risk: low
- The process-heavy real-tool tests may flake under CI or local parallel load. They involve nested engines, a 1 s engine-killed timeout with pid-liveness checks, and a 64 MiB output write per run. · severity: low (residual — addressed by inline post-phase stress_suite_tests_under_load) · → mitigation: inline post-phase stress_suite_tests_under_load
- Fixed-contract overrides: a `runners.yaml` override of `accounting` / `timeouts` / `unit` / `discovery` would silently turn the aggregate into an anchor-eligible or unbounded unit. The engine merges overrides before validating and gives the adapter no veto, so the adapter's list and run must enforce the contract themselves. A future adapter-side bypass, such as a new verb that skips list, would reopen this. · severity: low (residual — addressed in the plan by Step 0 #15, list and run checks, and tests 5b and 15 with layer-attributed mutants q–q4 and r) · → mitigation: none (in-plan)
- The list-time refusals (a foreign `bind:` matching `aitestmap/runners.yaml`, `exclude:` over it, `bind:` on the suite) reject configurations that load today. These are loud refusals of configurations where the suite unit would otherwise be silently dropped, never a behaviour change for existing runners. · severity: low · → mitigation: none (intended fail-closed rule; README + t1857 note)

### Goal-achievement risk: low
- `bash -c` instead of the body's `sh -c` (user decision 2026-10-26). The task body is amended in the same task, and t1857 / t1859_4 are noted. · severity: low · → mitigation: none
- The recursion diagnostic is a lexical heuristic, so an indirect `./ait test` slips past it. That is by design: the t1854_7 runtime guard is the protection, and test 11 proves it through a hidden script. · severity: low · → mitigation: none

### Planned mitigations
- timing: post-phase | name: stress_suite_tests_under_load | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health flakiness of the process-heavy real-tool tests | desc: run the builtin package tests 10× under concurrent full-suite load and fix any flake with event waits

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9: archival on the
current branch, with no merge. Commits: engine (`goengines/**`) first, then
framework (the task body), kept separate per the aitasks_go cutover note.
