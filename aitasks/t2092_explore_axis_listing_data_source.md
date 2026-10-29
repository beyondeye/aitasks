---
priority: medium
effort: medium
depends: [1853_4]
issue_type: chore
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-21 10:07
updated_at: 2026-10-21 10:07
---

## Goal

After t1853_4 lands, explore whether axis listing should use live test discovery, the committed scan, or an explicit choice between them. Recommend a clear contract balancing freshness, reproducibility, availability and cost; do not assume a new flag or cache is necessary.

## Context to re-verify

Requested by the user after a shadow discussion of t1853_4's draft plan on 2026-10-21. The coarse plan describes variant counts from the saved scan; the detailed draft proposes live discovery for axes --list, following the check command. Live discovery can provide current counts but depends on runner availability and can disagree with the committed data used by later test selection. These are draft observations, not confirmed defects.

## Exploration

1. Read t1853_4's final notes and implementation, record the baseline commit, and verify the actual inputs and side effects of axes --list, --check and --explain. Locate the current selector contract under t1855 and distinguish existing behavior from future assumptions.
2. Reproduce fresh and stale saved scans, missing scans, unavailable or failing runner discovery, excluded tests and a changed variant set. Compare listed counts with the saved selection input and measure discovery overhead on a representative fixture or available project. Record limitations if no representative project is available.
3. Compare live-only, saved-only and explicitly chosen live/saved modes; consider whether simply reporting data provenance and freshness would solve the confusion. Assess reproducibility, offline availability, latency, maintenance cost, output compatibility, and error/fallback behavior. Avoid silently mixing sources.
4. Recommend the smallest improvement, or justify retaining the existing contract. Define defaults, absent/stale-data handling, machine-readable provenance if useful, and concrete examples explaining any difference between listing and selection.

## Deliverables / acceptance

- A durable decision record with observed command outcomes, selected/listed data comparison and measured or explicitly unmeasured costs.
- A reasoned recommendation and acceptance cases for normal, stale and unavailable-discovery scenarios.
- Identify separately scoped implementation work if warranted. This exploration does not require changing production behavior or adding caching infrastructure.

## Starting references

- aiplans/p1853/p1853_4_m2_4_axes_and_variants.md (or its archived successor)
- goengines/cmd/ait-testmap/
- goengines/internal/testmap/registry/
- goengines/internal/testmap/runner/
- aidocs/testing_engine/n014_explorer_006_proposal.md
- t1855 (selection and attribution); resolve current path by ID

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t15** id=2026-10-25T08:54:50Z.20f11d080899674f760a2130 from=aitasks_go#t15 at=2026-10-25T08:54:50Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
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

> **✉ note:t22_3** id=2026-10-29T22:23:41Z.87864791ffaf934f326a3845 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:23:41Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.
