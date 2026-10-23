---
priority: medium
effort: medium
depends: [t2131_7, t1859_4, t1859_5]
issue_type: feature
status: Postponed
labels: [testmap, go_engine, testing, gates]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-23 11:51
updated_at: 2026-10-23 11:51
---

## Context

Child 8 of t2131 (test-map code-module tier).
- **Parent plan:** `aiplans/p2131_testmap_code_modules_tier.md`, default 11.
- **Coarse plan:** `aiplans/p2131/p2131_8_module_completion_mode.md`.
- **Wave:** G (with M8.5).

This child adds the **`module` completion-policy mode** (user priority 1b): `completion.mode: full|selected|module|auto`, plus `completion.widen: module|submodule` (default `module`).

**Automation-first:** no human approval is needed to admit `module`; the engine admits it.

**Default 11, verbatim:**
- **Required cadence.** `module` requires a valid `full_run_every` (all three triggers). `READINESS:cadence_declared` is a criterion for `module` as well as `auto`; when unmet, the run is `POLICY_DEMOTED:module->full|cadence_declared`.
- **Decision order** for each completion run under `module`. It **reuses M8.5's `cadence.go` and `policy` verb**; there is no second implementation.
  1. Readiness `NOT_YET` → full.
  2. The first `ADMISSIBLE` → the engine records `approved_by: engine:readiness@<run>`, `mode: module` in `costs/policy.yaml`.
  3. A due cadence trigger (`tasks`, `days`, or `selection_ratio_above` computed on the **widened** estimate) → full, with `cadence:<trigger>`.
  4. Any later unmet criterion → `POLICY_DEMOTED:module->full|<criterion>`.
  5. A reach fallback → full, with `widen_full:<reason>`.
  6. Otherwise → `module|next_full_in:<n>`.
- **Counters.** Every full run resets them, exactly as under `auto`: `last_full_run`, and `selected_since_full := 0`. Each module run increments `selected_since_full`.
- **Approval and output.**
  - A human `approved_by` stays optional.
  - `result=` grows `MODE:module|…` within the 200-character cap.
  - Readiness reports `POLICY:module|…|next_full_in:<n>`.
- **`auto` in v1.** `auto` never lands on `module`.
- **Who enables it.** `mode: module` is written by onboarding only once the engine supports it (t2131_11), or by the project.

## Dependency hold

`Postponed` only because a provider has no child id yet:

- **M4.4** (`readiness` and its criteria and counters; `internal/feedback`), in t1855.

The provider parent's coarse pass adds the id and flips this task to `Ready` once nothing is left unresolved. In `depends:`: `t2131_7` (selector `--widen`, which `test` uses), `t1859_4` (M8.4: the `POLICY` hook in `aitask_test.sh`, the `policy` verb, the `result=` carrier) and `t1859_5` (M8.5: `cadence.go`, the `policy.yaml` writes, `cadence_declared`). Keep these when wiring; `aitask_update.sh --deps` replaces the list.

## Key Files to Modify (as M8.4/M8.5 land them)

- `goengines/internal/testmap/registry/config.go`: the enum at ~202, plus `completion.widen`.
- `goengines/internal/testmap/feedback/policy/` (M8.4) and `feedback/cadence.go` (M8.5): the `module` arm.
- `.aitask-scripts/aitask_test.sh` (M5.1 / M8.4): the `module` arm of the `POLICY` hook, which passes `--widen` to `test`.
- `tests/test_ait_test_entrypoint.sh`: the `module` matrix.

## Reference Files for Patterns

- Proposal *Completion policy* (~1940-1960, ~3847-3879) and *Auto completion policy and cadence* (~3882-3920), as amended by t2131_1.
- `aiplans/p1859/p1859_4_m8_4_completion_policy_full_selected.md` and `p1859_5_m8_5_auto_policy_and_cadence.md` (the `auto` decision order to mirror).

## Implementation Plan

1. **Step 0 — Reality check.** Read these as landed:
   - M8.4's `POLICY` hook, carrier and readiness lines;
   - M8.5's `cadence.go`, decision order and `policy.yaml` writes, reused as they are;
   - the `config.go` enum and the `cadence_declared` validation.

   **Stop if t1859_4, t1859_5 or M4.4 have not landed.**
2. Extend the config enum and `widen`.
3. Add the `module` arm in the `policy` verb, `cadence.go` and the bash front.
4. Readiness lines.
5. The matrix tests.

## Verification Steps

- **The `module` matrix:**
  - `NOT_YET` → full;
  - the first `ADMISSIBLE` records the engine approval;
  - each cadence trigger forces full with `cadence:<trigger>`;
  - after a full run, `selected_since_full` is 0 and `last_full_run` is updated;
  - a module run increments the counter;
  - a missing or invalid `full_run_every` → `cadence_declared` unmet → full;
  - demotion per criterion;
  - `widen_full:<reason>`;
  - `engine_absent`;
  - empty selection.
- `result=` is at most 200 characters.
- Readiness reports `POLICY:module|…`.
- The cadence code is M8.5's, not a copy (grep).
