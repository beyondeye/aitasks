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

After t1853_4 lands, explore whether explicit axis filtering can be made easier to understand and safer with incomplete declarations while retaining useful control over test-run size. Deliver an evidence-backed design recommendation; this task does not preselect or implement a new policy.

## Context to re-verify

Requested by the user after a shadow discussion of t1853_4's draft plan on 2026-10-21. The draft proposes that automatic selection retains undeclared variant values when their axis is affected, but an explicit forced facet drops variants on that axis unless their declarations prove a match. Other axes and unclaimed ordinary tests pass. These are proposed behaviors, not confirmed implementation facts.

## Exploration

1. Read t1853_4's final implementation notes, landed code and tests; record the baseline commit and actual behavior. Locate the current M4.1 selector work under t1855. Evaluate the library directly if the selector is not implemented yet, and distinguish tested behavior from future integration assumptions.
2. Exercise declared matches and mismatches, undeclared values, missing axes, multiple forced facets, contradictory requests, plain tests with and without claims, and unrelated axes. Show selected and excluded test IDs and explain why each survives or disappears.
3. Compare the landed policy with retaining unknown variants, refusing ambiguous filtering, and reporting exclusions or uncertainty without changing selection. Assess missed-test risk, run size, predictability, automation, compatibility and implementation cost. These alternatives come from the discussion, not an assertion that the original author considered them.
4. Recommend the smallest worthwhile improvement, or justify retaining the current behavior. Define concrete examples, diagnostic/exit behavior and migration implications. Coordinate proposed selector-contract changes with its owning task; do not assume this task owns the selector implementation.

## Deliverables / acceptance

- A durable decision record with reproducible examples, a behavior matrix, pros and cons, and a clear recommendation.
- Keep automatic selection's conservative coverage guarantee explicit; do not silently weaken it to implement a user-requested filter.
- Identify narrowly scoped implementation work and acceptance checks if a change is worthwhile. No production behavior changes are required for this exploration.

## Starting references

- aiplans/p1853/p1853_4_m2_4_axes_and_variants.md (or its archived successor)
- goengines/internal/testmap/axes/
- aidocs/testing_engine/n014_explorer_006_proposal.md
- aitasks/t1855_testmap_m4_selection_freshness_and_feedback.md (resolve current task path by ID if renamed)

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t15** id=2026-10-25T08:54:45Z.9cfe5f9a44b10918ab47218a from=aitasks_go#t15 at=2026-10-25T08:54:45Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
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

> **✉ note:t22_3** id=2026-10-29T22:23:35Z.6c9fa3eea0eb45371d05e257 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:23:35Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.
