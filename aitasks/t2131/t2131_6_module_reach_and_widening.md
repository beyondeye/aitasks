---
priority: medium
effort: medium
depends: [t2131_5]
issue_type: feature
status: Ready
labels: [testmap, go_engine, testing]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-23 11:51
updated_at: 2026-10-24 23:23
---

## Context

Child 6 of t2131 (test-map code-module tier).
- **Parent plan:** `aiplans/p2131_testmap_code_modules_tier.md`, defaults 7 and 10.
- **Coarse plan:** `aiplans/p2131/p2131_6_module_reach_and_widening.md`.
- **Wave:** C (M2.7). Depends on t2131_5 (membership).

This child builds the **library** that both consumers share:
- the selector's `--widen-modules` (t2131_7);
- the `module` completion mode (t2131_8).

It lives in `goengines/internal/testmap/modules` and can land before M4.1 exists.

**Automation-first:** no human step.

> **Revised 2026-10-24 (user decision): flat code modules, no submodules.** Reach and widening are **one operation**, `Widen`, with no level, no parent fallback and no hierarchy in its interface. The contract is the proposal's component *Code modules*.

**Default 7 — reach, initial mechanism (user decision, 2026-10-23: keep it simple; correctness unchanged):**
- **The graph.** Reach reads only the **current** (post-change) dependency graph.
- **The affected set** is the owning modules of the reached paths, which are:
  - the changed paths;
  - every file in the **transitive** reverse file closure of the changed paths over resolved edges. Indirect dependents count.

  Each affected module carries evidence `{module, origin: <changed path>, via?: <reached path>}`.
- **What pulls nothing in.** An internal edit that nothing outside the module reaches pulls in no dependents. Reach never recurses through module-level deps.
- **When the bound is unsafe, run full.** The absence of a resolved edge is **never** proof of independence. The run falls back to the **full suite** and prints `WIDEN_FULL:<reason>|<first path>|<more_n>` for:
  - `deleted_path` / `renamed_path`: the current graph has no node for the old path;
  - `unmapped_path`: a changed or reached path is outside every module, including root-only Gradle paths;
  - `uncertain_reference`: **any** in-repo file anywhere carries dependency uncertainty: an `Unresolved` entry naming an in-repo target, an opacity reason, a `<dynamic>` source, or a `gradle-dynamic` build. Without clearing, no uncertain reference can be shown not to reach the change, directly or indirectly. The line names the first such file and counts the rest;
  - `modules_stale`: the modules table has drifted.
- **Left out of the initial scope:** a historical (base-revision) graph and per-language clearing. The only classification is the scanner's existing in-repo vs outside-the-universe distinction. A form the scanner cannot tell apart counts as uncertainty.
- **Recording.** Every fallback is recorded:
  - on the `WIDEN_FULL:` line;
  - in the widen outcome carried by the prediction record (t2131_7);
  - in the per-reason counts `score` derives from the records (`WIDEN_SCORED:`), never in a second store.
- **Smarter analysis** (conservative inclusion of uncertain files, per-language clearing to a fixed point, a base-revision graph) is a **named follow-up**. It is gated on t2131_12 showing excessive fallbacks. Do **not** add it here.

**Default 10 — `Widen`** (one operation: "find the modules containing changed files and their transitive reverse dependents, add every test belonging to those modules, keep the tests already selected"):
- `Widen(current graph, table, membership, change surface, plain selection)` returns either the affected modules with evidence plus the added tests, or `full:<reason>`;
- the result is the plain selected tests ∪ every member test of the affected modules;
- selected tests outside the affected modules are kept;
- added tests carry the reason `module(<name>) <- <changed path>[ via <reached path>]`;
- added tests are budget-exempt;
- the plain set is returned alongside the added tests, for the paired prediction record.

## Key Files to Modify

- `goengines/internal/testmap/modules/widen.go` (new; the reach walk may be an internal helper of it), plus its tests.
- The intake of change-surface lines (deletions and renames). Reuse the shape M4.1 will use (`--changes -` line intake) if it exists; otherwise a minimal internal type that t2131_7 adapts.

## Reference Files for Patterns

- `deps/graph.go` (`Reverse`, `Closure`, `Opaque`, `Facts().Unresolved`, `Problems()`) and `deps/deps.go:53-67` (the `Unresolved` forms).
- `cost/eligibility.go:276-343` (`Closure` / `opaqueIn` usage).
- `deps/helpers_test.go` (`repo`, `scanRepo`) for real-graph fixtures.
- The memory hub on mutants (`feedback_mutants_need_guard_specific_signal`): one fixture per guard, built so that only that guard can fire.

## Implementation Plan

1. **Step 0 — Reality check.**
   - List every `Unresolved` form the scanners emit, and which ones are already recorded as outside the repository.
   - Check how the change surface reports deletions and renames.
   - Measure each `WIDEN_FULL` reason's frequency on this repo's graph and on a Gradle fixture. This repo has no codemap: the **test harness** generates one with `aitask_codemap.sh --scan`; the engine never runs it (Invariant 5).
   - Record the numbers in the plan for t2131_12. No clearing is added to bring them down.
2. `Widen`: the closure, the guards in the order above, the owning-module mapping with evidence, membership expansion, the plain set and the reasons.
3. Tests (below).

## Verification Steps

`ait engine test` is green.

**Ordinary widening.** Fully resolved fixtures with no uncertainty anywhere:
- an internal edit pulls in no dependents;
- a public-surface edit pulls in the dependent;
- the **indirect chain**: C → B → A over resolved edges, with a change in A, gives `{A, B, C}`. Mutant (direct reverse edges only) → red;
- a module-level dep with no file reach adds nothing;
- selected tests outside the affected modules are kept;
- the proposal's worked examples 1 (one module), 2 (a transitive chain over three modules, with the `via` reasons) and 5 (unsafe changes run full), and example 6's widening over a root Go package (`go:tool` → `go:.`).

**One fixture per guard.** Each asserts its exact `WIDEN_FULL:<reason>`, and its mutant (remove that guard) turns it red:
- `deleted_path`: delete a file nothing references, so no `Unresolved` entry exists; with the guard removed, the result is a module widening;
- `renamed_path`: rename an unreferenced file;
- `uncertain_reference`, one fixture each, in a module the change does not otherwise reach:
  - an in-repo `Unresolved` entry;
  - an opaque file;
  - a `<dynamic>` source;
  - a `gradle-dynamic` build;
- `unmapped_path`: plus the root-only Gradle variant;
- `modules_stale`: over a clean graph;
- an out-of-repo reference the scanner records as external does **not** fire `uncertain_reference`.

**Recording:** every fallback sets the widen outcome (with its reason) that t2131_7's prediction record carries.

**Measured frequencies** are recorded in the plan.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2131_3** id=2026-10-25T08:10:31Z.c1f3d471dcb389819b67de9a from=t2131_3 from_verified=yes at=2026-10-25T08:10:31Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
>
> | Advisory, from t2131_3 (landed in commit eb6baa4c9), for reach/widening:
> | - Live table and drift: `modules.Scan(ctx, root, reg)` returns `Result{Doc, Refused, Files (= Graph.Universe()), Graph}`. Compute staleness with `registry.ModulesDrift(root, res.Doc)`. Measured `check` with the live inference: ≈220 ms pinned on the aitasks shape (≈33 ms without a declared table).
> | - Judge ownership over the full universe (`Universe()`), never `Graph.Files()`: JSON, Markdown and config files are owned too.
> | - A registry with no declared table (no committed `_modules.yaml`, no hand `modules:`) has every path unmapped, so it falls back to full. `check` does not report drift for it.
> | - Gradle modules are declared projects only (`GradleModule.Declared`). A build directory no settings file includes is unmapped, so a change there means `unmapped_path`.
> | - `deps:` in the table are computed over the persisted rows only, never hand modules. They are inspection evidence, consistent with "reach never trusts them".

> **✉ note:t15** id=2026-10-25T08:55:01Z.985fb034d0bd3594f30f9af6 from=aitasks_go#t15 at=2026-10-25T08:55:01Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
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

> **✉ note:t22_3** id=2026-10-29T22:24:07Z.481a971dd3f3f4ed7b18af61 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:24:07Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.
