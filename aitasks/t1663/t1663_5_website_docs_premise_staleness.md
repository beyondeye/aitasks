---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: [t1663_4]
issue_type: documentation
status: Implementing
labels: [task-workflow, documentation]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1538
implemented_with: claudecode/opus5_5
created_at: 2026-09-01 15:20
updated_at: 2026-11-08 13:13
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

> **✉ note:t1663_4** id=2026-11-08T09:33:06Z.cd3daa7f7ac5a89fb840dff5 from=t1663_4 from_verified=yes at=2026-11-08T09:33:06Z base=620039d7bbcb9d6bd5911d5275e58bd2814fa872 base_branch=main dirty=yes host=omg16
>
> | From t1663_4, landed in 620039d7b. Advisory context for the website docs; re-verify against the tree.
> | 
> | - The check is task-workflow Step 3 **Check 7** (not Check 6, which is the inbox check). Ready tasks only; manual_verification tasks are skipped (Check 3 owns them).
> | - Four options: Proceed / Review & replan with this evidence / Postpone task / Pick a different task. Postpone ends with a new `postponed` Stopped-banner outcome.
> | - The evidence-class resolution table (what "Proceed" does with CHANGED, DELETED, never_existed, invalid_reference, unverifiable rows), the headless report-only rule and the lifecycle table are in aidocs/framework/task_premise_staleness.md, "Interaction" and "Baseline lifecycle".
> | - Framework-internal, not user commands: `aitask_premise_stale.sh advance` / `owner`, and `aitask_pick_own.sh --expect-status`.
> | - Known limits worth stating for users: invalid file_references entries recur until fixed by hand; kept never-existing references keep being reported; a session outside the agent's tmux pane without AIT_AGENT_PID cannot advance the baseline (owner_unverifiable).

> **👁 note:read** id=2026-11-08T10:53:11Z.e452e7caa7935a64af57b007 by=t1663_5 at=2026-11-08T10:53:11Z mode=explicit ids=2026-09-10T18:36:40Z.59bd5f09eff34c23e8a9fb5f,2026-11-08T09:33:06Z.cd3daa7f7ac5a89fb840dff5

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-08T11:13:10Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-08T11:17:05Z status=pass attempt=1 type=human
