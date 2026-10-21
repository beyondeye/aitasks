---
priority: low
effort: medium
depends: [1854_6, 1854_7]
issue_type: feature
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-21 22:07
updated_at: 2026-10-21 22:07
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
