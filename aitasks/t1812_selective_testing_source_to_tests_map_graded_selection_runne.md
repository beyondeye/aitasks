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
