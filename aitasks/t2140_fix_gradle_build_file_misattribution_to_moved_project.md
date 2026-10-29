---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [testmap, go_engine, testing]
gates: [risk_evaluated]
anchor: 1852
followup_kind: upstream_defect
created_at: 2026-10-25 10:09
updated_at: 2026-10-25 10:09
---

## Origin
Spawned from t2131_3 during Step 8b review.

## Upstream defect
- `goengines/internal/testmap/deps/gradle.go:209-215` — a build file whose directory maps by `moduleNameOf` onto an existing project name with a different `projectDir` (e.g. `include(":api")` moved to `services/api` plus a stray `api/build.gradle.kts`) is attached to that project as its `BuildFile` through `addModule`'s by-name return; this also feeds `sourceEdges` (the module-build closure edges of every Kotlin / Java source of the project).

## Diagnostic context
In `buildGradle`, the build-file loop looks a build file's directory up in `byDir`; on a miss it calls `addModule(moduleNameOf(d), d)`. `addModule` returns the existing module **by name** when one exists, so a build file in `api/` resolves to the `:api` project even though settings moved `:api` to `services/api/`. If `api/build.gradle.kts` sorts before `services/api/build.gradle.kts` (it does), it becomes `:api`'s `BuildFile` (`if m.BuildFile == ""`), and the project's real build file is never attached. t2131_3's Gradle modules provider guards against it (`build:` evidence only when the build file lies under the project's directory), but the deps graph itself — `GradleModule.BuildFile`, the module-build closure edges and the build-file opacity/dynamic attribution — still carries the wrong file.

## Suggested fix
In the build-file loop, when `byDir[d]` misses, only reuse a by-name module whose `Dir == d`; otherwise create a distinct record (or skip it — it is a build directory no settings file includes, `Declared: false`). Add a regression test in `deps/gradle_test.go` with the moved project plus the stray build file, asserting `:api`'s `BuildFile` is `services/api/build.gradle.kts` and its sources' `module-build` edge targets it.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t15** id=2026-10-25T08:55:13Z.cd966f5a06aa217a213ebd48 from=aitasks_go#t15 at=2026-10-25T08:55:13Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
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

> **✉ note:t22_3** id=2026-10-29T22:24:37Z.af9002a77c4f61203e49f2bb from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:24:37Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.
