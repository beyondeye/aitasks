---
Task: t1853_3_m2_3_dependency_scanners.md
Parent Task: aitasks/t1853_testmap_m2_registry_and_map_model.md
Sibling Tasks: aitasks/t1853/t1853_1_*.md, aitasks/t1853/t1853_2_*.md, aitasks/t1853/t1853_4_*.md, aitasks/t1853/t1853_5_*.md, aitasks/t1853/t1853_6_*.md
Archived Sibling Plans: aiplans/archived/p1853/p1853_*_*.md
Base branch: main
Output branch: main
---

# Plan: t1853_3 — M2.3 Dependency scanners

## Context

Parent goal: M2 — Registry and map model (everything that reads and writes
`aitestmap/` without running a test). This is **M2.3 Dependency scanners**, wave
**B**: the dependency closure the selector walks and the static facts the seeder and the packet writer read. Providers: M1.2 (`t1852_2`, landed, archived) and M2.2 (`t1853_2`).

This coarse plan records what the proposal fixes for M2.3. It does not design internals against providers that do not exist yet; the Reality check below does that when this child is picked.

**Automation-first (user directive, 2026-10-11).** Human review belonged to an
older design. No verb, load rule or check rule shipped here may make a human
action a precondition of any path; `by: human:<email>` is an optional recorded
value, never a gate. A human-only step met in the proposal is reported to its
owning parent (note), never encoded here.

## Proposal reading list

`aidocs/testing_engine/n014_explorer_006_proposal.md` (M2 cut fixed in `3bc0de8ac`): Module Map row M2.3; *Dependency scanners (M2.3)*; *Annotation scanner and rewriter* (the `--suggest` / `--from-body` arms); `assumption_static_granularity_v1`, `assumption_kotlin_scanner_fail_closed`; `tradeoff_static_scanner_overselection`; *Named follow-ups* (versioned plugin contract, symbol-level attribution — not v1); *Architecture → The
registry directory, Where state lives, Line-protocol index*; *Invariants every
module honours*; *Assumptions → The map and freshness (M2, M4)* and *Variants,
broad tests and runners (M2, M3)*; *Tradeoffs → Map and registry structure
(M2, M3)*. Parent plan `aiplans/p1853_testmap_m2_registry_and_map_model.md`
(Deviations from the proposal). Engine rules: `goengines/README.md` ("Rules
for engine submodules", "Interfaces"). Owns cells read `internal/<pkg>` as
`goengines/internal/testmap/<pkg>`.

## Owned files / provides / consumes

- **Owns:** `goengines/internal/testmap/deps/**`; the `--suggest` / `--from-body` arms in `goengines/internal/testmap/annot/` (named extension of M2.2); one red-proved fixture per opaque branch; the red-proved changed-local-import fixture.
- **Provides:** the closure (M4.1); `static:invocation` / `static:import` / `static:package` facts, anchor lines, declared symbols (M6.2, M7.1, M7.4); `annotate --suggest` / `--from-body`.
- **Consumes:** M1.2: `internal/platform` (`PoolCap`, `NewGroup`, `CacheRoot`), `internal/gitx`, `testmap.CacheDir()`, fixtures; M2.2: the `annot` package and its arm extension point.

## Step 0 — Reality check (MANDATORY, before any code; outcome recorded in this plan file)

Execute and record here, before writing any code:

1. Re-read the proposal's Module Map row for M2.3, its component
   subsections, and the row of every interface it consumes (*Cross-module
   interfaces*).
2. Inspect the **actual current state** of every provider on the merge target
   — verbs, line protocols, files, hooks and tests — and name the task and
   commit that landed each. The proposal and this coarse plan are claims to
   verify, never facts. Specifically:
- **Decide the `go list` cache key** (Deviation 7): it must change with any Go source's import set as well as `go.mod` / `go.sum` — candidates: per-file import parse keyed by blob; a digest over the module's `.go` blobs incl. uncommitted edits. Record the choice and why.
- M2.2 as landed: where the `--suggest` / `--from-body` arms attach.
   - The parent plan's *Repository reality anchors* (verified 2026-10-11 at
     `2fe3f8cb7`) — re-verify each one this child relies on.
3. Tabulate every difference: *proposal says* / *coarse plan says* /
   *repository has*.
4. Decide per difference: adapt this child to reality; revise this coarse
   plan; or revise the proposal (cut errors and interface changes go there,
   per the parent body's protocol §1). Record the decision and its reason.
5. Send a note (`/aitask-note`) to every downstream child whose assumptions a
   difference or decision breaks, hedging what the tree cannot prove.
6. Re-confirm that every file this child will touch is owned by M2.3 or is
   the owner's named extension (the "one owning submodule" rule).

## Implementation steps (coarse)

1. Step 0 — Reality check (above).
2. Scanner interface + the XDG blob cache (`<blob-sha1>.json`), inverted in memory.
3. bash scanner: literal invocation / source facts incl. `$SCRIPT_DIR`- and `$PROJECT_DIR`-relative forms against every source root.
4. python scanner: direct imports of main-root files incl. the file's own `sys.path` bootstrap.
5. go scanner: `go list -deps -json` behind the import-set-aware cache key; package membership facts.
6. kotlin scanner with the closed construct list and every opaque branch (inline fun, `const val`, DI bindings, reflection, generated / KSP sources, unreadable file); Gradle module graph.
7. Plugin protocol under `aitestmap/scanners/` (one JSON line per file `{file, deps, opaque?, reads?}`); opt-in `android-res` symbol scanner.
8. Exported facts: the three `static:*` relations, anchor lines, declared symbols (never a source body).
9. `annotate --suggest <test>` (covers lines from the closure) and `annotate --from-body` (Kotlin symbol resolution) as arms in `annot`.

## Verification

- One red-proved fixture per Kotlin opaque branch.
- bash literal invocation incl. the `$SCRIPT_DIR` / `$PROJECT_DIR` forms; python `sys.path` bootstrap import; go package membership.
- Plugin JSON-line protocol; cache hit by blob; `android-res` opt-in.
- `annotate --suggest` / `--from-body` outputs on fixtures.
- **Go cache invalidation, red-proved:** in a fixture module, add an import of another local package with `go.mod` / `go.sum` byte-identical, re-scan, and assert the new dependency (and the test it reaches) appears; the case must fail against a `go.sum`-only key.
- `ait engine test` (`go vet` + `go test` over `goengines/`) green; the
  Invariants 4–5 tripwire in `goengines/guards_test.go` passes.
- No path shipped here requires a human action (automation-first).

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9 (archival; current
branch, no merge).
