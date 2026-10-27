---
Task: t2160_fix_pytest_fake_evidence_race_hang.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2160 — TestPytestFakeEvidence "hang" under `go test -race`

## Context

t1854_12 found `TestPytestFakeEvidence` failing deterministically under
`go test -race` with `HANG:TestPytestFakeEvidence|2m0s`, stopping in the
writer-less-FIFO `Load` at `pytest_linux_test.go:856`. The task suspected the
FIFO path (`pytestReadOwn`, t1854_9 CR2) and left the root cause unproven.

**Root cause (proven in planning; not a FIFO bug, not an adapter bug):** the
race runtime sleeps `GORACE` `atexit_sleep_ms` (default **1000 ms**) before
every race-instrumented process exits. This test binary is every supervisor
and every builtin process (`builtin/main_test.go:24-27`), so each engine call
pays a sequential chain of 1 s exits: `describe` (supervisor + adapter) = 2 s,
`list` (supervisor + adapter + inner supervisor) = 3 s, `run` = 3 s. That is
about 8 s per subtest and 5 s per tail `Load`.

Evidence (all under `-race`, host load ~9–11):

| run | result |
|---|---|
| guarded, ×3 (as reported) | `HANG` at line 856, the FIFO `loadErr` (goroutine dump: engine in `procsup.(*Proc).Wait`, entered < 1 min before the kill) |
| live `ps` at 108 s | still progressing normally (a `describe` had just started); no stuck process |
| in-process (`AIT_HANGGUARD_ISOLATE='TestPytestFakeEvidence\|debug'`), no guard | **PASS in 121.57 s**: every subtest exactly 8.10–8.11 s (a timer, not CPU) |
| same, `GORACE=atexit_sleep_ms=0` | **PASS in 1.51 s**: every subtest 0.10 s |
| `TestPytestReadOwn` (FIFO unit test) | passes in 1 s |

8 s + 12 × 8.1 s + 3 × 5 s ≈ 120.2 s against the 120 s `pytestHangLimit`. The
FIFO `Load` is just the phase running when the budget ran out, which is why
every run failed at the same point. The same tax inflates every
self-re-executing package's race run (procsup, runner, builtin).

**Intended outcome:** hang-guarded tests run without the race runtime's exit
sleep, so `TestPytestFakeEvidence` (and the builtin package) is green under
`-race`. The hang limits stay as they are, so a real hang still fails at them.
An explicit `atexit_sleep_ms` in the parent's `GORACE` is honoured.

### Composition: prefix, and let the runtime's last assignment win

The runtime is left to parse `GORACE`; the plan reimplements none of its
grammar. A substring "is it already set?" check misreads text inside another
option's value (`strip_path_prefix=/work/atexit_sleep_ms=demo/`). A parser
mirroring the runtime's grammar would need a timing oracle to stay honest,
and that oracle can fail falsely on a loaded or paused host. Instead, the child
gets `atexit_sleep_ms=0 <parent options>`. Measured on the go1.27.2 race
runtime (exit time of a race-built test binary run with `-test.run='^$'`):

| parent `GORACE` → child `GORACE` | exit | |
|---|---|---|
| unset → `atexit_sleep_ms=0` | 0.009 s | default: no sleep |
| `halt_on_error=1` → `atexit_sleep_ms=0 halt_on_error=1` | 0.008 s | unrelated option kept |
| `strip_path_prefix=/work/atexit_sleep_ms=demo/` → prefixed | 0.008 s | the misleading value: no sleep |
| `strip_path_prefix="x atexit_sleep_ms=0 y"` → prefixed | 0.008 s | quoted value |
| `atexit_sleep_ms=250` / `halt_on_error=1,atexit_sleep_ms=250` → prefixed | 0.259 s | explicit override wins |
| `atexit_sleep_ms=1000` (also `… halt_on_error=1`, `  ,atexit_sleep_ms=1000`) → prefixed | 1.008 s | explicit override wins |
| `atexit_sleep_ms` / `strip_path_prefix="x` → prefixed | exit 66 | a refused parent stays refused |
| (control) unset parent, no prefix | 1.01 s | the default sleep |

The prefix is one complete option followed by a separator, so the parent's
options parse exactly as they would on their own.

## Approach

Fix it at the single choke point every guarded test's process tree starts
from: `hangguard.runChild` (`goengines/internal/testsupport/hangguard/hangguard.go:307`),
which already builds the subprocess env (`hangguard.go:337`). Every
descendant (supervisors, builtins, nested engines) inherits it. This covers
procsup, runner, builtin and hangguard (~160 isolated tests) without touching
five separate `TestMain`s. The pytest adapter and `pytestReadOwn` are correct
and stay unchanged.

### 1. `goengines/internal/testsupport/hangguard/hangguard.go`

Add, next to `runChild`:

```go
// childGORACE is the subprocess's GORACE entry: atexit_sleep_ms=0, then the
// parent's options. A race-instrumented process sleeps atexit_sleep_ms
// (default 1000) before it exits, and every process a guarded test chains —
// supervisors, builtins, nested engines — is this binary, so under -race each
// exit charges a second to limit: TestPytestFakeEvidence's chain measured
// 121.6 s against its 120 s limit, and 1.5 s without the sleep. The runtime
// applies GORACE's options in order, the last assignment winning, so a parent
// that sets atexit_sleep_ms keeps its value; the prefix is a complete option
// and a separator, so the parent's options parse as they would alone (one the
// runtime refuses stays refused). Go prints a race report where the race is
// detected and still exits 66; the sleep only gives goroutines still running
// after main returns a second more to race. A binary built without -race
// ignores GORACE.
func childGORACE(parent string) string {
	if parent == "" {
		return "GORACE=atexit_sleep_ms=0"
	}
	return "GORACE=atexit_sleep_ms=0 " + parent
}
```

In `runChild` (line 337):
`cmd.Env = append(append(append(os.Environ(), childGORACE(os.Getenv("GORACE"))), env...), "TMPDIR="+tmp, marker)`.
`os/exec` uses the last value of a duplicate key, so this overrides the
inherited `GORACE`, and a caller's `env` still wins. Add one sentence to the
package doc comment: the subprocess runs without the race runtime's exit sleep
unless the parent asks for one (see `childGORACE`).

### 2. Test: `goengines/internal/testsupport/hangguard/controls_linux_test.go`

An end-to-end check through the real `runChild`, under controlled parent
settings, asserting exact child values:
- `controlFixture`: a new mode `gorace` writes `os.Getenv("GORACE")` to
  `<dir>/gorace`.
- `TestIsolationControls`: a new subtest `gorace` with one
  `runChild(t, name, hangLimit, settings, controlEnv+"=gorace|"+dir)` per row.
  It sets the parent's variable first: `t.Setenv("GORACE", v)`, and for the
  unset row `t.Setenv` followed by `os.Unsetenv`, so cleanup restores it. The
  child's value must match exactly:

  | parent | child |
  |---|---|
  | unset | `atexit_sleep_ms=0` |
  | `halt_on_error=1` | `atexit_sleep_ms=0 halt_on_error=1` (option preserved) |
  | `strip_path_prefix=/work/atexit_sleep_ms=demo/` | `atexit_sleep_ms=0 strip_path_prefix=/work/atexit_sleep_ms=demo/` (the targeted regression) |
  | `halt_on_error=1,atexit_sleep_ms=250` | `atexit_sleep_ms=0 halt_on_error=1,atexit_sleep_ms=250` (override kept, after the prefix) |
  | `atexit_sleep_ms=1000` | `atexit_sleep_ms=0 atexit_sleep_ms=1000` |

  This fails if `runChild` stops injecting, injects anything but `0`, puts the
  prefix after the parent's options (an override would lose), skips the prefix
  on a misleading value, or drops the parent's options. Every row is
  runtime-valid, so it also passes under `-race`; the 1000 row's child sleeps
  1 s at exit, well inside `hangLimit`. The pure helper gets no separate unit
  test, because these rows pin its every output end to end.

### 3. `goengines/README.md`, the hang guard (M3.2b) row (line 365)

Append, current-state style: the subprocess, and everything it starts, runs
with `GORACE` prefixed by `atexit_sleep_ms=0`, because under `-race` every exit
of the re-executed binary would otherwise charge 1 s to `limit`. The runtime
applies the last assignment, so a parent's own `atexit_sleep_ms` still wins.
This is the race-mode note the task asked for. It goes on the hang guard row
rather than the pytest row because the pytest adapter behaves correctly; the
environment-specific fix lives in the guard.

Not changed: `pytestHangLimit`, `bashHangLimit` and their comments, the pytest
adapter, and the pytest README row.

## Verification

1. `gofmt -l` and `go vet ./internal/testsupport/hangguard/` are clean.
2. `go test -count=1 ./internal/testsupport/hangguard/` and the same with
   `-race`: the `gorace` rows plus the existing controls and tripwire pass.
3. Mutants, run in a scratch copy of `goengines/` (never in the shared
   worktree); each must fail the `gorace` subtest:
   - **M1** `runChild` without the `childGORACE` entry: fails the unset row.
   - **M2** append instead of prepend: fails every set-parent row (an
     override would lose).
   - **M3** skip the prefix when `strings.Contains(parent, "atexit_sleep_ms=")`:
     fails the misleading-value row (the targeted regression).
4. Fix proof: `go test -race -count=1 -v -run 'TestPytestFakeEvidence$' ./internal/testmap/runner/builtin/`
   passes through the guard (not debug mode), well under 120 s.
5. Negative control, and proof that an explicit override wins through the
   composition at runtime level:
   `GORACE=atexit_sleep_ms=1000 go test -race -count=1 -run 'TestPytestFakeEvidence$' ./internal/testmap/runner/builtin/`
   reproduces `HANG:TestPytestFakeEvidence|2m0s`.
6. The original failing command, green:
   `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1 go test -race -count=1 -timeout 45m ./internal/testmap/runner/builtin/`.
   Record the wall time against the earlier 666 s figure.
7. Blast radius (every isolated subprocess's env changes): `ait engine test`
   (go vet + go test over `goengines/`), plus
   `go test -race -count=1 -timeout 45m ./internal/procsup/ ./internal/testmap/runner/`.
8. `bash goengines/ci/preflight.sh`, if it runs locally (tripwire), passes.

Then Step 8 review/commit (`bug: … (t2160)`) and Step 9 post-implementation
archival, per the task workflow. The probe evidence above goes into the
archived plan's final notes verbatim.

## Risk

### Code-health risk: low
- Every isolated subprocess tree (procsup, runner, builtin, hangguard) gains a
  `GORACE` entry, so a test asserting an exact child environment could change
  · severity: low · → mitigation: none beyond Verification §2, §7 (a planning
  grep found no exact-env assertions in builtin; the full module runs in both
  modes)
- The composition relies on the runtime's last-assignment-wins rule (measured
  above). A Go release that changed it would make the prefix override a
  parent's explicit `atexit_sleep_ms`; the cost would be only a lost request
  *for* the sleep, never a slower or failing test · severity: low ·
  → mitigation: none: documented in `childGORACE`; Verification §5
  re-measures it
- Child processes lose the race runtime's 1 s post-`main` window, so a race by
  a goroutine still running after `main` returns in a child could go
  unreported · severity: low · → mitigation: none: an accepted tradeoff,
  documented in `childGORACE`; an explicit parent `atexit_sleep_ms` restores
  it

### Goal-achievement risk: low
- The task suggested fixing the FIFO open/read. The plan changes test support
  instead, because the measurements show the FIFO path never blocks
  (121.57 s → 1.51 s with only the knob changed) · severity: low ·
  → mitigation: none: Verification §4–6 reproduce both directions
