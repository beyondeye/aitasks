---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [testing, testmap, gates]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1859_2, t1859_3, t1859_4, t1859_5, t1859_6]
anchor: 1852
created_at: 2026-09-22 09:19
updated_at: 2026-10-30 12:10
---

Split (aitasks_go#t22 cutover): the engine half of this task is aitasks_go#t65
in beyondeye/aitasks_go. This body is the framework half.

## Goal

Part of the **testing engine / test map** feature — ten parent tasks, one per
module of the proposal. This is **M8 — Completion policy and gates**: what
completion runs, who decided it, and the gates that keep the map honest.

This module delivers the verifier exit contract (75 → `command_refused`, 3 →
`command_errored`) and the two environment variables every gate command sees;
the `testmap_check` consistency gate and the `testmap_fresh` procedure gate
that precede `tests_pass`; the committed completion policy (`completion.mode:
full | selected`) as the `POLICY` arm of `ait test`; and the self-approving
`auto` policy that flips itself behind a cadence of full runs, recording its
approval in the engine's own ledger (`costs/policy.yaml`), never in the
committed declaration. Invariant 9 binds: one completion gate.

Since the t22 cutover, the engine Go of M8.4 and M8.5 (the `policy` package,
the verb `policy`, `cadence.go`, the `readiness` / `brief` / `score` lines)
lives in aitasks_go#t65 and its children aitasks_go#t65_1 and aitasks_go#t65_2 in
beyondeye/aitasks_go. This task stays the M8 parent for the framework
children: t1859_2 (M8.2), t1859_3 (M8.3), t1859_6 (the seeds step) and the
framework halves of t1859_4 / t1859_5 (the `POLICY` arms in `aitask_test.sh`,
`fallback_command`, the `result=` lines, the policy commit, the
`tests/test_ait_test_entrypoint.sh` cases). t1859_4 and t1859_5 wait on their
engine halves through `xdeps`.

This task carries the module's cut — submodules, owned files, the interfaces
it provides and consumes, the seams later modules land into it — and the
planning protocol. It does **not** restate the specification.

**Proposal (authoritative for every detail):**
`aidocs/testing_engine/n014_explorer_006_proposal.md` — start at the *Module
Map* entry `#### M8 — Completion policy and gates`, then the *Components*
subsections tagged `(M8.x)` (listed under *Reading list* below), then the
narrative sections those components name. *Architecture*, *Design decisions*
and the *Invariants every module honours* apply to every module.

**Acceptance:** the union of the framework components' test lists (*Module
Map — How to read it*): M8.2, M8.3, the seeds step, and the front halves of
M8.4 / M8.5. The engine lists are aitasks_go#t65's.

## Submodules (one child task each — settled at the coarse planning pass)

| submodule | scope | depends on | wave |
|---|---|---|---|
| **M8.1** Verifier exit contract and environment | landed (t1859_1): rows 75 / 3 in `run_project_command_key()`, `AIT_GATE_TASK_ID` / `AIT_GATE_RUN_ID` / `AIT_GATE_RESULT_FILE`, `aitask_run_project_command.sh --task-id`, the docblock, `tests/test_gate_verifiers.sh` cases | — | A |
| **M8.2** `testmap_check` gate (t1859_2) | `aitask_gate_testmap_check.sh`: engine exits 0/1/2/3/64 and a missing engine map to 0/1/3/3/3/3. It always runs `check --strict`, with `bootstrap_until` as the strict flip. It reports `SEEDED:` / `ADOPTED:…` and the task's `UNMAPPED_SOURCE:` (failing past `bootstrap_until`). On `UNSTAMPED` it fails with a repair handoff. It adds the `testmap_check` entry to `gates_reference.yaml`, synced to `gates.yaml`, with **no `unlocks`**. Owns the verifier script, its reference entry, its allowlist entries, and the `tests/test_gates_reference_drift.sh` update | M2.1, M2.6 (landed), M4.2 (aitasks_go#t61, not yet decomposed), M8.1 (landed) | E |
| **M8.3** `testmap_fresh` procedure gate (t1859_3) | the skill `aitask-gate-testmap-fresh` and its stale workflow: `stale --task`, diffs per `STALE` row, retarget, re-stamp `EVIDENCED`, structural rows, never guess `UNKNOWN`, `adopted(… by <who>)` context. The autonomous lane never confirms `STALE` and never first-stamps. `UNSTAMPED` is a `pass` during bootstrap and otherwise a `fail` with a handoff to t1853_7. Also owns the `testmap_fresh` registry entry and the five `ait testmap` allowlist entries, `.claude/skills/aitask-gate-testmap-fresh/**`, goldens | M4.2, M4.3 (aitasks_go#t61, not yet decomposed) | E |
| **M8.3 seeds step** (t1859_6) | the seeds step of the same skill: `onboard review --ids` for touched test files; attended pre-fill / confirm / override / trust-batch; autonomous `--agent-verdicts` | M8.3, M7.1, M7.2 (aitasks_go#t64, not yet decomposed) | G |
| **M8.4 front** (t1859_4) | the `POLICY` arm of `aitask_test.sh` for `full` and `selected` (calling the engine's `policy decide` / `readiness`, `POLICY_DEMOTED:selected->full`), `on_empty_selection`, `deferred`, `fallback_command` under `engine_absent`, the `result=` field written through M8.1's `AIT_GATE_RESULT_FILE`, cases in `tests/test_ait_test_entrypoint.sh`. The `policy` package, the verb and the `readiness` line are aitasks_go#t65_1 | M8.1, M3.2 (landed), M5.1 (t1856, not yet decomposed), aitasks_go#t65_1 (`xdeps`) | E |
| **M8.5 front** (t1859_5) | the `auto` arm of the `POLICY` step, the `POLICY:auto\|…` line shapes, the front's `ait: testmap policy <flip\|full-run> (t<id>)` commit of `aitestmap/costs/policy.yaml`, a cadence full run ignoring `on_empty_selection`, `result=` carrying `policy:auto\|next_full_in:<n>` or `cadence:<trigger>`, the `auto` matrix in `tests/test_ait_test_entrypoint.sh`. `cadence.go`, the verb's `auto` arm and writes, and the `readiness` / `score` / `brief` lines are aitasks_go#t65_2 | t1859_4, aitasks_go#t65_2 (`xdeps`) | G |

## Cross-module seams

**Provides** (defined here, consumed elsewhere):

- The verifier exit contract and the two environment variables — M8.1 → M5.1
  (mode), M8.4, M9.1 (the `build-verification.md` branch), M9.2.
- The consistency gate placed before `tests_pass` (by list position) — M8.2.
- The before-commit freshness step and the in-gate reading site — M8.3 → M9.5
  (ports), M10.x.
- One gate whose meaning is a committed policy: the front's `POLICY` arms and
  `result=` lines, and the `completion:` block data — M8.4, M8.5 → M6.5
  (`--policy selected`), M9.1. The engine's `POLICY:` lines → M5.2 and M6.1
  are aitasks_go#t65's.
- The self-approving policy behind the scheduled full run — M8.5 (front here,
  cadence and writes in aitasks_go#t65_2).

**Consumes:** the registry and the adoption tables (M2.1, M2.6); the builtins
and the `fallback_command` path (M3.2); cost rows and the `costs/policy.yaml`
format (M3.4); the `stale` report and the evidence join (M4.2, M4.3, from
aitasks_go#t61); `readiness` and the window score (M4.4, aitasks_go#t61); `ait test`
and its `POLICY` hook (M5.1); the brief (M5.2, aitasks_go#t62); packets and the
verdict intake for M8.3's seeds step (M7.1, M7.2, aitasks_go#t64); the `policy`
verb (aitasks_go#t65_1, aitasks_go#t65_2); existing `lib/gate_verifier_lib.sh`,
`aitask_run_project_command.sh`, `.aitask-scripts/gates_reference.yaml` and
`tests/test_gates_reference_drift.sh`, the gate ledger in
`lib/gate_ledger.py`. Engine outputs are consumed through the shim; the bash
tests use a fake engine.

**Hooks and extensions** (a file has one owner; a later submodule lands its
edit as the owner's named extension):

- M8.4 and M8.5 fill the `POLICY` hook that **M5.1** leaves in
  `aitask_test.sh`; their test cases land in M5.1's
  `tests/test_ait_test_entrypoint.sh`.
- M8.3 ships in wave E **without** its seeds step and gains it in wave G, as
  two children (t1859_3, t1859_6).
- M8.1's result carrier `AIT_GATE_RESULT_FILE` is written by the bash front
  (M8.4 / M8.5), never by the engine.
- The front reads `runners.yaml`'s full-suite `fallback_command:` itself when
  the engine is absent (`completion.engine_absent: fallback_command`), with no
  engine to parse `runners.yaml` (t1854 note).
- The gate chain `testmap_fresh` → `testmap_check` → `tests_pass` is set by
  list position. No M8 gate declares `unlocks`, because any explicit
  `unlocks` switches the whole declared set to DAG mode. M6.5's `enable` owns
  the order, and refuses a set that is already a DAG
  (`ENABLE_REFUSED:gate_dag_mode|…`).
- An `UNSTAMPED` failure under `require_stamp` past `bootstrap_until` is
  handed to the automated repair coordinator t1853_7 (engine half
  aitasks_go#t59_1). Unattended completion in that configuration requires it
  (rollout prerequisite). t1853_7 consumes M8.2 and M8.3 to repair
  check / freshness failures and rerun the real verifier.
- **Automation-first:** no path requires a person. `selected`'s human
  `approved_by` is an optional attended alternative to the self-approving
  `auto`. The freshness gate's autonomous lane never confirms `STALE` and
  never invents a stamp.
- `gates_reference.yaml` edits follow the edit protocol in its header (the
  maintainer `cp` to the live registry, the drift test, the
  `lib/gate_ledger.py` parser when a key is added).
- Invariants 1, 8 and 9 bind: a demotion runs full, a cadence full run is
  never skipped; a declared gate errors (exit 3) and never skips; `tests_pass`
  runs `./ait test --gate` and nothing else decides what completion means.

## Contract notes for the gate children (from the notes this task received; re-verify)

- **`check` contract** (t1853_1, t1853_6): exits 0 pass, 1 failing finding, 2
  `TESTMAP_ABSENT:aitestmap/`, 3 `CONTRACT_MISMATCH` / `REGISTRY_INVALID` /
  `INPUT_UNAVAILABLE` / `INPUT_ERROR` / `CHECK_ERROR` (stderr, nothing on
  stdout), 64 usage. Stdout is the findings, then
  `CHECK:<pass|fail>|<findings>|<failing>`. `check` always prints `SEEDED:<n>`
  and `ADOPTED:<n>|human <h>|agent <a>|auto <m>` just before `CHECK:`; they
  are not counted and never fail. The M2.6 reports are Info findings that
  never fail, even under `--strict` past `bootstrap_until`.
- **Permission touchpoints** (t1852): the first skill of this module that
  calls `ait testmap` owes the five-touchpoint checklist
  (`.claude/settings.local.json`, `.codex/rules/default.rules`,
  `seed/claude_settings.local.json`, `seed/codex_rules.default.rules`,
  `seed/opencode_config.seed.json`); t1859_3 takes it.
- **M2.6** (t1853): t1853_6 has landed, so the M8.2 child records it as a
  landed provider.

## Known inconsistencies in the proposal — settled

- **Resolved.** M8.2 listed M2.6 (then wave E) as a dependency; M2.6 has
  since moved to wave B (t1853, `3bc0de8ac`). The remaining conflict, M8.2
  (wave D) depending on M4.2 (wave D), is resolved by moving M8.2 to wave E.
  The full set of cut fixes is in `aiplans/p1859_*.md` (*Deviations*).

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
module → task map at the end). Since the t22 cutover the engine halves of
several parents live in beyondeye/aitasks_go. The modules are cut by ownership
of files, verbs and line protocols, so children of different parents meet on
the interfaces listed above. Two consequences are binding.

### 1. Coarse planning pass — done for M8

- M8's coarse pass already ran: one child per submodule row (t1859_1–t1859_6),
  "Stop here". The cutover re-decomposed the engine halves of M8.4 / M8.5 under
  aitasks_go#t65 and added the cross-repo edges t1859_4 → aitasks_go#t65_1 and
  t1859_5 → aitasks_go#t65_2.
- Keep each child plan coarse: it does **not** design internals against
  providers that do not exist yet; that is the reality check's job (§2 below).
- Express cross-module order in task data, not in prose: `depends:` inside
  this repository, `xdeps` (`xdeprepo: aitasks_go`) on aitasks_go tasks. The
  holds on M4.2 / M4.3 / M4.4 (aitasks_go#t61), M7.1 / M7.2 (aitasks_go#t64) and M5.1
  (t1856) are wired by those parents' coarse passes (t1855, t1858, t1856)
  when their child ids exist.
- Parent-level `depends:` stays empty on purpose: module-level dependencies
  form a cycle (M6.5 → M8.2 / M8.4, M8.3 → M7.1 / M7.2, M7.1 → M6.2) and would
  block wrongly; the real graph is acyclic only at submodule granularity.
- Deviations from the proposal go into a **"Deviations from the proposal"**
  section of the plan. A wrong cut is fixed **in the proposal**, not patched
  in a plan (`assumption_modules_map_to_parent_tasks`). Send a note
  (`/aitask-note`) to every parent whose tables the change touches, including
  the aitasks_go halves (`--project aitasks_go`).

### 2. Reality check at child implementation time — a mandatory step in every child's plan

**Every child task's plan MUST carry an explicit "Reality check" step, executed
before any code is written, and its outcome MUST be recorded in the child's
plan file.** The step:

1. Re-reads the proposal's Module Map row for this submodule, its component
   subsections, and the row of every interface it consumes.
2. Inspects the **actual current state** of every provider it consumes and
   names the task and commit that landed each one. Engine providers are
   inspected in beyondeye/aitasks_go (or through the installed engine and
   `goengines/README.md` exports).
3. Tabulates every difference: *proposal says* / *coarse plan says* /
   *repository has*.
4. Decides, per difference: adapt; revise the coarse plan; or revise the
   proposal. Records the decision and its reason.
5. Sends a note (`/aitask-note`) to every downstream child whose assumptions a
   difference or a decision breaks, hedging what cannot be proven.
6. Re-confirms that every file this child will touch is owned by this
   submodule, or that the edit lands as the owner's named extension.

A child whose plan lacks this step, or whose step is not recorded as executed,
is not implementing this task as specified.

## Acceptance

- The union of the M8.2 / M8.3 / seeds-step component test lists plus the
  front halves of M8.4 / M8.5 is green in the bash suite (fake engine).
- The drift test is green; the five allowlist touchpoints are present.
- The cross-repo edges t1859_4 → aitasks_go#t65_1 and t1859_5 → aitasks_go#t65_2 are
  recorded (`xdeps`, `xdeprepo: aitasks_go`).
- The body points to aitasks_go#t65 (header above).

## Module → task map

| module | framework (aitasks) | engine (aitasks_go) |
|---|---|---|
| M1 — Engine foundation and distribution | t1852 (landed) | — |
| M2 — Registry and map model | t1853 | aitasks_go#t59 |
| M3 — Runners, scheduling and cost | t1854 | aitasks_go#t60 |
| M4 — Selection, freshness and feedback | t1855 (tracker) | aitasks_go#t61 |
| M5 — Run surface | t1856 | aitasks_go#t62 (M5.2 `brief`) |
| M6 — Onboarding | t1857 | aitasks_go#t63 |
| M7 — Agent review and author annotation | t1858 | aitasks_go#t64 |
| M8 — Completion policy and gates | t1859 | aitasks_go#t65 (aitasks_go#t65_1, aitasks_go#t65_2) |
| M9 — Workflow integration, skills and documentation | t1860 | — |
| M10 — Rollout to the target repositories | t1861 | — |

All ten aitasks parents share the topic anchor of the M1 task, so the board's
By-Topic view shows the whole feature as one lane.

## Carried obligations (framework half)

- `## Goal` / "the verifier exit contract (75 → `command_refused`, 3 → `command_errored`) and the two environment variables every gate command sees" — M8.1 row of *Submodules* (landed, t1859_1)
- `## Goal` / "the `testmap_check` consistency gate and the `testmap_fresh` procedure gate that precede `tests_pass`" — M8.2 and M8.3 rows of *Submodules* (t1859_2, t1859_3)
- `## Goal` / "the committed completion policy (`completion.mode: full | selected`) as the `POLICY` arm of `ait test`" — M8.4 front row (t1859_4); the decision logic and verb are aitasks_go#t65_1
- `## Goal` / "the self-approving `auto` policy that flips itself behind a cadence of full runs, recording its approval in the engine's own ledger (`costs/policy.yaml`), never in the committed declaration" — M8.5 front row (t1859_5); cadence and writes are aitasks_go#t65_2
- `## Goal` / "Invariant 9 binds: one completion gate" — *Goal* and *Hooks* (Invariants bullet)
- `## Goal` / "carries the module's cut … and the planning protocol" — *Goal* and *Planning and implementation protocol*
- `## Goal` **Acceptance:** / "the union of the module's components' test lists" — *Goal* (acceptance line) and *Acceptance*, first bullet
- `## Submodules` row M8.1 (rows 75/3, `AIT_GATE_TASK_ID`/`AIT_GATE_RUN_ID`/`AIT_GATE_RESULT_FILE`, `--task-id`, docblock, `tests/test_gate_verifiers.sh`) — M8.1 row (landed, t1859_1)
- `## Submodules` row M8.2 `testmap_check` gate (verifier, exit mapping, `--strict`, `bootstrap_until`, `SEEDED:`/`ADOPTED:`, `UNMAPPED_SOURCE:`, `UNSTAMPED` handoff, reference entry no `unlocks`, allowlist, drift test) — M8.2 row (t1859_2)
- `## Submodules` row M8.3 `testmap_fresh` procedure gate (skill, stale workflow, autonomous lane rules, registry entry, five allowlist entries, goldens) — M8.3 row (t1859_3)
- `## Submodules` row / "M8.3 seeds step" (`onboard review --ids`, attended pre-fill/confirm/override/trust-batch, autonomous `--agent-verdicts`) — M8.3 seeds step row (t1859_6)
- `## Submodules` row M8.4 (`completion:` block, `POLICY` arm full/selected, `POLICY_DEMOTED`, `fallback_command`, `result=`, readiness `POLICY:`, `--policy selected` data, verb `policy decide`; owns arm, `policy` package, test cases) — M8.4 front row (t1859_4)
- `## Submodules` row M8.5 (`cadence.go`, `auto` arm, `costs/policy.yaml` writes, `POLICY_WRITE:`, commit, `POLICY_FLIPPED:`, triggers, `POLICY:auto|…`, `cadence_declared`, `CADENCE:`, `approved_by|engine`, window-score trigger, brief fields, `auto` matrix) — M8.5 front row (t1859_5)
- `## Submodules` / "depends on" / "wave" columns — *Submodules* depends and wave columns, with the engine and cross-repo providers named
- `## Cross-module seams` **Provides** / "verifier exit contract and the two environment variables — M8.1 → M5.1, M8.4, M9.1, M9.2" — *Cross-module seams* → Provides
- **Provides** / "consistency gate placed before `tests_pass` (by list position) — M8.2" — *Cross-module seams* → Provides
- **Provides** / "before-commit freshness step and the in-gate reading site — M8.3 → M9.5, M10.x" — *Cross-module seams* → Provides
- **Provides** / "One gate whose meaning is a committed policy; the `completion:` block and the `POLICY:` lines — M8.4, M8.5 → M5.2 (brief), M6.1 (`detect --write`), M6.5 (`--policy selected`), M9.1" — *Cross-module seams* → Provides (front and data consumers here; engine `POLICY:` lines are aitasks_go#t65's)
- **Provides** / "self-approving policy behind the scheduled full run — M8.5" — *Cross-module seams* → Provides
- **Consumes** / "registry and adoption tables (M2.1, M2.6); builtins and `fallback_command` path (M3.2); cost rows and `costs/policy.yaml` format (M3.4); `stale` report and evidence join (M4.2, M4.3); `readiness` and window score (M4.4); the brief (M5.2); packets and verdict intake (M7.1, M7.2)" — *Cross-module seams* → Consumes (engine providers through the shim; fake engine in tests)
- **Consumes** / "`ait test` and its `POLICY` hook (M5.1); existing `lib/gate_verifier_lib.sh`, `aitask_run_project_command.sh`, `gates_reference.yaml`, `tests/test_gates_reference_drift.sh`, `lib/gate_ledger.py`" — *Cross-module seams* → Consumes
- **Hooks** / "M8.4 and M8.5 fill the `POLICY` hook that M5.1 leaves in `aitask_test.sh`; their test cases land in M5.1's `tests/test_ait_test_entrypoint.sh`" — *Cross-module seams* → Hooks
- **Hooks** / "M8.3 ships in wave E without its seeds step and gains it in wave G, as two children" — *Cross-module seams* → Hooks (t1859_3, t1859_6)
- **Hooks** / "M8.1's result carrier `AIT_GATE_RESULT_FILE` is written by the bash front (M8.4 / M8.5), never by the engine" — *Cross-module seams* → Hooks
- **Hooks** / "gate chain `testmap_fresh` → `testmap_check` → `tests_pass` set by list position. No M8 gate declares `unlocks` … M6.5's `enable` owns the order … `ENABLE_REFUSED:gate_dag_mode`" — *Cross-module seams* → Hooks (gate chain by list position)
- **Hooks** / "`UNSTAMPED` failure … handed to the automated repair coordinator t1853_7 … (rollout prerequisite)" — *Cross-module seams* → Hooks (`UNSTAMPED` handoff to t1853_7 / aitasks_go#t59_1)
- **Hooks** / "Automation-first: no path requires a person … `auto` … freshness gate's autonomous lane never confirms `STALE`" — *Cross-module seams* → Hooks (automation-first)
- **Hooks** / "`gates_reference.yaml` edits follow the edit protocol (maintainer `cp`, drift test, `lib/gate_ledger.py` parser)" — *Cross-module seams* → Hooks (`gates_reference.yaml` edit protocol)
- **Hooks** / "Invariants 1, 8 and 9 bind: a demotion runs full, a cadence full run is never skipped; a declared gate errors (exit 3) and never skips; `tests_pass` runs `./ait test --gate`" — *Cross-module seams* → Hooks (Invariants 1, 8, 9)
- `## Known inconsistencies` / "Resolved. M8.2 … moved to wave E … cut fixes in `aiplans/p1859_*.md` (Deviations)" — *Known inconsistencies in the proposal — settled* (record only)
- `## Reading list` (Module Map, Components, Workflow Seam, Data Flow, Agent Review Pass, Overview, Assumptions) — *Reading list in the proposal*
- `## Reading list` / "Framework rules: `aidocs/gates/aitask-gate-framework.md`, `aitask-gate-template`, `aitask-gate-docs-updated`" — *Reading list in the proposal*, framework rules bullet
- Protocol §1 bullets (coarse pass one child per row + "Stop here"; keep coarse; cross-module order in task data; parent `depends:` empty; deviations into proposal + notes) — *Planning and implementation protocol* §1 (pass done; engine halves re-decomposed under aitasks_go#t65; cross-repo edges)
- Protocol §2 steps 1–6 + "A child whose plan lacks this step…" — *Planning and implementation protocol* §2
- `## Module → task map` — *Module → task map* (both repositories)
- Inbox t1852 sequencing / goengines layout — *Planning and implementation protocol* §1 (submodule-granular sequencing)
- Inbox t1852 / "Permission touchpoints … the first skill … owes the five-touchpoint checklist" — *Contract notes for the gate children*, permission touchpoints bullet (taken by t1859_3)
- Inbox t1853 / "M2.6 (t1853_6) moved … wire `t1853_6` into the M8.2 child's `depends:`" — *Contract notes for the gate children*, M2.6 bullet (t1853_6 landed; satisfied)
- Inbox t1853 / "Automation-first … `selected`'s human `approved_by` and M8.3's attended confirm steps" — *Cross-module seams* → Hooks (automation-first: `selected` approval optional, attended confirm steps)
- Inbox t1853_7 / "consumes M8.2 and M8.3 … failure-handoff integration" — *Cross-module seams* → Hooks (`UNSTAMPED` handoff bullet: t1853_7 consumes M8.2 and M8.3)
- Inbox t1853_1 `check` exits/severities contract — *Contract notes for the gate children*, `check` contract bullet
- Inbox t1854 / "Dev 13 full-suite p95 … M8.5's cadence compares" → E; "Dev 14 `costs/policy.yaml` … writer logic stays M8.5's" → E; "`fallback_command:` … Reading it when the engine is absent … is the bash front's job" — *Cross-module seams* → Hooks (`fallback_command:` read by the front); Dev 13 / Dev 14 are aitasks_go#t65's
- Inbox t1853_6 / "`check` ALWAYS prints `SEEDED:`/`ADOPTED:` … Info findings never failing" — *Contract notes for the gate children*, `check` contract bullet (`SEEDED:` / `ADOPTED:`, Info findings)
- Inbox aitasks_go#t15 cutover notice — The freeze is over; the engine halves live in aitasks_go#t65 (header above)

## Relocated to aitasks_go

The engine scope below moved to aitasks_go#t65 and is quoted for reference only.

> - aitasks_go#t65 is the aitasks_go coordinator for M8's engine halves only: aitasks_go#t65_1 (`goengines/internal/testmap/feedback/policy/`, verb `policy decide`, readiness `POLICY:` line) and aitasks_go#t65_2 (`cadence.go`, the verb's `auto` arm and both `policy.yaml` write points, `POLICY_WRITE:`, readiness `cadence_declared`/`CADENCE:`/`approved_by|engine`, `score` window trigger, brief `next full in`/`FULL_GATE:` cadence fields).
> - It inherits M8's binding rules for the engine side: Invariants 1/8/9 as they apply to the verb (a demotion runs full; a cadence full run is never skipped); the engine's approval lives only in `costs/policy.yaml`, never in `config.yaml`; the engine never writes `AIT_GATE_RESULT_FILE` and never commits.
> - Acceptance checks:
>   - aitasks_go#t65_1 and aitasks_go#t65_2 acceptance lists green in `ait engine test` / private CI;
>   - `policy` registered as a named extension of M1.2's verb table; exit/version/verb contract unchanged elsewhere;
>   - no engine path writes `config.yaml`, `AIT_GATE_RESULT_FILE` or a git commit.


## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1852** id=2026-09-22T14:31:42Z.6809a9ba803cfccd75559d8b from=t1852 at=2026-09-22T14:31:42Z base=d0836b4f1750fde12e5e30260cd0d34396793a17 base_branch=main dirty=yes host=omg16
>
> | **Sequencing clarification (advisory, from the t1852 coarse pass, 2026-09-22).** The user asked that M1's children be *implemented* before M2 (t1853) is *planned*. Read the "plan all ten parents before implementing any child" paragraph in this task's body as an upper bound on how far planning may run ahead, not a requirement to plan against providers that do not exist. The rule is submodule-granular, never whole-parent (module-level deps form a cycle: M6.5 -> M8.2/M8.4, M8.3 -> M7.1/M7.2, M7.1 -> M6.2): start this parent's coarse pass once the specific provider submodules its wave-earliest children consume have landed in the tree, and implement its children in proposal wave order. A standalone cross-linking chore task (created from t1852's pass, followup_kind risk_mitigation) checks every "depends on" cell against real depends entries once all ten parents are decomposed; it accepts archived children as evidence and never rewrites M10.2-M10.5 (cross-repo).
> | 
> | **Go source layout (proposal fix, commit 07a546087 on main).** The engine source directory is `goengines/`, not `engine/`: one Go module (`github.com/beyondeye/aitasks/goengines`) for every distributable Go executable, `goengines/cmd/ait-testmap/`, shared packages `goengines/internal/{gitx,platform,lineproto}`, and every testmap-specific package under `goengines/internal/testmap/<pkg>`. Wherever the proposal (and this task's owns cells) write `internal/<pkg>`, read `goengines/internal/testmap/<pkg>`. Unchanged: the binary name `ait-testmap`, `$AITASKS_HOME/engine/v<V>/`, the `ait engine` verbs. CI workflow is `goengines-check.yml`; the release job is `goengines`. M1.2 (t1852_2) creates the module root; each later submodule adds only its own package and replaces only its own stub verb.
> | 
> | **Permission touchpoints for `ait testmap` / `aitask_testmap.sh` are the first skill consumer's, not M1's** (t1852 plan, Deviation 2): no skill in M1 invokes the shim, and `aidocs/framework/aitasks_extension_points.md` forbids dead-weight allowlist entries. The first skill of this module that calls `ait testmap` or `./.aitask-scripts/aitask_testmap.sh` owes the five-touchpoint checklist (`.claude/settings.local.json`, `.codex/rules/default.rules`, `seed/claude_settings.local.json`, `seed/codex_rules.default.rules`, `seed/opencode_config.seed.json`) as an explicit deliverable of that child. Hedge: written against main @ 07a546087 with M1 not yet implemented; the shim's final path is M1.4's to confirm.

> **✉ note:t1853** id=2026-10-11T14:44:08Z.198b8cb0da3921c9fe3d07d6 from=t1853 at=2026-10-11T14:44:08Z base=3bc0de8ac7a9c9d1f60173e1257715a744efc451 base_branch=main dirty=yes host=omg16
>
> | Advisory, from the t1853 (M2) coarse pass. Proposal M2 cut fixed in commit 3bc0de8ac on main.
> | 
> | - **M2.6 (t1853_6) moved from wave E to wave B**, so M8.2 (wave D) can depend on it directly; wire `t1853_6` into the M8.2 child's `depends:`.
> | 
> | **Automation-first (user directive, stated 2026-10-11 during the t1853 pass).** Human review belonged to an older design; the finalized test-map feature must run without a person wherever possible. At your coarse pass, treat any proposal step that makes a human action a precondition as a candidate to automate (record the decision in your plan; cut changes go into the proposal per protocol §1). From my reading, M8 candidates are the `selected` policy's human `approved_by` and M8.3's "never confirm STALE autonomously" / attended confirm steps. Not verified against your module's full text.

> **✉ note:t1853_7** id=2026-10-12T05:56:03Z.c7972367fb74c925b06fad07 from=t1853_7 at=2026-10-12T05:56:03Z base=8395bc6c68f1b977f83470466b549547d4b1ec58 base_branch=main dirty=no host=omg16
>
> | Advisory cross-reference: the user requested full automatic test-map repair for adoption of existing codebases. Created [t1853_7](t1853/t1853_7_automate_testmap_repair_for_existing_codebases.md) for the check → repair → recheck loop, including missing annotations and invalid ownership.
> | 
> | The new sibling consumes M8.2 and M8.3 to repair check/freshness failures and rerun the real verifier. A verifier retry count of zero does not provide this coordinator. Base gates remain independent; the new sibling lands the later failure-handoff integration without false gate success.
> | 
> | As of this moment, the consumer is Postponed pending real provider child IDs. Its dependency table names this parent's required modules; resolve and add actual child dependencies during decomposition, preserving current edges. t1863 explicitly audits this supplementary consumer and its hold in addition to the original module rows.

> **✉ note:t1853_1** id=2026-10-12T08:28:22Z.5c7dfe9ea56086c8a885fe65 from=t1853_1 from_verified=yes at=2026-10-12T08:28:22Z base=c07193265578ec723aa5994ca4bf20ed5116222e base_branch=main dirty=yes host=omg16
>
> | For M8.2 (testmap_check verifier): M2.1 shipped `ait-testmap check [--strict] [--json]` in 0d04347ab; the full contract is in the proposal at c07193265 (Enumeration and reconciliation, the severity table). Advisory, as of that tree.
> | 
> | Exits:
> | - 0: pass
> | - 1: a failing finding
> | - 2: TESTMAP_ABSENT:aitestmap/ (no registry)
> | - 3: CONTRACT_MISMATCH / REGISTRY_INVALID / INPUT_UNAVAILABLE / INPUT_ERROR / CHECK_ERROR, on stderr with nothing on stdout
> | - 64: usage
> | 
> | stdout is the findings, then CHECK:<pass|fail>|<findings>|<failing>; --json prints {status, findings[{rule, fields, fail}], failing}.
> | 
> | Severities:
> | - always fail: STALE_PATH, UNANNOTATED_MEMBER, DEAD_MEMBER, OWNS_VIOLATION, DUPLICATE_RULE, and UNSTAMPED (which is emitted only under require_stamp past bootstrap_until)
> | - fail only under --strict past bootstrap_until: UNREGISTERED, UNMAPPED_ARTIFACT, SCAN_DRIFT
> | - info: WAIVER_EXPIRED
> | 
> | An absent bootstrap_until means no bootstrap window. An inspection failure never yields CHECK:pass.
> | 
> | Until M2.2 and M3.1 wire their inputs, check exits 3 with INPUT_UNAVAILABLE. M2.1 met no human-only step that needs reporting.

> **✉ note:t1854** id=2026-10-13T16:21:23Z.5d16051f9f1781f63491d628 from=t1854 at=2026-10-13T16:21:23Z base=6a3a81efc30577c762d42f815f3e95eac95b4e3f base_branch=main dirty=no host=omg16
>
> | Advisory, from the t1854 (M3) coarse pass (proposal at 6a3a81efc). These are tree claims; verify them at your pass.
> | 
> | - **Dev 13: full-suite p95.** M8.5's cadence compares the selection estimate against `selection_ratio_above × full p95`, and `FULL_GATE:` / `--gate-timeout` use the same number. It is now defined in *Cost ledger*: the M3.4 estimate (Σ groups `overhead.p95` + Σ **top-level** ids p95), applied to the newest `full-` run on the host class.
> |   - Accounting is disjoint: a suite parent's inclusive time counts once and its child rows never add to it. A 100 s suite with 40 s + 60 s children in a 105 s invocation counts 105 s, not 205 s.
> | - **Dev 14.** The `costs/policy.yaml` sketch in *The registry directory* now carries `contract`, matching *Where state lives*. M3.4 (t1854_4) owns the format and its read/write helpers, including the `CONTRACT_MISMATCH` refusal. The writer logic stays M8.5's.
> | - `fallback_command:` is defined by M3.1 (t1854_1) on suite runners only. Reading it when the engine is absent (`completion.engine_absent: fallback_command`) is the bash front's job, with no engine to parse `runners.yaml`. Plan accordingly in M8.4.

> **✉ note:t1853_6** id=2026-10-19T09:18:14Z.93071cbd91876017944568cc from=t1853_6 from_verified=yes at=2026-10-19T09:18:14Z base=093d98a197a65931bdd6f104d4a919f965dfc0ee base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1853_6 (M2.6 adoption tables). It describes the tree as of aaeb10b0f, so verify it in your reality check. M8's children are not decomposed yet, so this note goes to the parent.
> | 
> | For the `testmap_check` verifier (M8.2):
> | 
> | - `check` ALWAYS prints the two summary lines, even with no adoption files. They come after every finding and immediately before `CHECK:`:
> |   - `SEEDED:<n>`
> |   - `ADOPTED:<n>|human <h>|agent <a>|auto <m>`
> | - They are NOT counted in `CHECK:<status>|<findings>|<failing>` and never fail.
> | - `--json` carries them in a separate `summary` array.
> | - The M2.6 reports (`SEED_SHADOWED`, `SEED_REJECTED`, `ADOPTED_ORPHAN`, `REVIEW_UNRECORDED`) are Info findings: counted in `<findings>`, never failing, even under `--strict` past `bootstrap_until`.

> **👁 note:read** id=2026-10-19T09:41:08Z.8411bc4ccaaacbce7b09fd0d by=t1859 at=2026-10-19T09:41:08Z mode=explicit ids=2026-09-22T14:31:42Z.6809a9ba803cfccd75559d8b,2026-10-11T14:44:08Z.198b8cb0da3921c9fe3d07d6,2026-10-12T05:56:03Z.c7972367fb74c925b06fad07,2026-10-12T08:28:22Z.5c7dfe9ea56086c8a885fe65,2026-10-13T16:21:23Z.5d16051f9f1781f63491d628,2026-10-19T09:18:14Z.93071cbd91876017944568cc

> **✉ note:t15** id=2026-10-25T08:53:59Z.7c1dabadd2e2830cccce2fef from=aitasks_go#t15 at=2026-10-25T08:53:59Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
>
> | Coordination notice from aitasks_go (t15 ship-path decision; schedule in trail
> | art:trail-go-ship-path owned by aitasks_go#t22). Advisory context, not an
> | instruction. It does not change this task's scope.
> | 
> | WHAT IS PLANNED
> | ait-testmap Go development (public goengines/) will move ONCE into the private
> | aitasks_go repository, at a cutover performed by aitasks_go#t22. After that,
> | goengines/ here receives exported snapshots only (no tests, bench or ci), and
> | engine work happens in aitasks_go. As of 2026-10-25 the cutover has no date.
> | Its prerequisites are aitasks_go t20 and t21 and aitasks t2138.
> | 
> | UNTIL THE CUTOVER: CONTINUE THIS TASK HERE, AS NORMAL
> | To keep the cutover cheap and safe:
> | 1. Land goengines/ changes on main promptly. Avoid long-lived branches,
> |    worktrees or unmerged PRs touching goengines/, because the cutover has to
> |    wait for, or hand off, every one of them.
> | 2. Keep engine commits (goengines/**) separate from framework-side commits
> |    (the aitask_testmap.sh shim, installer/setup, skills, docs, aitestmap/).
> |    Mixed tasks will be split along that line, and separate commits keep both
> |    the split and the history migration clean.
> | 3. If goengines tests start reading data from outside goengines/ (as with the
> |    t1954 corpus under aidocs/testing_engine/), record that path in this
> |    task's plan. The migration must copy it into the private module.
> | 4. Add no new Go binary or non-testmap package to goengines/. ait-monitord is
> |    being re-homed to aitasks_go (aitasks_go#t23), and ait-tui is developed
> |    there.
> | 5. Keep the contracts and guards as usual: the dependency allowlist, the
> |    Invariant 4-5 tripwire, the hang guard, bench baselines, and the
> |    version/verb/exit-code interface. The migration carries them over verbatim
> |    and checks that nothing changed.
> | 
> | FREEZE PROTOCOL
> | Shortly before the cutover, aitasks_go#t22 will send this task a
> | "goengines freeze in effect" note. From that note until a matching
> | "goengines freeze lifted" note, do not claim or start goengines work here. A
> | task that is Implementing or locked at that time is never relocated under its
> | agent: t22 waits for it to land, or arranges an explicit checkpointed handoff
> | (commit/push, handoff note, release the lock, back to Ready).
> | 
> | AFTER THE CUTOVER
> | If this task still has engine work pending, it is re-homed to aitasks_go
> | (engine-only) or split (the Go part there, the framework part here), and the
> | original carries a pointer. Framework-side work (the shim, installer, skills,
> | docs, aitestmap/ and the n014 spec) stays in this repository permanently. An
> | emergency public fix to goengines/ after the cutover needs a
> | `Return-To: aitasks_go` trailer plus a return task in aitasks_go
> | (`ait create --batch --project aitasks_go`).

> **✉ note:t22_3** id=2026-10-29T22:22:52Z.9594683c3e097d8c720116f7 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:22:51Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.
