---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [testing, testmap, go_engine, skills]
anchor: 1852
created_at: 2026-09-22 09:19
updated_at: 2026-09-22 09:19
---

## Goal

Part of the **testing engine / test map** feature — ten parent tasks, one per
module of the proposal. This is **M6 — Onboarding**: bringing an existing
test tree onto the map, in levels, as tasks.

This module delivers the `onboard.yaml` phase ledger and the engine verbs that
record into it (`detect` / `inventory` / `status` / `finish`, `seed` with the
origin table and noisy-OR, `adopt` / `reject` with the autonomous floor
enforced, `classify` / `scaffold` for levels 2 and 3), and the resumable
`aitask-testmap-onboard` skill that runs one aitask per level, reaches level 1
in attended and headless profiles alike, and writes the `enable` phase's
project configuration.

This task carries the module's cut — submodules, owned files, the interfaces
it provides and consumes, the seams later modules land into it — and the
planning protocol. It does **not** restate the specification.

**Proposal (authoritative for every detail):**
`aidocs/testing_engine/n014_explorer_006_proposal.md` — start at the *Module
Map* entry `#### M6 — Onboarding`, then the *Components* subsections tagged
`(M6.x)` (listed under *Reading list* below), then the narrative sections
those components name. *Architecture*, *Design decisions* and the *Invariants
every module honours* apply to every module.

**Acceptance:** the union of the module's components' test lists (*Module Map —
How to read it*).

## Submodules (one child task each — settled at the coarse planning pass)

| submodule | scope | depends on | wave |
|---|---|---|---|
| **M6.1** Phase ledger, detect, inventory, status, finish | the `onboard.yaml` schema and phase rows, `onboard detect [--write] [--force]` with the closed detector list and `DETECT_DIFF:`, `inventory`, `status`, `finish [--auto]`, the `AIT_PROFILE_HEADLESS=1` refusals, `report_testmap_state()`'s `bootstrapping\|<next>` state, `ONBOARD_NEXT:` on the brief. Owns `internal/onboard/{ledger,detect,inventory,status,finish}.go` and the extension of `report_testmap_state()` | M1.5, M2.1, M2.5, M3.1, M5.2 | E |
| **M6.2** Seeder and origin table | `onboard seed`, the origins `static:*` / `convention` / `cochange` / `plan` / `prose` / `coverage`, the class column, noisy-OR, the `helper_roots` / `helper_fanin` separation, the `SEED_*` lines, `--apply`, `--json --out`. Owns `internal/seed`, one fixture repo per origin | M2.3, M2.6, M3.2, M6.1 | E |
| **M6.3** Adoption verbs | `onboard adopt --class [--accept-min] [--scope] [--dry-run]`, `--class --auto` with the autonomous floor enforced (`ADOPT_REFUSED:not-autonomous`), per-row `<test> [<source>]` / `--area --batch` / `--files-from -`, `onboard reject`, `ADOPT_REFUSED:dirty-foreign`, the `ADOPT_SKIP` cases, `WROTE:`, `ADOPT_SUMMARY:`, provenance rows, the reviewed-stamp path deleting provenance rows. Owns `internal/onboard/{adopt,reject}.go` | M2.2, M2.6, M6.2 | E |
| **M6.4** Classify and scaffold | `onboard classify [--apply\|--propose]` with `kind_proposals[]`, the level-2 writes (kind / area / scope / reads / batch lines, `needs:` bindings, `resources.yaml` entries), `onboard scaffold --axes \| --runner <builtin> --as <name> \| --members` with `SCAFFOLD_TODO`. Owns `internal/onboard/{classify,scaffold}.go` | M2.4, M2.5, M3.4, M6.1 | G |
| **M6.5** Onboarding skill | the `aitask-testmap-onboard` stub + `SKILL.md.j2` + one procedure file per phase; the survey and level proposal; task creation and claim; the `enable` phase's edits to `project_config.yaml`, profiles, `gates.yaml`, `docs:` / `notes:`, the hand-maintained `CLAUDE.md`; the `full_run` phase (`costs --gate-timeout`, the next level's task with `depends:`); the `--policy selected` re-entry; `--no-task`; refresh mode; the headless flow; goldens; `tests/test_testmap_onboard_ledger.sh`. Owns `.claude/skills/aitask-testmap-onboard/**`, `tests/golden/skills/aitask-testmap-onboard/`, the ledger test | M4.4, M5.1, M6.1, M6.2, M6.3, M8.2, M8.4 | F |

## Cross-module seams

**Provides** (defined here, consumed elsewhere):

- `onboard.yaml` phases and `ONBOARD_NEXT:` — M6.1 → M1.5
  (`report_testmap_state`), M5.2, M6.5, M7.2 (`reviews[]`), M7.3
  (`calibration[]`), M6.4 (`kind_proposals[]`).
- `registry/seeded.yaml` rows and the origin table with its class column —
  M6.2 (rows; the schema is M2.6's) → M4.1 (`edge(seeded:…)`), M4.4
  (`--propose`), M6.3, M7.1, M7.2.
- The adoption transitions and the `ADOPT_*` lines; every non-agent adoption
  path; the rewriter calls the verdict intake reuses — M6.3 → M7.2, M6.5, M8.3.
- Levels 2 and 3 — M6.4.
- Levels 0 and 1 attended; levels 0 and 1 headless once M7.2 and M7.5 exist —
  M6.5 → M9.5 (ports), M10.x (rollout).

**Consumes:** the installed engine and `report_testmap_state()` (M1.5); the
registry, scoped rows, axes and adoption tables (M2.1, M2.4, M2.5, M2.6); the
rewriter (M2.2); scanner facts (M2.3); the runner contract, builtins,
`resources.yaml` and costs (M3.1, M3.2, M3.3, M3.4); `readiness` (M4.4); `ait
test` and the brief (M5.1, M5.2); the `testmap_check` gate and the completion
policy (M8.2, M8.4); the verdict intake and the review skill for the headless
level 1 (M7.2, M7.5); existing framework surfaces `aitask_create.sh`,
`aitask_pick_own.sh`, `ait attach`, `aitask_task_commit.sh`, the profiles.

**Hooks and extensions** (a file has one owner; a later submodule lands its
edit as the owner's named extension):

- M6.1 extends `report_testmap_state()` (owned by **M1.5**) with
  `bootstrapping\|<next>` and adds `ONBOARD_NEXT:` to the brief (**M5.2**).
- The `review.md` sub-phase under this skill's tree is owned by **M7.5**; M6.5
  ships without it, and headless level 1 lands when M7.2 and M7.5 exist.
- `internal/onboard` spans M6.x and M7.x by verb; `review.go` is M7's.
- `seeded.yaml`'s schema and write routing are **M2.6**'s; M6.2 writes its
  rows, `attribute --propose` (**M4.4**) also writes rows.
- The level task the skill creates uses `--type chore --labels
  testing,testmap`; the rollout tasks (**M10**) are these level tasks in each
  target repository.
- Invariants 3 and 10 bind: an autonomous path may seed everything, may adopt
  a class only when every member carries a rule, a measurement or a reading
  and clears `agent_review.accept_min`, and may never adopt a heuristic alone,
  reject a seed, change a kind or declare an axis; headless runs record kind
  proposals and never enter level 3. Every skill edit follows
  `aidocs/framework/skill_authoring_conventions.md` and
  `stub-skill-pattern.md` (Claude Code first; goldens in the same commit).

## Reading list in the proposal

- *Module Map* — `#### M6`, *How to read it*, *Cross-module interfaces*,
  *Suggested implementation order* (waves E, F, G).
- *Components* — *Onboarding verbs (M6.1 / M6.3 / M6.4)*, *Seeder (M6.2)*,
  *Adoption ledger: seeded → adopted → reviewed (M6.3 transitions)*,
  *Onboarding skill `aitask-testmap-onboard` (M6.5)*, *Scoped-row registry and
  areas (the onboarding signals consumed by M6.4)*, *Engine install, upgrade
  and state report (the `bootstrapping` state)*.
- *The Adoption Model* — whole section.
- *Onboarding: Levels × Phases* — whole section, especially *Invocation and
  task shape* and *Detection, per target repository*.
- *Data Flow* — *Onboarding level 0*, *Level 1: seeds → verdicts → stamped
  edges*.
- *Overview* — *How the loop closes without a person* (mechanism 2, the
  autonomous floor).
- *Assumptions* — *Seeding and adoption (M6, M7)*, *Onboarding (M6)*;
  *Tradeoffs* — *Seeding, adoption and onboarding (M6, M7)*; *Open questions*.

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
