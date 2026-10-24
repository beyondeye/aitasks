---
priority: medium
effort: medium
depends: [t2131_3]
issue_type: feature
status: Ready
labels: [testmap, go_engine, testing]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-23 11:51
updated_at: 2026-10-24 23:23
---

## Context

Child 4 of t2131 (test-map code-module tier).
- **Parent plan:** `aiplans/p2131_testmap_code_modules_tier.md`, default 5.
- **Coarse plan:** `aiplans/p2131/p2131_4_modules_language_package_providers.md`.
- **Wave:** C (M2.7). Depends on t2131_3 (table, driver and verb).

The dependency graph knows Go and Python packages only during resolution, then **discards** them:
- `goResult` is dropped (`deps/golist.go:80-85`);
- `pyPackage` / `pyModel` are dropped (`deps/python.go:1511-1523,1756-1763`);
- `goRaw.Package` is dropped (`resolve.go:12`).

So `deps.Graph` exposes no package facts. This child exposes those facts and adds the two providers:
- **Go:** every package under a `go.mod` is one module, `go:<dir>`;
- **Python:** every package (a regular package or a namespace portion) is one module, `py:<dir>`.

Revised 2026-10-24 (user decision): code modules are flat, with no submodules. These are **package providers**:
- a package module owns **only that package's own source files** directly in its directory (`*.go` with test files, or `*.py` / `*.pyi`);
- it never owns a subtree, so a subpackage is just another module and no package claims the unrelated files beside it;
- the name writes `/` as `:` and the repository root directory as `.`. A root package is `go:.` / `py:.`. It is legitimate and bounded, because it owns only its own files;
- a package directory whose name contains `:` or another character the name rule refuses is `MODULE_REFUSED:<provider>|<dir>|unnameable`, and its files stay unmapped.

The contract is the proposal's component *Code modules*.

Both rank below hand, agent, codemap and Gradle (default 5). Overlaps are reported as `MODULE_CONFLICT:`.

**Why a separate child:** it carries the immutability and cache-key risk, so it should not block the table work in t2131_3.

**Automation-first:** no human step.

## Key Files to Modify

- `goengines/internal/testmap/deps/graph.go`: new copy-returning accessors (e.g. `GoPackages()`, `PyPackages()`), keeping `Graph` immutable.
- `goengines/internal/testmap/deps/scan.go`, `golist.go`, `python.go` and `resolve.go`: retain the facts on the graph.
- The deps cache: its key must cover every newly retained input (memory `feedback_cache_keys_cover_every_consumed_input`).
- `goengines/internal/testmap/modules/`: the `golang` and `python` providers.

## Reference Files for Patterns

- `deps/graph.go`: `Modules()` returns a sorted copy (119-125).
- `deps/kotlin_test.go:523-604`: the copy-immutability test for `Modules()`.
- `deps/helpers_test.go` (`repo`, `scanRepo`, `requireEdge`) and `internal/testmap/fixture/fixture.go` (real git fixtures).

## Implementation Plan

1. **Step 0 — Reality check.**
   - Read what the cache stores and keys on.
   - Run `deps.Scan` on this repo and on fixtures to see which package facts exist.
   - Confirm that the t2131_3 provider interface is as landed.
2. Retain the Go module and package facts on the graph, plus the Python package and namespace-portion facts, with copy-returning accessors.
3. Extend the cache key. Add a test that changing a package fact changes the key.
4. Add the two providers in `modules`, with precedence and conflicts per t2131_3.

## Verification Steps

`ait engine test` is green, plus:
- a Go module and package fixture;
- Python packages, including a namespace portion;
- accessors return copies;
- the cache key changes when package facts change;
- a Go/Python vs codemap overlap reported as `MODULE_CONFLICT:`;
- the proposal's worked example 6:
  - `go.mod` sits at the root of `example.com/tool`, so `go:.` owns `main.go` and `main_test.go`, `go:tool` owns `tool/*.go`, and `README.md` is unmapped;
  - a change to `tool/parse.go` reached from `main.go` affects {`go:tool`, `go:.`};
  - a change to `README.md` is `WIDEN_FULL:unmapped_path`;
- name safety: `a/b/` gives `go:a:b` and `a.b/` gives `go:a.b` (distinct), while `a:b/` is refused (`MODULE_REFUSED:go|a:b|unnameable`);
- run on this repo's own `deps.Scan`, with the result recorded in the plan.
