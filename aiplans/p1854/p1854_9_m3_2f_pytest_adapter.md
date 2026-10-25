---
Task: t1854_9_m3_2f_pytest_adapter.md
Parent Task: aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md
Sibling Tasks: aitasks/t1854/t1854_1_*.md, aitasks/t1854/t1854_2_*.md, aitasks/t1854/t1854_3_*.md, aitasks/t1854/t1854_4_*.md, aitasks/t1854/t1854_5_*.md, aitasks/t1854/t1854_6_*.md, aitasks/t1854/t1854_7_*.md, aitasks/t1854/t1854_8_*.md, aitasks/t1854/t1854_10_*.md, aitasks/t1854/t1854_11_*.md, aitasks/t1854/t1854_12_*.md, aitasks/t1854/t1854_13_*.md, aitasks/t1854/t1854_14_*.md
Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-25 16:37
---

# Plan: t1854_9 — M3.2f pytest adapter

## Context

Child **M3.2f** of t1854. This task adds the second production builtin runner,
`pytest`. It is the first `accounting: cases` / `discovery: native` adapter.
M10.1 (t1861) uses it for aitasks' ~378 `tests/test_*.py` modules, and
thinking_backend uses it too.
- **Builds on:**
  - the t1854_6 scaffold (`runner/builtin`: `Register`, `Env.Supervise`, `Env.Fresh`, `Results.Case`, `SplitCommand`, `DiscoveryBound`);
  - the t1854_2 case reconciler;
  - the t1854_7 recursion guard;
  - the t1854_5 hang guard.
- **Follows:** the `bash-file` pattern (t1854_8, `p1854_8`).
- **Authoritative:** the task body, for G1–G10.
- **Acceptance criteria:** amended at the user's direction (2026-10-25, the plan review). The evidence contract is an **engine-owned, observe-only pytest plugin that records exact runtime nodeids**, in place of JUnit XML. Step 7 edits the task body.

Automation-first: no step makes a human action a precondition.

## Step 0 — Reality check (done 2026-10-25 at main `c774eb540`)

**Tools on this host:**
- pytest 8.4.2, CPython 3.14.8 and pytest-xdist 3.8.0, in `~/.aitask/venv`;
- `python3` on PATH = the `~/.aitask/bin/python3` shim, which runs the venv python;
- `pytest` is not on PATH.

Everything was measured in scratch fixtures and in a `git archive HEAD` export of aitasks. The shared tree was never touched.

| # | task body says | repository / tool has | decision |
|---|---|---|---|
| 1 | register with `runner.RegisterBuiltin` | `builtin.Register(Adapter{…})` | use it; Linux-only `init` in `pytest_linux.go` (G10: darwin pending) |
| 2 | case identities = collected nodeids | list case rows `<unit>\tcase\t<id>`; run `Results.Case` → `cases.jsonl`; the reconciler (G1a/G1b) **and G3 are engine-owned** | the adapter writes case rows only: never a unit row, **never start rows** (#3). G3 needs only tests |
| 3 | `timeouts: batch` | batch with no start rows: every unreported unit at the kill is `batch_timeout` | one pytest per invocation. No start rows, because which file was running is unknowable, so `batch_timeout` is the honest attribution |
| 4 | **(plan review, concern 1)** report testcase ↔ nodeid via JUnit `(classname, name)` | **JUnit keys are not identities**: `tests/test_a.py::TestC::test_m` and `tests/test_a/TestC.py::test_m` both give `classname="tests.test_a.TestC" name="test_m"` (measured). A collect-only-vs-run substitution would map the replacement onto the discovered identity, so a pass is falsely accepted | **evidence = exact runtime nodeids** from an engine-owned plugin (#5). The JUnit criterion is **dropped** (user decision): `--junitxml` is not passed, and a project's own junitxml config is untouched |
| 5 | "passes no `-c` / `--rootdir` / `-p`" | a `-p` module must be importable. Measured plugin (`pytest_configure`, `pytest_collectreport`, `pytest_collection_finish`, `pytest_runtest_logreport`, `pytest_sessionfinish`), guarded to the **controller** (`not hasattr(config, "workerinput")`). Plain and under `-n 2` it records the rootdir, the items, non-passed collect reports, every phase of every test **once**, and the exitstatus. xdist forwards worker test and collect reports (skip, error) to the controller | **deviation, user-authorized 2026-10-25:** `-p _aitestmap_pytest_evidence`, its directory **prepended to `PYTHONPATH`**, and `AIT_TESTMAP_PYTEST_EVIDENCE=<file>`. No `-c` / `--rootdir` / `-o`. This is adapter-scoped and distinct from the deferred **suite**-command plugin injection (t2118, parent directive "injected pytest plugins deferred"). Written down for t2082 / t2118 / t1854_14 / t1861 (notes) |
| 6 | **(concern 2)** zero collected → G3 | `pytest.skip(..., allow_module_level=True)`: zero items, collect rc 5, but a **collect report `skipped`** for collector nodeid `tests/test_s.py` (plain and xdist; measured). JUnit renders it as `classname="" name="tests.test_s"` | a skipped collector is an **expected identity** of its unit (the collector nodeid). Run maps its skip record to `skip` with the reason (G4: the tool's own verdict). So a module-skipped unit is `skip` under **either** `zero_tests` policy, alone or in a mixed batch, with no `unexpected_case`. G3 stays for genuinely empty modules |
| 7 | **(concern 3)** rootdir agreement | nodeids are rootdir-relative. The rootdir is the ini dir found from the args upward, else cwd (measured: root `pytest.ini` + cwd `tests/sub` → `tests/sub/…`; nested `tests/pytest.ini` → rootdir below cwd; a file outside it → nodeid `::test_o`) | the plugin **reports `config.rootpath`**, so the plan's union-based inference is **deleted**. Mapping: `EvalSymlinks(R)/f == EvalSymlinks(C)/a`, string-exact and unique. Lowering = `rel(R, C/a)`. Run re-checks its own reported R against every lowering (rootdir drift → mechanism). Regression: `t/t.py` + `t/t/t.py`, root ini, importlib (measured: collects and passes) |
| 8 | xfail/xpass/skip/teardown | phases per test: setup / call / teardown. Measured records: xfail = call `skipped` + `wasxfail`; fail+teardown error = call `failed` + teardown `failed` (pytest counts it "1 failed, 1 error") | one row per terminal tool result (rule below). Fail+teardown error → two rows → `duplicate_case` (non-pass; stated in describe) |
| 9 | colliding identities at discovery → `duplicate_case` | the engine's `ParseList` refuses a repeated case row (RUNNER_PROTOCOL → `INPUT_ERROR:lister`); this is t1854_2's rule | discovery duplicates → `INPUT_ERROR:lister`; run duplicates → `duplicate_case`. Never deduplicated; both are real-tool tests (a conftest duplicating items) |
| 10 | collection error = `INPUT_ERROR:lister` | plain: rc 2; `-n 2`: rc **1** and the tests still run. Both record a collect `failed` | any `failed` collect record in discovery → list error naming nodeid + message, whatever the rc |
| 11 | measure `--collect-only` on aitasks | 378 files → 9901 nodeids, rc 0, **14.2 s** (DiscoveryBound 270 s). Side effects: gitignored `__pycache__` only; no `.pytest_cache`; module-level code runs | stated in describe / README (M10.1: every `Load` pays ~14 s) |
| 12 | `python -I` / `-E` (t2118's named failure mode) | they ignore `PYTHONPATH`, so the `-p` import fails and pytest exits with a usage error | detected: no evidence session / rc 4 → list error `pytest evidence plugin not loaded (does the interpreter honour PYTHONPATH?)`. Tested |
| 13 | hang guard / tripwire | `runner/builtin` is already in `tripwirePackages`; `bashfile_tripwire_test.go` covers every non-scaffold, non-test `.go` file | nothing to add; `hangguard.Isolated(t, pytestHangLimit)` in every process-starting test |
| 14 | CI pinned pytest | both workflows' `go test` steps set `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1` (t1854_8); setup-python runs only after `go test` in `check` | install `pytest==8.4.2 pytest-xdist==3.8.0` before `go test` in `goengines-check.yml` `check` and `release.yml` `goengines` (legacy-gated), in a separate commit. Pin the ordering in `tests/test_release_workflow_goengines.py` |
| 15 | default command | aitasks runs `$PY -m pytest <files>` | default `python3 -m pytest` |
| 16 | option-shaped / special paths | `./-tests/test_o.py` → nodeid `-tests/test_o.py::…` (measured); `::` in an arg is a node selector | operand `./<path>`; list refuses a bound path containing `::` |
| 17 | `cmd` TestRunnerVerb | pins `[bash-file]` | `want = [bash-file, pytest]` + `runner pytest describe` |
| 18 | data from outside goengines/ | none; the plugin source lives in `goengines/` (`//go:embed`) | none (aitasks_go note) |
| 19 | G10 versions | — | the session record carries the pytest and python versions. Discovery refuses anything other than pytest 8.x on CPython ≥ 3.10 (`PYTEST_UNSUPPORTED:<detail>` list error) |

Touched files outside `builtin/pytest*`, each a named extension of its owner:
- `builtin/bashfile.go`: `gitInventory` factored out, byte-for-byte behaviour;
- `builtin/builtin.go`: doc;
- `cmd/ait-testmap/main_test.go`;
- `goengines/README.md`;
- the two workflows and `tests/test_release_workflow_goengines.py` (separate commit);
- the task body's acceptance criteria (Step 7).

## Evidence contract (the plugin)

**`builtin/pytest_evidence_plugin.py`**, embedded with `//go:embed` and written out as `_aitestmap_pytest_evidence.py`:
- Stdlib only (`json`, `os`, `platform`).
- **Observe-only:** no hookwrappers, no item or report mutation.
- On a non-controller (`workerinput`) process, or when `AIT_TESTMAP_PYTEST_EVIDENCE` is unset, it does nothing. Otherwise it opens the file line-buffered, in append mode.
- Records are one JSON object per line (`ensure_ascii=True`):
  - `{"k":"session","v":1,"rootdir":…,"pytest":…,"python":…,"impl":…}`, at configure;
  - `{"k":"items","nodeids":[…]}`, at `pytest_collection_finish` (absent under the xdist controller);
  - `{"k":"collect","nodeid":…,"outcome":"skipped"|"failed","message":…}`, for every non-passed collect report. The skip message is the reason from the `(path, line, reason)` longrepr; a failure gives the first line of `longreprtext`;
  - `{"k":"test","nodeid":…,"when":"setup"|"call"|"teardown","outcome":…,"xfail":<reason or null>,"message":…,"duration":<s>}`;
  - `{"k":"end","exitstatus":N}`, at session finish.
- Messages are bounded to 512 characters in Python, and bounded again in Go.
- Go owns all the semantics; the plugin only records (memory: helpers report evidence).

**Strict Go parse** (`pytestParseEvidence(data, mode)`), shared by list and run. Any violation → error (malformed):
- the first record is `session` and the last is `end`; exactly one of each;
- known kinds and members only, with lossless JSON;
- `end.exitstatus` == the process exit code;
- **mode-specific `items`:**
  - **discovery requires exactly one** well-formed `items` record. Genuine zero-item collection writes an explicit `[]`;
  - a missing `items` record is malformed, so lost inventory can never become all-zero units hidden by `zero_tests: skip`;
  - measured: pytest 8.4.2 `--collect-only` emits it plain and under `-n 2`, both for a populated collection and for an entirely module-skipped one (rc 5);
  - execution allows zero or one, because the xdist controller never collects.

**Unit mapping** (`pytestUnitOf(R, C, args, nodeid)`):
- `f` = the nodeid up to the first `::` (all of it if there is none);
- `f` must be non-empty and relative, with no `..`;
- the unit is the arg `a` with `Clean(EvalSymlinks(R)/f) == Clean(EvalSymlinks(C)/a)`;
- the match is exact, so there is at most one. No match → error.

**Row rule** (per `test` record, in order):
- setup: `failed` → error `setup: <msg>`; `skipped` → skip (`xfail: <reason>` if xfail, else the reason); `passed` → no row;
- call: `passed` → pass (`xpass: <reason>` if xfail); `failed` → fail; `skipped` → skip / xfail as above;
- teardown: `failed` → error `teardown: <msg>`; **`skipped` → skip `teardown: <reason>`** (measured: a fixture calling `pytest.skip` in teardown after a passing call gives `call/passed` + `teardown/skipped`, rc 0, plain and xdist); `passed` → no row;
- so every non-passed phase is its own terminal verdict, and the call always gives one. A pass followed by a teardown skip is two rows. The reconciler rejects that identity as `duplicate_case`, with no phase aggregation in the adapter (never-collapse);
- `collect` record: `skipped` → skip row, identity = the collector nodeid, with the reason; `failed` → error row, identity = the collector nodeid;
- an unknown `when` or `outcome` → malformed;
- duration = the record's duration in ms.

The rows keep evidence order and are never deduplicated.

## Adapter behaviour

**List** (`pytestList`):
1. Inventory: the factored `gitInventory` (supervised `git ls-files -z --cached --others --exclude-standard`, fail-closed on stderr / exit / truncation / `toolFailure`).
   - bind filter (default `**/test_*.py`, `**/*_test.py`);
   - regular files only;
   - `registry.ParseID`;
   - refuse `::` and control characters.

   With no bound files, write no rows and do not run pytest.
2. Private temp dir (removed on return): `plugin/_aitestmap_pytest_evidence.py`, `evidence.jsonl`, `out`, `err`.
3. `e.Supervise`:
   - argv = `pytestArgv(cmd, ["-p", mod, "--collect-only", "-q"], files)`;
   - Dir = cwd;
   - Env = `pytestEnv(os.Environ(), pluginDir, evidence)`, which prepends `PYTHONPATH` and keeps everything else, including `AIT_TESTMAP_ACTIVE`;
   - `Timeout: DiscoveryBound()`, `OutputMax: pytestListMax`.
4. Errors, in order:
   - `toolFailure` / truncation;
   - evidence missing or without a `session` record → the "plugin not loaded" error (rc + first stderr line);
   - a parse error (discovery mode: exactly one `items` record required);
   - any `failed` collect record → `collection error: <nodeid>: <msg>`;
   - rc ∉ {0, 5} → `pytest exit <rc>: <first stderr line>`;
   - any `test` record → error;
   - an unsupported version (#19).
5. Units: every bound file, with lowering = `rel(R, C/a)`. Each `items` nodeid and each `skipped` collector nodeid maps through `pytestUnitOf` to its unit. An unmapped one → error naming it and R.
6. Write rows sorted by unit id: `<id>\tfile\t<lowering>`, then `<id>\tcase\t<nodeid>` for its items in collection order, then its skipped collectors. Each identity goes through `runner.ValidCaseID`; nothing is deduplicated.

**Run** (`pytestRun`):
1. `SplitCommand(e.Command)` or `python3 -m pytest`. An error → `PYTEST_ERROR:command:…`, exit 64.
2. Check `e.Entry()` and `m.ReportDir`, and per unit:
   - the id lies under cwd, giving `arg = rel(cwd, id)`, which passes `registry.CheckPath`;
   - the lowering is clean and relative;
   - every case's file part == the lowering.

   A violation → `PYTEST_ERROR:protocol:…`, exit 3 (no unit rows under cases, so this is a mechanism). No units → exit 2.
3. Write the plugin to `<RD>/pytest-plugin/`. The evidence goes to `<RD>/pytest-evidence.jsonl`, and the logs to `<RD>/pytest.stdout|stderr`.
4. Run one `e.Supervise`: argv = `pytestArgv(cmd, ["-p", mod], args)`, Dir = cwd, Env as in list, `Timeout` = `m.DeadlineS`, Grace = 1 s.
5. **Mechanism** → `PYTEST_ERROR:…` on stderr, exit 3, **no case rows**. Mechanism is any of:
   - `toolFailure` (start, supervisor, cleanup, containment, cancel, timeout) or a signal;
   - rc ∉ {0, 1, 2, 5};
   - evidence absent, or refused by `e.Fresh` (stale, link, oversize, replaced dir: G6);
   - malformed evidence;
   - **rootdir drift**: some unit with `R_run/lowering ≠ C/arg`;
   - an **unattributable** nodeid (`pytestUnitOf` fails);
   - **exit inconsistency**: rc 0 with a fail/error row; rc 1 or 2 with none; rc 5 with any `test` record.
6. Otherwise write every row (`res.Case`). Exit 0 if no row is fail/error, 1 if one is, 2 if there are no rows. The engine reconciles (missing → `incomplete`, duplicate → `duplicate_case`, unexpected → `unexpected_case`) and applies G3.

**Describe.** YAML comments carry:
- the contract above;
- the plugin deviation (`-p`, `PYTHONPATH`, the env var; observe-only);
- discovery side effects (imports, `__pycache__`) and cost;
- the status rule (xfail → skip, xpass → pass, fail+teardown error → duplicate_case, a module skip → skip);
- what a pass proves;
- the unsupported cases: `-I` / `-E` interpreters, conftest-level directory skips (pytest itself aborts), files outside the rootdir;
- logs;
- support: pytest 8.x on CPython ≥ 3.10, linux.

Keys:
```yaml
unit: file
accounting: cases
discovery: native
timeouts: batch
```

## Implementation steps

1. **`builtin/pytest_evidence_plugin.py`**: the plugin (contract above).
2. **`builtin/pytest.go`** (`//go:build unix`):
   - the constants;
   - the `//go:embed`;
   - `pytestAdapter`, `pytestDescribe`;
   - `pytestArgv`, the single builder both verbs use: `cmd + flags + "./"+files`;
   - `pytestEnv`, `pytestWritePlugin`, `pytestParseEvidence`, `pytestUnitOf`, `pytestRows`;
   - `pytestList`, `pytestRun`.
3. **`builtin/bashfile.go`:** extract `gitInventory(ctx, e, dir, max)`. bash-file's tests 14 and 15 stay the unchanged oracle.
4. **`builtin/pytest_linux.go`:** `init` registration.
5. **Named extensions:**
   - the `builtin.go` doc names `pytest (pytest_linux.go)`;
   - `cmd/ait-testmap/main_test.go` `TestRunnerVerb`: `want = [bash-file pytest]` on Linux, plus `runner pytest describe` ⊇ `accounting: cases`.
6. **Tests.** The pure ones are in `pytest_test.go`: unguarded, starting no process, never referencing the adapter value.
   1. `TestPytestParseEvidence`:
      - ok;
      - missing session or end;
      - **discovery without an `items` record** → error, while discovery with `items: []` is ok;
      - execution without `items` → ok;
      - two `items` records → error;
      - two ends;
      - an unknown kind or member;
      - an exit mismatch;
      - a truncated last line;
      - invalid JSON.
   2. `TestPytestRows`: the phase table, including xfail, xpass, strict xpass (call failed), setup error, fail+teardown error (two rows), **pass+teardown skip (two rows: pass, skip `teardown: <reason>`)**, a collect skip and a collect failure.
   3. `TestPytestUnitOf`:
      - R = C, R above C, R below C;
      - **`t/t.py` + `t/t/t.py`** (concern 3: each nodeid maps uniquely);
      - an empty `f` (`::x`);
      - `..`;
      - a symlinked C;
      - no match.
   4. `TestPytestArgvShared`: list and run argv differ exactly by `--collect-only -q`, and the files (`./`-prefixed) come last.
   5. `TestPytestEnv`: `PYTHONPATH` prepended (unset and set cases), the evidence var set, other vars kept.
   6. `TestPytestDescribe`: `ParseDescribe` + `Validate` give file / cases / native / batch, plus the comments.

   The real-tool tests are in `pytest_linux_test.go`:
   - each starts with `hangguard.Isolated(t, pytestHangLimit = 120 s)`;
   - `requirePytest(t)` looks for `python3` on PATH, then `~/.aitask/venv/bin/python`, with pytest 8.x on CPython ≥ 3.10. Otherwise it skips, or fails under `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1`. `requireXdist` works the same way;
   - the fixtures are `newRepo` with `builtin: pytest` entries.

   7. `TestPytestDiscoveryAndRun`. The case rows equal plain `pytest --collect-only -q` (without the plugin, so transparency is checked). The fixture has:
      - pass and fail tests;
      - parametrized ids (`a/b`, `c::d`, `e.f`);
      - a class and a `unittest.TestCase`;
      - xfail, xpass and strict xpass;
      - a skip with a reason and `@skip(reason=)`;
      - a setup error;
      - fail plus a teardown error;
      - **a pass followed by a teardown `pytest.skip("cleanup cannot finish")`, in its own file**.

      Asserted: the statuses, the engine counters, the skipped list with reasons, run exit 1, containment supervisor, and the evidence and logs present. Both teardown units are `error`/`duplicate_case`. The teardown-skip unit's evidence holds the skip row with reason `teardown: cleanup cannot finish`; it is **not** `pass`.
   8. `TestPytestCollectionError`: Load fails and names the broken file; `cmd` `scan` prints `INPUT_ERROR:lister|`.
   9. `TestPytestRootdirAboveCwd`: root `pytest.ini`, `cwd: sub`. The lowering is `sub/tests/test_x.py`, and the run passes.
   10. `TestPytestNestedIniBelowCwd`: `tests/pytest.ini`, so R = `tests` and the lowering is `x/test_a.py`, and the run passes. Adding a bound file outside `tests/` → a Load error naming `::test_o` and R.
   11. **`TestPytestOverlappingPaths` (concern 3 regression):** `t/t.py` + `t/t/t.py`, root `pytest.ini` with `--import-mode=importlib`. Both units pass with their own nodeids.
   12. **`TestPytestSubstitutionKeyCollision` (concern 1 regression, the user's repro):**
       - setup: `--import-mode=importlib`, the runner has `zero_tests: skip`;
       - `tests/test_a.py` defines `TestC.test_m` only under `--collect-only`;
       - `tests/test_a/TestC.py` defines `test_m` only otherwise.

       Expect: `tests/test_a.py` → `error`/`incomplete`; `tests/test_a/TestC.py` → `error`/`unexpected_case`, **not** skip; run accounting shows no pass.
   13. `TestPytestSubstitutionRename`: `test_b` under collect-only, `test_c` otherwise → `error` with `unexpected_case,incomplete`.
   14. **`TestPytestModuleLevelSkip` (concern 2 regressions):**
       - (a) isolated: one module-skipped file alone (rc 5) → `skip`, reason `mod reason`, under both `zero_tests` policies;
       - (b) mixed: the skipped module plus a passing module in one batch → `skip` + `pass`, with no `unexpected_case`;
       - (c) skipped at discovery but not at run (env-armed) → `error`;
       - (d) not skipped at discovery but skipped at run → `error` (`incomplete` + `unexpected_case`).
   15. `TestPytestZeroTests`: an empty file → `error`/`zero_tests` by default, `skip` under `zero_tests: skip`. Its batch neighbour passes.
   16. `TestPytestBatchNo`: two `# testmap:batch no` files plus two plain ones → two singleton invocations and one shared invocation.
   17. `TestPytestDuplicates`: a conftest duplicates an item only at run → `duplicate_case`; the same conftest active in collect-only → Load refused (`already listed`, i.e. `INPUT_ERROR:lister`).
   18. `TestPytestXdist` (`requireXdist`): `-n 2`. Every phase is recorded once (case rows = tests), a failing case is `fail`, a module skip is `skip`, **a pass+teardown-skip test → `error`/`duplicate_case` with the teardown reason**, and a collection error under xdist (rc 1) at run → `error` (`unexpected_case`). Discovery under `-n 2` (populated, and entirely module-skipped) satisfies the required `items` record.
   19. `TestPytestBatchTimeoutKillsTree`: `batch_timeout_s: 3`, and a test backgrounds `sleep 300`. Every unit is `batch_timeout`, and both pids are gone.
   20. `TestPytestRecursionThroughExecution`: a test runs `__nested_engine run` at the root; the state file has `RUN_ERROR:recursion|` and exactly `VIA:marker`. Against the other fixture → `NESTED_OK:0`.
   21. `TestPytestRecursionThroughDiscovery`: an armed `conftest.py` runs `__nested_engine check` under `--collect-only` and raises `pytest.UsageError(<line>)`. Load fails with `RUN_ERROR:recursion|`, and the state file has `VIA:marker`. Against the other fixture → OK.
   22. `TestPytestCommandOverride`:
       - `command: python3;x` → a list error, and run exit 64;
       - **`command: <python> -I -m pytest`** → the "plugin not loaded" list error (#12);
       - the default command, tested when `python3` qualifies.
   23. `TestPytestContainmentUnavailable`: `Main([pytest describe])` → exit 3, `CONTAINMENT_UNAVAILABLE:linux`.
   24. `TestPytestFakeEvidence` uses a `command:` bash shim writing crafted evidence. Each case → mechanism, every unit non-pass:
       - a stale file (`touch -d 2000-01-01`);
       - a symlink;
       - malformed JSON;
       - absent with rc 0;
       - no `end` record;
       - `end.exitstatus` ≠ rc;
       - rc 0 with a fail row;
       - rc 1 with no fail/error row;
       - an unattributable nodeid;
       - rootdir drift;
       - pytest `9.0.0` in `session` (the list error `PYTEST_UNSUPPORTED`);
       - **discovery evidence of a valid `session` plus a matching `end` (rc 0) with no `items` record**, under `zero_tests: skip` → a list error, never all-zero units.
   25. `TestPytestOptionShapedPath`: `-tests/test_o.py` runs through `./`; `tests/test_a::b.py` → a list error.
7. **README:**
   - the registration rows;
   - a new Interfaces row **`pytest` builtin (M3.2f)**: classes, the evidence contract and plugin deviation, discovery, the run line, the row rule, the outcome and mechanism rules, no start rows, what a pass proves, logs, what it reads, cost, support (CI pins pytest 8.4.2 / xdist 3.8.0), and the test names;
   - the plugin file in the layout.
8. **CI (separate non-engine commit):**
   - `check`: move `Setup Python` (3.12) before `go test`, and add `python -m pip install pytest==8.4.2 pytest-xdist==3.8.0`;
   - `release.yml` `goengines`: the same two steps, legacy-gated;
   - the guard test asserts in both jobs that the install precedes the first `go test ./...`, with the same gate. Run it locally.
9. **Task body:** rewrite the Discovery / Execution / "What it reads" acceptance bullets:
   - native collect-only with the evidence plugin;
   - exact runtime nodeids;
   - module-level skips as collector identities;
   - the reported rootdir;
   - `-p` / `PYTHONPATH` documented;
   - the junit criterion removed, with the reason.

   Keep every freshness, missing/duplicate, skip-reason and exit-consistency guarantee. Commit with `aitask_task_commit.sh`.
10. **Notes** (`./ait note`, once the code is committed, citing the SHA):
    - **t2082:** what it reads, including the plugin, `PYTHONPATH` and the ini resolved from the args upward;
    - **t1861:** bind `tests/test_*.py`, ~14 s discovery, module-skip semantics, and that `-I` interpreters are unsupported;
    - **t1854_14:** JUnit `(classname, name)` keys are **not** collision-safe (the concern-1 repro), so its JUnit attribution must refuse or prove uniqueness;
    - **t2118:** the measured xdist controller-guard facts, `-I` detection, and that this adapter's plugin exists and is adapter-scoped.

### Red proofs

Each proof is an isolated mutant on a **scratch copy** of `goengines/`, sha256-restored, with the copy diffed identical afterwards. All are expected red:
- (a) the worker guard removed from the plugin → test 18 (duplicate rows);
- (b) the skipped-collector identity not emitted at discovery → test 14 (`unexpected_case`);
- (c) run rows filtered to the expected identities → test 12 (the other unit turns `skip`);
- (d) the end-exitstatus check removed → test 24;
- (e) the exit-consistency check removed → test 24;
- (f) evidence read via `os.ReadFile` instead of `e.Fresh` → test 24 (stale / symlink);
- (g) the rootdir-drift check removed → test 24;
- (h) rows deduplicated → test 17;
- (i) `AIT_TESTMAP_ACTIVE` dropped from `pytestEnv` → tests 20 and 21 (`VIA:ancestor`);
- (j) registration removed → `TestRunnerVerb`;
- (k) `os/exec` imported → the adapter tripwire;
- (l) start rows written → test 19 (`timeout` instead of `batch_timeout`);
- (m) the operand without `./` → test 25;
- (n) the collect-failed check removed from list → test 8;
- (o) the version check removed → test 24;
- (p) `pytestUnitOf` by basename or suffix instead of exact equality → tests 3 and 11;
- (q) teardown `skipped` dropped from the row rule → tests 2, 7 and 18 (the unit turns `pass`);
- (r) the discovery `items`-required check removed → test 1 and test 24's no-items case (the units turn `skip` under `zero_tests: skip`).

### Verify

- `./ait engine test` green;
- `GOOS=darwin go vet ./...`;
- `./build.sh all`;
- the builtin package with `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1`, no skips;
- `go test -race -count=1 -timeout 45m ./internal/testmap/runner/builtin/`;
- `python -m unittest tests/test_release_workflow_goengines.py`;
- `bash tests/test_goengines_build.sh`;
- the real-binary end-to-end `ait-testmap run --all` on a scratch pytest fixture.

### Post-phase (risk mitigations)

1. [stress_pytest_tests_under_load] Run `go test -count=10 ./internal/testmap/runner/builtin/` while a concurrent `go test -count=1 -p 8 ./...` loads the host.
   - Record the pass count in the Final Notes.
   - Fix any failure before review by replacing a sleep- or poll-based wait with an event wait, or by widening a bound with a stated reason. Never by skipping the test.
   - Repeat until 10/10 pass under load.
2. [dogfood_aitasks_pytest] Run the adapter for real on aitasks:
   - Export `git archive HEAD` of aitasks into the scratchpad and `git init` + commit it. The shared tree is never used.
   - Add `aitestmap/runners.yaml` with one entry: `builtin: pytest`, `bind: ['tests/test_*.py']`, `command: <python with pytest> -m pytest`, `batch_timeout_s: 1800`.
   - With the built `ait-testmap`, run `check` and then `run --all`.
   - Assert:
     - 378 units (or the export's current count);
     - the case-row set ⊇ the nodeid set of plain `pytest --collect-only -q tests/test_*.py` on the same export, the difference being only skipped-collector identities, each listed;
     - `run` has no mechanism cause and no `unexpected_case` / duplicate / unattributable row.
   - Test failures that come from the export's environment are counted, not fixed.
   - Record in the Final Notes: discovery time, the per-status counts and `RUN_ACCOUNTING`.
   - Any adapter refusal is fixed before review.

## What the adapter reads (for t2082 — repeated in Final Notes)

- **Command line:**
  - list: `<command: | python3 -m pytest> -p _aitestmap_pytest_evidence --collect-only -q ./<cwd-relative file>…`;
  - run: `<command: | python3 -m pytest> -p _aitestmap_pytest_evidence ./<cwd-relative file>…`.
  - No `-c` / `--rootdir` / `-o` / `--junitxml`.
- **Environment the adapter adds:**
  - `PYTHONPATH=<engine-private plugin dir>[:<inherited>]`;
  - `AIT_TESTMAP_PYTEST_EVIDENCE=<file>`.

  Everything else is inherited, including the recursion marker. The plugin is engine-owned and observe-only: its source is part of the engine version, not a project input.
- **Cwd:** the entry's `cwd` (default the root), an ancestor of every listed test.
- **Config pytest resolves itself:**
  - the ini found from the **args' common ancestor upward**, i.e. from the tests' ancestors, possibly above the repository;
  - `conftest.py` files along the tests' paths;
  - `PYTEST_ADDOPTS` / `PYTEST_PLUGINS`;
  - installed entry-point plugins.
- **Inventory:** `git ls-files -z --cached --others --exclude-standard` in the cwd (`gitx.Env()`).
- **runners.yaml:** `cwd`, `bind`, `command`, `batch_timeout_s`, `zero_tests`.

## Verification (= acceptance criteria, as amended)

Each amended criterion maps to a test:
- classes → 6.6;
- discovery → 6.3, 7–11, 14;
- the exact-identity evidence → 6.1, 6.2, 12, 13, 24;
- G3 → 14, 15;
- batch no → 16;
- real-tool cases → 7, 9–19;
- fakes → 24;
- containment → 23;
- recursion → 20, 21;
- duplicates → 17;
- support claims → 22, 24 + describe + README + CI;
- `ait engine test` → Verify.

## Risk

### Code-health risk: medium
- Process-heavy real-tool tests (~19 tests: pytest startups, xdist, nested engines, a batch-timeout kill) may flake under CI or local parallel load · severity: medium (residual — addressed by inline post-phase stress_pytest_tests_under_load) · → mitigation: inline post-phase stress_pytest_tests_under_load
- Factoring `gitInventory` out of `bashfile.go` touches t1854_8's landed adapter · severity: low · → mitigation: none (bash-file's own tests 14/15 run unchanged as the oracle)
- The embedded Python plugin is a second-language component inside the engine, with its own compatibility surface (pytest 8.x hook API) · severity: low · → mitigation: none (stdlib-only, observe-only, version-gated by #19; real-tool tests cover plain and xdist)
- The pinned `pip install` adds a network step to two required CI jobs · severity: low · → mitigation: none (intended G10 behaviour)

### Goal-achievement risk: low
- The fail-closed contract (exit consistency, rootdir drift, unattributable nodeids, `-I` interpreters, version gate) might refuse aitasks (M10.1) for a reason no fixture showed · severity: low (residual — addressed by inline post-phase dogfood_aitasks_pytest) · → mitigation: inline post-phase dogfood_aitasks_pytest
- Semantic decisions: fail+teardown-error and pass+teardown-skip → `duplicate_case` (non-pass); discovery duplicates → `INPUT_ERROR:lister`; the plugin `-p` deviation (user-authorized) · severity: low · → mitigation: none (Step 0 #5/#8/#9; describe, README, notes)

### Planned mitigations
- timing: post-phase | name: stress_pytest_tests_under_load | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health flakiness of the real-tool tests | desc: run the builtin package tests 10x under concurrent full-suite load and fix any flake with event waits
- timing: post-phase | name: dogfood_aitasks_pytest | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement risk that fail-closed mapping refuses the real M10.1 consumer | desc: run check + run --all with a pytest entry on an exported aitasks tree and prove full case accounting with no mechanism/unattributable rows

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9: archival on the
current branch, with no merge.
