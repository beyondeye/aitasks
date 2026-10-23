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
updated_at: 2026-10-23 11:51
---

## Context

Child 6 of t2131 (test-map code-module tier).
- **Parent plan:** `aiplans/p2131_testmap_code_modules_tier.md`, defaults 7 and 10.
- **Coarse plan:** `aiplans/p2131/p2131_6_module_reach_and_widening.md`.
- **Wave:** C (M2.7). Depends on t2131_5 (membership).

This child builds the **library** that both consumers share:
- the selector's `--widen` (t2131_7);
- the `module` completion mode (t2131_8).

It lives in `goengines/internal/testmap/modules` and can land before M4.1 exists.

**Automation-first:** no human step.

**Default 7 — reach, initial mechanism (user decision, 2026-10-23: keep it simple; correctness unchanged):**
- **The graph.** Reach reads only the **current** (post-change) dependency graph.
- **The affected set** is:
  - the modules containing a changed path;
  - every module with a file in the **transitive** reverse file closure of the changed paths over resolved edges. Indirect dependents count.
- **What pulls nothing in.** An internal edit that nothing outside the module reaches pulls in no dependents. Reach never recurses through module-level deps.
- **When the bound is unsafe, run full.** The absence of a resolved edge is **never** proof of independence. The run falls back to the **full suite** and prints `WIDEN_FULL:<reason>|<path>` for:
  - `deleted_path` / `renamed_path`: the current graph has no node for the old path;
  - `unmapped_path`: a changed or reached path is outside every module, including root-only Gradle paths;
  - `uncertain_reference`: **any** in-repo file anywhere carries dependency uncertainty: an `Unresolved` entry naming an in-repo target, an opacity reason, a `<dynamic>` source, or a `gradle-dynamic` build. Without clearing, no uncertain reference can be shown not to reach the change, directly or indirectly. The line names the first such file and counts the rest;
  - `modules_stale`: the modules table has drifted.
- **Left out of the initial scope:** a historical (base-revision) graph and per-language clearing. The only classification is the scanner's existing in-repo vs outside-the-universe distinction. A form the scanner cannot tell apart counts as uncertainty.
- **Recording.** Every fallback is recorded:
  - on the `WIDEN_FULL:` line;
  - in the widen outcome carried by the prediction record (t2131_7);
  - in a per-reason counter.
- **Smarter analysis** (conservative inclusion of uncertain files, per-language clearing to a fixed point, a base-revision graph) is a **named follow-up**. It is gated on t2131_12 showing excessive fallbacks. Do **not** add it here.

**Default 10 — `Widen`:**
- the result is the plain selected tests ∪ every member test of the affected (sub)modules, at level `module` or `submodule`;
- selected tests outside the affected modules are kept;
- added tests carry the reason `module(<id>) <- <path>`;
- added tests are budget-exempt;
- the plain set is returned alongside the added tests, for the paired prediction record.

## Key Files to Modify

- `goengines/internal/testmap/modules/reach.go` and `widen.go` (new), plus their tests.
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
2. `Reach`: the closure, the guards in the order above, and the per-reason counter.
3. `Widen`: membership expansion, the plain set and the reasons.
4. Tests (below).

## Verification Steps

`ait engine test` is green.

**Ordinary widening.** Fully resolved fixtures with no uncertainty anywhere:
- an internal edit pulls in no dependents;
- a public-surface edit pulls in the dependent;
- the **indirect chain**: C → B → A over resolved edges, with a change in A, gives `{A, B, C}`. Mutant (direct reverse edges only) → red;
- a module-level dep with no file reach adds nothing;
- selected tests outside the affected modules are kept;
- submodule vs module level.

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

**Recording:** every fallback sets the per-reason counter and the widen outcome.

**Measured frequencies** are recorded in the plan.
