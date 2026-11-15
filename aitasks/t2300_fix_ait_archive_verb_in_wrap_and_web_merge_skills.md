---
priority: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [documentation, doc_quality]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2258
followup_kind: upstream_defect
created_at: 2026-11-15 13:05
updated_at: 2026-11-15 13:11
---

## Origin

Spawned from t2284 during Step 8b review.

## Upstream defect

- `.claude/skills/aitask-wrap/SKILL.md.j2:349` names a non-existent `ait archive <N>` dispatcher verb. The flags belong to `./.aitask-scripts/aitask_archive.sh`. The current text is "the user can archive manually later with `ait archive <N>`".
- `.claude/skills/aitask-web-merge/materialize-gates.md:33` names the same non-existent verb ("repair manually via aitask_gate.sh materialize-active + ait archive").

## Diagnostic context

t2284 corrected the same claim on `website/content/docs/development/task-format.md`
(the `archived_reason` row now names `./.aitask-scripts/aitask_archive.sh`). The
`ait` dispatcher has no `archive` verb. These two skill sources were left out of
t2284's scope because they are skill sources with goldens and ported copies.

## Suggested fix

Replace `ait archive <N>` with `./.aitask-scripts/aitask_archive.sh <N>` in both
sources. Then regenerate the affected goldens, run
`./.aitask-scripts/aitask_skill_verify.sh`, and port the change to the Codex and
OpenCode trees (or create tasks to port it).
