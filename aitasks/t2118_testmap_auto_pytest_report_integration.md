---
priority: low
effort: medium
depends: [t1854_14]
issue_type: feature
status: Postponed
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
created_at: 2026-10-21 22:07
updated_at: 2026-10-30 12:10
---

## Context

Deferred integration from the t1854 M3.2 re-decomposition (2026-10-21; see
the parent t1854's *M3.2 re-decomposition* section). It is not part of M3 v1.

The rejected first M3.2 design injected a pytest plugin (`PYTHONPATH` plus
`-p` in `PYTEST_ADDOPTS`) into suite commands to collect per-test JUnit XML.
The user directive is that injected pytest plugins are a **separately designed
integration** that reports through t1854_14's documented reporting contract.

## Goal

Design and, only if it can meet the contract, implement an opt-in automatic
pytest report integration for `full: true` suites. It writes a
reporting-contract format, so attribution goes through the shared engine
reconciler (t1854_2, G1a/G1b), and case identities are checked against the
`pytest` adapter's native discovery (t1854_9).

## Acceptance criteria

- **A written design first.** It covers:
  - per-process report files (several pytest processes per suite), xdist controller versus workers, and an explicit `--junitxml` from the project;
  - failure modes (`python -I` / `-E` ignoring `PYTHONPATH` must never break the suite: detected and refused, or degraded to "no child evidence");
  - which discovery the identities are reconciled against.
- **Transparency tests** with real pytest 8.x: the suite's exit and outputs are unchanged.
- **Reconciliation tests** through t1854_14's path: duplicates, substitutions, missing cases, mixed pass/skip.
- **Opt-in only**; off by default.

## Un-park when

t1854_14 and t1854_9 have landed.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1854_9** id=2026-10-26T08:06:31Z.298425d9feeb472b036cd246 from=t1854_9 from_verified=yes at=2026-10-26T08:06:31Z base=7f49dbd62e8c9ab5ae05de2935184d3bf72256d7 base_branch=main dirty=no host=omg16
>
> | Advisory, from t1854_9 (M3.2f pytest adapter), as landed in 0c2f693c9. Not checked against your design.
> | - The pytest BUILTIN adapter now loads an engine-owned, observe-only evidence plugin (-p + PYTHONPATH prepend; goengines/internal/testmap/runner/builtin/pytest_evidence_plugin.py). It is adapter-scoped (the engine runs pytest itself) and does not implement your deferred suite-command injection; the user authorized it for the builtin on 2026-10-25.
> | - Measured facts you can reuse (pytest 8.4.2, xdist 3.8.0): plugin hooks fire in xdist workers too, so a plugin must write only on the controller (`not hasattr(config, "workerinput")`); the controller then receives every worker test report and collect report (skip, error) exactly once; pytest_collection_finish does not run on the controller in an xdist run, but does under --collect-only -n. Under xdist a collection error does not abort the session (exit 1, tests still run); plain pytest exits 2.
> | - `python -I -m pytest -p <module>`: exit 1, traceback ending `ImportError: Error importing plugin …` on stderr — detectable as "plugin did not load" (the builtin refuses the list). A conftest raising UsageError in pytest_configure exits 4 before the plugin writes anything.
> | - Teardown phases can skip (pytest.skip in fixture teardown → teardown/skipped after call/passed).

> **✉ note:t22_3** id=2026-10-29T22:23:50Z.0326bc69e2a3a5bb51dfb1ad from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:23:50Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:12:14Z.3cd24724fa225894647813d1 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:12:14Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | Re-homed: the engine work of this task moved to aitasks_go#t75
> | (beyondeye/aitasks_go). This task is Postponed as a pointer and must not be
> | picked. History of its completed siblings: aitasks_go
> | aidocs/aitasks_go/testmap_history/.
