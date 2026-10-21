---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [task_attachments, html_plans]
gates: [risk_evaluated]
anchor: 1065
created_at: 2026-07-06 18:29
updated_at: 2026-07-06 18:29
boardidx: 140288
---

**Design spec:** `aidocs/unified_artifact_design.md` §4, §10.

## Context

Brainstorm / evaluation task (settled at t1076_2 planning: the `attachments:` and
`artifacts:` frontmatter fields stay SEPARATE for now, and this task tracks the
deferred unification question).

The unified artifact design reconciles the two models (§10): an attachment is the
single-version, never-repointed degenerate case of an artifact. t1030 stores
attachment state inline in frontmatter (`hash`/`backend` — safe because
immutable); t1076_2 stores artifact state in per-artifact manifests
(`artifacts/manifests/<id>.json`) with handle-only frontmatter.

## Goal

Evaluate the pros and cons of recasting attachments as single-version artifacts
under the one `artifacts:` schema (`kind: attachment`), and either:
- decide + plan a migration (frontmatter recast, `ait attach` CLI over the
  manifest layer, per-blob refcount ledger interplay, fold/gc paths, tests), or
- record a durable decision to keep the two fields separate (update design §4/§10
  from "settled for now" to "settled permanently" with the rationale).

## Considerations to weigh

- One schema/CLI surface vs. the churn of rewriting shipped, test-pinned t1030
  code (attach CLI, per-blob meta ledger, fold rebind, board decref, gc).
- Manifest-per-attachment overhead (a file per attachment on the data branch)
  vs. inline-hash zero-indirection reads.
- The gc blocking set already unions both reference classes (frontmatter hashes +
  manifest versions) — unification would collapse them to one.
- Consumer impact: board, mobile app, website — anything parsing `attachments:`.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1890** id=2026-10-21T12:34:04Z.1c6b506268c1c557115be1ea from=t1890 from_verified=yes at=2026-10-21T12:34:04Z base=ba4fde3822c67af2fb3aee56c36a16d673b3e1d2 base_branch=main dirty=yes host=omg16
>
> | Advisory from t1890 (aidocs/artifact_storage_lifecycle.md, commit ba4fde382). The storage lifecycle (download model, routing, retention, purge scope) was decided once for both attachments and artifacts, because they share the blob store. Whichever way you decide on unification, cross-reference that doc rather than restating the policy.
