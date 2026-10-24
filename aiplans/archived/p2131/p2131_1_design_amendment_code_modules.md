---
Task: t2131_1_design_amendment_code_modules.md
Parent Task: aitasks/t2131_testmap_code_modules_tier.md
Sibling Tasks: aitasks/t2131/t2131_2_*.md … aitasks/t2131/t2131_12_*.md
Archived Sibling Plans: aiplans/archived/p2131/p2131_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-24 23:09
---

# Plan: t2131_1 — Proposal amendment for flat code modules (verified, revised)

## Context

t2131 adds a **code-module** grouping to the test map: a middle ground between
"tests selected from the changed files" and "the full suite". This child
writes the design into `aidocs/testing_engine/n014_explorer_006_proposal.md`
so every later child implements against proposal text.

**Revision (user decision, 2026-10-24): one flat set of modules, with no
submodule concept.** The two-level design (module → submodule) that the
parent pass fixed on 2026-10-23 is dropped. A module is a named grouping of
source paths, discovered from project structure or refined through overrides.
Every module has the same standing. The aim stays the same, with fewer
concepts and fewer interacting rules. The trade-off is accepted: there is no
built-in way to pick a small region and its larger parent. Extra levels are
reconsidered only if measurements show flat modules give runs that are too
broad.

So this pass does two documentation jobs:
- **A.** amend the proposal for the flat design;
- **B.** revise the parent task and plan, this task, and the affected child
  tasks and plans to match. Dependency holds and unrelated requirements are
  kept.

Rules carried over:
- **Automation-first.** No verb, rule or gate needs a human action, and agent
  output keeps `by:`.
- **Conservative reach.** Use the current graph only. Fall back to the full
  suite on a deletion, a rename, an unmapped path, an in-repo uncertainty or
  a stale table. The absence of a resolved edge is never proof of
  independence. Every fallback reason is recorded and measured. Smarter
  analysis is a gated follow-up.
- **Wording.** New prose says "work package" for M1–M10 / Mx.y. The bulk
  rename stays with t2131_2.

## Step 0 — Reality check (done; main @ bcdeff693)

1. The proposal is unchanged since c6b1b491c (older than ee468201f). Every
   anchor cited in the task body holds:
   - Vocabulary 163; process map 286-342;
   - registry tree 344-365; config 370-409;
   - *Where state lives* 411-436; line-protocol index 438-462;
   - decisions 466-647 (19 of them, so the new one is 20);
   - M2 table 694-705; interfaces 819-847; waves 849-872;
   - follow-ups 874-888; data flow 922-941;
   - run surface 1599-1702; workflow-seam policy 1940-1960;
   - package list 1994; verb table 2036-2042;
   - loader 2195-2322 (eight tables 2197-2200, reserved names 2306-2309);
   - areas 2831-2941; runner contract 2962-3045; selector 3266-3296;
   - feedback 3388-3424; `test` composite 3427-3446;
   - onboarding verbs 3605-3688; completion 3847-3879; auto 3882-3920;
   - tradeoff 4664.
2. `M2.7`, the verb `modules`, every new prefix, `_modules.yaml` and
   `--widen-modules` are all unused. "tier" occurs twice, both unrelated.
3. `TestVerbTableMatchesProposal` (`goengines/cmd/ait-testmap/main_test.go:21-52`)
   is a hard-coded list and does not parse the proposal. `policy` already sits
   in the proposal's table without being in the Go list, so a proposal-only
   `modules` entry breaks nothing; t2131_3 adds it to Go.
4. t1855, t1857, t1859_4, t1859_5, t1853 and t1854_11 each hold one or two
   advisory notes `from=t2131` (2026-10-23). Those notes describe the
   **two-level** design: `--widen submodule|module`, `completion.widen`,
   `group_by: module|submodule`, nested ids. So this pass's contract notes
   must say which statements are now withdrawn, not only add new facts
   (memory: send the note when your change breaks the reference).
5. t2131_2 is `Ready` (not landed), so today's headings are used. No other
   `Implementing` task's plan touches the proposal.
6. Code facts behind the provider rules:
   - `Graph.ModuleOf` already picks the deepest containing Gradle directory
     (`deps/graph.go:127-155`), and the root project `:` has `Dir ""`;
   - the id-fragment rule refuses only `/ # @ |`, whitespace and control
     characters (`registry/id.go:123-143`), and area names also refuse glob
     metacharacters (`scoped.go:334-342`). So `:` is legal: a Gradle path
     minus its leading colon is a valid, unique name;
   - `ReadCodemap` recurses `children` to any depth and refuses duplicate
     names (`registry/areas_import.go:79-126`).

## The flat design (what A writes and B propagates)

**D1 — One abstraction.** A *code module* is a named set of source paths. Its
record is `{name, provider, by?, root? | paths?, gradle?, evidence[], deps?}`.
- There are no nested records, no parent/child relation and no qualified
  ids.
- The id is the name, and names follow the area-name rule.
- The generated table is `aitestmap/registry/_modules.yaml`.
- The hand override is a flat `modules: {<name>: {paths: [<glob>…]}}` block
  in a hand file. A nested key such as `submodules:` or `children:` is an
  unknown key and is refused.

**D2 — Provider boundary rules (initial, deterministic).** There are two
kinds of provider.
- A **subtree provider** (codemap, Gradle) declares a module as one
  directory, its root. The module owns every path under that root that is
  not under a deeper root of the **same provider**. **Deepest root wins.**
  Nesting creates no membership and no expansion: a nested root is simply
  another module.
- A **package provider** (Go, Python) declares a module as one package. The
  module owns **only that package's own source files**: the `*.go` files,
  test files included, directly in the package directory, or the `*.py` /
  `*.pyi` files directly in it. It never owns a subtree, so a subpackage is
  simply another module, and no package claims unrelated content beside it
  (READMEs, scripts, `testdata/`; those stay unmapped unless another provider
  owns them).
- A **glob provider** (hand, agent) declares a module as a set of globs.

| rank | provider | kind | module boundary | name | known limitation |
|---|---|---|---|---|---|
| 1 (wins) | hand `modules:` | glob | the listed globs (unioned across hand files, like areas) | the key | two hand modules claiming one path → `REGISTRY_INVALID` (an authoring error) |
| 2 | `provider: agent` rows (in `_modules.yaml`, `by: agent:<string>`; t2131_9's intake) | glob | the proposed globs | as proposed | the intake refuses an overlap between two agent rows |
| 3 | codemap `code_areas.yaml` (read, never run) | subtree | **every entry at any depth** is a module rooted at its `path` | `codemap:<root>` | granularity is whatever the map's author wrote; a parent entry owns only the files no child covers; the entry's own name is shown as evidence |
| 4 | Gradle | subtree | **every included project**, rooted at its `projectDir`, at any nesting depth | `gradle:<Gradle path without the leading :>` (e.g. `gradle:services:payments:api`) | one project = one module, however mixed its sources; an aggregate project owns only its own build files |
| 5 | Go | package | every package under a `go.mod`; it owns its own `*.go` files | `go:<dir>` | fine-grained (one module per package); a package's non-Go files are unmapped; coarser grouping comes from the codemap, agent or hand |
| 5 | Python | package | every package (a regular package or a namespace portion); it owns its own `*.py` / `*.pyi` files | `py:<dir>` | the same; a flat `tests/` directory is no package, so membership comes from covered sources |

- **Generated names cannot collide.** A generated name is
  `<provider prefix>:<native id>`, where the native id is:
  - the Gradle path for Gradle, which is unique by construction;
  - the repo-relative directory with `/` written as `:` for the codemap, Go
    and Python;
  - for the repository root directory, `.`. No directory component can be
    `.`, so `go:.` / `py:.` are unambiguous.

  `:` is never part of a directory component. A root whose directory or
  project name contains `:` or another character the name rule refuses
  (`# @ |`, whitespace, control characters, glob metacharacters) is **not a
  module**: it is reported `MODULE_REFUSED:<provider>|<root>|unnameable` and
  its paths stay unmapped. So the mapping is injective. For example, `a/b/`
  → `go:a:b` and `a.b/` → `go:a.b`, while `a:b/` is refused. The prefixes
  `codemap:`, `gradle:`, `go:` and `py:` are reserved, and a hand or agent
  name using one is refused. Names can only collide between the two glob
  providers: the hand module wins, and the agent row is dropped and reported
  `MODULE_CONFLICT:`.
- **No subtree module at the repository root.** The Gradle root project `:`
  (the existing protection) and a codemap entry at the root would each own
  the whole repository. Each is refused as
  `MODULE_REFUSED:<provider>|.|repository_root`, and the files only it would
  own stay unmapped. A **root package is legitimate**: `go:.` / `py:.` owns
  only that package's own source files in the root directory, so it is
  bounded and cannot become a catch-all.
- **Ownership.** Each mapped path has exactly one owning module: the
  highest-ranked provider claiming it wins. Within one subtree provider the
  deepest root wins. Go and Python never claim the same file (each owns
  only its own language's sources), so rank 5 needs no tie-break.
  An uncovered path stays unmapped; nothing is guessed.
- **Conflicts.** `MODULE_CONFLICT:<winner>@<provider>|<loser>@<provider>|<paths_n>|<first path>`
  (Info) is printed once per winner/loser pair whose path sets overlap but
  differ, and for the hand/agent name collision above. A refinement is
  normal: a hand `api` over `services/api/public/**` takes those paths from
  `codemap:services:api`, which keeps the rest. A lower module left with no
  paths is absent from the effective table.
- **No granularity system.** There is no knob that picks how deep a provider
  cuts. Boundaries are refined only through codemap entries, agent proposals
  and hand overrides, all with provenance.

**D3 — Module → module `deps:`** carry one file-level evidence pair each. They
are for inspection only, and reach never trusts them.

**D4 — Membership.** It is computed at load in `registry` and never persisted.
- A test's modules are its path-containment module (if any) ∪ the owning
  modules of every source it covers (`_scanned.yaml` covers, hand, adopted
  and seeded edges). Covered-source modules count even when path membership
  exists.
- `testmap:module <name>…` (allowed on any kind) replaces only the
  path-derived part. An annotation that would drop a covered-source module is
  a finding.
- A test with no module at all is `MODULE_UNRESOLVED:<test>` (Info, counted,
  never guessed).
- There is one kind of membership; nothing is inherited.

**D5 — Module widening, one operation.** "Find the modules containing changed
files and their transitive reverse dependents. Add every test belonging to
those modules. Preserve tests already selected."
- `Widen(current graph, table, membership, change surface, plain selection)`
  returns one of two results:
  - the affected modules, each with its evidence
    `{module, origin: <changed path>, via?: <reached path>}`, plus the added
    tests with their reasons;
  - or `full:<reason>`.
- Path reach is the changed paths ∪ the transitive reverse closure over
  resolved edges. Each reached path maps to its one owning module. An
  internal edit pulls no dependents (nothing outside reaches it), and reach
  never recurses through module `deps:`.
- **Full fallback**, printed as `WIDEN_FULL:<reason>|<first path>|<more_n>`,
  for these reasons:
  - `deleted_path` / `renamed_path`;
  - `unmapped_path`: a changed **or reached** path no module owns, including
    root-only Gradle files;
  - `uncertain_reference`: any in-repo uncertainty anywhere (an `Unresolved`
    entry naming an in-repo target, an opacity reason, a `<dynamic>` source,
    a `gradle-dynamic` build), where a form the scanner cannot classify
    counts as uncertainty and an out-of-universe reference does not;
  - `modules_stale`.
- There is no level, no parent fallback and no hierarchy in the interface.
- Recording: the `WIDEN_FULL:` line, the prediction record's widen outcome,
  and per-reason counts that `score` derives from records (`WIDEN_SCORED:`).
  There is never a second store.

**D6 — Public surface.**
- **Spelling.** One spelling, `--widen-modules`, on `select`, `explain` and
  `test` (engine) and on `ait test`. It is a plain flag with no value. The
  name avoids the proposal's other "widen" senses.
- **Output.** `WIDENED:<modules_n>|<added_n>` comes ahead of the rows. The
  reason token is `module(<name>) <- <changed path>[ via <reached path>]`.
  The `SELECTED:` shape is unchanged.
- **Budget.** Widened tests are budget-exempt, so they are never `DEFERRED`.
- **Config.** `completion.mode: full|selected|module|auto`. There is **no
  `completion.widen`**: the mode names the strategy.
- **Grouping.** `group_by: module`; there is no `group_by: submodule`.
  `{module}` resolves from the module's `gradle` path, and a module without
  one is refused.
- **Summary lines.** `MODULES:<modules_n>|<unmapped_paths_n>|<provider>=<n>,…`
  and `MODULE:<name>|<provider>|<root or globs>|<members_n>|<evidence>`.
  `MODULE_OF:<path|test-id>|<name>|path|covers:<source>|annotation` comes from
  `modules --explain`. The other lines are `MODULES_DRIFT:<path>`,
  `MODULE_UNRESOLVED:<test>` and
  `MODULE_REFUSED:<provider>|<root>|unnameable|repository_root`.
- No submodule count, level field or placeholder for a future hierarchy
  exists anywhere.

**D7 — Execution and recording.**
- A `WIDEN_FULL` outcome executes through the **canonical full-run path**:
  - `test --widen-modules` / `ait test --widen-modules` run exactly what
    `--all` runs: `run --all`, `full: true` suites once, `subsumed_by`
    honoured, the `full-` prefix, anchors, cost rows and the automatic
    `score`;
  - under `module` completion it is an ordinary full completion run, which
    also scores the window and resets the counters.
- **Wording-conflict fix.** "`select --widen-modules` and `explain
  --widen-modules` never execute or score a test. Each writes exactly what
  its plain form writes, a task-scoped `select` therefore still writing the
  task's prediction record (now carrying the widen outcome)." No prohibition
  of prediction recording appears anywhere.
- **Paired prediction record.** It holds the plain selection, the widen
  outcome (the added tests, or `full:<reason>`), and an identity: base
  revision, change-surface digest, registry digest and modules-table digest.
  A record without the widened part scores exactly as today, and newest-wins
  keeps the pair together.
- While `completion.mode` is `module`, every task-scoped selection records
  the widen outcome whether or not the flag was passed, so evidence builds
  up with no person involved. What a selection *runs* is unchanged.

**D8 — Readiness judges the strategy it executes.**
- `selected` / `auto` use plain sets only, as today. A miss the plain set had
  and the widened set caught is a false negative for them.
- `module` uses the widened sets:
  - `max_false_negatives` counts widened false negatives. A record with no
    widened part counts its plain false negatives.
  - `min_scored_full_runs` and `min_full_runs_since_map_change` count a full
    run only when every record it scored carries a widened part and at least
    one of those parts is not `full:`. Open Question 9's rule (count only
    non-trivial selections) applies on top.
  - A modules-table change (the table digest the records carry) counts as a
    map change.
- There is no widening level, so there is no rule for changing one.

**D9 — `module` completion.** It reuses M8.5's `cadence.go`, the `policy`
verb and the `policy.yaml` writes. The decision order:
1. `NOT_YET` → full (`POLICY:module|full|not_yet:<c>`).
2. The first `ADMISSIBLE` run → `approved_by {who: engine:readiness@<run>,
   mode: module}`, printed as `POLICY_FLIPPED:module->module|…` (the mode,
   then what it now runs). An approval recorded under `auto` does not count.
3. A due cadence trigger (`tasks`, `days`, or `selection_ratio_above` on the
   widened estimate) → full, `cadence:<trigger>`.
4. A later unmet criterion → `POLICY_DEMOTED:module->full|<criterion>`, with
   `approved_by` cleared.
5. A widen fallback → full, `POLICY:module|full|widen_full:<reason>`. The
   widening is computed once, before step 3; when it falls back, the ratio
   is not evaluated.
6. Otherwise the widened set runs, `POLICY:module|module|next_full_in:<n>`,
   and `selected_since_full` is incremented.

Around the order:
- Every full run resets the counters, and `module` needs a valid
  `full_run_every` (`cadence_declared`).
- A human `approved_by` is optional.
- `result="MODE:module|<n units>|policy:module|next_full_in:<n>"` stays
  within 200 characters.
- `auto` never lands on `module` in v1.
- `detect --write` never writes `module`; the onboarding skill writes it
  only once the engine supports it (t2131_11).

**D10 — Areas.** An area may list `modules: [<name>…]`, which expands at
load to those modules' **effective** paths.
- A name that is unknown, or absent from the effective table, is refused as
  `DEAD_SCOPE:<file>|areas|<area>|module:<name>`.
- A reference follows later boundary changes. It is a hand-authored opt-in,
  and *Code modules* says so.
- **`areas --import-codemap` is unchanged from the landed M2.5 contract.**
  It still copies each entry's `<path>/**` glob and never writes a module
  reference, so an imported area's breadth never depends on the modules
  table, on provider precedence or on an override. This removes the earlier
  planned M2.5 deviation; the import's duplicate-name refusal stays as landed.
- **Check:** a codemap entry `api` at `services/api/` and a hand module `api`
  over `services/api/public/**` give an imported area `api` =
  `services/api/**`. A change to `services/api/internal/x.go` still reaches
  that area's broad tests. In the modules table the hand `api` owns
  `public/` and `codemap:services:api` keeps `internal/`; the two names never
  collide.

**D11 — Concrete examples.** These are written into the component, and each
must give exactly one affected-module set and one test set.
1. **One module.** `gradle:services:payments:api` (`services/payments/api/`)
   and `codemap:auth` (`auth/`). A change to
   `services/payments/api/src/Charge.kt` that nothing outside the module
   imports. Affected: {`gradle:services:payments:api`}. Tests: the plain
   selection ∪ that module's members.
2. **Transitive chain.** Codemap entries give `codemap:ledger`,
   `codemap:billing` and `codemap:reports`. `billing/Invoice.kt` imports
   `ledger/Entry.kt`, and `reports/Monthly.kt` imports `billing/Invoice.kt`.
   A change to `ledger/Entry.kt` gives affected {`codemap:ledger`,
   `codemap:billing`, `codemap:reports`}, with reasons
   `module(codemap:billing) <- ledger/Entry.kt via billing/Invoice.kt` and
   `module(codemap:reports) <- ledger/Entry.kt via reports/Monthly.kt`.
   Tests: the members of all three ∪ the plain selection.
3. **A test in several modules.** Hand modules are `board`
   (`.aitask-scripts/board/**`) and `lib` (`.aitask-scripts/lib/**`).
   `tests/test_board.sh` is in no module by path. It covers
   `.aitask-scripts/board/aitask_board.py` and
   `.aitask-scripts/lib/task_utils.sh`, so its modules are {`board`, `lib`}.
   A change to `.aitask-scripts/lib/task_utils.sh` that no other module's
   file reaches gives affected {`lib`}, and the test set includes
   `tests/test_board.sh`.
4. **A deeply nested native project.** `settings.gradle.kts` includes
   `:services` (`services/`) and `:services:payments:api`
   (`services/payments/api/`). `services/payments/api/src/A.kt` is owned by
   `gradle:services:payments:api` only (deepest root). A change there
   affects {`gradle:services:payments:api`} plus its reverse dependents. It
   never affects `gradle:services` by nesting; that module joins only if a
   file it owns imports the changed file. The root project `:` is no module
   (`MODULE_REFUSED:gradle|.|repository_root`), so a change to the root-only
   `build.gradle.kts` gives `WIDEN_FULL:unmapped_path|build.gradle.kts|0`.
5. **Unsafe change.** A change that deletes `lib/old.sh` gives
   `WIDEN_FULL:deleted_path|lib/old.sh|0`. A change to `tools/x.sh`, which no
   module owns, gives `WIDEN_FULL:unmapped_path|tools/x.sh|0`. Either way
   `ait test --widen-modules` runs the canonical full run, as it does for
   example 4's root file.
6. **Root and child packages** (provider acceptance). `go.mod` sits at the
   repository root for `example.com/tool`. The root directory holds
   `main.go`, `main_test.go` and `README.md`, and `tool/` holds `parse.go`
   and `parse_test.go`.
   - Modules: `go:.` owns `main.go` and `main_test.go`; `go:tool` owns
     `tool/parse.go` and `tool/parse_test.go`. `README.md` is unmapped.
   - `main.go` imports `example.com/tool/tool`. A change to `tool/parse.go`
     reaches `main.go`, so the affected set is {`go:tool`, `go:.`} with
     `module(go:.) <- tool/parse.go via main.go`. Tests: `tool/parse_test.go`
     and `main_test.go` ∪ the plain selection.
   - A change to `main.go` that nothing imports gives affected {`go:.`}.
   - Only a change to `README.md` falls back
     (`WIDEN_FULL:unmapped_path|README.md|0`).
7. **Name safety** (provider acceptance): packages `a/b/` and `a.b/` become
   `go:a:b` and `go:a.b`. A package directory `a:b/` is refused
   (`MODULE_REFUSED:go|a:b|unnameable`), and its files stay unmapped.

## Implementation — Part A: proposal edits

Every rule lives in one place: the new component *Code modules*. Other
sections cross-reference it.

1. **Invariant 1** (109-112): "a module widening or `module` completion that
   cannot bound its reach runs full."
2. **Section markers.** Append `component_code_modules` to the `dimensions`
   lists of the `architecture`, `design_decisions`, `run_surface` and
   `workflow_seam` markers.
3. **Vocabulary** (after ~250):
   - **Code module** (D1, D2 in one paragraph: flat, inferred, one owner per
     path, a test in several modules);
   - **Work package** (M1–M10 / Mx.y; Gradle, Go and Python "module" keep
     their meaning);
   - *Mode and policy*: add `module`;
   - *Cadence*: "under `auto` and `module`".
4. **Process map** (299-315):
   - the `POLICY` line gains `module`;
   - `internal/registry [M2.1, M2.6, M2.7] nine tables: … + modules`;
   - a new line `internal/modules [M2.7] providers · modules
     --list|--explain|--scan · Widen`;
   - the selectr line gains `· --widen-modules`.
5. **Registry tree** (346-365) gains `_modules.yaml`, and the config comment
   adds `module` to `mode`.
6. **Config block** (370-382): `mode:` comment lists `module` (needs
   `full_run_every`; never written by `detect --write`).
7. **Where state lives** (416-431):
   - a new row for the modules table (the D1 schema: generated by `modules
     --scan --apply`, with agent rows carried over unchanged and never
     re-inferred, plus the hand block);
   - the contract paragraph covers `_modules.yaml`;
   - the policy ledger gets `approved_by.mode: auto|module`;
   - the completion row lists `module`.
8. **Line-protocol index**:
   - a new row for `MODULE:` `MODULES:` `MODULE_OF:` `MODULE_CONFLICT:`
     `MODULE_UNRESOLVED:` `MODULE_REFUSED:` `MODULES_DRIFT:` `WIDENED:`
     `WIDEN_FULL:` (with the five reasons) → component *Code modules*;
   - the selector row gains `module(…)`;
   - the feedback row gains `WIDEN_SCORED:`;
   - the policy row gains `POLICY:module|…`.
9. **Decision 20** (after 19): **"Code modules are flat, data-derived
   structure and a cut knob — not labels, tiers of trust or a hierarchy."**
   - Modules are inferred from build files, packages, the codemap and agent
     proposals with `by:`, then persisted and inspectable with hand
     overrides.
   - It re-checks t1812:55-56 explicitly: the graded walk stays, and widening
     is one more cut knob applied after it that only adds tests.
   - Modules stay separate from areas.
   - Rejected alternatives:
     - areas as modules (flat broad-only scope, refused on unit blocks);
     - hand-declared labels (a second, drifting definition);
     - **a built-in module → submodule hierarchy**, which needs nested ids, a
       level switch, parent expansion and per-level evidence for a choice
       measurements have not asked for. It is reconsidered only if t2131_12
       shows flat modules give runs that are too broad.
10. **M2 table** (705), new row **M2.7 Code modules**:
    - **scope:** D1–D5, plus the `testmap:module` key as a named extension of
      M2.2, and area `modules:` references as a named extension of M2.5
      (`areas --import-codemap` stays as landed);
    - **component:** `component_code_modules`;
    - **owns:** `registry/modules*.go`, `internal/modules/**`;
    - **provides:** the table, membership, path lookup and `Widen` to M3.1,
      M4.1, M4.4, M4.5, M6.x, M8.4 and M8.5;
    - **depends:** M2.1, M2.2, M2.3, M2.5, M2.6.

    A sentence under the table names the named extensions elsewhere and their
    deliverers: t2131_7, _8, _9, _10 and _11.
11. **Interfaces** (826): the registry row says "nine tables (M2.1, M2.6,
    M2.7)". A new row: modules table / lookup / membership / `Widen` /
    `MODULE_*` / `WIDEN*` lines, consumed by M3.1, M4.1, M4.4, M4.5, M6.1,
    M6.4, M6.5, M8.4 and M8.5.
12. **Waves.** C gains M2.7. A sentence after the table: the consumers land
    in D (`--widen-modules` with M4.4) and G (`module` mode with M8.5).
13. **Named follow-ups:**
    - smarter reach gated on t2131_12's measured `WIDEN_FULL` share:
      conservative inclusion of uncertain files, per-language clearing to a
      fixed point, and a base-revision graph for deletions and renames;
    - `auto` learning `module`;
    - additional module levels, only if measurements show flat modules are
      too broad.
14. **Data flow** (922-941): two `POLICY:module` lines, the widened run and
    `widen_full`.
15. **Run surface:**
    - forms add `ait test --widen-modules`;
    - step 6 gets one sentence pointing at the `module` arm;
    - step 7 adds `WIDENED:` / `WIDEN_FULL:` and the reason token, with a
      `WIDEN_FULL` running as `--all` does;
    - the output contract adds `POLICY:…|module|…` and the two lines.
16. **Workflow-seam *Completion policy*** (1940-1960): one sentence on the
    third flip shape.
17. **Go engine package list** adds `internal/modules`. The **verb table**
    adds `modules` (`--list`, `--explain <path|test-id>`, `--scan [--apply]`;
    "M2.7's named extension of the table, like `policy`"). `check` stays
    under 300 ms including `MODULES_DRIFT`.
18. **Registry loader:** "eight" → "nine tables" (adding M2.7's modules
    table), and the reserved names add `_modules.yaml`.
19. **New component** `### Code modules *(M2.7; consumers M3.1, M4.1, M4.4,
    M4.5, M6.x, M8.4, M8.5)*`, inside section markers, after `<!-- /section:
    component_suite_registry -->`. Sub-blocks:
    - *Table and names* (D1);
    - *Providers and ownership* (D2, with the table and its limitations);
    - *Module deps* (D3);
    - *The verb* (`modules`, the D6 lines; `--scan --apply` drift-gated like
      `scan --apply`, `WROTE:` reused);
    - *Freshness*: `MODULES_DRIFT:` by live re-inference over the cached
      `deps.Scan` inside `check`'s budget; consumers treat drift as
      `modules_stale`; if t2131_3 measures it over budget, detection moves to
      the consumers, still failing toward full;
    - *Membership* (D4);
    - *Widening* (D5, D7, and the D11 examples verbatim).
20. **Scoped-row registry and areas** (2853-2857): D10's `modules:`
    references and their `DEAD_SCOPE` shape. The `--import-codemap` bullet
    (2917-2922) gains one sentence: it keeps writing `<path>/**` globs and
    never module references, so the import's breadth is independent of the
    modules table. Include the narrower same-name override check from D10 as
    an example. There is no M2.5 deviation.
21. **Runner contract** (3003-3015):
    - `group_by: module` (M2.7's named extension of M3.1, delivered by
      t2131_10) groups by the test's path-containment module through the
      `registry` lookup, with no `deps` import;
    - a test without one stays in the runner's ungrouped group;
    - a test in several modules lands in exactly one group;
    - `{module}` follows D6.
22. **Selector** (3266-3296): one sentence on the widening stage and the
    paired record (D7). **Engine `test` composite** (3427-3446): the
    `--widen-modules` flag; `WIDEN_FULL` continues as the `--all` path;
    `--explain --widen-modules` stops after `select`.
23. **Feedback tools:**
    - the paired scoring and `WIDEN_SCORED:<records_n>|plain_fn:<n>|widened_fn:<n>|full:<reason>=<n>,…`;
    - `predictions.yaml` rows get an optional `widened {added_n, fn,
      full?}`;
    - the paragraph **"Which prediction set readiness judges"** (D8);
    - `cadence_declared` applies to `auto` and `module`;
    - `POLICY:module|…`.
24. **Completion policy component:** `mode full|selected|module|auto`;
    `full_run_every` is required for `module`; `module` is never written by
    `detect --write`; `MODE:<full|selected|module>`.
25. **Auto completion policy and cadence:** a new paragraph, "**The `module`
    arm**" (D9).
26. **Onboarding verbs** (+ one sentence in the onboarding-skill component):
    - `detect` / `inventory` print `MODULES:` and `MODULE_UNRESOLVED:` to-dos
      (t2131_9);
    - the agent review writes `provider: agent` rows and `testmap:module`
      lines, can be rerun, and has no human gate;
    - the `module` mode is enabled only through t2131_11.
27. **Tradeoffs:**
    - "eight tables, two generated files" → "nine tables, three generated
      files";
    - a new `tradeoff_flat_modules`: no small-region-plus-parent choice,
      accepted;
    - a new `tradeoff_module_reach_full_fallback`: any in-repo uncertainty
      forces full; measured per reason; relieved only by the gated
      follow-ups.

## Implementation — Part B: decomposition revision

Each task file is edited in place with `updated_at` bumped. Every
hierarchy-only requirement (nested ids, the level switch, parent expansion,
the fold rule, `completion.widen`, `group_by: submodule`, per-level
acceptance) is removed. Dependency holds, `depends:`, statuses and
unrelated requirements are kept. Each body that changes gains one line:
"Revised 2026-10-24 (user decision): flat code modules, no submodules; see
the proposal's component *Code modules*."

28. **Parent task `aitasks/t2131_testmap_code_modules_tier.md`:**
    - the Goal says "a code-module grouping … widened to every test of the
      code modules a change affects" (drop "two-level", "module →
      submodule");
    - the codemap bullet keeps its facts. "Flattens `children`, losing the
      hierarchy" now reads: the area import keeps doing that, unchanged, and
      the modules provider takes every entry as a flat module;
    - decisions 1a (`--widen-modules`), 4 and 5 are updated ("At most two
      tiers" and "module / submodule" give way to the flat rule), keeping the
      2026-10-23 user-confirmed text with a dated revision note;
    - the expected-decomposition wording is updated.
29. **Parent plan `aiplans/p2131_testmap_code_modules_tier.md`:**
    - a revision note in *Context*;
    - defaults are rewritten with **their numbers kept**, so child
      references stay valid:
      - 1: unchanged except the "nine / three" counts;
      - 2: verb unchanged;
      - 3: freshness unchanged;
      - 4 → "Names" (flat, area-name rule, no qualified form);
      - 5 → D2's table;
      - 6: unchanged;
      - 7 → D5 (reach and widening as one operation);
      - 8 → D4;
      - 9 → D10 (area references only; the codemap import is unchanged);
      - 10 → D6/D7 (surface, execution, paired record);
      - 11 → D8/D9 (no `completion.widen`);
      - 12 → `group_by: module` only;
      - 13 → decision 20, incl. the rejected hierarchy;
      - 14: unchanged;
    - the decomposition table scope cells for _1, _3, _4, _6, _7, _8, _10
      and _11, and the template's Reality-check / acceptance lists, lose
      every submodule item. The acceptance lists gain the D11 examples where
      they belong (_3: example 4 and the root `:`; _4: examples 6 and 7;
      _5: example 3; _6: examples 1, 2 and 5, plus 6's root-package widening; _7: the full-path execution and the
      recording-conflict wording).
30. **This task `t2131_1`:** the body reflects the flat design (the Key
    Files bullets for ids, `--widen`, `completion.widen` and `group_by`).
    The plan file is replaced by this plan through externalization.
31. **t2131_2 (rename):** the collision paragraph says the code-module
    feature introduces "module" only. The work-package rename (both
    work-package tiers) is unchanged.
32. **t2131_3 (table and core providers), task and plan:**
    - (4) becomes flat names;
    - the codemap provider is "every entry at any depth is a module named
      `codemap:<root>`, deepest root wins". Duplicate entry names across
      parents are irrelevant to module names; the entry name is evidence;
    - the Gradle provider is "every included project at any depth, named
      `gradle:<path>`", with the fold rule removed;
    - the D2 name rule: reserved prefixes, `.` for the root directory, and
      `MODULE_REFUSED:` for `unnameable` and for a subtree root at the
      repository root (the Gradle `:`, a codemap root entry);
    - add the ownership rule and the conflict aggregation;
    - acceptance:
      - "three-tier input refused" → "a nested `submodules:` / `children:`
        key refused";
      - plus example 4, the root `:` and a codemap root entry refused as
        `repository_root`, a codemap with duplicate names across parents
        (distinct `codemap:` names), a hand name with a reserved prefix
        refused, and the hand/agent name collision;
    - the plan's `Module{…Submodules…}` struct loses `Submodules` and gains
      `Root`.
33. **t2131_4 (Go/Python), task and plan:**
    - the provider rules become "every package is a module named `go:<dir>`
      / `py:<dir>` (`/` written as `:`, the root directory as `.`). It owns
      only the package's own source files in its directory (`*.go`, or
      `*.py` / `*.pyi`), never a subtree";
    - a directory with an unnameable character is refused;
    - acceptance gains D11 example 6 (distinct `go:.` and `go:tool`, ordinary
      widening over the root package, `README.md` unmapped) and example 7
      (`a/b/` vs `a.b/` distinct, `a:b/` refused).
34. **t2131_5 (membership and areas), task and plan:**
    - it gains example 3 as an acceptance item;
    - its default-9 part shrinks to area `modules:` references
      (effective-path expansion, the `DEAD_SCOPE:…|module:<name>` refusal);
    - **the codemap-import change is removed**: the import stays as landed,
      writing globs, and the "codemap import writes refs" acceptance item
      becomes "the import still writes `<path>/**` globs";
    - add D10's narrower same-name override check as acceptance (an imported
      area keeps `services/api/**` breadth under a hand `api` over
      `public/**`).
35. **t2131_6 (reach and widening), task and plan:**
    - the library becomes the one `Widen` operation (D5) with its evidence
      records;
    - drop "at level `module` or `submodule`" and "submodule vs module
      level";
    - acceptance gains examples 1, 2 and 5;
    - keep every per-guard fixture and mutant.
36. **t2131_7 (selector), task and plan:**
    - `--widen submodule|module` → `--widen-modules`;
    - `WIDENED:<modules_n>|<added_n>`;
    - the reason token with `via`;
    - `WIDEN_FULL` = the canonical full run;
    - the recording-wording rule;
    - the paired record without a level;
    - the D8 readiness rule in M4.4 scope;
    - widen outcomes recorded automatically under `module`.
37. **t2131_8 (completion), task and plan:**
    - drop `completion.widen` everywhere (the enum change only);
    - the front passes `--widen-modules`;
    - the D8/D9 text;
    - keep its holds and `depends:`.
38. **t2131_10 (batching), task and plan:** `group_by: module` only; drop the
    submodule golden.
39. **t2131_11 (enable), task and plan:** it writes `completion.mode: module`
    + `full_run_every`, with no `completion.widen`.
40. **t2131_9 and t2131_12:** read in full and changed only if they rely on
    levels. t2131_12 gains "decide whether flat modules are too broad, the
    trigger for reconsidering levels" among its measured decisions.

### Post-phase (risk mitigations)

1. [proposal_consistency_audit] Before the commit, run a scratchpad script
   over the proposal **and** every Part-B file. It fails on any of:
   - a remaining `submodule` in the code-module sense, a `<module>/` id,
     `completion.widen`, `group_by: submodule`, `--widen ` followed by a
     level, "parent-module", "two-level" or "two tiers" in the code-module
     sense (allowlist the work-package uses that t2131_2 owns, listed
     explicitly);
   - any statement that `areas --import-codemap` writes module references,
     or any `<parent>-<child>` naming rule;
   - a generated module name without its `codemap:` / `gradle:` / `go:` /
     `py:` prefix in an example;
   - a new prefix missing from the index or from the *Code modules*
     component;
   - unbalanced `section:` markers;
   - a remaining "eight tables" / "two generated files";
   - `_modules.yaml` missing from the tree, *Where state lives* or the
     reserved names;
   - `modules` missing from the verb table.

   Fix and re-run until clean. The script and its output go into the Final
   Implementation Notes.

## Commit and notes

41. Step 8 review first. Then, path-scoped:
    - `git commit -F - -- aidocs/testing_engine/n014_explorer_006_proposal.md`
      with `documentation: Amend test-map proposal for flat code modules
      (t2131_1)`;
    - `./.aitask-scripts/aitask_task_commit.sh -m "ait: Revise t2131
      decomposition for flat code modules" <each Part-B task/plan path>`
      (never this task's own plan, which is committed by the plan step), then
      `./ait git show --stat`.
42. **Contract notes.** Use `./ait note <id> --from 2131_1 --file -` with a
    quoted heredoc. Each note is advisory, written as of `<sha>` and names
    the sections. Each one **withdraws the earlier note's two-level
    statements explicitly** and adds the newly fixed shapes:
    - **t1853:** M2.7 row, *Code modules*, the D2 provider rules, names
      (`<provider>:<native id>`, `MODULE_REFUSED:`) and ownership, the flat
      hand block, agent rows in `_modules.yaml`, area `modules:` references.
      It also withdraws the earlier note's codemap-import deviation: the
      import stays as landed;
    - **t1855:** `--widen-modules` (replacing `--widen submodule|module`),
      `WIDENED:<modules_n>|<added_n>`, the reason token, the canonical-full
      execution, the recording wording, the paired record without a level,
      the D8 readiness rule, `WIDEN_SCORED:`;
    - **t1857:** the `MODULES:` shape and the agent intake left to t2131_9.
      It also withdraws the earlier "the import's level-0 output will
      change" statement: `areas --import-codemap` is unchanged;
    - **t1859_4:** no `completion.widen`; `MODE:<full|selected|module>`;
    - **t1859_5:** the D9 order, the `approved_by.mode` match, the D8 rule;
    - **t1854_11:** `group_by: module` only; the `{module}` refusal.

    Each must return `NOTE_APPENDED:`.

## Verification

- The post-phase audit is clean.
- Each D11 example is re-derived by hand from the written rules and gives
  one affected set and one test set that match the text. Example 6 yields
  distinct names or an explicit refusal in every case. D10's override check
  keeps the imported area at `services/api/**`.
- The proposal states one `Widen` operation, with no level, no parent
  fallback and no hierarchy field.
- The WIDEN_FULL execution sentence appears in *Code modules*, the `test`
  composite and the Run Surface, all naming `--all`.
- The recording wording does not forbid prediction records.
- D8 is in *Feedback tools*; D9 is in *Auto completion policy*.
- `grep -c '^depends:\|^status:'` on every revised child is unchanged
  against `git show HEAD:` (holds and deps preserved).
- `NOTE_APPENDED:` for all six notes.

## Risk

### Code-health risk: low
- About 27 proposal sites and about 20 task/plan files change in one pass.
  Internal drift (a leftover submodule rule, an index miss) is plausible.
  This is documentation only. · severity: low · → mitigation: inline
  post-phase proposal_consistency_audit
- Editing sibling task and plan files touches shared task data. Each is
  committed path-scoped, `depends:`/`status:` are read back, and no sibling
  is `Implementing`. · severity: low · → mitigation: none

### Goal-achievement risk: medium
- The per-package Go/Python rule may be too fine, and a large Gradle project
  or codemap entry too coarse. The flat model has no built-in fix. Bounded:
  codemap, agent and hand refine boundaries, and t2131_12 measures breadth.
  Levels are a gated follow-up. · severity: medium · → mitigation: none
  (covered by t2131_9 / t2131_12)
- Line shapes fixed before code exists may prove the wrong shape. Each
  child's Reality check amends the proposal. · severity: medium · →
  mitigation: none (covered by the children)
- The conservative readiness rule may make `module` slow to become
  admissible. It fails toward full, and t2131_12 measures it. · severity:
  low · → mitigation: none

### Planned mitigations
- timing: post-phase | name: proposal_consistency_audit | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: internal inconsistency across the proposal and the revised task/plan files (code health) | desc: scripted pre-commit audit for leftover hierarchy terms, index/component/marker/count consistency

## Step 9 reference

Shared post-implementation (task-workflow Step 9). Current branch, no merge.

## Post-Review Changes

### Change Request 1 (2026-10-25 00:40)
- **Requested by user:** three review concerns. (1) `ait test --widen-modules`
  was advertised, but the bash front's flag list (component *Test entrypoint*)
  lacked it, and no child owned parsing and forwarding it. (2) The `module` arm's
  ordered steps put `NOT_YET → full` before "a later unmet criterion →
  `POLICY_DEMOTED`". A first-match implementation could never reach the
  demotion for an approved policy, so the approval would never be cleared.
  (3) t2131_2 claimed that every remaining "submodule" is the work-package
  sense, which ignores the two intentional code-module uses.
- **Changes made:**
  - **Proposal.** The front's flag list gains `--widen-modules`, parsed and
    forwarded unchanged with no widening logic. The M2.7 consumer sentence
    names the front (t2131_7). The `module` arm is restructured into two
    exclusive admission branches. "Not approved" leads to `not_yet` (no
    write) or the flip. "Approved" leads to `POLICY_DEMOTED`, with
    `approved_by` cleared, or continues. Approved means `approved_by` with
    `mode: module`. The cadence, widen-fallback and widened-run steps
    follow.
  - **t2131_7 task and plan.** They own the front's flag parsing and
    forwarding plus a fake-engine invocation check in
    `tests/test_ait_test_entrypoint.sh`. The dependency hold gains **M5.1
    (t1856)**, and the Reality check stops if M5.1 has not landed.
  - **t2131_8 task and plan.** They carry the same two-branch order. The
    matrix gains "approved + newly unmet criterion → demotion and approval
    cleared, never `not_yet`".
  - **Parent plan.** Default 10 records the front forwarding. Default 11
    records the two-branch order. The decomposition row for _7 gets hold
    `M4.1, M4.4, M4.5, M5.1` and the front in its scope. The template
    Reality-check and acceptance lists for _7 and _8 are updated.
  - **t2131_2 task and plan.** They keep the rejected-hierarchy wording
    (decision 20) and the refused `submodules:` / `children:` keys as
    written, listed under "Keep as is".
  - **Contract notes (step 42).** They gain a seventh recipient, **t1856
    (M5)**: wire the M5.1 id into t2131_7's hold, and the front's flag
    table gains `--widen-modules`. The t1859_5 note points out that the
    `auto` arm's prose has the same first-match ambiguity (advisory only).
- **Files affected:** `aidocs/testing_engine/n014_explorer_006_proposal.md`;
  `aiplans/p2131_testmap_code_modules_tier.md`;
  `aitasks/t2131/t2131_{2,7,8}_*.md`; `aiplans/p2131/p2131_{2,7,8}_*.md`.

## Final Implementation Notes
- **Actual work done:**
  - **Part A, the proposal.** Every D1–D11 site was amended, plus Change
    Request 1:
    - vocabulary (*Code module*, *Work package*, `module` under *Mode and
      policy* / *Cadence*);
    - invariant 1, decision 20 and section-marker dimensions;
    - the process map, registry tree, config block, *Where state lives* and
      the line-protocol index;
    - the M2.7 row, its consumer sentence, interfaces, waves and named
      follow-ups;
    - data flow, Run Surface forms / step 6 / step 7 / output contract, and
      the workflow-seam policy;
    - the Go package list, verb table and budget, and the loader's "nine
      tables" / reserved name / `modules:` hand key;
    - the new component *Code modules* (table and names, providers and
      ownership, deps, the verb, freshness, membership, widening, worked
      examples 1–6, tests);
    - area `modules:` references (`areas --import-codemap` unchanged), the
      runner `group_by: module`, the selector, the `test` composite and the
      front's flag table;
    - feedback tools (paired scoring, `WIDEN_SCORED:`, "Which prediction set
      readiness judges");
    - the completion policy component, the `module` arm (two exclusive
      admission branches), onboarding verbs and skill, and two tradeoffs.
  - **Part B, the task data.** Revised for the flat design: the parent task
    and plan (defaults rewritten with numbers kept), this task, and the
    t2131_2 … t2131_12 tasks and plans. Every task's `depends:` / `status:` /
    `children_to_implement:` was verified unchanged against `HEAD`.
- **Deviations from plan:**
  - The design was revised **four times during planning** at the user's
    review, and those revisions *are* the plan:
    - the two-level design was replaced by flat modules;
    - submodule reach evidence, readiness evidence and the full-fallback
      execution were defined;
    - the area import stays as landed, with collision-safe provider-prefixed
      names;
    - root packages became package-bounded (`go:.`) instead of refused.
  - One more review round (Change Request 1) added the front flag ownership
    (t2131_7 now held on M5.1 / t1856), the two-branch `module` order and the
    t2131_2 wording fix.
  - Example 7 (name safety) went into the provider acceptance lists and the
    component's test list rather than as a seventh worked example.
- **Issues encountered:**
  - The audit's first run flagged 4 lines: revision-note continuation lines
    and the codemap file's own `two-tier` shape. They were resolved with an
    explicit `(path, line prefix)` allowlist instead of loosening the
    patterns.
  - A manual pass over every remaining "submodule" in the proposal confirmed
    that each one is the work-package sense, the rejected alternative or the
    refused key.
- **Key decisions:**
  - one spelling, `--widen-modules`, a plain flag;
  - generated names are `<provider>:<native id>` (`/` → `:`, the root as
    `.`), so they cannot collide;
  - subtree providers (codemap, Gradle) use deepest-root ownership;
    package providers (Go, Python) own only their own source files;
  - only subtree roots at the repository root are refused;
  - module references in areas expand to effective paths, while the codemap
    import keeps writing globs;
  - readiness under `module` is judged on widened sets, conservatively;
  - `POLICY_FLIPPED:module->module` follows `auto`'s "mode → what it runs"
    convention.
- **Upstream defects identified:** None
- **post-phase proposal_consistency_audit:**
  - Script, kept in the scratchpad: `audit.py`.
  - It checks:
    - hierarchy leftovers (`<module>/`, `completion.widen`, `group_by:
      submodule`, `--widen <level>`, `module|submodule`, parent-module,
      two-level / two tiers / two-tier, `<parent>-<child>`, "import writes
      refs", "deeper folds", `WIDENED:<level>`, `Widen(level`) across the
      proposal and all 24 Part-B files, with an explicit 4-entry allowlist;
    - each new prefix appears in both the index and the component;
    - `WIDEN_SCORED:` appears in the index and in feedback tools;
    - section markers are balanced;
    - no "eight tables" / "two generated files" remains;
    - `_modules.yaml` appears in the tree, state table and reserved names;
    - `modules` appears in the verb table;
    - generated names in the examples carry their prefix;
    - the `WIDEN_FULL` → `--all` sentence appears in its three homes.
  - Final output: `AUDIT:PASS|0 findings`.
- **Notes for sibling tasks:**
  - The proposal's component *Code modules* is now the contract. Where a
    child body and the proposal differ, the proposal wins, and a child whose
    Reality check finds a rule wrong amends the proposal in its own change.
  - Every child body carries a dated "Revised 2026-10-24" marker. The
    defaults keep their numbers.
  - **t2131_2:** the proposal has grown by about 450 lines, so re-measure the
    rename inventory. The two code-module uses of "submodule" stay.
  - **t2131_3:** the `Module` struct is flat
    (`{Name, Provider, By, Root, Paths, Gradle, Evidence, Deps}`).
  - **t2131_7:** now also held on M5.1 (t1856).
  - **t2131_8:** implement the two-branch admission order. The `auto` arm's
    prose (M8.5) still lists `NOT_YET` and "a later unmet criterion"
    separately, the same first-match ambiguity. t1859_5 was told; it is
    advisory only.
