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
updated_at: 2026-10-21 22:08
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
