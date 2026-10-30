---
priority: medium
effort: medium
depends: [t2131_3, t1854_11]
issue_type: feature
status: Postponed
labels: [testmap, go_engine, testing]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-23 11:52
updated_at: 2026-10-30 12:10
---

## Context

Child 10 of t2131 (test-map code-module tier).
- **Parent plan:** `aiplans/p2131_testmap_code_modules_tier.md`, default 12.
- **Coarse plan:** `aiplans/p2131/p2131_10_per_module_batching.md`.
- **Wave:** after M3.2h (the gradle-class adapter, t1854_11).

This is the "later optimization" in t2131's priorities: **per-module execution batching**. One invocation per module (e.g. `./gradlew :core:test`) replaces per-class invocations.

**Automation-first:** no human step.

**Default 12:**
- `group_by: module` is a new value in M3.1's `describe` vocabulary (today `none|file|dir|regex:<re>`, `runner/describe.go:200,336`). There is no `group_by: submodule` (revised 2026-10-24, user decision: code modules are flat).
- A test whose own path has no module stays in the runner's ungrouped group.
- Each test groups by its **path-containment** module, using the `registry` path → module lookup from t2131_3. `runner` imports `registry`, never `deps`.
- A test that belongs to several modules still lands in exactly one group.
- `{module}` in `command:` resolves from the module's `gradle` project path. A module without one is refused (`INPUT_ERROR:runner`), never guessed.
- The canonical grouping key `(runner, group_by group, resource set, wave class, batch identity)` stays **one** function shared by M3.3 (execution), M4.1 (invocation groups, `SELECTED:` `<groups>`) and M3.4 (estimate).

The runner-contract change is recorded in the proposal by t2131_1.

## Dependencies

`depends: [t2131_3, t1854_11]`:
- **t2131_3:** the table and lookup;
- **t1854_11:** M3.2h, which defines the `{module}` placeholder and the `regex:^(?:(.*?)/)?src/` module grouping this child generalizes.

The task is `Ready` but blocked until both land. M3.1 (t1854_1, archived) owns the grouping function.

## Key Files to Modify

- `goengines/internal/testmap/runner/describe.go`: the `grouper()` (~336) and the `group_by` validation.
- The gradle-class adapter's `{module}` expansion (as landed by t1854_11).
- The `runner` tests and grouping goldens.

## Reference Files for Patterns

- `aiplans/archived/p1854/p1854_1_m3_1_runner_contract_and_repository.md`, D4 (the `group_by` vocabulary).
- `aiplans/p1854/p1854_11_m3_2h_gradle_class_adapter.md` (the `{module}` placeholder).
- Proposal *Runner contract* (~2962+) and the canonical grouping key (~831, ~3007).

## Implementation Plan

1. **Step 0 — Reality check.** Read M3.1's grouping function and the gradle-class adapter's `{module}` handling as landed.
2. Add `module` to `grouper()` through the registry lookup.
3. Add the `{module}` expansion.
4. Tests.

## Verification Steps

- A grouping golden for `group_by: module`, including a test with no path module (ungrouped).
- `group_by: submodule` is refused as an unknown value.
- `{module}` is refused for a module without a `gradle` path.
- A multi-module test lands in exactly one group.
- `{module}` expansion.
- Existing `group_by` values are unchanged (goldens).
- The grouping key is still one shared function (grep).
- `ait engine test` is green.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2131_3** id=2026-10-25T08:10:33Z.0ff59cb5ccb33abc0476d36f from=t2131_3 from_verified=yes at=2026-10-25T08:10:33Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
>
> | Advisory, from t2131_3 (landed in commit eb6baa4c9), for `group_by: module`:
> | - `registry.ModulesOf(reg).OwnerOf(path)` is universe-free and cheap. It returns "" when unmapped and an `*InvalidError` on a hand-module overlap, so the runner side needs no deps import.
> | - `gradle:` rows carry the Gradle project path in `ModuleRow.Gradle` (e.g. `:services:payments:api`) for `{module}` expansion. Other providers leave it empty, so `{module}` should be refused for them.
> | - Grouping wants the test's path-containment module. Membership through covered sources is t2131_5's and is not persisted.

> **✉ note:t15** id=2026-10-25T08:55:04Z.494ae93f40ad2fa8c06b1161 from=aitasks_go#t15 at=2026-10-25T08:55:04Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
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

> **✉ note:t22_3** id=2026-10-29T22:24:19Z.e0c77c32b7076efe6c012e60 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:24:19Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:12:39Z.84939bb8ac207ee8d0a6dd87 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:12:39Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | Re-homed: the engine work of this task moved to aitasks_go#t77_7
> | (beyondeye/aitasks_go). This task is Postponed as a pointer and must not be
> | picked. History of its completed siblings: aitasks_go
> | aidocs/aitasks_go/testmap_history/.

> **✉ note:t22_4** id=2026-10-30T10:16:58Z.7e0c8a78b9f1596fe2094545 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:16:58Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | goengines freeze lifted (aitasks_go#t22 cutover complete).
> | Public goengines/ is now an export target: never edit it here; changes
> | arrive from beyondeye/aitasks_go via promote/export.sh.
> | - Engine work of this task now lives in aitasks_go#t77_7; this task is
> |   Postponed and kept only as a pointer.
