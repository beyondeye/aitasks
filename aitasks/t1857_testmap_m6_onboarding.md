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
