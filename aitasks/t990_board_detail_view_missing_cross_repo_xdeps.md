---
priority: high
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_board, tui]
file_references: [.aitask-scripts/board/aitask_board.py:2427-2476]
created_at: 2026-06-15 08:30
updated_at: 2026-06-15 08:30
---

## Problem

`ait board` shows a task's cross-repo dependency (`xdeps`/`xdeprepo`) on the **task card** but not in the **task detail** view. Reproduced with a task in a linked repo that has an `xdep` on a task in another repo: the card displays the dependency, the detail popup omits it.

## Root cause

Two render paths handle cross-repo deps, but only the card includes them:

- **Card** — `TaskCard.compose` (`.aitask-scripts/board/aitask_board.py:800-849`) builds `xdep_display` from `xdeprepo` + `xdeps`, queries live status via `manager.get_xdep_status(...)`, and yields a `↗ {refs}` label plus a `🌐 blocked (cross-repo)` status indicator.
- **Detail** — `TaskDetailScreen._build_relations_fields` (`aitask_board.py:2427-2476`) builds the "Dependencies & hierarchy" collapsible (consumed in `compose` at :2585-2589). It handles `depends`, `verifies`, parent, children, `folded_tasks`, `folded_into` — but has **no `xdeps`/`xdeprepo` branch**, so the cross-repo dependency never appears in the detail view.

## Fix shape

Add an `xdeps`/`xdeprepo` branch to `_build_relations_fields` so the detail's relations section shows cross-repo deps with live status, consistent with the card. Reusable infra already exists:

- `_gather_cross_repo_refs(task)` (:4480) — ordered, de-duped `(repo, id)` refs from frontmatter + body notation
- `_open_cross_repo_task(repo, id)` (:4502) and `action_open_cross_repo` / `#` binding (:4507) — open a ref read-only
- `manager.get_xdep_status(repo, id)` (:422) — live, per-refresh-cached status

Preferred: a focusable relations field (like `DependsField`/`VerifiesField`) that mirrors the card's `↗ {ref} [{status}]` string and opens the cross-repo task read-only on Enter. Minimum acceptable: a `ReadOnlyField` mirroring the card string. Honor the both-or-neither `xdeprepo`/`xdeps` invariant.

See `aidocs/framework/tui_conventions.md` for board/TUI conventions.
