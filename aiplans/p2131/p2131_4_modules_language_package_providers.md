---
Task: t2131_4_modules_language_package_providers.md
Parent Task: aitasks/t2131_testmap_code_modules_tier.md
Sibling Tasks: aitasks/t2131/t2131_1_*.md … aitasks/t2131/t2131_3_*.md, aitasks/t2131/t2131_5_*.md … aitasks/t2131/t2131_12_*.md
Archived Sibling Plans: aiplans/archived/p2131/p2131_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2131_4 — Go and Python package providers (coarse)

## Context

- **Parent goal.** The code-module tier.
- **This child.** It exposes the Go and Python package facts that `deps`
  computes during resolution and then discards:
  - `goResult` (`deps/golist.go:80-85`);
  - `pyPackage` / `pyModel` (`deps/python.go:1511-1523,1756-1763`);
  - `goRaw.Package` (`resolve.go:12`).

  It then adds the two providers (default 5):
  - **Go:** every package under a `go.mod` is one module, `go:<dir>`;
  - **Python:** every package (regular or a namespace portion) is one module,
    `py:<dir>`.

  Revised 2026-10-24 (user decision): code modules are flat. These are
  **package providers**:
  - a module owns only the package's own source files directly in its
    directory (`*.go`, or `*.py` / `*.pyi`), never a subtree;
  - `/` is written as `:` and the root directory as `.` (`go:.` is a
    legitimate, bounded root package);
  - an unnameable directory (one containing `:` …) is refused as
    `MODULE_REFUSED:<provider>|<dir>|unnameable`.

  Both rank below hand, agent, codemap and Gradle.
- **Wave:** C (M2.7). Depends on t2131_3.

This coarse plan records what the parent pass fixed for this slice. It does not design internals against providers that do not exist yet; the Reality check below does that when this child is picked.

**Automation-first:** no human step.

## Reading list

- `deps/graph.go`, `deps/scan.go` (171-219), `deps/golist.go`,
  `deps/python.go` and `deps/resolve.go`.
- The deps cache: what it stores and keys on.
- `deps/kotlin_test.go:523-604` (the copy-immutability test).
- The t2131_3 provider interface, as landed.

## Owned files / provides / consumes

- **Owns:**
  - the new `deps.Graph` accessors and the retention of package facts;
  - the cache-key extension;
  - `modules` providers `golang` and `python`.
- **Provides:** module rows from Go and Python packages.
- **Consumes:** the t2131_3 driver, precedence and `MODULE_CONFLICT:`.

## Step 0 — Reality check

1. Read what the cache stores and keys on. Every newly retained input must be
   in the key (memory `feedback_cache_keys_cover_every_consumed_input`).
2. Run `deps.Scan` on this repo and on fixtures, and list the package facts
   available.
3. Confirm the t2131_3 provider interface as landed.
4. Record the outcome here.

## Implementation steps (coarse)

1. Retain the Go module and package facts and the Python package facts
   (including namespace portions) on the graph.
2. Add copy-returning accessors, so `Graph` stays immutable.
3. Extend the cache key.
4. Add the two providers, with precedence and conflicts per t2131_3.
5. **Commit.** `feature: … (t2131_4)`.

## Verification / acceptance

`ait engine test` is green, plus:
- a Go module and package fixture;
- Python packages, including a namespace portion;
- accessors return copies;
- the cache key changes when package facts change;
- a Go/Python vs codemap overlap reported as `MODULE_CONFLICT:`;
- the proposal's worked example 6 (`go:.` and `go:tool` distinct; ordinary
  widening over the root package; `README.md` unmapped);
- `a/b/` and `a.b/` give the distinct names `go:a:b` and `go:a.b`; `a:b/` is
  refused;
- this repo's own scan result recorded here.

## Step 9 reference

Shared post-implementation. Current branch, no merge.
