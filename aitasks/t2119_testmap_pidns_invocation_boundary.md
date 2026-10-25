---
priority: low
effort: medium
depends: [t1854_6, t1854_7]
issue_type: feature
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-21 22:07
updated_at: 2026-10-21 22:08
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
