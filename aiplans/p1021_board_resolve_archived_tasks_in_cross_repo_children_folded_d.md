---
Task: t1021_board_resolve_archived_tasks_in_cross_repo_children_folded_d.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Resolve archived tasks in board cross-repo / children / folded relation dialogs (t1021)

## Context

In `ait board`'s task-detail view, opening a relation dialog for a **cross-repo
dependency** whose target task has been archived shows it as not found
(rendered `(UNREACHABLE)` / "not found in project") instead of resolving its
content. Reproduction: in the `aitasks_mobile` workspace, task `14` has a
cross-repo dep `aitasks#822`; task 822 is Done and archived in the `aitasks`
repo, so the dep popup can't find it.

This is the **same class of bug** already fixed for same-repo Depends/Verifies
dialogs in commit `c9e9383c2` (t992), which added
`TaskManager.find_task_including_archived()` + `_load_archived_task()` (backed by
`find_archived_markdown_by_id()` in `.aitask-scripts/lib/archive_iter.py`). Three
relation surfaces were missed by that fix. The reported, reproducible one is the
cross-repo path; the rest are addressed as cheap parity (see Scope note).

**Scope note (chosen: cross-repo + parity swaps).** Only the **cross-repo** fix
is reproducible today. The Children/Folded/Parent/FoldedInto swaps are *parity*
with the shipped Depends/Verifies pattern and are **no-ops in practice by
design** — the archive script removes archived children from a parent's
`children_to_implement` (so the Children field only lists active children), and
folded task files are *deleted*, not archived (so `find_archived_*` can't recover
them). They are included for consistency and to guard anomalous/manually-edited
states; the task AC is annotated accordingly.

## Files to modify

- `.aitask-scripts/board/aitask_board.py` — the fix (one new helper + 6 small edits)
- `tests/test_board_archived_relation_lookup.py` — extend the existing t992 regression suite

## Implementation

### 1. Cross-repo archived resolution (the real bug)

`_resolve_cross_repo_task()` (line ~2258) currently globs only the resolved
repo's active `aitasks/` (lines 2293–2305). Extract the file-locating logic into
a **pure, root-parameterized helper** (testable without the
`aitask_project_resolve.sh` subprocess), with an active→archived fallback that
reuses the already-imported `find_archived_markdown_by_id`:

```python
def _read_cross_repo_task_content(root: Path, tid: str) -> str | None:
    """Task text for ``tid`` under ``root`` — active first, then the repo's
    archive store — or None if absent. Raises OSError only when an existing
    active file can't be read (archive misses are swallowed by the iterator)."""
    if "_" in tid:
        parent = tid.split("_")[0]
        matches = sorted((root / "aitasks" / f"t{parent}").glob(f"t{tid}_*.md"))
    else:
        matches = sorted((root / "aitasks").glob(f"t{tid}_*.md"))
    if matches:
        return matches[0].read_text(encoding="utf-8")
    archived = find_archived_markdown_by_id(tid, root / "aitasks" / "archived")
    if archived:
        return archived[1]
    return None
```

Then replace the body of `_resolve_cross_repo_task` from line 2293 onward with:

```python
    # Active tasks first, then the repo's archive store (mirrors
    # find_task_including_archived for same-repo deps, t992 — so an archived
    # cross-repo dep resolves instead of showing UNREACHABLE).
    try:
        content = _read_cross_repo_task_content(root, tid)
    except OSError as e:
        return (title, f"Could not read task file: {e}", True)
    if content is None:
        return (title, f"Task t{tid} not found in project '{repo}'.", True)
    return (title, content, False)
```

This preserves the existing "Could not read task file" error for an unreadable
*active* file, and makes the content popup agree with the status badge (which
already reads archived via `get_xdep_status` → `aitask_query_files.sh
task-status`).

### 2. Children dialog parity (`ChildrenField`, lines ~1674–1691)

Add a `_find_task_by_number` helper mirroring `DependsField` (lines 1464–1467)
and route both the single- and multi-child paths through
`find_task_including_archived`, opening archived children read-only:

```python
    def _find_task_by_number(self, num):
        num_str = str(num)
        task_id = num_str if num_str.startswith('t') else f"t{num_str}"
        return self.manager.find_task_including_archived(task_id)
```

- single: `task = self._find_task_by_number(self.children_ids[0])`, push
  `TaskDetailScreen(task, self.manager, read_only=getattr(task, "archived", False))`
- multi: `task = self._find_task_by_number(child_id_str)` (display label unchanged)

### 3. `ChildPickerItem.on_key` (line ~2485)

Open the selected child with archived-awareness, matching `DepPickerItem`
(lines 2200–2205):
`TaskDetailScreen(self.child_task, self.manager, read_only=getattr(self.child_task, "archived", False))`

### 4. Folded dialog parity (`FoldedTasksField._open_folded`, lines ~1722–1743)

Swap both `self.manager.find_task_by_id(tid)` calls →
`self.manager.find_task_including_archived(tid)`. The detail screen already opens
`read_only=True` (single) and `FoldedTaskPickerItem` already opens
`read_only=True`, so no read-only change needed.

### 5. `FoldedIntoField._open_target` (line ~1848) and `ParentField._open_parent` (line ~1879)

Swap `find_task_by_id` → `find_task_including_archived`, and push with
`read_only=getattr(task, "archived", False)`.

### 6. Tests (extend `tests/test_board_archived_relation_lookup.py`)

The file already loads the board module with a temp `TASK_DIR` and writes
active/archived task fixtures (`_write_task`, `_load_board_module`). Add:

- **Cross-repo (the regression for the reported bug)** — exercises the pure
  helper against an independent on-disk ground truth, no subprocess:
  - `test_cross_repo_active_task_resolves` — active `<root>/aitasks/t822_*.md` →
    helper returns its content.
  - `test_cross_repo_archived_task_resolves` — only
    `<root>/aitasks/archived/t822_*.md` exists → helper returns its content
    (was `None` before the fix). Also assert a `<parent>_<child>` id resolves
    from `archived/t<parent>/`.
  - `test_cross_repo_missing_returns_none` — neither present → `None`.
- **Children parity** — `test_children_field_resolves_archived_child`: write
  `archived/t13/t13_9_*.md`, build `ChildrenField(["t13_9"], …)`, assert
  `_find_task_by_number("t13_9")` returns the archived task with `.archived` True.
- **Folded parity** — `test_folded_field_resolves_archived_task`: write an
  archived parent, assert `FoldedTasksField` resolves it via
  `find_task_including_archived`.

Run: `python3 -m pytest tests/test_board_archived_relation_lookup.py -v`

## Verification

1. `python3 -m pytest tests/test_board_archived_relation_lookup.py -v` — all pass,
   including the new archived cross-repo case.
2. `python3 -m pytest tests/test_archive_iter_consolidated.py -v` — confirm the
   reused `find_archived_markdown_by_id` is unaffected.
3. `python3 -c "import ast,sys; ast.parse(open('.aitask-scripts/board/aitask_board.py').read())"`
   syntax sanity (board has no standalone import-time entry point).
4. Manual (covered by the live scenario): in a workspace whose `aitasks#<id>`
   dep is archived in the other repo, open the cross-repo dep popup → content
   renders instead of "(UNREACHABLE)" / "not found in project".

## Risk

### Code-health risk: low
- Contained change in one file that mirrors an already-shipped pattern (t992) and
  reuses the existing, tested `find_archived_markdown_by_id`. The
  `_resolve_cross_repo_task` refactor preserves its error-return semantics. · severity: low · → mitigation: None

### Goal-achievement risk: low
- The reported cross-repo bug is directly fixed and unit-tested against an
  independent on-disk ground truth (archived file written, helper asserted to
  return it). The parity swaps are no-ops by design but harmless. · severity: low · → mitigation: None

## Post-Implementation

Per task-workflow Step 9: review/approve, commit (`bug:` prefix, `(t1021)`),
update plan, merge to main, archive t1021.

## Final Implementation Notes

- **Actual work done:** Implemented all 6 edits in `.aitask-scripts/board/aitask_board.py`
  exactly as planned: (1) new module-level pure helper `_read_cross_repo_task_content(root, tid)`
  (active glob → archived fallback via the already-imported `find_archived_markdown_by_id`);
  (2) `_resolve_cross_repo_task` refactored to call it, preserving the "Could not read task
  file" / "not found in project" error returns; (3) `ChildrenField` gained a
  `_find_task_by_number` helper and routes single+multi through `find_task_including_archived`
  with archived-read-only opening; (4) `ChildPickerItem.on_key` opens archived children
  read-only; (5) `FoldedTasksField._open_folded` both lookups swapped to archived-aware;
  (6) `FoldedIntoField._open_target` and `ParentField._open_parent` swapped + read-only-aware.
  Extended `tests/test_board_archived_relation_lookup.py` with 2 parity tests
  (Children, Folded) and a new `CrossRepoTaskResolutionTests` class (5 cases: active,
  archived parent, archived child, active-wins-over-archived, missing).
- **Deviations from plan:** None. The cross-repo helper test asserts against an independent
  on-disk ground truth (a real archived file under a temp "other repo" root), exercising the
  active→archived fallback directly without the `aitask_project_resolve.sh` subprocess.
- **Issues encountered:** A transient outage of the Bash safety classifier blocked test
  execution and bookkeeping mid-task; the work was fully resumable from `Implementing` and
  completed once the classifier recovered. No code impact.
- **Key decisions:** Extracted the file-locating logic into a pure root-parameterized helper
  (testability-first) rather than inlining the archived fallback in `_resolve_cross_repo_task`,
  so the active→archived behavior is unit-testable in isolation. Scope was confirmed with the
  user as "cross-repo + parity swaps": only the cross-repo path is reproducible today; the
  Children/Folded/Parent/FoldedInto swaps are parity with the shipped t992 Depends/Verifies
  pattern and are no-ops by design (archived children are dropped from `children_to_implement`;
  folded files are deleted, not archived) — included for consistency and anomaly-guarding.
- **Upstream defects identified:** None.

## Verification results

- `python3 -m unittest tests.test_board_archived_relation_lookup` — 11/11 OK.
- `python3 -m unittest tests.test_archive_iter_consolidated` — 24/24 OK (reused helper unaffected).
- `python3 -c "import ast; ast.parse(...)"` board syntax — OK.
