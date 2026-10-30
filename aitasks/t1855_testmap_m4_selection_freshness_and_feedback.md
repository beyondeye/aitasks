---
priority: medium
effort: high
depends: []
issue_type: feature
status: Postponed
labels: [testing, testmap, go_engine]
anchor: 1852
created_at: 2026-09-22 09:19
updated_at: 2026-10-30 12:10
---

Split (aitasks_go#t22 cutover): the engine half of this task is aitasks_go#t61
in beyondeye/aitasks_go. This body is the framework half.

## Goal

Tracker for **M4 — Selection, freshness and feedback** of the testing engine
/ test map feature (ten modules, one parent task each; see the module → task
map below). All five M4 submodules (M4.1–M4.5) are Go engine packages and
verbs, so all M4 implementation moved to aitasks_go#t61. Its coarse pass runs in
aitasks_go and creates one child per submodule there.

This task is **Postponed**. It keeps only the framework side of that pass:

1. the n014 proposal edits the pass decides
   (`aidocs/testing_engine/n014_explorer_006_proposal.md` stays in this
   repository and stays authoritative for every detail);
2. pointing the aitasks-side consumers of M4 at aitasks_go#t61's child ids, as
   cross-repo edges;
3. keeping the module → task map and the t1863 audit inputs current.

**Un-park:** when aitasks_go#t61 sends this task a note mapping each M4.x to its
aitasks_go id, set this task Ready and do the work below. Archive it once the
steps below are done and aitasks_go#t61 is Done.

## Proposal edits (protocol §1: a wrong cut is fixed in the proposal)

- **Wave order vs. stated dependencies.** The M2.6 part is settled: M2.6
  moved to wave B (t1853, `3bc0de8ac`) and landed (t1853_6). Still open: M4.5
  (wave C) lists M4.4 (wave D). aitasks_go#t61 decides the engine ordering; one
  resolution under the proposal's own rule is that M4.5 ships `test --all`
  without the `score` trigger and M4.4 adds `score` as a subscriber of M3.1's
  ordered post-run hook. This task then fixes the Module Map and the wave
  tables to match. Decide with the M2 and M8 parents (t1853 / aitasks_go#t59,
  t1859 / aitasks_go#t65).
- **One `RESULT:` shape.** *The Run Surface → Output and exit contract* has
  `RESULT:pass|fail|skip|error|refused|<n passed>|<n failed>|<n skipped>`;
  *Engine `test` composite (M4.5)* has `RESULT:pass|fail|skip|deferred|<run_id>`.
  M4.5 (aitasks_go#t61's child) and M5.1 (t1856) agree on one shape; this task
  writes it into the proposal.
- **Automation-first cut changes.** If aitasks_go#t61's M4.2 plan automates the
  "human re-stamp" paths in `stale --confirm*` or the stamp semantics, write
  that cut change into the proposal.
- **Reality-check deviations.** Every module or interface cut change that a
  aitasks_go#t61 child's Reality check reports arrives here as a note. Edit the
  proposal, then send a note to every parent whose tables the change touches
  (t1853, t1856–t1861 here; their aitasks_go halves with
  `./ait note <id> --project aitasks_go --from 1855 --file -`).

## Cross-repo holds on M4 (Edge decisions of the t22 relocation map)

`depends:` cannot cross repositories. A hold on an aitasks_go task is an
`xdeps` entry with `xdeprepo: aitasks_go`; it unblocks only when the target is
Done. When aitasks_go#t61's child ids arrive, give each consumer an `xdeps` entry
naming the specific child, and remove the matching prose hold from its body:

| consumer | holds on | existing `xdeps` to keep |
|---|---|---|
| t1859_2 (M8.2) | M4.2 | — |
| t1859_3 (M8.3) | M4.2, M4.3 | — |
| t2131_12 | M4.4 | aitasks_go#t77 |

The split framework halves t1853_7, t1859_4, t1859_5, t2131_7 and t2131_8 get
no direct M4 entry: they reach M4 only through their engine halves
(aitasks_go#t59_1, aitasks_go#t65_1, aitasks_go#t65_2, aitasks_go#t77_4, aitasks_go#t77_5), on which
they already hold `xdeps`, and those engine halves hold M4 inside aitasks_go.

Use `./.aitask-scripts/aitask_update.sh --batch <id> --xdeps "<existing>,<new>" --xdeprepo aitasks_go`.
The flag replaces the whole list, so repeat the existing entries. Check the
flag names with `--help` before the first call. A consumer stays Postponed
while any of its holds still names an undecomposed milestone; flip it to
Ready only once nothing in its hold is left unresolved.

The in-repo consumers in aitasks_go (aitasks_go#t65_1, aitasks_go#t65_2, aitasks_go#t77_4,
aitasks_go#t77_5, aitasks_go#t59_1) are wired by aitasks_go#t61 itself.

## Module → task map and cross-linking

- Update the module → task map below once the ids exist: M4's engine work is
  aitasks_go#t61 and its children in aitasks_go; this task is the framework
  tracker.
- Feed t1863 (the cross-linking pass): send it aitasks_go#t61's child ids and the
  `xdeps` written above. t1863 accepts re-homed rows; do not add `depends:`
  to Postponed pointer originals, link the aitasks_go replacement instead.

## Acceptance

- The proposal tables are consistent: no wave contradiction, one `RESULT:`
  shape.
- Every consumer in the table carries an `xdeps` hold naming the specific
  aitasks_go#t61 child id (`xdeprepo: aitasks_go`), and its prose hold for that
  M4.x is gone.
- The body points to aitasks_go#t61 (header above) and the module → task map names
  it.
- This task is archived once aitasks_go#t61 is Done.

## Planning protocol (framework side)

- Express cross-module order in task data, not prose: in-repo `depends:`
  here, `xdeps` across repositories.
- Parent-level `depends:` stays empty on purpose: module-level dependencies
  form a cycle (M6.5 → M8.2 / M8.4, M8.3 → M7.1 / M7.2, M7.1 → M6.2); the real
  graph is acyclic only at submodule granularity.
- Deviations from the proposal are fixed **in the proposal**, not patched in a
  plan; that is the proposal's own falsifier
  (`assumption_modules_map_to_parent_tasks`). Send a note (`/aitask-note`) to
  every parent whose tables the change touches.
- After all ten parents are planned, one cross-linking pass (t1863) checks
  every "depends on" cell against a real `depends:` or `xdeps` entry, and
  the module → task map against the parents' real ids.

## Reading list in the proposal

- *Module Map* — `#### M4`, *How to read it*, *Cross-module interfaces*,
  *Suggested implementation order* (waves C, D).
- *Components* tagged `(M4.x)`; *The Run Surface* — *Output and exit
  contract* (the `RESULT:` shape); *Architecture* — *Line-protocol index*.

## Module → task map

| module | framework (aitasks) | engine (aitasks_go) |
|---|---|---|
| M1 — Engine foundation and distribution | t1852 (landed) | — |
| M2 — Registry and map model | t1853 | aitasks_go#t59 |
| M3 — Runners, scheduling and cost | t1854 | aitasks_go#t60 |
| M4 — Selection, freshness and feedback | t1855 (this tracker) | aitasks_go#t61 |
| M5 — Run surface | t1856 | aitasks_go#t62 (M5.2 `brief`) |
| M6 — Onboarding | t1857 | aitasks_go#t63 |
| M7 — Agent review and author annotation | t1858 | aitasks_go#t64 |
| M8 — Completion policy and gates | t1859 | aitasks_go#t65 |
| M9 — Workflow integration, skills and documentation | t1860 | — |
| M10 — Rollout to the target repositories | t1861 | — |

All ten aitasks parents share the topic anchor of the M1 task, so the board's
By-Topic view shows the whole feature as one lane.

## Carried obligations (framework half)

- `## Goal` / "Proposal (authoritative …)" — *Goal*: the proposal stays in this repository and authoritative; this task edits it
- `## Known inconsistencies` / "Wave order vs. stated dependencies … Decide with the M2 and M8 parents and fix the proposal's tables (protocol §1)" — *Proposal edits*, wave bullet: aitasks_go#t61 decides the engine ordering, this task fixes the tables
- `## Reading list in the proposal` — *Reading list in the proposal* (the sections the table fixes touch)
- Protocol §1 / "Express cross-module order in task data … `depends:`" — *Cross-repo holds on M4* (xdeps) and *Planning protocol*
- Protocol §1 / "Parent-level `depends:` stays empty" — *Planning protocol*, parent-level `depends:` bullet
- Protocol §1 / "Deviations … fixed **in the proposal** … Send a note to every parent" — *Proposal edits*, reality-check bullet: edit the proposal, then notify every parent
- Protocol §1 / "After all ten parents are planned, one cross-linking pass" — *Module → task map and cross-linking*: feed t1863 the child ids and xdeps
- `## Module → task map` — *Module → task map* (both repositories) and its update step
- Inbox t1853 / "Automation-first … M4's candidates are the 'human re-stamp' paths in `stale --confirm*`" — *Proposal edits*, automation-first bullet
- Inbox t1854 / "Wave contradiction … M4.5 ships `--all` without the `score` trigger" — *Proposal edits*, wave bullet
- Inbox t1854 / "Two `RESULT:` shapes … M4.5 and M5.1 should agree on one" — *Proposal edits*, `RESULT:` bullet
- Inbox t1859 / "Waiting on your child ids … t1859_2 ← M4.2, t1859_3 ← M4.2, M4.3, t1859_4 ← M4.4, t1859_5 ← M4.4 … flip each … to Ready" — *Cross-repo holds on M4*: t1859_2–t1859_5 get `xdeps` on the aitasks_go#t61 children, then flip to Ready when nothing is left in their holds
- Inbox t2131 (08:55) / "wire their ids into these three [t2131_7, t2131_8, t2131_12] … Flip each child to Ready" — *Cross-repo holds on M4*: t2131_7, t2131_8 and t2131_12 rows
- Inbox t2131_1 / "keep `t2131_6` and add the M4.1, M4.4, M4.5 and M5.1 ids" — *Cross-repo holds on M4*, t2131_7 row: its framework half dropped that edge (the reach task is now aitasks_go#t77_3 in aitasks_go, reached through aitasks_go#t77_4); the M4.1 / M4.4 / M4.5 holds become `xdeps`, the M5.1 hold is t1856's child
- Inbox aitasks_go#t15 / coordination / freeze / re-home — The freeze is over; engine work for M4 lives in aitasks_go#t61 (header above)

## Relocated to aitasks_go

The engine scope below moved to aitasks_go#t61 and is quoted for reference only.

> - aitasks_go#t61 owns the whole M4 engine, decomposed at its coarse pass in aitasks_go into one child per submodule (M4.1–M4.5, with the `M4.x` id in each name). Each child plan carries the binding Reality-check step.
> - M4.1: `internal/selectr`, `internal/changesurface`, `select` / `explain`. M4.2: `internal/stale`, `stale`. M4.3: the evidence join. M4.4: `internal/feedback`, `score` / `attribute` / `readiness`. M4.5: the `test` composite. Each lands with the API facts from the inbox notes (adoption, scoped join, axes, cost ledger, recursion guard), and with seams left for the M8.4 `policy` / M8.5 `cadence.go` extensions and t2131_7 `--widen-modules`.
> - Engine-side decisions: the automation-first review of the `stale --confirm*` human re-stamp paths, the M4.5 ↔ M4.4 `score` trigger ordering, and keeping the prediction record schema additive.
> - Acceptance:
>   - The union of the M4.1–M4.5 component test lists passes in aitasks_go CI, including the bench budgets (e.g. `select` 200 ms warm).
>   - Invariant 2 holds: seeds never suppress `STALE`, never satisfy `require_stamp`, and never count under `--strict`.
>   - The `test` verb enters through the recursion guard (G9).
>   - The change-surface intake parses the `COMMITTED:` / `TASK:` / `OTHER:` / `UNKNOWN:` lines exactly as `aitask_change_surface.sh` emits them (fixture-based).
>   - One `RESULT:` shape is agreed with M5.1 and pinned by tests.


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

> **✉ note:t1854_7** id=2026-10-23T07:52:10Z.31d4f31737c55b42b3854a69 from=t1854_7 from_verified=yes at=2026-10-23T07:52:10Z base=ee468201fb47e48ead1fdab3019d6384bfaf8f23 base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1854_7 (M3.2d recursion guard, G9), landed in commit ee468201f. Not checked against your plan; re-verify in your own Step 0.
> | 
> | - For M4.5: the `test` verb (and `select`) must reach runner processes only through `runner.Load` / `runner.Run`, which now hold the recursion guard: a nested entry for the same repository is refused before any runner starts (`RUN_ERROR:recursion|<root>`, exit 3, or `RUN_ERROR:recursion-unverifiable|<root>|<detail>`). `cmd/ait-testmap/scancheck.go` `reportError` prints that line whatever wraps it, so a new verb that routes errors through `reportError` gets the same line.
> | - In-process callers (a scheduler, an executor, a post-run hook) must pass the context they were given to `Load` / `Run`; the guard detects in-process re-entry through it. A call with a fresh `context.Background()` is treated as independent.
> | - `Repository.Identity` carries the repository identity (realpath of the git common dir) if a verb needs it.
> | - Details: goengines/README.md Interfaces row "recursion guard (M3.2d, G9)".

> **✉ note:t2131** id=2026-10-23T08:55:39Z.ebcd9199993629d467000eec from=t2131 at=2026-10-23T08:55:39Z base=6b3161606e2989d1865628155f4e0bc1021cb917 base_branch=main dirty=yes host=omg16
>
> | t2131 (test-map code-module tier) is now decomposed. Three of its children are Postponed with a Dependency hold on M4 work packages that have no child ids yet:
> | - t2131_7 `selector_module_widening`: held on M4.1, M4.4, M4.5. depends: [t2131_6].
> | - t2131_8 `module_completion_mode`: held on M4.4. depends: [t2131_7, t1859_4, t1859_5].
> | - t2131_12 `retrospective_module_tier_evaluation`: held on M4.4. depends: [t2131_7, t2131_8].
> | 
> | When your coarse pass creates the M4 children, wire their ids into these three with `aitask_update.sh --batch <id> --deps "<existing>,<new>"`. That flag replaces the list, so repeat the existing deps. Flip each child to Ready once nothing in its hold is left unresolved.
> | 
> | Contract facts your M4 pass may want, all advisory. The proposal text arrives with t2131_1, which is not landed yet:
> | - t2131_7 adds `select` / `test --widen submodule|module` as a stage after the graded walk:
> |   - widened tests are budget-exempt (never DEFERRED);
> |   - new lines: `WIDENED:<level>|<modules_n>|<added_n>` and `WIDEN_FULL:<reason>|<path>`;
> |   - the `SELECTED:` shape is unchanged.
> | - t2131_7 also makes the M4.1 prediction record carry a paired form:
> |   - the plain selection, plus the widen outcome (level + added tests, or `full:<reason>`), plus an identity (base revision, change-surface digest, registry and modules-table digests);
> |   - M4.4 `score` then scores both sets against the same full run, with false negatives per set.
> | 
> |   A record without the widened part must score exactly as today. Please keep the record schema additive so this fits.
> | - Reach (t2131_6) uses the current graph only. It falls back to the full suite on any deletion, rename, unmapped path or in-repo dependency uncertainty.
> | 
> | Plans: `aiplans/p2131_testmap_code_modules_tier.md` and `aiplans/p2131/`.

> **✉ note:t2131_1** id=2026-10-24T21:25:29Z.78e81b0e99598dc8f9b39f0d from=t2131_1 from_verified=yes at=2026-10-24T21:25:29Z base=5adc28fe429efa614cfea3e208dce4cfcc83d765 base_branch=main dirty=no host=omg16
>
> | Advisory, from t2131_1. Not an instruction; your own planning decides. The claims below are tree-relative, as of commit 5adc28fe4 (main), which amends aidocs/testing_engine/n014_explorer_006_proposal.md.
> | 
> | The module-widening contract that the 2026-10-23 t2131 notes described is now in the proposal, revised to FLAT code modules (user decision, 2026-10-24).
> | 
> | **Withdrawn from the earlier notes:**
> | - `select` / `test --widen submodule|module`: the replacement is ONE plain flag, `--widen-modules`, on `select`, `explain`, `test` and `ait test`;
> | - `WIDENED:<level>|<modules_n>|<added_n>`: it is now `WIDENED:<modules_n>|<added_n>`;
> | - "level" anywhere in the prediction record: the widen outcome is just the added tests, or `full:<reason>`.
> | 
> | **Where to read:**
> | - component *Code modules* → *Widening* (incl. worked examples 1–6);
> | - *Selector*;
> | - *Engine `test` composite*;
> | - *Feedback tools*, incl. the new paragraph "Which prediction set readiness judges";
> | - *The Run Surface*, steps 6–7 and the output contract.
> | 
> | **Newly fixed:**
> | - `Widen` is one operation:
> |   - the affected modules are the owning modules of the changed paths ∪ their transitive reverse closure over resolved edges;
> |   - each carries evidence `{module, origin, via?}`;
> |   - the reason token is `module(<name>) <- <changed path>[ via <reached path>]`;
> |   - widened tests are budget-exempt.
> | - `WIDEN_FULL:<reason>|<first path>|<more_n>`, with reasons `deleted_path`, `renamed_path`, `unmapped_path`, `uncertain_reference` and `modules_stale`.
> | - **Execution.** A `WIDEN_FULL` outcome executes through the canonical `--all` path (`full-` prefix, anchors, cost rows, automatic score), never a re-listing.
> | - **Recording.** `select` / `explain --widen-modules` never execute or score, but each writes exactly what its plain form writes, so a task-scoped `select` still writes the prediction record.
> | - **The paired record:** plain selection + widen outcome + identity (base revision, change-surface digest, registry and modules-table digests). Under `completion.mode: module`, every task-scoped selection records the widen outcome automatically.
> | - **Scoring.** `score` prints `WIDEN_SCORED:<records_n>|plain_fn:<n>|widened_fn:<n>|full:<reason>=<n>,…`. `predictions.yaml` rows gain an optional `widened {added_n, fn, full?}`; a record without it scores as today.
> | - **Readiness judges the strategy each mode executes:**
> |   - `selected` / `auto`: plain sets only;
> |   - `module`: widened sets. A record without a widened part counts its plain false negatives. A full run counts toward the run totals only when every scored record carries a widened part and at least one of them is not `full:`. A modules-table change counts as a map change.
> | 
> | **New for M5:** t2131_7 is now also held on M5.1 (t1856), because the `ait test` front parses and forwards the public `--widen-modules` flag. When wiring ids into t2131_7, keep `t2131_6` and add the M4.1, M4.4, M4.5 and M5.1 ids.

> **✉ note:t15** id=2026-10-25T08:53:48Z.8eb59989a60e80d73eb807a8 from=aitasks_go#t15 at=2026-10-25T08:53:48Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
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

> **✉ note:t22_3** id=2026-10-29T22:22:40Z.ed69ea0ff8c7c2ba48ae4e2c from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:22:40Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:11:29Z.a96eb1e577209e79254601f2 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:11:29Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | Split: the engine half of this task is aitasks_go#t61. This task's body
> | was trimmed to the framework half (the removed scope is quoted under
> | "Relocated to aitasks_go").
