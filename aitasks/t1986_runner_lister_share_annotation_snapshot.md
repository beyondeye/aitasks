---
priority: low
effort: medium
depends: []
issue_type: performance
status: Ready
labels: [testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
followup_kind: review_finding
created_at: 2026-10-14 17:26
updated_at: 2026-10-14 17:26
---

## Context

Review finding from t1854_1 (M3.1, runner contract), dispositioned as a
follow-up by the reviewer. In production `scan` / `check`, M2.1's
`registry.readInputs` (`goengines/internal/testmap/registry/inputs.go`)
already reads every annotation through `annot.Source{}.Annotations` before it
calls `Lister.List`. M3.1's `runner.Load`
(`goengines/internal/testmap/runner/repo.go`) then calls
`annot.Source{}.Annotations` again, for the `testmap:runner` overrides and
the `batch` / `needs` keys. Every `scan` / `check` therefore lists and parses
the repository's annotated files twice.

## Goal

One annotation read per operation, without changing any behaviour.

- **Option A:** a per-operation annotation snapshot that `readInputs` hands
  to the lister.
- **Option B:** an internal `runner.LoadWith(ctx, root, anns)` that accepts
  existing annotations. `Lister` would then need a way to receive them, and
  `UnitLister` is M2.1's interface, so any change to it is a named extension
  agreed with its owner.

Whichever option is taken:

- standalone `run` keeps loading its own annotations;
- the lister's fail-closed behaviour is unchanged (an annotation error is
  still `INPUT_ERROR`);
- `run` / `scan` / `check` outputs are byte-identical before and after.

## Verification

- A benchmark (`BenchmarkScanWithRunnerLister` or similar) recorded with
  `benchgate -update` shows the second parse gone.
- A test pins that `annot.Source` runs once per `scan` / `check` (a counting
  source injected through the same seam).
- `ait engine test` stays green.
