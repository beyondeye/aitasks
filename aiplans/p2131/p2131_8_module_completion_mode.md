---
Task: t2131_8_module_completion_mode.md
Parent Task: aitasks/t2131_testmap_code_modules_tier.md
Sibling Tasks: aitasks/t2131/t2131_1_*.md … aitasks/t2131/t2131_7_*.md, aitasks/t2131/t2131_9_*.md … aitasks/t2131/t2131_12_*.md
Archived Sibling Plans: aiplans/archived/p2131/p2131_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2131_8 — `module` completion mode with the cadence (coarse)

## Context

- **Parent goal.** The code-module tier.
- **This child.** It adds the `module` completion-policy mode (user priority
  1b): `completion.mode: full|selected|module|auto`. There is no
  `completion.widen` (revised 2026-10-24, user decision: flat code modules,
  no submodules); the mode names the strategy.
- **Wave:** G (with M8.5).

This coarse plan records what the parent pass fixed for this slice. It does not design internals against providers that do not exist yet; the Reality check below does that when this child is picked.

**Automation-first.** The engine admits `module`; a human `approved_by` stays
optional.

**Default 11, verbatim:**
- **Required cadence.** A valid `full_run_every` (all three triggers) is
  required. `READINESS:cadence_declared` applies to `module` as well as
  `auto`; when unmet, the run is `POLICY_DEMOTED:module->full|cadence_declared`.
- **Decision order.** It reuses M8.5's `cadence.go` and the `policy` verb;
  there is no second implementation.
  *Approved* means `costs/policy.yaml` holds `approved_by` with `mode:
  module`; one under `auto` does not count. Each run takes exactly one
  admission branch (revised 2026-10-25, so the demotion is reachable):
  1. **not approved:** `NOT_YET` → full (`not_yet:<criterion>`, nothing
     written); `ADMISSIBLE` → `approved_by: engine:readiness@<run>`, `mode:
     module` in `costs/policy.yaml`, `POLICY_FLIPPED:module->module|…`, and
     continue at 3;
  2. **approved:** any unmet criterion →
     `POLICY_DEMOTED:module->full|<criterion>`, `approved_by` cleared, full
     (the only branch that clears an approval); all met → continue at 3;
  3. a due trigger (`tasks`, `days`, or `selection_ratio_above` on the
     **widened** estimate) → full, with `cadence:<trigger>`;
  4. a reach fallback → full, with `widen_full:<reason>`, through the
     canonical full-run path (the widening is computed once, before step 3);
  5. otherwise `module|next_full_in:<n>`.
- **Counters.** A full run resets `last_full_run` and sets
  `selected_since_full := 0`. A module run increments it.
- **Readiness under `module`** judges the widened sets (proposal *Feedback
  tools*; delivered by t2131_7):
  - a record without a widened part counts its plain false negatives;
  - a full run counts only when every scored record carries a widened part
    and at least one is not `full:`;
  - a modules-table change is a map change.
- **Output.** `result=` grows `MODE:module|…` and stays at most 200
  characters. Readiness reports `POLICY:module|…`.
- **`auto` in v1.** It never lands on `module`.

## Dependency hold

`Postponed` until the M4 coarse pass (t1855) wires the id for:
- **M4.4** (`readiness`, its criteria and counters).

In `depends:`:
- `t2131_7` (`test --widen-modules`);
- `t1859_4` (M8.4: the `POLICY` hook, the `policy` verb, the `result=`
  carrier);
- `t1859_5` (M8.5: `cadence.go`, the `policy.yaml` writes,
  `cadence_declared`).

Keep these when wiring.

## Reading list

- Proposal *Completion policy* (~1940-1960, ~3847-3879), *Auto completion
  policy and cadence* (~3882-3920), *Feedback tools* readiness (~3414-3421)
  and the config block (~370-409). All as amended by t2131_1.
- `aiplans/p1859/p1859_4_m8_4_completion_policy_full_selected.md` and
  `aiplans/p1859/p1859_5_m8_5_auto_policy_and_cadence.md` (the `auto`
  decision order to mirror).

## Owned files / provides / consumes

- **Owns:**
  - the `config.go` enum;
  - the `module` arm in the `policy` package / `cadence.go` and in
    `aitask_test.sh`'s `POLICY` hook;
  - the readiness `POLICY:module` lines;
  - the `module` matrix in `tests/test_ait_test_entrypoint.sh`.
- **Provides:** module mode for t2131_11's enabling write. If none exists, the
  supported-modes capability probe that t2131_11 needs.
- **Consumes:** t2131_7, t1859_4, t1859_5 and M4.4 as landed.

## Step 0 — Reality check

1. Read M8.4's `POLICY` hook, carrier and readiness lines as landed.
2. Read M8.5's `cadence.go`, decision order and `policy.yaml` writes; reuse
   them as they are.
3. Read the `config.go` enum and the `cadence_declared` validation.
4. Check whether the engine reports supported modes. If not, add a capability
   line to the `policy` verb for t2131_11.
5. **Stop if t1859_4, t1859_5 or M4.4 have not landed.**
6. Record the outcome here.

## Implementation steps (coarse)

1. The config enum.
2. The `module` arm in the `policy` verb and `cadence.go`, plus the counter
   handling.
3. The bash front's `module` arm, which passes `--widen-modules` to `test`.
4. Readiness lines.
5. The capability probe, if needed.
6. The matrix tests.
7. **Commit.** `feature: … (t2131_8)`.

## Verification / acceptance

- **The `module` matrix:**
  - not approved + `NOT_YET` → full, nothing written;
  - not approved + the first `ADMISSIBLE` records the engine approval and
    runs on to the cadence step;
  - approved + a criterion that becomes unmet (e.g. `max_false_negatives`) →
    `POLICY_DEMOTED:module->full|<criterion>`, `approved_by` cleared — never
    the `not_yet` branch;
  - each cadence trigger forces full with `cadence:<trigger>`;
  - after a full run, `selected_since_full` is 0 and `last_full_run` is
    updated;
  - a module run increments the counter;
  - a missing or invalid `full_run_every` → `cadence_declared` unmet → full;
  - demotion per criterion;
  - `widen_full:<reason>` (a full run through the canonical path, counters
    reset);
  - an approval recorded under `mode: auto` does not admit `module`;
  - `engine_absent`;
  - empty selection.
- `result=` is at most 200 characters.
- Readiness reports `POLICY:module|…`.
- The cadence code is M8.5's, not a copy (grep).

## Step 9 reference

Shared post-implementation. Current branch, no merge.
