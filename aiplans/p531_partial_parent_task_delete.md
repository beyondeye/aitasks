---
Task: t531_partial_parent_task_delete.md
Worktree: (none — working on current branch)
Branch: (none — working on current branch)
Base branch: main
---

# t531 — Partial parent task delete/archive in ait board

## Context

Task t475 is a parent task with several siblings. Most have been implemented; the remaining ones are no longer relevant (designs changed, or their work was absorbed elsewhere). The user wants to clean this up from `ait board` without corrupting metadata, and discovered two gaps in the board's delete/archive handling.

**Gap 1 — Archive a parent with pending children.** The archive button in the task detail screen calls `aitask_archive.sh --superseded <num>`. For a parent task, `archive_parent()` (`aitask_archive.sh:170-242`) does **not** inspect `children_to_implement`. It silently archives the parent, leaving the child task files stranded in `aitasks/t<parent>/` with a dangling reference to an archived parent.

**Gap 2 — Delete a child task.** `_do_delete` (`aitask_board.py:4204-4259`) does `git rm` on the collected files and commits. When the deleted item is a child task, the parent's `children_to_implement` is **not** updated (contrast with `aitask_archive.sh:397` which calls `aitask_update.sh --remove-child`). The parent is left with a stale child reference.

**Gap 3 — No orphaned-parent prompt.** If the user deletes all pending children one by one, the parent ends up with an empty (but still present) `children_to_implement` list and stays in its current status. `.claude/skills/task-workflow/SKILL.md:50-65` already defines an "orphaned parent" check, but the board TUI never surfaces it.

### User scenarios to support

1. **Archive parent, discard remaining disposable children.** User opens parent t475 in detail view, presses Archive. Any remaining `Ready`/`Postponed`/`Editing` children should be deleted (they're no longer relevant), their `children_to_implement` references removed, then the parent archived as Done. If a child is `Implementing` or an unarchived `Done`, refuse and tell the user to handle it first.

2. **Delete remaining children one by one, parent auto-cleans up.** User deletes each remaining child from the board. Every child delete must update the parent's `children_to_implement`. When the last pending child is deleted, prompt the user to archive the now-orphaned parent.

---

## Verified current behavior

| Operation | Target | Current behavior | Gap |
|-----------|--------|------------------|-----|
| Delete (`_do_delete`) | Parent | `_collect_delete_files` walks children; everything `git rm`'d. | OK |
| Delete (`_do_delete`) | Child | Only child file + its plan `git rm`'d. | Parent `children_to_implement` not updated. No orphan check. |
| Archive (`_do_archive` → `archive_parent`) | Parent w/ pending children | Silently moves parent only. | Children stranded; dangling `children_to_implement` inside archived parent. |
| Archive (`_do_archive` → `archive_child`) | Child | `aitask_update.sh --remove-child`; auto-archives parent if all done. | OK |

Key call sites:

- `aitask_board.py:1280-1342` — `DeleteArchiveConfirmScreen` (Delete/Archive/Cancel buttons)
- `aitask_board.py:3367-3389` — dispatch from task detail result `"delete_archive"`
- `aitask_board.py:4082-4122` — `_collect_delete_files` (includes children only in the delete path)
- `aitask_board.py:4167-4193` — `_execute_archive` / `_do_archive` (calls `aitask_archive.sh --superseded`)
- `aitask_board.py:4195-4259` — `_execute_delete` / `_do_delete` (git rm, no parent update)
- `aitask_archive.sh:170-242` — `archive_parent()` (no child inspection)
- `aitask_archive.sh:342-514` — `archive_child()` (already does `--remove-child` + parent auto-archive)

Reusable primitives:

- `aitask_update.sh --batch <parent_num> --remove-child "t<task_id>" --silent` — already used by `archive_child` and `handle_folded_tasks` in `aitask_archive.sh`.
- `self.manager.get_child_tasks_for_parent(task_num)` — used at `aitask_board.py:4112`.
- `aitask_archive.sh --superseded <task_num>` — existing archive entry point.

---

## Solution

All changes live in `.aitask-scripts/board/aitask_board.py`. The shared `aitask_archive.sh` and `aitask_update.sh` scripts are reused as-is — no script changes needed. This keeps the behavior orchestration in the UI layer where interactive confirmation happens.

### Change A — Categorize pending children before archiving a parent

Add a helper `_categorize_pending_children(task_num)` that uses `self.manager.get_child_tasks_for_parent` and returns three buckets by status:

- `disposable`: `Ready`, `Postponed`, `Editing` — safe to delete as part of cascade.
- `blocking`: `Implementing` — refuse the cascade.
- `unarchived_done`: `Done` (not yet archived) — refuse the cascade, user should archive them first.

### Change B — Route archive of a parent with pending children through a new cascade path

Modify the dispatch block at `aitask_board.py:3367-3389` (or the `on_action_chosen` closure) so that when the user clicks **Archive** on a parent task:

1. Call `_categorize_pending_children(task_num)`.
2. If `blocking` or `unarchived_done` is non-empty, push an error confirmation screen listing the offending children and the required action ("Archive/handle t<N> first"), then return without archiving.
3. If `disposable` is non-empty (and the two other buckets are empty), push a new `ArchiveParentCascadeConfirmScreen` (a light variant of `DeleteArchiveConfirmScreen`) and pass the disposable child list through. See the **Confirmation transparency** subsection below for exact label content.
4. If all three buckets are empty (no pending children), fall through to the existing `_execute_archive` / `_do_archive` behavior (unchanged).

The child-task archive path (clicking Archive on a child task) is untouched — `aitask_archive.sh` already handles it correctly.

#### Confirmation transparency (applies to all new/updated dialogs)

Every new or updated confirmation dialog must explicitly list every affected task and **exactly what will happen to it** — never just "N files affected". The user should be able to read the dialog and know which rows become archived entries, which rows get deleted, and which rows stay put.

**Parent cascade archive dialog (`ArchiveParentCascadeConfirmScreen`):**

```
Archive parent 't475_foo'?

Will be ARCHIVED (moved to aitasks/archived/):
    t475_foo.md                [parent — status: Ready]
    aiplans/p475_foo.md

Will be DELETED (disposable pending children):
    t475/t475_3_bar.md         [Ready]
    t475/t475_5_baz.md         [Postponed]
    aiplans/p475/p475_3_bar.md
    aiplans/p475/p475_5_baz.md

[Archive + delete children]  [Cancel]
```

Section headers (`Will be ARCHIVED`, `Will be DELETED`) must be shown verbatim. Each line shows the file path and, for task files, the current status in brackets. Plan files appear as indented siblings beneath their task. If a section is empty it is omitted entirely.

**Blocking/refusal dialog (when children include `Implementing` or unarchived `Done`):**

```
Cannot archive parent 't475_foo' — active children remain:

Blocking (must be handled first):
    t475/t475_2_xyz.md         [Implementing]
    t475/t475_7_qux.md         [Done — run archive on it]

Disposable (would be deleted if cascade proceeded):
    t475/t475_3_bar.md         [Ready]

[OK]
```

Only an `OK` button (no cascade option). The disposable section is included so the user knows the full picture even though the cascade is refused.

**Orphan-parent prompt (after last child delete, Scenario B):**

```
Parent 't475_foo' has no more pending children.

Will be ARCHIVED (moved to aitasks/archived/):
    t475_foo.md                [parent — status: <current>]
    aiplans/p475_foo.md

Archive it as completed now?

[Yes, archive parent]  [No, leave it]
```

**Existing `DeleteArchiveConfirmScreen` (parent delete path, unchanged structure):**

Tighten the existing layout so that under "Files affected" each row is annotated with its fate. When the user is looking at a parent with pending children, the label should spell out that **both Delete and Archive** will remove those children:

```
Delete or Archive 't475_foo'?

[!] This parent has 2 pending children.
    - Delete will remove the parent and all children.
    - Archive will move the parent to archived/ and delete the children.

Will be ARCHIVED (on Archive) / DELETED (on Delete):
    t475_foo.md                [parent — status: Ready]
    aiplans/p475_foo.md

Will be DELETED (both actions):
    t475/t475_3_bar.md         [Ready]
    t475/t475_5_baz.md         [Postponed]
    aiplans/p475/p475_3_bar.md
    aiplans/p475/p475_5_baz.md

[Delete]  [Archive]  [Cancel]
```

Implementation note: centralize the formatting in a small helper like `_format_affected_files(buckets: dict[str, list]) -> list[str]` so the three dialog variants (cascade archive, blocking refusal, orphan prompt, updated delete/archive) share the same renderer and stay consistent.

### Change C — Cascade-delete disposable children, then archive the parent

Extend `_execute_archive` to accept an optional `cascade_children: list[Task]` argument (default `None`), and `_do_archive` to accept the same. Inside `_do_archive`, when `cascade_children` is non-empty:

1. For each child in `cascade_children`:
   - `aitask_update.sh --batch <parent_num> --remove-child "t<parent>_<child>" --silent` (mirrors `aitask_archive.sh:397`).
   - `git rm -f <child_task_file>` and `git rm -f <child_plan_file>` if the plan exists. Use `_task_git_cmd()` like the existing delete path (`aitask_board.py:4218`).
2. Best-effort `rmdir` on `aitasks/t<parent>/` and `aiplans/p<parent>/` if now empty (same pattern as `_do_delete:4229-4240`).
3. Then invoke `./.aitask-scripts/aitask_archive.sh --superseded <parent_num>` as before. The archive script will pick up the now-empty `children_to_implement` and archive the parent cleanly, committing the child-removal and the archive together (the commit happens inside the archive script and will include the staged child deletions).

**Important:** do the child deletions before calling the archive script so the single commit that the archive script creates includes everything. If that doesn't work (because `aitask_update.sh` commits its own updates), fall back to an explicit `task_git commit` for the child deletions first, then the archive script runs normally. Verify during implementation which path `--silent` takes.

### Change D — Delete child must update parent and prompt for orphan cleanup

Modify `_execute_delete` / `_do_delete` (`aitask_board.py:4195-4259`):

1. Before the git rm loop, detect child-task deletion: a child has `task_num` formatted as `<parent>_<child>` (inspect the path: `task.filepath.parent.name.startswith("t")`). Pass `is_child` and `parent_num` into `_do_delete`.
2. If `is_child`, run `aitask_update.sh --batch <parent_num> --remove-child "t<task_num>" --silent` **before** git-rm'ing the child file (or the script won't find it to clean the reference) — mirror `aitask_archive.sh:397`.
3. After the delete commit succeeds, if `is_child`, re-read the parent task via `self.manager.reload_task(...)` (or `self.manager.load_tasks()` is already called) and check the parent's `children_to_implement`. If it is now empty and the parent's `status` is not `Done`, push an orphan-parent prompt from the main thread (`call_from_thread`).
4. Orphan prompt: a small `ConfirmScreen` (existing Textual confirm dialog) with "Parent t\<parent\> has no more pending children. Archive it as completed? **Yes / No**". If Yes, call `_execute_archive(parent_num, parent_task, cascade_children=None)` — the parent now has no pending children so the existing path works.

### Change E — Reformat `DeleteArchiveConfirmScreen` to be explicit

Rewrite the body composed in `DeleteArchiveConfirmScreen.compose` (`aitask_board.py:1297-1326`) to use the transparent layout from the Confirmation transparency subsection above. The screen now receives the categorized file buckets (parent file/plan, disposable children + their plans) and renders them under labelled sections, using the shared `_format_affected_files` helper.

This is not just cosmetic — it replaces the current flat "Files affected" list with explicit ARCHIVED vs DELETED sections and per-row status annotations so the user can see exactly what each button will do.

---

## Files to modify

- `.aitask-scripts/board/aitask_board.py`
  - `DeleteArchiveConfirmScreen.compose` (around 1297-1326) — Change E warning line
  - Task detail dispatch block (`on_action_chosen`, 3367-3389) — Change B routing
  - New helper `_categorize_pending_children` — Change A
  - New screen class `ArchiveParentCascadeConfirmScreen` (or reuse `DeleteArchiveConfirmScreen` with a tighter label and only the Archive/Cancel buttons) — Change B
  - `_execute_archive` / `_do_archive` (4167-4193) — Change C (accept `cascade_children`)
  - `_execute_delete` / `_do_delete` (4195-4259) — Change D (child `--remove-child`, orphan prompt)

No changes to:
- `.aitask-scripts/aitask_archive.sh` (reused as-is)
- `.aitask-scripts/aitask_update.sh` (reused as-is)

---

## Verification

Manual testing via `ait board` in a scratch branch with synthetic tasks. Create three parents to exercise each flow:

**Test 1 — Archive parent with disposable children (Scenario A):**
1. Create parent `tX` with 3 children, all `Ready`.
2. Open `tX` in detail view, press Archive.
3. Expect: cascade-confirm screen listing the 3 children. Confirm.
4. Expect: `aitasks/archived/tX_*.md` exists with `children_to_implement: []` (or no such field), three child files gone from `aitasks/tX/`, `aiplans/pX/` removed, a single commit (or two — acceptable) with a clean `git status`.

**Test 2 — Archive parent with a blocking child (Scenario A, edge case):**
1. Parent `tY` with children: one `Ready`, one `Implementing`.
2. Open `tY`, press Archive.
3. Expect: error/refusal dialog naming the `Implementing` child. Parent not archived, no files deleted.

**Test 3 — Delete children one by one (Scenario B):**
1. Parent `tZ` with 2 `Ready` children.
2. Open first child, press Delete → Delete. Expect: child file gone, parent's `children_to_implement` now has 1 entry (verify by reading the parent file). No orphan prompt yet.
3. Open second child, press Delete → Delete. Expect: child gone, parent `children_to_implement: []`, orphan prompt appears offering to archive parent. Accept.
4. Expect: parent moved to `aitasks/archived/`, commit clean.

**Test 4 — Existing flows unchanged (regressions):**
1. Delete a parent with children (Delete button) — should still cascade-delete everything (existing behavior, untouched).
2. Archive a child — should still route through `aitask_archive.sh` child path (existing behavior, untouched).
3. Archive a parent with zero children — should still call archive script directly (existing behavior, untouched).

After manual tests, run lint on the changed script: `shellcheck .aitask-scripts/aitask_*.sh` (no shell changes, but cheap sanity).

End-to-end by running `ait board` locally; the board TUI has no automated test suite for these flows.

---

## Step 9 — Post-Implementation

Normal flow: user review (Step 8), commit with `feature: Cascade archive/delete for parent tasks in ait board (t531)`, plan file commit via `./ait git`, then `aitask_archive.sh 531` and `./ait git push`.
