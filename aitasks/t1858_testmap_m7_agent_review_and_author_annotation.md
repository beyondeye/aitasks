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
