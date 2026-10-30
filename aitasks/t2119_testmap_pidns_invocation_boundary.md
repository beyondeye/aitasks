---
priority: low
effort: medium
depends: [t1854_6, t1854_7]
issue_type: feature
status: Postponed
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-21 22:07
updated_at: 2026-10-30 12:10
---

## Context

Split from t1854_6 (M3.2c, supervised execution) during the t1854 M3.2
re-decomposition (2026-10-21). G8a requires a per-invocation cleanup
ownership boundary that survives a builtin crash. t1854_6 ships only a cgroup
v2 leaf backend. Hosts without a delegated cgroup fall back to the engine's
subreaper tree and **run invocations serially** (`PARALLEL_REFUSED:containment`).

A PID-namespace backend would let those hosts run in parallel. It was deferred
because t1854_7's cleared-environment (`env -i`) recursion backstop compares
the outer engine's stored pid against the caller's ancestry. Inside a PID
namespace, pids, parent visibility and the `/proc` view all differ, and no
namespace-aware mapping existed.

## Acceptance criteria

- **A test hook forces the pidns backend** (unprivileged user and pid namespaces; on 2026-10-21 `unshare -U -r -p -f` worked on the reference host).
- **Namespace-aware recursion detection.** Map the outer run-lock holder across the namespace boundary, e.g. carry the holder's identity into the namespace, or check the namespace's own parent from outside. A cleared-environment nested `run` / `check` of the same repository, started from **execution** and from **discovery** inside the namespace, is refused.
- **A fixture-repository call from inside the namespace is allowed.**
- **Isolated cleanup.** t1854_6's overlap test (invocation A SIGKILLed with a `setsid()` descendant, B unaffected) passes under pidns.
- **It joins t1854_6's backend-parameterized recursion test.**
- **Only then** does `procsup.Boundary` enable pidns, only where unprivileged user namespaces work, and with `Overlappable()` true. Every other host stays `tree` / serial.
- **Docs.** README rows updated. `ait engine test` is green.

## Consumes

t1854_6 (`procsup.Boundary`), t1854_7 (the recursion guard).

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1854_7** id=2026-10-23T07:52:28Z.2c48314d627a31f130b9dbcc from=t1854_7 from_verified=yes at=2026-10-23T07:52:28Z base=ee468201fb47e48ead1fdab3019d6384bfaf8f23 base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1854_7 (M3.2d recursion guard, G9), landed in commit ee468201f. Not checked against your plan; re-verify in your Step 0.
> | 
> | - The guard's cleared-environment (`env -i`) backstop stores holder records `{pid, start}` in `<git-common-dir>/ait-testmap/active/h-<pid>-<unique>` and matches them against the nested process's ancestry, read from `/proc/<pid>/stat` (ppid, field 22 starttime) of the namespace the nested engine runs in.
> | - Both the recorded pid/start and the walk are values of the reader's own PID namespace; there is no namespace mapping. A PID-namespace boundary between the outer engine and a nested one would make the outer engine's record unmatchable (different pid, and the parent chain ends at the namespace's pid 1), so the backstop would admit the nested run. This is exactly the G8a reason the pidns backend is deferred: before enabling it, the backstop needs a namespace-aware mapping (or the boundary must keep the holder visible), and t1854_6's parameterized `recursionCases()` / `checkRecursion` (runner/recursion_test.go) must pass under it.
> | - Unreadable records are refused only when their name names an ancestor pid; a pidns-mapped pid could alias an unrelated process too.

> **✉ note:t1854_6** id=2026-10-25T06:58:48Z.79e0775c7b5e320aaff9ab42 from=t1854_6 from_verified=yes at=2026-10-25T06:58:48Z base=60ca89154aa0d66ceec006c9f8c6b764fe661ae6 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1854_6 (M3.2c), as landed in commit 60ca89154. This changes your task's premise; re-verify against goengines/README.md ("supervised execution", "halt", "recursion guard").
> | 
> | - t1854_6 implemented a dedicated per-start supervisor (procsup), not the cgroup-leaf / subreaper-tree boundary. Invocations already overlap safely on Linux (runner.Overlappable() is true), so "until it lands, hosts without a delegated cgroup run invocations serially" no longer holds.
> | - The remaining G8a residual is the supervisor's own death: its subtree may be left running; it is detected, recorded cleanup_unverified, and halts the process. A PID-namespace (or cgroup) backend would harden exactly that.
> | - Any new backend must join procsup.Backends() and runner's recursionBackends table (TestRecursionBackendsCovered fails until it does), keeping the env -i ancestry refusal, including TestRecursionOrphan, green.

> **✉ note:t15** id=2026-10-25T08:54:53Z.b869525e0c41bd400f1d9708 from=aitasks_go#t15 at=2026-10-25T08:54:53Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
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

> **✉ note:t22_3** id=2026-10-29T22:23:53Z.a2c992397085cd8b1bc549c0 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:23:53Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:12:16Z.e10778c203b304f532dcdd13 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:12:16Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | Re-homed: the engine work of this task moved to aitasks_go#t76
> | (beyondeye/aitasks_go). This task is Postponed as a pointer and must not be
> | picked. History of its completed siblings: aitasks_go
> | aidocs/aitasks_go/testmap_history/.
