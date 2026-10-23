---
Task: t1854_7_m3_2d_recursion_guard.md
Parent Task: aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md
Sibling Tasks: aitasks/t1854/t1854_1_*.md, aitasks/t1854/t1854_2_*.md, aitasks/t1854/t1854_3_*.md, aitasks/t1854/t1854_4_*.md, aitasks/t1854/t1854_5_*.md, aitasks/t1854/t1854_6_*.md, aitasks/t1854/t1854_8_*.md, aitasks/t1854/t1854_9_*.md, aitasks/t1854/t1854_10_*.md, aitasks/t1854/t1854_11_*.md, aitasks/t1854/t1854_12_*.md, aitasks/t1854/t1854_13_*.md, aitasks/t1854/t1854_14_*.md
Archived Sibling Plans: aiplans/archived/p1854/p1854_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-22 23:00
---

# Plan: t1854_7 — M3.2d Recursion guard (G9)

## Context

A test, a suite command or a framework's native discovery can start another
engine run of the **same repository** (pytest collection imports `conftest.py`,
`go test -list` runs package `init`). Through `./ait test` that would also reach
`aitask_test.sh`, against Invariant 5. This task adds the **runtime** refusal
(G9) to the two engine entries that start runner processes, `runner.Run` and
`runner.Load` (so `scan`, `check`, `classify`, later `test` / `select`). It is a
prerequisite of every production adapter (t1854_6 onward). The task body
(`aitasks/t1854/t1854_7_m3_2d_recursion_guard.md`) is authoritative for G1–G10
and the acceptance criteria. Automation-first: no human step anywhere.

## Step 0 — Reality check (done 2026-10-22, main `ed04c92a5`)

**Callers of `Run` / `Load`.**
- `Run` (`runner/run.go:128`): Stat `aitestmap/` → `newRunID` → `Load` →
  `selectUnits` → mkdir run dir → `Executor.Execute(invs, iv.invoke)` →
  `runHooks`. Caller: `cmd/ait-testmap/run.go:61`; tests in `runner` and
  `cost/eligibility_test.go` (all on `fixture.New` repos).
- `Load` (`runner/repo.go:187`): `LoadConfig` → `registry.LoadConfig` →
  per entry `loadRunner` (spawns `describe`, `list`) → annotations → assign →
  `gitx.ListFiles`. Callers: `Run`; `Lister.List` (`repo.go:486`), which
  `cmd/ait-testmap/scancheck.go:26` wires into `scan`, `check` and every verb
  using `testmapInputs` / `registry.ReadInputs`.
- Every runner process goes through `Runner.command` (`repo.go:142`):
  `call` (describe/list, env = `os.Environ()`), `invoke.go:152` (run).
- The only post-run hook (`cost.Hook`) does not call `Load`.

**No engine test runs `Run` / `Load` against the real repository.** The three
test files that locate the real repo (`gitx/status_test.go`,
`deps/kotlinfamily_test.go`, `hangguard/tripwire_test.go`) never reach
`Run` / `Load`; every runner/cost/cmd test uses `fixture.New` (a fresh
`t.TempDir()` repository with its own `.git`). So an active marker for the
enclosing repository cannot refuse any existing test.

| # | task body says | repository has | decision |
|---|---|---|---|
| D1 | "a per-repository run **lock** under `.aitask-testmap/`" | `.aitask-testmap/` is per **worktree** (`StateDir` under `root`); a flock is exclusive | **Revise.** A *holder registry* (one file per active entry, not an exclusive lock — concurrent runs must not block) under `<git-common-dir>/ait-testmap/active/`. Under `.aitask-testmap/` an `env -i` nested entry in another worktree would miss the holder. `<git-dir>/ait-testmap/` already hosts the adoption and costs locks, so this is the established place for engine bookkeeping outside the work tree |
| D2 | refusal line `RUN_ERROR:recursion\|<root>` for `Run` and `Load` | `scan` / `check` wrap every lister error as `INPUT_ERROR:lister\|…` (`registry/inputs.go:184`) and `reportError` prints the outer line | **Adapt.** A dedicated `*runner.RecursionError`; `reportError` (`cmd/ait-testmap/scancheck.go:60`, a named extension) prints its line first, so every verb prints exactly `RUN_ERROR:recursion\|<root>`, exit 3 |
| D3 | "`env -i`" tests | under a fully empty env the nested engine cannot find `git` (gitx execs `git` by name) | **Adapt.** The `env -i` cases keep only `PATH` (no marker, no `HOME`, nothing else). A separate case with no `PATH` at all asserts the fail-closed path: identity unresolvable → `RUN_ERROR:recursion-unverifiable\|<root>\|…`, exit 3, no runner started |
| D4 | ancestry backstop "records the holder's pid and start time" | no process-ancestry code; `proc_linux.go` already reads `/proc/<pid>/stat` through the injectable `readStat`; darwin uses `/bin/ps` | **Adapt.** Linux: `/proc/<pid>/stat` field 4 (ppid) and 22 (starttime ticks). Darwin: one `ps -A -o pid=,ppid=,lstart=` snapshot under `LC_ALL=C`. Other unix: no implementation → fail closed (`recursion-unverifiable`) |
| D5 | carried fact: hang guard unexported in `runner` | t1854_5 (inbox note, verified): `hangguard.Isolated`; `runner` keeps `isolated(t, hangLimit)`; `runner` is in `tripwirePackages` with starters `Run`, `Load`, `sweepSession` | **Adapt.** Every new process-starting test starts `if !isolated(t, hangLimit) { return }`; pure tests stay unguarded (a guarded test with no process start fails the tripwire). No tripwire entry change is needed |
| D6 | "goengines' own suite under an active marker → green" | nothing sets a marker in tests | **Adapt.** `runner`'s new `TestMain` exports the enclosing repository's identity as `AIT_TESTMAP_ACTIVE` for the whole package run, so every runner test runs under an active marker. Plus a one-off full-suite run under the marker (Verification) |
| D7 | cmd `run.go` "the error line" | `reportError` is in `scancheck.go` | `run.go`: doc comment only; the print is in `reportError` (D2) |

**Plan review (user, 2026-10-22), each verified and adopted:** (1) a post-run
hook receives `Run`'s context while the holder record is held, the own pid was
excluded and the marker lives only in child environments, so a hook calling
`Load` was admitted → context detector; (2) a walk that ended at a vanished
intermediate could admit an `env -i` nested run → restart + two-identical-walks
rule, else unverifiable; (3) the checkout has no `aitestmap/`, so a real-repo
parity run never reaches the guard → configured-fixture evidence added;
(4) the exported marker omitted context-held identities, so Run(A) → Run(B)
dropped A from B's runner processes → marker = inherited ∪ context ∪ identity,
with a cross-repository test.

Touched files: `runner/{run,repo}.go` and new `runner/recursion*.go` (this
task, named extension of M3.1); `cmd/ait-testmap/{run,scancheck}.go` (named
extension: the error line); `goengines/README.md`. All are this task's or a
named extension of their owner.

## Design

### Identity
`runner.Identity(ctx, root) (string, error)`: `git rev-parse --git-common-dir`
through `gitx.Repo{Dir: root}` (scrubbed env, so `GIT_DIR` cannot redirect it);
a relative answer is joined to `root`; then `filepath.EvalSymlinks`. A linked
worktree answers the main repository's `.git`, so it gets the same identity.

### Marker
`AIT_TESTMAP_ACTIVE` = the active identities, `:`-joined, each with `%` → `%25`
and `:` → `%3A` (a path may contain `:`). `ParseActive` refuses a bad escape,
an empty item or a relative path (fail closed: `recursion-unverifiable`).

### The guard (`enterGuard(ctx, root) (context.Context, *guard, error)`)
Runs after `LoadConfig` / `registry.LoadConfig` (a repository with no
`runners.yaml` starts no runner and keeps its current errors) and before the
first `loadRunner`, so before any runner process. Three detectors, one per way
a nested entry can arrive:
1. identity; failure → `RecursionError{Unverifiable}`.
2. **context (in-process re-entry):** the context carries the identities this
   request already holds (`withActive(ctx, set)` / `activeIn(ctx)`). Identity
   present → `RecursionError{Via: "context"}`. `Run` passes the guarded context
   to `load`'s describe/list, to `Executor.Execute` (so `invoke`) and to
   `runHooks`, so a post-run hook or an executor calling `Load` / `Run` with the
   context it received is refused before any describe. An **independent**
   in-process call (its own context) is not nested and is allowed: a
   process-wide rule could not tell the two apart. Residual: a hook that drops
   its context for `context.Background()` is seen as independent (README: hooks
   and executors must pass the context they were given).
3. **marker (child processes):** parse the inherited `AIT_TESTMAP_ACTIVE`;
   identity present → `RecursionError{Via: "marker"}`.
4. **ancestry (cleared environment):** read every holder record in
   `<identity>/ait-testmap/active/`, then take a **stable walk** of this
   process's strict ancestors (below). A holder whose `(pid, start)` is on the
   walk → `RecursionError{Via: "ancestor:<pid>"}`. A holder whose pid is gone or
   whose start differs is provably stale and is removed; an unreadable record is
   kept. The engine's own pid is not on the walk (in-process re-entry is the
   context detector's job), so a concurrent non-ancestor run is unaffected.
5. register this entry: `{pid, start, root}` JSON, written to a temp file and
   renamed to `h-<pid>-<unixnano>` (atomic; unique per entry, also in-process).
6. return the guarded context `withActive(ctx, activeIn(ctx) ∪ {identity})` and
   `guard{identity, marker, release}`, where the exported **marker =
   inherited `AIT_TESTMAP_ACTIVE` ∪ `activeIn(ctx)` ∪ {identity}** (order kept,
   deduplicated). So an in-process Run(A) → Load/Run(B) exports both A and B to
   B's describe/list/run, and a child of B entering A is refused by the marker
   detector, not only by ancestry (which the pre-subreaper orphan case can
   defeat). Lifetimes: the context set lives as long as the call that carries
   it; the marker exists only in the environments of this entry's runner
   processes; the engine's own environment is never changed.
   `release` removes the own record (best effort; a leftover is pruned later).

**Stable walk.** One lookup `lookupProc(pid) (procFact{ppid, start}, procState, error)`
(an injectable package var), `procState` ∈ {found, gone, foreign}. A walk starts
at this process (its own stat gives the first ppid, never a separately sampled
`os.Getppid()`) and follows `ppid` to pid 1 / 0.
- **gone** mid-walk (ESRCH/ENOENT and `kill(pid, 0)` = ESRCH) means the chain
  changed under the walk: a launcher exited and its child was reparented, possibly
  straight to the outer engine once t1854_6's subreaper exists. The walk is
  **restarted** from this process — never truncated.
- **foreign** (stat unreadable or absent but `kill(pid, 0)` = EPERM: a live
  process of another user under `hidepid`) is a verified end of what can be seen:
  the walk stops there (README residual: an ancestor of another user hides the
  chain above it; the engine of the same user above it would be invisible).
- any other error → unverifiable.
- a completed walk is accepted only when the **next** complete walk is identical
  (same `(pid, ppid, start)` links); otherwise walk again. At most 5 walks; no two
  consecutive identical complete walks → `RecursionError{Unverifiable, Detail:
  "ancestry unstable"}`. A walk longer than 4096 links (a cycle) → unverifiable.
- darwin: each walk takes a fresh `ps` snapshot; a ppid absent from the snapshot is
  **gone** (restart), same stability rule.

`RecursionError{Root, Via, Detail string; Unverifiable bool}` implements
`Error`, `Line` and `ExitCode` (3): `RUN_ERROR:recursion|<root>` or
`RUN_ERROR:recursion-unverifiable|<root>|<detail>`. `Via` is for diagnostics
and tests only; it is not on the line (the criterion pins the line).

Platform files: `recursion_linux.go` (`procStart(pid) (ppid int, start string, err error)`
via `readStat`), `recursion_darwin.go` (ps snapshot), `recursion_other.go`
(error). The lookup goes through a package var so tests can fault-inject.

## Implementation steps

1. **`runner/recursion.go`** (new): `ActiveEnv`, `Identity`, `ParseActive`,
   `FormatActive`, `RecursionError`, `guard`, `enterGuard`, holder read / write /
   prune, `ancestors`. Plus the three platform files above.
2. **`runner/repo.go`**:
   - `Repository.Identity string` (set from the guard; M4.5 / M5.1 read it).
   - `Runner.active string`; `command()` drops any inherited `AIT_TESTMAP_ACTIVE=`
     from `env` and appends `AIT_TESTMAP_ACTIVE=<r.active>` when `r.active != ""`,
     so describe, list and run (builtin and script) all carry it.
   - Split `Load` into `load(ctx, root) (context.Context, *Repository, func(), error)`,
     which reads both configs, enters the guard, loads the runners (describe/list
     under the guarded context) with `active` set, and releases on its own error
     path; `Load` = `load` + immediate release.
3. **`runner/run.go`**: `Run` calls `load` and `defer release()`, so the holder
   record spans discovery, execution and the post-run hooks; it uses the guarded
   context returned by `load` for `exec.Execute` and `runHooks`.
4. **`cmd/ait-testmap/scancheck.go`** `reportError`: `errors.As(err, &*runner.RecursionError)`
   before the generic `lineError` branch. **`run.go`**: document the refusal lines
   in `runRun`'s comment.
5. **Tests — `runner/recursion_test.go`** (process-starting ones `isolated`):
   - `runner/recursion_main_test.go`: `TestMain` — argv `__nested_engine check|run`
     makes the test binary a minimal engine in its cwd (`Load` / `Run --all`;
     prints the error `Line()` and `VIA:<via>` on stderr, exits with the
     `ExitCode`/`rep.Exit()`), so no `go build` is needed and the dispatch works
     under `env -i` (argv, not env). Otherwise it exports the enclosing
     repository's identity in `AIT_TESTMAP_ACTIVE` (D6; skipped when not in a
     git checkout) and runs `m.Run()`. The nested call clears `AIT_HANGGUARD_ISOLATE`.
   - `recursionCase{name, origin (discovery|execution), verb (check|run), wrap (sh|bash|python), clear (env -i, PATH kept), target (same|worktree|fixture), want (refused|allowed)}`,
     `recursionCases()` and `checkRecursion(t, c)` — exported to the package so
     t1854_6 can loop them over its boundary backends. A fixture runner script
     nests once (guarded by `mkdir "$D/nest.once"`, so a disabled guard yields a
     wrong exit, never a fork bomb), records the nested stdout/stderr/rc, and logs
     every `describe` with `$$`. The outer entry is the in-process `Load` (discovery)
     or `Run` (execution). Assertions: refused → rc 3, stderr line exactly
     `RUN_ERROR:recursion|<target root>`, `VIA:` = `marker` (or `ancestor:<pid of
     the outer>` under `env -i`), no extra `describe` logged; allowed → nested rc
     0/2 and its runner ran.
   - `TestRecursionGuard` runs the table: execution × {sh, bash, python} ×
     {marker, env -i} on the same repo; discovery × {check, run} × {marker, env -i};
     worktree × {marker, env -i}; fixture × {discovery, execution} × {marker, env -i}
     → allowed. python3 missing → skip (fail under `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1`).
   - `TestGuardRefusesBeforeAnyRunnerStarts`: `t.Setenv(ActiveEnv, identity)` →
     `Load` and `Run` return `*RecursionError`; no `describe` logged, no
     `.aitask-testmap/runs/` dir, no holder record left.
   - `TestMarkerReachesEveryRunnerProcess`: describe/list/run each record
     `$AIT_TESTMAP_ACTIVE`; equals inherited ∪ identity.
   - `TestCrossRepositoryMarker`: fixtures A and B. A post-run hook of `Run(A)`
     calls `Run(ctx, B)` with the context it received → allowed (B ≠ A); B's
     describe, list and run each record a marker containing **both** A and B
     (plus the inherited TestMain identity); B's run arm then calls the nested
     engine on A (marker kept, PATH etc. inherited) → `RUN_ERROR:recursion|<A>`
     with `VIA:marker`. A second variant removes A's holder record before that
     nested call, so only the marker can refuse it.
   - `TestConcurrentNonAncestorUnaffected`: a nested-engine child running a
     `run` that blocks on a FIFO holds a record; the test process's own `Load`
     of the same repo succeeds; then the FIFO is released.
   - `TestInProcessReentry`: a one-shot post-run hook (registered for the test
     via `withHooks`) calls `Load(ctx, root)` with the context it received →
     `*RecursionError{Via: "context"}`, and no `describe` beyond the outer run's
     is logged; an `Executor` stand-in doing the same inside `Execute` → refused.
     Meanwhile an independent goroutine `Load(context.Background(), root)` of the
     same repo while that `Run` is blocked (FIFO in its runner) → allowed.
   - `TestAncestryWalk` (pure, fake `lookupProc`, unguarded): an intermediate
     that vanishes in the first walk, the second and third walks showing the
     reparented chain self → holder → 1 → refused `ancestor:<holder>` (never
     admitted on the truncated walk); a chain that changes on every walk →
     `ancestry unstable`; a foreign ancestor ends the walk (holder above it not
     seen, allowed); a cycle → unverifiable; an unexpected lookup error →
     unverifiable.
   - `TestHolderRecords`: a holder naming a live non-ancestor (`sleep` child) →
     allowed and kept; dead pid → pruned; same pid, other start → not matched,
     pruned; records removed on release and after an error return.
   - `TestGuardUnverifiable`: injected ancestor lookup error; malformed marker;
     non-git root with a `runners.yaml`; empty `PATH` nested case → `recursion-unverifiable`.
   - `TestActiveMarkerFormat` and `TestIdentity` (worktree + symlinked root same,
     another fixture different; this one starts git → `isolated`).
   - **cmd**: `TestRunAndCheckRecursionLine` in `cmd/ait-testmap/run_test.go` —
     fixture with a runner, `t.Setenv` the marker: `run --all` and `check` each
     print exactly `RUN_ERROR:recursion|<root>` on stderr, nothing on stdout, exit 3.
6. **Red proofs** — one isolated mutant at a time, each restored byte-identical
   (`cmp` against a saved copy), each showing a guard-specific failure:
   context check off; guarded context not passed to hooks; context identities
   left out of the exported marker; marker check off;
   ancestry check off; walk truncates on gone instead of restarting; stability
   check off; export in `command()` off; identity = `root` instead of the common
   dir; holder registered after the runners load; self counted as an ancestor /
   pid-only match; unverifiable fails open; `reportError` branch removed.
7. **README** (`goengines/README.md`): new Interfaces row "recursion guard (M3.2d,
   G9)" (identity, marker format, holder registry path and record, refusal lines,
   residuals, pinned-by tests); add `AIT_TESTMAP_ACTIVE` to the "runner invocation"
   row's env list; G9 row of the evidence contract points to the new row.
8. **Owner notes** (`/aitask-note`, at implementation time): t1856 (M5.1:
   `aitask_test.sh` enters through the guarded engine first, never strips
   `AIT_TESTMAP_ACTIVE`, its tests use fixture repos); t1855 (M4.5: the `test`
   verb goes through `runner.load`'s guard); t1854_6 (the parameterizable
   `recursionCases` / `checkRecursion`, and that the ancestry chain relies on
   reparenting to the engine — its subreaper makes orphaned/`setsid` descendants
   visible); t2119 (pid-namespace backend: holder `(pid, start)` are host-namespace
   values, no mapping).

### Post-phase (risk mitigations)

1. [real_repo_check_parity] Build the engine (`go build -o "$SCRATCH/ait-testmap.new" ./cmd/ait-testmap`).
   (a) **Compatibility, real checkout:** from the repository root run `check`
   and `scan` (no `--apply`) with the new and the installed engine; stdout,
   stderr and exit must be identical. The checkout has **no `aitestmap/`**
   (verified 2026-10-22), so this only shows the early paths are unchanged;
   it is not evidence that the guard ran.
   (b) **Guard exercised, configured fixture:** a scratch git repository with
   `aitestmap/contract`, a `runners.yaml` and one runner script whose `describe`
   and `list` append `$$`, `$AIT_TESTMAP_ACTIVE` and `ls <common-dir>/ait-testmap/active/`
   to a log outside the repo. Run the new binary's `check`, `scan` and `run --all`
   there twice — with no marker, and with `AIT_TESTMAP_ACTIVE=<an unrelated
   repository's identity>`. Each must exit as the installed engine does on the
   same fixture (same stdout), and the log must show discovery ran, exactly one
   holder record present while it ran, the marker = inherited ∪ fixture identity,
   and the `active/` directory empty afterwards. Record commands and results in
   Final Notes.
2. [darwin_ps_parser_test] Put the darwin `ps -A -o pid=,ppid=,lstart=` parser
   (`parsePsAncestry(out string) (map[int]procFact, error)`) in a file with no
   build tag (`recursion_ps.go`), so `recursion_darwin.go` only runs `ps` and
   calls it. Add `TestParsePsAncestry` (pure, unguarded): well-formed rows,
   `lstart` keeps its five fields verbatim as the start token, a malformed or
   short line and a duplicate pid are errors, blank lines skipped.

**Residuals (README + Final Notes):** without t1854_6's subreaper, a descendant
orphaned before it nests is reparented away and escapes the `env -i` backstop
(the marker still catches it); darwin ancestry is compile-checked only (no
macOS CI, no darwin host); a read-only git common dir makes `run` / `check` fail
closed.

## Verification

- `cd goengines && go vet ./... && go test ./internal/testmap/runner/ ./cmd/ait-testmap/ ./internal/testmap/cost/`
- Full suite under an active marker:
  `AIT_TESTMAP_ACTIVE="$(cd goengines && realpath "$(git rev-parse --git-common-dir)")" go test ./...` → green.
- `GOOS=darwin go vet ./...` (compile check of `recursion_darwin.go`).
- `bash goengines/ci/preflight.sh` (tripwire) and `ait engine test` → green.
- Red proofs per step 6, each failing for its own reason and restored.

## Risk

### Code-health risk: low
- The guard sits on the entry every `scan` / `check` / `run` (and so every testmap gate) goes through; a false refusal or an over-eager fail-closed path would break all of them · severity: low (residual — addressed by inline post-phase real_repo_check_parity) · → mitigation: inline post-phase real_repo_check_parity
- The darwin ancestry path cannot be exercised here (no macOS host, no macOS CI) · severity: low (residual — the parser is tested on Linux; only the `ps` call is unexercised) · → mitigation: inline post-phase darwin_ps_parser_test
- Holder records in the git common dir: stale-record pruning races a fresh registration · severity: low · → mitigation: none (pruning removes only a record whose `(pid, start)` is provably not alive; records are published by rename)

### Goal-achievement risk: medium
- The `env -i` backstop follows the parent chain; until t1854_6's subreaper lands, a descendant orphaned before it nests is reparented away and escapes it (the marker still catches it whenever the env is inherited) · severity: medium · → mitigation: none (owned by t1854_6; note sent; README residual)
- In-process re-entry is detected through the context; a hook or executor that discards its context for `context.Background()` looks like an independent call · severity: low · → mitigation: none (README contract for hooks/executors; the only in-tree hook, `cost.Hook`, does not call `Load`)
- A live ancestor of another user (hidepid) hides the chain above it from the `env -i` backstop · severity: low · → mitigation: none (README residual; refusing there would break every entry under `hidepid=2`)
- Deviations D1 (holder registry in the git common dir instead of a lock under `.aitask-testmap/`) and D3 (`env -i` cases keep `PATH`) could be read as missing the literal criterion · severity: low · → mitigation: none (decided in Step 0 with the reason recorded)

### Planned mitigations
- timing: post-phase | name: real_repo_check_parity | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: false refusal / fail-closed on the scan-check-run entry | desc: compare check/dry scan with the installed engine on the real repo (no aitestmap/: compatibility only), and on a configured fixture with no marker and an unrelated marker, logging discovery, holder registration and release
- timing: post-phase | name: darwin_ps_parser_test | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: untested darwin ancestry path | desc: untagged ps-snapshot parser with a Linux-run table test

## Final Implementation Notes
- **Actual work done:** G9 runtime recursion guard as planned. `runner/recursion.go` (identity, marker format, `RecursionError`, context entries, holder records, stable ancestry walk) + `recursion_linux.go` (`/proc/<pid>/stat` ppid / starttime, `kill(pid,0)` gone/foreign classification), `recursion_darwin.go` (one `ps -A -o pid=,ppid=,lstart=` snapshot per walk), `recursion_ps.go` (untagged ps parser), `recursion_other.go` (fail closed). `repo.go`: `Load` = `load` + release; `load` reads both configs, enters the guard, then `loadGuarded`; `Runner.marker func() string` sets `AIT_TESTMAP_ACTIVE` in `command()` (inherited one dropped); `Repository.Identity`. `run.go`: `Run` holds the guard from discovery through the hooks and passes the guarded context to the executor and hooks. `cmd/ait-testmap/scancheck.go` `reportError` prints a `*runner.RecursionError` line before the generic branch (scan/check wrap lister errors in `INPUT_ERROR`); `run.go` doc. README: new Interfaces row "recursion guard (M3.2d, G9)", `AIT_TESTMAP_ACTIVE` in the runner-invocation row, G9 row of the evidence contract.
- **Deviations from plan:** (1) context entries carry a `done` flag ended at release and the marker is computed per process start from the caller's still-live entries (review CR1); the guard keeps only the caller's entry pointers, not its context (CR2). (2) Holder records are read through `readReport` (64 KiB, no symlink/FIFO/non-regular) and an unreadable record is never skipped silently (name-pid rule, CR1). (3) `nestedEngine` keeps `AIT_HANGGUARD_ISOLATE` (CR1). (4) `stableWalk` takes the view factory as a parameter, so the pure `TestAncestryWalk` never references the platform view (the lexical tripwire would otherwise see darwin's `exec.Command` and demand the hang guard).
- **Issues encountered:** `Identity(".")` returned a relative path (TestMain passes "."): fixed with `filepath.Abs` before `EvalSymlinks`. An empty `( )` subshell in fixture scripts is a bash syntax error (nest default is `:`). A FIFO-based test gate deadlocked when no reader appeared — replaced by a polled gate file. The installed v0.39.0 engine is older than t1854_2, so parity uses an engine built from `HEAD` via `git archive` (no stash).
- **Key decisions:** D1 holder registry in `<git-common-dir>/ait-testmap/active/` (concurrent runs never block; covers every worktree under `env -i`); D3 `env -i` cases keep `PATH`, a no-`PATH` case pins the unverifiable path; refusal line stays exactly `RUN_ERROR:recursion|<root>` (detector in `RecursionError.Via` only).
- **Verification evidence (durable):**
  - `./ait engine test` → exit 0 (vet, `ci/preflight.sh` tripwire, full suite); `AIT_TESTMAP_ACTIVE="$(realpath "$(git rev-parse --git-common-dir)")" go test ./...` in `goengines/` → exit 0; `GOOS=darwin go vet ./internal/testmap/runner/` and `GOOS=freebsd go build ./...` → ok.
  - Red proofs (scratch driver applying one textual mutant at a time, running `go test ./internal/testmap/runner/ -run <recursion tests>` or the cmd test, restoring and byte-comparing): all 18 RED and restored — context check off; guarded context not passed on; context ids left out of the marker; marker check off; ancestry check off; walk truncates on gone; stability check off (`if prev != nil || true`); export in `command()` off; identity = root; holder registered after the runners load (record renamed away during `loadGuarded`); self counted as an ancestor; pid-only match; unverifiable ancestry fails open; `reportError` branch removed; release keeps the context entry; marker fixed at entry; unreadable records skipped; records read through `os.ReadFile` (FIFO → HANG).
  - real_repo_check_parity: (a) real checkout `check` / `scan`, new vs `HEAD`-built engine → identical (`TESTMAP_ABSENT`, rc 2; compatibility only). (b) scratch git repo with `aitestmap/registry/config.yaml`, `runners.yaml` and a logging `shell.sh`; `check`, `scan`, `run --all` with no marker and with `AIT_TESTMAP_ACTIVE=/home/ddt/Work/aitasks/.git` → stdout/stderr/rc identical to the `HEAD` build; every new-engine runner call logged `holders=1` and marker = inherited ∪ fixture identity; 0 records left.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - t1854_6: `recursionCases()` / `checkRecursion(t, c)` are the table to run per boundary backend; the outer entry is the in-process test process, the nested engine is the test binary via `__nested_engine check|run` (argv dispatch in `TestMain`, works under `env -i`). The `env -i` backstop follows the parent chain: the subreaper is what keeps an orphaned/`setsid` descendant's chain reaching the engine. Holder `(pid, start)` are host-namespace values (t2119).
  - Any in-process caller (hook, executor, M3.3 scheduler) must pass the context it received to `Load` / `Run`; an independent `context.Background()` call is treated as independent.
  - New process-starting tests in `runner` take `isolated(t, …)`; a pure test must not reference `newProcView` (lexical tripwire).
  - `runner` tests run under `AIT_TESTMAP_ACTIVE` = the enclosing repo identity (TestMain); assertions on runner env must account for it.
  - Adapters record what they read (t2082): the guard reads `git rev-parse --git-common-dir` in `root`, `AIT_TESTMAP_ACTIVE`, and `<common-dir>/ait-testmap/active/`.

## Step 9 reference

Post-implementation follows task-workflow Step 9 (current branch, no merge).

## Post-Review Changes

### Change Request 1 (2026-10-23 00:30)
- **Requested by user:** four review findings, each verified (CONFIRMED) and addressed:
  1. `withActive` stored a permanent identity slice, so a hook that kept its context past `Run` was refused by `Load(saved, root)` after the entry had been released.
  2. `readHolders` silently skipped a malformed or invalid record, so replacing an ancestor's record with garbage admitted the nested entry.
  3. `readHolders` used `os.ReadFile` on every `h-*` entry: a FIFO named `h-*` blocked the engine before discovery.
  4. (follow-up) the nested-engine test helper unset `AIT_HANGGUARD_ISOLATE`, hiding its runner processes from the watchdog's cleanup.
- **Changes made:**
  1. The context carries `*ctxEntry{id, done atomic.Bool}`; `guard.release` sets `done`; `activeIn` / `liveEntries` drop released entries. The marker is now `guard.marker()`, computed when each runner process starts (`Runner.marker func() string`), from the inherited identities, the caller's still-live entries and this identity — so a process started after an outer release does not carry it.
  2. A record is `valid` only when read, decoded, `pid` agreeing with its `h-<pid>-<unique>` name, and `start` non-empty. An invalid record naming one of this process's ancestors → `recursion-unverifiable`; naming a live non-ancestor → irrelevant (kept); naming a gone pid → pruned. A name that is not `h-<pid>-<unique>` → unverifiable.
  3. Records are read through `readReport(path, holderMax = 64 KiB)` (O_NOFOLLOW, O_NONBLOCK, regular file only, bounded); an absent file is still "released meanwhile".
  4. `nestedEngine` keeps an inherited `AIT_HANGGUARD_ISOLATE` (TestMain dispatches before `m.Run`, so it cannot trigger an isolation).
  New tests: `TestReleasedContext` (saved context after release; a Run(B) outliving Run(A) whose run process starts after A's release), `TestUnreadableHolderRecords` (malformed, FIFO, symlink, directory, oversized, pid/name mismatch, no start, unnamed → unverifiable; unreadable records of a live non-ancestor kept, of a gone pid pruned; no read blocks). Four more mutants (release keeps the entry, marker fixed at entry, unreadable records skipped, records read unbounded).
- **Files affected:** `goengines/internal/testmap/runner/{recursion.go,repo.go,recursion_test.go,recursion_main_test.go}`, `goengines/README.md`.

### Change Request 2 (2026-10-23 01:00)
- **Requested by user:** the guard kept the caller's whole `context.Context` (and each Runner the bound `g.marker`), so a retained `Repository` / `RunReport.Repo` pinned the caller's context value chain after release (CONFIRMED, follow-up).
- **Changes made:** `guard.callers []*ctxEntry` (the caller's entries live at entry) replaces `guard.parent context.Context`; `marker()` filters them with `liveIDs`, so release still drops them dynamically. `withActive(ctx, append(slices.Clip(held), e))` so the context's slice never shares a backing array with `g.callers`.
- **Follow-up cleanup:** removed `activeIn`, left unused by this change (`liveEntries` / `liveIDs` cover both uses).
- **Files affected:** `goengines/internal/testmap/runner/recursion.go`.
