---
priority: low
effort: low
depends: []
issue_type: bug
status: Postponed
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
followup_kind: upstream_defect
created_at: 2026-10-25 09:00
updated_at: 2026-10-30 12:10
---

## Origin

Spawned from t1854_6 (M3.2c supervised execution) during Step 8b review.

## Upstream defect

- `goengines/internal/testmap/runner/exec_unix.go:execUnsupervised` — the darwin (unsupervised) path sweeps the runner's session after `cmd.Run` has reaped the runner, so the session number can in principle have been reused by an unrelated session (pre-existing M3.1 behaviour, kept unchanged by t1854_6 and documented as a residual of the unsupervised path).

## Diagnostic context

t1854_6 moved Linux execution onto a dedicated per-start supervisor (`internal/procsup`). Two review findings there established that a session-number sweep is sound only while the session is known to still have its original members:

- After the runner has been reaped, nothing pins the session id.
- If every member is gone, the number can be reallocated, and the sweep's `sid == S` then identifies whichever session holds the number now.

On Linux the engine therefore never signals by session number. The darwin path (`procsup.Available()` fails; no `PR_SET_CHILD_SUBREAPER`) still runs M3.1's `execUnsupervised`: `exec.CommandContext` + `Setsid` + `cmd.Run()` (which reaps the runner), then `sweepSession(cmd.Process.Pid, SweepTimeout)`. `procsup.SweepSession` documents the precondition.

Production builtin adapters refuse on darwin (`CONTAINMENT_UNAVAILABLE`), so this affects only project script runners there. darwin is compiled and vetted only (no CI execution).

## Suggested fix

Keep the session pinned until the sweep is done: start the runner without letting os/exec reap it (e.g. `os.StartProcess` + a sweep loop that runs while the leader is still an unreaped zombie, then `wait4` the leader last), or sweep only members that are confirmed descendants. Pin it with a darwin-only test, plus a code-level assertion on Linux CI that the sweep runs before the reap.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t15** id=2026-10-25T08:55:07Z.cafd647832b5685f44b52dc5 from=aitasks_go#t15 at=2026-10-25T08:55:07Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
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

> **✉ note:t22_3** id=2026-10-29T22:24:28Z.1d4a3d019ae5c7dfda133c83 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:24:28Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:12:42Z.60200cd174b80c7a2f0e0319 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:12:42Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | Re-homed: the engine work of this task moved to aitasks_go#t78
> | (beyondeye/aitasks_go). This task is Postponed as a pointer and must not be
> | picked. History of its completed siblings: aitasks_go
> | aidocs/aitasks_go/testmap_history/.

> **✉ note:t22_4** id=2026-10-30T10:17:06Z.a80dffd66f3a5554b6317682 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:17:06Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | goengines freeze lifted (aitasks_go#t22 cutover complete).
> | Public goengines/ is now an export target: never edit it here; changes
> | arrive from beyondeye/aitasks_go via promote/export.sh.
> | - Engine work of this task now lives in aitasks_go#t78; this task is
> |   Postponed and kept only as a pointer.
