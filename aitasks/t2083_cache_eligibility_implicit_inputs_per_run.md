---
priority: low
effort: medium
depends: []
issue_type: performance
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
followup_kind: review_finding
created_at: 2026-10-20 15:21
updated_at: 2026-10-20 15:21
---

## Origin

Review finding (medium, follow-up disposition) raised during t2081's Step 8 review: anchor eligibility recomputes repository-wide data per result.

## Problem

`cost.Rows` invokes `judge.decide` for every result of a run with one `judge`, whose loaded `inputs` (graph, reads, covers) are immutable for the run. Still, per result:
- `implicitFiles` (`goengines/internal/testmap/cost/implicit.go`) clones and scans `g.Files()` for every Go or Kotlin test: same-directory `.go` files, and every Gradle script;
- Kotlin `implicitHit` scans `g.Files()` again for non-root settings scripts (included builds);
- `judge.extend` re-walks `Graph.Closure` for every implicit input. For Kotlin that is every Gradle script, shared by all Kotlin tests;
- `implicitHit` for Go opens an `os.Root` and runs `regularNoFollow` per modified path.

A large batch therefore repeats repository-wide work and allocations.

## Goal

Cache, inside the judge or its `inputs`, computed at most once per run:
- a directory → Go files index;
- the Gradle script list;
- the included-build directories;
- memoized `Closure` results per start file (closures are immutable for the run).

Keep every `anchor_reason` byte-identical. All of `cost/implicit_test.go` and `cost/eligibility_test.go` must pass unchanged. Add a benchmark (or a counted-call test) showing that the per-result repository scans are gone on a multi-unit batch, with a pre-change control.
