---
Task: t2131_testmap_code_modules_tier.md
Base branch: main
Output branch: main
---

# Plan: t2131 — Testmap code-module tier (coarse planning pass)

## Context

t2131 adds a two-level **code-module tier** (module → submodule) to the test map.
It sits between "tests mapped to the changed files" and "the full suite": a
selection can be widened to every test of the code modules a change affects,
and completion can run at module scope. Today:
- every map edge is test → source file;
- selection has two outcomes, selected or full;
- the proposal (`aidocs/testing_engine/n014_explorer_006_proposal.md`) has no
  module or tier concept ("tier" occurs zero times, and every "widen" there
  means something else).

The task body records five user-confirmed decisions (priorities, evidence-based
reach, multi-module membership, modules ≠ areas, naming) and an expected
decomposition. This session does only the **coarse planning pass**, the way the
M2, M3 and M8 parents did theirs:
- one child per slice of scope;
- a coarse plan per child recording scope, owned files, provided and consumed
  interfaces, acceptance list and the mandatory **Step 0 — Reality check**;
- children whose providers have no child id yet are `Postponed`, with a
  **Dependency hold** paragraph.

The session stops at the child checkpoint. No code is written.

**Decisions taken in this session (user, 2026-10-23):**
- The prose rename uses **"work package" for both tiers**: "work package M2",
  "work package M2.5", and "child work package" only where the tier matters.
- A trailing **retrospective-evaluation child** is part of the split.
- The trail (`art:trail-testmap-feature`) is refreshed by a **separate
  `/aitask-trail` run** after this pass.
- **Blocking review concerns, verified and folded in:**
  - `module` mode applies the full-run cadence (default 11);
  - the onboarding write that enables `module` mode waits for module-mode
    support (t2131_11);
  - the selector captures paired plain and widened prediction records that
    scoring reads (t2131_7).
- **Reach is simplified for the initial scope** (default 7):
  - it uses the current dependency graph only;
  - it falls back to the full suite whenever deletions, renames or dependency
    uncertainty (indirect dependencies included) prevent safely bounding the
    affected modules. The absence of a resolved edge is never proof of
    independence;
  - there is no historical graph and no per-language uncertainty clearing;
  - fallback reasons are recorded and their frequency measured. Smarter
    analysis comes later, and only if the measurements show excessive
    fallbacks.

  The required correctness is unchanged; only the initial mechanism is
  simpler.

**Sequencing** follows the submodule-granular wave rule (memory
`feedback_testmap_parents_in_strict_wave_order`):
- The table, provider, membership and reach children consume only landed
  providers (M2.1, M2.3, M2.5, M2.6, M3.1), so they are admissible now.
- The selector, completion and onboarding children consume work packages whose
  parents are undecomposed (M4 is t1855, M6 is t1857), so they are held.

**Automation-first** (memory `feedback_testmap_automation_first_no_human_review`):
- No verb, rule or gate in any child may require a human action.
- Agent output keeps its `by:` provenance.

**Inbox.** t2131 has no unread notes. At creation it already sent advisory notes
to t1855 (M4), t1857 (M6) and t1859_4 (M8.4). It has not notified t1853 (M2) or
t1859_5 (M8.5).

**Plan review.** An agent review of the first draft found 11 problems. All are
folded in:
- the table's home;
- an automated route into `module` mode;
- agent proposals as a provider;
- the codemap duplicate definition;
- what an annotation may drop;
- the budget;
- the stale-table route;
- the Gradle root project;
- the deps;
- the split of the table child and of the rename;
- the create-time `--status`.

## Repository reality anchors (verified 2026-10-23, main @ ee468201f)

| fact | state now |
|---|---|
| `deps.Graph` | `Modules()` has **no non-test caller**; `ModuleOf` has one (`cost/implicit.go:157`); `Reverse` none; `Closure` in `classify.go:370`, `cost/eligibility.go:276,300`; `Opaque` + `Facts().Unresolved` in `cost/eligibility.go:338-343`. The graph is built from **one tree**, so a deleted file has no node. The Gradle root project `:` has `Dir ""`, and `within("")` contains every path (`deps/graph.go:153-155`). |
| unresolved refs | `FileFacts.Unresolved` holds refs and imports that matched no file, `<dynamic>[/<tail>]` bash sources, and Go inputs outside the universe (`deps/deps.go:53-67`). |
| Gradle dynamic | an unreadable dependency block sets `m.Deps = allNames()` (`deps/gradle.go:273`) and marks the build file opaque `gradle-dynamic` (`deps/resolve.go:111-114`). |
| Go / Python packages | known only during resolution: `goResult` (`deps/golist.go:80-85`) and `pyPackage`/`pyModel` (`deps/python.go:1511-1523,1756-1763`) are **discarded**, so the graph exposes no package tier. |
| import direction | `registry ← annot ← deps ← {classify, cost}`. `runner` imports `registry`, `annot` and `axes`, never `deps`; its grouper is `func(registry.ID) (string, error)` (`runner/describe.go:336`). |
| registry loader | `RegisterFile` / `RegisterHandTable` / `RegisterPostLoad` (`registry/load.go:113-128`). An `_`-prefixed file without a loader is refused (`load.go:184-186`); an unregistered hand key is "unknown key" (`load.go:317-327`). `_scanned.yaml` is decoded with `KnownFields(true)` (`load.go:407`), so a new row field is a schema change in `ScannedRow` (`registry/scan.go:29-36`). |
| generated+hand precedent | `_scoped.yaml` + `areas:`/`scopes:` (`registry/scoped.go:122-182,408-413`): rows carry `File`, `WithGenerated` gives `check` a live view, and writes are drift-gated (`registry/scan.go:199-287`). |
| areas | flat `Area{Name, Globs, From}` (`scoped.go:62-66`). Names refuse `/` (`checkAreaName`, `scoped.go:334-342`). Area, scope and trigger are refused on unit-kind blocks (`scoped.go:669-672`). |
| codemap import | `ReadCodemap` flattens `children` and requires globally unique names (`registry/areas_import.go:79-126`). The generator names children by bare subdirectory, so two `tests/` children collide (`aitask_codemap.py:180,195`). `onboard detect` is still a stub (`verbs.go:57`). |
| annotation grammar v3 | the key switch is at `annot/grammar.go:413-533`. A new key also needs a `Unit` field (48-65), `File.Annotated()` (80-89), `registry.UnitAnnotation` (`registry/inputs.go:33-63`) and `annot/source.go:toRegistry` (141-199). The rewriter writes **only `covers` lines** (`annot/rewrite.go:304-325,490-521`). |
| verb table | frozen to the proposal list by `TestVerbTableMatchesProposal` (`cmd/ait-testmap/main_test.go:21-52`). `select`, `explain`, `test`, `readiness` and `onboard *` are stubs (exit 64). `internal/selectr` does not exist. |
| budgets | `scan` / `check` / `stale --task` < 300 ms; `select` < 200 ms warm, < 1.5 s cold (proposal 2043-2046). |
| prediction record | Every task-scoped selection writes the task's prediction record, newest wins per task (proposal 245, 917). The record is owned by M4.1 (735, 835) and scored after every full run by M4.4 `score`. Scoring writes `costs/predictions.yaml` (`PREDICTION_SCORED:` / `PREDICTION_FALSE_NEGATIVES:` / `PREDICTION_MISSED:`; 3392-3394). |
| completion and cadence | `Completion{Mode,…}` is parsed, and the enum `full\|selected\|auto` is validated at `registry/config.go:202`. **Nothing reads it.** `selected` needs a human `run_gate_admission.approved_by`, otherwise it demotes. `auto` is engine-approved in `costs/policy.yaml` (proposal 3848-3866). The `full_run_every {tasks, selection_ratio_above, days}` triggers and `READINESS:cadence_declared` are scoped to `auto` only (239, 1656, 1009, 3419, 3856). Their implementation is M8.5's `internal/feedback/cadence.go` (788). |
| data files here | there is no `aitestmap/` at the repo root and no `aitasks/metadata/code_areas.yaml` (only `seed/code_areas.yaml`, with `areas: []`). The engine never runs `aitask_codemap.sh` (Invariant 5). |
| M3 grouping | `group_by: none\|file\|dir\|regex:<re>` (M3.1, landed, `p1854_1` D4). The `{module}` placeholder exists only in the gradle-class adapter plan (`t1854_11`, `Ready`, depends `t1854_6`). |
| downstream | t1855 (M4) and t1857 (M6) are `Ready` and **undecomposed**. t1859_4 (M8.4) and t1859_5 (M8.5) are `Postponed`, held on M4.4 and M5.x. t1853 (M2) is open only for `t1853_7` (Postponed). The only in-flight topic task is t1854_7 (the runner recursion guard), with no overlap. |
| `aitask_create.sh` | accepts `--status` (line 190); `Postponed` is validated (line 2225). `aitask_update.sh --deps` replaces the whole list. |
| duplicates | none: `module tier`, `code module`, `--widen`, `modules.yaml` and `testmap:module` match only t2131 and its three notes. |

## Design defaults this pass fixes (written into the proposal by t2131_1)

These are the starting positions every child body records. t2131_1 writes them
into the proposal. A later child whose Reality check finds one wrong amends the
proposal in the same change and notes its siblings.

1. **Home: table in `registry`, inference above `deps`.**
   - `registry` (new `registry/modules*.go`) owns:
     - the schema and the `_modules.yaml` loader and renderer (`KnownFields(true)`);
     - the hand `modules:` table;
     - area `modules:` references;
     - membership;
     - the `MODULE_*` check rules;
     - path → module lookup.
   - A new package `internal/testmap/modules` (above `deps`) owns the providers,
     the `modules --scan` writer and the reach and widening library.
   - New work package **M2.7 — Code modules** owns both. "Eight tables" becomes
     nine; "two generated files" becomes three (proposal 4664).
2. **Verb `modules`** (added to the proposal verb list and the frozen test):
   `--list`, `--explain <path|test-id>`, and `--scan [--apply]`, which writes
   `_modules.yaml` and is drift-gated like `scan --apply`.
3. **Freshness.**
   - **Detection.** `check` gains `MODULES_DRIFT`, like `SCAN_DRIFT`: a live
     re-inference over the cached `deps.Scan`, within the 300 ms budget.
   - **Consumers.** `select --widen` and `module` mode treat a drifted table as
     `WIDEN_FULL:modules_stale`.
   - **Over budget.** If t2131_3 measures the check over budget, drift detection
     moves to the consumers only, still failing toward full.
4. **Ids and tiers.**
   - A module name and a submodule name are each an id fragment (the
     area-name rule).
   - The qualified form `<module>/<submodule>` appears only in output and in
     `testmap:module` values.
   - YAML nests submodules under their module. A submodule has no submodules,
     so the schema enforces two tiers.
   - Submodule names are unique within their module only.
5. **Providers, in precedence order:**

   | rank | provider | maps to |
   |---|---|---|
   | 1 (wins) | hand `modules:` overrides | project-authored |
   | 2 | `provider: agent` proposals | carry `by: agent:<string>`; the slot is reserved by t2131_3 and written by t2131_9 |
   | 3 | the codemap (read directly, never run) | parent → module, child → submodule |
   | 4 | Gradle | `:a` → module, `:a:b` → submodule, deeper folds into `:a:b`; **the root project `:` is not a module** |
   | 5 | Go | `go.mod` module → module, first package level → submodule |
   | 5 | Python | top-level package → module, first subpackage → submodule |

   - Every row records `provider:` and its evidence.
   - A disagreement is always reported as `MODULE_CONFLICT:` with both sides'
     evidence, even when precedence settles it.
   - A path that no provider covers stays unmapped. There is no guessing
     fallback.
6. **Module → module edges.** `modules --scan` records `deps:` per module, with
   one file-level evidence pair each. These edges are for inspection only;
   reach (7) never trusts them.
7. **Evidence-based reach, initial mechanism: the current graph plus a
   conservative fallback.**
   - **The graph.** Reach reads only the **current** (post-change) dependency
     graph.
   - **The affected set** is:
     - the modules containing a changed path;
     - every module with a file in the **transitive** reverse file closure of
       the changed paths over resolved edges. Indirect dependents count.
   - **What does not pull modules in.** An edit inside a module that nothing
     outside it reaches pulls in no dependents. Reach never recurses through
     module-level deps for their own sake.
   - **When the bound is unsafe, run full.** The absence of a resolved edge is
     never proof of independence. So the affected set is used only when no
     uncertainty could carry the change's impact outside it. Otherwise the run
     falls back to the **full suite** and prints
     `WIDEN_FULL:<reason>|<path>`:
     - `deleted_path` / `renamed_path`: the change surface deletes or renames
       a path (the current graph has no node for it);
     - `unmapped_path`: a changed or reached path lies outside every module,
       including root-only Gradle paths;
     - `uncertain_reference`: any in-repo file anywhere carries dependency
       uncertainty. That means an `Unresolved` entry naming an in-repo
       target, an opacity reason, a `<dynamic>` source, or a `gradle-dynamic`
       build. Without clearing, no uncertain reference can be shown not to
       reach the changed paths, directly or indirectly. The reason names the
       first such file and counts the rest;
     - `modules_stale`: the modules table has drifted.
   - **What the initial scope leaves out:** no historical (base-revision)
     graph and no per-language clearing of uncertain references.
     - The one classification it makes is the scanner's existing in-repo vs
       outside-the-universe distinction. A reference the scanner already
       records as targeting outside the repository is not uncertainty about
       an in-repo dependency.
     - If the scanner cannot tell the two apart for a form, that form counts
       as uncertainty.
   - **Recording and measuring.** Every fallback reason is recorded:
     - on the `WIDEN_FULL:` line;
     - in the prediction record's widen outcome (default 10);
     - in a per-reason counter.

     t2131_6 measures each reason's frequency on this repo's graph and on a
     Gradle fixture.
   - **Smarter analysis is a named follow-up, not v1.** It is gated on
     t2131_12 showing excessive full-suite fallbacks. Candidates:
     - include uncertain files conservatively with their reverse closure,
       instead of falling back;
     - per-language clearing iterated to a fixed point over the growing reach
       set;
     - a base-revision graph for deletions and renames.
8. **Membership** is computed at load, inside `registry`, and never persisted.
   - **Base membership.** A test belongs to the modules that path containment
     gives it, **plus** the modules of its covered sources: `_scanned.yaml`
     covers, hand, adopted and seeded edges. Covered-source modules count even
     when path membership exists, so flat `tests/` directories work.
   - **Annotation.** `testmap:module <id>…` is a new grammar key, allowed on
     any kind. It reaches the loader through a new optional `ScannedRow`
     field, byte-identical when empty.
     - It replaces **only the path-derived part**; covered-source modules
       always stay.
     - An annotation that would drop one is a finding.
   - **Unresolved.** A test with no membership is a `MODULE_UNRESOLVED:` check
     finding (Info, counted). It is never guessed.
9. **Areas reference modules.**
   - An area may list `modules: [<id>…]`, which expands to those modules'
     globs.
   - `areas --import-codemap` writes module references instead of copying
     globs.
   - A child name that collides across parents is qualified `<parent>-<child>`
     instead of refused.
   - This is a recorded deviation from the landed M2.5 contract.
10. **Widening.** `select --widen submodule|module` and `test --widen
    submodule|module`.
    - **The result set.** It is the selected tests ∪ every member test of the
      affected (sub)modules. Selected tests outside those modules are kept.
    - **New output.** A reason token `module(<id>) <- <path>`, and a
      `WIDENED:<level>|<modules_n>|<added_n>` line ahead of the rows. The
      `SELECTED:` shape is unchanged.
    - **Placement.** The widening stage runs after the graded walk.
    - **The budget.** Widened tests are budget-exempt (never `DEFERRED`).
    - **Paired prediction.** A widened task-scoped selection writes **one**
      prediction record holding:
      - the **plain** selection (the graded walk, pre-widening);
      - the widen outcome: the level and the added tests, or
        `full:<reason>`;
      - the identity the score needs to compare both against the same later
        full run: base revision, change-surface digest, and the registry and
        modules-table digests.

      `score` scores the plain and widened sets against that run and reports
      false negatives per set. A record without the widened part scores
      exactly as today.
11. **Completion: `module` mode, with the cadence.**
    - **Configuration.** `completion.mode: full|selected|module|auto` plus
      `completion.widen: module|submodule` (default `module`).
    - **Required cadence.** `module` requires a valid `full_run_every` (all
      three triggers). `READINESS:cadence_declared` becomes a criterion for
      `module` as well as `auto`; when unmet, the run is
      `POLICY_DEMOTED:module->full|cadence_declared`.
    - **Decision order for each completion run under `module`.** It reuses
      M8.5's `cadence.go` and `policy` verb (no second implementation):
      1. readiness `NOT_YET` → full;
      2. first `ADMISSIBLE` → the engine records
         `approved_by: engine:readiness@<run>`, `mode: module` in
         `costs/policy.yaml`;
      3. a due cadence trigger (`tasks`, `days`, or the
         `selection_ratio_above` ratio computed on the **widened** estimate) →
         full, with `cadence:<trigger>`;
      4. any later unmet criterion → `POLICY_DEMOTED:module->full|<criterion>`;
      5. a reach fallback → full, with `widen_full:<reason>`;
      6. otherwise → `module|next_full_in:<n>`.
    - **Reset after a full run.** Every full run resets the counters, exactly
      as under `auto`: `last_full_run` and `selected_since_full := 0`. Each
      module run increments `selected_since_full`.
    - **Approval and `result=`.** A human `approved_by` stays optional.
      `result=` grows `MODE:module|…` within the 200-character cap.
    - **`auto` in v1.** `auto` never lands on `module`.
    - **Who enables it.** `mode: module` is written by onboarding only once
      the engine supports it (t2131_11), or by the project.
12. **Runner contract.** `group_by: module|submodule` is a new `describe` value
    (M3.1's vocabulary). Each test groups by its path-containment module.
    `{module}` resolves from the table's Gradle name where one exists.
13. **The t1812 re-check (t2131_1).** A new design decision states:
    - code modules are logical source groupings derived from data, not
      hand-typed labels and not profile tiers;
    - widening is a cut knob applied after the graded walk.

    That squares the tier with t1812:55-56.
14. **The prose rename (t2131_2).**
    - Work-package prose and headings are renamed: "Module Map" →
      "Work-Package Map", and so on.
    - Section marker ids, node metadata keys and task names and ids keep their
      identifiers.
    - Gradle, Go and Python "module" stay as they are.
    - A vocabulary entry defines "work package" and "code module".

## Decomposition — twelve children

**Creation flags.**
- Create all twelve in order with `--parent 2131 --no-sibling-dep`, so
  `t2131_<n>` matches the row.
- Pass `--status Postponed` at creation for the held rows, so they are never
  pickable in between.
- Priority is `medium`. The profile adds `--gates risk_evaluated`.

**Archived providers** are recorded in the bodies only, never in `depends:`:
M2.1–M2.6 (`t1853_1..6`), M3.1 (`t1854_1`) and M3.4 (`t1854_4`).

**Labels.**
- Default: `testmap,go_engine,testing`.
- _1 and _2: `testmap,testing,documentation`.
- _8: adds `gates`.
- _9 and _11: add `skills`.

| child | name | type / effort | scope | depends | hold | status | wave |
|---|---|---|---|---|---|---|---|
| t2131_1 | `design_amendment_code_modules` | documentation / medium | Edits the proposal for defaults 1–13. The targets: vocabulary; design decision 20; a new M2 component *Code modules* (reach as default 7 states it, with the fallback-reason vocabulary); the M2.7 row and the waves table; the registry tree, *Where state lives*, the table and generated-file counts and the reserved names; line-protocol rows (`MODULE:`, `MODULE_CONFLICT:`, `MODULE_UNRESOLVED:`, `MODULES_DRIFT`, `WIDENED:`, `WIDEN_FULL:`); the verb list; *Selector*, *Run Surface* and the output contract (`--widen`, budget exemption, the paired prediction record); *Feedback tools* (paired scoring, `cadence_declared` for `module`); *Completion policy*, the config block, the data-flow matrix and readiness `POLICY:` (default 11's decision order); *Scoped-row registry and areas*; M3.1 `group_by: module`; onboarding lines; *Named follow-ups* (smarter reach analysis, gated on the measured fallback share); the t1812 re-check. Then sends **contract notes** with the commit SHA to t1853, t1855, t1857, t1859_4, t1859_5 and t1854_11. | — | — | Ready | now |
| t2131_2 | `proposal_work_package_rename` | documentation / low | Default 14 only: a mechanical prose and heading rename, with every kept identifier listed. Timed so that no other session is editing the proposal. | — | — | Ready | now |
| t2131_3 | `modules_table_and_core_providers` | feature / high | In `registry`: the schema (`provider:` enum including the reserved `agent`, plus `by:`), the `_modules.yaml` loader and renderer, the hand `modules:` table, path → module lookup, `MODULE_CONFLICT:` and `MODULES_DRIFT`. The `modules` package: the inference driver with the codemap and Gradle providers (root `:` excluded) and the module → module `deps:` evidence. The `modules` verb (`--list`, `--explain <path>`, `--scan [--apply]`), the verb-table test and the README interface rows. | t2131_1 | — | Ready | B/C (M2.7) |
| t2131_4 | `modules_language_package_providers` | feature / medium | Exposes Go and Python package facts on `deps.Graph` through copy-returning accessors, with the cache key covering them. Adds the Go and Python providers. | t2131_3 | — | Ready | C (M2.7) |
| t2131_5 | `test_module_membership` | feature / high | Default 8: the `testmap:module` key (parser, `UnitAnnotation`, `ScannedRow` field and render, `SCAN_DRIFT`, goldens, conformance records), membership, the annotation semantics, `MODULE_UNRESOLVED:` / unknown-id findings and `modules --explain <test-id>`. Default 9: area `modules:` references and the codemap import writing them. | t2131_3 | — | Ready | C (M2.7) |
| t2131_6 | `module_reach_and_widening` | feature / medium | The library in `modules`: `Reach(current graph, table, change surface) → affected modules with evidence \| full reason` (default 7: transitive reverse closure over resolved edges; full on deletion, rename, unmapped path, any in-repo uncertainty, or a stale table; a per-reason counter) and `Widen(level, affected, membership) → plain + added tests with reasons` (default 10). Fallback frequency is measured per reason on this repo's graph (with a codemap the test harness generates through `aitask_codemap.sh --scan`, never the engine) and on a Gradle fixture. | t2131_5 | — | Ready | C (M2.7) |
| t2131_7 | `selector_module_widening` | feature / high | Wires t2131_6 into `select` / `explain` (M4.1) and `test` (M4.5): `--widen`, the reason token, `WIDENED:` / `WIDEN_FULL:`, the budget exemption and the explain rows. Also the **paired prediction record** (plain + widen outcome incl. the fallback reason + identity, default 10) and its scoring contract in M4.4 `score`: both sets are scored against the same full run, false negatives are reported per set, and a record without the widened part scores as today. | t2131_6 | M4.1, M4.4, M4.5 | Postponed | D (after M4.4) |
| t2131_8 | `module_completion_mode` | feature / medium | Default 11: the config enum and `completion.widen`; the `module` arm of M8.4's `POLICY` hook in `aitask_test.sh` (it passes `--widen` to `test`, from t2131_7); engine admission and the cadence decision order through M8.5's `cadence.go` and `policy.yaml` writes (no second implementation); `cadence_declared` for `module`; `MODE:module` / `POLICY_DEMOTED:module->full`; readiness `POLICY:module\|…\|next_full_in:<n>`. | t2131_7, t1859_4, t1859_5 | M4.4 | Postponed | G (with M8.5) |
| t2131_9 | `onboarding_module_review` | feature / high | `onboard detect` / `classify` / `inventory` surface the inferred modules (a `MODULES:` summary, `MODULE_UNRESOLVED:` to-dos). When no codemap exists, the skill generates one on the framework side (`aitask_codemap.sh --write`). The M6.5 skill's agent review writes `provider: agent` proposals (intake shaped like `kind_proposals[]`; a conflict is reported, not won) and `testmap:module` lines through a key-aware rewriter planner next to `PlanCovers`. It **never writes `completion.mode: module`**, and a test pins that. No human gate. | t2131_5 | M6.1, M6.4, M6.5 | Postponed | F/G (with M6) |
| t2131_10 | `per_module_batching` | feature / medium | Default 12: `group_by: module\|submodule` in M3.1's grouping function through the `registry` path → module lookup, and `{module}` expansion. The canonical grouping key stays one function shared by M3.3, M4.1 and M3.4. | t2131_3, t1854_11 | — | Ready (blocked by deps) | after M3.2h |
| t2131_11 | `onboarding_enable_module_mode` | feature / low | The M6.5 skill's enabling write: `completion.mode: module` with `completion.widen` and a valid `full_run_every`, with agent provenance. It is written only when the engine reports `module` as supported (a capability probe of the landed config validation, never a version guess) and the modules table resolves with no `MODULE_UNRESOLVED:` blocking readiness. Verified on both sides: a fake engine without `module` support gets no write; the real engine gets the write and loads it. | t2131_8, t2131_9 | M6.5 | Postponed | G (after M8.5) |
| t2131_12 | `retrospective_module_tier_evaluation` | chore / medium | Runs once a registered project with `aitestmap/` has scored paired predictions. Measures, from the paired records (t2131_7): the miss rate of the plain vs the widened set against the same full runs; the added cost (M3.4 ledger); the **full-fallback share per `WIDEN_FULL` reason**; and the cadence's full-run share under `module`. Decides whether the smarter-reach follow-ups (default 7) are justified, and whether `auto` should learn `module`. Outcomes go into its plan; follow-ups are filed only where the data justifies them. | t2131_7, t2131_8 | M4.4 | Postponed | after G |

**Dependency holds** follow the convention of t1853_7 and t1859_4:
- The hold paragraph lists the unresolved `M<n>.<m>` refs.
- A provider parent's coarse pass wires the real child ids with
  `aitask_update.sh --batch <id> --deps "<existing>,<new>"`. That flag replaces
  the list, so the existing deps are kept explicitly.
- The same pass flips the child to `Ready` once nothing is left unresolved.
- A child never takes a placeholder dependency on a whole parent.

**Critical path:** _1 → _3 → _5 → _6 → _7 → _8 → _11. _2, _4 and _10 sit off it.

## Child plan template (`aiplans/p2131/p2131_<n>_<name>.md`)

**Header** per `planning.md`:
- `Task:`
- `Parent Task: aitasks/t2131_testmap_code_modules_tier.md`
- `Sibling Tasks:`
- `Archived Sibling Plans: aiplans/archived/p2131/p2131_*_*.md`
- `Base branch: main`
- `Output branch: main`
- no `Worktree:`

Then:

1. **Context.**
   - The parent goal, this row and the wave.
   - Verbatim: *"This coarse plan records what the parent pass fixed for this
     slice. It does not design internals against providers that do not exist
     yet; the Reality check below does that when this child is picked."*
   - The automation-first rule.
   - The design defaults this child consumes, quoted by number.
   - For held children, the **Dependency hold** paragraph.
2. **Reading list.**
   - The amended proposal sections once t2131_1 lands; before that, this
     parent plan's defaults.
   - For every child: *Registry loader and writer* (2195), *Dependency
     scanners* (2509-2725) and *Scoped-row registry and areas* (2831-2941).
   - _6/_7: *Selector* (3266), *Run Surface* steps 7-8 (1665-1693), the
     prediction record (245, 917) and *Feedback tools* (3388).
   - _8/_11: *Completion policy* (1940, 3847) and *Auto completion policy and
     cadence* (3882).
   - _9/_11: *Onboarding verbs* (3605) and *Onboarding skill* (3690).
   - _10: *Runner contract* (2962) and `p1854_1` D4.
3. **Owned files / provides / consumes**, taken from the table and the
   defaults.
4. **Step 0 — Reality check (MANDATORY, before any code; outcome recorded in
   the plan file).** Re-verify the anchors this child touches; by pick time
   they are claims, not facts. Child-specific items:
   - **_1:**
     - grep that `M2.7`, the verb `modules` and every new line prefix are
       free in the proposal;
     - confirm which notes t1855, t1857 and t1859_4 already hold from t2131,
       so the contract notes add only what changed.
   - **_2:**
     - list every file outside the proposal that cites a heading being
       renamed, and keep each cited anchor resolvable;
     - check that no `Implementing` task's plan is editing the proposal now.
   - **_3:**
     - measure provider overlap on a combined Gradle + codemap fixture;
     - measure the `MODULES_DRIFT` cost against the 300 ms `check` budget;
     - confirm that the `registry`-side lookup needs no `deps` import.
   - **_4:**
     - keep `Graph` immutable and copy-returning;
     - cover the new facts in the cache key (memory
       `feedback_cache_keys_cover_every_consumed_input`);
     - run on this repo's own `deps.Scan`.
   - **_5:**
     - which effective-edge sources exist at load;
     - how unknown `testmap:area` names are treated, mirrored for module ids;
     - whether any registered project already has a codemap-imported
       `areas.yaml` (the default-9 deviation).
   - **_6:**
     - list every `Unresolved` form the scanners emit, and which ones the
       scanner already records as outside the repository. Only in-repo forms
       count as uncertainty; a form that cannot be told apart counts;
     - how the change surface reports deletions and renames;
     - measure each `WIDEN_FULL` reason's frequency on this repo's graph and
       on a Gradle fixture, and record the numbers in the plan for t2131_12.
       No clearing is added to bring them down.
   - **_7:**
     - M4.1's landed walk, reason grammar and prediction-record schema;
     - M4.4's landed `score` and its `predictions.yaml` rows;
     - the `explain --sources --format table` columns;
     - how `test` (M4.5) forwards `--widen`;
     - **stop if M4.1/M4.4/M4.5 have not landed.**
   - **_8:**
     - M8.4's landed `POLICY` hook, carrier and readiness lines;
     - M8.5's `cadence.go`, its decision order and the `policy.yaml` writes,
       reused as they are;
     - the `config.go` enum and the `cadence_declared` validation;
     - **stop if t1859_4, t1859_5 or M4.4 have not landed.**
   - **_9:**
     - M6.1 detect / inventory and M6.4 classify line classes as landed;
     - the M6.5 skill and its `kind_proposals[]` intake;
     - the rewriter ownership checks for a non-`covers` key;
     - **stop if M6.1/M6.4/M6.5 have not landed.**
   - **_10:**
     - M3.1's grouping function and the gradle-class adapter's `{module}`
       regex as landed.
   - **_11:**
     - how the landed engine reports supported completion modes (config
       validation dry-run or a `policy` capability line); add the probe to
       t2131_8's verb if none exists;
     - the M6.5 `enable` phase's config writes;
     - **stop if t2131_8 or M6.5 have not landed.**
   - **_12:**
     - which registered projects carry `aitestmap/` and scored paired
       records;
     - M4.4 `score` and the M3.4 ledger fields as landed;
     - **stop if M4.4 has not landed or no project has data.**
5. **Implementation steps (coarse).** The scope cell expanded into ordered
   steps naming files, tables, verbs and line classes.
6. **Verification / acceptance:**
   - **_1:**
     - every new prefix appears in the line-protocol index;
     - the verb list, the registry tree and the counts agree;
     - default 7's fallback rule (no historical graph, no clearing, recorded
       reasons) is stated in the component text, with smarter analysis under
       *Named follow-ups*;
     - default 10's paired record and default 11's decision order are stated;
     - `NOTE_APPENDED:` for every contract note.
   - **_2:**
     - every remaining work-package "module" is a kept identifier;
     - every cited anchor resolves.
   - **_3:**
     - a `_modules.yaml` load → render golden round trip;
     - codemap fixture with duplicate child names across parents;
     - Gradle `projectDir` override;
     - `gradle-dynamic` flagged;
     - root `:` excluded;
     - hand override wins and is reported;
     - three-tier input refused;
     - the reserved `provider: agent` row loads;
     - `TestVerbTableMatchesProposal` updated;
     - exact-line CLI tests for `modules`;
     - a `MODULES_DRIFT` negative control.
   - **_4:**
     - Go module and package fixture;
     - Python packages, including a namespace portion;
     - accessors return copies;
     - the cache key changes when package facts change.
   - **_5:**
     - parse goldens and `TestParseErrors` cases;
     - `ScannedRow` round trip, byte-identical when empty;
     - the flat-`tests/` fixture gets the membership;
     - the annotation replaces only path membership, and a drop is a finding;
     - `MODULE_UNRESOLVED:` is counted, not failing;
     - an area module ref expands, and an unknown ref is refused;
     - the codemap import writes refs.
   - **_6:** ordinary widening and conservative fallback, each guard isolated.

     **Ordinary widening** (a fully resolved fixture with no uncertainty
     anywhere):
     - an internal edit pulls in no dependents;
     - a public-surface edit pulls in the dependent;
     - the **indirect chain**: C → B → A over resolved edges, with a change
       in A, gives `{A, B, C}`. Mutant (direct reverse edges only) → red;
     - no recursion through module-level deps (a module dep with no file
       reach adds nothing);
     - selected tests outside the affected modules are kept;
     - submodule vs module level.

     **One fixture per retained guard**, each built so that **only** that
     guard can fire. It asserts the exact `WIDEN_FULL:<reason>`, and its
     mutant (remove that guard) turns it red:
     - `deleted_path`: delete a file nothing references (no importer, so no
       `Unresolved` entry anywhere); with the guard removed, the result is a
       module widening;
     - `renamed_path`: rename an unreferenced file;
     - `uncertain_reference`, one fixture per form, each in a module the
       change does not otherwise reach:
       - an in-repo `Unresolved` entry;
       - an opaque file;
       - a `<dynamic>` source;
       - a `gradle-dynamic` build;
     - `unmapped_path`: a changed path outside every module, plus the
       root-only Gradle variant;
     - `modules_stale`: a drifted table over a clean graph;
     - an out-of-repo reference the scanner records as external does **not**
       fire `uncertain_reference`.

     **Recording:** every fallback sets the per-reason counter and the widen
     outcome that t2131_7's prediction record carries.

     **Measured frequencies** are recorded in the plan.
   - **_7:**
     - exact lines for `select --widen`;
     - the reasons appear in `explain`;
     - the `SELECTED:` shape is unchanged;
     - widened tests are never `DEFERRED`;
     - the prediction record carries plain + widen outcome (level and added
       tests, or `full:<reason>`) + identity;
     - `score` against one full run reports false negatives per set (a miss
       the plain set has and the widened set catches);
     - a record without widening scores byte-identically to today;
     - newest-wins per task keeps the pair together.
   - **_8:**
     - the `module` matrix:
       - `NOT_YET` → full;
       - the first `ADMISSIBLE` records the engine approval;
       - each cadence trigger (`tasks`, `days`, `selection_ratio_above` on
         the widened estimate) forces full with `cadence:<trigger>`;
       - after a full run, `selected_since_full` is reset to 0 and
         `last_full_run` updated;
       - a module run increments the counter;
       - a missing or invalid `full_run_every` → `cadence_declared` unmet →
         full;
       - demotion per criterion, `widen_full:<reason>`, `engine_absent`,
         empty selection;
     - `result=` is at most 200 characters;
     - readiness reports `POLICY:module|…`;
     - the cadence code is M8.5's, not a copy (grep).
   - **_9:**
     - detect / classify / inventory lines;
     - an agent proposal is written with `by: agent:<string>` and reloaded;
     - a conflict is reported;
     - no write of `completion.mode`;
     - no step requires a person;
     - the skill goldens pass through `aitask_skill_verify.sh`.
   - **_10:**
     - a grouping golden;
     - a multi-module test lands in exactly one group;
     - `{module}` expansion;
     - existing `group_by` values are unchanged.
   - **_11:**
     - with a fake engine lacking `module`: no write, with a reported reason;
     - with the real engine: the write lands with agent provenance, loads,
       and readiness reports `cadence_declared|met`;
     - an unresolved table blocks the write;
     - the skill goldens pass.
   - **_12:**
     - an outcomes table in the plan, including the fallback share per
       reason;
     - follow-ups (smarter reach, `auto` learning `module`) only where data
       backs them.
   - **Every child:**
     - `ait engine test` is green where Go is touched;
     - no path requires a human action.
7. **Step 9 reference.** The shared post-implementation; current branch, no
   merge.

## Post-approval sequence

0. **Externalize this plan** (`plan-externalization.md`) to
   `aiplans/p2131_testmap_code_modules_tier.md`, then commit it path-scoped.
1. **Create t2131_1 … t2131_12 in order** (`task-creation-batch.md`).
   - Flags: `--parent 2131 --no-sibling-dep`, `--deps` and `--labels` per row,
     and `--status Postponed` for _7, _8, _9, _11 and _12.
   - Each body carries the Context / Key Files / Reference Files /
     Implementation Plan / Verification sections, plus the hold paragraph
     where one applies.
   - Read back every id. **Stop if an id differs from its row.**
2. **Revert the parent:**
   `aitask_update.sh --batch 2131 --status Ready --assigned-to "" --plan-approved-at ""`,
   then `aitask_lock.sh --unlock 2131`.
3. **Write the twelve child plans** from the template. Commit them with
   `aitask_task_commit.sh`, naming each path, and treat any
   `SKIPPED:unknown:` line as a missing file.
4. **Send the dependency-hold notes** through `/aitask-note` with
   `--from 2131`. Each note is advisory and hedged as written against the SHA.
   - **t1855:** when M4 is decomposed:
     - wire the M4.1, M4.4 and M4.5 ids into t2131_7;
     - wire the M4.4 id into t2131_8 and t2131_12;
     - flip each to `Ready` once nothing is left unresolved.

     Also: M4.1's prediction record and M4.4's `score` gain the paired
     plain/widened form in t2131_7. Keep the record schema additive.
   - **t1857:** wire the M6.1, M6.4 and M6.5 ids into t2131_9, and the M6.5
     id into t2131_11. Also: M6.5's `enable` phase gains the `module`-mode
     write only through t2131_11.
   - **t1859_4:** t2131_8 depends on it and adds a `module` arm to its
     `POLICY` hook. Its body line 48 still names `t1854_2`, where the
     frontmatter has `t1854_12, t1854_7`.
   - **t1859_5:** t2131_8 depends on it.
     - `module` reuses `cadence.go`, the engine approval and the decision
       order.
     - `cadence_declared` also applies to `module`.
     - `auto` never lands on `module` in v1.
   - **t1854_11:** t2131_10 depends on it. `{module}` will resolve from the
     module table.
   - **t1853:** M2.7 adds a ninth registry table and a third generated file.
     t1853_7's repair loop may treat `MODULE_UNRESOLVED:` and
     `MODULE_CONFLICT:` as repairable findings.
   - **t1863:** the cross-linking audit should cover t2131's edges.

   A `LIVE_NONE:` after `NOTE_APPENDED:` is a success.
5. **Run the checks.** Run the post-phase step
   `[verify_creation_and_hold_wiring]` below, then the *Verification* checks.
   **Do not reach the child checkpoint while either reports a mismatch.**
6. **Close out.**
   - Manual-verification offer: the expected answer is "No" (there is no TUI
     surface).
   - Child checkpoint: the expected answer is "Stop here".
   - Next actions: `/aitask-pick 2131_1` (or `2131_2`), and the separate
     `/aitask-trail` refresh of `art:trail-testmap-feature`.

### Post-phase (risk mitigations)

1. [verify_creation_and_hold_wiring] After step 4 and before step 6, check
   four things:
   - **(a) Frontmatter.** For each `aitasks/t2131/t2131_<n>_*.md`, read back
     `depends`, `status`, `labels` and `gates`, and compare them with the
     decomposition table. Archived providers must be absent from `depends`.
   - **(b) Hold paragraphs.** For each of t2131_7, _8, _9, _11 and _12, grep
     the body's `Dependency hold` paragraph for every `M<n>.<m>` in the row's
     hold cell.
   - **(c) Notes.** Confirm that step 4 returned `NOTE_APPENDED:` for every
     parent named in a hold: t1855 (M4.1, M4.4, M4.5) and t1857 (M6.1, M6.4,
     M6.5).
   - **(d) Commit scope.** For every commit this pass made, run
     `./ait git show --stat --format='%h %s' <sha>`. Each commit may touch only
     its own task, plan or inbox paths.

   Any mismatch → fix it with a path-scoped commit and re-run (a)–(d). Never
   amend or revert a commit that carries another session's paths: report it
   instead.

## Verification (of this pass)

- `ls aitasks/t2131/` lists twelve children, and
  `grep -H '^depends:\|^status:' aitasks/t2131/*.md` matches the table.
- `grep -L 'Step 0 — Reality check' aiplans/p2131/*.md` is empty.
- `grep -L 'does not design internals against providers that do not exist yet' aiplans/p2131/*.md` is empty.
- `grep -L 'Dependency hold' aitasks/t2131/t2131_{7,8,9,11,12}_*.md` is empty.
- `aitask_ls.sh -v 15` shows t2131 as "Has children", with status `Ready` and
  no lock (`aitask_lock.sh --check 2131`).
- Every note step returned `NOTE_APPENDED:`.

## Risk

### Code-health risk: low
- This pass makes about 30 commits to the shared task-data branch (task files,
  plans, notes). The claim's sync already warned that the data worktree holds
  another session's unstaged changes. An unscoped commit would sweep those in.
  All writers used here are path-scoped. · severity: low (residual — each
  commit's scope is read back by inline post-phase
  verify_creation_and_hold_wiring) · → mitigation: inline post-phase
  verify_creation_and_hold_wiring

### Goal-achievement risk: medium
- **Defaults fixed before any code may be the wrong shape.** These include
  engine admission and the cadence order for `module`, the codemap import
  deviation, and the split of the table between `registry` and `modules`.
  Each is bounded by three things:
  - the amendment lands first;
  - every child's Reality check amends the proposal when it finds a default
    wrong;
  - the retrospective child measures the outcome.

  · severity: medium · → mitigation: none (covered by the children)
- **The conservative reach fallback may make widening rarely useful.** Any
  in-repo uncertainty anywhere forces full. In repos with `<dynamic>` sources
  or unresolved refs (this repo's bash tree is likely one), widening may
  almost always fall back. That is correct by design, but low in value until
  smarter analysis lands. Bounded by:
  - t2131_6 measures the per-reason frequency at implementation time;
  - t2131_12 measures the real fallback share;
  - the smarter-reach follow-ups are named and gated on those numbers.

  · severity: medium · → mitigation: none (covered by t2131_6 / t2131_12 and
  the named follow-ups)
- **The held children depend on other parents' passes.** t2131_7, _8, _9, _11
  and _12 become pickable only when the M4 and M6 passes wire their ids.
  · severity: low (residual — hold paragraphs and provider notes verified by
  inline post-phase verify_creation_and_hold_wiring; t1863's audit is noted to
  cover the edges) · → mitigation: inline post-phase
  verify_creation_and_hold_wiring
- **This repo cannot show the tier's value.** It has no `aitestmap/` and no
  codemap, so the value shows only on target repos. · severity: medium · →
  mitigation: none (covered by t2131_6's generated-codemap measurement and
  t2131_12)
- **The chain to first value is long.** The critical path is seven children,
  and the selector child also waits for M4.4. · severity: low · → mitigation:
  none

### Planned mitigations
- timing: post-phase | name: verify_creation_and_hold_wiring | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: unscoped commit sweep (code health); held children never wired (goal achievement) | desc: read back child frontmatter, hold paragraphs, provider NOTE_APPENDED lines and per-commit path scope before the child checkpoint

## Step 9 reference

Child tasks run Step 9 (Post-Implementation) individually. The parent is
archived with its last child.
