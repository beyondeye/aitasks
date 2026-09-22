---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [testing, testmap, bash_scripts]
anchor: 1852
created_at: 2026-09-22 09:19
updated_at: 2026-09-22 09:19
---

## Goal

Part of the **testing engine / test map** feature — ten parent tasks, one per
module of the proposal. This is **M5 — Run surface**: how an agent or a
person runs tests, in any repository state.

This module delivers `ait test` — a bash front in three modes (interactive,
completion, advisory) over the engine `test` composite, which still answers
correctly when no registry or no engine exists (`TESTMAP_ABSENT` delegation to
the project's `test_command`, `ENGINE_MISSING`); the computed project brief
(`ait test --howto`); and the fourteen-line `## Running Tests` section every
agent reads at session start.

This task carries the module's cut — submodules, owned files, the interfaces
it provides and consumes, the seams later modules land into it — and the
planning protocol. It does **not** restate the specification.

**Proposal (authoritative for every detail):**
`aidocs/testing_engine/n014_explorer_006_proposal.md` — start at the *Module
Map* entry `#### M5 — Run surface`, then the *Components* subsections tagged
`(M5.x)` (listed under *Reading list* below), then the narrative sections
those components name. *Architecture*, *Design decisions* and the *Invariants
every module honours* apply to every module.

**Acceptance:** the union of the module's components' test lists (*Module Map —
How to read it*).

## Submodules (one child task each — settled at the coarse planning pass)

| submodule | scope | depends on | wave |
|---|---|---|---|
| **M5.1** `ait test` bash front | the modes, task resolution (incl. the new `aitask_lock.sh --list-mine` verb), the intake, `TESTMAP_ABSENT` delegation to `aitask_run_project_command.sh test_command`, `ENGINE_MISSING`, the advisory verdict and log, the exit contract, run-id prefixes, `UNANNOTATED_TEST` / `HINT`, the `POLICY` hook (M8.4 / M8.5 fill it; until then completion runs `--all`), the `ait` dispatcher arm, the five permission touchpoints. Owns `.aitask-scripts/aitask_test.sh`, the `ait` `test)` arm, `--list-mine` in `aitask_lock.sh`, `tests/test_ait_test_entrypoint.sh` with the fake engine, the `tests/test_touchpoint_count_contract.sh` re-pin | M1.4, M4.1, M4.5 | D |
| **M5.2** Brief | `brief [--md]`, `ait test --howto [--md]`, `ait testmap brief`; the `TESTMAP:` / `RUNNER:` / `FULL_GATE:` / `GATE:` / `VERBS:` / `AXES:` / `RESOURCE:` / `NEW_TEST:` / `DOCS:` / `NOTES:` lines. Owns `internal/brief`, verb `brief` | M2.1, M2.4, M3.4, M5.1 | D |
| **M5.3** Agent instructions seed | the fourteen-line `## Running Tests` section; the `tests/test_agent_instructions.sh` case. Owns that section of `seed/aitasks_agent_instructions.seed.md` and the test case | M5.1 | D |

## Cross-module seams

**Provides** (defined here, consumed elsewhere):

- `ait test` modes, the exit table, the advisory `VERDICT:` / `REASON:` —
  M5.1 → M8.4 (`tests_pass` through `test_command`), M9.1, M9.2, every agent.
- The computed project brief — M5.2 → every agent; M6.1, M7.3 and M8.5 add
  lines to it.
- The sentence every agent reads at session start — M5.3.

**Consumes:** the shim `ait testmap` (M1.4); the ranked list and the `test`
composite (M4.1, M4.5); the registry, axes and costs the brief reads (M2.1,
M2.4, M3.4); the verifier exit contract and the two environment variables
(M8.1) for the completion mode; `aitask_run_project_command.sh` and
`aitask_change_surface.sh` (exist today).

**Hooks and extensions** (a file has one owner; a later submodule lands its
edit as the owner's named extension):

- The `POLICY` hook in `aitask_test.sh` is left in place by M5.1 and filled by
  **M8.4** (`full` / `selected`) and **M8.5** (`auto`); until then completion
  runs `--all`. This interim state is deliberate
  (`tradeoff_module_boundaries_cut_across_packages`) — do not pre-empt it.
- `tests/test_ait_test_entrypoint.sh` is M5.1's; M8.4 and M8.5 add their cases
  (incl. the `auto` matrix) to it.
- The brief's additive lines land later: `ONBOARD_NEXT:` (**M6.1**),
  `AGENT_REVIEW:` (**M7.3**), `KIND_PROPOSALS:` / `REVIEW_HUMAN:`, the policy
  and cadence fields and `next full in` (**M8.5**).
- The workflow-seam data rows that name `ait test` are owned by M5.1
  (*Workflow seam — the data edits*); the procedure edits are **M9.1**'s.
- Invariant 8: every seam degrades to a printed skip where the engine or the
  registry is absent in advisory mode; a declared gate errors (exit 3) and
  never skips.

## Reading list in the proposal

- *Module Map* — `#### M5`, *How to read it*, *Cross-module interfaces*,
  *Suggested implementation order* (wave D).
- *Components* — *Test entrypoint `ait test` (M5.1)*, *Agent brief (M5.2)*,
  *Agent instructions (M5.3)*.
- *The Run Surface* — whole section (*Forms*, *Resolution, in order*, *Output
  and exit contract*, *The two environment variables*, *`ait test --howto`*,
  *The generic instructions section*).
- *Running Tests*.
- *Data Flow* — *A task in steady state*, *A completion run under policy*.
- *Assumptions* / *Tradeoffs* — *Run surface and workflow (M5, M8, M9)*;
  *Open questions*.
- Framework rules that apply: `aidocs/framework/shell_conventions.md`; the
  permission-touchpoint contract pinned by
  `tests/test_touchpoint_count_contract.sh`.

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
