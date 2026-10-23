---
priority: medium
effort: medium
depends: [t2131_7, t2131_8]
issue_type: chore
status: Postponed
labels: [testmap, go_engine, testing]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-23 11:52
updated_at: 2026-10-23 11:52
---

## Context

Child 12 of t2131 (test-map code-module tier), the trailing **retrospective evaluation** (user decision, 2026-10-23).
- **Parent plan:** `aiplans/p2131_testmap_code_modules_tier.md`.
- **Coarse plan:** `aiplans/p2131/p2131_12_retrospective_module_tier_evaluation.md`.
- **Wave:** after G.

The tier was designed under partial information. In particular, reach uses a deliberately simple, conservative mechanism: the current graph only, with a full-suite fallback on any deletion, rename or dependency uncertainty. This child measures whether that design pays off, and files follow-ups **only where the data justifies them**.

**What it measures**, on a registered project with `aitestmap/` and scored **paired** prediction records (t2131_7):
- **Misses:** the miss rate of the plain selection vs the module-widened set, against the same full runs (M4.4 window scoring);
- **Cost:** the added cost of widening (M3.4 ledger: per-group estimate, full-suite p95);
- **Fallback share:** the full-fallback share per `WIDEN_FULL` reason (`deleted_path`, `renamed_path`, `unmapped_path`, `uncertain_reference`, `modules_stale`), from the recorded widen outcomes and per-reason counters;
- **Cadence:** the full-run share under `module` mode.

**What it decides:**
- Whether the **smarter-reach follow-ups** named in the proposal are justified by excessive fallbacks:
  - conservative inclusion of uncertain files;
  - per-language clearing to a fixed point;
  - a base-revision graph.
- Whether `auto` should learn `module`.

The outcomes go into its plan. New tasks are created only with data behind them.

## Dependency hold

`Postponed` only because a provider has no child id yet:

- **M4.4** (`score` window scoring, `predictions.yaml`), in t1855.

The provider parent's coarse pass adds the id and flips this task to `Ready` once nothing is left unresolved. In `depends:`: `t2131_7` (the paired records) and `t2131_8` (module mode). Keep them when wiring; `aitask_update.sh --deps` replaces the list. Landed: M3.4 (t1854_4, the cost ledger).

## Key Files

- None to modify up front. Its outputs are the plan's outcomes table and any data-backed follow-up tasks.

## Reference Files for Patterns

- `aidocs/framework/planning_conventions.md`, "Plan split: in-scope sibling children" (the retrospective-evaluation child).
- t2131_6's plan: the fallback frequencies measured at implementation time, as the baseline.

## Implementation Plan

1. **Step 0 — Reality check.**
   - Which registered projects (`ait projects list`) carry `aitestmap/` and scored paired records.
   - M4.4 `score` and the M3.4 ledger fields as landed.

   **Stop if M4.4 has not landed or no project has data.**
2. Collect the four measurements.
3. Write the outcomes table.
4. Decide on each follow-up, and file only the data-backed ones.

## Verification Steps

- The outcomes table is in the plan, including the fallback share per reason.
- Every follow-up filed cites the measurement behind it.
