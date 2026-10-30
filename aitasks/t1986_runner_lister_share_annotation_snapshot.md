---
priority: low
effort: medium
depends: []
issue_type: performance
status: Postponed
labels: [testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
followup_kind: review_finding
created_at: 2026-10-14 17:26
updated_at: 2026-10-30 12:10
---

## Context

Review finding from t1854_1 (M3.1, runner contract), dispositioned as a
follow-up by the reviewer. In production `scan` / `check`, M2.1's
`registry.readInputs` (`goengines/internal/testmap/registry/inputs.go`)
already reads every annotation through `annot.Source{}.Annotations` before it
calls `Lister.List`. M3.1's `runner.Load`
(`goengines/internal/testmap/runner/repo.go`) then calls
`annot.Source{}.Annotations` again, for the `testmap:runner` overrides and
the `batch` / `needs` keys. Every `scan` / `check` therefore lists and parses
the repository's annotated files twice.

## Goal

One annotation read per operation, without changing any behaviour.

- **Option A:** a per-operation annotation snapshot that `readInputs` hands
  to the lister.
- **Option B:** an internal `runner.LoadWith(ctx, root, anns)` that accepts
  existing annotations. `Lister` would then need a way to receive them, and
  `UnitLister` is M2.1's interface, so any change to it is a named extension
  agreed with its owner.

Whichever option is taken:

- standalone `run` keeps loading its own annotations;
- the lister's fail-closed behaviour is unchanged (an annotation error is
  still `INPUT_ERROR`);
- `run` / `scan` / `check` outputs are byte-identical before and after.

## Verification

- A benchmark (`BenchmarkScanWithRunnerLister` or similar) recorded with
  `benchgate -update` shows the second parse gone.
- A test pins that `annot.Source` runs once per `scan` / `check` (a counting
  source injected through the same seam).
- `ait engine test` stays green.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1985** id=2026-10-15T05:57:51Z.f3c41ec6b704588068c40319 from=t1985 from_verified=yes at=2026-10-15T05:57:51Z base=a81352ffb83835a8bed91624f991841c01902cee base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1985 (hang watchdog for the runner package's tests), as of commit a81352ffb:
> | 
> | - In goengines/internal/testmap/runner, every test that starts a process (newRepo/fixture.New, Run, Load, registry.Scan/Check with Lister{}, exec.Command, …) now starts with
> |       if !isolated(t, hangLimit) {
> |           return
> |       }
> |   That runs it in a re-executed subprocess under a 20 s bound, with HANG:<test>|<limit> reporting and env-marker cleanup of its runner processes.
> | - If the "annot.Source runs once per scan/check" test you plan lands in package runner and builds a fixture repo, it likely needs this guard as its first statement. A counting seam set in the parent is not visible to the subprocess: set it inside the test body, which runs in the child.
> | - If the test lands in package registry instead, the helper is not available there (it is _test.go code of package runner), and today nothing equivalent exists in registry.
> | - Follow-up t1998 will add a tripwire that enforces the guard in package runner.

> **✉ note:t1998** id=2026-10-15T21:03:15Z.1076596da93eb1c9727f9334 from=t1998 from_verified=yes at=2026-10-15T21:03:15Z base=a669462a3cc2140f3fec671c5c9099a4d0dc27da base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1998 (hang-guard tripwire), as of commit b82f4becc. It updates the t1985 note you already carry. Not checked against your plan.
> | 
> | - The `if !isolated(t, hangLimit) { return }` convention is now ENFORCED in package goengines/internal/testmap/runner.
> |   - runner/isolation_tripwire_test.go fails any top-level test that reaches a process start without that exact guard as its first statement.
> |   - goengines/ci/preflight.sh runs the tripwire alone before `go test ./...`, in both workflows and `ait engine test`.
> | - Load is one of its hand-listed starters, in `localStarters` with Run and sweepSession, because Load reaches processes through methods (Runner.call, gitx.Repo{}.ListFiles) that name resolution cannot follow.
> |   - If your refactor renames Load or moves the process-reaching work behind a new package-level entry point, update localStarters in isolation_tripwire_test.go.
> |   - A renamed starter fails as "localStarters names X, which this package does not declare".
> |   - Guarded tests whose path the analysis can no longer see fail as "guarded, but the tripwire sees no process start".
> | - New tests that exercise the lister or Load through a real fixture (newRepo/fixture.New, registry.Scan with Lister{}) must start with the guard. Calls through methods, interfaces and func-typed fields are not followed.

> **✉ note:t15** id=2026-10-25T08:54:33Z.a05103ac90eb3c5bed3883cc from=aitasks_go#t15 at=2026-10-25T08:54:33Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
>
> | Coordination notice from aitasks_go (t15 ship-path decision; schedule in trail
> | art:trail-go-ship-path owned by aitasks_go#t22). Advisory context, not an
> | instruction. It does not change this task's scope.
> | 
> | WHAT IS PLANNED
> | ait-testmap Go development (public goengines/) will move ONCE into the private
> | aitasks_go repository, at a cutover performed by aitasks_go#t22. After that,
> | goengines/ here receives exported snapshots only (no tests, bench or ci), and
> | engine work happens in aitasks_go. As of 2026-10-25 the cutover has no date.
> | Its prerequisites are aitasks_go t20 and t21 and aitasks t2138.
> | 
> | UNTIL THE CUTOVER: CONTINUE THIS TASK HERE, AS NORMAL
> | To keep the cutover cheap and safe:
> | 1. Land goengines/ changes on main promptly. Avoid long-lived branches,
> |    worktrees or unmerged PRs touching goengines/, because the cutover has to
> |    wait for, or hand off, every one of them.
> | 2. Keep engine commits (goengines/**) separate from framework-side commits
> |    (the aitask_testmap.sh shim, installer/setup, skills, docs, aitestmap/).
> |    Mixed tasks will be split along that line, and separate commits keep both
> |    the split and the history migration clean.
> | 3. If goengines tests start reading data from outside goengines/ (as with the
> |    t1954 corpus under aidocs/testing_engine/), record that path in this
> |    task's plan. The migration must copy it into the private module.
> | 4. Add no new Go binary or non-testmap package to goengines/. ait-monitord is
> |    being re-homed to aitasks_go (aitasks_go#t23), and ait-tui is developed
> |    there.
> | 5. Keep the contracts and guards as usual: the dependency allowlist, the
> |    Invariant 4-5 tripwire, the hang guard, bench baselines, and the
> |    version/verb/exit-code interface. The migration carries them over verbatim
> |    and checks that nothing changed.
> | 
> | FREEZE PROTOCOL
> | Shortly before the cutover, aitasks_go#t22 will send this task a
> | "goengines freeze in effect" note. From that note until a matching
> | "goengines freeze lifted" note, do not claim or start goengines work here. A
> | task that is Implementing or locked at that time is never relocated under its
> | agent: t22 waits for it to land, or arranges an explicit checkpointed handoff
> | (commit/push, handoff note, release the lock, back to Ready).
> | 
> | AFTER THE CUTOVER
> | If this task still has engine work pending, it is re-homed to aitasks_go
> | (engine-only) or split (the Go part there, the framework part here), and the
> | original carries a pointer. Framework-side work (the shim, installer, skills,
> | docs, aitestmap/ and the n014 spec) stays in this repository permanently. An
> | emergency public fix to goengines/ after the cutover needs a
> | `Return-To: aitasks_go` trailer plus a return task in aitasks_go
> | (`ait create --batch --project aitasks_go`).

> **✉ note:t22_3** id=2026-10-29T22:23:24Z.1bf0f64b9473ed6a1fe87fcb from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:23:24Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:11:51Z.4dc391c010fd698077edbd63 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:11:51Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | Re-homed: the engine work of this task moved to aitasks_go#t67
> | (beyondeye/aitasks_go). This task is Postponed as a pointer and must not be
> | picked. History of its completed siblings: aitasks_go
> | aidocs/aitasks_go/testmap_history/.
