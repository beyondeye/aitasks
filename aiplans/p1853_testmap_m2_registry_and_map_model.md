---
Task: t1853_testmap_m2_registry_and_map_model.md
Base branch: main
Output branch: main
---

# Plan: t1853 — Testmap M2: Registry and map model (coarse planning pass)

## Context

The test map feature (`aidocs/testing_engine/n014_explorer_006_proposal.md`) is
cut into ten modules, one parent task each (t1852–t1861). This task is **M2 —
Registry and map model**: everything that reads and writes `aitestmap/` without
running a test.

The task body binds the protocol: this session performs only the **coarse
planning pass** — one child per submodule row (M2.1–M2.6), a coarse plan per
child recording scope, owned files, provided/consumed interfaces, acceptance
test lists, wave, and the **mandatory Reality-check step** — then **stops** at
the child checkpoint. No engine code is written. "Yes, create child tasks" and
"Stop here" are prescribed by the task body and treated as decided.

**Sequencing.** M2's wave-earliest children consume only M1.2, which landed
(t1852_2, `33012bff7`); all of M1 is implemented and archived. So this pass is
admissible under the submodule-granular rule (memory
`feedback_testmap_parents_in_strict_wave_order`; t1852's note in the inbox).

## Repository reality anchors (verified 2026-10-11, main @ 2fe3f8cb7)

| fact | state now |
|---|---|
| Go module | `goengines/` (module `github.com/beyondeye/aitasks/goengines`, `go 1.26.0`, toolchain `go1.27.1`); deps `yaml.v3`, `x/sync` only — `doublestar/v4` is allowlisted, added by its first importer |
| verb table | `goengines/cmd/ait-testmap/verbs.go`: `scan check annotate verify axes areas classify` are `stub(...)` rows exiting 64 with `NOT_IMPLEMENTED:<verb>`; a submodule replaces only its own row with `{Name, Run, Exits}` (README "Rules for engine submodules") |
| shared packages | `internal/{lineproto,platform,gitx}`; `internal/testmap` (`Contract = 1`, `CheckContract` → `*ContractMismatchError`); `internal/testmap/fixture` (`fixture.New(t)`, `Commit(t, task, type, desc)`); `internal/benchgate` + `bench/baseline.txt` |
| invariants | `goengines/guards_test.go` lexical tripwire for Invariants 4–5 (never writes `aitasks/` etc., never invokes `aitask_*.sh`, never commits); per-line `// invariant5-ok:` exemption |
| `internal/testmap/<pkg>` for M2 | none exist (`registry`, `annot`, `deps`, `axes`) |
| `aitestmap/` | does not exist in this repo (M10.1 creates it) |
| codemap | `aitask_codemap.sh --scan` writes `aitasks/metadata/code_areas.yaml`; the engine may read it, never run the script (Invariant 5) — `areas --import-codemap` reads the file |
| M3 (t1854) | not decomposed; no runner contract (`internal/runner`) exists |
| cross-linking | t1863 (`Ready`): a dependency on an **archived** child is satisfied and is neither added nor required |

## Decomposition — six children, one per submodule row

Create all six with `--no-sibling-dep`; set `depends:` exactly as below (ids are
assigned in row order, so `t1853_<n>` = `M2.<n>`). M1.2 (`t1852_2`) is archived,
so it is recorded in the bodies, never written into `depends:`.

| child | name | scope (Module Map row, after the Deviations below) | depends | wave | effort |
|---|---|---|---|---|---|
| t1853_1 | `m2_1_registry_core` | `aitestmap/` layout; id grammar `<path>[#<member>][@<variant>]`; the loader + one merge rule over `registry/*.yaml`, with the edges / rules / waivers tables (scopes+areas land from M2.5, axes from M2.4, seeds+adopted from M2.6); `owns:` glob routing; `config.yaml` schema with every key and default; `exclude:` globs; deterministic sorted writes only on change; `CONTRACT_MISMATCH`; `check` framework + rules `STALE_PATH`, `UNSTAMPED` (past `bootstrap_until` under `require_stamp`), `UNANNOTATED_MEMBER`, `DEAD_MEMBER`, `UNREGISTERED`, `UNMAPPED_ARTIFACT`; `scan --apply` persisting `variants:` to `_scanned.yaml` over **two injected inputs** — an annotation source (M2.2 plugs it) and a unit lister (M3.1 plugs the runner repository) | — (M1.2 = t1852_2, landed) | A | high |
| t1853_2 | `m2_2_annotation_grammar_rewriter` | grammar v3 (`testmap:unit` blocks, every key), per-language comment leaders, Python docstrings read-only, unknown-key refusal with line number, the stamp format `@<date>/<blob10>`, the line-targeted rewriter (`REWRITE_CONFLICT`), fixed per-language insertion positions, `annotate <test> <source>…`, `verify`, `# Covers:` prose never matched; plugs its scanner into `scan` as the annotation source; leaves a **post-re-stamp hook** in `verify` / `annotate` that M2.6 fills (the provenance-row cleanup) | t1853_1 | A | high |
| t1853_3 | `m2_3_dependency_scanners` | bash, python, go (`go list -deps -json` behind a cache whose key changes whenever any Go source's import set can change — **not** `go.sum` alone; Deviation 7), kotlin opaque contract, Gradle module graph, plugin protocol under `aitestmap/scanners/`, opt-in `android-res`, the XDG blob cache, the exported facts (`static:invocation` / `static:import` / `static:package`, anchor lines, declared symbols); **plus `annotate --suggest` and `annotate --from-body` as named extensions of M2.2's `internal/annot`** | t1853_2 (M1.2 landed) | B | high |
| t1853_4 | `m2_4_axes_and_variants` | `axes.yaml` + the axes table in the loader; runner-side `axis:` / `token_format:` (named extension of M3.1's `describe` parse); `<unit>@<value>` ids; the facet join and forced-facet resolution as library API (`select --axis` flag is parsed by M4.1); `axes --list\|--check\|--explain`; the three axis rules `DEAD_AXIS_SOURCE`, `UNKNOWN_VARIANT`, `UNCOVERED_VALUE`; observed sources widen-only | t1853_1; **M3.1 (t1854 child, wired at t1854's pass)** | C | medium |
| t1853_5 | `m2_5_scoped_rows_and_areas` | `_scoped.yaml`, `registry/areas.yaml` + `areas:` blocks, `areas --import-codemap`, `owns:` by area name, kind ranking data, triggers, `reads`, `DEAD_SCOPE` / `KIND_MISMATCH\|CONVERT_TO_SUITE`, digest-exemption of scoped rows, `classify --suggest` with the source-set/directory-convention and resource signals plus `fanout:<n>` (the recorded-p95 signal lands with M6.4) | t1853_1 | B | medium |
| t1853_6 | `m2_6_adoption_tables` | `seeds` + `adopted` tables in the loader; `onboard.yaml` `rejections[]` / `reviews[]` / `kind_proposals[]` / `calibration[]` as read tables; load rules `SEED_SHADOWED`, `ADOPTED_ORPHAN`, absent-`by:`-is-human; the write routing API every verb touching the three files uses; `SEEDED:` / `ADOPTED:` counts on `check`; **fills M2.2's post-re-stamp hook so a human `verify` / `annotate` re-stamp deletes the matching `adopted.yaml` row** (named extension of M2.2; Deviation 8) | t1853_1, t1853_2 | **B** (proposal said E) | medium |

Labels per child: the parent's `testing,testmap,go_engine`. Priority `medium`,
type `feature`; the profile injects `--gates risk_evaluated`.

## Deviations from the proposal (cut fixes — edited in the proposal, protocol §1)

Each is a submodule consuming a later-wave or same-wave-dependent provider that
its "depends on" cell omits, resolved by the proposal's own rule ("the earlier
submodule ships without that step and the later submodule adds it; both entries
say so").

1. **M2.6 wave E → B** (the inconsistency the task body names). Its consumers
   M4.1 (C), M4.2 / M4.4 / M8.2 (D) need it; its deps (M2.1, M2.2) are wave A.
   B is the earliest legal wave. Wave-B state text gains "seeded and adopted
   rows load". Notes to t1855 (M4) and t1859 (M8).
2. **`scan` / `check` vs. annotations and runners (M2.1 ↔ M2.2 ↔ M3.1 cycle).**
   Edges are `testmap:covers` lines read by M2.2's scanner, and the universe
   comes from runners' `list` (M3.1, which depends on M2.1). M2.1 keeps the
   `scan` / `check` verbs, persistence and rule framework, defined over an
   injected annotation source and unit lister and tested with fixture
   implementations; **M2.2** plugs the annotation scanner in; **M3.1** plugs
   the runner repository in (named extension, added to M3.1's row). Note to
   t1854.
3. **Table and check-rule partition inside `internal/registry`.** The *Registry
   loader* component gives M2.1 "six core tables (edges, scopes, areas, rules,
   waivers, axes)" and every check rule, while the Module Map gives the scoped
   tables to M2.5 and "the three axis check rules" to M2.4 — two owners. Fix:
   M2.1 owns the loader, merge rule, id grammar and the edges / rules / waivers
   tables; scopes + areas and `DEAD_SCOPE` / `KIND_MISMATCH` land from M2.5;
   the axes table and `DEAD_AXIS_SOURCE` / `UNKNOWN_VARIANT` / `UNCOVERED_VALUE`
   from M2.4 (removed from M2.1's row); seeds / adopted and `SEEDED:` /
   `ADOPTED:` / `SEED_SHADOWED` / `ADOPTED_ORPHAN` from M2.6.
4. **`annotate --suggest` / `--from-body` need M2.3** (the closure; the Kotlin
   scanner's symbol resolution) but M2.2 is wave A and M2.3 wave B. They move
   to M2.3 as named extensions of M2.2's `internal/annot`; M2.3 gains M2.2 as
   a dependency (B after A — no wave change).
5. **M2.4 consumes M3.1** (`describe`'s `axis:` / `token_format:`): add M3.1 to
   its "depends on" (B before C — no wave change). `select --axis` is parsed by
   M4.1's `select`; M2.4 provides the resolution. Notes to t1854, t1855.
6. **`classify --suggest`'s recorded-p95 signal needs the cost ledger** (M3.4,
   wave C) but M2.5 is wave B. The signal lands with **M6.4** (which already
   depends on M2.5 and M3.4 and consumes the signals) as a named extension of
   M2.5's verb; M6.4's row says so. Note to t1857.
7. **The `go list` cache key is unsound (correctness fix).** The *Dependency
   scanners* component caches `go list -deps -json` "by `go.sum` digest"
   (proposal lines 2188–2189). Adding an import of another **local** package
   changes the dependency graph without touching `go.sum`, so the cached result
   would omit the new relationship and the selector would miss affected tests.
   Fix in the proposal: the cached result is keyed so that any change to a Go
   source file's import set (or to `go.mod` / `go.sum`) invalidates it — the
   exact key (per-file import parse by blob, a digest over the module's `.go`
   blobs incl. uncommitted edits, …) is left to M2.3's Reality check. M2.3's
   acceptance gains the red-proved case below.
8. **Re-stamp → `adopted.yaml` provenance had no owner.** The proposal
   (*Where state lives*, line 417; *Registry loader*, line 2148; *Adoption
   ledger*) has a re-stamp through `verify`, `annotate`, `stale
   --confirm-source` or a per-row `adopt` act on that edge's provenance row.
   `verify` / `annotate` are M2.2's and land in wave A, before M2.6's tables
   exist; nothing assigned that integration to them, and an API-level test of
   the routing would pass while the commands never call it. Fix: M2.2 leaves a
   post-re-stamp hook in both commands carrying the re-stamped edges and the
   actor; **M2.6 fills it** as a named extension of M2.2, and both rows say
   so. Under the automation-first principle below, the rule M2.6 applies is
   **by actor**: an automated re-stamp (agent or engine) refreshes the
   matching row and keeps its `by:` — it never launders a machine claim into a
   "reviewed" edge — and only an explicit human actor deletes the row. The
   later callers (`stale --confirm-source` in M4.2, per-row `adopt` in M6.3)
   already depend on M2.6 and call its routing directly. M2.6's acceptance
   gains the command-level cases below.

**Automation-first principle (user directive at this pass, 2026-10-11).**
Human review belonged to an older design; the finalized feature must run
without a person wherever possible. For M2 this means: no M2 verb, load rule
or check rule may make a human action a precondition of any path; `by:
human:<email>` stays a value the data model can record (an optional input),
never a gate; M2 encodes no "awaiting a person" state of its own. Where the
proposal still keeps a human-only step owned by another module (seed
rejection "only by a person", `REVIEW_HUMAN` parking, kind changes, axis
declaration, the absent-`by:`-is-human reading), M2 ships only the data and
verbs, and the owning parent is told to automate it at its own coarse pass
(notes in step 5). Every child body and plan carries this paragraph.

Not deviations, recorded so children do not re-derive them: owns cells read
`internal/<pkg>` as `goengines/internal/testmap/<pkg>` (proposal fix
`07a546087`); `areas --import-codemap` reads `aitasks/metadata/code_areas.yaml`
and never runs `aitask_codemap.sh` (Invariant 5); component text that names
selector / attribute behaviour (distance-1 join ranking, suite budget,
missing-trigger attribution) describes the feature — M2.5 provides the data and
join function, M4.1 / M4.4 own the verbs (Module Map wins, as in t1852
Deviation 1).

## Cross-module seams (recorded in every child body)

**Provides:** the loaded registry, id grammar, config keys (M2.1, M2.6 → every
engine package); `testmap:` grammar, stamp format, rewriter API (M2.2 → M4.2,
M6.3, M7.2, M7.4); scanner facts and closure (M2.3 → M4.1, M6.2, M7.1, M7.4);
variant expansion (M2.4 → M4.1, M3.4, M4.3, M6.4); scoped join, kind vocabulary,
onboarding signals (M2.5 → M4.1, M6.4); seeded / adopted rows and
`seeded.yaml` schema (M2.6 → M4.1, M4.2, M4.4, M6.2, M6.3, M7.1, M7.2, M8.2).

**Consumes:** M1.2 (landed); M3.1 for M2.4 only.

**Named extensions:** into M2-owned code — M3.1 (runner lister into
`scan`/`check`), M7.4 (`annotate --author` into `internal/annot`), M6.4
(p95 signal into `classify --suggest`), M2.3 (`--suggest` / `--from-body` into
`internal/annot`), M2.4 / M2.5 / M2.6 (their tables and rules into M2.1's
loader and `check`), M2.6 (provenance-row cleanup into M2.2's `verify` /
`annotate` post-re-stamp hook). Out of M2 — M2.4 into M3.1's `describe` parse. Every
later writer of `seeded.yaml` / `adopted.yaml` / `onboard.yaml` goes through
M2.6's write routing. Invariant 6 (comment-only adoption, never into a Python
docstring) is enforced in the M2.2 rewriter. Named follow-ups (not v1):
versioned scanner-plugin contract; symbol-level Kotlin/Python attribution.

## Child plan template (`aiplans/p1853/p1853_<n>_<name>.md`)

Child header per `planning.md` (`Task:`, `Parent Task:`, `Sibling Tasks:`,
`Archived Sibling Plans:`, `Base branch: main`, `Output branch: main`, no
`Worktree:`), then:

1. **Context** — parent goal, this row, the wave, and verbatim: *"This coarse
   plan records what the proposal fixes for M2.<n>. It does not design
   internals against providers that do not exist yet; the Reality check below
   does that when this child is picked."*
2. **Proposal reading list** — Module Map `#### M2` row; its component
   subsection(s) (*Registry loader and writer*, *Enumeration and
   reconciliation* / *Annotation scanner and rewriter* / *Dependency scanners*
   / *Variant axes*, *Axis resolver verbs* / *Scoped-row registry and areas*,
   *Broad-test scheduling (M2.5 half)* / *Adoption ledger*); *Architecture →
   Vocabulary, The registry directory, Where state lives, Line-protocol
   index*; *Invariants*; *Assumptions → The map and freshness*, *Variants,
   broad tests and runners*; *Tradeoffs → Map and registry structure*; the
   parent plan's Deviations; `goengines/README.md`.
3. **Owned files / provides / consumes** — from the tables above.
4. **Step 0 — Reality check (MANDATORY, before any code; outcome recorded in
   this plan file)** — the six sub-steps of the parent body §2, starting from
   the anchors table above (claims, not facts, by pick time). For M2.1 the
   provider is M1.2 (`33012bff7`); for M2.4 it includes M3.1's actual
   `describe` surface.
5. **Implementation steps (coarse)** — the scope cell expanded into ordered
   steps naming the package and verb row; no internal design beyond the
   proposal.
6. **Verification / acceptance** (component test lists):
   - M2.1: golden tests for the core merges and the id grammar (member and
     variant fragments); one fixture per owned check rule; newer `contract:` →
     `CONTRACT_MISMATCH` exit 3; re-`scan --apply` with no change is
     byte-identical (writes only on change, sorted); `exclude:` paths never
     listed / never `UNREGISTERED`; `scan --apply` persisting `variants:` via
     a fixture lister; `UNMAPPED_ARTIFACT`; bench `scan` / `check` < 300 ms on
     the aitasks shape, baseline recorded.
   - M2.2: grammar parse goldens per language incl. Python docstring read and
     `testmap:unit` block ownership; unknown key refused with a line number;
     `REWRITE_CONFLICT` on a changed line; placement goldens per language
     (bash after shebang + leading `#` block, Python after the docstring as `#`
     lines, Go after the package clause, Kotlin after imports / inside the
     member block); `git diff -w --ignore-blank-lines` shows comments only;
     `# Covers:` prose never matched or rewritten; `verify` re-stamps.
   - M2.3: one red-proved fixture per Kotlin opaque branch (inline fun, `const
     val`, DI binding, reflection, generated/KSP, unreadable); bash literal
     invocation incl. `$SCRIPT_DIR` / `$PROJECT_DIR` forms; python `sys.path`
     bootstrap import; go package membership; plugin JSON-line protocol;
     cache hit by blob; `android-res` opt-in; `annotate --suggest` /
     `--from-body` outputs; **go cache invalidation, red-proved**: in a
     fixture module, add an import of another local package with `go.mod` /
     `go.sum` byte-identical, re-scan, and assert the new dependency (and the
     test it reaches) appears — the case must fail against a `go.sum`-only key.
   - M2.4: `axes --list` counts; `--check` the three rules; `--explain` `AXIS:`
     lines incl. `-`; `<unit>@<value>` ids; facet join and forced facet;
     observed sources widen-only.
   - M2.5: `_scoped.yaml` / `areas.yaml` merge goldens; `areas
     --import-codemap` from a fixture `code_areas.yaml`; `owns:` by area name;
     `DEAD_SCOPE`, `KIND_MISMATCH|CONVERT_TO_SUITE`; scoped rows never
     digest-stale; `CLASSIFY:<test>|<kind>|<reason>` for each shipped signal
     and `fanout:<n>`.
   - M2.6: goldens for the two adoption-table merges, the `by:` merge, the
     absent-`by:` rule and the shadow rule; `ADOPTED_ORPHAN`; per-file
     `contract:` refusal; `SEEDED:<n>` / `ADOPTED:<n>|human <h>|agent <a>|auto
     <m>` on `check`; write-routing API unit tests per verb row; **command-level
     re-stamp cases** through the real `verify` and `annotate` verbs on a
     fixture with two `adopted.yaml` rows (the edge being re-stamped and an
     unrelated one): an automated actor refreshes the matching row and keeps
     its `by:`; an explicit human actor deletes the matching row; in both the
     unrelated row is byte-identical, and re-stamping an edge with no
     provenance row leaves `adopted.yaml` untouched.
   - Every child: no path it ships requires a human action (automation-first
     principle); a human-only step it meets in the proposal is reported to the
     owning parent, not encoded.
7. **Step 9 reference** — shared post-implementation; current branch, no merge.

## Post-approval sequence

0. Edit the proposal for Deviations 1–8 in one change: the M2.1–M2.6 Module Map
   rows (incl. M2.3 depends `M1.2, M2.2`, M2.4 depends `M2.1, M3.1`, the M2.2
   hook and M2.6's fill of it); M3.1, M4.1 and M6.4 rows (named extensions /
   `--axis`); the wave table (M2.6 → B, state text); the *Registry loader and
   writer* (partition sentence; re-stamp provenance rule by actor),
   *Annotation scanner and rewriter* (the two moved annotate arms; the hook),
   *Dependency scanners* (the `go list` cache key requirement) and *Scoped-row
   registry and areas* (p95 signal) component paragraphs. Commit path-scoped:
   `git commit -m "documentation: Fix the M2 cut in the testmap proposal (t1853)" -- aidocs/testing_engine/n014_explorer_006_proposal.md`.
0b. **Synchronize t1853's own body with the corrected cut** — t1863 Step 1
   repairs children against the parent's `## Submodules` table, so that table
   is the source it reads, not the notes. Edit
   `aitasks/t1853_testmap_m2_registry_and_map_model.md` in place (Edit tool;
   the `## Inbox` section is never touched): every row's scope cell to match
   the decomposition table above; the "depends on" cells to exactly
   `M1.2` / `M2.1` / `M1.2, M2.2` / `M2.1, M3.1` / `M2.1` / `M2.1, M2.2`; M2.6's
   wave to `B`; the *Known inconsistencies* section rewritten as resolved
   (pointing at the proposal commit); the *Hooks and extensions* bullets
   gaining the M3.1 lister, M2.3 annotate arms, M2.6 re-stamp hook, M6.4 p95
   extensions and the automation-first paragraph. Commit with
   `aitask_task_commit.sh -m "ait: Sync t1853 submodule table with the corrected M2 cut" aitasks/t1853_testmap_m2_registry_and_map_model.md`.
1. Externalize this plan (`aitask_plan_externalize.sh 1853 --force --profile
   aitasks/metadata/profiles/fast.yaml --no-worktree`), commit with
   `aitask_task_commit.sh`.
2. Create the six children (`aitask_create.sh --batch --commit --parent 1853
   --no-sibling-dep …`, descriptions carrying the Child Task Documentation
   Requirements sections), then set `depends:` per the table.
3. Revert the parent (`aitask_update.sh --batch 1853 --status Ready
   --assigned-to "" --plan-approved-at ""`; `aitask_lock.sh --unlock 1853`).
4. Write the six child plans to `aiplans/p1853/`; commit them together naming
   every file.
5. Send notes (`/aitask-note`, citing the proposal commit from step 0):
   t1854 (M3.1 plugs the runner lister into `scan`/`check`; at its pass add
   `t1854_1` to `t1853_4`'s `depends:`); t1855 (M2.6 now wave B; `select
   --axis` is M4.1's); t1857 (p95 signal is M6.4's); t1859 (M2.6 wave B for
   M8.2); t1863 (the pending `t1853_4 → M3.1` edge; M1.2 edges omitted as
   archived); and the **automation-first directive** to t1854–t1861, naming
   the human-only steps the proposal still carries in their modules (M6.3
   `onboard reject` "only a person", M7.2 `REVIEW_HUMAN` parking, M6.4 kind
   changes, level-3 axis declaration, M8.4 `selected` approval) for each
   parent to automate at its own coarse pass. Update memory
   `feedback_testmap_parents_in_strict_wave_order` (t1853 decomposed; drop the
   "decisions to reuse when re-picking t1853") and save the automation-first
   directive as a feedback memory.
6. Manual-verification sibling prompt; child checkpoint → **Stop here**.

### Post-phase (risk mitigations)

1. [verify_child_plans_carry_reality_check] After step 4 writes the six child
   plans and before they are committed, run
   `grep -L 'Step 0 — Reality check' aiplans/p1853/p1853_*_*.md` and
   `grep -L 'does not design internals against providers that do not exist yet' aiplans/p1853/p1853_*_*.md`.
   Both must print nothing; a named file is fixed before the commit.
2. [verify_child_dependency_graph] After step 2 sets `depends:`, read back
   `grep '^depends:' aitasks/t1853/t1853_*_*.md`. Expected exactly: `_1 []`,
   `_2 [t1853_1]`, `_3 [t1853_2]`, `_4 [t1853_1]`, `_5 [t1853_1]`,
   `_6 [t1853_1, t1853_2]`. Any other value is corrected with
   `aitask_update.sh --batch 1853_<n> --deps …` before the parent is reverted.
3. [verify_parent_table_matches_graph] After steps 0, 0b and 2, extract the
   M2 "depends on" cells from both tables, counting fields **from the end**
   (scope cells contain escaped `\|`, so fixed left offsets drift; checked on
   all six current rows): the proposal's Module Map has depends as the last
   column (`$(NF-1)`), t1853's `## Submodules` has depends then wave
   (`$(NF-2)`). The table edits in steps 0 / 0b keep those column layouts.
   ```bash
   x() { awk -F'|' -v off="$2" '/^\| \*\*M2\.[1-6]\*\*/{c=$(NF-off); gsub(/^ +| +$/,"",c); print c}' "$1"; }
   x aidocs/testing_engine/n014_explorer_006_proposal.md 1 > "$S/prop.txt"
   x aitasks/t1853_testmap_m2_registry_and_map_model.md 2 > "$S/parent.txt"
   printf '%s\n' 'M1.2' 'M2.1' 'M1.2, M2.2' 'M2.1, M3.1' 'M2.1' 'M2.1, M2.2' > "$S/expected.txt"
   diff "$S/expected.txt" "$S/prop.txt" && diff "$S/expected.txt" "$S/parent.txt"
   ```
   (`$S` = the session scratchpad.) Both diffs must be empty, with exactly six
   lines each. Then map each cell to the child graph: `M1.2` →
   omitted (t1852_2 archived); `M2.<m>` → `t1853_<m>` present in the child's
   `depends:`; `M3.1` → absent from `depends:` and named in `t1853_4`'s body
   as `M3.1 (pending: t1854 not decomposed)`. Any mismatch is fixed before the
   parent is reverted.

## Verification (of this pass)

- `aitask_ls.sh -v --children 1853 99` lists six `Ready` children; M2.1
  unblocked; the rest blocked exactly per the table.
- `grep -L 'Step 0 — Reality check' aiplans/p1853/p1853_*_*.md` and the
  no-internals sentence grep both print nothing.
- Parent `Ready`, unassigned, unlocked, `children_to_implement: [1853_1 … 1853_6]`.
- Proposal: the wave table lists M2.6 under B; M2.3's row names the two
  annotate arms and depends `M1.2, M2.2`; M2.4 depends `M2.1, M3.1`; M3.1's
  row names the runner lister; `grep -n 'go.sum. digest' ` on the proposal
  returns nothing in *Dependency scanners*.
- t1853's `## Submodules` table, the proposal's M2 rows and the child graph
  agree (post-phase 3).

## Risk

### Code-health risk: low
- The pass writes task/plan data and one documentation edit; a wrong `depends:` cell would mis-block or early-unblock a child · severity: low (residual — checked by the inline post-phase) · → mitigation: inline post-phase verify_child_dependency_graph

### Goal-achievement risk: medium
- The eight cut fixes are hypotheses made before M3/M4/M6 are planned; a child implemented without executing its Reality check would build against the proposal's description instead of the tree · severity: low (residual — heading and sentence grep-verified; executing the step remains the child's obligation) · → mitigation: inline post-phase verify_child_plans_carry_reality_check
- The `t1853_4 → M3.1` edge cannot be wired until t1854 is decomposed, and t1863 audits children against the parent's `## Submodules` table; a stale table would let it miss the edge and M2.4 unblock early · severity: medium · → mitigation: inline post-phase verify_parent_table_matches_graph (plus t1863 and the step-5 notes)
- The `go list` cache key in the proposal is unsound (local import change with unchanged `go.sum`) · severity: high before the fix · → mitigation: Deviation 7 proposal fix + M2.3 red-proved acceptance case
- Re-stamp provenance integration into M2.2's commands had no owner · severity: medium before the fix · → mitigation: Deviation 8 named extension + M2.6 command-level acceptance cases

### Planned mitigations
- timing: post-phase | name: verify_child_plans_carry_reality_check | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — child plan lacking the mandatory Reality check | desc: grep every child plan for the Step 0 heading and the no-internals sentence before committing them
- timing: post-phase | name: verify_child_dependency_graph | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — a wrong depends cell mis-blocking a child | desc: read the six depends lines back and compare with the decomposition table before reverting the parent
- timing: post-phase | name: verify_parent_table_matches_graph | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — t1863 auditing children against a stale parent submodule table | desc: diff the proposal's and t1853's M2 depends cells and map them onto the child depends, incl. the pending M3.1 reference
