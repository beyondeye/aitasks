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

> **✉ note:t1853** id=2026-10-11T14:44:14Z.e49235bb90ae3a2e5eb58ae0 from=t1853 at=2026-10-11T14:44:14Z base=3bc0de8ac7a9c9d1f60173e1257715a744efc451 base_branch=main dirty=yes host=omg16
>
> | Advisory, from the t1853 (M2) coarse pass (proposal commit 3bc0de8ac).
> | 
> | **Automation-first (user directive, stated 2026-10-11 during the t1853 pass).** Human review belonged to an older design; the finalized test-map feature must run without a person wherever possible. At your coarse pass, treat any proposal step that makes a human action a precondition as a candidate to automate (record the decision in your plan; cut changes go into the proposal per protocol §1).

> **✉ note:t1853_2** id=2026-10-12T14:31:21Z.a276832bc01bdf5937902e59 from=t1853_2 from_verified=yes at=2026-10-12T14:31:21Z base=7229dee868985aafae8cd16e493614d1904311b5 base_branch=main dirty=no host=omg16
>
> | For M10.1 (aitasks onboarding): M2.2's annotation source landed in f096db065 (contract in the proposal at 7229dee86). Advisory, as of that tree; the probe numbers below are a moment-relative reading.
> | 
> | - annot.Source reads the git-visible files (`git ls-files --cached --others --exclude-standard`) minus `exclude:`. So the ignored aiwork/, .aitask-crews/ and website/node_modules/ are never read.
> | - Annotations are read only on lexically proven comment lines. testmap-shaped text in heredocs, strings and raw strings — e.g. goengines' own Go test fixtures and bash heredoc fixtures — is ignored, so no `exclude:` is needed for it.
> | - Every Python file is parsed (its docstring value can spell the token). A file the lexer cannot close (an unterminated string, heredoc or raw string) and that may carry an annotation fails the scan with INPUT_ERROR:annotations.
> | - Probe over this repository on 2026-10-12: 1,345 known-language files, 0 lexically uncertain, 0 annotated, Source succeeds in ~130 ms. Comment lines match tokenize/ast for Python (631 files) and shfmt for bash (647 files).
> | 
> | No human-only step was met.

> **✉ note:t1854** id=2026-10-13T16:21:26Z.e8b664e6ff9303e7f0aadace from=t1854 at=2026-10-13T16:21:26Z base=6a3a81efc30577c762d42f815f3e95eac95b4e3f base_branch=main dirty=no host=omg16
>
> | Advisory, from the t1854 (M3) coarse pass (proposal at 6a3a81efc). This is a tree claim; verify it at your pass.
> | 
> | **Dev 6: the serial carve-out pin moved to M10.1.** The proposal had M3.2 own "the serial carve-out pin in `tests/test_serial_carveout_doc_drift.sh`". That check asserts the `testmap:batch no` annotations agree with `SERIAL_CARVE_OUT` in `tests/run_all_python_tests.sh`. No such annotation exists before M10.1, which writes them, so a wave-B pin would be vacuous.
> | 
> | The M10.1 row now owns the agreement check, extending `tests/test_serial_carveout_doc_drift.sh`, alongside the four annotations. M3.2 (t1854_2) keeps only the `pytest` builtin's honouring of `testmap:batch no`, with its own Go tests.
> | 
> | Also for M10.4 / M10.5:
> | - the `device` builtin reads the allocator handle from M3.1's manifest field, which M3.3 fills;
> | - `bash-file list --invocations` was removed from the proposal. The seeder reads M2.3's bash facts directly.

> **✉ note:t1954_4** id=2026-10-14T18:37:29Z.4b75f2523ab0ce423a65a13c from=t1954_4 from_verified=yes at=2026-10-14T18:37:29Z base=f8d4b2ef54e729ae6e7ee76c1ba3f63395660f14 base_branch=main dirty=yes host=omg16
>
> | t1954 (multi-language annotation parsers) is complete. Report: aidocs/testing_engine/t1954_annotation_parser_research.md (sections 7 and 12). Verdict for M10: context plus a suggestion.
> | - All five targets use only the supported languages: bash, Python, Go and Kotlin. aitasks_mobile's 2 Swift files are app sources.
> | - On 2026-10-14 snapshots of the six registered repositories, the landed readers were never uncertain. No candidate parser differed from them in any annotation record (7,866 files; results/t4/realrepo_totals.md).
> | - Suggestion: at rollout, rerun the read-only realrepo walk for the target at the then-current annot. The research harness in aidocs/testing_engine/t1954_parser_research/ does this on a checkout of a recorded commit; see its README.
> | - Kotlin targets (M10.4 aitasks_mobile, M10.5 thinking_app): until t1990 lands, check that the target has no Kotlin 2.2 multi-dollar strings (`git grep -E '\$\$+"' -- '*.kt' '*.kts'`). There were none on 2026-10-14.

> **✉ note:t1992** id=2026-10-15T22:35:47Z.32dcb7c76a121eb35a5db0ad from=t1992 from_verified=yes at=2026-10-15T22:35:47Z base=25b145da77a96b402c146b89a340243a6d0a3440 base_branch=main dirty=no host=omg16
>
> | Advisory context from t1992 (Kotlin-family lexer evaluation), for M10's Kotlin targets (M10.4 aitasks_mobile, M10.5 thinking_app). Tree-relative claims are dated by this note's base commit.
> | 
> | - The t1954_4 rollout check "until t1990 lands, grep Kotlin targets for multi-dollar strings" no longer guards annot. t1990 landed (cf210a9e9): annot now models `$$"…"`. The two deps lexers still fail closed on them (the file is opaque, or its module widens). That is the safe direction, so a hit is a precision cost, not a safety one.
> | - New check, until t2030 lands: a Kotlin file whose first line is a `#!` shebang that holds `{` or `(` silently loses its dependencies in deps.
> |   - Measured through `scanKotlin` at 2874e66ea: `Package=""`, `Decls=[]`, no opaque reason, no error.
> |   - A shebang holding `/*` makes annot refuse the file. When the file carries `testmap:`, that is a whole-scan SyntaxError.
> |   - deps routes `.kt` and non-Gradle `.kts` (e.g. `*.main.kts`) through ktLex, so scripts are the exposed shape.
> |   - Check: `git ls-files '*.kt' '*.kts' | xargs head -qn1 | grep -c '^#!'`.
> | - Exposure in the snapshots t1992 walked on 2026-10-16 (commits recorded in t1992's plan): 0 of 2051 Kotlin files start with `#!`, and 0 contain `$$"`. That is a reading at those commits, not a standing fact about the live trees.
> | - Evidence and the full divergence table are in t1992's decision record (`aiplans/archived/p1992_kotlin_family_shared_lexical_core_evaluation.md` once archived). The guard is `goengines/internal/testmap/deps/kotlinfamily_test.go`.

> **✉ note:t1859** id=2026-10-19T12:47:15Z.c737e4c73e713d674497ae9c from=t1859 at=2026-10-19T12:47:15Z base=bf32b336c0b0673eccba125bf097df173405e8d7 base_branch=main dirty=yes host=omg16
>
> | Advisory, from the t1859 (M8) coarse pass. Proposal fix: commit bf32b336c.
> | 
> | Your M10 rows depend on M8.3 = t1859_3. The review loops of M10.1 and M10.3–M10.5 also rely on its seeds step, t1859_6.
> | 
> | Rollout prerequisite (Dev 14): a target that runs autonomous lanes under `require_stamp: true` past `bootstrap_until` needs t1853_7 (the automated repair coordinator) to have landed. Before then, UNSTAMPED edges fail testmap_fresh and testmap_check loudly and are never auto-repaired.
> | 
> | The cadence defaults per target (Open question 13) are M8.5's (t1859_5). Tree claims; verify them at your pass.

> **✉ note:t2030** id=2026-10-20T05:59:20Z.69c75f0dc05419832d51d3d0 from=t2030 from_verified=yes at=2026-10-20T05:59:20Z base=d0a790a91dfb10bfe76c99daafe0e7ac065226c7 base_branch=main dirty=yes host=omg16
>
> | t2030 has landed (code commit d0a790a91). This affects the rollout pre-check recorded in this task's inbox ("New check, until t2030 lands: …"):
> | - A leading Kotlin `#!` shebang no longer hides anything. ktLex, annot's classifyKotlin and the kts blanker now all skip it, matching Kotlin.flex's SHEBANG_COMMENT: offset 0, after an optional BOM, and only when a newline ends the line. The shebang pre-check for target repositories is no longer needed.
> | - New behaviour worth checking during the rollout instead: a Kotlin file that contains a lone CR (a `\r` not followed by `\n`) now fails closed. In deps it is opaque (`untokenizable`), and a `.gradle.kts` file is read unblanked and marked dynamic. In annot the file is Uncertain ("lone carriage return"), which is a whole-scan SyntaxError if the file carries `testmap:`. Exposure as of 2026-10-19: 0 of the 2051 tracked .kt/.kts files across the 8 registered repos (grep -lzP '\r(?!\n)').
> | - deps cache schemaVersion is now 14, so cached entries are rescanned once.

> **✉ note:t1854_2** id=2026-10-21T19:10:47Z.865aaaffe44d841a05bfb6cd from=t1854_2 from_verified=yes at=2026-10-21T19:10:47Z base=5582dd4f455372f5ba40a43b6d2dffe2101089b3 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1854_2 (the M3.2 re-decomposition, 2026-10-21). Ids are as of the commit this note records.
> | - M10.1 (aitasks) needs t1854_8 (bash-file) and t1854_9 (pytest); the serial carve-out pin is still yours (Dev 6).
> | - M10.4 (aitasks_mobile) needs t1854_11 (gradle-class) and t1854_13 (device). t1854_13 is **Postponed**: there is no emulator / adb environment, and it needs M3.3's allocator.
> | - An adapter counts as "supported" only for the real-tool configurations its integration tests cover (G10). The first real Gradle and device runs in a target repository are where fixture-versus-reality drift shows, so record it there.
> | - M10.5 (thinking_app) needs t1854_12 (suite aggregate) and t1854_14 (the reporting contract, for `verify-active` child rows).
> | Details: parent t1854, section "M3.2 re-decomposition (2026-10-21)".

> **✉ note:t15** id=2026-10-25T08:54:05Z.53836bf3715335f6131f8751 from=aitasks_go#t15 at=2026-10-25T08:54:05Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
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

> **✉ note:t1854_8** id=2026-10-25T12:30:49Z.d9530ae2d886e39cfd1b304b from=t1854_8 from_verified=yes at=2026-10-25T12:30:49Z base=c774eb540e034fdb097cf2d4d4e34a16b08a15a2 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1854_8 (M3.2e bash-file adapter), landed in e88923ecb. Verify against goengines/README.md ("bash-file builtin (M3.2e)") before relying on it.
> | 
> | - For the aitasks rollout (M10.1), bind the bash-file entry to `tests/test_*.sh`, not the adapter's default `**/test_*.sh`. The default also matches `tests/lib/test_scaffold.sh`, which is a helper, not a test (counted at main eb6baa4c9: 455 tests/test_*.sh, plus that one).
> | - The adapter runs `bash ./<cwd-relative path>` from the entry's cwd (default the root), so `$0` is `./tests/test_x.sh`. The aitasks `dirname "$0"` / `BASH_SOURCE` header shape was verified to work (TestBashFileAitasksShape).
> | - bash-file is registered on linux only (G10); on darwin `builtin: bash-file` is unresolved (pending).

> **✉ note:t1854_9** id=2026-10-26T08:06:16Z.b6f1d9fe22317fb4fa1bc00c from=t1854_9 from_verified=yes at=2026-10-26T08:06:16Z base=7f49dbd62e8c9ab5ae05de2935184d3bf72256d7 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1854_9 (M3.2f pytest adapter), as landed in 0c2f693c9. Verify against goengines/README.md before relying on it. Measurements below were on a `git archive HEAD` export of aitasks on 2026-10-25 and are dated by that, not by your tree.
> | - Bind the aitasks entry to `tests/test_*.py` (the default `**/test_*.py`, `**/*_test.py` would match test files outside tests/). Discovery: 378 files, 9901 case identities (identical to plain `pytest --collect-only -q`), 17-18 s per Load — every check/run pays it.
> | - A serial single invocation of the whole suite took >30 min and hit `batch_timeout_s: 1800` (all 378 units batch_timeout; nothing survived the kill). With `command: <venv python> -m pytest -n 4 --dist loadfile` and `batch_timeout_s: 3600` the run took 508 s: 378/378 units reconciled (9835 pass, 13 fail, 53 skip; the 13 failures reproduce under plain pytest in that export — missing task-data layout). So: use xdist (loadfile) or a batch timeout well above the serial runtime.
> | - Default command is `python3 -m pytest`; set `command:` where python3 on PATH lacks pytest. An interpreter run with -I / -E ignores PYTHONPATH, so the engine's evidence plugin cannot load and the list is refused.
> | - A module skipped at collection (pytest.skip(allow_module_level=True)) is one expected identity (its module node id) and reports skip with its reason, independent of zero_tests. A test that fails or passes and then errors or skips in teardown is error:duplicate_case.
> | - `# testmap:batch no` makes a file a singleton invocation (tested); the serial carve-out pin stays yours.

> **✉ note:t22_3** id=2026-10-29T22:23:12Z.cbb414738c2bcfcfd29342b9 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:23:12Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:15:52Z.a71e267ef9673a4c9ee37edf from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:15:52Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | goengines freeze lifted (aitasks_go#t22 cutover complete).
> | Public goengines/ is now an export target: never edit it here; changes
> | arrive from beyondeye/aitasks_go via promote/export.sh.
> | - This task has no engine part and stays here unchanged.
