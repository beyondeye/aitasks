---
Task: t2131_12_retrospective_module_tier_evaluation.md
Parent Task: aitasks/t2131_testmap_code_modules_tier.md
Sibling Tasks: aitasks/t2131/t2131_1_*.md … aitasks/t2131/t2131_11_*.md
Archived Sibling Plans: aiplans/archived/p2131/p2131_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2131_12 — Retrospective evaluation of the code-module tier (coarse)

## Context

- **Parent goal.** The code-module tier.
- **This child.** It is the trailing **retrospective evaluation** (user
  decision, 2026-10-23). The tier was designed under partial information. In
  particular, reach starts with a deliberately conservative mechanism: the
  current graph only, with a full-suite fallback on any deletion, rename or
  dependency uncertainty. This child measures whether that pays off and files
  follow-ups **only where the data justifies them**.
- **Wave:** after G.

This coarse plan records what the parent pass fixed for this slice. It does not design internals against providers that do not exist yet; the Reality check below does that when this child is picked.

**Automation-first:** no human step in the measurement.

## Dependency hold

`Postponed` until the M4 coarse pass (t1855) wires the id for:
- **M4.4** (`score` window scoring, `predictions.yaml`).

In `depends:`: `t2131_7` (the paired records) and `t2131_8` (module mode).
Keep these when wiring. Landed: M3.4 t1854_4 (the cost ledger).

## Reading list

- `aidocs/framework/planning_conventions.md`, "Plan split: in-scope sibling
  children".
- t2131_6's plan: the fallback frequencies measured at implementation time,
  as the baseline.
- Proposal *Code modules* → *Named follow-ups* (the smarter-reach
  candidates).

## Owned files / provides / consumes

- **Owns:** this plan's outcomes table, plus any data-backed follow-up tasks.
- **Consumes:** the paired prediction records (t2131_7), the M3.4 ledger, the
  per-reason fallback counters (t2131_6) and the M4.4 window scores.

## Step 0 — Reality check

1. Which registered projects (`ait projects list`) carry `aitestmap/` and
   scored paired records.
2. M4.4 `score` and the M3.4 ledger fields as landed.
3. **Stop if M4.4 has not landed or no project has data.**
4. Record the outcome here.

## Implementation steps (coarse)

1. **Measure:**
   - **misses:** the miss rate of plain vs widened sets against the same full
     runs;
   - **cost:** the added cost of widening;
   - **fallbacks:** the full-fallback share per `WIDEN_FULL` reason;
   - **cadence:** the full-run share under `module`.
2. **Outcomes table** in this plan.
3. **Decide:**
   - whether to adopt the smarter-reach follow-ups (conservative inclusion of
     uncertain files, per-language clearing to a fixed point, a base-revision
     graph), judged on the fallback share;
   - whether `auto` should learn `module`.

   File only the data-backed ones.
4. **Commit.** `chore: … (t2131_12)`.

## Verification / acceptance

- The outcomes table is present, including the fallback share per reason.
- Every follow-up filed cites the measurement behind it.

## Step 9 reference

Shared post-implementation. Current branch, no merge.
