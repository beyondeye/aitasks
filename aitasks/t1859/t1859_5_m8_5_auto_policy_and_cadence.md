---
priority: medium
effort: high
depends: [t1859_4, t1854_4]
xdeps: [t65_2]
xdeprepo: aitasks_go
issue_type: feature
status: Postponed
labels: [testing, testmap, gates]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-19 15:43
updated_at: 2026-10-30 12:10
---

Split (aitasks_go#t22 cutover): the engine half of this task is aitasks_go#t65_2
in beyondeye/aitasks_go. This body is the framework half.

Child of t1859 (test-map **M8 — Completion policy and gates**), submodule
**M8.5 — Auto policy and cadence**, wave **G**: the bash front. This is the
self-approving `auto` policy, which closes the loop without a person:
- `ait test --gate` flips to the selection on the first `ADMISSIBLE` run,
  recording `approved_by: engine:readiness@<run>` in the engine's own ledger
  `aitestmap/costs/policy.yaml` (never in `config.yaml`);
- a cadence (`full_run_every {tasks, selection_ratio_above, days}`) forces full
  runs, so scoring never stops;
- an unmet criterion demotes loudly.

The decision, the cadence (`cadence.go`), the verb `policy`'s `auto` arm and
both `policy.yaml` writes, and the `readiness` / `score` / `brief` lines are
aitasks_go#t65_2. This task adds the front's `auto` arm, invokes the verb, commits
the file the engine wrote, and writes `result=`. It waits on aitasks_go#t65_2
through `xdeps` (`xdeprepo: aitasks_go`), which unblocks only when
aitasks_go#t65_2 is Done. Its tests use a fake engine that speaks the verb's
published `auto` line protocol.

Authoritative spec: `aidocs/testing_engine/n014_explorer_006_proposal.md` —
the `#### M8` row, components *Auto completion policy and cadence*, *Cost
ledger* (`policy.yaml`, the full-suite p95), *Feedback tools* (cadence lines)
and *Agent brief*, *Data Flow → The policy flip*, *Overview → How the loop
closes* (mechanism 4), Invariants 1 / 5 / 7 / 9, and Open question 13. The
parent plan `aiplans/p1859_testmap_m8_completion_policy_and_gates.md` lists
the cut fixes in *Deviations*: Dev 2 and Dev 7.

This coarse plan records what the proposal fixes for M8.5's front. It does
not design internals against providers that do not exist yet; the Reality
check does that when this child is picked.

## Dependency hold

`Postponed` because its providers have not landed:

- **aitasks_go#t65_2** (the `auto` arm of the verb, the writes, the cadence):
  `xdeps`.
- **M5.1** (`aitask_test.sh` and its `POLICY` hook,
  `tests/test_ait_test_entrypoint.sh`), in t1856, reached through t1859_4.

In `depends:`: M8.4 `t1859_4` (the front's `full` / `selected` arms), M3.4
`t1854_4` (landed). The M4.4 (`readiness`, `score`) and M5.2 (`brief`) holds
are engine-side: aitasks_go#t65_2 holds on them in aitasks_go. If t1855 adds an
`xdeps` entry on aitasks_go#t61's M4.4 child here, keep it. Never depend on a whole
provider parent. Flip this task to `Ready` once nothing in its hold is left
unresolved.

## Key Files to Modify

- `.aitask-scripts/aitask_test.sh`: the `auto` arm, the `POLICY:auto|…` line
  shapes, and the path-scoped commit `ait: testmap policy <flip|full-run>
  (t<id>)` of `aitestmap/costs/policy.yaml` after the engine's
  `POLICY_WRITE:` (the engine never commits). A cadence full run ignores
  `on_empty_selection`. `result=` carries `policy:auto|next_full_in:<n>` or
  `cadence:<trigger>`, within the 200-character cap.
- `tests/test_ait_test_entrypoint.sh`: the `auto` matrix (fake engine).

## Reference Files for Patterns

- `./ait git` versus plain git: `policy.yaml` is code-branch data, so commit it
  with plain `git commit -- <path>`, path-scoped.
- The result carrier rules are in t1859_4's body and in the
  `run_project_command_key()` docblock of `.aitask-scripts/lib/gate_verifier_lib.sh`.

## Implementation Plan

0. **Reality check (MANDATORY, before any code; record the outcome).** Stop if
   aitasks_go#t65_2 or M5.1 has not landed. Read aitasks_go#t65_2's published `auto`
   protocol and build the fake engine from it. Decide the commit / worktree
   side of the concurrent-counter question: several sessions or worktrees may
   write and commit `policy.yaml`; aitasks_go#t65_2 decides the lock and the
   read-modify-write; this task decides the commit and merge behaviour, with
   a rule that fails toward running more.
1. Add the front's arm and commit.
2. Write the tests.

## Verification Steps

- The `auto` matrix through the front (fake engine):
  - `NOT_YET` → full;
  - first `ADMISSIBLE` → flip, write, and a path-scoped commit;
  - each cadence trigger → full;
  - the steady selection with the counter incremented;
  - a cadence full run ignores `on_empty_selection`.
- The `result=` shapes stay within the 200-character cap.

## Carried obligations (framework half)

- Intro / "`ait test --gate` flips to the selection on the first `ADMISSIBLE` run, recording `approved_by: engine:readiness@<run>` in … `aitestmap/costs/policy.yaml` (never in `config.yaml`)" — Intro: the front invokes the verb and commits; the decision and write are aitasks_go#t65_2's
- Intro / "a cadence (`full_run_every {tasks, selection_ratio_above, days}`) forces full runs, so scoring never stops" — Intro; the cadence is aitasks_go#t65_2's, the front honours a cadence full run (*Key Files*)
- Intro / "an unmet criterion demotes loudly" — Intro and *Key Files* (the front prints the demotion line it receives)
- `## Dependency hold` / "In `depends:`: M8.4 `t1859_4`, M3.4 `t1854_4`" — *Dependency hold*, `depends:` paragraph (t1859_4, t1854_4) plus `xdeps` on aitasks_go#t65_2
- Key Files / "`aitask_test.sh`: the `auto` arm, the `POLICY:auto|…` line shapes" — *Key Files*, `aitask_test.sh` bullet
- Key Files / "the path-scoped commit `ait: testmap policy <flip|full-run> (t<id>)` (the engine never commits)" — *Key Files*, `aitask_test.sh` bullet (path-scoped commit)
- Key Files / "A cadence full run ignores `on_empty_selection`" — *Key Files*, `aitask_test.sh` bullet
- Key Files / "`result=` carries `policy:auto|next_full_in:<n>` or `cadence:<trigger>`" — *Key Files*, `aitask_test.sh` bullet (`result=`)
- Key Files / "`tests/test_ait_test_entrypoint.sh`: the `auto` matrix" — *Key Files*, entrypoint matrix bullet
- Reference / "`policy.yaml` is code-branch data, so commit it with plain `git commit -- <path>`, path-scoped" — *Reference Files for Patterns*, plain-git bullet
- Plan step 0 / "Reality check … Stop if M3.4, M4.4 or M5.2 has not landed. Decide how the committed counter behaves when several sessions or worktrees write it concurrently: a lock, read-modify-write, and a merge rule that fails toward running more" — *Implementation Plan* step 0 (stops on aitasks_go#t65_2 and M5.1; the commit / merge side of the concurrency decision)
- Plan step 3 / "Add the front's arm and commit" — *Implementation Plan* step 1
- Plan step 5 / "Write the tests" — *Implementation Plan* step 2 (entrypoint matrix); the Go tests are aitasks_go#t65_2's
- Verification / "`auto` matrix: `NOT_YET` → full" — *Verification Steps*, matrix bullet (front path)
- Verification / "first `ADMISSIBLE` → flip, write, and a path-scoped commit" — *Verification Steps*, matrix bullet (path-scoped commit)
- Verification / "each cadence trigger → full" — *Verification Steps*, matrix bullet (front path)
- Verification / "the steady selection with the counter incremented" — *Verification Steps*, matrix bullet (front path)
- Verification / "a cadence full run ignores `on_empty_selection`" — *Verification Steps*, matrix bullet (`on_empty_selection` ignored)

## Relocated to aitasks_go

The engine scope below moved to aitasks_go#t65_2 and is quoted for reference only.

> - `goengines/internal/testmap/feedback/cadence.go`: the three triggers (`selected_since_full ≥ tasks`; selection estimate ≥ `selection_ratio_above` × newest full-suite p95 on the host class via `cost.FullSuiteP95`; `now − last_full_run.at ≥ days`), under 50 ms; API callable by a second mode (`module`, t2131_8).
> - The verb `policy` `auto` arm with its two write points through `cost.ReadPolicy`/`cost.WritePolicy` (`contract`, `CONTRACT_MISMATCH` refusal), each printing `POLICY_WRITE:`; pre-run flip (`POLICY_FLIPPED:auto->selected|engine:readiness@<run>`) or demotion (`POLICY_DEMOTED:auto->full|<criterion>`, clearing `approved_by`), post-run full-run reset or selected increment; the concurrency decision for the read-modify-write (lock / merge rule that fails toward running more).
> - Readiness `cadence_declared`, `CADENCE:`, `approved_by|met|engine`; `score` window-score trigger; brief `next full in <n>` and cadence on `FULL_GATE:`.
> - Acceptance checks:
>   - engine-side `auto` decision matrix (`NOT_YET` → full; first `ADMISSIBLE` → flip + write; each trigger → full; steady selected increments the counter; demotion clears `approved_by`);
>   - engine tests for the window score attributing a miss to the right task;
>   - cadence budget < 50 ms;
>   - `ait engine test` green;
>   - engine never commits and never writes `config.yaml`.


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

> **✉ note:t2131_1** id=2026-10-24T21:26:01Z.85a4ac0de126ff7f4d25d33d from=t2131_1 from_verified=yes at=2026-10-24T21:26:01Z base=5adc28fe429efa614cfea3e208dce4cfcc83d765 base_branch=main dirty=no host=omg16
>
> | Advisory, from t2131_1. Not an instruction; your own planning decides. The claims below are tree-relative, as of commit 5adc28fe4 (main), which amends aidocs/testing_engine/n014_explorer_006_proposal.md.
> | 
> | The `module` arm from the 2026-10-23 t2131 note is now in the proposal, in component *Auto completion policy and cadence* → "The `module` arm". It reuses `cadence.go`, the `policy` verb and both `policy.yaml` write points, with no second implementation.
> | 
> | **Changed relative to the earlier note:**
> | - The decision order is now **two exclusive admission branches**:
> |   - *approved* means `approved_by` with `mode: module`; one recorded under `mode: auto` does not count;
> |   - **not approved:** `NOT_YET` → full (`not_yet:<c>`, nothing written); `ADMISSIBLE` → `approved_by {…, mode: module}`, `POLICY_FLIPPED:module->module|…`, and the run continues;
> |   - **approved:** any unmet criterion → `POLICY_DEMOTED:module->full|<criterion>` and `approved_by` cleared (the only branch that clears it); all criteria met → continue.
> | - The steps after admission:
> |   - a due cadence trigger (ratio on the widened estimate) → full;
> |   - a widening fallback → full (`widen_full:<reason>`) through the canonical full-run path; the widening is computed once, before the cadence step;
> |   - otherwise `module|next_full_in:<n>`.
> | - Readiness criteria under `module` are judged on the **widened** prediction sets (*Feedback tools* → "Which prediction set readiness judges"); `auto` still uses plain sets.
> | - `policy.yaml`'s `approved_by.mode` is `auto|module`.
> | - `completion.widen` does not exist.
> | 
> | **Possibly relevant to your own arm (an observation, unverified against any code):** the `auto` arm's prose in the same component still lists "`NOT_YET` → full" and "a later unmet criterion → `POLICY_DEMOTED:auto->full` and `approved_by` cleared" as separate items. A first-match reading never reaches the demotion for an already-approved policy. The `module` arm now states the split explicitly; mirroring it for `auto` may avoid the same ambiguity.

> **✉ note:t22_3** id=2026-10-29T22:23:04Z.38c1cf44279f7d18b27c6580 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:23:04Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.
