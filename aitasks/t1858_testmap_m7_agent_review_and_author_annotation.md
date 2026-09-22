---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [testing, testmap, go_engine, skills, codeagent]
anchor: 1852
created_at: 2026-09-22 09:19
updated_at: 2026-09-22 09:19
---

## Goal

Part of the **testing engine / test map** feature — ten parent tasks, one per
module of the proposal. This is **M7 — Agent review and author annotation**:
the reading — packets out, verdicts in — plus the authoring agent's own
claims.

Static closure proves that a test *runs* a script, not that it *checks* it;
turning evidence into a claim needs a reader of the test body, and an agent
can be that reader. This module delivers the packet writer, the one verdict
intake all three reading sites share (*verifies* adopts, *drives* / *unsure*
parks, only a person's `reject` removes), calibration against a ground truth,
the authoring agent's `annotate --author`, the `aitask-testmap-review` skill
with its launch surfaces (`ait skillrun`, `ait codeagent`, `ait crew
runner` — print mode an explicit opt-in on each), and the crew form.
Invariant 4 binds: the engine never launches a code agent, never calls a
model, never decides a verdict.

This task carries the module's cut — submodules, owned files, the interfaces
it provides and consumes, the seams later modules land into it — and the
planning protocol. It does **not** restate the specification.

**Proposal (authoritative for every detail):**
`aidocs/testing_engine/n014_explorer_006_proposal.md` — start at the *Module
Map* entry `#### M7 — Agent review and author annotation`, then the
*Components* subsections tagged `(M7.x)` (listed under *Reading list* below),
then the narrative sections those components name. *Architecture*, *Design
decisions* and the *Invariants every module honours* apply to every module.

**Acceptance:** the union of the module's components' test lists (*Module Map —
How to read it*).

## Submodules (one child task each — settled at the coarse planning pass)

| submodule | scope | depends on | wave |
|---|---|---|---|
| **M7.1** Packet writer | `onboard review [--next N] [--class] [--scope] [--ids] [--json] [--out <dir>]`, the memo skip, grouping by test file, the packet line protocol with assertion flagging per language and the `packet_lines` ceiling, `packet_sha`. Owns `internal/onboard/review.go` (writer), fixture repos per language for packet shape | M2.3, M2.6, M6.2 | F |
| **M7.2** Verdict intake | `onboard adopt --agent-verdicts - --by <agent-string> --run <id>`, every validation (`VERDICT_INVALID` reasons, `VERDICT_STALE`, the `--by` grammar through `lib/agent_string.sh`), the writes for `verifies` / `drives` / `unsure`, parking, `REVIEW_HUMAN`, `reviews[]`, `REVIEW_APPLIED:` / `REVIEW_PARKED:` / `REVIEW_HUMAN:`. Owns `internal/onboard/review.go` (intake) | M6.3, M7.1 | F |
| **M7.3** Calibration and agreement | `onboard review --calibrate <n>`, `REVIEW_AGREEMENT:`, `agent_review.measured_confidence`, `REVIEW_ORIGIN_DEMOTED`, `calibration[]`; the `AGENT_REVIEW:` brief line and the `CALIBRATION:` / `REVIEW_AGREEMENT:` readiness lines. Owns the calibration paths in `review.go` and the additive lines in `brief` and `readiness` | M4.4, M5.2, M7.2 | G |
| **M7.4** Author annotation | `ait testmap annotate --author <test> <source>... [--task] [--by]`, the change-surface refusal, the unregistered refusal, the `adopted.yaml` row with origin `agent:author`, `AUTHOR_STAMPED:` / `AUTHOR_UNCORROBORATED:`, `agent_review.author`. Owns the `--author` arm in `internal/annot` | M2.2, M2.3, M2.6, M4.1, M5.1 | F |
| **M7.5** Review skill and launch surfaces | the `aitask-testmap-review` stub + `SKILL.md.j2` + `review-batch.md` (the verifies-or-drives rule stated once), the onboarding skill's `review.md` sub-phase invoking it, `ait skillrun testmap-review`, the `testmap-review` operation in `aitask_codeagent.sh` (interactive by default, `--print` only under `--headless`), `verified.testmap-review` in the three model seeds and `aitask-add-model`, goldens, the `tests/test_codeagent.sh` pin, the no-`claude -p` grep test. Owns `.claude/skills/aitask-testmap-review/**`, `review.md` under the onboarding skill, the `aitask_codeagent.sh` operation, the model-seed keys, `tests/golden/skills/aitask-testmap-review/` | M6.5, M7.1, M7.2 | G |
| **M7.6** Crew form | `onboard review --out <dir> --crew <id>` registering one reviewer per packet file through `aitask_crew_addwork.sh --type testmap-review --work2do review-batch.md`, the printed `ait crew runner` line, `onboard review --collect <crew-id>`. Owns the `--crew` / `--collect` arms in `review.go`, a fixture crew test | M7.1, M7.2, M7.5 | H |

## Cross-module seams

**Provides** (defined here, consumed elsewhere):

- Review packets and the verdict grammar — M7.1, M7.2 → M6.5 (`review.md`),
  M7.5, M7.6, M8.3 (the seeds step).
- The one verdict intake all three reading sites share — M7.2 → the
  `testmap_fresh` in-gate step (M8.3), the pre-review Affected Tests procedure
  (M9.1), the bulk skill (M7.5).
- The measured number that replaces the prior — M7.3.
- `annotate --author` and the `AUTHOR_*` lines — M7.4 → M9.1 (the autonomous
  branch), M9.3.
- Bulk reading, attended and headless; the launch rule pinned by test — M7.5 →
  M9.5 (ports), M10.x.
- A parallel pass — M7.6.

**Consumes:** the rewriter and the stamp format (M2.2); scanner facts (M2.3);
the adoption tables (M2.6); the ranked list and the change-surface parse
(M4.1); `readiness` (M4.4); `ait test` (M5.1) and the brief (M5.2); seeded rows
(M6.2); the adoption transitions (M6.3); the onboarding skill tree (M6.5);
existing framework surfaces `ait skillrun`, `aitask_codeagent.sh`,
`aitask_crew_addwork.sh`, `lib/agent_string.sh`, the model seeds and
`aitask-add-model`.

**Hooks and extensions** (a file has one owner; a later submodule lands its
edit as the owner's named extension):

- M7.4 lands `--author` in `internal/annot`, owned by **M2.2**, as its named
  extension.
- M7.3's `AGENT_REVIEW:` (brief, **M5.2**) and `CALIBRATION:` /
  `REVIEW_AGREEMENT:` (readiness, **M4.4**) are additive lines on protocols
  owned elsewhere.
- M7.5 owns `review.md` inside **M6.5**'s skill tree and the `testmap-review`
  operation inside `aitask_codeagent.sh`; M7.6 registers work through
  `aitask_crew_addwork.sh` and never a raw agent launch.
- M7.2 reuses **M6.3**'s rewriter path and provenance row; it never forks
  them.
- The Step-8 in-gate site (**M8.3** seeds step) and the Step-7 authoring site
  (**M9.1**) are consumers: M7 defines the packet, the intake and the skill,
  not the sites.
- Invariants 3 and 4 bind; the calibration, `--by` provenance and
  `adopted(… by <who>)` display (invariant 7) are how an adopted row never
  pretends to be a human review.
- Named follow-ups (not v1): a second-model cross-check of verdicts through
  `ait codeagent testmap-review --agent-string <other>` (M7.3);
  `agent_review.min_verified` as a floor on which models may write `--by`
  (M7.5); `--source-lines <n>` in the packet (M7.1).

## Reading list in the proposal

- *Module Map* — `#### M7`, *How to read it*, *Cross-module interfaces*,
  *Suggested implementation order* (waves F, G, H).
- *Components* — *Agent review verbs (M7.1 / M7.2 / M7.3 / M7.6)*, *Agent
  review pass (M7.5)*, *Author annotation (M7.4)*, *Adoption ledger (M7.2
  verdict transitions)*, *Annotation scanner and rewriter (`--author`)*,
  *Skills (the review skill)*.
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
