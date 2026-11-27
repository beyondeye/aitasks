---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [workflow, skills]
gates: [risk_evaluated]
anchor: 2258
followup_kind: upstream_defect
created_at: 2026-11-27 11:21
updated_at: 2026-11-27 11:21
---

## Origin

Spawned from t2369 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_change_surface.sh:445 — a path is labelled COMMITTED: for any earlier task-tagged commit even when another task later committed, edited or (untracked) recreated it, and TASK: for a plan-cited path another session edited; consumers other than Step 8 (the docs_updated gate step 2, the shadow scope helper) still trust both labels`

## Diagnostic context

While dogfooding t2369's documentation review, `aitask_change_surface.sh list 2369` printed `TASK:` for `install.sh`, `.github/workflows/release.yml`, `aidocs/framework/shell_conventions.md` and `aidocs/framework/skill_authoring_conventions.md`. t2369 never edited them: its plan names their paths, and another session was editing them. Review concerns on t2369 then reproduced, in scratch repositories, `COMMITTED:` for a page (a) edited by another task after the tagged commit, (b) replaced by another task's later commit with a clean `git status`, and (c) deleted by the tagged commit and recreated untracked by another task.

t2369 worked around this for its own consumer only: `task-workflow/doc-review.md` makes the agent account for `TASK:` paths, and `aitask_doc_review.sh since-task-commit` compares a `COMMITTED:` page by content with the last commit tagged `(t<id>)` and names later commits (see `aidocs/framework/doc_review_record.md`, "Limits"). The helper's header documents the `TASK:` limit ("P2 is DECLARED, not proven") but not the `COMMITTED:` one.

## Suggested fix

Have `list` report ownership of the committed revision separately from what happened to the path since (for example a second field, or a `COMMITTED_THEN_CHANGED:` class), reusing the content comparison in `since-task-commit`, and review the other consumers: `aitask-gate-docs-updated` step 2 and `lib/shadow_scope.py`.
