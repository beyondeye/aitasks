---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
followup_kind: risk_mitigation
created_at: 2026-10-25 09:00
updated_at: 2026-10-25 09:00
---

## Origin

Risk-mitigation ("after") follow-up for t1854_6, created at Step 8d after implementation landed.

## Risk addressed

addresses: supervisor death can leave its subtree running

- G8a is narrowed: membership survives every test-code process's death, but not the supervisor's own. A same-uid test can kill the supervisor, and its subtree may then be left running. This is detected, recorded `cleanup_unverified` and halts all work, but it is not prevented. Accepted by the user (2026-10-24) as a stated residual; the hardening is deferred. · severity: medium · → mitigation: supervisor_cgroup_hardening

## Goal

Place each `procsup` supervisor (`ait-testmap __supervise`, landed in t1854_6, commit 60ca89154) in a delegated cgroup v2 leaf wherever one exists, so the kernel keeps the subtree's membership even after the supervisor itself dies:

- On supervisor death, the client kills the leaf (`cgroup.kill`) and verifies it empty recursively (`cgroup.events populated 0`; a parent-only `cgroup.procs` read is not a proof). Today this case is only recorded and halted.
- Add the backend to `procsup.Backends()` and to runner's `recursionBackends` (`TestRecursionBackendsCovered`). Keep the `env -i` ancestry refusal green under it, including `TestRecursionOrphan`: a cgroup leaf alone does not change ppid, so the supervisor's subreaper stays.
- Decide CI coverage: whether to give GitHub's `ubuntu-latest` a delegated cgroup, and an `AIT_TESTMAP_REQUIRE_CGROUP`-style knob that turns a missing leaf into a failure where a cgroup is declared. That knob was withdrawn from t1854_6 together with the cgroup backend.
- Settle the host details:
  - the leaf placement under the engine's own cgroup (the "no internal processes" rule: an empty `subtree_control` permits leaves beside populated processes);
  - `CLONE_INTO_CGROUP` via `SysProcAttr.UseCgroupFD`;
  - stale empty-leaf removal.

The t1854_6 plan (archived p1854_6) records the reference host's layout and the earlier cgroup design review.
