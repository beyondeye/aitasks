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
updated_at: 2026-10-25 00:40
---

## Context

Child 8 of t2131 (test-map code-module tier).
- **Parent plan:** `aiplans/p2131_testmap_code_modules_tier.md`, default 11.
- **Coarse plan:** `aiplans/p2131/p2131_8_module_completion_mode.md`.
- **Wave:** G (with M8.5).

This child adds the **`module` completion-policy mode** (user priority 1b): `completion.mode: full|selected|module|auto`. There is **no `completion.widen`**: the mode names the strategy (revised 2026-10-24, user decision: flat code modules, no submodules; the contract is the proposal's *Auto completion policy and cadence* → "The `module` arm").

**Automation-first:** no human approval is needed to admit `module`; the engine admits it.

**Default 11, verbatim:**
- **Required cadence.** `module` requires a valid `full_run_every` (all three triggers). `READINESS:cadence_declared` is a criterion for `module` as well as `auto`; when unmet, the run is `POLICY_DEMOTED:module->full|cadence_declared`.
- **Decision order** for each completion run under `module`. It **reuses M8.5's `cadence.go` and `policy` verb**; there is no second implementation.
  *Approved* means `costs/policy.yaml` holds `approved_by` with `mode: module`. An approval recorded under `mode: auto` does not count. Readiness runs first, and each run takes **exactly one** admission branch (revised 2026-10-25, so that the demotion is reachable):
  1. **Not approved.**
     - `NOT_YET` → full (`POLICY:module|full|not_yet:<criterion>`), nothing written.
     - `ADMISSIBLE` → the engine records `approved_by: engine:readiness@<run>`, `mode: module` in `costs/policy.yaml`, prints `POLICY_FLIPPED:module->module|…`, and continues at 3.
  2. **Approved.**
     - Any unmet criterion → `POLICY_DEMOTED:module->full|<criterion>`, `approved_by` cleared, full. This is the only branch that clears an approval.
     - All criteria met → continue at 3.
  3. A due cadence trigger (`tasks`, `days`, or `selection_ratio_above` computed on the **widened** estimate) → full, with `cadence:<trigger>`.
  4. A reach fallback → full, with `widen_full:<reason>`, run through the canonical full-run path. The widening is computed once, before step 3, and when it falls back the ratio is not evaluated.
  5. Otherwise → `module|next_full_in:<n>`.
- **Readiness under `module`** judges the widened sets (the proposal's *Feedback tools* → "Which prediction set readiness judges"; delivered by t2131_7 in M4.4):
  - a record without a widened part counts its plain false negatives;
  - a full run counts toward the run totals only when every scored record carries a widened part and at least one is not `full:`;
  - a modules-table change is a map change.
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

The provider parent's coarse pass adds the id and flips this task to `Ready` once nothing is left unresolved. In `depends:`: `t2131_7` (selector `--widen-modules`, which `test` uses), `t1859_4` (M8.4: the `POLICY` hook in `aitask_test.sh`, the `policy` verb, the `result=` carrier) and `t1859_5` (M8.5: `cadence.go`, the `policy.yaml` writes, `cadence_declared`). Keep these when wiring; `aitask_update.sh --deps` replaces the list.

## Key Files to Modify (as M8.4/M8.5 land them)

- `goengines/internal/testmap/registry/config.go`: the enum at ~202 (no new key).
- `goengines/internal/testmap/feedback/policy/` (M8.4) and `feedback/cadence.go` (M8.5): the `module` arm.
- `.aitask-scripts/aitask_test.sh` (M5.1 / M8.4): the `module` arm of the `POLICY` hook, which passes `--widen-modules` to `test`.
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
2. Extend the config enum.
3. Add the `module` arm in the `policy` verb, `cadence.go` and the bash front.
4. Readiness lines.
5. The matrix tests.

## Verification Steps

- **The `module` matrix:**
  - not approved + `NOT_YET` → full, nothing written;
  - not approved + the first `ADMISSIBLE` records the engine approval and runs on to the cadence step;
  - approved + a criterion that becomes unmet (e.g. `max_false_negatives`) → `POLICY_DEMOTED:module->full|<criterion>` and `approved_by` cleared. It never takes the `not_yet` branch;
  - each cadence trigger forces full with `cadence:<trigger>`;
  - after a full run, `selected_since_full` is 0 and `last_full_run` is updated;
  - a module run increments the counter;
  - a missing or invalid `full_run_every` → `cadence_declared` unmet → full;
  - demotion per criterion;
  - `widen_full:<reason>` (a full run through the canonical path, counters reset);
  - an approval recorded under `mode: auto` does not admit `module`;
  - `engine_absent`;
  - empty selection.
- `result=` is at most 200 characters.
- Readiness reports `POLICY:module|…`.
- The cadence code is M8.5's, not a copy (grep).

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t22_3** id=2026-10-29T22:24:13Z.86e79f709e49527a3c984fbb from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:24:13Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.
