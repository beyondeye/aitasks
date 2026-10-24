---
Task: t2131_7_selector_module_widening.md
Parent Task: aitasks/t2131_testmap_code_modules_tier.md
Sibling Tasks: aitasks/t2131/t2131_1_*.md … aitasks/t2131/t2131_6_*.md, aitasks/t2131/t2131_8_*.md … aitasks/t2131/t2131_12_*.md
Archived Sibling Plans: aiplans/archived/p2131/p2131_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2131_7 — Selector `--widen-modules` and the paired prediction record (coarse)

## Context

- **Parent goal.** The code-module tier.
- **This child.** It adds the on-demand widening tier (user priority 1a) by
  wiring t2131_6 into `select` / `explain` (M4.1) and `test` (M4.5). It also
  owns the **paired prediction record** and its scoring contract (M4.4), which
  t2131_12's comparison needs.
- **Wave:** D (after M4.4).

This coarse plan records what the parent pass fixed for this slice. It does not design internals against providers that do not exist yet; the Reality check below does that when this child is picked.

**Automation-first:** no human step.

> **Revised 2026-10-24 (user decision): flat code modules, no submodules.**
> One widening behaviour, one spelling (`--widen-modules`), no level in any
> flag, line or record. The contract is the proposal's component *Code
> modules*.

**Default 10 — what this child adds:**
- **Flags.** `select` / `explain --widen-modules` and `test
  --widen-modules`, a plain flag with no value.
- **Output.**
  - the reason token `module(<name>) <- <changed path>[ via <reached path>]`;
  - a `WIDENED:<modules_n>|<added_n>` line ahead of the rows. The `SELECTED:`
    shape is unchanged;
  - `WIDEN_FULL:<reason>|<first path>|<more_n>` passed through from t2131_6.
- **Full fallback execution.** A `WIDEN_FULL` outcome of `test
  --widen-modules` runs the **canonical full-run path**: exactly what `--all`
  runs, with its scoring and accounting. It is never a re-listing.
- **Recording wording.** `select` / `explain --widen-modules` never execute or
  score a test. Each writes exactly what its plain form writes, so a
  task-scoped `select` still writes the prediction record.
- **The public flag.** M5.1's bash front (`aitask_test.sh`) parses `ait test
  --widen-modules` and forwards it unchanged to the engine `test` composite
  (a named extension of M5.1). It adds no widening logic of its own.
- **Placement.** Widening runs after the graded walk.
- **Budget.** Widened tests are **never `DEFERRED`**.
- **The paired record.** A widened task-scoped selection writes **one**
  record:
  - the plain selection;
  - the widen outcome: the added tests, or `full:<reason>`;
  - the identity: base revision, change-surface digest, registry and
    modules-table digests.
- **Scoring.** `score` scores the plain and widened sets against the same
  later full run and reports false negatives per set (`WIDEN_SCORED:`;
  `predictions.yaml` gains an optional `widened {added_n, fn, full?}`).
- **Readiness judges the executed strategy.** `selected` / `auto` read plain
  sets only. `module` reads widened sets:
  - a record without a widened part counts its plain false negatives;
  - a full run counts toward the run totals only when every scored record
    carries a widened part and at least one is not `full:`;
  - a modules-table change is a map change.
- **Automatic recording.** Under `completion.mode: module` every task-scoped
  selection records the widen outcome, even without the flag.
- **Compatibility.** A record without the widened part scores exactly as
  today. Newest-wins per task keeps the pair together.

## Dependency hold

`Postponed` until the M4 coarse pass (t1855) and the M5 coarse pass (t1856) wire ids for:
- **M4.1** (the selector, `select` / `explain`, the prediction record);
- **M4.4** (`score`, `predictions.yaml`);
- **M4.5** (the `test` composite);
- **M5.1** (the `ait test` bash front, in t1856), added 2026-10-25 for the
  public flag.

In `depends:`: `t2131_6`. Keep it when wiring; `--deps` replaces the list.

## Reading list

- Proposal *Selector* (~3266-3295), *Run Surface* steps 7-8 and the output
  contract (~1665-1693), the prediction record (~245, ~917), *Feedback tools*
  (~3388-3425) and *Engine `test` composite* (~3427). All as amended by
  t2131_1.
- `internal/testmap/modules` (`Widen`).

## Owned files / provides / consumes

- **Owns:** the widening stage and lines in `internal/selectr`; the
  prediction-record fields; the paired scoring and the readiness
  prediction-set rule in `internal/feedback`; the CLI flag wiring; the
  `--widen-modules` arm of `aitask_test.sh`'s flag parsing and its
  fake-engine case in `tests/test_ait_test_entrypoint.sh`.
- **Provides:** `test --widen-modules` for t2131_8's `POLICY` arm; the paired records
  for t2131_12.
- **Consumes:** M4.1, M4.4, M4.5 and M5.1 as landed; t2131_6.

## Step 0 — Reality check

1. Read M4.1's walk, reason grammar and prediction-record schema as landed.
2. Read M4.4's `score` and `predictions.yaml` rows as landed.
3. Read the `explain --sources --format table` columns.
4. Read how `test` forwards flags to `select`, and how its `--all` path is
   entered for a `WIDEN_FULL` outcome.
5. Read M5.1's flag parsing in `aitask_test.sh` and its fake engine.
6. **Stop if M4.1/M4.4/M4.5 or M5.1 have not landed.**
7. Record the outcome here.

## Implementation steps (coarse)

1. The `--widen-modules` flag and the widening stage (after the walk, before
   ranking and the budget; widened rows exempt; `WIDEN_FULL` → the `--all`
   path in `test`).
2. The output lines and the explain rows; the front's flag parsing and
   forwarding.
3. The paired prediction record (additive schema).
4. Paired scoring in `score`, and the readiness prediction-set rule.
5. Tests.
6. **Commit.** `feature: … (t2131_7)`.

## Verification / acceptance

- Exact lines for `select --widen-modules`.
- A `WIDEN_FULL` outcome of `test --widen-modules` runs the canonical `--all`
  path (scoring and accounting). `select` / `explain --widen-modules` execute
  nothing, yet a task-scoped `select` still writes the prediction record.
- Readiness under `module` counts a caught-by-widening miss as no false
  negative; under `auto` the same miss is one.
- The reasons appear in `explain`.
- The `SELECTED:` shape is unchanged.
- Widened tests are never `DEFERRED`.
- The record carries plain + widen outcome + identity.
- `score` against one full run reports false negatives per set: a miss the
  plain set has and the widened set catches.
- A record without widening scores byte-identically to today.
- Newest-wins keeps the pair together.
- `ait test --widen-modules` (and `--explain --widen-modules`) reaches the fake
  engine with the flag forwarded unchanged; a control run without the flag
  forwards none.
- `ait engine test` is green.

## Step 9 reference

Shared post-implementation. Current branch, no merge.
