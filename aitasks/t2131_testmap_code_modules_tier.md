---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [testmap, go_engine, testing]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t2131_2, t2131_7, t2131_8, t2131_9, t2131_11, t2131_12]
anchor: 1852
created_at: 2026-10-23 07:59
updated_at: 2026-10-30 12:10
---

Split (aitasks_go#t22 cutover): the engine half of this task is aitasks_go#t77
in beyondeye/aitasks_go. This body is the framework half.

## Goal

Add a **code-module tier** — one flat set of code modules — to the `ait
testmap` design and engine. It sits between "tests mapped to the changed
files" and "the full suite": a selection can be widened to run *all tests of
the code modules a change affects*, and the completion policy can run at
module scope.

This task is the **framework parent** of the tier. The engine work
(providers, membership, the `Widen` library, selector widening, the `module`
policy, onboarding lines, batching) is aitasks_go#t77 and its children in
beyondeye/aitasks_go. This task owns the design (the n014 spec), the
framework halves and framework-only children, the trail refresh and the
cross-repo links.

> **Revised 2026-10-24 (user decision): flat code modules, no submodules.**
> The two-level module → submodule design recorded on 2026-10-23 is
> replaced by one flat set of modules with one widening rule. The contract is
> the proposal's component *Code modules*
> (`aidocs/testing_engine/n014_explorer_006_proposal.md`, t2131_1).

## Children

| child | scope | waits on |
|---|---|---|
| t2131_2 | proposal work-package rename (n014 prose only) | — |
| t2131_7 | framework half: `aitask_test.sh` parses `ait test --widen-modules` and forwards it | `xdeps` aitasks_go#t77_4; M5.1 in t1856 |
| t2131_8 | framework half: the `module` arm of the `POLICY` hook | `depends` t2131_7, t1859_4, t1859_5; `xdeps` aitasks_go#t77_5 |
| t2131_9 | framework half: onboarding skill boundary-review step, codemap generation | `xdeps` aitasks_go#t77_6; M6.5 in t1857 |
| t2131_11 | the onboarding skill's guarded enabling write of `completion.mode: module` | `depends` t2131_8, t2131_9; `xdeps` aitasks_go#t77_5 (support and the probe) |
| t2131_12 | retrospective: module-tier evaluation | `depends` t2131_7, t2131_8, t2131_9; `xdeps` aitasks_go#t77 |

Landed: t2131_1 (design amendment), t2131_3 (modules table and core
providers). The engine-only children (formerly numbers 4, 5, 6 and 10 here)
now live in aitasks_go as aitasks_go#t77_1, aitasks_go#t77_2, aitasks_go#t77_3 and
aitasks_go#t77_7, under aitasks_go#t77; they are no longer children of this task.

Cross-repo edges are `xdeps` (`xdeprepo: aitasks_go`) and unblock only when
the target is Done. **Closure order:** this parent archives automatically
once its last local child is archived. t2131_12 holds `xdeps` on aitasks_go#t77,
which is Done only when all of its engine children are, so this task closes
after the engine parent.

## Decisions taken during exploration (user-confirmed; design record)

These are recorded in the n014 spec by t2131_1. The engine children of
aitasks_go#t77 implement them.

1. **Priorities.**
   - First: (a) an on-demand **widening tier** on `select` / `test`, one
     flag, `--widen-modules`, with no level (*revised 2026-10-24*), and (b) a
     **`module` completion-policy mode** next to `full | selected | auto`.
   - Later optimization: per-module execution batching (e.g. one `./gradlew :core:test`).
   - Unmapped / opaque / empty-selection fallback **stays full-suite** unless the
     module boundaries and cross-module dependencies give enough evidence that a
     narrower run is safe.
2. **Which modules a module-scope run includes.** Evidence-based reach
   through the reverse dependency closure; each affected module runs its
   complete test set; no recursive expansion through module dependencies;
   individually selected tests outside those modules are kept; full fallback
   for `gradle-dynamic`, opaque files and unresolved references.
3. **Test → module membership.** Multiple modules per test; covered-source
   modules count even when path membership exists (in this repo `tests/`
   holds tests whose sources live in `.aitask-scripts/`); `testmap:module`
   annotations correct the inference; unresolved membership stays visible.
4. **Modules vs areas.** Separate concepts (modules: a flat structural
   grouping; areas: broad-test impact scope). Modules are inferred by
   providers (Gradle, Go and Python packages, the `code_areas.yaml` codemap
   with every entry a flat module, and agent proposals) and persisted as a
   generated, inspectable table with hand `modules:` entries as overrides
   only. An area may reference modules by name. Inferred boundaries are
   inspectable and overridable.
5. **Naming.**
   - Use `module` in CLI and YAML (*revised 2026-10-24:* there is no
     submodule).
   - In the design prose, call M1–M10 **implementation work packages** to remove
     the collision (task file names and ids stay as they are). This is t2131_2.
   - State in the design that code modules are **logical source groupings**:
     build-system modules can seed them but need not define their boundaries
     exactly. One flat tier (*revised 2026-10-24*). Landed with t2131_1;
     t2131_2 verifies it is there.

## Where it plugs into the planned trail (`art:trail-testmap-feature`)

The trail now spans two repositories. Engine rows live in aitasks_go; the
trail itself is framework planning work here, refreshed by t1863.

- **New registry table + inference + membership.** Landed (t2131_3); the
  rest is aitasks_go#t77_1 and aitasks_go#t77_2.
- **Selector widening.** Engine work in aitasks_go#t77_4, on M4.1 (`internal/selectr`,
  aitasks_go#t61, not yet decomposed). The framework side is t2131_7's forward,
  on M5.1 (t1856). Once aitasks_go#t61 creates its M4.1 child, the cross-link is
  a same-repo edge in aitasks_go; nothing here needs an edge to it.
- **Completion mode.** M8.4 / M8.5 own `completion.mode`, the `result=`
  carrier and cadence; M4.4 `readiness` must learn `module` too. Engine:
  aitasks_go#t77_5 (on aitasks_go#t65_1, aitasks_go#t65_2 and M4.4 in aitasks_go#t61). Framework:
  t2131_8's `POLICY` hook arm (on t1859_4, t1859_5).
- **Onboarding (M6, t1857).** Engine lines and intake: aitasks_go#t77_6 (on M6.1 /
  M6.4 in aitasks_go#t63, not yet decomposed). The M6.5 skill is the natural place
  for an agent to propose or correct module boundaries: t2131_9 (framework
  half) and the enabling write t2131_11.
- **Design doc.** The n014 amendment (data model, membership, selection
  grade, completion mode, onboarding, the decisions above) landed with
  t2131_1; the work-package rename is t2131_2.
  Re-check the t1812 decision "not hand-typed basic/deep/deepest labels and
  not profile tiers" (t1812:56): this tier is data-derived structure, not a
  hand label, and the amendment must say so explicitly. Confirm it is in the
  t2131_1 text (under t2131_2, which edits the same file).

## Acceptance

- Every framework child (t2131_2, t2131_7, t2131_8, t2131_9, t2131_11,
  t2131_12) archived.
- Each framework half's `xdeps` points at its engine half in aitasks_go
  (aitasks_go#t77_4, aitasks_go#t77_5, aitasks_go#t77_6; t2131_11 → aitasks_go#t77_5; t2131_12 →
  aitasks_go#t77).
- The trail (`art:trail-testmap-feature`) places the children of both
  repositories, including the aitasks_go#t77 ids.
- The t1812 "data-derived, not a hand label" statement is confirmed in the
  n014 amendment.

## Carried obligations (framework half)

- Goal / "Add a code-module tier … to the `ait testmap` design and engine" — design in n014 (landed t2131_1, plus t2131_2); the engine is aitasks_go#t77.
- Goal / "the completion policy can run at module scope" — t2131_8 (`aitask_test.sh` `POLICY` hook arm); engine policy aitasks_go#t77_5.
- Decisions 1 / "(a) an on-demand widening tier on `select` / `test` … `--widen-modules`" — t2131_7 (the public `ait test` front); engine flag aitasks_go#t77_4.
- Decisions 1 / "(b) a `module` completion-policy mode" — t2131_8; engine aitasks_go#t77_5.
- Decisions 4 / "Modules are inferred by providers: Gradle, Go and Python packages, the codemap … and agent proposals" — the agent review step in the onboarding skill is t2131_9; the providers and intake are aitasks_go#t77_1 and aitasks_go#t77_6.
- Decisions 5 / "In the design prose, call M1–M10 implementation work packages" — t2131_2.
- Decisions 5 / "State in the design that code modules are logical source groupings … one flat tier" — landed with t2131_1; t2131_2 verifies it.
- Where it plugs in / "Selector widening. Lives in M4.1 … needs a module-widening reason" — the engine part is aitasks_go#t77_4; the planning cross-link to t1855 is handled in *Where it plugs in* (M4.1 is in aitasks_go#t61; its child becomes a same-repo edge of aitasks_go#t77_4).
- Where it plugs in / "Completion mode. M8.4 … M8.5 … M4.4 `readiness` must learn it too" — t2131_8 (bash hook); engine aitasks_go#t77_5.
- Where it plugs in / "Onboarding (M6) `detect` / `classify` should surface inferred modules" — engine aitasks_go#t77_6; "The M6.5 skill … propose or correct module boundaries" — t2131_9 (skill half).
- Where it plugs in / "Design doc. Amend … n014 … the work-package rename" — amendment landed (t2131_1); rename t2131_2.
- Where it plugs in / "Re-check the t1812 decision … the amendment should say so explicitly" — *Where it plugs in → Design doc* and *Acceptance*: confirm it in the t2131_1 text.
- Expected decomposition 1 / "Design amendment … notes to t1855, t1857, t1859_4 and t1853" — done (t2131_1 archived).
- Expected decomposition 3 / "Selector widening (with or after the M4.1 child)" — t2131_7; engine aitasks_go#t77_4.
- Expected decomposition 4 / "`module` completion mode (with or after M8.4/M8.5)" — t2131_8; engine aitasks_go#t77_5.
- Expected decomposition 5 / "Onboarding surfacing and the agent review of inferred boundaries (with M6)" — t2131_9 (skill half) and t2131_11 (enabling write); engine aitasks_go#t77_6.
- Expected decomposition / "The trail (`art:trail-testmap-feature`) should be refreshed to place these children" — t1863 refreshes it, placing the aitasks_go#t77 ids cross-repo (*Acceptance*).
- (implicit, retrospective child) t2131_12 measurement — t2131_12, which waits on aitasks_go#t77.

## Relocated to aitasks_go

The engine scope below moved to aitasks_go#t77 and is quoted for reference only.

> - aitasks_go#t77 is the engine-side container for the code-module tier: Go/Python package providers (aitasks_go#t77_1), test→module membership and area module refs (aitasks_go#t77_2), the `Widen` reach library (aitasks_go#t77_3), the engine half of selector widening (aitasks_go#t77_4), the engine half of `module` completion mode (aitasks_go#t77_5, including the supported-modes capability probe t2131_11 needs), the engine half of onboarding module review (aitasks_go#t77_6), and per-module batching (aitasks_go#t77_7).
> - The engine's parent plan copy (defaults 5, 7–12) is imported with it; the aitasks `aiplans/p2131_testmap_code_modules_tier.md` and `aiplans/p2131/p2131_<n>_*.md` coarse plans for the relocated children move/copy to aitasks_go.
> - Acceptance checks:
>   - every aitasks_go#t77 child archived with `ait engine test` (private goengines CI) green;
>   - the tier's engine contract matches n014 component *Code modules* (flat modules, one `--widen-modules`, `WIDEN_FULL:` reasons, `MODULE_*` findings);
>   - the `module` mode, `WIDEN_SCORED:` and paired prediction records exist in the engine so t2131_11/t2131_12 can consume them.


## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t15** id=2026-10-25T08:54:11Z.40d6b502aec3f50c9d23f8e8 from=aitasks_go#t15 at=2026-10-25T08:54:11Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
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

> **✉ note:t22_3** id=2026-10-29T22:23:56Z.afeac3cfdb1869398b1d3c2e from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:23:56Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.
