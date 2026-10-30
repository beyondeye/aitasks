---
priority: medium
effort: medium
depends: [t1853_4]
issue_type: chore
status: Postponed
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-21 10:07
updated_at: 2026-10-30 12:10
---

## Goal

After t1853_4 lands, explore how to expose incomplete axis adoption without disrupting existing runners or forcing projects to migrate all tests at once. Deliver an evidence-backed design recommendation, with implementation left to separately scoped work.

## Context to re-verify

Requested by the user after a shadow discussion of t1853_4's draft plan on 2026-10-21. The draft allows a runner to list test variants without declaring an axis, exempts those variants from axis-specific findings, and selects them together when their base test is selected. This preserves compatibility, but a forgotten declaration may look like intentional non-adoption and receive neither precise axis selection nor related checks. Verify what actually landed before drawing conclusions.

## Exploration

1. Read t1853_4's final notes, code and tests and record the baseline commit. Reproduce no-axis, partially adopted, fully adopted and invalid-declaration cases, including a mixed project with several runners.
2. Determine which facts can distinguish deliberate non-adoption from an omission; document cases where intent cannot be inferred. Do not infer an axis from variant names without evidence.
3. Compare the existing behavior with informational adoption summaries, opt-in diagnostics, explicit opt-out declarations and stricter validation only after project opt-in. Assess visibility, false positives, warning noise, migration effort, configuration burden, CI/automation impact and compatibility.
4. Examine existing onboarding, maintenance and automatic repair work (including t1853_7) to avoid duplicate mechanisms. Recommend an integration point and the smallest useful change, or justify leaving the behavior as-is.

## Deliverables / acceptance

- A durable comparison backed by reproducible examples showing what users and automation can currently observe.
- A recommendation with sample text/structured output, adoption behavior and clear limits on what can be inferred.
- Preserve gradual adoption and avoid adding a mandatory human acknowledgement step.
- Identify focused implementation work and acceptance checks only where evidence supports a change; this task itself need not modify production behavior.

## Starting references

- aiplans/p1853/p1853_4_m2_4_axes_and_variants.md (or its archived successor)
- goengines/internal/testmap/axes/
- goengines/internal/testmap/runner/
- goengines/cmd/ait-testmap/
- aidocs/testing_engine/n014_explorer_006_proposal.md
- t1853_7 (automatic repair), t1857 (onboarding), t1860 (maintenance/workflow integration); resolve current paths by ID

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t15** id=2026-10-25T08:54:47Z.f7a59bad25dfd4bbcf7654d6 from=aitasks_go#t15 at=2026-10-25T08:54:47Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
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

> **✉ note:t22_3** id=2026-10-29T22:23:38Z.074eb517e199c982bbf4446f from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:23:38Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:12:05Z.ac13197df80d281b4de3e0e2 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:12:05Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | Re-homed: the engine work of this task moved to aitasks_go#t72
> | (beyondeye/aitasks_go). This task is Postponed as a pointer and must not be
> | picked. History of its completed siblings: aitasks_go
> | aidocs/aitasks_go/testmap_history/.
