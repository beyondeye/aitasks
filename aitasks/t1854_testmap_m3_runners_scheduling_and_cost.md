---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [testing, testmap, go_engine]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1854_14]
anchor: 1852
created_at: 2026-09-22 09:19
updated_at: 2026-10-30 12:09
---

Split (aitasks_go#t22 cutover): the engine half of this task is aitasks_go#t60
in beyondeye/aitasks_go. This body is the framework half.

## Goal

Part of the **testing engine / test map** feature — ten parent tasks, one per
module of the proposal. This is the framework-side tracker of **M3 —
Runners, scheduling and cost**: everything that executes a test and records
what it cost.

All remaining M3 work is engine work, and since the t22 cutover engine
development lives in beyondeye/aitasks_go. The engine-side M3 parent is
aitasks_go#t60, with the children aitasks_go#t60_1 (M3.3 scheduler), aitasks_go#t60_2
(M3.2g `go-test` / `engine-test`), aitasks_go#t60_3 (M3.2h `gradle-class`),
aitasks_go#t60_4 (M3.2j `device`, Postponed) and aitasks_go#t60_5 (the engine half of
M3.2k, the suite reporting contract). Public `goengines/` is an export target
only; never edit it here.

This task keeps the framework side of M3:
- the n014 proposal's M3 cut
  (`aidocs/testing_engine/n014_explorer_006_proposal.md`, *Module Map* entry
  `#### M3 — Runners, scheduling and cost` and the `(M3.x)` components). The
  proposal stays here and is authoritative for both halves. Every proposal
  correction an aitasks_go child's Reality check decides on (protocol §2,
  step 4) arrives here by note and is applied or rejected here;
- the module → task map below;
- task-data cross-linking inside aitasks;
- one framework child, t1854_14, rescoped to the proposal conformance edit
  for M3.2k (the *Reference runners (M3.2)* paragraph on `full: true` suite
  child evidence, and Open Question 8).

## Acceptance

- This body points to aitasks_go#t60 (done above).
- The framework half of t1854_14 is archived.
- Every proposal revision an aitasks_go child requested via
  `./ait note --project aitasks` is applied, or rejected with a reason
  recorded in this task's plan.
- This task is archived only after aitasks_go#t60 is archived (closure rule). The
  order is encoded: t1854_14 holds `xdeps` on aitasks_go#t60
  (`xdeprepo: aitasks_go`), which unblocks only when aitasks_go#t60 is Done, and this parent
  archives automatically with its last child.

## Proposal cut history

The M3 cut was corrected at the coarse pass — proposal commit `6a3a81efc`;
the rationale is the *Deviations* section of
`aiplans/p1854_testmap_m3_runners_scheduling_and_cost.md`. This is a
historical record; nothing is pending.

**Automation-first (user directive, 2026-10-11).** The two human-flavoured
steps next to M3 (trusting `concurrency` after reviewing the schedule report;
confirming `runners.yaml` per runner) belong to onboarding (M6, t1857), which
is asked to automate them. No M3 verb makes a human action a precondition;
that engine rule is carried by aitasks_go#t60.

**Serial carve-out.** The `pytest` runner honours `testmap:batch no` (landed
in t1854_9). The aitasks carve-out annotations and the agreement check in
`tests/test_serial_carveout_doc_drift.sh` are **M10.1**'s, owned by t1861.

## Reading list in the proposal

Maintained here; the aitasks_go children read the same sections.

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

This feature spans **ten parent tasks**, one per module of the proposal (see
the module → task map at the end), and since the t22 cutover two
repositories: engine work in beyondeye/aitasks_go, framework work here.

### 1. Coarse planning pass

- The coarse pass for M3 is done (M3.1–M3.4, then the 2026-10-21 M3.2
  re-decomposition into M3.2a–k, at the user's direction). Keep the coarse
  plan coarse: a child's plan records scope, owned files, interfaces and
  acceptance, and leaves internals to the Reality check.
- Express cross-module order in task data, not in prose. Inside this
  repository a child's `depends:` names the child ids it consumes
  (`./.aitask-scripts/aitask_update.sh --batch <child-id> --deps ...`, which
  replaces the whole list). A provider in aitasks_go is held through `xdeps`
  (`--xdeps ... --xdeprepo aitasks_go`), which unblocks only when the target
  is Done. Never add `depends` on a Postponed pointer original; link the
  aitasks_go replacement instead. One cross-linking pass (t1863) checks every
  "depends on" cell against a real edge, across both repositories.
- Parent-level `depends:` stays empty on purpose, here and in aitasks_go#t60:
  module-level dependencies form a cycle (M6.5 → M8.2 / M8.4, M8.3 → M7.1 /
  M7.2, M7.1 → M6.2) and would block wrongly; the real graph is acyclic only
  at submodule granularity.
- Deviations from the proposal found while planning go into a **"Deviations
  from the proposal"** section of the plan. A wrong cut — a file two
  submodules must own, a dependency the wave table contradicts — is fixed
  **in the proposal**, not patched in a plan; that is the proposal's own
  falsifier (`assumption_modules_map_to_parent_tasks`). Send a note
  (`/aitask-note`) to every parent whose tables the change touches, in either
  repository.

### 2. Reality check at child implementation time

Every child's plan, in either repository, carries a recorded "Reality check"
step before any code (the full six steps are in aitasks_go#t60). Two of its steps
reach this repository:

- **Step 4 (decide).** Per difference: adapt the child to reality; or revise
  its coarse plan; or revise the proposal. A proposal revision from an
  aitasks_go child arrives here by note and is applied here (cut errors and
  interface changes go into the proposal, per §1), or rejected with a reason.
- **Step 5 (notify).** The child sends a note to every downstream child whose
  assumptions a difference or a decision breaks, hedging what cannot be
  proven from the tree. Cross-repo notes use `--project`.

## Module → task map

| module | parent task (aitasks) | engine parent (aitasks_go) |
|---|---|---|
| M1 — Engine foundation and distribution | t1852 (archived) | — |
| M2 — Registry and map model | t1853 | aitasks_go#t59 |
| M3 — Runners, scheduling and cost | t1854 | aitasks_go#t60 |
| M4 — Selection, freshness and feedback | t1855 | aitasks_go#t61 |
| M5 — Run surface | t1856 | aitasks_go#t62 |
| M6 — Onboarding | t1857 | aitasks_go#t63 |
| M7 — Agent review and author annotation | t1858 | aitasks_go#t64 |
| M8 — Completion policy and gates | t1859 | aitasks_go#t65 |
| M9 — Workflow integration, skills and documentation | t1860 | — |
| M10 — Rollout to the target repositories | t1861 | — |

All ten share the topic anchor of the M1 task, so the board's By-Topic view
shows the whole feature as one lane.

## Cross-linking inside aitasks

- The M3.2 re-decomposition re-pointed t1859_4 (M8.4): it depends on t1854_12
  and t1854_7 (both archived), where it used to depend on t1854_2. That edge
  is task data on t1859_4; nothing more to do here.
- The serial carve-out drift pin is M10.1's (t1861), unchanged (Dev 6).
- The sequencing clarification from t1852 still holds: planning is
  submodule-granular, never whole-parent; the cross-linking chore (t1863)
  accepts archived children as evidence and never rewrites M10.2–M10.5
  (cross-repo).
- The t1853 note's M2.4 → M3.1 edge was applied to t1853_4, now archived.

## Closure rule

M3 closes only when every M3.2 sibling is archived. The remaining siblings
live in aitasks_go under aitasks_go#t60; the Postponed device adapter
(aitasks_go#t60_4) keeps M3 open until an emulator environment exists; that is
the honest state. This task closes after aitasks_go#t60. The deferred tasks
aitasks_go#t74, aitasks_go#t75 and aitasks_go#t76 do not hold M3 open.

## Carried obligations (framework half)

- Goal / "Proposal (authoritative for every detail): `aidocs/testing_engine/n014_explorer_006_proposal.md`" — *Goal*: this task owns the spec's M3 cut; aitasks_go#t60 reads it across repositories.
- Submodules / M3.2 row "Re-decomposed … into M3.2a–k" — *Goal*: the engine adapters are aitasks_go#t60's children; the proposal edit is t1854_14.
- Hooks / "The cut was corrected … proposal commit `6a3a81efc`; rationale in *Deviations* of `aiplans/p1854_…`" — *Proposal cut history*; nothing pending.
- Hooks / "`pytest` runner honours `testmap:batch no`; carve-out annotations and `tests/test_serial_carveout_doc_drift.sh` are M10.1's" — *Proposal cut history → Serial carve-out*: the drift test stays with t1861; the honouring landed (t1854_9).
- Automation-first / "two human-flavoured steps … belong to onboarding (M6)" — *Proposal cut history → Automation-first*: owned by t1857.
- Reading list — *Reading list in the proposal*, maintained here.
- Protocol §1 / "coarse planning pass … one child per submodule row … Stop here" — *Protocol §1*, first item: done.
- Protocol §1 / "Keep the coarse plan coarse" — *Protocol §1*, first item: done.
- Protocol §1 / "Express cross-module order in task data … one cross-linking pass" — *Protocol §1*, second item: cross-linking stays here; cross-repo edges are `xdeps` / pointers.
- Protocol §1 / "Parent-level `depends:` stays empty on purpose" — *Protocol §1*, third item; this task keeps `depends: []`.
- Protocol §1 / "Deviations … wrong cut fixed in the proposal … send a note to every parent" — *Protocol §1*, last item.
- Protocol §2 / step 4 "adapt …; or revise this child's coarse plan; or revise the proposal" — *Protocol §2 → Step 4*: proposal revisions land here.
- Protocol §2 / step 5 "Sends a note to every downstream child …" — *Protocol §2 → Step 5*: cross-repo notes via `--project`.
- Module → task map — *Module → task map*, with the aitasks_go engine-parent column.
- Siblings / t1854_14 "M3.2k suite reporting contract" — *Goal*: t1854_14 keeps the proposal half; the engine half is aitasks_go#t60_5.
- Also re-pointed / "t1859_4 (M8.4) depends on t1854_12 + t1854_7" — *Cross-linking inside aitasks*, first item.
- Closure rule / "M3 closes only when every M3.2 sibling above is archived … t1854_13 keeps M3 open" — *Closure rule* and *Acceptance*: aitasks_go#t60 closes on its children; this task closes after aitasks_go#t60 (aitasks#t1854_13 became aitasks_go#t60_4).
- Closure rule / "t2117 / t2118 / t2119 do not hold M3 open" — *Closure rule* (now aitasks_go#t74, aitasks_go#t75, aitasks_go#t76).
- Coverage audit / row "individual results need a documented reporting contract and verified attribution" (t1854_14) — *Goal*: the proposal text is t1854_14's; the contract and README are aitasks_go#t60_5's.
- Coverage audit / "serial carve-out drift pin — M10.1 (t1861)" — *Cross-linking inside aitasks*, second item.
- Inbox t1852 / sequencing clarification and the cross-linking chore — *Cross-linking inside aitasks*, third item.
- Inbox t1853 / "M2.4 now depends on M3.1 … `aitask_update.sh --batch 1853_4 --deps`" — *Cross-linking inside aitasks*, last item: applied; t1853_4 is archived.
- Inbox aitasks_go#t15 / cutover protocol — the header of this body is the pointer; the engine work moved to aitasks_go#t60.

## Relocated to aitasks_go

The engine scope below moved to aitasks_go#t60 and is quoted for reference only.

> - aitasks_go#t60 is the engine-side M3 parent in aitasks_go. Its children are aitasks_go#t60_1 (scheduler), aitasks_go#t60_2 (go-test/engine-test), aitasks_go#t60_3 (gradle-class), aitasks_go#t60_4 (device, Postponed) and aitasks_go#t60_5 (the engine half of the suite reporting contract).
> - It carries the binding parts of the body: the submodule cut, the cross-module seams, the hooks/extensions, the automation-first rule, the G1–G10 guarantees, and protocol §2 (the mandatory per-child Reality check).
> - It closes when every R child is archived. Like the original, the Postponed device adapter keeps it open.
> - Acceptance:
>   - the union of the M3 component test lists (proposal *Module Map — How to read it*) is green in aitasks_go `goengines/`;
>   - every R child is archived;
>   - the aitasks_go#t74, aitasks_go#t75 and aitasks_go#t76 deferrals are tracked and do not hold aitasks_go#t60 open.


## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1852** id=2026-09-22T14:31:22Z.ecd6180d0e75396a6f96fae7 from=t1852 at=2026-09-22T14:31:22Z base=d0836b4f1750fde12e5e30260cd0d34396793a17 base_branch=main dirty=yes host=omg16
>
> | **Sequencing clarification (advisory, from the t1852 coarse pass, 2026-09-22).** The user asked that M1's children be *implemented* before M2 (t1853) is *planned*. Read the "plan all ten parents before implementing any child" paragraph in this task's body as an upper bound on how far planning may run ahead, not a requirement to plan against providers that do not exist. The rule is submodule-granular, never whole-parent (module-level deps form a cycle: M6.5 -> M8.2/M8.4, M8.3 -> M7.1/M7.2, M7.1 -> M6.2): start this parent's coarse pass once the specific provider submodules its wave-earliest children consume have landed in the tree, and implement its children in proposal wave order. A standalone cross-linking chore task (created from t1852's pass, followup_kind risk_mitigation) checks every "depends on" cell against real depends entries once all ten parents are decomposed; it accepts archived children as evidence and never rewrites M10.2-M10.5 (cross-repo).
> | 
> | **Go source layout (proposal fix, commit 07a546087 on main).** The engine source directory is `goengines/`, not `engine/`: one Go module (`github.com/beyondeye/aitasks/goengines`) for every distributable Go executable, `goengines/cmd/ait-testmap/`, shared packages `goengines/internal/{gitx,platform,lineproto}`, and every testmap-specific package under `goengines/internal/testmap/<pkg>`. Wherever the proposal (and this task's owns cells) write `internal/<pkg>`, read `goengines/internal/testmap/<pkg>`. Unchanged: the binary name `ait-testmap`, `$AITASKS_HOME/engine/v<V>/`, the `ait engine` verbs. CI workflow is `goengines-check.yml`; the release job is `goengines`. M1.2 (t1852_2) creates the module root; each later submodule adds only its own package and replaces only its own stub verb.

> **✉ note:t1852_2** id=2026-09-24T06:18:23Z.806d7ec4977018b28bdd2d48 from=t1852_2 from_verified=yes at=2026-09-24T06:18:23Z base=33012bff731972003d827cd6b152419d11ab9353 base_branch=main dirty=yes host=omg16
>
> | The M1.2 engine skeleton landed (t1852_2, commit 33012bff7). Your first engine children build on it; goengines/README.md ("Rules for engine submodules", "## Interfaces") is the reference:
> | - Verb table: cmd/ait-testmap/verbs.go registers every verb as stub("<verb>"). A submodule replaces only its own row with {Name, Run, Exits}; Exits is the verb's exit contract, and a code outside it becomes exit 3.
> | - Packages go under goengines/internal/testmap/<pkg>. Shared: internal/gitx (read-only git, BlobDigest, IsAncestor, LsTree), internal/platform (PoolCap 8, NewGroup, Lock, CacheRoot), internal/lineproto (Format/Line/Emit, exit codes).
> | - Registry contract: testmap.Contract = 1; testmap.CheckContract(path, data) returns *ContractMismatchError (Line() → CONTRACT_MISMATCH:<path>|<file>|<engine>, exit 3). contract: must be a non-negative int; merge keys and aliases are resolved.
> | - Cache: testmap.CacheDir() = ${XDG_CACHE_HOME:-$HOME/.cache}/aitasks/testmap.
> | - Fixtures: fixture.New(t, [SHA256()]) with Write/Remove/Commit(t, task, type, desc)/History/Run gives deterministic `(t<id>)` histories, isolated from the caller's git config. Add your own fixture constructors on top of Repo.
> | - Benchmarks: add BenchmarkX for each latency budget, record with `go run ./internal/tools/benchgate -baseline bench/baseline.txt -update`, and add budget=<d> where the proposal pins one. The full gate fails if a baseline benchmark disappears.
> | - Dependencies are allowlisted (yaml.v3, doublestar/v4, x/sync — doublestar is added by its first importer). Invariants 4-5 have a lexical tripwire in guards_test.go; a legitimate look-alike literal is exempted per line with `// invariant5-ok: <reason>`.

> **✉ note:t1853** id=2026-10-11T14:44:00Z.81faa743d19fd4b459a3bc75 from=t1853 at=2026-10-11T14:44:00Z base=3bc0de8ac7a9c9d1f60173e1257715a744efc451 base_branch=main dirty=yes host=omg16
>
> | Advisory, from the t1853 (M2) coarse pass. Proposal M2 cut fixed in commit 3bc0de8ac on main.
> | 
> | - **M3.1 gains a named extension:** the runner-backed unit lister that M2.1's `scan` / `check` call. M2.1 ships both verbs over an injected lister, tested with a fixture; M3.1 plugs the runner repository in. This was added to M3.1's Module Map row.
> | - **M2.4 now depends on M3.1** (`describe`'s `axis:` / `token_format:` land in M3.1's `describe` parse as M2.4's named extension). When you create your children, add the M3.1 child id to t1853_4's `depends:`, e.g. `./.aitask-scripts/aitask_update.sh --batch 1853_4 --deps "t1853_1,t1854_<m>"` (read the list first: --deps replaces it). t1853_4's body says "M3.1 (pending: t1854 not decomposed)".
> | 
> | **Automation-first (user directive, stated 2026-10-11 during the t1853 pass).** Human review belonged to an older design; the finalized test-map feature must run without a person wherever possible. At your coarse pass, treat any proposal step that makes a human action a precondition as a candidate to automate (record the decision in your plan; cut changes go into the proposal per protocol §1).

> **✉ note:t1853_1** id=2026-10-12T08:28:19Z.bb643c747c78eef51dac4376 from=t1853_1 from_verified=yes at=2026-10-12T08:28:19Z base=c07193265578ec723aa5994ca4bf20ed5116222e base_branch=main dirty=yes host=omg16
>
> | For M3.1 (not yet decomposed): M2.1 (registry core) landed in 0d04347ab; the proposal contract is at c07193265. Advisory, as of that tree; re-verify when M3.1 is planned.
> | 
> | The runner repository plugs into scan/check as registry.UnitLister (goengines/internal/testmap/registry/inputs.go):
> | - List(ctx, root) ([]Listing, error)
> | - Listing{Runner; Bound []string (test files the runner's bindings match: the UNREGISTERED candidates); ArtifactGlobs []string (describe's artifact_glob:); Units []ListedUnit{ID registry.ID, Kind, Lowering, Artifact}}
> | 
> | Wire it by setting Lister in testmapInputs() in goengines/cmd/ait-testmap/scancheck.go. Until then scan and check exit 3 with INPUT_UNAVAILABLE.
> | 
> | Ids must satisfy the id grammar (registry.ParseID: <path>[#<member>][@<variant>]). Invalid ids, invalid globs or a List error become INPUT_ERROR:lister|<detail>, exit 3.
> | 
> | How the fields are used:
> | - variant ids are persisted as variants: on their base unit in _scanned.yaml
> | - the Artifact column feeds UNMAPPED_ARTIFACT
> | - a listed unit of an exclude:d test path claims nothing

> **✉ note:t1853_3** id=2026-10-13T12:53:06Z.f007341165d9982df9324fe7 from=t1853_3 from_verified=yes at=2026-10-13T12:53:06Z base=2c04a9639cc377ce62858e5af12bbc3a0f76412b base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1853_3 (M2.3 dependency scanners), as landed in 2c04a9639. Verify against the code.
> | 
> | For M3.2: `bash-file list --invocations` overlaps M2.3's bash facts. `deps.Scan(...).Static(path)` already yields `static:invocation` edges with anchor lines, and `Facts(path)` adds the closure-only ones. The bash scanner covers:
> | - `SCRIPT_DIR` / `PROJECT_DIR` bindings, where every binding of a variable counts
> | - `source` / `.`, exec and interpreter calls
> | - embedded `python3 -c` / heredoc imports
> | - suffix matching for non-literal words
> | 
> | Printing those facts rather than re-scanning would keep one bash resolver. That is a suggestion, not a requirement. No human-only step was needed in M2.3.

> **👁 note:read** id=2026-10-13T14:42:18Z.e459ab7e4339e7252aea8abd by=t1854 at=2026-10-13T14:42:18Z mode=explicit ids=2026-09-22T14:31:22Z.ecd6180d0e75396a6f96fae7,2026-09-24T06:18:23Z.806d7ec4977018b28bdd2d48,2026-10-11T14:44:00Z.81faa743d19fd4b459a3bc75,2026-10-12T08:28:19Z.bb643c747c78eef51dac4376,2026-10-13T12:53:06Z.f007341165d9982df9324fe7

> **✉ note:t15** id=2026-10-25T08:53:45Z.eeb12517a59945a2e10e57dd from=aitasks_go#t15 at=2026-10-25T08:53:45Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
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

> **✉ note:t2141** id=2026-10-26T09:55:37Z.b84fb3c9416123269a123637 from=t2141 from_verified=yes at=2026-10-26T09:55:37Z base=7f49dbd62e8c9ab5ae05de2935184d3bf72256d7 base_branch=main dirty=no host=omg16
>
> | Advisory context from t2141 (observing goengines-check after t2138). It doesn't change this task's scope.
> | 
> | As of runs 40187609686 (309e0b8c6), 40279191111 (6e315def2) and 40301069108 (a probe identical to 6e315def2), `Go engines check` → `check` → `go test ./...` fails on GitHub-hosted runners in `internal/procsup`. The cause is hangguard LEAK reports from TestHaltStartInterleavings (3/3 runs) and TestSupervisorDeathHalts (1/3), tests that t1854_6 landed in 60ca89154. They pass locally. Filed as t2148 (bug, high).
> | 
> | Consequence for pending children: until t2148 lands, any push touching goengines/ will show `check` red at `go test`, and every later step (cross-build, sums loop, guards) is skipped. A red `check` there is not by itself evidence of a regression in a child's change. Look for `LEAK:Test…` lines under `internal/procsup`. The run-time observations are moment-relative; re-check `gh run list --workflow goengines-check.yml` before relying on them.

> **✉ note:t22_3** id=2026-10-29T22:22:23Z.0d3a1e60df5f62a3e019937b from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:22:23Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:11:12Z.f5f038dce2d3f2160d37f0e5 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:11:12Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | Split: the engine half of this task is aitasks_go#t60. This task's body
> | was trimmed to the framework half (the removed scope is quoted under
> | "Relocated to aitasks_go").
