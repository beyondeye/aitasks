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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1985** id=2026-10-15T05:57:51Z.f3c41ec6b704588068c40319 from=t1985 from_verified=yes at=2026-10-15T05:57:51Z base=a81352ffb83835a8bed91624f991841c01902cee base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1985 (hang watchdog for the runner package's tests), as of commit a81352ffb:
> | 
> | - In goengines/internal/testmap/runner, every test that starts a process (newRepo/fixture.New, Run, Load, registry.Scan/Check with Lister{}, exec.Command, …) now starts with
> |       if !isolated(t, hangLimit) {
> |           return
> |       }
> |   That runs it in a re-executed subprocess under a 20 s bound, with HANG:<test>|<limit> reporting and env-marker cleanup of its runner processes.
> | - If the "annot.Source runs once per scan/check" test you plan lands in package runner and builds a fixture repo, it likely needs this guard as its first statement. A counting seam set in the parent is not visible to the subprocess: set it inside the test body, which runs in the child.
> | - If the test lands in package registry instead, the helper is not available there (it is _test.go code of package runner), and today nothing equivalent exists in registry.
> | - Follow-up t1998 will add a tripwire that enforces the guard in package runner.
