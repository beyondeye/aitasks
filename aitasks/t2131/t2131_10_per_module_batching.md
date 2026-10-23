---
priority: medium
effort: medium
depends: [t2131_3, t1854_11]
issue_type: feature
status: Ready
labels: [testmap, go_engine, testing]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-23 11:52
updated_at: 2026-10-23 11:52
---

## Context

Child 10 of t2131 (test-map code-module tier).
- **Parent plan:** `aiplans/p2131_testmap_code_modules_tier.md`, default 12.
- **Coarse plan:** `aiplans/p2131/p2131_10_per_module_batching.md`.
- **Wave:** after M3.2h (the gradle-class adapter, t1854_11).

This is the "later optimization" in t2131's priorities: **per-module execution batching**. One invocation per module (e.g. `./gradlew :core:test`) replaces per-class invocations.

**Automation-first:** no human step.

**Default 12:**
- `group_by: module|submodule` is a new value in M3.1's `describe` vocabulary (today `none|file|dir|regex:<re>`, `runner/describe.go:200,336`).
- Each test groups by its **path-containment** module, using the `registry` path → module lookup from t2131_3. `runner` imports `registry`, never `deps`.
- A test that belongs to several modules still lands in exactly one group.
- `{module}` in `command:` resolves from the table's Gradle name where one exists.
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
2. Add `module` / `submodule` to `grouper()` through the registry lookup.
3. Add the `{module}` expansion.
4. Tests.

## Verification Steps

- A grouping golden for module and submodule.
- A multi-module test lands in exactly one group.
- `{module}` expansion.
- Existing `group_by` values are unchanged (goldens).
- The grouping key is still one shared function (grep).
- `ait engine test` is green.
