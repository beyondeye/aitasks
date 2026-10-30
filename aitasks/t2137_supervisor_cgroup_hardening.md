---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Postponed
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
followup_kind: risk_mitigation
created_at: 2026-10-25 09:00
updated_at: 2026-10-30 12:10
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t15** id=2026-10-25T08:55:10Z.ef31734e744b9e1593846d2f from=aitasks_go#t15 at=2026-10-25T08:55:10Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
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

> **✉ note:t22_3** id=2026-10-29T22:24:31Z.b0d45441231884567834abf4 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:24:31Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:12:44Z.642bdb0adb6c06944749af4f from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:12:44Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | Re-homed: the engine work of this task moved to aitasks_go#t79
> | (beyondeye/aitasks_go). This task is Postponed as a pointer and must not be
> | picked. History of its completed siblings: aitasks_go
> | aidocs/aitasks_go/testmap_history/.
