---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [testing, testmap, gates]
anchor: 1852
created_at: 2026-09-22 09:19
updated_at: 2026-09-22 09:19
---

## Goal

Part of the **testing engine / test map** feature — ten parent tasks, one per
module of the proposal. This is **M8 — Completion policy and gates**: what
completion runs, who decided it, and the gates that keep the map honest.

This module delivers the verifier exit contract (75 → `command_refused`, 3 →
`command_errored`) and the two environment variables every gate command sees;
the `testmap_check` consistency gate and the `testmap_fresh` procedure gate
that unlock `tests_pass`; the committed completion policy (`completion.mode:
full | selected`) as the `POLICY` arm of `ait test`; and the self-approving
`auto` policy that flips itself behind a cadence of full runs, recording its
approval in the engine's own ledger (`costs/policy.yaml`), never in the
committed declaration. Invariant 9 binds: one completion gate.

This task carries the module's cut — submodules, owned files, the interfaces
it provides and consumes, the seams later modules land into it — and the
planning protocol. It does **not** restate the specification.

**Proposal (authoritative for every detail):**
`aidocs/testing_engine/n014_explorer_006_proposal.md` — start at the *Module
Map* entry `#### M8 — Completion policy and gates`, then the *Components*
subsections tagged `(M8.x)` (listed under *Reading list* below), then the
narrative sections those components name. *Architecture*, *Design decisions*
and the *Invariants every module honours* apply to every module.

**Acceptance:** the union of the module's components' test lists (*Module Map —
How to read it*).

## Submodules (one child task each — settled at the coarse planning pass)

| submodule | scope | depends on | wave |
|---|---|---|---|
| **M8.1** Verifier exit contract and environment | `run_project_command_key()` rows 75 → error (`command_refused`) and 3 → error (`command_errored`) for opted-in keys, `AIT_GATE_TASK_ID` / `AIT_GATE_RUN_ID` exported around the command, `aitask_run_project_command.sh --task-id` exporting the former, the docblock table. Owns the two rows and exports in `lib/gate_verifier_lib.sh`, the export in `aitask_run_project_command.sh`, the `tests/test_gate_verifiers.sh` cases | — | A |
| **M8.2** `testmap_check` gate | `aitask_gate_testmap_check.sh` (`SEEDED:`, `ADOPTED:…`, `UNMAPPED_SOURCE:`, `--strict` past `bootstrap_until`), the `testmap_check` and `testmap_fresh` entries in `gates_reference.yaml` synced to `gates.yaml` (`unlocks: [tests_pass]`). Owns the verifier script, the two reference entries, the `tests/test_gates_reference_drift.sh` update | M2.1, M2.6, M4.2, M8.1 | D — see *Known inconsistencies* |
| **M8.3** `testmap_fresh` procedure gate | the skill `aitask-gate-testmap-fresh` (the stale workflow: `stale --task`, diffs per `STALE` row, retarget, re-stamp `EVIDENCED`, structural rows, `UNSTAMPED` prompts, never guess `UNKNOWN`, never confirm `STALE` autonomously, `adopted(… by <who>)` context); **its seeds step** (`onboard review --ids` for touched test files; attended pre-fill / confirm / override / trust-batch; autonomous `--agent-verdicts`) lands only when M7.2 exists. Owns `.claude/skills/aitask-gate-testmap-fresh/**`, goldens | M4.2, M4.3; seeds step: M7.1, M7.2 | E (without the seeds step) / G (seeds step) |
| **M8.4** Completion policy `full` / `selected` | the `completion:` block (`mode`, `deferred`, `on_empty_selection`, `engine_absent`), the `POLICY` arm of `aitask_test.sh` for `full` and `selected` (readiness re-check, `POLICY_DEMOTED:selected->full`), `fallback_command` under `engine_absent`, the `result=` field on the gate-run ledger block, `readiness`'s `POLICY:` line, the data the `--policy selected` re-entry writes. Owns the `POLICY` arm in `aitask_test.sh`, the `policy` package in `internal/feedback`, cases in `tests/test_ait_test_entrypoint.sh` | M3.2, M4.4, M5.1, M8.1 | E |
| **M8.5** Auto policy and cadence | `internal/feedback/cadence.go`, the `auto` arm of the `POLICY` step, `costs/policy.yaml` writes and `POLICY_WRITE:`, the front's `ait: testmap policy <flip\|full-run> (t<id>)` commit, `POLICY_FLIPPED:`, the three triggers, the `POLICY:auto\|…` line shapes, `cadence_declared`, the `CADENCE:` readiness line, `approved_by\|engine`, the window-score trigger in M4.4, the `next full in` and `FULL_GATE:` cadence fields on the brief. Owns `cadence.go`, the `auto` arm, the additive lines in `readiness` and `brief`, the `auto` matrix in `tests/test_ait_test_entrypoint.sh` | M3.4, M4.4, M5.2, M8.4 | G |

## Cross-module seams

**Provides** (defined here, consumed elsewhere):

- The verifier exit contract and the two environment variables — M8.1 → M5.1
  (mode), M8.4, M9.1 (the `build-verification.md` branch), M9.2.
- The consistency gate that unlocks `tests_pass` — M8.2.
- The before-commit freshness step and the in-gate reading site — M8.3 → M9.5
  (ports), M10.x.
- One gate whose meaning is a committed policy; the `completion:` block and
  the `POLICY:` lines — M8.4, M8.5 → M5.2 (brief), M6.1 (`detect --write`),
  M6.5 (`--policy selected`), M9.1.
- The self-approving policy behind the scheduled full run — M8.5.

**Consumes:** the registry and the adoption tables (M2.1, M2.6); the builtins
and the `fallback_command` path (M3.2); cost rows and the `costs/policy.yaml`
format (M3.4); the `stale` report and the evidence join (M4.2, M4.3);
`readiness` and the window score (M4.4); `ait test` and its `POLICY` hook
(M5.1); the brief (M5.2); packets and the verdict intake for M8.3's seeds step
(M7.1, M7.2); existing `lib/gate_verifier_lib.sh`,
`aitask_run_project_command.sh`, `.aitask-scripts/gates_reference.yaml` and
`tests/test_gates_reference_drift.sh`, the gate ledger in `lib/gate_ledger.py`.

**Hooks and extensions** (a file has one owner; a later submodule lands its
edit as the owner's named extension):

- M8.4 and M8.5 fill the `POLICY` hook that **M5.1** leaves in
  `aitask_test.sh`; their test cases land in M5.1's
  `tests/test_ait_test_entrypoint.sh`.
- M8.4 adds the `policy` package and M8.5 adds `cadence.go` to
  `internal/feedback` (**M4.4**'s); both add additive lines to `readiness`
  (M4.4) and `brief` (**M5.2**).
- M8.5 owns the *writer logic* of `costs/policy.yaml`; its format and helpers
  are **M3.4**'s. The engine's approval lives there, the human's in the
  committed `config.yaml` — never the other way round.
- M8.3 ships in wave E **without** its seeds step and gains it in wave G;
  whether that is one child with two phases or two children is settled at the
  coarse pass.
- `gates_reference.yaml` edits follow the edit protocol in its header (the
  maintainer `cp` to the live registry, the drift test, the
  `lib/gate_ledger.py` parser when a key is added).
- Invariants 1, 8 and 9 bind: a demotion runs full, a cadence full run is
  never skipped; a declared gate errors (exit 3) and never skips; `tests_pass`
  runs `./ait test --gate` and nothing else decides what completion means.

## Known inconsistencies in the proposal — settle at the coarse pass

- **M8.2 (wave D) lists M2.6 (wave E) as a dependency.** The same conflict
  exists for M4.1, M4.2 and M4.4; resolve it once with the M2 and M4 parents
  (move M2.6 forward, or ship `testmap_check` without the `SEEDED:` /
  `ADOPTED:` lines and let M2.6 extend it) and fix the proposal's tables
  (protocol §1).

## Reading list in the proposal

- *Module Map* — `#### M8`, *How to read it*, *Cross-module interfaces*,
  *Suggested implementation order* (waves A, D, E, G).
- *Components* — *Gates (M8.1 contract; M8.2 `testmap_check`; M8.3
  `testmap_fresh`)*, *Completion policy (M8.4)*, *Auto completion policy and
  cadence (M8.5)*, *Freshness (the gate M8.3)*, *Cost ledger (`policy.yaml`
  writer)*, *Feedback tools (cadence lines)*.
- *The Workflow Seam and the One Completion Gate* — *Gates*, *Completion
  policy*, *Verification of the seam, by module*.
- *Data Flow* — *A completion run under policy*, *The policy flip*.
- *The Agent Review Pass* — *The in-gate site (Step 8)*.
- *Overview* — *How the loop closes without a person* (mechanism 4).
- *Assumptions* / *Tradeoffs* — *Run surface and workflow (M5, M8, M9)*;
  *Open questions*.
- Framework rules that apply: `aidocs/gates/aitask-gate-framework.md`, the
  `aitask-gate-template` skill (verifier contract), the
  `aitask-gate-docs-updated` skill as the precedent for a procedure-backed
  gate.

## Planning and implementation protocol (binding for this task and every child)

This feature spans **ten parent tasks**, one per module of the proposal (see the
module → task map at the end). The modules are cut by ownership of files, verbs
and line protocols, not by Go package or by script, so children of different
parents touch the same packages and scripts and meet on the interfaces listed
above. Two consequences are binding.

### 1. Coarse planning pass — all ten modules, before any submodule is implemented

- Plan this task through the normal workflow (`/aitask-pick` → planning). In the
  Complexity Assessment choose **"Yes, create child tasks"** and decompose into
  **one child task per submodule row** in the table above (keep the `M<n>.<m>`
  id in the child name); let the workflow write the child plan files; at the
  child-task checkpoint choose **"Stop here"** so nothing is implemented. Do the
  same for the other nine parents, in wave order (A → I), **before implementing
  any child of any parent**.
- Keep the coarse plan coarse. A child's plan records what the proposal fixes for
  that submodule — scope, owned files, provided and consumed interfaces, the
  component test lists that are its acceptance — and its wave. It does **not**
  design internals against providers that do not exist yet; that is the reality
  check's job (§2 below), and the child plan must say so in as many words.
- Express cross-module order in task data, not in prose. Each child's `depends:`
  names the child ids of the other parents it consumes, in the `t<parent>_<m>`
  form (for example `depends: [t<M2 parent>_1]`), taken from the "depends on"
  column above. When the provider parent has not been planned yet, the child body
  records the `M<n>.<m>` reference and the dependency is filled with
  `./.aitask-scripts/aitask_update.sh --batch <child-id> --deps ...` as soon as
  the provider's children exist. After all ten parents are planned, one
  cross-linking pass checks every "depends on" cell against a real `depends:`
  entry, and checks the module → task map below against the parents' real ids.
- Parent-level `depends:` stays empty on purpose: module-level dependencies form
  a cycle (M6.5 → M8.2 / M8.4, M8.3 → M7.1 / M7.2, M7.1 → M6.2) and would block
  wrongly; the real graph is acyclic only at submodule granularity.
- Deviations from the proposal found while planning go into a **"Deviations from
  the proposal"** section of the plan. A wrong cut — a file two submodules must
  own, a dependency the wave table contradicts — is fixed **in the proposal**, not
  patched in a plan; that is the proposal's own falsifier
  (`assumption_modules_map_to_parent_tasks`). Send a note (`/aitask-note`) to
  every parent whose tables the change touches.

### 2. Reality check at child implementation time — a mandatory step in every child's plan

The coarse plan is a hypothesis written before its providers existed. **Every
child task's plan MUST carry an explicit "Reality check" step, executed before
any code is written, and its outcome MUST be recorded in the child's plan
file.** The step:

1. Re-reads the proposal's Module Map row for this submodule, its component
   subsections, and the row of every interface it consumes (the *Cross-module
   interfaces* table).
2. Inspects the **actual current state** of every provider it consumes — the
   verbs, line protocols, files, hooks and tests as they exist on the merge
   target now — and names the task and commit that landed each one. The
   proposal's description of a provider and the coarse plan's description of it
   are both claims to be verified, never facts to be assumed.
3. Tabulates every difference in three columns: *proposal says* / *coarse plan
   says* / *repository has*.
4. Decides, per difference: adapt this child to reality; or revise this child's
   coarse plan; or revise the proposal (cut errors and interface changes go
   there, per §1). Records the decision and its reason.
5. Sends a note (`/aitask-note`) to every downstream child whose assumptions a
   difference or a decision breaks, hedging what cannot be proven from the tree.
6. Re-confirms that every file this child will touch is owned by this submodule,
   or that the edit lands as the owner's named extension (the "one owning
   submodule" rule in *Module Map — How to read it*).

A child whose plan lacks this step, or whose step is not recorded as executed,
is not implementing this task as specified.

## Module → task map

| module | parent task |
|---|---|
| M1 — Engine foundation and distribution | t1852 |
| M2 — Registry and map model | t1853 |
| M3 — Runners, scheduling and cost | t1854 |
| M4 — Selection, freshness and feedback | t1855 |
| M5 — Run surface | t1856 |
| M6 — Onboarding | t1857 |
| M7 — Agent review and author annotation | t1858 |
| M8 — Completion policy and gates | t1859 |
| M9 — Workflow integration, skills and documentation | t1860 |
| M10 — Rollout to the target repositories | t1861 |

All ten share the topic anchor of the M1 task, so the board's By-Topic view
shows the whole feature as one lane.
