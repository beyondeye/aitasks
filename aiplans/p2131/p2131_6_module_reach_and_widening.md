---
Task: t2131_6_module_reach_and_widening.md
Parent Task: aitasks/t2131_testmap_code_modules_tier.md
Sibling Tasks: aitasks/t2131/t2131_1_*.md … aitasks/t2131/t2131_5_*.md, aitasks/t2131/t2131_7_*.md … aitasks/t2131/t2131_12_*.md
Archived Sibling Plans: aiplans/archived/p2131/p2131_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2131_6 — Reach and widening library (coarse)

## Context

- **Parent goal.** The code-module tier.
- **This child.** It builds the library shared by the selector's `--widen`
  (t2131_7) and by `module` completion (t2131_8), in
  `internal/testmap/modules`.
- **Wave:** C (M2.7). Depends on t2131_5. It lands before M4.1 exists.

This coarse plan records what the parent pass fixed for this slice. It does not design internals against providers that do not exist yet; the Reality check below does that when this child is picked.

**Automation-first:** no human step.

**Default 7 — reach.** This is the initial mechanism, kept simple by user
decision on 2026-10-23. Correctness is unchanged.
- **The graph.** Only the **current** (post-change) dependency graph.
- **The affected set.**
  - the modules containing a changed path;
  - every module with a file in the **transitive** reverse closure of the
    changed paths over resolved edges.
- **What pulls nothing in.** Internal-only edits pull in no dependents. There
  is no recursion through module-level deps.
- **Full fallback.** The absence of a resolved edge is never proof of
  independence. Fall back to the **full suite** with
  `WIDEN_FULL:<reason>|<path>` for:
  - `deleted_path` / `renamed_path`;
  - `unmapped_path`, including root-only Gradle paths;
  - `uncertain_reference`: **any** in-repo file anywhere with an in-repo
    `Unresolved` entry, an opacity reason, a `<dynamic>` source or a
    `gradle-dynamic` build. The line names the first such file and counts the
    rest;
  - `modules_stale`.
- **Left out.** No historical graph and no per-language clearing. The only
  classification is the scanner's existing in-repo vs external distinction; a
  form that cannot be told apart counts as uncertainty.
- **Recording.** Every fallback goes on the line, into the widen outcome (for
  t2131_7's prediction record) and into a per-reason counter.
- **Smarter analysis** is a named follow-up gated on t2131_12. Do not add it
  here.

**Default 10 — `Widen`.**
- **Result.** The plain selected tests ∪ every member test of the affected
  (sub)modules. Selected tests outside them are kept.
- **Reason.** `module(<id>) <- <path>`.
- **Budget.** Budget-exempt.
- **Return value.** The plain set is returned alongside the added tests.

## Reading list

- The proposal component *Code modules* (from t2131_1).
- `deps/graph.go` (`Reverse`, `Closure`, `Opaque`, `Facts`, `Problems`) and
  `deps/deps.go:53-67`.
- `cost/eligibility.go:276-343`.
- `deps/helpers_test.go` (real-graph fixtures).
- Memory `feedback_mutants_need_guard_specific_signal`.

## Owned files / provides / consumes

- **Owns:** `internal/testmap/modules/reach.go`, `widen.go` and their tests.
- **Provides:**
  - `Reach(current graph, table, change surface) → affected modules + evidence | full reason`;
  - `Widen(level, affected, membership) → plain + added tests + reasons`;
  - the per-reason counter.
- **Consumes:** t2131_3's table, lookup and `MODULES_DRIFT`; t2131_5's
  membership.

## Step 0 — Reality check

1. List every `Unresolved` form the scanners emit. Mark which ones the scanner
   already records as outside the repository.
2. How deletions and renames reach the library. Use M4.1's `--changes -`
   intake shape if it exists; otherwise define a minimal type that t2131_7
   adapts.
3. Measure each `WIDEN_FULL` reason's frequency:
   - on this repo's graph, with a codemap that the **test harness** generates
     through `aitask_codemap.sh --scan` (the engine never runs it,
     Invariant 5);
   - on a Gradle fixture.

   Record the numbers here for t2131_12. Do not add clearing to bring them
   down.
4. Record the outcome here.

## Implementation steps (coarse)

1. `Reach`: the closure, then the guards (deleted/renamed, unmapped,
   uncertainty, stale), then the per-reason counter.
2. `Widen`: membership expansion, the plain set and the reasons.
3. Tests (below).
4. **Commit.** `feature: … (t2131_6)`.

## Verification / acceptance

**Ordinary widening.** Fully resolved fixtures with no uncertainty anywhere:
- an internal edit pulls in no dependents;
- a public-surface edit pulls in the dependent;
- the **indirect chain**: C → B → A over resolved edges, with a change in A,
  gives `{A, B, C}`. Mutant (direct reverse edges only) → red;
- a module-level dep with no file reach adds nothing;
- selected tests outside the affected modules are kept;
- submodule vs module level.

**One fixture per retained guard.** Each is built so that **only** that guard
can fire. It asserts the exact `WIDEN_FULL:<reason>`, and its mutant (remove
that guard) turns it red:
- `deleted_path`: delete a file nothing references, so no `Unresolved` entry
  exists anywhere. With the guard removed, the result is a module widening;
- `renamed_path`: rename an unreferenced file;
- `uncertain_reference`, one fixture per form, each in a module the change
  does not otherwise reach:
  - an in-repo `Unresolved` entry;
  - an opaque file;
  - a `<dynamic>` source;
  - a `gradle-dynamic` build;
- `unmapped_path`, plus the root-only Gradle variant;
- `modules_stale`, over a clean graph;
- an out-of-repo reference the scanner records as external does **not** fire
  `uncertain_reference`.

**Recording.** Every fallback sets the per-reason counter and the widen
outcome.

**Measured frequencies** are recorded in this plan.

`ait engine test` is green.

## Step 9 reference

Shared post-implementation. Current branch, no merge.
