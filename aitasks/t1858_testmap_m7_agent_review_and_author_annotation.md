---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [testing, testmap, go_engine, skills, codeagent]
anchor: 1852
created_at: 2026-09-22 09:19
updated_at: 2026-10-30 12:10
---

Split (aitasks_go#t22 cutover): the engine half of this task is aitasks_go#t64
in beyondeye/aitasks_go. This body is the framework half.

## Goal

Part of the **testing engine / test map** feature — ten parent tasks, one per
module of the proposal. This is **M7 — Agent review and author annotation**:
the reading — packets out, verdicts in — plus the authoring agent's own
claims.

Static closure proves that a test *runs* a script, not that it *checks* it;
turning evidence into a claim needs a reader of the test body, and an agent
can be that reader. Five of the six submodules are engine Go — the packet
writer (M7.1), the verdict intake (M7.2), calibration (M7.3), `annotate
--author` (M7.4) and the crew form's engine arms (M7.6) — and moved to
aitasks_go#t64, whose coarse pass decomposes them in aitasks_go.

This task keeps **M7.5 — Review skill and launch surfaces**: the
`aitask-testmap-review` skill with its launch surfaces (`ait skillrun`, `ait
codeagent`, `ait crew runner` — print mode an explicit opt-in on each). It
also keeps the module-level coarse planning for that row and the cross-repo
wiring of M7's consumers in this repository.

**Invariant 4 binds:** the engine never launches a code agent, never calls a
model, never decides a verdict. Launching legitimately lives here, in the
skill and the `testmap-review` codeagent operation.

**Proposal (authoritative for every detail):**
`aidocs/testing_engine/n014_explorer_006_proposal.md` — start at the *Module
Map* entry `#### M7 — Agent review and author annotation`, then the
*Components* subsections tagged `(M7.x)`, then the narrative sections those
components name. *Architecture*, *Design decisions* and the *Invariants every
module honours* apply to every module.

**Acceptance:** M7.5's component test list (*Module Map — How to read it*).
The M7.1–M7.4 and M7.6 lists belong to aitasks_go#t64.

## Submodules

| submodule | scope | depends on | wave |
|---|---|---|---|
| **M7.5** Review skill and launch surfaces | the `aitask-testmap-review` stub + `SKILL.md.j2` + `review-batch.md` (the verifies-or-drives rule stated once), the onboarding skill's `review.md` sub-phase invoking it, `ait skillrun testmap-review`, the `testmap-review` operation in `aitask_codeagent.sh` (interactive by default, `--print` only under `--headless`), `verified.testmap-review` in the three model seeds and `aitask-add-model`, goldens, the `tests/test_codeagent.sh` pin, the no-`claude -p` grep test, and the five allowlist touchpoints if the skill calls the shim. Owns `.claude/skills/aitask-testmap-review/**`, `review.md` under the onboarding skill, the `aitask_codeagent.sh` operation, the model-seed keys, `tests/golden/skills/aitask-testmap-review/` | M6.5 (t1857, not yet decomposed), M7.1, M7.2 (aitasks_go#t64, not yet decomposed) | G |

The engine rows (M7.1, M7.2, M7.3, M7.4, M7.6; waves F, F, G, F, H) are
aitasks_go#t64's children. M7.6's crew arms consume this task's `review-batch.md`
and register reviewers through `aitask_crew_addwork.sh`, so aitasks_go#t64's M7.6
child takes `xdeps` on the M7.5 child here once it exists: report its id to
aitasks_go#t64.

## Cross-module seams

**Provides** (defined here, consumed elsewhere):

- Bulk reading, attended and headless; the launch rule pinned by test — M7.5
  → M9.5 (ports), M10.x.
- `review-batch.md`, the work file M7.6's crew form hands each reviewer.

**Consumes:** the packets and the verdict intake (M7.1, M7.2, through the
shim); the onboarding skill tree (M6.5, t1857); existing framework surfaces
`ait skillrun`, `aitask_codeagent.sh`, `aitask_crew_addwork.sh`,
`lib/agent_string.sh`, the model seeds and `aitask-add-model`.

**Hooks and extensions** (a file has one owner; a later submodule lands its
edit as the owner's named extension):

- M7.5 owns `review.md` inside **M6.5**'s skill tree and the
  `testmap-review` operation inside `aitask_codeagent.sh`.
- The Step-8 in-gate site (**M8.3** seeds step, t1859_6) and the Step-7
  authoring site (**M9.1**, t1860) are consumers: M7 defines the packet, the
  intake and the skill, not the sites.
- Named follow-ups (not v1): a second-model cross-check of verdicts through
  `ait codeagent testmap-review --agent-string <other>` (the launch is this
  task's operation; the agreement accounting is aitasks_go#t64's M7.3);
  `agent_review.min_verified` as a floor on which models may write `--by`
  (the config / model-seed side here; the `--by` check in aitasks_go#t64's M7.2
  intake).

## Automation-first (user directive, 2026-10-11)

Treat every proposal step that makes a human action a precondition as a
candidate to automate. M7's candidates are `REVIEW_HUMAN` parking (two
`unsure` verdicts → a person) and `drives` / `unsure` rows "listed for a
person". aitasks_go#t64 decides the engine emission; this task decides how the
skill lists such rows, and writes cut changes into the proposal.

## Wiring (the consumers wait on M7's child ids)

- **t1859_6** (M8.3 seeds step) waits on M7.1 (packets, `onboard review
  --ids`) and M7.2 (`onboard adopt --agent-verdicts`). When aitasks_go#t64
  reports its child ids, give t1859_6 `xdeps` on both (`xdeprepo:
  aitasks_go`), remove the prose hold, and flip it from Postponed to Ready
  once nothing in its hold is left unresolved.
- **t1853_7** (the repair coordinator) consumes M7.2 (verdict adoption) and
  M7.4 (`annotate --author`) as first-stamp routes, and M7.5. Give its
  framework half `xdeps` on the M7.2 and M7.4 children and a `depends:` edge
  on the M7.5 child, preserving its current edges. Base providers never
  depend back on the coordinator. (aitasks_go#t64 wires the engine half
  aitasks_go#t59_1 in aitasks_go.)
- M7.5 ← M6.5 (t1857's child): in-repo `depends:`. M7.5 ← M7.1, M7.2:
  `xdeps` on aitasks_go#t64's children.
- Notify the other downstream consumers (t1860 for M9.1 / M9.3 / M9.5, t1861
  for M10.x) of the new ids.

`--deps` and `--xdeps` replace the whole list, so repeat the existing
entries. `xdeps` unblock only when the target is Done.

## Reading list in the proposal

- *Module Map* — `#### M7`, *How to read it*, *Cross-module interfaces*,
  *Suggested implementation order* (waves F, G, H).
- *Components* — *Agent review pass (M7.5)*, *Skills (the review skill)*;
  *Agent review verbs (M7.1 / M7.2 / M7.3 / M7.6)* as consumed.
- *The Agent Review Pass* — whole section (*The packet*, *The verdict*,
  *Calibration*, *The skill*, *Launch surfaces*, *The in-gate site (Step 8)*,
  *The authoring site (Step 7)*, *Budgets*).
- *Overview* — *How the loop closes without a person* (mechanisms 1, 3, 5).
- *The Adoption Model* — *The autonomous floor*, *The origin table*.
- *Data Flow* — *Level 1: seeds → verdicts → stamped edges*.
- *Assumptions* / *Tradeoffs* — *Seeding, adoption and onboarding (M6, M7)*;
  *Open questions*.
- Framework rules that apply: `aidocs/framework/skill_authoring_conventions.md`,
  `stub-skill-pattern.md`, `agent_runtime_guards_audit.md`; the `claude -p`
  headless-mode caveat in `shell_conventions.md`.

## Planning and implementation protocol (binding for this task and every child)

This feature spans **ten parent tasks**, one per module of the proposal (see the
module → task map at the end). Since the t22 cutover the engine halves of
several parents live in beyondeye/aitasks_go. The modules are cut by ownership
of files, verbs and line protocols, so children of different parents meet on
the interfaces listed above. Two consequences are binding.

### 1. Coarse planning pass

- Plan this task through the normal workflow (`/aitask-pick` → planning). In
  the Complexity Assessment choose **"Yes, create child tasks"** and create
  **one child task for the M7.5 row** (keep `M7.5` in the child name); let the
  workflow write the child plan file; at the child-task checkpoint choose
  **"Stop here"**. Sequencing is submodule-granular: start once the providers
  of the child have landed, and implement in proposal wave order.
- Keep the coarse plan coarse. The child's plan records what the proposal
  fixes for M7.5 — scope, owned files, provided and consumed interfaces, the
  component test list that is its acceptance — and its wave. It does **not**
  design internals against providers that do not exist yet; that is the
  reality check's job (§2 below), and the child plan must say so.
- Express cross-module order in task data, not in prose: `depends:` inside
  this repository, `xdeps` (`xdeprepo: aitasks_go`) on aitasks_go tasks (see
  *Wiring*), using `./.aitask-scripts/aitask_update.sh --batch <child-id>
  --deps ...` / `--xdeps ... --xdeprepo aitasks_go`.
- Parent-level `depends:` stays empty on purpose: module-level dependencies
  form a cycle (M6.5 → M8.2 / M8.4, M8.3 → M7.1 / M7.2, M7.1 → M6.2) and would
  block wrongly; the real graph is acyclic only at submodule granularity.
- Deviations from the proposal found while planning go into a **"Deviations
  from the proposal"** section of the plan. A wrong cut is fixed **in the
  proposal**, not patched in a plan (`assumption_modules_map_to_parent_tasks`).
  Send a note (`/aitask-note`) to every parent whose tables the change
  touches. aitasks_go#t64 sends its engine-side deviations here as notes; this task
  writes them into the proposal.

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

- M7.5's component test list is green: goldens, `aitask_skill_verify.sh`, the
  `tests/test_codeagent.sh` pin, the no-`claude -p` grep test.
- t1859_6 is Ready with its M7.1 / M7.2 cross-repo edges recorded.
- t1853_7's M7.x rows are resolved (M7.2 / M7.4 `xdeps`, M7.5 `depends:`).
- The body points to aitasks_go#t64 (header above).

## Module → task map

| module | framework (aitasks) | engine (aitasks_go) |
|---|---|---|
| M1 — Engine foundation and distribution | t1852 (landed) | — |
| M2 — Registry and map model | t1853 | aitasks_go#t59 |
| M3 — Runners, scheduling and cost | t1854 | aitasks_go#t60 |
| M4 — Selection, freshness and feedback | t1855 (tracker) | aitasks_go#t61 |
| M5 — Run surface | t1856 | aitasks_go#t62 (M5.2 `brief`) |
| M6 — Onboarding | t1857 | aitasks_go#t63 |
| M7 — Agent review and author annotation | t1858 (M7.5) | aitasks_go#t64 (M7.1–M7.4, M7.6) |
| M8 — Completion policy and gates | t1859 | aitasks_go#t65 |
| M9 — Workflow integration, skills and documentation | t1860 | — |
| M10 — Rollout to the target repositories | t1861 | — |

All ten aitasks parents share the topic anchor of the M1 task, so the board's
By-Topic view shows the whole feature as one lane. t1863's cross-linking pass
checks this table against the parents' real ids.

## Carried obligations (framework half)

- `## Goal` / "the `aitask-testmap-review` skill with its launch surfaces (`ait skillrun`, `ait codeagent`, `ait crew runner` — print mode an explicit opt-in on each)" — *Goal* and the M7.5 row of *Submodules*
- `## Goal` / "Invariant 4 binds: the engine never launches a code agent, never calls a model, never decides a verdict" — *Goal* (Invariant 4): launching lives in this task's skill and operation; the engine tripwire is aitasks_go#t64's
- `## Goal` / "This task carries the module's cut … and the planning protocol" — *Goal* and *Planning and implementation protocol* (M7.5's cut; the engine rows' cut is aitasks_go#t64's)
- `## Goal` **Acceptance:** / "the union of the module's components' test lists" — *Goal* (acceptance line) and *Acceptance*, first bullet
- `## Submodules` row M7.5 Review skill and launch surfaces (skill tree, `review.md`, `aitask_codeagent.sh` op, model-seed keys, goldens, `tests/test_codeagent.sh`, no-`claude -p` grep) — M7.5 row of *Submodules*
- `## Submodules` / "depends on" column (M2.3, M2.6, M6.2 / M6.3, M7.1 / M4.4, M5.2, M7.2 / M2.2, M2.3, M2.6, M4.1, M5.1 / M6.5, M7.1, M7.2 / M7.1, M7.2, M7.5) — M7.5 depends cell and *Wiring* (M7.5 ← M6.5 in-repo; ← M7.1, M7.2 via `xdeps`); M7.6 → M7.5 is aitasks_go#t64's `xdeps` onto this repository
- `## Submodules` / "wave" column (F, F, G, F, G, H) — M7.5 row (wave G) and the engine waves noted under *Submodules*
- **Provides** / "Bulk reading, attended and headless; the launch rule pinned by test — M7.5 → M9.5, M10.x" — *Cross-module seams* → Provides
- **Consumes** / "the onboarding skill tree (M6.5); existing framework surfaces `ait skillrun`, `aitask_codeagent.sh`, `aitask_crew_addwork.sh`, `lib/agent_string.sh`, the model seeds and `aitask-add-model`" — *Cross-module seams* → Consumes (skill tree, `ait skillrun`, `aitask_codeagent.sh`, model seeds, `aitask-add-model`)
- **Hooks** / "M7.5 owns `review.md` inside M6.5's skill tree and the `testmap-review` operation inside `aitask_codeagent.sh`" — *Cross-module seams* → Hooks
- **Hooks** / "The Step-8 in-gate site (M8.3 seeds step) and the Step-7 authoring site (M9.1) are consumers: M7 defines the packet, the intake and the skill, not the sites" — *Cross-module seams* → Hooks
- **Hooks** named follow-up / "a second-model cross-check of verdicts through `ait codeagent testmap-review --agent-string <other>` (M7.3)" — *Cross-module seams* → Hooks, named follow-ups (launch via this task's operation)
- **Hooks** named follow-up / "`agent_review.min_verified` as a floor on which models may write `--by` (M7.5)" — *Cross-module seams* → Hooks, named follow-ups (config / model-seed side)
- `## Reading list` (Module Map, Components, Agent Review Pass, Overview, Adoption Model, Data Flow, Assumptions/Tradeoffs) — *Reading list in the proposal*
- `## Reading list` / "Framework rules: `skill_authoring_conventions.md`, `stub-skill-pattern.md`, `agent_runtime_guards_audit.md`; the `claude -p` caveat in `shell_conventions.md`" — *Reading list in the proposal*, framework rules bullet
- Protocol §1 / "Plan this task … 'Yes, create child tasks' … one child task per submodule row … 'Stop here'" — *Planning and implementation protocol* §1, first bullet (one M7.5 child here)
- Protocol §1 / "Keep the coarse plan coarse … child plan must say so" — *Planning and implementation protocol* §1
- Protocol §1 / "Express cross-module order in task data … `depends:` … `aitask_update.sh --batch <child-id> --deps`" — *Planning and implementation protocol* §1 and *Wiring*
- Protocol §1 / "Parent-level `depends:` stays empty on purpose" — *Planning and implementation protocol* §1
- Protocol §1 / "Deviations … fixed in the proposal … Send a note to every parent whose tables the change touches" — *Planning and implementation protocol* §1, deviations bullet (aitasks_go#t64's deviations arrive here as notes)
- Protocol §2 steps 1–6 (re-read Module Map row; inspect actual provider state naming task+commit; tabulate proposal/coarse plan/repository; decide per difference; note downstream children; re-confirm file ownership) and / "A child whose plan lacks this step … is not implementing this task" — *Planning and implementation protocol* §2
- `## Module → task map` — *Module → task map* (both repositories; t1863 checks it)
- Inbox t1852 / "Sequencing clarification … implement its children in proposal wave order" — *Planning and implementation protocol* §1 (wave order)
- Inbox t1853 / "Automation-first … M7 candidates are `REVIEW_HUMAN` parking … and `drives` / `unsure` rows 'listed for a person'" — *Automation-first*: the skill decides how `drives` / `unsure` rows are listed
- Inbox t1853_7 / "consumes M7.2, M7.4 and M7.5 … resolve and add actual child dependencies during decomposition" — *Wiring*, t1853_7 bullet
- Inbox t1859 / "add both child ids [M7.1, M7.2] to t1859_6's depends and flip it from Postponed to Ready" — *Wiring*, t1859_6 bullet
- Inbox t1859 / "t1853_7 … first-stamp routes include M7.2 verdict adoption and M7.4 `annotate --author`" — *Wiring*, t1853_7 bullet (first-stamp routes M7.2 / M7.4)
- Inbox aitasks_go#t15 (cutover notice, keep engine/framework commits separate, record outside-goengines data paths) — The freeze is over; the engine rows live in aitasks_go#t64 (header above)

## Relocated to aitasks_go

The engine scope below moved to aitasks_go#t64 and is quoted for reference only.

> - aitasks_go#t64 owns the engine rows M7.1 (packet writer `onboard review [--next N] [--class] [--scope] [--ids] [--json] [--out <dir>]`, memo skip via `AdoptionOf(reg).NeedsReview`, packet line protocol, per-language assertion flagging, `packet_lines` ceiling, `packet_sha`, per-language fixture repos), M7.2 (verdict intake `onboard adopt --agent-verdicts - --by --run`, `VERDICT_INVALID`/`VERDICT_STALE`, verifies/drives/unsure writes, parking, `REVIEW_HUMAN`, `reviews[]`, `REVIEW_APPLIED:`/`REVIEW_PARKED:`/`REVIEW_HUMAN:` via `OpenAdoption(..., RouteAdoptAgentVerdicts)` + `RecordVerdict`), M7.3 (calibration `--calibrate <n>`, `REVIEW_AGREEMENT:`, `measured_confidence`, `REVIEW_ORIGIN_DEMOTED`, `calibration[]`, `AGENT_REVIEW:` brief line, `CALIBRATION:`/`REVIEW_AGREEMENT:` readiness lines), M7.4 (`annotate --author` arm, change-surface and unregistered refusals, `adopted.yaml` row origin `agent:author`, `AUTHOR_STAMPED:`/`AUTHOR_UNCORROBORATED:`, `agent_review.author`, explicit refusal on `ErrNoLeader`/`ErrUncertainContext`/`ErrByteOrderMark`), M7.6 (`--crew <id>` / `--collect <crew-id>` arms, printed `ait crew runner` line, fixture crew test).
> - Its own coarse pass decomposes those five rows (one child each, M-id in the name, Reality-check step mandated) and runs the per-child reality check.
> - It honours Invariant 4 (engine never launches an agent, never calls a model, never decides a verdict) and Invariants 3/7.
> - Acceptance checks:
>   - the union of the M7.1/M7.2/M7.3/M7.4/M7.6 component test lists (proposal *Module Map — How to read it*), green in `ait engine test` / private CI;
>   - Invariant 4-5 tripwire still green (no agent launch, no model call from the engine);
>   - `annotate --author` refuses explicitly (not silently) on the three annot errors (t1954_4 note);
>   - packet eligibility uses `NeedsReview`, never `reviews[]` alone (t1853_6 note);
>   - M7.6 never launches an agent raw — only registers via `aitask_crew_addwork.sh` and prints the runner line.


## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1852** id=2026-09-22T14:31:39Z.c635747c878744c8cd8a8d7a from=t1852 at=2026-09-22T14:31:39Z base=d0836b4f1750fde12e5e30260cd0d34396793a17 base_branch=main dirty=yes host=omg16
>
> | **Sequencing clarification (advisory, from the t1852 coarse pass, 2026-09-22).** The user asked that M1's children be *implemented* before M2 (t1853) is *planned*. Read the "plan all ten parents before implementing any child" paragraph in this task's body as an upper bound on how far planning may run ahead, not a requirement to plan against providers that do not exist. The rule is submodule-granular, never whole-parent (module-level deps form a cycle: M6.5 -> M8.2/M8.4, M8.3 -> M7.1/M7.2, M7.1 -> M6.2): start this parent's coarse pass once the specific provider submodules its wave-earliest children consume have landed in the tree, and implement its children in proposal wave order. A standalone cross-linking chore task (created from t1852's pass, followup_kind risk_mitigation) checks every "depends on" cell against real depends entries once all ten parents are decomposed; it accepts archived children as evidence and never rewrites M10.2-M10.5 (cross-repo).
> | 
> | **Go source layout (proposal fix, commit 07a546087 on main).** The engine source directory is `goengines/`, not `engine/`: one Go module (`github.com/beyondeye/aitasks/goengines`) for every distributable Go executable, `goengines/cmd/ait-testmap/`, shared packages `goengines/internal/{gitx,platform,lineproto}`, and every testmap-specific package under `goengines/internal/testmap/<pkg>`. Wherever the proposal (and this task's owns cells) write `internal/<pkg>`, read `goengines/internal/testmap/<pkg>`. Unchanged: the binary name `ait-testmap`, `$AITASKS_HOME/engine/v<V>/`, the `ait engine` verbs. CI workflow is `goengines-check.yml`; the release job is `goengines`. M1.2 (t1852_2) creates the module root; each later submodule adds only its own package and replaces only its own stub verb.

> **✉ note:t1853** id=2026-10-11T14:44:06Z.f8b748e02ccb8c8de7cc792c from=t1853 at=2026-10-11T14:44:06Z base=3bc0de8ac7a9c9d1f60173e1257715a744efc451 base_branch=main dirty=yes host=omg16
>
> | Advisory, from the t1853 (M2) coarse pass (proposal commit 3bc0de8ac).
> | 
> | **Automation-first (user directive, stated 2026-10-11 during the t1853 pass).** Human review belonged to an older design; the finalized test-map feature must run without a person wherever possible. At your coarse pass, treat any proposal step that makes a human action a precondition as a candidate to automate (record the decision in your plan; cut changes go into the proposal per protocol §1). From my reading, M7 candidates are `REVIEW_HUMAN` parking (two `unsure` verdicts → a person) and `drives` / `unsure` rows "listed for a person". Not verified against your module's full text. Note also: M2.6 applies the re-stamp provenance rule by actor (automated re-stamps keep `by:`).

> **✉ note:t1853_7** id=2026-10-12T05:56:01Z.f0a98e0ce139937920532c57 from=t1853_7 at=2026-10-12T05:56:01Z base=8395bc6c68f1b977f83470466b549547d4b1ec58 base_branch=main dirty=no host=omg16
>
> | Advisory cross-reference: the user requested full automatic test-map repair for adoption of existing codebases. Created [t1853_7](t1853/t1853_7_automate_testmap_repair_for_existing_codebases.md) for the check → repair → recheck loop, including missing annotations and invalid ownership.
> | 
> | The new sibling consumes M7.2, M7.4 and M7.5 for evidence-based annotation/adoption and agent review. Legacy backfill must use the onboarding/review path while preserving the author annotation change-surface boundary. Base providers must not depend back on the coordinator.
> | 
> | As of this moment, the consumer is Postponed pending real provider child IDs. Its dependency table names this parent's required modules; resolve and add actual child dependencies during decomposition, preserving current edges. t1863 explicitly audits this supplementary consumer and its hold in addition to the original module rows.

> **✉ note:t1853_2** id=2026-10-12T14:31:19Z.671b6d227628e536bac5ee48 from=t1853_2 from_verified=yes at=2026-10-12T14:31:19Z base=7229dee868985aafae8cd16e493614d1904311b5 base_branch=main dirty=no host=omg16
>
> | For M7.2 / M7.4: M2.2 landed in f096db065 (contract in the proposal at 7229dee86). Advisory, as of that tree.
> | 
> | - `annotate --author` is an arm: register it in `annotateArms` (goengines/cmd/ait-testmap/annotate.go). Until then it prints NOT_IMPLEMENTED:annotate --author, exit 64.
> | - M2.2's annotate / verify already take `--by human:<email>|agent:<s>|auto` (default agent:$AIT_AGENT_STRING, else unspecified). Reuse annot.ParseActor; M7.4's agent-string-only rule for --author is yours to add.
> | - Write stamps through annot.PlanCovers + annot.Apply (comment lines only; one file atomically). annot.RegisterRestampHook is the hook M2.6 fills with the actor.
> | 
> | No human-only step was met.

> **✉ note:t1853_3** id=2026-10-13T12:53:03Z.ef25bf06693dda0d6c2ffb11 from=t1853_3 from_verified=yes at=2026-10-13T12:53:03Z base=2c04a9639cc377ce62858e5af12bbc3a0f76412b base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1853_3 (M2.3 dependency scanners), as landed in 2c04a9639. Claims about that tree; verify before relying.
> | 
> | For M7.1 / M7.4:
> | - Packets: `Graph.Facts(path).Symbols` (declared functions, verbs and tokens; Python top-level defs and classes; Go exported symbols; Kotlin top-level declarations), and anchor lines on `Static()` deps.
> | - Corroboration: `Graph.Closure(test, 0)` (unbounded) gives reachability. Closure-only edges count for reachability but are never seeds.
> | - The `--author` arm can register the way M2.3's arms do: `cmd/ait-testmap/annotate_deps.go` adds `annotateArms["--suggest"]` / `["--from-body"]` from an `init()`.
> | - Stamp inferred sources through `annot.AnnotateWith(ctx, root, test, sources, actor, annot.AnnotateOptions{Origin, Snapshot})`:
> |   - `Origin` reaches the hook as `Restamp.Origin` (`--from-body` uses `scanner:from-body`).
> |   - `Snapshot` is the snapshot of the reading you inferred from; `Apply` re-checks it, and `--from-body` re-infers once on a conflict.
> | - No human-only step was needed in M2.3.

> **✉ note:t1954_4** id=2026-10-14T18:37:20Z.586b656df44bda0fc1e1909e from=t1954_4 from_verified=yes at=2026-10-14T18:37:20Z base=f8d4b2ef54e729ae6e7ee76c1ba3f63395660f14 base_branch=main dirty=yes host=omg16
>
> | t1954 (multi-language annotation parsers) is complete. Report: aidocs/testing_engine/t1954_annotation_parser_research.md (sections 11 and 12). Verdict for M7: action (one check).
> | - annotate --author (M7.4) writes through annot.PlanCovers + annot.Apply. That path is unchanged.
> | - The check: it must refuse explicitly when annot returns ErrNoLeader (unsupported language), ErrUncertainContext (the lexer cannot prove the file) or ErrByteOrderMark (a BOM with no slot, t1969). A silent success or an empty result is not acceptable.
> | - Advisory order: t1991, the hermetic annot conformance suite from the t1954 corpus, should land before M7.4 edits annot, so that a reader regression fails go test.

> **✉ note:t1853_6** id=2026-10-19T09:18:12Z.d6836dcdcfdde7d585c2588e from=t1853_6 from_verified=yes at=2026-10-19T09:18:12Z base=093d98a197a65931bdd6f104d4a919f965dfc0ee base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1853_6 (M2.6 adoption tables). It describes the tree as of aaeb10b0f, so verify it in your reality check. M7's children are not decomposed yet, so this note goes to the parent.
> | 
> | - **`onboard adopt --agent-verdicts` (M7.2).** Use `OpenAdoption(ctx, root, registry.RouteAdoptAgentVerdicts)` and call `RecordVerdict(VerdictRecord{Test, Covers, Review: SeedReview{Verdict, By, Run, PacketSHA, TestBlob, …}, Adopt: *AdoptedRow})` per pair.
> |   - The low-level ops are refused on this route.
> |   - The replay data (`by`, `run`, `packet_sha`, `test_blob`) is required, else `ADOPTION_ROUTE:…|replay-data`.
> |   - A `verifies` adoption's `AdoptedRow` must carry the same four fields.
> |   - Stamp the test file first through `annot.AnnotateWith`.
> | - **Packet selector (M7.1).** It MUST judge eligibility with `AdoptionOf(reg).NeedsReview(test, covers, testBlob, reader)` (or `Reviews()`), never with `reviews[]` alone. The memo is `reviews[]` ∪ the records carried by a seed's `evidence.agent_review` and a `verifies` adoption's row, so a failed memo write never re-hides or re-selects a pair. Every route also preserves an unrecorded record before it destroys the carrier. Until the memo catches up, `check` prints `REVIEW_UNRECORDED`.
> | - **Schema.** `SeedReview.assert_line` is an int.
> | - **`annotate --author` (M7.4).** Going through `AnnotateWith` with `AnnotateOptions{Origin: "agent:author"}` and an agent actor, the intent hook creates the adopted row for a first stamp, with origin `[agent:author]`, `by`, `adopted_at` and `stamp`. Enrich it (confidence 0.90, task, run) with `PutAdopted` on `RouteAnnotateAuthor`. An already-stamped pair gets no row from the hook, so `--author` must `PutAdopted` it explicitly.

> **✉ note:t1859** id=2026-10-19T12:47:11Z.65740348a9db83d09987ae8f from=t1859 at=2026-10-19T12:47:11Z base=bf32b336c0b0673eccba125bf097df173405e8d7 base_branch=main dirty=yes host=omg16
>
> | Advisory, from the t1859 (M8) coarse pass. Proposal fix: commit bf32b336c.
> | 
> | The seeds step of the testmap_fresh gate is a separate child, t1859_6 (wave G). It waits on M7.1 (packets, `onboard review --ids`) and M7.2 (`onboard adopt --agent-verdicts`). At your coarse pass, add both child ids to t1859_6's depends and flip it from Postponed to Ready.
> | 
> | Also, t1853_7 is now the repair coordinator for UNSTAMPED past bootstrap. Its first-stamp routes include M7.2 verdict adoption and M7.4 `annotate --author`. Tree claims; verify them at your pass.

> **✉ note:t15** id=2026-10-25T08:53:56Z.dd716918fa1144daf467d0f8 from=aitasks_go#t15 at=2026-10-25T08:53:56Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
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

> **✉ note:t22_3** id=2026-10-29T22:22:49Z.48a9444781248d53224db19a from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:22:49Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:11:38Z.638964069cf02924d4dedbf0 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:11:38Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | Split: the engine half of this task is aitasks_go#t64. This task's body
> | was trimmed to the framework half (the removed scope is quoted under
> | "Relocated to aitasks_go").
