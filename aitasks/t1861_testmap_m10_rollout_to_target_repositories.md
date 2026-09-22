---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [testing, testmap]
anchor: 1852
created_at: 2026-09-22 09:19
updated_at: 2026-09-22 09:19
---

## Goal

Part of the **testing engine / test map** feature — ten parent tasks, one per
module of the proposal. This is **M10 — Rollout to the target repositories**:
the feature applied.

The five target repositories — `aitasks`, `aitasks_go`, `thinking_backend`,
`aitasks_mobile`, `thinking_app` — are each brought onto the map by the
onboarding skill's own level tasks (levels 0–1; levels 0–3 for
`thinking_app`), plus the repository-specific decisions the proposal's
detection table records. The rollout adds no framework code: a target-specific
need discovered here becomes a note or a follow-up on the owning framework
parent, never a patch in the target.

**Where the tasks live.** Per the proposal, the rollout tasks live in each
target repository and are created through `ait create --batch --project
<name>`; every target is registered in the per-user projects registry
(`ait projects list`). This parent is the local coordinator: **M10.1 is a
local child** (this repository); **M10.2 – M10.5 are cross-repo tasks** created
in their own repositories at the coarse planning pass, following
`.claude/skills/task-workflow/planning-cross-repo.md` and
`cross-repo-child-assignment.md`, and referenced from here with the
`<project>#<id>` notation (`aidocs/framework/cross_repo_references.md`). Every
rollout task depends on the framework release that carries M1–M9 reaching the
target (its `ait upgrade`), not on this repository's tasks directly — the exact
`xdeps:` / `xdeprepo:` shape is settled at the coarse pass.

This task carries the module's cut and the planning protocol. It does **not**
restate the specification.

**Proposal (authoritative for every detail):**
`aidocs/testing_engine/n014_explorer_006_proposal.md` — start at the *Module
Map* entry `#### M10 — Rollout to the target repositories`, then *Onboarding:
Levels × Phases* (especially *Invocation and task shape* and *Detection, per
target repository*). *Architecture*, *Design decisions* and the *Invariants
every module honours* apply to every module.

**Acceptance:** each target's `onboard.yaml` ledger finished at the named
level, its completion gate running `./ait test --gate`, and the decisions in
the detection table recorded in its `aitestmap/config.yaml`.

## Submodules (one child task each — settled at the coarse planning pass)

| submodule | scope | depends on | wave |
|---|---|---|---|
| **M10.1** aitasks levels 0–1 (local) | the hand-maintained `CLAUDE.md` paragraph; the pytest serial carve-out pinned as `testmap:batch no`; the `repo-git-index` mutex; the review loop over ~718 pairs; level 2 proposals for the ~40 tmux / live-TUI / real-install tests | M6.5, M7.5, M8.3, M9.1 | I |
| **M10.2** aitasks_go levels 0–1 (cross-repo) | `static:package` by rule, no reading; `go test -coverprofile` per unit as `coverage`; the parity suite as an e2e suite row with a `tmux` resource | M6.5, M8.3, M9.1 | I |
| **M10.3** thinking_backend levels 0–1 (cross-repo) | the `verify_build` question (keep by default), `test_command: ./ait test` over 40 units, `golden/` as `reads` | M6.5, M7.5, M8.3, M9.1 | I |
| **M10.4** aitasks_mobile levels 0–1 (cross-repo) | one `gradle-class` runner per source set, `device` for `androidDeviceTest` with the emulator allocator, `device_policy: filter_by_resource` | M3.2 (`gradle-class`, `device`), M6.5, M7.5, M8.3, M9.1 | I |
| **M10.5** thinking_app levels 0–3 (cross-repo) | `verify-active` as the `full: true` suite runner with `subsumed_by`, the `heavy-run` admission resource, 139 `static:import` files through review, JaCoCo when enabled, then `onboard scaffold --runner gradle-class --as screen-matrix`, `axes.yaml`, `testmap:unit` blocks in `ScreenFixtures.kt` | M2.4, M3.2, M6.4, M6.5, M7.5, M8.3, M9.1 | I |

## Cross-module seams

**Provides:** each target repository onboarded through its own level tasks;
the first real calibration data (M7.3) and cadence runs (M8.5); the
per-target evidence the proposal's *Assumptions* on seeding, onboarding and
runners are falsified or confirmed against.

**Consumes:** the onboarding skill (M6.5), the review skill (M7.5), the
freshness gate (M8.3), the workflow seam (M9.1); the `gradle-class` and
`device` runners (M3.2); axes and `scaffold` for level 3 (M2.4, M6.4); the
framework release carrying M1–M9, installed in each target.

**Hooks and notes:**

- Each level task is what M6.5's skill creates (`--type chore --labels
  testing,testmap`, the seed dump attached, `onboard.yaml` carrying the task
  id); the M10.x child is the *decision record* the skill consumes — the
  detection table row and the repository-specific choices — and the parent of
  the level tasks it spawns in that repository.
- Repository-specific hazards the proposal already names: the aitasks pytest
  serial carve-out and the `.git/index.lock` mutex (M10.1), the emulator
  allocator (M10.4), `verify-active` subsuming the unit runs and the
  `heavy-run` resource (M10.5).
- Cross-repo references use the `<project>#<id>` notation and the registry;
  never a sibling-directory path (`CLAUDE.md`, *Cross-repo coordination*).

## Reading list in the proposal

- *Module Map* — `#### M10`, *Suggested implementation order* (wave I).
- *Onboarding: Levels × Phases* — whole section; *Detection, per target
  repository* is the table each child transcribes.
- *Overview* — *What the feature is* (the five targets).
- *The Adoption Model* — *The autonomous floor* (which classes adopt headless
  in each target).
- *Assumptions* — *Seeding and adoption (M6, M7)*, *Onboarding (M6)*,
  *Variants, broad tests and runners (M2, M3)*.
- Framework rules that apply: `aidocs/framework/cross_repo_references.md`,
  `.claude/skills/task-workflow/planning-cross-repo.md`,
  `cross-repo-child-assignment.md`.

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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1852** id=2026-09-22T14:31:52Z.358525cb335defe87770962e from=t1852 at=2026-09-22T14:31:52Z base=d0836b4f1750fde12e5e30260cd0d34396793a17 base_branch=main dirty=yes host=omg16
>
> | **Sequencing clarification (advisory, from the t1852 coarse pass, 2026-09-22).** The user asked that M1's children be *implemented* before M2 (t1853) is *planned*. Read the "plan all ten parents before implementing any child" paragraph in this task's body as an upper bound on how far planning may run ahead, not a requirement to plan against providers that do not exist. The rule is submodule-granular, never whole-parent (module-level deps form a cycle: M6.5 -> M8.2/M8.4, M8.3 -> M7.1/M7.2, M7.1 -> M6.2): start this parent's coarse pass once the specific provider submodules its wave-earliest children consume have landed in the tree, and implement its children in proposal wave order. A standalone cross-linking chore task (created from t1852's pass, followup_kind risk_mitigation) checks every "depends on" cell against real depends entries once all ten parents are decomposed; it accepts archived children as evidence and never rewrites M10.2-M10.5 (cross-repo).
