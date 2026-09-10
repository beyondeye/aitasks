---
priority: medium
effort: low
depends: [t1663_4]
issue_type: documentation
status: Ready
labels: [task-workflow, documentation]
gates: [risk_evaluated]
anchor: 1538
created_at: 2026-09-01 15:20
updated_at: 2026-09-02 10:05
---

Document the advisory premise-staleness check in the website docs.

## Context

Fifth child of t1663 — docs are a first-class child per `aidocs/framework/planning_conventions.md`, not a verification afterthought. Design source: `aidocs/framework/task_premise_staleness.md`; the landed behavior of children 1-4 is the documentation source of truth (document current source, not the plan — re-check against what actually shipped).

## Key files

- `website/content/docs/workflows/` — a new page (or a section of the pick/task-workflow page, matching how the manual-verification workflow is documented in `website/content/docs/workflows/manual-verification.md`) covering: what the check is (advisory, evidence-backed, never blocking); when it fires (picking a Ready task with a stored `premise_baseline` and derivable scope); the four dispositions and what each does to the baseline; how to opt a task in and out; the v1 boundary (legacy tasks silent; no time-based verdicts).

  **Opt-in wording is fixed by t1673 — state these conditions and no others.** A task is seeded at creation when `ait create` carries `--file-ref` (Tier A scope) **or** `--verifies` (Tier B — the only input yielding an `exact` origin). **`--followup-of` does not seed**, and the docs must not imply "follow-up seeding": `--followup-of` writes only `anchor:`, which Tier B refuses by contract. Opting out is clearing the field. See `aidocs/framework/task_premise_staleness.md` "Seeding" and "Tier B reachability" — do not re-derive the criterion from the older prose.
- `website/content/docs/development/task-format.md` — cross-check the field row child 2 added reads correctly in context.

## Conventions

- Current-state-only prose (no version history), per `aidocs/framework/documentation_conventions.md`.
- Genericize agent references (the docs name no specific coding agent).
- `hugo build --gc --minify` in `website/` must pass; anchors verified manually (hugo does not fail dead fragments).

## Verification

- Build passes; the new page renders; cross-references from/to the manual-verification workflow page resolve both ways.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1687** id=2026-09-10T18:36:40Z.59bd5f09eff34c23e8a9fb5f from=t1687 at=2026-09-10T18:36:40Z base=e2f12c49990459143f2e387db431b5222fc66ef7 base_branch=main dirty=no host=omg16
>
> | Docs-coordination sweep, run outside any task: `from=` names the overlapping
> | task, not an agent working on it, so it is unverified. Advisory only —
> | tree-relative claims are dated by this note's base SHA; `~` line numbers are
> | approximate. Verify before acting.
> | 
> | 1. The design has the check fire on every entry path — pick, board agent
> |    launch, explore (aidocs/framework/task_premise_staleness.md ~195-196) — not
> |    only on picking a Ready task. Document what ships.
> | 
> | 2. t1687 (Concepts gap sweep) lists "Task premise staleness" as a concept
> |    candidate. Nothing has shipped yet, so its own criterion excludes it; a note
> |    to t1687 says the topic belongs to you. If it writes one anyway, link it
> |    rather than duplicate.
> | 
> | 3. Keep this check distinct from the existing verification_baseline pre-check
> |    (development/task-format.md ~62). workflows/_index.md is hand-curated, so a
> |    new page needs a bullet there.
