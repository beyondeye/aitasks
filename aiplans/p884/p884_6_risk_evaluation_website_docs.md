---
Task: t884_6_risk_evaluation_website_docs.md
Parent Task: aitasks/t884_add_task_risk_evaluation_in_planning.md
Sibling Tasks: aitasks/t884/t884_*.md
Archived Sibling Plans: aiplans/archived/p884/p884_*_*.md
Worktree: aiwork/t884_6_risk_evaluation_website_docs
Branch: aitask/t884_6_risk_evaluation_website_docs
Base branch: main
---

# Plan: t884_6 — Website docs for risk evaluation

> Parent architecture & decisions: `aiplans/p884_add_task_risk_evaluation_in_planning.md`.
> Depends on t884_1, t884_3, t884_4. NOT gated on t884_5.

## Goal

Document the user-visible surfaces. Follow `aidocs/documentation_conventions.md`:
current-state only, generic placeholder project names, "autonomous" not
"auto-execution".

## Steps (extend existing pages in place; read them first)

1. **`risk` task field** — on the board docs + `ait create`/`ait update` docs: values high/medium/low, how to set/view.
2. **Risk-evaluation planning step** — the two dimensions (code-health + goal-achievement) and the `## Risk` plan section, on the planning/task-workflow docs.
3. **Risk-mitigation before/after flow** — propose-and-confirm; before = blocking dep, after = post-implementation.
4. **`risk_evaluation` profile key** — on the execution-profiles / settings docs (opt-in; off by default), alongside `qa_mode` / `manual_verification_followup_mode`.
5. **Force re-verification** — one line: a landed "before" mitigation forces plan re-verify on next pick.
6. Update an `_index.md` only if the feature spans pages.

## Reference patterns

- Existing execution-profiles doc (profile-key rows).
- `website/content/docs/workflows/manual-verification.md` — model for a planning-integrated procedure.

## Verification

- `cd website && hugo build --gc --minify` clean (no broken links); visually confirm via `./serve.sh`.

## Notes for sibling tasks

Behavior covered by t884_M manual-verification sibling.
