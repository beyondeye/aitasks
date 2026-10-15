---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: test
status: Implementing
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
followup_kind: risk_mitigation
implemented_with: claudecode/opus5_5
created_at: 2026-10-15 08:56
updated_at: 2026-10-15 22:53
---

## Origin

Risk-mitigation ("after") follow-up for t1985, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — future process-starting runner tests omitting the isolated() guard

- New process-starting tests added later can omit the guard, silently reopening the suite-timeout hang for them. "Every process-starting test" holds only for today's tests · severity: medium · → mitigation: isolation_tripwire

## Goal

t1985 runs every process-starting test of
`goengines/internal/testmap/runner` under a hang watchdog. Each such test
starts with

```go
if !isolated(t, hangLimit) {
	return
}
```

and is then re-executed in a subprocess with its own deadline, a `HANG:`
report and marker-based cleanup (`watchdog_unix_test.go`,
`watchdog_linux_test.go`). The guard is a convention: nothing stops a new
test that drives `Run` from omitting it and hanging the suite again.

Add a source tripwire test, in the style of the module's
`TestInvariant5Tripwire` / `TestInvariant5TripwireCatches` in
`goengines/guards_test.go`:

- Parse the runner package's `_test.go` files with `go/ast`. For every
  top-level `Test*` function, compute whether it reaches a process-starting
  call, transitively through package-level helper functions: `Run`,
  `runAll`, `timedRun`, `Load`, `registry.Scan`, `registry.Check`,
  `execRunner`, `sweepSession`, `startSession`, `exec.Command` /
  `exec.CommandContext`, `newRepo` / `fixture.New`, and the fixture helpers
  built on them (`batchRepo`, `threeRepo`, `provRepo`, …).
- Fail when such a test's **first statement** is not the `isolated(t, …)`
  guard.
- An explicit allowlist with reasons for the watchdog's own controls, which
  start processes but must not isolate themselves: `TestIsolationControls`
  and `TestReapMarkedUncertainty`.
- A negative control proving the tripwire catches: an unguarded test that
  calls `runAll` directly, one that reaches it through a helper, and one
  whose guard is not the first statement. Plus a benign case, a pure test,
  which must not be flagged.
- Survey at creation (t1985): 33 guarded tests, 20 pure unguarded ones,
  2 allowlisted controls, and `TestChildRunPattern` (pure). The tripwire
  must pass on that tree, and fail when a guard line is removed (red proof).

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1993** id=2026-10-15T12:02:52Z.43cc59358a1a61aa3833f568 from=t1993 from_verified=yes at=2026-10-15T12:02:52Z base=cbfc74fed97d56da9204ea726daa43e69323b943 base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1993 (bounded read of the watchdog's subprocess output), as of commit cbfc74fed. Tree-relative claims only; check them against your own tree.
> | 
> | t1993 adds test code to the files your tripwire parses:
> | - watchdog_unix_test.go: new top-level `TestScanOutput`. It is pure: it calls only `scanOutput` over in-memory readers (strings.Reader, testing/iotest wrappers, a generated `xs` reader). It starts no process and calls none of the process-starting functions your task lists. It also adds the non-test helpers `scanOutput` (a chunked io.Reader scanner used by runChild) and the type `xs`.
> | - watchdog_linux_test.go: a new `noisy` subtest inside the allowlisted `TestIsolationControls` (it calls `runChild`, as its sibling subtests do), and a `noisy` mode in `controlFixture`.
> | 
> | Possible effect on t1998: the creation-time survey in your task body ("20 pure unguarded ones", plus `TestChildRunPattern`) now has one more pure unguarded test. If the tripwire or its tests hardcode that count, it is off by one at this SHA. The guarded and allowlisted counts are unchanged.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-15T19:53:28Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-15T21:00:21Z status=pass attempt=1 type=human
