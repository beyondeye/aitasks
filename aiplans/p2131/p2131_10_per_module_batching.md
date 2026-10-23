---
Task: t2131_10_per_module_batching.md
Parent Task: aitasks/t2131_testmap_code_modules_tier.md
Sibling Tasks: aitasks/t2131/t2131_1_*.md … aitasks/t2131/t2131_9_*.md, aitasks/t2131/t2131_11_*.md, aitasks/t2131/t2131_12_*.md
Archived Sibling Plans: aiplans/archived/p2131/p2131_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2131_10 — Per-module execution batching (coarse)

## Context

- **Parent goal.** The code-module tier.
- **This child.** It implements the "later optimization" from the parent's
  priorities: one invocation per module (e.g. `./gradlew :core:test`).
- **Wave:** after M3.2h. Depends on t2131_3 (table and lookup) and t1854_11
  (the gradle-class adapter, `{module}`).

This coarse plan records what the parent pass fixed for this slice. It does not design internals against providers that do not exist yet; the Reality check below does that when this child is picked.

**Automation-first:** no human step.

**Default 12:**
- `group_by: module|submodule` is a new `describe` value (M3.1 vocabulary;
  today `none|file|dir|regex:<re>`).
- Each test groups by its **path-containment** module, through the `registry`
  lookup. `runner` imports `registry`, never `deps`.
- A multi-module test lands in exactly one group.
- `{module}` resolves from the table's Gradle name.
- The canonical grouping key stays **one** function shared by M3.3, M4.1 and
  M3.4.

## Reading list

- `aiplans/archived/p1854/p1854_1_m3_1_runner_contract_and_repository.md`
  D4.
- `aiplans/p1854/p1854_11_m3_2h_gradle_class_adapter.md`.
- Proposal *Runner contract* (~2962+) and the canonical grouping key (~831,
  ~3007), as amended by t2131_1.
- `runner/describe.go` (~200, ~336).

## Owned files / provides / consumes

- **Owns:** the `group_by: module|submodule` branch of `grouper()` and its
  validation; the `{module}` expansion; the tests.
- **Provides:** module-batched invocations.
- **Consumes:** t2131_3's lookup; M3.1 (t1854_1, archived); t1854_11.

## Step 0 — Reality check

1. Read M3.1's grouping function and the gradle-class adapter's `{module}`
   handling as landed.
2. Confirm that the grouping key is still one function.
3. Record the outcome here.

## Implementation steps (coarse)

1. `grouper()` gains `module` / `submodule` through the registry lookup.
2. The `{module}` expansion from the table's Gradle name.
3. Tests and goldens.
4. **Commit.** `feature: … (t2131_10)`.

## Verification / acceptance

- A grouping golden for module and submodule.
- A multi-module test lands in exactly one group.
- `{module}` expansion.
- Existing `group_by` values are unchanged.
- One shared grouping function (grep).
- `ait engine test` is green.

## Step 9 reference

Shared post-implementation. Current branch, no merge.
