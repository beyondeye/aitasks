---
priority: high
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Done
labels: [ui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-17 11:26
updated_at: 2026-06-17 12:02
completed_at: 2026-06-17 12:02
boardidx: 150
---

## Problem

In the `ait board` task-detail view, relation dialogs show "(not found)" / "(UNREACHABLE)" for a depended-on task that has been **archived**, instead of resolving its title/status.

Reproduction (user-reported): In the `aitasks_mobile` workspace, task `14` has a cross-repo dependency `aitasks#822`. Task 822 in the `aitasks` repo is now Done and archived. Selecting the cross-repo dependency line in the task detail and opening the dependency list dialog shows `822` as not found, because the resolver only looks in the other repo's active `aitasks/` directory.

This is the same class of bug fixed for **same-repo** Depends/Verifies dialogs in commit `c9e9383c2` (task t992), but three relation dialogs were missed.

## Root cause

The t992 fix added `TaskManager.find_task_including_archived()` (`.aitask-scripts/board/aitask_board.py:410`) + `_load_archived_task()` (backed by `find_archived_markdown_by_id()` in `.aitask-scripts/lib/archive_iter.py`) and wired it into the **Depends** (`DependsField`) and **Verifies** (`VerifiesField`) dialogs only. Still active-only:

1. **Cross-repo deps** — `_resolve_cross_repo_task()` (`aitask_board.py:2258`): at lines 2293-2300 it globs only `root / "aitasks"` of the resolved other repo (comment says "active tasks only"); never `root / "aitasks/archived/"`. Returns `Task t<id> not found in project '<repo>'.`, rendered as `(UNREACHABLE)` in `CrossRepoDepsField._format_ref()` (line 1620). Note: the cross-repo **status badge** already resolves correctly via `get_xdep_status()` → `aitask_query_files.sh task-status`, which DOES read archived — so only the content/title resolution is broken and the two surfaces disagree.
2. **Children dialog** — `ChildrenField._open_child()` (lines 1676, 1683) uses `find_task_by_id()` (active-only) → `(not found)` at line 1688.
3. **Folded Tasks dialog** — `FoldedTasksField._open_folded()` (lines 1726, 1735) uses `find_task_by_id()` → `(not found)` at line 1740.

## Acceptance criteria

- Children and Folded Tasks dialogs resolve archived tasks via `find_task_including_archived()` (mirroring the Depends/Verifies fix), opening them read-only (`read_only=getattr(task, "archived", False)`) consistently with the t992 wiring.
- The cross-repo dependency dialog resolves an archived task in the **other** repo: when `root/aitasks/` has no match, fall back to that repo's archived store. `find_task_including_archived()` is local-only, so this needs an `archive_iter`-style lookup parameterized by the resolved cross-repo root (or reuse of `find_archived_markdown_by_id()` against `root`). Investigate whether `archive_iter` helpers accept an arbitrary root or need a small parameterization.
- Cross-repo content/title resolution agrees with the already-correct status badge (no more "Done badge but UNREACHABLE content").
- Tests cover each newly-archived-aware dialog path (Children, Folded, cross-repo), following the t992 test approach.

## References

- Prior fix: commit `c9e9383c2` (t992) — `aitasks/archived/t992_board_resolve_archived_tasks_in_verifies_dialog.md`
- Key files: `.aitask-scripts/board/aitask_board.py`, `.aitask-scripts/lib/archive_iter.py`
- Read `aidocs/framework/tui_conventions.md` (board TUI) before editing.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-17T08:52:30Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-17T08:52:31Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-17T09:00:57Z status=pass attempt=1 type=human
