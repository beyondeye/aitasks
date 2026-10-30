---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [testing, testmap, go_engine, skills]
anchor: 1852
created_at: 2026-09-22 09:19
updated_at: 2026-10-30 12:10
---

Split (aitasks_go#t22 cutover): the engine half of this task is aitasks_go#t63
in beyondeye/aitasks_go. This body is the framework half.

## Goal

Part of the **testing engine / test map** feature — ten parent tasks, one per
module of the proposal. This is **M6 — Onboarding**: bringing an existing
test tree onto the map, in levels, as tasks.

The module delivers the `onboard.yaml` phase ledger and the engine verbs that
record into it (`detect` / `inventory` / `status` / `finish`, `seed`, `adopt` /
`reject`, `classify` / `scaffold`) — now aitasks_go#t63 in aitasks_go — and the
resumable `aitask-testmap-onboard` skill that runs one aitask per level,
reaches level 1 in attended and headless profiles alike, and writes the
`enable` phase's project configuration. This task stays the M6 parent for the
framework part:

- **M6.1, framework part:** the `report_testmap_state()`
  `TESTMAP:bootstrapping|<next>` branch in `.aitask-scripts/aitask_setup.sh`,
  plus its `tests/test_install_engine_binary.sh` case.
- **M6.5 in full:** the onboarding skill.
- The five permission touchpoints, the onboarding docs stating the
  four-language policy, the proposal edits and notes, and the wiring of
  t2131_9, t2131_11 and t1853_7.

It carries the module's cut and the planning protocol; it does **not** restate
the specification.

**Proposal (authoritative for every detail):**
`aidocs/testing_engine/n014_explorer_006_proposal.md` — start at the *Module
Map* entry `#### M6 — Onboarding`, then the *Components* subsections tagged
`(M6.x)`, then the narrative sections those components name.
*Architecture*, *Design decisions* and the *Invariants every module honours*
apply to every module.

**Acceptance:** the union of the framework components' test lists (*Module
Map — How to read it*): the M6.1 setup case and M6.5. The M6.1–M6.4 engine
test lists belong to aitasks_go#t63.

## Submodules (framework children — settled at the coarse planning pass)

| submodule | scope | depends on | wave |
|---|---|---|---|
| **M6.1 (framework part)** State report branch | `report_testmap_state()`'s `TESTMAP:bootstrapping\|<next phase>` branch for an unfinished `aitestmap/onboard.yaml`, between the absent and onboarded arms (a comment marks the spot); its own case in `tests/test_install_engine_binary.sh` next to T1–T3. Owns that extension of M1.5's reporter. May be its own small child or folded into M6.5's work | M1.5 (t1852_5, landed); the ledger format of aitasks_go#t63's M6.1 child (`xdeps`) | E |
| **M6.5** Onboarding skill | the `aitask-testmap-onboard` stub + `SKILL.md.j2` + one procedure file per phase; the survey and level proposal; task creation and claim (`--type chore --labels testing,testmap`); the `enable` phase's edits to `project_config.yaml`, profiles, `gates.yaml`, `docs:` / `notes:`, the hand-maintained `CLAUDE.md`, with the gate order and `ENABLE_REFUSED:gate_dag_mode`; the `full_run` phase (`costs --gate-timeout`, the next level's task with `depends:`); the `--policy selected` re-entry; `--no-task`; refresh mode; the headless flow; goldens; `tests/test_testmap_onboard_ledger.sh`; the five permission touchpoints. Owns `.claude/skills/aitask-testmap-onboard/**`, `tests/golden/skills/aitask-testmap-onboard/`, the ledger test | M4.4 (aitasks_go#t61, not yet decomposed), M5.1 (t1856, not yet decomposed), M6.1–M6.3 (aitasks_go#t63, not yet decomposed), M8.2 (t1859_2), M8.3 (t1859_3), M8.4 (t1859_4) | F |

M6.2–M6.4 and the engine part of M6.1 are aitasks_go#t63's children. Headless
level 1 additionally needs M7.2 (aitasks_go#t64, not yet decomposed) and M7.5
(t1858).

## M6.5 contract notes (from the notes this task received; re-verify at the Reality check)

- **Setup report** (t1852_5): `report_testmap_state()` ships
  `TESTMAP:engine-missing`, `TESTMAP:absent|run /aitask-testmap-onboard` and
  `TESTMAP:onboarded`. "Registry present" is `aitestmap/config.yaml`. Setup
  reports and never onboards; the state prints after `install_engine_binary`
  on `ait setup` only.
- **Permission touchpoints** (t1852): the first skill of this module that
  calls `ait testmap` or `./.aitask-scripts/aitask_testmap.sh` owes the
  five-touchpoint checklist (`.claude/settings.local.json`,
  `.codex/rules/default.rules`, `seed/claude_settings.local.json`,
  `seed/codex_rules.default.rules`, `seed/opencode_config.seed.json`) as an
  explicit deliverable.
- **Gate order** (t1859 Dev 13): `enable` inserts `testmap_fresh,
  testmap_check` immediately before `tests_pass`, or appends all three in
  that order. It never reorders entries and never adds `unlocks:`; any
  explicit `unlocks` flips the whole set into DAG mode
  (`gate_orchestrator._dag_mode` in `.aitask-scripts/lib/gate_orchestrator.py`).
  Before writing, `enable` runs a compatibility check with the orchestrator's
  own predicate; in DAG mode it writes nothing and prints
  `ENABLE_REFUSED:gate_dag_mode|<profile>|<gates declaring unlocks>`. Merging
  the map gates into an existing DAG is a named follow-up.
- **Headless config** (t1859 Dev 14): autonomous lanes under
  `require_stamp: true` past `bootstrap_until` need the repair coordinator
  (t1853_7 / aitasks_go#t59_1). Until it lands, `enable` does not create that
  state for headless profiles.
- **Procedure gates** (t1859): t635_29 (headless procedure-gate dispatch) has
  not landed. Until it does, `testmap_fresh` defers as "needs agent" in
  autonomous lanes, so declaring it into a headless profile blocks archival.
- **Policy** (t1859): `--policy selected` stays an optional attended
  alternative; `auto` is the automated route.
- **Gate timeout** (t1854 Dev 12, t1854_4): `full_run` consumes
  `ait testmap costs --gate-timeout <gate> [--host-class <hc>]`, which prints
  `GATE_TIMEOUT_SUGGESTED:<gate>|<seconds>` (max(600, ⌈3 × full-suite p95⌉),
  exit 0). Before a full run qualifies it prints `COSTS_NO_FULL_RUN:<hc>` on
  stderr and exits 2, so call it only after the `full_run` phase's measured
  run (`--run-id full-…` with `--all`, every invocation cause-free).
  Untimed members add `COSTS_UNMEASURED:<hc>|<n>`.
- **Language policy** (t1954_4): inline annotations are supported in bash,
  Python, Go and Kotlin only. The skill surfaces unsupported-language test
  files explicitly (the engine's `ADOPT_SKIP …|no-leader` lines), never as
  "no annotations"; the onboarding docs and the skill state the four-language
  policy.
- **Code modules** (t2131, t2131_1): the skill is the natural place for an
  agent to propose or correct module boundaries; that work is t2131_9's
  framework half. `detect --write` never writes `completion.mode: module`;
  `enable` writes it only through t2131_11, once the engine reports `module`
  as supported.
- **Repair** (t1853_7): M6.5's onboarding integration consumes the repair
  coordinator to migrate a whole existing corpus; that extension lands in
  t1853_7's framework half.

## Cross-module seams

**Provides** (defined here, consumed elsewhere):

- The `report_testmap_state` consumer of `onboard.yaml` phases (M6.1 → M1.5);
  the ledger and `ONBOARD_NEXT:` themselves are aitasks_go#t63's.
- Levels 0 and 1 attended; levels 0 and 1 headless once M7.2 and M7.5 exist —
  M6.5 → M9.5 (ports), M10.x (rollout).

**Consumes:** the installed engine and `report_testmap_state()` (M1.5); the
engine verbs of M6.1–M6.4 (aitasks_go#t63) through the shim; `readiness` (M4.4,
aitasks_go#t61); `ait test` (M5.1, t1856) and the brief (M5.2, aitasks_go#t62 through
t1856's front); the `testmap_check` gate and the completion policy (M8.2
t1859_2, M8.4 t1859_4); the verdict intake and the review skill for the
headless level 1 (M7.2 in aitasks_go#t64, M7.5 in t1858); existing framework
surfaces `aitask_create.sh`, `aitask_pick_own.sh`, `ait attach`,
`aitask_task_commit.sh`, the profiles.

**Hooks and extensions** (a file has one owner; a later submodule lands its
edit as the owner's named extension):

- M6.1's framework part extends `report_testmap_state()` (owned by **M1.5**)
  with `bootstrapping|<next>`; M6.1's engine part adds `ONBOARD_NEXT:` to the
  brief (aitasks_go#t63 → aitasks_go#t62).
- The `review.md` sub-phase under this skill's tree is owned by **M7.5**
  (t1858); M6.5 ships without it, and headless level 1 lands when M7.2 and
  M7.5 exist.
- The level task the skill creates uses `--type chore --labels
  testing,testmap`; the rollout tasks (**M10**) are these level tasks in each
  target repository.
- Invariants 3 and 10 bind the skill flow: an autonomous path may seed
  everything, may adopt a class only when every member carries a rule, a
  measurement or a reading and clears `agent_review.accept_min`, and may never
  adopt a heuristic alone, reject a seed, change a kind or declare an axis;
  headless runs record kind proposals and never enter level 3. The engine
  verbs enforce the same refusals (aitasks_go#t63).
- Every skill edit follows `aidocs/framework/skill_authoring_conventions.md`
  and `stub-skill-pattern.md` (Claude Code first; goldens in the same commit).

## Automation-first (user directive, 2026-10-11)

Treat every proposal step that makes a human action a precondition as a
candidate to automate; record the decision in the child plan and fix cut
changes in the proposal. Framework-side candidates: the skill's per-runner
confirmation of `runners.yaml`, the "listed for a person" steps, the
`onboard reject` / `adopt --class` / kind-change / axis-declaration flows as
the skill presents them. The engine-side decisions for the same verbs are
aitasks_go#t63's; it sends its cut changes here as notes.

## Wiring (when the children exist)

- M6.5 ← M5.1 (t1856's child), M8.2 / M8.3 / M8.4 (t1859_2, t1859_3,
  t1859_4): in-repo `depends:` edges.
- M6.5 ← M6.1, M6.2, M6.3 (aitasks_go#t63's children), M4.4 (aitasks_go#t61's child),
  and for headless level 1 M7.2 (aitasks_go#t64's child): `xdeps` with
  `xdeprepo: aitasks_go`. Until the ids exist, the child body records the
  prose hold with its owner, e.g. "M6.3 (aitasks_go#t63, not yet decomposed)".
- The M6.1 framework branch ← aitasks_go#t63's M6.1 child: `xdeps`.
- t2131_9 ← M6.5 and t2131_11 ← M6.5: in-repo `depends:` edges. t2131_9's
  M6.1 / M6.4 holds are engine-side (aitasks_go#t77_6 ← aitasks_go#t63's children,
  wired by aitasks_go#t63).
- t1853_7 ← M6.5: an in-repo `depends:` edge.

`--deps` and `--xdeps` replace the whole list, so repeat the existing
entries. Flip a consumer to Ready only once nothing in its hold is left
unresolved; `xdeps` unblock only when the target is Done.

## Reading list in the proposal

- *Module Map* — `#### M6`, *How to read it*, *Cross-module interfaces*,
  *Suggested implementation order* (waves E, F, G).
- *Components* — *Onboarding skill `aitask-testmap-onboard` (M6.5)*,
  *Onboarding verbs (M6.1 / M6.3 / M6.4)* (as consumed), *Engine install,
  upgrade and state report (the `bootstrapping` state)*, *Code modules*.
- *The Adoption Model* — whole section.
- *Onboarding: Levels × Phases* — whole section, especially *Invocation and
  task shape* and *Detection, per target repository*.
- *Data Flow* — *Onboarding level 0*, *Level 1: seeds → verdicts → stamped
  edges*.
- *Overview* — *How the loop closes without a person* (mechanism 2).
- *Assumptions* — *Seeding and adoption (M6, M7)*, *Onboarding (M6)*;
  *Tradeoffs* — *Seeding, adoption and onboarding (M6, M7)*; *Open questions*.

## Planning and implementation protocol (binding for this task and every child)

This feature spans **ten parent tasks**, one per module of the proposal (see the
module → task map at the end). Since the t22 cutover the engine halves of
several parents live in beyondeye/aitasks_go. The modules are cut by ownership
of files, verbs and line protocols, so children of different parents meet on
the interfaces listed above. Two consequences are binding.

### 1. Coarse planning pass

- Plan this task through the normal workflow (`/aitask-pick` → planning). In
  the Complexity Assessment choose **"Yes, create child tasks"** and decompose
  into **one child task per row** of the table above (the M6.1 framework part,
  unless folded into M6.5, and M6.5; keep the `M6.<m>` id in the child name);
  let the workflow write the child plan files; at the child-task checkpoint
  choose **"Stop here"**. Start once the provider submodules the
  wave-earliest child consumes have landed (submodule-granular), and
  implement in proposal wave order.
- Keep the coarse plan coarse. A child's plan records what the proposal fixes
  for that submodule — scope, owned files, provided and consumed interfaces,
  the component test lists that are its acceptance — and its wave. It does
  **not** design internals against providers that do not exist yet; that is
  the reality check's job (§2 below), and the child plan must say so.
- Express cross-module order in task data, not in prose: `depends:` inside
  this repository, `xdeps` (`xdeprepo: aitasks_go`) on aitasks_go tasks (see
  *Wiring*).
- Parent-level `depends:` stays empty on purpose: module-level dependencies
  form a cycle (M6.5 → M8.2 / M8.4, M8.3 → M7.1 / M7.2, M7.1 → M6.2) and would
  block wrongly; the real graph is acyclic only at submodule granularity.
- Deviations from the proposal found while planning go into a **"Deviations
  from the proposal"** section of the plan. A wrong cut is fixed **in the
  proposal**, not patched in a plan (`assumption_modules_map_to_parent_tasks`).
  Send a note (`/aitask-note`) to every parent whose tables the change touches,
  including the aitasks_go halves (`--project aitasks_go`).

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

- The skill goldens and `tests/test_testmap_onboard_ledger.sh` pass.
- The DAG fixture (`build_verified` → `tests_pass` → `lint`) is refused with
  `ENABLE_REFUSED:gate_dag_mode`, and a linear control is written in order.
- The `tests/test_install_engine_binary.sh` bootstrapping case passes.
- The touchpoint contract test passes with the five touchpoints present.
- Headless level 1 is gated on M7.2 / M7.5.
- The body points to aitasks_go#t63 (header above).

## Module → task map

| module | framework (aitasks) | engine (aitasks_go) |
|---|---|---|
| M1 — Engine foundation and distribution | t1852 (landed) | — |
| M2 — Registry and map model | t1853 | aitasks_go#t59 |
| M3 — Runners, scheduling and cost | t1854 | aitasks_go#t60 |
| M4 — Selection, freshness and feedback | t1855 (tracker) | aitasks_go#t61 |
| M5 — Run surface | t1856 | aitasks_go#t62 (M5.2 `brief`) |
| M6 — Onboarding | t1857 (M6.1 setup branch, M6.5) | aitasks_go#t63 (M6.1 engine, M6.2–M6.4) |
| M7 — Agent review and author annotation | t1858 | aitasks_go#t64 |
| M8 — Completion policy and gates | t1859 | aitasks_go#t65 |
| M9 — Workflow integration, skills and documentation | t1860 | — |
| M10 — Rollout to the target repositories | t1861 | — |

All ten aitasks parents share the topic anchor of the M1 task, so the board's
By-Topic view shows the whole feature as one lane.

## Carried obligations (framework half)

- `## Goal` / "the resumable `aitask-testmap-onboard` skill that runs one aitask per level, reaches level 1 in attended and headless profiles alike" — *Goal* and the M6.5 row of *Submodules*
- `## Goal` / "writes the `enable` phase's project configuration" — M6.5 row (`enable` phase edits) and *M6.5 contract notes*, gate order bullet
- `## Goal` / "**Acceptance:** the union of the module's components' test lists" — *Goal* (acceptance line) and *Acceptance*; the engine lists are aitasks_go#t63's
- `## Submodules` / M6.1 row "`report_testmap_state()`'s `bootstrapping|<next>` state" — M6.1 (framework part) row of *Submodules*
- `## Submodules` / M6.5 row (skill stub + `SKILL.md.j2` + procedures; survey; task creation; `enable` edits; `full_run`; `--policy selected`; `--no-task`; refresh; headless; goldens; `tests/test_testmap_onboard_ledger.sh`) — M6.5 row of *Submodules*
- `## Cross-module seams` › Provides / "`onboard.yaml` phases and `ONBOARD_NEXT:` — M6.1 → M1.5 (`report_testmap_state`), M5.2, M6.5, M7.2, M7.3, M6.4" — *Cross-module seams* → Provides (the `report_testmap_state` consumer); the ledger and line are aitasks_go#t63's
- `## Cross-module seams` › Provides / "Levels 0 and 1 attended; levels 0 and 1 headless once M7.2 and M7.5 exist — M6.5 → M9.5, M10.x" — *Cross-module seams* → Provides
- `## Cross-module seams` › Consumes / "the installed engine and `report_testmap_state()` (M1.5)" — *Cross-module seams* → Consumes; *M6.5 contract notes*, setup report bullet
- `## Cross-module seams` › Consumes / "`readiness` (M4.4)" — *Cross-module seams* → Consumes (`readiness` from aitasks_go#t61); *Wiring* (M6.5 ← M4.4 via `xdeps`)
- `## Cross-module seams` › Consumes / "`ait test` and the brief (M5.1, M5.2)" — *Cross-module seams* → Consumes; *Wiring* (M6.5 ← M5.1)
- `## Cross-module seams` › Consumes / "the `testmap_check` gate and the completion policy (M8.2, M8.4)" — *Cross-module seams* → Consumes; *Wiring* (M6.5 ← t1859_2, t1859_4)
- `## Cross-module seams` › Consumes / "the verdict intake and the review skill for the headless level 1 (M7.2, M7.5)" — *Cross-module seams* → Consumes; *Hooks* (headless level 1 waits on M7.2 / M7.5); *Wiring*
- `## Cross-module seams` › Consumes / "`aitask_create.sh`, `aitask_pick_own.sh`, `ait attach`, `aitask_task_commit.sh`, the profiles" — *Cross-module seams* → Consumes
- `## Cross-module seams` › Hooks / "M6.1 extends `report_testmap_state()` (owned by M1.5) … and adds `ONBOARD_NEXT:` to the brief (M5.2)" — *Hooks*, first bullet (the `report_testmap_state()` extension)
- `## Cross-module seams` › Hooks / "The `review.md` sub-phase under this skill's tree is owned by M7.5; M6.5 ships without it" — *Hooks*, `review.md` bullet
- `## Cross-module seams` › Hooks / "The level task the skill creates uses `--type chore --labels testing,testmap`; the rollout tasks (M10) are these level tasks" — *Hooks*, level-task bullet
- `## Cross-module seams` › Hooks / "Invariants 3 and 10 bind: an autonomous path may seed everything, may adopt a class only when … may never adopt a heuristic alone, reject a seed, change a kind or declare an axis; headless runs record kind proposals and never enter level 3" — *Hooks*, Invariants 3 and 10 bullet (the skill flow)
- `## Cross-module seams` › Hooks / "Every skill edit follows `skill_authoring_conventions.md` and `stub-skill-pattern.md` (Claude Code first; goldens in the same commit)" — *Hooks*, skill-edit bullet
- `## Reading list` — *Reading list in the proposal*
- Protocol §1 / "decompose into one child task per submodule row" — *Planning protocol* §1, first bullet (M6.1 framework part and M6.5 here; the engine rows are aitasks_go#t63's)
- Protocol §1 / "Keep the coarse plan coarse" — *Planning protocol* §1
- Protocol §1 / "Express cross-module order in task data" — *Planning protocol* §1 and *Wiring* (M6.5 → aitasks_go#t63 children by `xdeps`)
- Protocol §1 / "Parent-level `depends:` stays empty" — *Planning protocol* §1
- Protocol §1 / "Deviations … fixed in the proposal … Send a note" — *Planning protocol* §1, deviations bullet
- Protocol §2 / Reality check steps 1–6 — *Planning protocol* §2
- `## Module → task map` — *Module → task map* (both repositories)
- Inbox t1852 / "Permission touchpoints … The first skill of this module that calls `ait testmap` … owes the five-touchpoint checklist" — *M6.5 contract notes*, permission touchpoints bullet; *Acceptance*
- Inbox t1852_5 / "`report_testmap_state()` … A comment marks where M6.1's `TESTMAP:bootstrapping|<next phase>` branch goes … M6.1 adds its own case there" — M6.1 (framework part) row and *M6.5 contract notes*, setup report bullet
- Inbox t1853 / "Automation-first … `onboard reject` 'only a person', `onboard adopt --class` … kind changes … level-3 axis declaration … absent-`by:`-is-human" — *Automation-first* (skill flow and proposal edits)
- Inbox t1853_7 / "M6.5 onboarding integration will consume the same coordinator" — *M6.5 contract notes*, repair bullet: the integration lands in t1853_7's framework half; *Wiring* (t1853_7 ← M6.5)
- Inbox t1854 / "Dev 12. `GATE_TIMEOUT_SUGGESTED:` … M6.5's `full_run` phase consumes it unchanged" — *M6.5 contract notes*, gate timeout bullet
- Inbox t1854 / "Automation-first … `concurrency: serial` at bootstrap …; `runners.yaml` … 'confirmed per runner'" — *Automation-first*: the skill's per-runner confirmation step
- Inbox t1954_4 / "Action 1: onboarding and adoption (M6.3, M6.5) must surface unsupported-language test files explicitly, as `ADOPT_SKIP …|no-leader`" — *M6.5 contract notes*, language policy bullet (the skill surfaces the lines)
- Inbox t1954_4 / "Action 2: the onboarding docs and skill state the four-language policy" — *M6.5 contract notes*, language policy bullet (docs and skill state the policy)
- Inbox t1859 / "M6.5 depends on t1859_2 (M8.2), t1859_3 (M8.3 …) and t1859_4 (M8.4)" — *Wiring*: M6.5 ← t1859_2, t1859_3, t1859_4 in-repo
- Inbox t1859 / "Dev 13: enable owns the gate order … `ENABLE_REFUSED:gate_dag_mode` … Acceptance: a pre-existing DAG fixture … is refused, and a linear control is written in order" — *M6.5 contract notes*, gate order bullet; *Acceptance* (DAG fixture)
- Inbox t1859 / "Dev 14. … finish and config should not create that state for headless profiles before [t1853_7]" — *M6.5 contract notes*, headless config bullet
- Inbox t1859 / "Not yet landed: t635_29 … declaring [procedure gates] into a headless profile blocks archival" — *M6.5 contract notes*, procedure gates bullet
- Inbox t1859 / "`--policy selected` stays an optional attended alternative; `auto` is the automated route" — *M6.5 contract notes*, policy bullet
- Inbox t1854_4 / "`ait testmap costs --gate-timeout` … call it only after the `full_run` phase's measured run" — *M6.5 contract notes*, gate timeout bullet
- Inbox t2131 (05:01) / modules inferred / inspectable; "M6.1 `detect` / M6.4 `classify` are natural places to surface them, and the M6.5 skill is the natural place for an agent to propose" — *M6.5 contract notes*, code modules bullet (owned by t2131_9's framework half)
- Inbox t2131 (08:55) / "wire their ids in [t2131_9 ← M6.1, M6.4, M6.5; t2131_11 ← M6.5] … Flip each child to Ready" — *Wiring*: t2131_9 ← M6.5 and t2131_11 ← M6.5 in-repo; the M6.1 / M6.4 holds are aitasks_go#t77_6's
- Inbox t2131_1 / "`MODULES:` … printed by `detect` and `inventory`; `inventory` also lists `MODULE_UNRESOLVED:`"; "`detect --write` never writes `completion.mode: module`. The `enable` phase writes it only through t2131_11" — *M6.5 contract notes*, code modules bullet (`enable` writes `completion.mode: module` only through t2131_11)
- Inbox aitasks_go#t15 / coordination / freeze / re-home — The freeze is over; the engine verbs live in aitasks_go#t63 (header above)

## Relocated to aitasks_go

The engine scope below moved to aitasks_go#t63 and is quoted for reference only.

> - aitasks_go#t63 owns the M6 engine verbs, decomposed at its coarse pass in aitasks_go into M6.1 (engine part), M6.2, M6.3 and M6.4 children, each with a Reality-check step.
> - M6.1:
>   - the `onboard.yaml` schema and phase rows, written node / row-level so M2.6's four keys survive;
>   - `onboard detect [--write] [--force]` with `DETECT_DIFF:`. It emits a strict `runners.yaml` (the adapter keys from the t1854_1 / t1854_2 / t1854_12 notes) and a pre-enable `test_command` snapshot (no recursion), and sets `bootstrap_until` to +90 days;
>   - `inventory`, `status`, `finish [--auto]`, and the `AIT_PROFILE_HEADLESS=1` refusals;
>   - the `ONBOARD_NEXT:` line as an extension of aitasks_go#t62's `brief`.
> - M6.2: `onboard seed` (the origin table, noisy-OR, `helper_roots` / `helper_fanin`, `SEED_*`, `--apply` via `RouteOnboardSeed`).
> - M6.3: `adopt` / `reject` with the autonomous floor, `ADOPT_SKIP …|no-leader` for unsupported languages, the M2.6 routes, `annot.AnnotateWith`.
> - M6.4: `classify` / `scaffold`, the recorded-p95 `classify.RegisterSignal`, `SCAFFOLD_TODO` lister / check recognition, and `axes.yaml` skeleton validity.
> - The automation-first decisions for `reject`, `adopt --class`, kind changes and `scaffold --axes` are made here.
> - Acceptance:
>   - The union of the M6.1–M6.4 component test lists passes in aitasks_go CI (one fixture repo per seed origin).
>   - Invariants 3 and 10 hold in the engine: no autonomous heuristic-only adoption, no autonomous reject, kind change or axis declaration; headless runs never enter level 3.
>   - `finish` / `detect --write` never create a `require_stamp: true`-past-bootstrap state for headless profiles before aitasks_go#t59_1 lands.
>   - `detect --force` after enable never emits a recursive suite command.


## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1852** id=2026-09-22T14:31:36Z.923921fdff8e5c8753c78a01 from=t1852 at=2026-09-22T14:31:36Z base=d0836b4f1750fde12e5e30260cd0d34396793a17 base_branch=main dirty=yes host=omg16
>
> | **Sequencing clarification (advisory, from the t1852 coarse pass, 2026-09-22).** The user asked that M1's children be *implemented* before M2 (t1853) is *planned*. Read the "plan all ten parents before implementing any child" paragraph in this task's body as an upper bound on how far planning may run ahead, not a requirement to plan against providers that do not exist. The rule is submodule-granular, never whole-parent (module-level deps form a cycle: M6.5 -> M8.2/M8.4, M8.3 -> M7.1/M7.2, M7.1 -> M6.2): start this parent's coarse pass once the specific provider submodules its wave-earliest children consume have landed in the tree, and implement its children in proposal wave order. A standalone cross-linking chore task (created from t1852's pass, followup_kind risk_mitigation) checks every "depends on" cell against real depends entries once all ten parents are decomposed; it accepts archived children as evidence and never rewrites M10.2-M10.5 (cross-repo).
> | 
> | **Go source layout (proposal fix, commit 07a546087 on main).** The engine source directory is `goengines/`, not `engine/`: one Go module (`github.com/beyondeye/aitasks/goengines`) for every distributable Go executable, `goengines/cmd/ait-testmap/`, shared packages `goengines/internal/{gitx,platform,lineproto}`, and every testmap-specific package under `goengines/internal/testmap/<pkg>`. Wherever the proposal (and this task's owns cells) write `internal/<pkg>`, read `goengines/internal/testmap/<pkg>`. Unchanged: the binary name `ait-testmap`, `$AITASKS_HOME/engine/v<V>/`, the `ait engine` verbs. CI workflow is `goengines-check.yml`; the release job is `goengines`. M1.2 (t1852_2) creates the module root; each later submodule adds only its own package and replaces only its own stub verb.
> | 
> | **Permission touchpoints for `ait testmap` / `aitask_testmap.sh` are the first skill consumer's, not M1's** (t1852 plan, Deviation 2): no skill in M1 invokes the shim, and `aidocs/framework/aitasks_extension_points.md` forbids dead-weight allowlist entries. The first skill of this module that calls `ait testmap` or `./.aitask-scripts/aitask_testmap.sh` owes the five-touchpoint checklist (`.claude/settings.local.json`, `.codex/rules/default.rules`, `seed/claude_settings.local.json`, `seed/codex_rules.default.rules`, `seed/opencode_config.seed.json`) as an explicit deliverable of that child. Hedge: written against main @ 07a546087 with M1 not yet implemented; the shim's final path is M1.4's to confirm.

> **✉ note:t1852_5** id=2026-10-06T20:13:02Z.b55b93254defec9219842e97 from=t1852_5 from_verified=yes at=2026-10-06T20:13:02Z base=7f412d482c3e1e67c0bae2729754b8505f95ba05 base_branch=main dirty=yes host=omg16
>
> | From t1852_5 (M1.5), tree-relative to code commit 7f412d482. These are claims for M6.1's planning to check against the landed files, not instructions.
> | 
> | - `report_testmap_state()` in `.aitask-scripts/aitask_setup.sh` ships three states:
> |   - `TESTMAP:engine-missing`: the shim's `testmap_resolve_engine` fails. It honours `AIT_TESTMAP_BIN` and `AIT_ENGINE`.
> |   - `TESTMAP:absent|run /aitask-testmap-onboard`;
> |   - `TESTMAP:onboarded`.
> | - A comment marks where M6.1's `TESTMAP:bootstrapping|<next phase>` branch goes, between the absent and onboarded arms. It is meant for an unfinished `aitestmap/onboard.yaml` ledger.
> | - "Registry present" is `aitestmap/config.yaml`, the same rule as the proposal's `ait test` resolution step 1, rather than the mere existence of an `aitestmap/` directory.
> | - Setup reports and never onboards. The state is printed after `install_engine_binary` on `ait setup` only; `install.sh` / `ait upgrade` do not call the reporter.
> | - `tests/test_install_engine_binary.sh` cases T1–T3 pin the three states; M6.1 adds its own case there.

> **✉ note:t1853** id=2026-10-11T14:44:04Z.2b67d0598064fd963be14004 from=t1853 at=2026-10-11T14:44:04Z base=3bc0de8ac7a9c9d1f60173e1257715a744efc451 base_branch=main dirty=yes host=omg16
>
> | Advisory, from the t1853 (M2) coarse pass. Proposal M2 cut fixed in commit 3bc0de8ac on main.
> | 
> | - **The recorded-p95 signal in `classify --suggest` is now M6.4's** (named extension of M2.5's verb; it needs M3.4's cost ledger, which M2.5 at wave B cannot read). This was added to M6.4's Module Map row.
> | - M2.6 (t1853_6) moved to wave B; M6.2 / M6.3 consume it.
> | 
> | **Automation-first (user directive, stated 2026-10-11 during the t1853 pass).** Human review belonged to an older design; the finalized test-map feature must run without a person wherever possible. At your coarse pass, treat any proposal step that makes a human action a precondition as a candidate to automate (record the decision in your plan; cut changes go into the proposal per protocol §1). From my reading, M6 still carries several human-only steps: `onboard reject` "only a person", `onboard adopt --class` described as a person's action, kind changes applied only by a person (M6.4), level-3 axis declaration (`scaffold --axes`), and the absent-`by:`-is-human reading of rejections. Not verified against your module's full text.

> **✉ note:t1853_7** id=2026-10-12T05:55:58Z.95df9d88f2abb6b00e35a6c3 from=t1853_7 at=2026-10-12T05:55:58Z base=8395bc6c68f1b977f83470466b549547d4b1ec58 base_branch=main dirty=no host=omg16
>
> | Advisory cross-reference: the user requested full automatic test-map repair for adoption of existing codebases. Created [t1853_7](t1853/t1853_7_automate_testmap_repair_for_existing_codebases.md) for the check → repair → recheck loop, including missing annotations and invalid ownership.
> | 
> | M6.5 onboarding integration will consume the same coordinator to migrate a whole existing test corpus, including files with no annotations. Base onboarding providers remain independently implementable; the new sibling lands the later integration extension.
> | 
> | As of this moment, the consumer is Postponed pending real provider child IDs. Its dependency table names this parent's required modules; resolve and add actual child dependencies during decomposition, preserving current edges. t1863 explicitly audits this supplementary consumer and its hold in addition to the original module rows.

> **✉ note:t1853_2** id=2026-10-12T14:31:16Z.a09316de5edfc2ea9be49a09 from=t1853_2 from_verified=yes at=2026-10-12T14:31:16Z base=7229dee868985aafae8cd16e493614d1904311b5 base_branch=main dirty=no host=omg16
>
> | For M6.3 (`onboard adopt`): M2.2's rewriter landed in f096db065 (contract in the proposal at 7229dee86). Advisory, as of that tree.
> | 
> | - annot.PlanCovers / File.Placement give the fixed per-language insertion:
> |   - bash: after the shebang and the header comments
> |   - Python: after the module docstring
> |   - Go: after the package clause
> |   - Kotlin: after the imports, or inside the member's testmap:unit block
> | - Write with one annot.Apply per file, carrying f.Snapshot().
> | - annot.ErrNoLeader (ParseFile on a file of no known language) maps to ADOPT_SKIP:<path>|no-leader.
> | - A file whose lexical context is uncertain (File.Ctx.Uncertain / annot.ErrUncertainContext) is never written.
> | - *annot.ConflictError is REWRITE_CONFLICT, exit 75.
> | 
> | No human-only step was met.

> **✉ note:t1853_3** id=2026-10-13T12:53:00Z.b4db1d5c21c6671350141946 from=t1853_3 from_verified=yes at=2026-10-13T12:53:00Z base=2c04a9639cc377ce62858e5af12bbc3a0f76412b base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1853_3 (M2.3 dependency scanners), as landed in 2c04a9639. These are claims about that tree; verify against the code.
> | 
> | For M6.2 seeder / M6.4:
> | - Seeds come only from `Graph.Static(path)`: deps with an `Origin` of `static:invocation`, `static:import` or `static:package`, each with an anchor `Line`.
> | - Closure-only edges (`Origin ""`) are never seeds. That covers `fallback`, `suffix`, `anywhere`, `embedded-python`, `package-fallback`, `same-package`, `init`, `conftest`, `path`, `module-build`, `build-input`, `plugin:<n>`, among others.
> | - Python claims `static:import` only when Python's choice is certain: the statement order and lexical scope are modelled, and an uncertain lone winner with no competing candidate is the exception. Uncertain cases deliberately produce no claim.
> | - Source roots = the repository root plus every directory some scanned file's bootstrap resolves to (bash directory variables, Python `sys.path` entries). Misses are retried against them, closure-only.
> | - `annotate --suggest <test>` (`deps.Suggest`) lists direct deps, walking `helper_roots:` helpers, with new/covered state. It may be a useful seed preview.
> | - No human-only step was needed in M2.3.

> **✉ note:t1854** id=2026-10-13T16:21:06Z.59c5c0c47b2aef2203f3c5bc from=t1854 at=2026-10-13T16:21:06Z base=6a3a81efc30577c762d42f815f3e95eac95b4e3f base_branch=main dirty=no host=omg16
>
> | Advisory, from the t1854 (M3) coarse pass. The proposal's M3 cut was fixed in 6a3a81efc; see the Deviations in aiplans/p1854_testmap_m3_runners_scheduling_and_cost.md. These are tree claims; verify them at your pass.
> | 
> | - **Dev 8.** `SCAFFOLD_TODO` recognition, and its `check` report, are now **M6.4's** named extension of M3.1's lister and M2.1's `check`. The M6.4 row says so. Until M6.4 lands, M3.1's lister refuses that `list` row as `INPUT_ERROR:lister`.
> | - **Dev 12.** `GATE_TIMEOUT_SUGGESTED:` is now homed in the *Cost ledger* component (M3.4), not under the onboarding verbs. M6.5's `full_run` phase consumes it unchanged.
> | - The **full-suite p95** behind `--gate-timeout` is now defined. It is the M3.4 estimate over the newest `full-` run, counting top-level ids only.
> | - **Detect and recursion.** `detect` must snapshot the *pre-enable* `test_command` into the `full` suite runner's command and its `fallback_command`. After the `enable` phase, `test_command` is `./ait test`. A `full` runner wrapping that would recurse, and would reach `aitask_test.sh` (Invariant 5). M3.2 (t1854_2) refuses such a command; `detect --force` after enable must not produce it.
> | - **Automation-first (user directive).** Two human-flavoured steps sit next to M3 and are yours to automate at your coarse pass:
> |   - `concurrency: serial` at bootstrap, with declarations "reviewed in the schedule report before concurrency is trusted" (`tradeoff_resource_declaration_completeness`). One possibility: flip to `parallel` on measured agreement between serial and parallel full runs.
> |   - `runners.yaml` written by `onboard detect --write` and "confirmed per runner".
> | 
> |   M3 itself encodes no human precondition. `schedule --check` is informational.

> **✉ note:t1854_1** id=2026-10-14T14:40:35Z.36dceb0162821ab97fe06c32 from=t1854_1 from_verified=yes at=2026-10-14T14:40:35Z base=02e4a1badd5a7a8af9d2e250e7108cb8e1cd993e base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1854_1 (M3.1), as landed in 3d1a2b628. Verify against goengines/README.md → Interfaces ("runners.yaml and resolution").
> | 
> | - `onboard detect --write` must emit aitestmap/runners.yaml. The file is strict, unknown keys are refused, and it must be a single YAML document:
> |   - top level: `{contract: 1, max_invocation_s?, runners: [...]}`;
> |   - each runner: `{name, builtin | script, command? (builtin only), cwd?, bind: [globs], timeout_s?, batch_timeout_s? (required iff timeouts: batch), max_invocation_s?, subsumed_by?, fallback_command? (only on a unit: suite runner)}`, plus any describe key as an override (unit, full, children, timeouts, …);
> |   - every timeout is finite and in [0.001, 2592000] s.
> | - subsumed_by must name a full: true runner, never itself, with no cycle. `run --all` refuses (exit 3) when a subsumed runner's terminal suite selects no unit. thinking_app's screen-matrix / gradle-class → verify-active chain is valid.
> | - An absent runners.yaml is now INPUT_ERROR:lister|aitestmap/runners.yaml: absent for scan / check (exit 3), not an empty universe.
> | - A `SCAFFOLD_TODO` list row is refused as INPUT_ERROR:lister until M6.4 adds recognition; the parser is ParseList in internal/testmap/runner/list.go.

> **✉ note:t1954_4** id=2026-10-14T18:37:16Z.2b4c3ef1f8d8338f96da84e5 from=t1954_4 from_verified=yes at=2026-10-14T18:37:16Z base=f8d4b2ef54e729ae6e7ee76c1ba3f63395660f14 base_branch=main dirty=yes host=omg16
>
> | t1954 (multi-language annotation parsers) is complete. Report: aidocs/testing_engine/t1954_annotation_parser_research.md (sections 8 and 12). Verdict for M6: action.
> | - Language policy: inline annotations are supported in bash, Python, Go and Kotlin only. Every other language is unsupported until a reader passes the onboarding contract (report section 9).
> | - Action 1: onboarding and adoption (M6.3, M6.5) must surface unsupported-language test files explicitly, as `ADOPT_SKIP …|no-leader` from annot.ErrNoLeader, and never as "no annotations". Lexically uncertain files are never written.
> | - Action 2: the onboarding docs and skill state the four-language policy.
> | - Placement is unchanged (annot.PlanCovers / File.Placement).
> | - All five M10 targets use only the supported four. aitasks_mobile's 2 Swift files are app sources, not tests.

> **✉ note:t1853_5** id=2026-10-18T15:59:29Z.90f1cb973ecd3dea5a5d6230 from=t1853_5 from_verified=yes at=2026-10-18T15:59:29Z base=6f6d1ed799167c432f1ae5ed90abeb346b712f4f base_branch=main dirty=yes host=omg16
>
> | Advisory, for M6.4 (onboard classify), from t1853_5 (M2.5) as landed in 6f6d1ed79. Not yet a child of t1857, so routed to the parent; re-verify at your Reality check.
> | 
> | `classify --suggest` lives in the importable package `goengines/internal/testmap/classify`. The proposal's M2.5 owns cell gained it, so `onboard classify` can wrap it.
> | 
> | API:
> | - `classify.Suggest(ctx, root, registry.Inputs, tests []string) ([]classify.Suggestion, error)`; each suggestion is `{Test, Kind, Reason, Current}`.
> | - `classify.RegisterSignal(name, func(classify.Input) ([]classify.Signal, error))`. A signal is `{Kind, Token}`; tokens carry no `|` or `;`. Register the recorded-p95 signal here. Registering a name twice panics.
> | 
> | The reason field is `;`-joined tokens: `convention:<glob>`, `resource:<name>` and `resource:needs:<name>`, `fanout:<n>`, then `areas:<a>,<b>`. The areas come from the registry areas table rather than raw `code_areas.yaml`.
> | 
> | Eligibility:
> | - Excluded files and `testmap:reads` helpers are never targets; they are refused when named.
> | - Variant-bearing files are never suggested a broad kind.
> | - A file whose member blocks declare a different kind is not suggested.
> | 
> | A suggestion only fires when it outranks the current kind. Nothing is written — kind changes stay with M6.4.

> **✉ note:t1853_6** id=2026-10-19T09:18:10Z.4c1f5b0427cfddd3dcf10d8b from=t1853_6 from_verified=yes at=2026-10-19T09:18:10Z base=093d98a197a65931bdd6f104d4a919f965dfc0ee base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1853_6 (M2.6 adoption tables). It describes the tree as of aaeb10b0f, so verify it in your reality check. M6's children are not decomposed yet, so this note goes to the parent.
> | 
> | The write routing the M6 verbs must use (goengines/internal/testmap/registry, `OpenAdoption(ctx, root, route)` … `Commit()`):
> | 
> | | verb | route | ops |
> | |---|---|---|
> | | `onboard seed --apply` | `RouteOnboardSeed` | `PutSeed`, which skips rejected pairs |
> | | `onboard adopt --class` / `--auto` | `RouteAdoptClass` | `RemoveSeed` + `PutAdopted` |
> | | per-row `adopt` | `RouteAdoptRow` | `RemoveSeed` + `DeleteAdopted` |
> | | `onboard reject` | `RouteOnboardReject` | `RemoveSeed` + `AddRejection` |
> | | `onboard classify --propose` | `RouteClassifyPropose` | `AddKindProposal` |
> | 
> | Any other op is `ADOPTION_ROUTE`.
> | 
> | - **Stamp test files through `annot.AnnotateWith`.** Its intent hook writes provenance for an agent/auto first stamp before the file is written.
> | - **`onboard.yaml` is shared with M6.1.** M2.6 reads and writes only `rejections[]`, `reviews[]`, `kind_proposals[]` and `calibration[]`, by splicing rows. Every other key is left byte-identical, and a flow-style top-level mapping is refused. M6.1's own writer must likewise keep those four keys intact (edit at the node or row level; never re-render the file from a struct that drops them).
> | - **Person-only rejection is NOT enforced by the routing.** `AddRejection` records whatever `by:` it is given, and an absent `by:` reads as a person's. `REJECT_REFUSED:headless` stays M6.3's to enforce, if it stays at all under automation-first.

> **✉ note:t1859** id=2026-10-19T12:47:09Z.d1872615f2bade9b9a9e6d81 from=t1859 at=2026-10-19T12:47:09Z base=bf32b336c0b0673eccba125bf097df173405e8d7 base_branch=main dirty=yes host=omg16
>
> | Advisory, from the t1859 (M8) coarse pass. The proposal fix is commit bf32b336c; the plan is aiplans/p1859_*.md. These are tree claims; verify them at your pass.
> | 
> | - **Dependencies.** M6.5 depends on t1859_2 (M8.2), t1859_3 (M8.3, new in Dev 12, because enable writes testmap_fresh) and t1859_4 (M8.4). M8.2 moved to wave E (Dev 11).
> | - **Dev 13: enable owns the gate order.**
> |   - It inserts `testmap_fresh, testmap_check` immediately before `tests_pass`, or appends all three in that order. It never reorders entries and never adds `unlocks:`. Any explicit `unlocks` flips the whole declared set into DAG mode (`gate_orchestrator._dag_mode`, .aitask-scripts/lib/gate_orchestrator.py:91), where gates without `unlocks` become terminal.
> |   - Before writing, enable runs a compatibility check with the orchestrator's own predicate. If the resulting set is in DAG mode, it writes nothing and prints `ENABLE_REFUSED:gate_dag_mode|<profile>|<gates declaring unlocks>`.
> |   - Acceptance: a pre-existing DAG fixture (build_verified→tests_pass→lint) is refused, and a linear control is written in order.
> |   - Merging the map gates into an existing DAG is a named follow-up.
> | - **Dev 14.** Autonomous lanes under `require_stamp: true` past `bootstrap_until` need the repair coordinator t1853_7. Until it lands, that configuration fails loudly at testmap_fresh/testmap_check. finish and config should not create that state for headless profiles before then.
> | - **Dev 4.** testmap_check always runs `check --strict`; `bootstrap_until` is the strict flip (detect --write sets +90 days, finish shortens it).
> | - **Not yet landed: t635_29** (headless procedure-gate dispatch). Until it lands, procedure gates such as testmap_fresh defer as "needs agent" in autonomous lanes, so declaring them into a headless profile blocks archival.
> | - **Automation-first.** `--policy selected` stays an optional attended alternative; `auto` is the automated route.

> **✉ note:t1854_4** id=2026-10-20T09:37:09Z.2c848ba36fea1c44e22dd839 from=t1854_4 from_verified=yes at=2026-10-20T09:37:09Z base=d70250f708143ce51667dd1491ae34f6919a4df5 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1854_4 (M3.4) as landed in 487271c89, for M6.5. These are tree claims: re-verify when you implement.
> | 
> | - **Output:** `ait testmap costs --gate-timeout <gate> [--host-class <hc>]` prints `GATE_TIMEOUT_SUGGESTED:<gate>|<seconds>` = max(600, ⌈3 × full-suite p95⌉), with exit 0.
> | - **Before a full run qualifies:** it prints `COSTS_NO_FULL_RUN:<hc>` on stderr and exits 2, so call it only after the `full_run` phase's measured run. That run must use `--run-id full-…` with `--all`, and every invocation must be cause-free.
> | - **Untimed members:** they add `COSTS_UNMEASURED:<hc>|<n>` on stderr; the median fallback is included in the suggestion.
> | - **Host class:** it defaults to `config.yaml host_class` (the hostname). `policy` / `predictions` are reserved and refused.

> **✉ note:t1853_4** id=2026-10-21T09:40:08Z.ef18f542fcfeab8c0eb87070 from=t1853_4 from_verified=yes at=2026-10-21T09:40:08Z base=1518db7680e1a4a7d968ae489f0c67218d0f7f34 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1853_4 (M2.4 Axes and variants) as landed in 1518db768; re-verify in your Reality check. Tree-relative claims only.
> | 
> | For M6.4's `onboard scaffold --axes` (the level-3 skeleton writer):
> | - Target schema: `aitestmap/axes.yaml` `{contract, axes: [{name, facets[], values{<value>: {<facet>: <v>}}, sources{<facet>: {<v>: [<glob>...]}}}]}`, decoded strictly (unknown keys refused).
> | - Load refusals that constrain a skeleton (`REGISTRY_INVALID:aitestmap/axes.yaml|...`, exit 3 for EVERY verb that loads the registry): `values` must be non-empty (`values is required`) — so an empty `values: {}` placeholder breaks the whole registry; every value must name exactly one v per declared facet; a source `v` must be carried by some declared value; names `[^.=\s|#@/]+` with no control char or Unicode whitespace; value names must be non-empty variant id fragments. A skeleton therefore has to be either complete enough to load or written somewhere the loader does not read until the maintainer fills it — your design call.
> | - Runner side: the scaffolded runner's describe declares `axis: <name>` (and optionally `token_format:`, placeholders {id} {base} {path} {member} {variant}); a runner naming no axis lists variants that are never judged by check.
> | - Checks the maintainer will see after filling: DEAD_AXIS_SOURCE (always fails), UNKNOWN_VARIANT and UNCOVERED_VALUE (fail under --strict past bootstrap); `axes --explain <path>` shows where a file lands.

> **✉ note:t1854_2** id=2026-10-21T19:10:44Z.dac78f0487962817441d083d from=t1854_2 from_verified=yes at=2026-10-21T19:10:44Z base=5582dd4f455372f5ba40a43b6d2dffe2101089b3 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1854_2 (the M3.2 re-decomposition, 2026-10-21). Shapes are planned, not landed; they are as of the commit this note records.
> | - Your body's line "M3.2 (t1854_2) refuses such a command" now reads: t1854_7 (the runtime recursion guard) plus t1854_12 (the suite adapter's command-text diagnostic).
> | - What `onboard detect --write` must emit when the adapters land:
> |   - `accounting: cases|unit|aggregate` and `discovery: native|inventory|candidates` (describe keys from t1854_2);
> |   - `zero_tests: error|skip` (default `error`);
> |   - `batch_timeout_s` for batch adapters;
> |   - the suite unit id `aitestmap/runners.yaml#<name>`;
> |   - a `{module}` placeholder in gradle commands.
> | - There is no `children:` until t1854_14 registers a reporting contract (G7). A `full` suite gets per-test child rows only from reports its command writes explicitly into `$AIT_TESTMAP_REPORT_DIR`.
> | - Adapters: t1854_8 bash-file, t1854_9 pytest, t1854_10 go-test / engine-test, t1854_11 gradle-class, t1854_12 suite, t1854_13 device (Postponed).
> | Details: parent t1854, section "M3.2 re-decomposition (2026-10-21)".

> **✉ note:t2131** id=2026-10-23T05:01:09Z.9db79a2fff0223911dd979d6 from=t2131 at=2026-10-23T05:01:09Z base=b460828651acc16079e3a895296343b1c422620d base_branch=main dirty=yes host=omg16
>
> | Advisory context from t2131 (testmap code-modules tier, status Ready, not yet planned). Nothing here is an instruction; your own planning decides.
> | 
> | t2131 adds a two-level code-module tier (module -> submodule) as a structural grouping of sources and tests. Modules are separate from areas: areas stay as broad-test impact scope and may reference modules by name. Parts that touch M6 onboarding, as decided during exploration (user-confirmed, not yet a landed design):
> | 
> | - Modules are inferred, not hand-maintained. The providers are:
> |   - Gradle `deps.Graph.Modules()` / `ModuleOf()` / `GradleModule.Deps` (landed in M2.3 but never persisted or exposed today);
> |   - Go and Python packages;
> |   - the two-tier `aitasks/metadata/code_areas.yaml`;
> |   - agent proposals.
> |   They are persisted as a generated, inspectable table, with hand `modules:` entries as overrides only. No independently maintained duplicate definitions.
> | - Inferred boundaries must be inspectable and overridable. M6.1 `detect` / M6.4 `classify` are natural places to surface them, and the M6.5 skill is the natural place for an agent to propose or correct boundaries.
> | - Membership: a test may belong to several modules. It comes from build structure and path containment plus the modules of the test's covered sources, even when path membership exists. This matters for flat test dirs like this repo's `tests/`. Annotations only correct it, and unresolved membership must be visible, not guessed. Onboarding reports should show it.
> | - `areas --import-codemap` (landed in M2.5) currently flattens `code_areas.yaml` children. t2131 plans to keep the hierarchy for modules, so any onboarding step that runs the import may see a changed shape.
> | - Code modules are logical groupings: build-system modules seed them but need not define their boundaries exactly. This may relate to `detect --write`'s `runners.yaml` `{module}` placeholder for Gradle. Per-module execution batching is a later t2131 step.
> | 
> | Terminology heads-up: t2131 uses `module`/`submodule` in CLI and YAML and renames M1-M10 to "implementation work packages" in the design prose of aidocs/testing_engine/n014_explorer_006_proposal.md.

> **✉ note:t2131** id=2026-10-23T08:55:54Z.7d23a7e996b7494468ec341b from=t2131 at=2026-10-23T08:55:54Z base=6b3161606e2989d1865628155f4e0bc1021cb917 base_branch=main dirty=yes host=omg16
>
> | t2131 (test-map code-module tier) is now decomposed. Two of its children are Postponed with a Dependency hold on M6 work packages that have no child ids yet:
> | - **t2131_9 `onboarding_module_review`**, held on M6.1, M6.4 and M6.5. depends: [t2131_5].
> |   - detect / classify / inventory surface the inferred modules (a `MODULES:` summary and `MODULE_UNRESOLVED:` to-dos);
> |   - the M6.5 skill's agent review writes `provider: agent` module proposals (intake shaped like `kind_proposals[]`) and `testmap:module` lines;
> |   - when the codemap is absent, the skill generates it on the framework side (`aitask_codemap.sh --write`);
> |   - it never writes `completion.mode`.
> | - **t2131_11 `onboarding_enable_module_mode`**, held on M6.5. depends: [t2131_8, t2131_9].
> |   - The M6.5 `enable` phase gains the `completion.mode: module` write **only** through this child, after the engine reports `module` as supported.
> | 
> | When your coarse pass creates the M6 children, wire their ids in with `aitask_update.sh --batch <id> --deps "<existing>,<new>"` (it replaces the list, so repeat the existing deps). Flip each child to Ready once nothing is left unresolved.
> | 
> | Advisory, ahead of t2131_1's proposal amendment (not landed yet): `areas --import-codemap` is planned to write module references instead of copied globs (t2131_5). `onboard detect --write` runs that import, so its level-0 output will change.
> | 
> | Plans: `aiplans/p2131_testmap_code_modules_tier.md` and `aiplans/p2131/`.

> **✉ note:t2131_1** id=2026-10-24T21:25:44Z.d99397f5ab52cf514e28a9a9 from=t2131_1 from_verified=yes at=2026-10-24T21:25:43Z base=5adc28fe429efa614cfea3e208dce4cfcc83d765 base_branch=main dirty=no host=omg16
>
> | Advisory, from t2131_1. Not an instruction; your own planning decides. The claims below are tree-relative, as of commit 5adc28fe4 (main), which amends aidocs/testing_engine/n014_explorer_006_proposal.md.
> | 
> | The onboarding touchpoints from the 2026-10-23 t2131 notes are now in the proposal, revised to FLAT code modules (user decision, 2026-10-24).
> | 
> | **Withdrawn from the earlier note:** "`areas --import-codemap` is planned to write module references instead of copied globs; `onboard detect --write`'s level-0 output will change." The import is unchanged; it still writes `<path>/**` globs, so detect's level-0 area output does not change.
> | 
> | **Where to read:**
> | - component *Onboarding verbs* (the new "Code modules on the onboarding surface" bullet);
> | - component *Onboarding skill* (the `enable`-phase sentence);
> | - component *Code modules*.
> | 
> | **Newly fixed:**
> | - `MODULES:<modules_n>|<unmapped_paths_n>|<provider>=<n>,…` is printed by `detect` and `inventory`; `inventory` also lists `MODULE_UNRESOLVED:<test>` lines as to-dos.
> | - Agent proposals:
> |   - they are flat glob modules (`provider: agent`, `by: agent:<agent-string>`);
> |   - their names may not use the generated prefixes `codemap:`, `gradle:`, `go:`, `py:`;
> |   - the intake refuses overlapping agent rows, and a hand module wins a name collision;
> |   - the intake is t2131_9's, shaped like `kind_proposals[]`.
> | - `detect --write` never writes `completion.mode: module`. The `enable` phase writes it only through t2131_11, once the engine reports `module` as supported.
> | 
> | The hold wiring the earlier note asked for is unchanged: M6.1, M6.4, M6.5 → t2131_9, and M6.5 → t2131_11.

> **✉ note:t15** id=2026-10-25T08:53:53Z.5ccb05586863bd017be53199 from=aitasks_go#t15 at=2026-10-25T08:53:53Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
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

> **✉ note:t1854_12** id=2026-10-27T07:01:55Z.28c3507aba2edaef2e52fb16 from=t1854_12 from_verified=yes at=2026-10-27T07:01:55Z base=aff353fe0e81e10eb613a30540418eb91c820e45 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1854_12 (M3.2i suite adapter), as landed in commit ecefd276d. Verify against goengines/README.md (the "suite builtin (M3.2i)" row) before relying on it.
> | 
> | For `onboard detect --write` emitting the full: true suite runner from the pre-enable test_command:
> | - The suite runs `bash -c <command:>` (not `sh -c`; user decision 2026-10-26), the shell the framework uses for test_command (lib/gate_verifier_lib.sh). So snapshot test_command verbatim, with no re-quoting for POSIX sh.
> | - Unit id `aitestmap/runners.yaml#<name>`, kind suite, one per entry.
> | - Emit NO `bind:` on the suite entry: the list refuses it.
> | - Emit no `unit` / `accounting` / `discovery` / `timeouts` override to another value: the suite's fixed contract (suite / aggregate / inventory / none) refuses them at list time. `full: true`, `needs:`, `subsumed_by` on other runners, and `fallback_command:` are fine. `children:` needs a registered reporting contract (t1854_14).
> | - The list also refuses when another runner's `bind:` matches `aitestmap/runners.yaml` (e.g. `aitestmap/**` or `**/*`), or when config.yaml `exclude:` matches it. The engine would otherwise silently drop the suite unit, so detect's catch-all binds must not cover that path.
> | - describe refuses a command naming the test front (`ait test`, `ait testmap test|run`, `ait-testmap test|run`, `aitask_test.sh`) with first stderr line `SUITE_RECURSION:<runner>|<word>`. Load reports it as `RUNNER_PROTOCOL:<runner>|describe|exit 3: SUITE_RECURSION:…`. A snapshot taken after enable (`./ait test`) is therefore refused, and a front behind a script is refused at runtime by t1854_7's guard.

> **✉ note:t22_3** id=2026-10-29T22:22:46Z.a2e5bcb47d93ed242290a650 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:22:46Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:11:35Z.2848a3ddb6160159de72304f from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:11:35Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | Split: the engine half of this task is aitasks_go#t63. This task's body
> | was trimmed to the framework half (the removed scope is quoted under
> | "Relocated to aitasks_go").
