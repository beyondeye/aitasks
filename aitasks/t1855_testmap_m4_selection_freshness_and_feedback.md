---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [testing, testmap, go_engine]
anchor: 1852
created_at: 2026-09-22 09:19
updated_at: 2026-09-22 09:19
---

## Goal

Part of the **testing engine / test map** feature — ten parent tasks, one per
module of the proposal. This is **M4 — Selection, freshness and feedback**:
the map put to use — what to run, what is stale, what the last run proved,
what the map got wrong.

This module delivers the change-surface intake and the graded selector with
`explain`, the stamp semantics and the `stale` tool, the evidence join that
turns `last_pass` anchors into `EVIDENCED` vs `STALE` per variant, the
feedback verbs (`score` after every full run, `attribute --propose`,
`readiness` with `LEVEL` / `NEXT`), and the engine `test` composite that runs
`select --include-stale → schedule → run` in one process.

This task carries the module's cut — submodules, owned files, the interfaces
it provides and consumes, the seams later modules land into it — and the
planning protocol. It does **not** restate the specification.

**Proposal (authoritative for every detail):**
`aidocs/testing_engine/n014_explorer_006_proposal.md` — start at the *Module
Map* entry `#### M4 — Selection, freshness and feedback`, then the
*Components* subsections tagged `(M4.x)` (listed under *Reading list* below),
then the narrative sections those components name. *Architecture*, *Design
decisions* and the *Invariants every module honours* apply to every module.

**Acceptance:** the union of the module's components' test lists (*Module Map —
How to read it*).

## Submodules (one child task each — settled at the coarse planning pass)

| submodule | scope | depends on | wave |
|---|---|---|---|
| **M4.1** Change-surface intake and selector | the `--changes -` line intake refusing `UNKNOWN:`, the graded walk with select / implies / escalate rules, variant expansion and axis join, test-dep at distance 1, `ESCALATE` on opaque files, the scoped join, kind-then-cost ranking, invocation groups, stale marks, `--include-stale`, the suite budget with `DEFERRED`, `--format lines\|json\|tokens`, the prediction record, `explain` and `explain --sources --format table`, the `edge(seeded:…)` and `adopted(…)` reasons, `SELECTED:` and `UNMAPPED_SOURCE:` ahead of the rows. Owns `internal/selectr`, `internal/changesurface`, verbs `select` and `explain` | M2.1, M2.3, M2.4, M2.5, M2.6, M3.4 | C — see *Known inconsistencies* |
| **M4.2** Freshness and staleness | stamp semantics (who may write one), `stale --task\|--all` with its line classes and encodings, `--confirm`, `--confirm-source`, `--confirm-evidenced`, `--retarget`, the `SEEDED:` / `ADOPTED:` summaries, the `adopted(…)` DISPLAY field, `bootstrap_until` / `require_stamp` / `flake_threshold`. Owns `internal/stale` (all but the join), verb `stale` | M2.2, M2.6, M4.1 | D |
| **M4.3** Evidence join | `last_pass` anchors per reached variant, flake and cause filtering, the ancestor check, one `git ls-tree` per sha, `EVIDENCED` vs `STALE` per variant, never rewriting. Owns the join in `internal/stale` + `internal/gitx` | M3.4, M4.2 | D |
| **M4.4** Feedback: score, attribute, readiness | automatic `score` after every full run (window scoring, per-task attribution, `REJECTION_CONTRADICTED`), `attribute` with `--propose` writing `seeded.yaml` rows of origin `observed`, `readiness` with `LEVEL` / `NEXT`, its criteria and counters. Owns `internal/feedback` (all but `cadence.go` and the `policy` package), verbs `score`, `attribute`, `readiness` | M2.6, M3.4, M4.1 | D |
| **M4.5** Engine `test` composite | `test --task --changes - \| --paths \| --all [--explain] [--budget-s] [--format] [--run <id>]` running `select --include-stale → schedule → run` in one process; `--all` as `run --all` honouring `subsumed_by` and triggering `score`. Owns verb `test` in `internal/selectr` | M3.2, M3.3, M4.1, M4.4 | C — see *Known inconsistencies* |

## Cross-module seams

**Provides** (defined here, consumed elsewhere):

- The ranked list, `SELECTED:`, `UNMAPPED_SOURCE:`, the prediction record,
  `explain --sources --format table` — M4.1 → M4.5, M5.1 (verdict), M9.1
  (procedure), M9.2 (QA).
- The `stale` report and the `adopted(…)` DISPLAY — M4.2 → M8.2, M8.3.
- Self-healing `STALE` rows — M4.3.
- The `readiness` lines, `LEVEL` / `NEXT`, the scored history the policy flip
  needs, the observed-seed path — M4.4 → M5.2, M6.1 (`status`), M6.5, M8.4,
  M8.5.
- The `test` composite's output — M4.5 → M5.1 (the one engine call the bash
  front makes).

**Consumes:** the loaded registry and the adoption tables (M2.1, M2.6); the
stamp format and the rewriter (M2.2); scanner facts (M2.3); variant expansion
(M2.4); the scoped join (M2.5); the builtins, the wave plan and the cost rows
(M3.2, M3.3, M3.4); the change-surface line intake `COMMITTED:` / `TASK:` /
`OTHER:` / `UNKNOWN:` produced by `aitask_change_surface.sh` (exists today —
M4.1 parses it, M4.2 / M5.1 / M7.4 reuse the parse).

**Hooks and extensions** (a file has one owner; a later submodule lands its
edit as the owner's named extension):

- `readiness` (M4.4) gains `CALIBRATION:` / `REVIEW_AGREEMENT:` from **M7.3**
  and `POLICY:`, `CADENCE:`, `approved_by\|engine` from **M8.4 / M8.5** — all
  additive; the base protocol is M4.4's.
- `internal/feedback` is M4.4's; **M8.4** adds the `policy` package and
  **M8.5** adds `cadence.go`.
- The `testmap_fresh` gate's role on top of freshness is **M8.3**'s; M4.2
  provides the report it consumes and never the workflow.
- `score` (M4.4) writes `costs/predictions.yaml`, whose store is **M3.4**'s;
  the window-score trigger is reused by M8.5's cadence.
- The `edge(seeded:…)` / `adopted(…)` reasons and `--propose` rows depend on
  the M2.6 tables — see the inconsistency below.
- Invariant 2 (a stamp is a claim; a seed is not) is enforced here: seeds
  never suppress `STALE`, anchor evidence, satisfy `require_stamp` or count
  under `--strict`.
- Named follow-up (not v1): hunk-level attribution inside a member file (with
  M2.3).

## Known inconsistencies in the proposal — settle at the coarse pass

- **Wave order vs. stated dependencies.** M4.1 (wave C), M4.2 and M4.4 (wave
  D) list M2.6 (wave E) as a dependency, and M4.5 (wave C) lists M4.4 (wave D).
  Either M2.6 moves to wave C and M4.5 to wave D, or the selector, `stale` and
  `readiness` ship without seeded / adopted rows and M2.6 extends them
  additively (and `test --all` ships without triggering `score`). Decide with
  the M2 and M8 parents and fix the proposal's tables (protocol §1).

## Reading list in the proposal

- *Module Map* — `#### M4`, *How to read it*, *Cross-module interfaces*,
  *Suggested implementation order* (waves C, D).
- *Components* — *Selector (M4.1)*, *Freshness (M4.2)*, *Staleness tool
  (M4.2)*, *Evidence join (M4.3)*, *Feedback tools (M4.4)*, *Engine `test`
  composite (M4.5)*.
- *Data Flow* — *A task in steady state*, *Reading the map without running
  anything*, *The policy flip* (what `score` and `readiness` feed).
- *The Run Surface* — *Resolution, in order*, *Output and exit contract*.
- *Architecture* — *Line-protocol index*.
- *Assumptions* — *The map and freshness (M2, M4)*; *Tradeoffs* — *Freshness
  and evidence (M4)*; *Open questions*.

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

> **✉ note:t1852** id=2026-09-22T14:31:28Z.8641bc6cad150c1cfe062eb9 from=t1852 at=2026-09-22T14:31:28Z base=d0836b4f1750fde12e5e30260cd0d34396793a17 base_branch=main dirty=yes host=omg16
>
> | **Sequencing clarification (advisory, from the t1852 coarse pass, 2026-09-22).** The user asked that M1's children be *implemented* before M2 (t1853) is *planned*. Read the "plan all ten parents before implementing any child" paragraph in this task's body as an upper bound on how far planning may run ahead, not a requirement to plan against providers that do not exist. The rule is submodule-granular, never whole-parent (module-level deps form a cycle: M6.5 -> M8.2/M8.4, M8.3 -> M7.1/M7.2, M7.1 -> M6.2): start this parent's coarse pass once the specific provider submodules its wave-earliest children consume have landed in the tree, and implement its children in proposal wave order. A standalone cross-linking chore task (created from t1852's pass, followup_kind risk_mitigation) checks every "depends on" cell against real depends entries once all ten parents are decomposed; it accepts archived children as evidence and never rewrites M10.2-M10.5 (cross-repo).
> | 
> | **Go source layout (proposal fix, commit 07a546087 on main).** The engine source directory is `goengines/`, not `engine/`: one Go module (`github.com/beyondeye/aitasks/goengines`) for every distributable Go executable, `goengines/cmd/ait-testmap/`, shared packages `goengines/internal/{gitx,platform,lineproto}`, and every testmap-specific package under `goengines/internal/testmap/<pkg>`. Wherever the proposal (and this task's owns cells) write `internal/<pkg>`, read `goengines/internal/testmap/<pkg>`. Unchanged: the binary name `ait-testmap`, `$AITASKS_HOME/engine/v<V>/`, the `ait engine` verbs. CI workflow is `goengines-check.yml`; the release job is `goengines`. M1.2 (t1852_2) creates the module root; each later submodule adds only its own package and replaces only its own stub verb.

> **✉ note:t1853** id=2026-10-11T14:44:02Z.754c0d19280094325705775a from=t1853 at=2026-10-11T14:44:02Z base=3bc0de8ac7a9c9d1f60173e1257715a744efc451 base_branch=main dirty=yes host=omg16
>
> | Advisory, from the t1853 (M2) coarse pass. Proposal M2 cut fixed in commit 3bc0de8ac on main.
> | 
> | - **M2.6 (adoption tables, t1853_6) moved from wave E to wave B.** M4.1 / M4.2 / M4.4 consume it, so it now lands before them; wire `t1853_6` into those children's `depends:`.
> | - **`select --axis` is M4.1's flag.** M2.4 (t1853_4) provides the facet join and forced-facet resolution as library API; M4.1's `select` parses `--axis` (now written into M4.1's row).
> | - Re-stamp provenance: `stale --confirm-source` (M4.2) calls M2.6's routing. The rule is applied **by actor**: an automated re-stamp refreshes the `adopted.yaml` row and keeps its `by:`; only an explicit human actor deletes it.
> | - The `go list` dependency cache is keyed on Go import sets, not `go.sum` alone (M2.3); the closure M4.1 walks no longer goes stale when a local import changes.
> | 
> | **Automation-first (user directive, stated 2026-10-11 during the t1853 pass).** Human review belonged to an older design; the finalized test-map feature must run without a person wherever possible. At your coarse pass, treat any proposal step that makes a human action a precondition as a candidate to automate (record the decision in your plan; cut changes go into the proposal per protocol §1). From my reading, M4's candidates are the "human re-stamp" paths in `stale --confirm*` / stamp semantics — unverified against your module's full text.

> **✉ note:t1853_2** id=2026-10-12T14:31:14Z.462639d729fbc47e04b9ffc6 from=t1853_2 from_verified=yes at=2026-10-12T14:31:14Z base=7229dee868985aafae8cd16e493614d1904311b5 base_branch=main dirty=no host=omg16
>
> | For M4.2 (`stale --confirm*`): M2.2's rewriter landed in f096db065 (contract in the proposal at 7229dee86). Advisory, as of that tree.
> | 
> | - Re-stamp through annot; never write test files directly. The path is annot.ParseFile, then annot.PlanCovers(f, member, source, stamp), then annot.Apply(root, annot.EditSet{Path, Snapshot: f.Snapshot(), Edits}).
> | - Stamps come from annot.SourceStamp(*os.Root, source, objectFormat) or annot.NewStamp. Get the root with os.OpenRoot and the format with gitx ObjectFormat.
> | - Each Edit carries Member + Source and is ownership-checked. A stale plan is *annot.ConflictError: REWRITE_CONFLICT:<path>|<line>, exit 75.
> | - A covers line inside a Python module docstring is never re-stamped (annot.ErrDocstring).
> | - The post-re-stamp hook (M2.6's provenance rule) is run only by annot's own annotate / verify engines. Per the M2 parent plan's Deviation 8, `stale --confirm-source` calls M2.6's routing directly.
> | 
> | No human-only step was met.

> **✉ note:t1853_3** id=2026-10-13T12:52:57Z.b08b40315fe0b1a9a6e184e0 from=t1853_3 from_verified=yes at=2026-10-13T12:52:57Z base=2c04a9639cc377ce62858e5af12bbc3a0f76412b base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1853_3 (M2.3 dependency scanners), as landed in 2c04a9639. These are claims about that tree; verify against the code before relying on them.
> | 
> | For M4.1 (selector):
> | - API: `deps.Scan(ctx, root, deps.Options{Config, CacheDir, Uncached}) → *Graph`. Then:
> |   - `Closure(path, max)`, BFS; `max <= 0` is unbounded. Walk it unbounded: source and import chains run deeper than 2 hops.
> |   - `Reverse`, `Static`, `Opaque`, `ModuleOf` (deepest Gradle module, for runner sets), `Problems`.
> |   - Accessors return copies.
> | - `Opaque` escalates only for a change to *that* file. A test whose own imports are uncertain is not marked opaque: the graph instead widens it with closure-only edges (`anywhere`, `suffix`, `fallback`, `package-fallback`). Treat every edge as reachability, whatever its origin.
> | - android-res (`symbol_scanners: [android-res]`):
> |   - `deps.ResKeys` / `deps.ChangedKeys(before, after)`; a nil side means every key.
> |   - A `<string>` and a `<plurals>` sharing a name share one key.
> |   - A Java file names every key (`*`).
> | - Measured scan cost on this host:
> |   - aitasks shape: warm about 116 ms (bench budget 150 ms), cold about 1.0 s (budget 1.5 s), both including `go list -test`.
> |   - This repository: warm about 100–120 ms single-core.
> |   That leaves about 80 ms of `select`'s 200 ms warm budget for everything else.
> | - No human-only step was needed anywhere in M2.3.

> **✉ note:t1854** id=2026-10-13T16:20:49Z.af97143f9d1b7416afa943e4 from=t1854 at=2026-10-13T16:20:49Z base=6a3a81efc30577c762d42f815f3e95eac95b4e3f base_branch=main dirty=no host=omg16
>
> | Advisory, from the t1854 (M3) coarse pass. The proposal's M3 cut was fixed in commit 6a3a81efc on main; see the Deviations in aiplans/p1854_testmap_m3_runners_scheduling_and_cost.md. These are claims about that tree, so verify them at your coarse pass.
> | 
> | - **Evidence join (M4.3), Dev 7.** Anchor eligibility is now decided at run time by M3.4 (t1854_4).
> |   - A pass becomes `last_pass` only when its invocation had no cause and HEAD did not move.
> |   - Its modified-path set must also be disjoint from: the unit's test file and test-side closure, its covers sources, the closure's `reads` globs, and the runner configuration.
> |   - For an opaque or suite closure the set must be empty.
> |   - The ledger row records `anchor` plus a reason.
> |   - The component text now gives M4.3 one guard of its own: drop an anchor whose `at` date is not strictly later than the edge's stamp date. A same-day anchor is dropped, which is fail-safe.
> |   - The cause filter is now pre-applied by M3.4.
> | - **Grouping (M4.1), Dev 9.** M3.1 (t1854_1) owns one canonical grouping function keyed by (runner, group_by group, resource set, wave class, batch identity).
> |   - `batch: no` units are singletons.
> |   - The wave class is the caller's input, derived from M2.5 kinds.
> |   - Use the same function and inputs for `SELECTED:` `<groups>` and the estimate, so both match what M3.3 executes.
> | - **Full-suite p95, Dev 13.** Estimates count top-level ids only. A child row never adds to its parent, and `overhead_ms` is elapsed time minus the top-level durations. The full-suite p95 is that estimate applied to the newest `full-` run.
> | - **`explain` (M4.1).** It prints M3.1's shadow-by-name resolution record.
> | - **Estimate kinds.** M3.4's estimate takes kinds from its caller.
> | - **M4.5.** It composes `run --all`, which is M3.1's verb and honours `subsumed_by`. The scheduler sits inside `run`, through M3.1's plan-executor seam, which M3.3 fills.
> | - **Wave contradiction, possibly in your cut.** M4.5 is in wave C but depends on M4.4, which is in wave D. One resolution under the proposal's own rule: M4.5 ships `--all` without the `score` trigger, and M4.4 adds it as a subscriber of M3.1's ordered post-run hook.
> | - **Two `RESULT:` shapes.** The Run Surface defines `RESULT:pass|fail|skip|error|refused|<n>...`, while the `test` composite defines `RESULT:pass|fail|skip|deferred|<run_id>`. M4.5 and M5.1 should agree on one.
> | - **Automation-first** (user directive). At your coarse pass, treat any human-only precondition as a candidate to automate.

> **✉ note:t1954_4** id=2026-10-14T18:37:13Z.4718b18075b9b53525bcd459 from=t1954_4 from_verified=yes at=2026-10-14T18:37:13Z base=f8d4b2ef54e729ae6e7ee76c1ba3f63395660f14 base_branch=main dirty=yes host=omg16
>
> | t1954 (multi-language annotation parsers) is complete. Report: aidocs/testing_engine/t1954_annotation_parser_research.md. Verdict for M4: context only.
> | - Decision: the landed M2.2 readers stay the production providers for bash, Python, Go and Kotlin. No reader or provider change reaches annot's API.
> | - M4.2's `stale --confirm` still re-stamps through annot (ParseFile → PlanCovers → Apply). Nothing changes for it.
> | - A test in an unsupported language carries no inline annotation (annot.ErrNoLeader), so there is nothing to confirm for it.
> | - Open defect, for awareness: Kotlin 2.2 multi-dollar strings can make the Kotlin reader read, and Apply write, a look-alike inside a raw string (t1990). Exposure was nil on 2026-10-14.

> **✉ note:t1853_5** id=2026-10-18T15:59:26Z.96ee9249e497a9cb92908ec7 from=t1853_5 from_verified=yes at=2026-10-18T15:59:26Z base=6f6d1ed799167c432f1ae5ed90abeb346b712f4f base_branch=main dirty=yes host=omg16
>
> | Advisory, for M4.1 (selector) and M4.2 (staleness), from t1853_5 (M2.5) as landed in 6f6d1ed79. Not yet children of t1855, so routed to the parent; re-verify at your Reality check.
> | 
> | **The scoped join (M4.1).** The call is `registry.ScopedOf(reg).Join(changed []string, units []registry.ID, closure registry.ClosureFunc) ([]registry.JoinHit, error)`.
> | - Each `JoinHit` carries `{Test, Kind, Distance:1, Via area|scope|trigger|reads, Ref, Path, BudgetExempt}`.
> | - `Ref` is the area name, the glob, or the helper. For `Via=reads`, `Ref` is the join-time `reads_from`; it is not persisted in `_scoped.yaml` (proposal revised).
> | - `BudgetExempt` is true for trigger and reads hits.
> | - You must pass the test-side closure. If any `reads` row exists and the closure is nil, Join returns `ErrNoClosure`.
> | - Hits are sorted by `(KindRank, test, via, ref, path)`. Cost ranking, `suite_budget_s` and `DEFERRED` remain yours.
> | - Kind order is `registry.KindRank`: unit < integration < e2e < device.
> | - One kind per test: `Join` and `KindOf` read the same effective rows. A kind conflict between generated and hand rows reads as the lowest-ranked kind and is reported as `SCOPE_CONFLICT`.
> | 
> | **Staleness (M4.2).** `ScopedOf(reg).DigestExempt(id)` is true for broad units: scoped rows are never digest-stale. Their fixture-pin `covers` stay ordinary stamped edges in `_scanned.yaml`. `STALE_AREA` / `REVIEW_DUE` were not built by M2.5.

> **✉ note:t1853_6** id=2026-10-19T09:18:08Z.2768eb78262d04feed0a58b4 from=t1853_6 from_verified=yes at=2026-10-19T09:18:08Z base=093d98a197a65931bdd6f104d4a919f965dfc0ee base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1853_6 (M2.6 adoption tables). It describes the tree as of aaeb10b0f, so verify it in your reality check. M4's children are not decomposed yet, so this note goes to the parent.
> | 
> | What M2.6 provides to M4.1 / M4.2 / M4.4 (goengines/internal/testmap/registry):
> | 
> | - `registry.AdoptionOf(reg)`:
> |   - `Seeds`: live seeds, already excluding shadowed and rejected pairs. These are the rows `edge(seeded:…)` walks.
> |   - `AdoptedFor(test, source)`: the provenance row of a stamped edge. `stale` / `explain` print `adopted(<origins> <confidence> by <who>)` from it. Confidence may be absent: a machine first stamp has no measured confidence.
> |   - `SeedsCovering(source)`.
> |   - `Classified(StampedPairs(edges))` re-judges the tables against other edges (`check` uses the live annotation edges).
> | - `registry.AdoptionSummary(a)` returns exactly the `SEEDED:` / `ADOPTED:` lines `check` prints. `stale --all` can reuse it.
> | - `stale --confirm-source` (M4.2) must go through `OpenAdoption(ctx, root, registry.RouteRestamp)` + `ApplyRestamps(registry.PhasePost, by, known, edges)` + `Commit()`, or simply re-stamp through `annot.AnnotateWith`, whose hooks already apply the rule. It must never write adopted.yaml directly.
> | - `attribute --propose` (M4.4) uses `RouteAttributePropose` with `PutSeed`; a rejected pair is skipped.
> | 
> | All writes are serialised by a git-dir lock. A failure after some files landed is `ADOPTION_PARTIAL` (exit 3), and re-running the verb converges. The README rows "adoption tables (M2.6)" and "write routing (M2.6)" hold the contract.

> **✉ note:t1859** id=2026-10-19T12:47:03Z.ad26b169fa7ac5a55fbb31cb from=t1859 at=2026-10-19T12:47:03Z base=bf32b336c0b0673eccba125bf097df173405e8d7 base_branch=main dirty=yes host=omg16
>
> | Advisory, from the t1859 (M8) coarse pass. The proposal fix is commit bf32b336c; the plan is aiplans/p1859_testmap_m8_completion_policy_and_gates.md. These are tree claims as of that commit; verify them at your pass.
> | 
> | - **Waiting on your child ids.** At your coarse pass, add M4 child ids to these tasks' depends and flip each from Postponed to Ready once its hold list is empty (the hold lists are in each body under "Dependency hold"):
> |   - t1859_2 (M8.2) ← M4.2
> |   - t1859_3 (M8.3) ← M4.2, M4.3
> |   - t1859_4 (M8.4) ← M4.4
> |   - t1859_5 (M8.5) ← M4.4
> | 
> |   t1859_5 also waits on M5.2, so it stays held until t1856 is wired.
> | - **M8.2 consumes M4.1's UNMAPPED_SOURCE:** for one task's change surface, through M4.2. The interface row now lists M8.2.
> | - **Named extensions in your packages:**
> |   - internal/testmap/feedback gains a `policy` package (M8.4) and `cadence.go` (M8.5);
> |   - readiness gains `POLICY:`, `CADENCE:`, `cadence_declared` and `approved_by|met|engine`;
> |   - `score` gains the window-score trigger after a cadence full run.
> | - **New engine verb `policy` (Dev 7).** M8.4 adds `decide`; M8.5 adds the `policy.yaml` writes. readiness's `POLICY:` line must call the same feedback/policy code.
> | - **M8.2 moved from wave D to wave E (Dev 11).** It depended on M4.2 inside the same wave.

> **✉ note:t1854_4** id=2026-10-20T09:37:04Z.0bea83fb60d1b7922f1d0ef7 from=t1854_4 from_verified=yes at=2026-10-20T09:37:04Z base=d70250f708143ce51667dd1491ae34f6919a4df5 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1854_4 (M3.4 cost ledger) as landed in 487271c89. These are tree claims: re-verify in your Reality check. The interfaces are pinned in goengines/README.md (rows "cost ledger", "anchor eligibility", "cost tables and fold", "estimate and full-suite p95").
> | 
> | - **Read API (M4.1 / M4.3 / M4.4):**
> |   - `cost.Load(root, hc)` / `cost.LoadAll(root)` return the committed `aitestmap/costs/<hc>.yaml` plus the pending ledger runs folded in memory. Anchors are visible before any `costs --update`.
> |   - `LastPass(id)` is per host class. An anchor on any host class counts (`assumption_passing_run_anchors_edges`), so M4.3 merges across `LoadAll`.
> |   - `Flaky(id, cfg.FlakeThreshold)`: flake = flips / pairs of consecutive clean pass-vs-fail observations at the same `head_sha`.
> | - **Anchors:**
> |   - The cause filter and run-time eligibility are already applied: `last_pass` advances only from `anchor: true` rows.
> |   - The ledger rows carry `clean`, `anchor` and `anchor_reason`.
> |   - `last_pass.at` is RFC 3339 UTC, for M4.3's strictly-later-than-stamp guard.
> | - **Estimate (M4.1):** `cost.Estimate(t, runner.Group(units, wave), kindOf)`. Disjoint: top-level units only, plus group overhead. An unmeasured id or group counts the median top-level p95 and is counted in `Unknown` / `UnknownGroups`, so apply your own safe direction.
> | - **Full runs (M4.5):** a run counts as the full-suite baseline only with `--run-id full-…` **and** `--all`, every invocation cause-free and unrefused, and a timed top-level result. M3.1's default `run-…` id never qualifies.
> | - **Hooks (M4.4):** post-run subscribers register in the single ordered `init` in `goengines/cmd/ait-testmap/costs.go`. Register `score` after `cost-ledger`, which it reads.
> | - **Stores:** `cost.AppendPrediction(root, entry)` is the `predictions.yaml` writer API (entry needs `run_id`; same-`run_id` entries are replaced; the newest 200 are kept; it runs under a lock).
> | - **Residual:** dirty-tree anchors are rare on this repo (89 % of bash tests have an unresolved `source`/`exec` → opaque). Expect mostly clean-tree anchors; see t2081.

> **✉ note:t1853_4** id=2026-10-21T09:39:50Z.51951beea2301261d03eb8d6 from=t1853_4 from_verified=yes at=2026-10-21T09:39:50Z base=1518db7680e1a4a7d968ae489f0c67218d0f7f34 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1853_4 (M2.4 Axes and variants) as landed in 1518db768; re-verify in your Reality check. Tree-relative claims only.
> | 
> | Library: goengines/internal/testmap/axes (rows in goengines/README.md "axes library (M2.4)").
> | - Committed state: `_scanned.yaml` rows gain `axis:` (the owning runner's describe `axis:`, on rows with variants) and `facets:` (the unit's `testmap:axis` claims). Read them via `axes.Of(reg)` + `reg.Units`; `select` never needs to run a runner for axis placement.
> | - M4.1 selection composition (caller obligation, NOT implemented in M2.4): the axis channel is additive. Select = `(*Table).Select(rows, t.Join(changed))` UNION `axes.Expand(rows, unit)` for every edge / dep / rule / test-dep reached unit; never intersect them (Invariant 1). A variant whose value the axis does not declare is placed by every hit on its axis (`Placed.Undeclared`). Reason text: `Placed.Reason()` = `axis(<a>.<f>=<v>) <- <path>`.
> | - M4.1 `--axis`: `ParseForce` -> `(*Table).ResolveForce` (`*ForceError`, Reason axis|facet|value) -> `ix, _ := axes.IndexRows(rows)` once, then `t.Admits(forces, ix, id)` per candidate. Semantics chosen here (revisable via protocol §1): forces on the same (axis, facet) are alternatives (OR), different facets AND; an undeclared value is cut; a plain unit with claims on the forced facet survives only if one matches; unclaimed units pass.
> | - M4.1 `--format tokens`: `runner.Describe.TokenFormat().Render(id)`; placeholders {id} {base} {path} {member} {variant}, default {id}.
> | - Deferred decision for M4.1's design: whether a source may name a facet value that ONLY plain-unit claims carry (no declared variant value carries it). Today that is refused at load as a misspelt source; weigh it together with typo detection and which `--axis` values are accepted.
> | - M4.4: `registry/observed.yaml` stays a reserved, refused file (no loader shipped). When you define it, feed observed axis sources through `(*Table).Widen` — widen-only: unions globs into declared (axis, facet, value) cells, never removes a glob or touches values, rejects undeclared axis/facet, an uncarried value or a bad glob.
> | - M4.3: variants are plain ids `<unit>@<value>`; nothing axis-specific is required for the per-variant evidence join.

> **✉ note:t1854_2** id=2026-10-21T19:10:39Z.df9b7f199c98ac4044808b0b from=t1854_2 from_verified=yes at=2026-10-21T19:10:39Z base=5582dd4f455372f5ba40a43b6d2dffe2101089b3 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1854_2 (the M3.2 re-decomposition, 2026-10-21). Ids are as of the commit this note records.
> | M4.5 (the engine `test` composite) consumed "M3.2 builtins". When you decompose, its child edges should name:
> | - t1854_2 (the evidence contract: accounting classes, `RUN_ACCOUNTING`, case reconciliation);
> | - t1854_6 (supervised execution and the `runner <name>` verb);
> | - t1854_7 (the recursion guard);
> | - the adapters you need (t1854_8 bash-file, t1854_9 pytest, t1854_10 go-test / engine-test, t1854_11 gradle-class, t1854_12 suite).
> | The `test` verb must enter through the same recursion guard as `run` / `Load` (G9: refuse a nested entry for the same repository, including under `env -i`; fixture repositories allowed).
> | Details: parent t1854, section "M3.2 re-decomposition (2026-10-21)".

> **✉ note:t2131** id=2026-10-23T05:01:06Z.4dfa481687ee145d29abdf01 from=t2131 at=2026-10-23T05:01:06Z base=b460828651acc16079e3a895296343b1c422620d base_branch=main dirty=yes host=omg16
>
> | Advisory context from t2131 (testmap code-modules tier, status Ready, not yet planned). Nothing here is an instruction; your own planning decides.
> | 
> | t2131 adds a two-level code-module tier (module -> submodule) between the per-file graded walk and the full suite. Two parts touch M4:
> | 
> | 1. M4.1 selector (`internal/selectr`) / M4.5 `test` composite: an on-demand widening grade, e.g. `select|test --widen submodule|module`. Decisions confirmed during exploration (user-confirmed, not yet a landed design):
> |    - The widening adds tests and never removes them. Individually selected tests that lie outside the widened modules are kept.
> |    - The affected modules are the touched modules plus each dependent module that has a file reaching a changed file through the reverse dependency closure (`deps.Graph.Reverse` / `Closure`). An edit internal to a module does not pull in its dependents.
> |    - Each affected module then contributes its complete test set, with no recursive expansion through module dependencies.
> |    - Widening falls back to full where the uncertainty is unbounded: `gradle-dynamic` builds (deps widen to every module), opaque files, unresolved references the closure cannot follow.
> |    - The unmapped / ESCALATE / empty-selection fallback stays full unless the module evidence shows a narrower run is safe.
> |    - A test may belong to several modules. Membership comes from build structure and path containment plus the modules of its covered sources; a `testmap:module`-style annotation only corrects it. Unresolved membership must be reported, never guessed.
> |    - Output needs a module-widening reason in `SELECTED:` / `explain`.
> |    - Open interplay question for your planning: does the suite budget's `DEFERRED` cut apply to widened tests?
> | 2. M4.4 `readiness`: the `POLICY:<mode>` line would need to know a `module` completion mode (M8.4 owns the mode; see t1859_4).
> | 
> | Suggestion for M4.1's coarse planning: leave a seam for a widening stage after the graded walk and before ranking and the budget, or record a dependency edge to t2131's selector child once it exists. The module table itself (generated + hand overrides, from Gradle `ModuleOf`/`Deps`, Go/Python packages, the two-tier `code_areas.yaml`) is planned as M2-style work under t2131 and does not wait on M4.
> | 
> | Terminology heads-up: t2131 uses `module`/`submodule` in CLI and YAML and renames M1-M10 to "implementation work packages" in the design prose of aidocs/testing_engine/n014_explorer_006_proposal.md.
