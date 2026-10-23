---
priority: medium
effort: high
depends: [t1859_4, t1854_4]
issue_type: feature
status: Postponed
labels: [testing, testmap, gates]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-19 15:43
updated_at: 2026-10-19 15:44
---

Child of t1859 (test-map **M8 — Completion policy and gates**), submodule
**M8.5 — Auto policy and cadence**, wave **G**. This is the self-approving
`auto` policy, which closes the loop without a person:
- `ait test --gate` flips to the selection on the first `ADMISSIBLE` run,
  recording `approved_by: engine:readiness@<run>` in the engine's own ledger
  `aitestmap/costs/policy.yaml` (never in `config.yaml`);
- a cadence (`full_run_every {tasks, selection_ratio_above, days}`) forces full
  runs, so scoring never stops;
- an unmet criterion demotes loudly.

Authoritative spec: `aidocs/testing_engine/n014_explorer_006_proposal.md` —
the `#### M8` row, components *Auto completion policy and cadence*, *Cost
ledger* (`policy.yaml`, the full-suite p95), *Feedback tools* (cadence lines)
and *Agent brief*, *Data Flow → The policy flip*, *Overview → How the loop
closes* (mechanism 4), Invariants 1 / 5 / 7 / 9, and Open question 13. The
parent plan `aiplans/p1859_testmap_m8_completion_policy_and_gates.md` lists
the cut fixes in *Deviations*: Dev 2 and Dev 7.

This coarse plan records what the proposal fixes for M8.5. It does not design
internals against providers that do not exist yet; the Reality check does that
when this child is picked.

**Automation-first:** this is the automated approval. Every write carries its
provenance.

## Dependency hold

`Postponed` only because providers have no child ids yet:

- **M4.4** (`readiness`, `score`), in t1855;
- **M5.2** (`brief`), in t1856.

Each provider parent's coarse pass adds the ids and flips this task to `Ready`
once nothing is left unresolved. In `depends:`: M8.4 `t1859_4`, M3.4
`t1854_4`. Never depend on a whole provider parent.

## Key Files to Modify

- `goengines/internal/testmap/feedback/cadence.go`: the three triggers. They
  are:
  - `selected_since_full ≥ tasks`;
  - the selection estimate ≥ `selection_ratio_above` × the newest full-suite
    p95 on this host class (the disjoint M3.4 figure);
  - `now − last_full_run.at ≥ days`.

  Budget: the check takes < 50 ms.
- The verb `policy` (from M8.4): the `auto` arm and the two write points. Each
  goes through M3.4's `policy.yaml` helpers (`contract` field, refusing
  `CONTRACT_MISMATCH`) and prints `POLICY_WRITE:aitestmap/costs/policy.yaml`:
  - pre-run: flip `POLICY_FLIPPED:auto->selected|engine:readiness@<run>`, or
    demotion `POLICY_DEMOTED:auto->full|<criterion>` clearing `approved_by`;
  - post-run: a full-run reset of `last_full_run` and
    `selected_since_full := 0`, or a selected increment.
- `.aitask-scripts/aitask_test.sh`: the `auto` arm, the `POLICY:auto|…` line
  shapes, and the path-scoped commit `ait: testmap policy <flip|full-run>
  (t<id>)` (the engine never commits). A cadence full run ignores
  `on_empty_selection`. `result=` carries `policy:auto|next_full_in:<n>` or
  `cadence:<trigger>`.
- `readiness` (M4.4's): `cadence_declared` (`tasks ≥ 2`,
  `0 < ratio ≤ 1`, `days ≥ 1`), `CADENCE:`, and `approved_by|met|engine`.
- `score` (M4.4's): the window-score trigger after a cadence full run.
- `brief` (M5.2's): `next full in <n>` and the cadence on `FULL_GATE:`.
- `tests/test_ait_test_entrypoint.sh`: the `auto` matrix.

## Reference Files for Patterns

- M3.4's `policy.yaml` helpers (t1854_4).
- `./ait git` versus plain git: `policy.yaml` is code-branch data, so commit it
  with plain `git commit -- <path>`, path-scoped.

## Implementation Plan

0. **Reality check (MANDATORY, before any code; record the outcome).** Stop if
   M3.4, M4.4 or M5.2 has not landed. Decide how the committed counter
   behaves when several sessions or worktrees write it concurrently: a lock,
   read-modify-write, and a merge rule that fails toward running more.
1. Write `cadence.go`.
2. Add the verb's `auto` arm and writes.
3. Add the front's arm and commit.
4. Add the readiness, score and brief lines.
5. Write the tests.

## Verification Steps

- The `auto` matrix:
  - `NOT_YET` → full;
  - first `ADMISSIBLE` → flip, write, and a path-scoped commit;
  - each cadence trigger → full;
  - the steady selection with the counter incremented;
  - a demotion clears `approved_by`;
  - a cadence full run ignores `on_empty_selection`.
- Engine tests for the window score attributing a miss to the right task.
- Cadence budget.
- `ait engine test` green.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1854_4** id=2026-10-20T09:37:06Z.00dde778c4368dd90b787ad1 from=t1854_4 from_verified=yes at=2026-10-20T09:37:06Z base=d70250f708143ce51667dd1491ae34f6919a4df5 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1854_4 (M3.4) as landed in 487271c89. These are tree claims: re-verify in your Reality check.
> | 
> | - **policy.yaml helpers:** `cost.ReadPolicy(root) (Policy, found, err)` and `cost.WritePolicy(root, p) (changed, err)`, with `cost.PolicyPath = aitestmap/costs/policy.yaml`.
> |   - Schema: `{contract, last_full_run{run_id, at, task, sha}, selected_since_full, approved_by{who, at, mode, statement}}`.
> |   - Unknown keys are kept and re-written.
> |   - A newer `contract:` is a `*testmap.ContractMismatchError` (`CONTRACT_MISMATCH`, exit 3) on read **and** on write.
> | - **Not covered:** `WritePolicy` is a whole-value write. A read-modify-write across your two write points is not serialized by M3.4; add your own lock if the verb can race.
> | - **Full-suite p95:** `cost.FullSuiteP95(table)` returns `{MS, RunID, Unmeasured, OK}`. It is disjoint (a suite parent's own time, never parent + children). `OK=false` until a `full-` `--all` run with every invocation cause-free and unrefused has been folded. Load the table with `cost.Load(root, cfg.HostClass())`.

> **✉ note:t2131** id=2026-10-23T08:56:00Z.9fcd04559e9bdfddb04d95e7 from=t2131 at=2026-10-23T08:56:00Z base=6b3161606e2989d1865628155f4e0bc1021cb917 base_branch=main dirty=yes host=omg16
>
> | t2131_8 (`module_completion_mode`, Postponed) depends on this task. It plans to **reuse** your `cadence.go`, engine approval and `policy.yaml` writes, rather than copy them.
> | 
> | - **Decision order planned for `module`** (it mirrors `auto`):
> |   1. NOT_YET → full;
> |   2. the first ADMISSIBLE → engine approval recorded with `mode: module`;
> |   3. a due cadence trigger (`selection_ratio_above` on the widened estimate) → full;
> |   4. an unmet criterion → `POLICY_DEMOTED:module->full|<criterion>`;
> |   5. a reach fallback → full;
> |   6. otherwise `module|next_full_in:<n>`.
> | - **Counters.** A full run resets them; a module run increments `selected_since_full`.
> | - **`cadence_declared`** becomes a readiness criterion for `module` too, so `module` requires a valid `full_run_every`.
> | - **`auto`** never lands on `module` in v1.
> | 
> | Advisory: shaping the cadence API so a second mode can call it, instead of hard-wiring `auto`, would help t2131_8.
> | 
> | Plans: `aiplans/p2131/p2131_8_module_completion_mode.md`.
