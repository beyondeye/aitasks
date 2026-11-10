---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [cross_repo, dependencies, go_engine, task_relations]
gates: [risk_evaluated]
created_at: 2026-11-10 12:36
updated_at: 2026-11-10 12:36
---

## Goal

Close the gap between "the aitasks_go task is Done" and "its code is in public aitasks". Today a cross-repo edge (`xdeps` with `xdeprepo: aitasks_go`) unblocks as soon as the aitasks_go task is **Done**. But engine code reaches this repository only through a later, manual export: a snapshot of the private `export` branch, recorded in `goengines/EXPORT.txt` and a commit trailer `Exported-From: beyondeye/aitasks_go@<sha>`. So an aitasks task can be picked while the code it needs exists only in aitasks_go.

Concrete case (as of 2026-11-10):
- aitasks_go#t62 (the `brief` verb) is Done in aitasks_go 32ddfe1, but the public export is still 544ed20 (the t22 bootstrap).
- The M5.2 front in aitasks#t1856 holds on t62 through `xdeps`, so it would unblock with no real `brief` in the public engine.

## Proposed design (to verify in planning)

1. **An "exported" condition for an xdeps edge.** The edge is satisfied when the target task is Done **and** every code commit of the target (the `(tN)` suffix in aitasks_go history) is an ancestor of the source sha in this repository's `goengines/EXPORT.txt`.
   - Options: a per-edge qualifier (e.g. `xdeps_exported: [62]`), a per-repository default (aitasks_go edges are export-gated), or an advisory pick-time warning only. Choose the minimal one that cannot block wrongly.
   - When the private repository is unreachable (no checkout registered, no access), report "unknown". **Never** report "exported".
2. **Surfaces:** `ait ls` / board blocked reasons, the pick-time Step 3 checks, and the notes and messages that already render xdeps state. Keep "Done but not exported" distinct from "not Done".
3. **The development workaround stays documented:** for protocol-only work, use a fake engine (as the M5 front tests do); for local runs, `AIT_TESTMAP_BIN=<abs path to an aitasks_go build>` (the shim accepts it without a version check). Neither may count as "exported".
4. **Shared code:** the "is aitasks_go#tN exported?" check is the same one the export-health skill needs (aitasks#t2272). Implement it once, as a script with a line protocol, and use it in both places.

## Context

- Ship-path policy: aitasks_go `aidocs/aitasks_go/ship_path.md`.
- Exporter and protocol: aitasks_go `promote/README.md`.
- Export skills: aitasks_go#t118 (the private side), aitasks#t2272 (the public side).
- Per-product export (one product exported without the others) is being designed in aitasks_go#t119. If it lands, `EXPORT.txt` may carry a source sha per product, and the condition must then check the product the task's files belong to.

## Acceptance

- A Done-but-not-exported aitasks_go dependency is reported distinctly, and either does not unblock or warns, as chosen.
- An exported one unblocks.
- An unreachable private repository reports "unknown".
- Tests use fixture repositories for both sides.
