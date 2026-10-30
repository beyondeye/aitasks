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
the *M3.2 re-decomposition* section of
`aitasks/t1854_testmap_m3_runners_scheduling_and_cost.md`). It is not part of
M3 v1.

The rejected first M3.2 design inferred per-file bash results by injecting a
`BASH_ENV` EXIT trap into a suite command. The user directive is that
automatic shell exit hooks are a **separately designed integration** that
reports through t1854_14's documented reporting contract. They are never
inferred from a suite's exit.

## Goal

Design and, only if it can meet the contract, implement an automatic
per-script exit report for `full: true` suites that run bash test files one per
process. Its output is a reporting-contract format (t1854_14), so attribution
goes through the shared engine reconciler (t1854_2, G1a/G1b).

## Acceptance criteria

- **A written design first.** It covers:
  - how the hook is installed without changing any command's own outcome: its exit status, `set -u`, an existing `BASH_ENV` chained, a test's own `trap … EXIT`;
  - which processes it records: top-level scripts only, filtered to discovered units of subsumed `bash-file` runners;
  - what it can never see (`exec`, replaced traps, a monolithic script). Those stay `unaccounted`, never a pass.
- **Transparency tests** with real bash, proving the command's exit and output are unchanged.
- **Reconciliation tests** through t1854_14's path: duplicates, missing and unexpected scripts.
- **Opt-in only**, named in `runners.yaml`; off by default.

## Un-park when

t1854_14 has landed and its reporting contract is stable.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t22_3** id=2026-10-29T22:23:47Z.86af85dc02915fed65582407 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:23:47Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.
