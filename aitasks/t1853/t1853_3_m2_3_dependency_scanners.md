---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-11 17:42
updated_at: 2026-10-11 17:42
---

## Context

Child **M2.3 — Dependency scanners** of t1853 (test map, module M2). Wave
**B**. The closure the selector walks and the static facts the seeder and the
packet writer read. **Providers:** M1.2 (`t1852_2`, landed, archived) and
M2.2 (`t1853_2`, for the two `annotate` arms).

Authoritative specification: `aidocs/testing_engine/n014_explorer_006_proposal.md`
(M2 cut fixed in `3bc0de8ac`) — Module Map row M2.3, component *Dependency
scanners (M2.3)*, *Annotation scanner and rewriter* (the `--suggest` /
`--from-body` arms), *Assumptions → `assumption_static_granularity_v1`,
`assumption_kotlin_scanner_fail_closed`*, *Tradeoffs →
`tradeoff_static_scanner_overselection`*, *Named follow-ups*. Parent plan:
`aiplans/p1853_testmap_m2_registry_and_map_model.md` (Deviations 4, 7).

**Coarse plan only.** `aiplans/p1853/p1853_3_m2_3_dependency_scanners.md`
records what the proposal fixes; its **Step 0 — Reality check** (mandatory,
before any code, recorded in the plan) inspects M1.2 and M2.2 as they landed
and decides the exact `go list` cache key.

## Scope (from the proposal, after the M2 cut fix)

- Built-in scanners: bash (literal invocation facts incl. `$SCRIPT_DIR` /
  `$PROJECT_DIR`-relative forms against every source root), python (direct
  imports incl. the file's own `sys.path` bootstrap), go (`go list -deps -json`
  behind a cache whose key changes with **any Go source's import set** and with
  `go.mod` / `go.sum` — never `go.sum` alone), kotlin with the opaque contract
  (closed construct list; inline functions, `const val`, DI bindings,
  reflection, generated/KSP sources and unreadable files mark the file opaque),
  the Gradle module graph.
- Plugin protocol: executables under `aitestmap/scanners/` speaking one JSON
  line per file `{file, deps, opaque?, reads?}`.
- The opt-in `android-res` symbol scanner.
- The XDG blob cache `${XDG_CACHE_HOME:-~/.cache}/aitasks/testmap/deps/<blob-sha1>.json`
  (`testmap.CacheDir()`), inverted in memory.
- Exported facts: `static:invocation` / `static:import` / `static:package`,
  anchor lines, declared symbols (never a source body).
- `annotate --suggest <test>` (covers lines from the closure) and `annotate
  --from-body` (from the Kotlin scanner's symbol resolution) as **named
  extensions of M2.2's `internal/annot`**.

## Key files to modify

- `goengines/internal/testmap/deps/**` — new package (owned).
- The `--suggest` / `--from-body` arms in `goengines/internal/testmap/annot/`
  (named extension of M2.2).

## Reference files for patterns

- `goengines/internal/platform` (`CacheRoot`, `PoolCap`, `NewGroup`),
  `goengines/internal/gitx` (`BlobDigest`, `LsTree`), `testmap.CacheDir()`,
  `goengines/internal/testmap/fixture/`.

## Provides / consumes

- **Provides:** the closure (M4.1), facts (M6.2, M7.1, M7.4), `annotate
  --suggest` / `--from-body`.
- **Consumes:** M1.2, M2.2.

## Implementation plan (coarse)

1. Step 0 — Reality check (decide the `go list` cache key).
2. Scanner interface + cache; per-language scanners; plugin protocol.
3. Kotlin opaque branches with red-proved fixtures; `android-res`.
4. The two `annotate` arms.

## Verification

- One red-proved fixture per Kotlin opaque branch; bash literal invocation
  incl. the `$SCRIPT_DIR` / `$PROJECT_DIR` forms; python `sys.path` bootstrap
  import; go package membership; plugin JSON-line protocol; cache hit by blob;
  `android-res` opt-in; `annotate --suggest` / `--from-body` outputs.
- **Go cache invalidation, red-proved:** in a fixture module, add an import
  of another local package with `go.mod` / `go.sum` byte-identical, re-scan,
  and assert the new dependency (and the test it reaches) appears; the case
  must fail against a `go.sum`-only key.

## Automation-first (user directive, 2026-10-11)

Human review belonged to an older design. No path shipped here may make a
human action a precondition.
