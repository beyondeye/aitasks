---
Task: t2131_7_selector_module_widening.md
Parent Task: aitasks/t2131_testmap_code_modules_tier.md
Sibling Tasks: aitasks/t2131/t2131_1_*.md … aitasks/t2131/t2131_6_*.md, aitasks/t2131/t2131_8_*.md … aitasks/t2131/t2131_12_*.md
Archived Sibling Plans: aiplans/archived/p2131/p2131_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2131_7 — Selector `--widen` and the paired prediction record (coarse)

## Context

- **Parent goal.** The code-module tier.
- **This child.** It adds the on-demand widening tier (user priority 1a) by
  wiring t2131_6 into `select` / `explain` (M4.1) and `test` (M4.5). It also
  owns the **paired prediction record** and its scoring contract (M4.4), which
  t2131_12's comparison needs.
- **Wave:** D (after M4.4).

This coarse plan records what the parent pass fixed for this slice. It does not design internals against providers that do not exist yet; the Reality check below does that when this child is picked.

**Automation-first:** no human step.

**Default 10 — what this child adds:**
- **Flags.** `select --widen submodule|module` and `test --widen
  submodule|module`.
- **Output.**
  - the reason token `module(<id>) <- <path>`;
  - a `WIDENED:<level>|<modules_n>|<added_n>` line ahead of the rows. The
    `SELECTED:` shape is unchanged;
  - `WIDEN_FULL:` passed through from t2131_6, whose fallback runs the full
    suite.
- **Placement.** Widening runs after the graded walk.
- **Budget.** Widened tests are **never `DEFERRED`**.
- **The paired record.** A widened task-scoped selection writes **one**
  record:
  - the plain selection;
  - the widen outcome: level + added tests, or `full:<reason>`;
  - the identity: base revision, change-surface digest, registry and
    modules-table digests.
- **Scoring.** `score` scores the plain and widened sets against the same
  later full run and reports false negatives per set.
- **Compatibility.** A record without the widened part scores exactly as
  today. Newest-wins per task keeps the pair together.

## Dependency hold

`Postponed` until the M4 coarse pass (t1855) wires ids for:
- **M4.1** (the selector, `select` / `explain`, the prediction record);
- **M4.4** (`score`, `predictions.yaml`);
- **M4.5** (the `test` composite).

In `depends:`: `t2131_6`. Keep it when wiring; `--deps` replaces the list.

## Reading list

- Proposal *Selector* (~3266-3295), *Run Surface* steps 7-8 and the output
  contract (~1665-1693), the prediction record (~245, ~917), *Feedback tools*
  (~3388-3425) and *Engine `test` composite* (~3427). All as amended by
  t2131_1.
- `internal/testmap/modules` (`Reach`, `Widen`).

## Owned files / provides / consumes

- **Owns:** the widening stage and lines in `internal/selectr`; the
  prediction-record fields; the paired scoring in `internal/feedback`; the CLI
  flag wiring.
- **Provides:** `test --widen` for t2131_8's `POLICY` arm; the paired records
  for t2131_12.
- **Consumes:** M4.1, M4.4 and M4.5 as landed; t2131_6.

## Step 0 — Reality check

1. Read M4.1's walk, reason grammar and prediction-record schema as landed.
2. Read M4.4's `score` and `predictions.yaml` rows as landed.
3. Read the `explain --sources --format table` columns.
4. Read how `test` forwards flags to `select`.
5. **Stop if M4.1/M4.4/M4.5 have not landed.**
6. Record the outcome here.

## Implementation steps (coarse)

1. The `--widen` flag and the widening stage (after the walk, before ranking
   and the budget; widened rows exempt).
2. The output lines and the explain rows.
3. The paired prediction record (additive schema).
4. Paired scoring in `score`.
5. Tests.
6. **Commit.** `feature: … (t2131_7)`.

## Verification / acceptance

- Exact lines for `select --widen`.
- The reasons appear in `explain`.
- The `SELECTED:` shape is unchanged.
- Widened tests are never `DEFERRED`.
- The record carries plain + widen outcome + identity.
- `score` against one full run reports false negatives per set: a miss the
  plain set has and the widened set catches.
- A record without widening scores byte-identically to today.
- Newest-wins keeps the pair together.
- `ait engine test` is green.

## Step 9 reference

Shared post-implementation. Current branch, no merge.
