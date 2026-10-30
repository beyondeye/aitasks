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
children_to_implement: [t1853_7]
anchor: 1852
created_at: 2026-09-22 09:19
updated_at: 2026-10-30 12:09
---

Split (aitasks_go#t22 cutover): the engine half of this task is aitasks_go#t59
in beyondeye/aitasks_go. This body is the framework half.

## Goal

Part of the **testing engine / test map** feature — ten parent tasks, one per
module of the proposal. This is the framework-side parent of **M2 — Registry
and map model**: everything that reads and writes `aitestmap/` without
running a test.

The M2 engine deliverables (M2.1–M2.6: the registry layout and loader, the
`testmap:` grammar and rewriter, the dependency scanners, axes and variants,
scoped rows and areas, the adoption tables) all landed as t1853_1 – t1853_6.
After the t22 cutover, engine development lives in beyondeye/aitasks_go:
the engine-side M2 parent is aitasks_go#t59, and the engine half of the repair
coordinator is aitasks_go#t59_1. Public `goengines/` is an export target only;
never edit it here.

This task keeps the framework side of M2:
- the n014 proposal's M2 cut
  (`aidocs/testing_engine/n014_explorer_006_proposal.md`, *Module Map* entry
  `#### M2 — Registry and map model` and the `(M2.x)` components). The
  proposal stays in this repository and is authoritative for both halves;
  aitasks_go children read it from here and send cut changes here by note;
- the M2 rows of the module → task map below;
- notes to other parents when the M2 cut changes;
- the M2 inputs to the cross-linking audit (t1863);
- its one child, t1853_7, now framework-only: the repair coordinator's
  agent-reasoning lane and its integration into onboarding, maintenance,
  task completion, gates, skills and docs.

## Acceptance

- This body points to aitasks_go#t59 and aitasks_go#t59_1 (done above).
- `children_to_implement` lists only the framework t1853_7.
- This parent archives only after the framework t1853_7 is Done, and t1853_7
  holds `xdeps` on aitasks_go#t59_1 (`xdeprepo: aitasks_go`), which unblocks only
  when that task is Done. Before closing, confirm aitasks_go#t59 is Done or
  archived in aitasks_go (a cross-repo check; ask by note if unsure).
- Every M2 proposal revision an aitasks_go child requested by note is
  applied to the proposal or rejected with a reason.

## Known inconsistencies in the proposal — resolved at the coarse pass

Settled on 2026-10-11 and fixed in the proposal (commit `3bc0de8ac`);
`aiplans/p1853_testmap_m2_registry_and_map_model.md` ("Deviations from the
proposal") records the reasons:

- M2.6 moved from wave E to **wave B** (its consumers M4.1 / M4.2 / M4.4 / M8.2
  are waves C–D).
- `scan` / `check` read two injected inputs: M2.2 plugs the annotation source,
  M3.1 plugs the runner lister (M2.1 ↔ M2.2 ↔ M3.1 cycle broken).
- Table and check-rule partition inside `internal/registry` among M2.1 / M2.4 /
  M2.5 / M2.6.
- `annotate --suggest` / `--from-body` moved to M2.3 (they read the closure);
  M2.3 depends on M2.2.
- M2.4 depends on M3.1 (`describe`'s `axis:` / `token_format:`).
- `classify --suggest`'s recorded-p95 signal lands with M6.4.
- The `go list` cache is keyed on import sets, not `go.sum` alone.
- The re-stamp provenance rule has an owner: M2.2's post-re-stamp hook, filled
  by M2.6, applied by actor.

These are done; nothing is pending. The proposal's "eight tables" for M2 is
now nine (t2131's M2.7 code-modules tier; its engine work is aitasks_go#t77's).

**Automation-first (user directive, 2026-10-11).** Human review belonged to an
older design; no M2 verb, load rule or check rule may make a human action a
precondition of any path. `by: human:<email>` is an optional recorded value,
never a gate. On this side the rule binds the skills, gates and docs that
drive M2 verbs; on the engine side it binds aitasks_go#t59.

## Reading list in the proposal

Maintained here; the aitasks_go children read the same sections.

- *Module Map* — `#### M2`, *How to read it*, *Cross-module interfaces*,
  *Suggested implementation order* (waves A, B, C, E).
- *Components* — *Registry loader and writer (M2.1 core; M2.6 adoption
  tables)*, *Annotation scanner and rewriter (M2.2)*, *Dependency scanners
  (M2.3)*, *Variant axes (M2.4)*, *Axis resolver verbs (M2.4)*, *Enumeration
  and reconciliation (M2.1)*, *Scoped-row registry and areas (M2.5)*,
  *Broad-test scheduling and staleness policy (M2.5 staleness half)*,
  *Adoption ledger: seeded → adopted → reviewed (M2.6 data)*.
- *Architecture* — *Vocabulary*, *The registry directory*, *Where state
  lives*, *Line-protocol index*.
- *The Adoption Model* — *The three states, with `by:`*, *The origin table*,
  *Placement: comment lines only*.
- *Assumptions* — *The map and freshness (M2, M4)*, *Variants, broad tests
  and runners (M2, M3)*; *Tradeoffs* — *Map and registry structure (M2, M3)*;
  *Open questions*.

## Planning and implementation protocol (binding for this task and every child)

This feature spans **ten parent tasks**, one per module of the proposal (see the
module → task map at the end), and since the t22 cutover two repositories:
engine work lives in beyondeye/aitasks_go, framework work here.

### 1. Coarse planning pass

- The coarse pass for M2 is done: one child per submodule row (t1853_1 –
  t1853_6, all landed), plus the supplementary sibling t1853_7.
- Keep the coarse plan coarse. A child's plan records what the proposal fixes
  for it — scope, owned files, provided and consumed interfaces, the
  component test lists that are its acceptance. It does **not** design
  internals against providers that do not exist yet; that is the reality
  check's job (§2), and the plan says so.
- Express cross-module order in task data, not in prose. Inside this
  repository a child's `depends:` names the child ids it consumes
  (`./.aitask-scripts/aitask_update.sh --batch <child-id> --deps ...`, which
  replaces the whole list). A provider in aitasks_go is held through `xdeps`
  (`--xdeps ... --xdeprepo aitasks_go`), which unblocks only when the target
  is Done. A provider in an undecomposed aitasks_go parent stays a prose hold
  that names the new owner (for example "M4.2 (aitasks_go#t61, not yet
  decomposed)") until that parent creates its children.
- Parent-level `depends:` stays empty on purpose, here and in aitasks_go#t59:
  module-level dependencies form a cycle (M6.5 → M8.2 / M8.4, M8.3 → M7.1 /
  M7.2, M7.1 → M6.2) and would block wrongly; the real graph is acyclic only
  at submodule granularity.
- Deviations from the proposal found while planning go into a **"Deviations
  from the proposal"** section of the plan. A wrong cut is fixed **in the
  proposal**, not patched in a plan; that is the proposal's own falsifier
  (`assumption_modules_map_to_parent_tasks`). Send a note (`/aitask-note`) to
  every parent whose tables the change touches, in either repository
  (`--project aitasks_go` for an aitasks_go parent). aitasks_go children
  report their deviations to this task by note; this task applies them.

### 2. Reality check at child implementation time — a mandatory step in every child's plan

**Every child task's plan MUST carry an explicit "Reality check" step,
executed before any code is written, and its outcome MUST be recorded in the
child's plan file.** This holds for the framework child t1853_7 here and for
aitasks_go#t59_1 in aitasks_go; each half's plan carries its own. The step:

1. Re-reads the proposal's Module Map row for this submodule, its component
   subsections, and the row of every interface it consumes (the *Cross-module
   interfaces* table).
2. Inspects the **actual current state** of every provider it consumes — the
   verbs, line protocols, files, hooks and tests as they exist now (engine
   providers in beyondeye/aitasks_go, framework providers here) — and names
   the task and commit that landed each one. The proposal's description of a
   provider and the coarse plan's description of it are both claims to be
   verified, never facts to be assumed.
3. Tabulates every difference in three columns: *proposal says* / *coarse plan
   says* / *repository has*.
4. Decides, per difference: adapt this child to reality; or revise this child's
   coarse plan; or revise the proposal (cut errors and interface changes go
   there, per §1). Records the decision and its reason.
5. Sends a note (`/aitask-note`) to every downstream child whose assumptions a
   difference or a decision breaks, hedging what cannot be proven from the
   tree (`--project aitasks_go` for a child there).
6. Re-confirms that every file this child will touch is owned by this
   submodule, or that the edit lands as the owner's named extension.

A child whose plan lacks this step, or whose step is not recorded as executed,
is not implementing this task as specified.

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
shows the whole feature as one lane. The cross-linking pass (t1863) audits
this map and the M2 dependency cells across both repositories.

## Carried obligations (framework half)

- `## Goal` — "Proposal (authoritative …) `aidocs/testing_engine/n014_…`" — *Goal*: the spec stays here and this task owns the M2 cut; aitasks_go#t59 reads it across repositories.
- `## Known inconsistencies` — eight cut fixes "fixed in the proposal (commit `3bc0de8ac`)" and plan Deviations — *Known inconsistencies*: done; the proposal and the plan stay here.
- `## Known inconsistencies` — "**Automation-first (user directive)** … no M2 verb, load rule or check rule may make a human action a precondition" — *Known inconsistencies → Automation-first*: binds the skills, gates and docs here; aitasks_go#t59 carries the engine invariant.
- `## Reading list in the proposal` — Module Map / Components / Architecture / Adoption Model / Assumptions — *Reading list in the proposal*, maintained here.
- Protocol §1 — "Plan this task … decompose into one child task per submodule row … 'Stop here'" — *Protocol §1*, first item: done for M2.1–M2.6; t1853_7 added as a supplementary sibling.
- Protocol §1 — "Keep the coarse plan coarse" — *Protocol §1*, second item; applies to t1853_7's plan.
- Protocol §1 — "Express cross-module order in task data … `aitask_update.sh --batch <child-id> --deps`" — *Protocol §1*, third item: `depends` in this repository, `xdeps` onto aitasks_go, prose holds naming the new owner for undecomposed parents.
- Protocol §1 — "Parent-level `depends:` stays empty on purpose" — *Protocol §1*, fourth item; this task keeps `depends: []`.
- Protocol §1 — "Deviations … fixed **in the proposal** … Send a note to every parent" — *Protocol §1*, last item: the proposal is here; aitasks_go children report deviations to this task by note.
- Protocol §2 — Reality check steps 1–6, "Every child task's plan MUST carry an explicit 'Reality check' step" — *Protocol §2*: t1853_7's plan carries its own.
- `## Module → task map` table — *Module → task map*, with the aitasks_go engine-parent column.
- children_to_implement=[t1853_7] — *Goal* and *Acceptance*: only the framework t1853_7 stays a child here; the engine half is aitasks_go#t59_1.
- Inbox aitasks_go#t15 — "keep engine commits separate … freeze protocol … re-homed … original carries a pointer" — the header of this body is the pointer; the engine work moved to aitasks_go#t59.

## Relocated to aitasks_go

The engine scope below moved to aitasks_go#t59 and is quoted for reference only.

> - aitasks_go#t59 is the thin engine-side container for M2 in aitasks_go. It carries the M2 cut, the seams and the binding protocol §2 (Reality check), and holds aitasks_go#t59_1, the engine half of t1853_7.
> - It owns any further engine work against the landed M2 packages (`goengines/internal/testmap/{registry,annot,deps,axes,classify}`, verbs `scan`/`check`/`annotate`/`verify`/`axes`/`areas`/`classify --suggest`). That covers the named extensions later modules land into them, on the engine side: M7.4 `--author`, the M6.4 recorded-p95 signal, the M6.4 `SCAFFOLD_TODO` check report.
> - Acceptance:
>   - The M2.1–M2.6 component test lists keep passing in aitasks_go CI after the migration (they are already satisfied by t1853_1..6).
>   - aitasks_go#t59_1 is archived.
>   - aitasks_go#t59 carries a pointer back to aitasks#t1853, and the module → repo map is recorded.


## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1852** id=2026-09-22T14:31:15Z.6c43dc2ecf5f2d0694ab4655 from=t1852 at=2026-09-22T14:31:15Z base=d0836b4f1750fde12e5e30260cd0d34396793a17 base_branch=main dirty=yes host=omg16
>
> | **Sequencing clarification (advisory, from the t1852 coarse pass, 2026-09-22).** The user asked that M1's children be *implemented* before M2 (t1853) is *planned*. Read the "plan all ten parents before implementing any child" paragraph in this task's body as an upper bound on how far planning may run ahead, not a requirement to plan against providers that do not exist. The rule is submodule-granular, never whole-parent (module-level deps form a cycle: M6.5 -> M8.2/M8.4, M8.3 -> M7.1/M7.2, M7.1 -> M6.2): start this parent's coarse pass once the specific provider submodules its wave-earliest children consume have landed in the tree, and implement its children in proposal wave order. A standalone cross-linking chore task (created from t1852's pass, followup_kind risk_mitigation) checks every "depends on" cell against real depends entries once all ten parents are decomposed; it accepts archived children as evidence and never rewrites M10.2-M10.5 (cross-repo).
> | 
> | **Go source layout (proposal fix, commit 07a546087 on main).** The engine source directory is `goengines/`, not `engine/`: one Go module (`github.com/beyondeye/aitasks/goengines`) for every distributable Go executable, `goengines/cmd/ait-testmap/`, shared packages `goengines/internal/{gitx,platform,lineproto}`, and every testmap-specific package under `goengines/internal/testmap/<pkg>`. Wherever the proposal (and this task's owns cells) write `internal/<pkg>`, read `goengines/internal/testmap/<pkg>`. Unchanged: the binary name `ait-testmap`, `$AITASKS_HOME/engine/v<V>/`, the `ait engine` verbs. CI workflow is `goengines-check.yml`; the release job is `goengines`. M1.2 (t1852_2) creates the module root; each later submodule adds only its own package and replaces only its own stub verb.

> **✉ note:t1852_2** id=2026-09-24T06:18:21Z.10ab06636ee23aae705623cc from=t1852_2 from_verified=yes at=2026-09-24T06:18:21Z base=33012bff731972003d827cd6b152419d11ab9353 base_branch=main dirty=yes host=omg16
>
> | The M1.2 engine skeleton landed (t1852_2, commit 33012bff7). Your first engine children build on it; goengines/README.md ("Rules for engine submodules", "## Interfaces") is the reference:
> | - Verb table: cmd/ait-testmap/verbs.go registers every verb as stub("<verb>"). A submodule replaces only its own row with {Name, Run, Exits}; Exits is the verb's exit contract, and a code outside it becomes exit 3.
> | - Packages go under goengines/internal/testmap/<pkg>. Shared: internal/gitx (read-only git, BlobDigest, IsAncestor, LsTree), internal/platform (PoolCap 8, NewGroup, Lock, CacheRoot), internal/lineproto (Format/Line/Emit, exit codes).
> | - Registry contract: testmap.Contract = 1; testmap.CheckContract(path, data) returns *ContractMismatchError (Line() → CONTRACT_MISMATCH:<path>|<file>|<engine>, exit 3). contract: must be a non-negative int; merge keys and aliases are resolved.
> | - Cache: testmap.CacheDir() = ${XDG_CACHE_HOME:-$HOME/.cache}/aitasks/testmap.
> | - Fixtures: fixture.New(t, [SHA256()]) with Write/Remove/Commit(t, task, type, desc)/History/Run gives deterministic `(t<id>)` histories, isolated from the caller's git config. Add your own fixture constructors on top of Repo.
> | - Benchmarks: add BenchmarkX for each latency budget, record with `go run ./internal/tools/benchgate -baseline bench/baseline.txt -update`, and add budget=<d> where the proposal pins one. The full gate fails if a baseline benchmark disappears.
> | - Dependencies are allowlisted (yaml.v3, doublestar/v4, x/sync — doublestar is added by its first importer). Invariants 4-5 have a lexical tripwire in guards_test.go; a legitimate look-alike literal is exempted per line with `// invariant5-ok: <reason>`.

> **👁 note:read** id=2026-10-11T11:47:00Z.122c1b785dc1bc10f7ef50a9 by=t1853 at=2026-10-11T11:47:00Z mode=explicit ids=2026-09-22T14:31:15Z.6c43dc2ecf5f2d0694ab4655,2026-09-24T06:18:21Z.10ab06636ee23aae705623cc

> **✉ note:t2131** id=2026-10-23T08:56:17Z.28dba72ffe5a527e16e1508a from=t2131 at=2026-10-23T08:56:17Z base=6b3161606e2989d1865628155f4e0bc1021cb917 base_branch=main dirty=yes host=omg16
>
> | t2131 (test-map code-module tier) adds a work package **M2.7 — Code modules**. Planned shape, advisory; the proposal text arrives with t2131_1, not landed yet:
> | - **New registry table.**
> |   - generated `_modules.yaml` plus a hand `modules:` table, registered via `RegisterFile` / `RegisterHandTable`;
> |   - "eight tables" becomes nine, and "two generated files" becomes three.
> | - **Package split.**
> |   - `registry` owns the schema, membership, path → module lookup and the `MODULE_*` rules (`MODULE_CONFLICT`, `MODULES_DRIFT`, `MODULE_UNRESOLVED`);
> |   - a new `internal/testmap/modules` above `deps` owns the providers and `modules --scan`.
> | - **New grammar key** `testmap:module`, allowed on any kind. It adds an optional `ScannedRow` field.
> | - **Areas.** Areas may reference `modules:`. `areas --import-codemap` is planned to write module refs and qualify colliding child names. That is a deviation from M2.5's landed contract, recorded by t2131_1.
> | - **Children:** t2131_3, t2131_4 and t2131_5 (Ready, after t2131_1).
> | 
> | For t1853_7's repair loop: `MODULE_UNRESOLVED:` and `MODULE_CONFLICT:` may be worth treating as repairable findings, e.g. via an agent `provider: agent` proposal or a `testmap:module` annotation. Both stay Info and non-failing in the plan.
> | 
> | Plans: `aiplans/p2131_testmap_code_modules_tier.md` and `aiplans/p2131/`.

> **✉ note:t2131_1** id=2026-10-24T21:25:14Z.3d8f1e6d1de62bb93b80a6de from=t2131_1 from_verified=yes at=2026-10-24T21:25:14Z base=5adc28fe429efa614cfea3e208dce4cfcc83d765 base_branch=main dirty=no host=omg16
>
> | Advisory, from t2131_1. Not an instruction; your own planning decides. The claims below are tree-relative, as of commit 5adc28fe4 (main), which amends aidocs/testing_engine/n014_explorer_006_proposal.md.
> | 
> | The code-module design you were told about on 2026-10-23 (note from t2131) is now in the proposal, and it changed: code modules are FLAT (user decision, 2026-10-24).
> | 
> | **Withdrawn from the earlier note:**
> | - "M2.7 … two tiers / submodules" — there are no submodules, nested records or qualified ids;
> | - "areas --import-codemap is planned to write module refs and qualify colliding child names (a deviation from M2.5)" — the import stays exactly as landed, still writing <path>/** globs. There is no M2.5 deviation.
> | 
> | **Where to read:**
> | - Module Map, M2 table: the M2.7 row and the consumer sentence under it;
> | - the new component *Code modules* (after *Scoped-row registry and areas*);
> | - *Where state lives*: the modules-table row;
> | - *Registry loader*: "nine tables" and the reserved name `_modules.yaml`.
> | 
> | **Newly fixed shapes:**
> | - Generated names are `<provider>:<native id>`: `codemap:<dir>`, `gradle:<Gradle path>`, `go:<dir>`, `py:<dir>`, with `/` written as `:` and the root directory as `.`. The four prefixes are reserved for hand and agent names.
> | - `MODULE_REFUSED:<provider>|<root>|unnameable|repository_root`. The Gradle root `:` and a codemap root entry are refused; a root Go/Python package is allowed.
> | - Ownership:
> |   - one owning module per mapped path;
> |   - subtree providers (codemap, Gradle): the deepest root wins;
> |   - package providers (Go, Python) own only their own source files;
> |   - two hand modules claiming one path → REGISTRY_INVALID.
> | - `MODULE_CONFLICT:<winner>@<p>|<loser>@<p>|<paths_n>|<first path>`, once per winner/loser pair.
> | - `agent` rows live in `_modules.yaml` and are carried over by `modules --scan --apply`.
> | - The hand block is flat: `modules: {<name>: {paths: […]}}`. A nested key is refused.
> | - An area's `modules: [<name>…]` expands to the modules' effective paths. An unknown or dropped name → `DEAD_SCOPE:<file>|areas|<area>|module:<name>`.
> | 
> | For t1853_7's repair loop the earlier remark still holds: `MODULE_UNRESOLVED:` and `MODULE_CONFLICT:` are Info findings, possibly repairable.

> **✉ note:t15** id=2026-10-25T08:53:42Z.d7ad8397af72d5a6c1646661 from=aitasks_go#t15 at=2026-10-25T08:53:42Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
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

> **✉ note:t22_3** id=2026-10-29T22:22:17Z.9bcb22b1e9cecb126a6e3037 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:22:17Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:11:06Z.41dca08c72a76828fdada959 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:11:06Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | Split: the engine half of this task is aitasks_go#t59. This task's body
> | was trimmed to the framework half (the removed scope is quoted under
> | "Relocated to aitasks_go").
