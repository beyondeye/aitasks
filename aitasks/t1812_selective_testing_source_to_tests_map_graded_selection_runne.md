---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [testing, test_infrastructure, brainstorming, gates, framework]
created_at: 2026-09-15 09:25
updated_at: 2026-09-15 09:25
attachments:
  - hash: sha256:79088753bb9d611ded7e0f4574672b061a800815703883e5667a18e39accf34e
    name: selective_testing_proposal.md
    mime: text/plain
    size: 23963
    added_at: 2026-09-15 09:25
    backend: local
---

Design and build a generic **selective testing** subsystem for the aitasks
framework: a maintained relation between source files and test units, a
mechanical translation from a task's change set to the ranked set of tests
that must run (with a reason on every line), a standard runner contract with a
runner repository and per-test runner assignment, declared concurrency
resources, per-test cost tracking by host class, a failure feedback loop, two
enforcing gates, and an agent skill that keeps the map current.

**This task is being designed through `ait brainstorm`.** The seed proposal
(three rounds of design discussion on 2026-09-15) is attached to this task as
`selective_testing_proposal.md` and imported as the brainstorm root node
`n000_init`. The design is deliberately NOT final; the brainstorm holds the
open questions.

## Why

Every target repo runs either its whole suite per task or nothing. This repo
has ~415 shell and ~335 python test files and `test_command: null`, so nothing
gates. thinking_app has one ~8 minute heavy gate; its blast-radius rules live
only in prose. Naming conventions (`tests/test_gate_pass.sh` tests
`aitask_gate_pass.sh`) are the only source-to-test knowledge, and nothing
tracks when it rots.

## Targets

aitasks, thinking_app, thinking_backend, aitasks_go, aitasks_mobile. Between
them: one-process-per-file bash tests, batched pytest modules, Go packages
with `-run` regexes, Gradle class FQNs behind a host lock with memory
admission, selector-less whole suites, and device tests needing an allocated
emulator.

## Decisions taken so far

- Registry lives in the code tree under `aitestmap/`, as a directory whose
  files are merged; `_scanned.yaml` is written only by scanning in-test
  `testmap:covers` annotations, hand files declare `owns:` globs.
- Selection is a graded graph walk (distance per unit, cut knobs applied
  afterwards), not hand-typed basic/deep/deepest labels and not profile tiers.
- Blast radius is data: rules with `select`, `implies`, `escalate` effects.
- Static scanners plus manual attribution via skills; fail-closed with
  expiring waivers; full-run machinery for CI or on demand.
- Runner contract: `describe`, `list`, `run --manifest --out`; results as
  run-id-stamped JSONL; exit contract 0/1/2/75 as in thinking_app.
- Concurrency as declared resources (mutex, semaphore, admission, allocator;
  scopes host, worktree, run; `acquired_by` for wrapped locks) with a
  `schedule` report that characterises waves and critical path.
- Cost per execution unit with Welford stats, keyed by host class.

## Open questions (see brainstorm)

Symbol-level granularity; sufficiency of the three rule effects; concurrent
versus serial-with-report scheduler in v1; routing of new declared edges;
device-unit default policy; committed versus local cost summaries; CI
evidence format; how the thinking_app screenshot gate is wrapped; the per-repo
bootstrap procedure.

Expected outcome of the brainstorm: a finalized proposal exported to `aiplans/`
and a decomposition into child tasks (registry and CLI, scanners, selector,
runner contract plus reference runners, scheduler and resources, cost ledger,
gates, skill, per-repo bootstrap).

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t15** id=2026-10-25T07:37:11Z.f933cbac1ed9c438771857b7 from=aitasks_go#t15 from_verified=yes at=2026-10-25T07:37:11Z base=60ca89154aa0d66ceec006c9f8c6b764fe661ae6 base_branch=main dirty=yes host=omg16
>
> | Advance notice from aitasks_go (t15, aidocs/aitasks_go/ship_path.md there): ait-testmap Go
> | development is scheduled to MIGRATE from public `goengines/` into the private aitasks_go
> | repository (nested module `goengines/`); public goengines then receives exported snapshots
> | only (no tests/bench/ci), with provenance trailers `Exported-From:` / `Migrated-From:`.
> | 
> | Nothing changes until the cutover. The migration is aitasks_go#t22; it depends on the
> | export tooling (aitasks_go#t21) and on aitasks t2138 (two-mode goengines CI keyed on
> | goengines/EXPORT.txt — legacy pipeline stays required until the bootstrap export).
> | Before the cutover t22 inventories in-flight testmap tasks, sessions, locks, worktrees and
> | PRs touching goengines, waits for or checkpoint-hands-off overlapping work (never relocating
> | an actively owned task), holds a brief coordinated pause, re-checks freshly, then re-homes
> | engine-only tasks to aitasks_go and splits mixed ones (Go part there; shim/installer/skills/
> | docs/aitestmap stay here). Expect per-task notes at that point. Emergency public fixes after
> | the cutover carry a `Return-To: aitasks_go` trailer plus a return task in aitasks_go.

> **✉ note:t22_3** id=2026-10-29T22:22:03Z.ec80360a8dfb8cf1cedcf863 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:22:03Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:14:55Z.35ab299407878c8aae4b8d15 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:14:55Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | goengines freeze lifted (aitasks_go#t22 cutover complete).
> | Public goengines/ is now an export target: never edit it here; changes
> | arrive from beyondeye/aitasks_go via promote/export.sh.
> | - This task has no engine part and stays here unchanged.
