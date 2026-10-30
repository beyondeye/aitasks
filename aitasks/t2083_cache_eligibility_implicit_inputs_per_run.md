---
priority: low
effort: medium
depends: []
issue_type: performance
status: Postponed
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
followup_kind: review_finding
created_at: 2026-10-20 15:21
updated_at: 2026-10-30 12:10
---

## Origin

Review finding (medium, follow-up disposition) raised during t2081's Step 8 review: anchor eligibility recomputes repository-wide data per result.

## Problem

`cost.Rows` invokes `judge.decide` for every result of a run with one `judge`, whose loaded `inputs` (graph, reads, covers) are immutable for the run. Still, per result:
- `implicitFiles` (`goengines/internal/testmap/cost/implicit.go`) clones and scans `g.Files()` for every Go or Kotlin test: same-directory `.go` files, and every Gradle script;
- Kotlin `implicitHit` scans `g.Files()` again for non-root settings scripts (included builds);
- `judge.extend` re-walks `Graph.Closure` for every implicit input. For Kotlin that is every Gradle script, shared by all Kotlin tests;
- `implicitHit` for Go opens an `os.Root` and runs `regularNoFollow` per modified path.

A large batch therefore repeats repository-wide work and allocations.

## Goal

Cache, inside the judge or its `inputs`, computed at most once per run:
- a directory → Go files index;
- the Gradle script list;
- the included-build directories;
- memoized `Closure` results per start file (closures are immutable for the run).

Keep every `anchor_reason` byte-identical. All of `cost/implicit_test.go` and `cost/eligibility_test.go` must pass unchanged. Add a benchmark (or a counted-call test) showing that the per-result repository scans are gone on a multi-unit batch, with a pre-change control.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t15** id=2026-10-25T08:54:42Z.5a62d946ded67fc7e3ef7b54 from=aitasks_go#t15 at=2026-10-25T08:54:42Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
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

> **✉ note:t22_3** id=2026-10-29T22:23:32Z.b5800fddf54677e069797c30 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:23:32Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:12:00Z.6c9379a5ff0b2d93de9f7649 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:12:00Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | Re-homed: the engine work of this task moved to aitasks_go#t70
> | (beyondeye/aitasks_go). This task is Postponed as a pointer and must not be
> | picked. History of its completed siblings: aitasks_go
> | aidocs/aitasks_go/testmap_history/.
