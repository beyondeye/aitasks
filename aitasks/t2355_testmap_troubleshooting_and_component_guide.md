---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: [testmap, testing, documentation]
anchor: 1852
created_at: 2026-11-24 19:13
updated_at: 2026-11-24 19:13
---

## Goal

Give maintainers a durable starting point when `ait test` or `ait testmap` behaves unexpectedly. The guide must remain usable after the M1–M10 implementation tasks and their plans are archived. Start with the interfaces already available and label any entries that still depend on unfinished work.

## Scope

- Coordinate with M9.3/M9.4 (t1860) so the maintenance skill, framework docs, and Go engine README point to the same guide. Keep the main guide in maintained repository documentation.
- Walk through the path from a task's changed files to its completion verdict. Map the registry, scanners and evidence, selection and widening, runners and scheduling, cost and scoring, readiness and completion policy, and the framework gates to their owning repositories, shipped commands or packages, and relevant M1–M10 work. Task and plan IDs can provide implementation history.
- Organize troubleshooting by observable symptoms. Include a selected run that missed a failure, unexpected full-suite fallbacks, tests missing from discovery, stale or opaque inputs, runner errors or timeouts, and a completion gate that refuses to run or changes policy. For each, give the first read-only checks, how to interpret the relevant output and stored evidence, and how to decide whether the fix belongs in a project's map, the Go engine, or the framework.
- Add a reusable incident record with the project, task, revision, and run IDs, expected and observed behavior, relevant evidence, suspected component, and any resulting fix task. Make it usable by the post-rollout retrospective.

## Acceptance

A maintainer can start from the framework docs, trace a missed test and an unexpected full run to the responsible component using documented evidence, and open an actionable follow-up without having to recover an archived implementation plan first. Verify commands and output against shipped behavior.
