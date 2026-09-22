---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [testing, testmap, go_engine]
anchor: 1852
created_at: 2026-09-22 09:19
updated_at: 2026-09-22 09:19
---

## Goal

Part of the **testing engine / test map** feature — ten parent tasks, one per
module of the proposal. This is **M3 — Runners, scheduling and cost**:
everything that executes a test and records what it cost.

This module delivers the runner contract every builtin and project script
implements (`describe` / `list` / `run --manifest`, `results.jsonl`, the exit
contract `0/1/2/75/64`), the reference runners for every target repository
(`bash-file`, `pytest`, `go-test`, `gradle-class`, `suite`, `device`,
`engine-test`), the scheduler over declared host resources with `flock(2)`
slot files and exit-75 deferral, and the cost ledger keyed by `(id, host
class)` that anchors `last_pass` evidence and stores predictions and the
policy file.

This task carries the module's cut — submodules, owned files, the interfaces
it provides and consumes, the seams later modules land into it — and the
planning protocol. It does **not** restate the specification.

**Proposal (authoritative for every detail):**
`aidocs/testing_engine/n014_explorer_006_proposal.md` — start at the *Module
Map* entry `#### M3 — Runners, scheduling and cost`, then the *Components*
subsections tagged `(M3.x)` (listed under *Reading list* below), then the
narrative sections those components name. *Architecture*, *Design decisions*
and the *Invariants every module honours* apply to every module.

**Acceptance:** the union of the module's components' test lists (*Module Map —
How to read it*).

## Submodules (one child task each — settled at the coarse planning pass)

| submodule | scope | depends on | wave |
|---|---|---|---|
| **M3.1** Runner contract and repository | `describe` / `list` / `run --manifest`, `runners.yaml` bindings, the `builtin:` scheme, `command:` / `cwd:` overrides, shadow-by-name, batching keys, per-unit timeouts, `results.jsonl` / `runner.json`, reconciliation as mechanism failures, the exit contract `0/1/2/75/64`, `subsumed_by:`, `fallback_command:`, `full: true` + `children:`. Owns `internal/runner` (contract, repository, the `run` verb) | M1.2, M2.1 | B |
| **M3.2** Reference runners | `bash-file` (+ `list --invocations`), `pytest` (junitxml, `testmap:batch no`), `go-test`, `gradle-class`, `suite`, `device`, `engine-test`; the `full` suite wrapper's `children:` post-processors (pytest junitxml, bash-file per-file exit, `go test -json`). Owns `internal/runner/builtin/*`, `ait-testmap runner <name>`, the serial carve-out pin in `tests/test_serial_carveout_doc_drift.sh` | M3.1 | B |
| **M3.3** Scheduler and resources | resource kinds and scopes, `resources.yaml`, `flock(2)` slot files, admission with 75 deferral and backoff, the allocator with signal-safe release, `errgroup` execution, batching per `group_by`, `broad_after_unit` waves, admission-holding invocations last, `concurrency: serial\|parallel`, the schedule report and its check half. Owns `internal/sched`, verb `schedule` | M3.1 | C |
| **M3.4** Cost ledger | Welford / P² per `(id, host class)`, `.aitask-testmap/ledger.jsonl`, `costs --update`, `last_pass`, flake rate, the per-group estimate, `costs/predictions.yaml` (store only), `costs --gate-timeout`, the run-id prefixes, the `costs/policy.yaml` file format (read/write helpers only). Owns `internal/cost`, verb `costs` | M3.1 | C |

## Cross-module seams

**Provides** (defined here, consumed elsewhere):

- The runner contract and `results.jsonl` — M3.1 → M3.2 (builtins), M3.3
  (execution), M3.4 (ledger rows), M6.1 (`detect` writes `runners.yaml`).
- Runners for every target repository without a project script — M3.2 → M4.5,
  M6.2, M8.4 (`fallback_command`), M10.4 (`gradle-class`, `device`), M10.5.
- `resources.yaml` and the wave plan `run` executes; exit 75 semantics — M3.3 →
  M4.5, M6.1 (`RESOURCE_HINT` → entries), M6.4 (`needs:` bindings).
- Cost rows, `last_pass`, the per-group estimate, `predictions.yaml`, the
  `costs/policy.yaml` format — M3.4 → M4.1 (ranking, budget), M4.3 (anchors),
  M4.4 (score, readiness), M6.5 (`--gate-timeout`), M8.5 (cadence state).

**Consumes:** M1.2 (the binary, the harnesses); the loaded registry (M2.1).

**Hooks and extensions** (a file has one owner; a later submodule lands its
edit as the owner's named extension):

- `costs/predictions.yaml` is a store here; **M4.4**'s `score` writes it.
- `costs/policy.yaml`: the format and its read/write helpers are M3.4's; the
  writer logic (`POLICY_WRITE:`, `approved_by: engine:readiness@<run>`) is
  **M8.5**'s.
- `component_broad_test_scopes` is split: the registry / staleness half is
  **M2.5**, the scheduling half is M3.3.
- The `pytest` runner's `testmap:batch no` is what M10.1 uses to pin the
  aitasks serial carve-out; the pin in `tests/test_serial_carveout_doc_drift.sh`
  is M3.2's.
- Invariant 1 (the loop can only fail toward running more) and invariant 4
  (the engine never launches a code agent) bind the runner and the scheduler.

## Reading list in the proposal

- *Module Map* — `#### M3`, *How to read it*, *Cross-module interfaces*,
  *Suggested implementation order* (waves B, C).
- *Components* — *Runner contract and repository (M3.1)*, *Reference runners
  (M3.2)*, *Scheduler and resources (M3.3)*, *Broad-test scheduling and
  staleness policy (M3.3 scheduling half)*, *Cost ledger (M3.4)*.
- *Architecture* — *Process map*, *Where state lives*, *Line-protocol index*.
- *Running Tests*; *The Run Surface — Output and exit contract*.
- *Assumptions* — *Variants, broad tests and runners (M2, M3)*; *Tradeoffs* —
  *Map and registry structure (M2, M3)*; *Open questions*.
- Framework rules that apply: `aidocs/framework/tmux_gateway.md` if any
  runner or resource touches tmux; the serial carve-out contract in
  `CLAUDE.md` (Testing).

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
| M1 — Engine foundation and distribution | @@M1@@ |
| M2 — Registry and map model | @@M2@@ |
| M3 — Runners, scheduling and cost | @@M3@@ |
| M4 — Selection, freshness and feedback | @@M4@@ |
| M5 — Run surface | @@M5@@ |
| M6 — Onboarding | @@M6@@ |
| M7 — Agent review and author annotation | @@M7@@ |
| M8 — Completion policy and gates | @@M8@@ |
| M9 — Workflow integration, skills and documentation | @@M9@@ |
| M10 — Rollout to the target repositories | @@M10@@ |

All ten share the topic anchor of the M1 task, so the board's By-Topic view
shows the whole feature as one lane.
