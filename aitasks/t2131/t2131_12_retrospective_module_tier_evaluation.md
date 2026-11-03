---
priority: medium
effort: medium
depends: [t2131_7, t2131_8, t2131_9]
xdeps: [77]
xdeprepo: aitasks_go
issue_type: chore
status: Postponed
labels: [testmap, go_engine, testing]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-23 11:52
updated_at: 2026-10-30 12:10
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
- **Fallback share:** the full-fallback share per `WIDEN_FULL` reason (`deleted_path`, `renamed_path`, `unmapped_path`, `uncertain_reference`, `modules_stale`), from the recorded widen outcomes (`WIDEN_SCORED:`);
- **Cadence:** the full-run share under `module` mode.
- **Boundary source:** every measurement above split by how the affected modules' boundaries were set: build or package providers and the codemap, versus agent-refined (`provider: agent` proposals and `testmap:module` corrections from t2131_9). The tier is not judged on package-derived boundaries alone.

**What it decides:**
- Whether the **smarter-reach follow-ups** named in the proposal are justified by excessive fallbacks:
  - conservative inclusion of uncertain files;
  - per-language clearing to a fixed point;
  - a base-revision graph.
- Whether `auto` should learn `module`.
- Whether flat code modules stay flat (user decision, 2026-10-24), under the pre-registered criteria below.

**Flat-modules evaluation — criteria pre-registered 2026-10-25 (user request), fixed before any data is read:**
- **Sample.** Only scored paired records whose widened part is not a `full:` fallback count. There must be at least **20** of them, the same number as `readiness.min_scored_full_runs`'s default. With fewer, the outcome is `insufficient_data`: no levels decision is taken, and the plan records how many records are still missing.
- **Parent-level counterfactual** (computed offline from committed data, with no engine change):
  - For each counted record, rebuild the state at its base revision with `git show <base>:…`: the modules table, the registry membership, the codemap or Gradle settings, and the cost ledger estimates. Then compute what a **parent-level widening** would have added.
  - Each module's **parent** is the nearest enclosing root of the same provider: the codemap parent entry, the enclosing included Gradle project, or the parent package directory. A hand or agent module, or a module with no enclosing root, is its own parent.
  - The parent level's set is the plain selection ∪ every test of every module under the affected modules' parents.
  - Per record, measure the parent level's added cost over flat widening, and the failures of the same full run that the parent level would have caught but flat widening missed.
- **Too broad** — the signal for **finer boundaries**, not for levels:
  - It fires when **≥ 25 %** of counted records have a flat-widened estimate **≥ `selection_ratio_above` × the full-suite p95** (the project's own cadence threshold, default 0.60). Widening that costs that much is already treated as "run full".
  - The response is boundary refinement: codemap entries, agent proposals (t2131_9) or hand overrides. A second level would not help, because flat modules already use the deepest root.
  - The outcome lists the modules that dominate those records.
- **Too narrow** — the only signal for **a coarser second level**. Both conditions must hold:
  - the parent-level counterfactual catches **≥ 2** failures that flat widening missed, in **≥ 2** distinct tasks;
  - in **≥ 75 %** of counted records, the parent-level estimate stays **below `selection_ratio_above` × the full-suite p95**.

  When it fires, the outcome is `consider_levels`, filed as a follow-up task that cites these numbers. When widened misses exist but the parent level would not have caught them, they are reach or membership problems, not a levels problem.
- **Outcome**, one of:
  - `keep_flat`;
  - `refine_boundaries` (too broad);
  - `consider_levels` (too narrow);
  - `insufficient_data`.

  It is written with the counts behind it and split by boundary source. Agent-refined modules are judged separately, so a provider's default rule is never blamed for a boundary an agent already fixed.
- **Changing a threshold after the data is read** requires stating the reason in the plan, and the outcome is then reported under both the original and the changed threshold.

The outcomes go into its plan. New tasks are created only with data behind them.

## Dependency hold

`Postponed` only because a provider has no child id yet:

- **M4.4** (`score` window scoring, `predictions.yaml`), in t1855.

The provider parent's coarse pass adds the id and flips this task to `Ready` once nothing is left unresolved. In `depends:`: `t2131_7` (the paired records), `t2131_8` (module mode) and `t2131_9` (agent-refined module boundaries). Keep them when wiring; `aitask_update.sh --deps` replaces the list. Landed: M3.4 (t1854_4, the cost ledger).

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
2. Collect the five measurements, each split by boundary source, plus the parent-level counterfactual.
3. Write the outcomes table.
4. Decide on each follow-up, and file only the data-backed ones. For the flat-modules question, apply the pre-registered criteria above exactly as written (`keep_flat` / `refine_boundaries` / `consider_levels` / `insufficient_data`).

## Verification Steps

- The outcomes table is in the plan, including the fallback share per reason.
- Every follow-up filed cites the measurement behind it.
- The flat-modules outcome is one of the four values, with the counted-record total, the too-broad share, the parent-level catches (failures and distinct tasks) and its cost share, each split by boundary source.
- The parent-level counterfactual is reproducible: the plan records the script and the base revisions it read.
- Any threshold changed after the data was read is listed with its reason, and the outcome is shown under both the original and the changed threshold.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t22_3** id=2026-10-29T22:24:25Z.501bbbc1f44bea98cb4513e1 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:24:25Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:17:03Z.ff11ea37d4ecd9bc6f98ee6c from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:17:03Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | goengines freeze lifted (aitasks_go#t22 cutover complete).
> | Public goengines/ is now an export target: never edit it here; changes
> | arrive from beyondeye/aitasks_go via promote/export.sh.
> | - This task has no engine part and stays here; it gained xdeps on aitasks_go#t77
> |   (unblocks only when that task is Done).

> **✉ note:t77_3** id=2026-11-03T16:14:40Z.3ace2223dd94c11a63cf0ed6 from=aitasks_go#t77_3 from_verified=yes at=2026-11-03T16:14:40Z base=2bdd5d45ad43388ab469245d481e253847d1c78a base_branch=main dirty=yes host=omg16
>
> | Advisory, from aitasks_go#t77_3 (the engine's reach/widening library, commit 97cebac in aitasks_go, not yet pushed as of this moment): the measured WIDEN_FULL frequencies your retrospective reads, and the uncertainty classification behind them.
> | Classification: uncertain_reference fires on ANY scanned file with an Unresolved entry or an opacity reason. The scanners never record external references in Unresolved (Python/Kotlin imports of no repo file and Go stdlib/out-of-repo packages are dropped), so every entry counts; gradle-dynamic always sets the gradle-dynamic opacity reason.
> | aitasks snapshot (HEAD 10957dd72, codemap from the default aitask_codemap.sh --scan, table applied): universe 3364, 35 modules, 935 unmapped files (.aitask-scripts/ 493, .claude/ 165, .opencode/ 116, .agents/ 78, seed/ 48, aireviewguides/ 22, root 11, aitestmap/ 2 -- the default scan leaves out framework dirs). Uncertain files 559: <dynamic> bash sources 465, in-repo unresolved bash refs 93, java-unscanned 1.
> | - single-file change of every universe file (n=3364): uncertain_reference 65.5%, unmapped_path 34.5%, widened 0%.
> | - last 100 commits' name-status surfaces replayed on the current graph (n=96, approximation): unmapped_path 68.8%, deleted_path 19.8%, uncertain_reference 11.5%, widened 0%.
> | - with uncertain_reference bypassed (scratch seam): those 65.5% / 11.5% would widen.
> | Synthetic Gradle fixture (5 projects, one gradle-dynamic build): uncertain_reference 68.4%, unmapped_path 31.6% (root build files); bypassed, the 68.4% widen.
> | Known under-count: bash `source "$1"` records no <dynamic> at all (aitasks_go#t90 follow-up). Full tables: aitasks_go aiplans/archived/p77/p77_3_module_reach_and_widening.md (after archival).
