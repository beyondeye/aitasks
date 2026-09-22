---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [git, task_metadata, robustness]
gates: [risk_evaluated]
anchor: 1599
followup_kind: risk_mitigation
created_at: 2026-09-04 15:53
updated_at: 2026-09-04 15:53
boardcol: now
boardidx: 26694
---

## Origin

Risk-mitigation ("after") follow-up for t1702, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — the same defect remains in `aitask_archive.sh`.

From t1702's `## Risk`: "The same defect remains in `aitask_archive.sh` (3
sites), so 'the board never swallows a bystander' is true only for these three
paths — the board's archive gesture still routes through that script · severity:
medium".

## Goal

t1702 gave the board's delete / rename / commit-dialog sites a pathspec and
removed their staging. The **archive** gesture was deliberately left out of
scope, so the swallow is still reachable from the board — by the one path a user
is most likely to take after finishing a task.

Two halves, and they must land together: fixing the script alone would leave its
caller staging deletions with nothing to consume them.

1. `.aitask-scripts/aitask_archive.sh:283,565,645` — three pathspec-less
   `task_git commit` calls. Route them through the scoped seam
   (`lib/task_utils.sh::ait_commit_paths_staging_untracked`, or
   `task_git_commit_scoped` directly), naming every path the archive wrote —
   the moved task/plan files, the parent's `children_to_implement`, and any
   carry-over checklist it seeded.
2. `.aitask-scripts/board/aitask_board.py:13718` (`_do_archive`) — `git rm -f`
   parks staged deletions in the shared `.aitask-data` index and currently
   *depends* on the archive script's index-wide commit to consume them. Once (1)
   is scoped, that dependency breaks: switch to a worktree unlink and let
   `commit -o` record the deletion, exactly as `_do_delete` now does.

Re-derive both line numbers before starting; do not trust these.

## Verification

- a bystander control per site: a file staged by a simulated concurrent session
  must not appear in the archive's commit
- negative control: each assertion must fail against today's pathspec-less
  `task_git commit`
- the archive must still commit everything it wrote — verify by measurement, as
  t1702 did, not by reading the source. t1702's characterization found the
  board's delete leaving the parent and revived-folded writes dirty and
  ownerless; check whether the archive path has the same omission before
  assuming its current pathspec is complete.

## References

- `tests/test_task_commit_scoped.sh` — the helper-level contract and its
  measured mutation matrix
- `tests/test_board_scoped_task_commit.py` — the board-level pattern (real
  worker bodies via `__wrapped__` over a `board_fixture` tree)
- `aidocs/framework/tui_conventions.md` — "Task and plan files: commit them
  path-scoped, and stage nothing you need not"

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1728** id=2026-09-08T19:20:55Z.f56423fac36121671b6d3f77 from=t1728 from_verified=yes at=2026-09-08T19:20:55Z base=d2a812b6505a41317941c8dddeb80ec8c90f14ea base_branch=main dirty=yes host=omg16
>
> | t1728 (Scope the ./ait git commit sites) landed and touched the same seam this
> | task plans to use. Three findings that may change your approach — advisory, not
> | a directive; verify each against the tree before acting.
> | 
> | 1. **Prefer `ait_commit_paths_staging_untracked` over bare
> |    `task_git_commit_scoped`.** This task's body says "route them through the
> |    scoped seam (or `task_git_commit_scoped` directly)". Going direct fixes the
> |    pathspec but introduces a second shared-index hazard, which
> |    `ait_commit_paths_staging_untracked`'s own header already documents: an
> |    unconditional `add` of a **tracked** path replaces the index entry another
> |    session staged for that same path. Measured against real git during t1728:
> |    with the `add`, a *failing* `commit -o` still leaves the index at the worktree
> |    content (the other session's staged version is gone); without it, that version
> |    survives. Archive paths are tracked and on the shared branch, so this applies.
> |    `--no-stage` is not a substitute — it is only correct when trackedness is
> |    proven, and `commit -o -- <untracked>` fails outright.
> | 
> | 2. **Its cleanup trap is armed by the CALLER, and `aitask_archive.sh` may
> |    already own an EXIT trap.** A bare `trap 'ait_unstage_staged_by_us' EXIT`
> |    silently replaces an existing handler. t1728 hit this at two sites and had to
> |    compose a single named cleanup function doing both jobs; a test that mutates
> |    the trap back to the naive form goes red, if you want the pattern.
> | 
> | 3. **`tests/test_no_unscoped_task_commit.sh` now scans a second seam**,
> |    `./ait git commit`, in addition to `task_git commit`. Its header previously
> |    said that seam was out of detection scope — that paragraph is rewritten. If
> |    any archive commit goes through `./ait git`, it is now guarded too. The new
> |    pattern matches on the quote-stripped line and has its own separate
> |    `AIT_GIT_ALLOWLIST` (one entry, `aitask_note.sh`, for prose the scanner
> |    cannot parse).
> | 
> | Also worth knowing when you write the absorb: every one of these helpers returns
> | 2 for "verified nothing to commit", and a trailing `(( crc == 1 )) && warn ...`
> | is a complete `&&` list — under `set -e` a false test makes it the failing last
> | command. t1728 writes every such branch as a real `if ... fi`.
> | 
> | Landed in commit d2a812b65; see aiplans/archived (or aiplans/) p1728 for the
> | full reasoning and the controls.

> **✉ note:t1794_9** id=2026-09-22T06:10:15Z.4c4f7262760fa9abcb315a4b from=t1794_9 from_verified=yes at=2026-09-22T06:10:15Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
>
> | t1794 split the board mono-file `.aitask-scripts/board/aitask_board.py`
> | (children t1794_1..8 landed; the last extraction is commit 387d8cb20). Any
> | `aitask_board.py:NN` anchor in your body or plan is STALE: aitask_board.py is
> | now ~6.8k lines (was ~13.7k) and most classes moved. Re-derive by symbol
> | (grep the class/function name), not by line number.
> | 
> | Where symbols live now (.aitask-scripts/board/):
> | - aitask_board.py: KanbanApp (incl. action_* handlers, _do_archive,
> |   action_work_report, sync), Kanban/InFlight/Topic columns, board-only modals
> |   (delete/archive/rename/commit/settings/cross-repo/gate choice), key map,
> |   command palette provider
> | - board_task_manager.py: TaskManager (paths injected as required kw-only
> |   tasks_dir / metadata_file / gates_registry_file; no module-global reads)
> | - board_task_model.py: Task, MoveResult, MergeResult
> | - board_workflow_phase.py: workflow-phase / in-flight derivation
> | - board_widgets.py: TaskCard, ColumnHeader, PickerItem, badge/marker helpers,
> |   LoadingOverlay
> | - board_detail_screen.py: TaskDetailScreen + its field widgets and pickers
> | - board_column_dialogs.py: ColumnEdit/Select/Manage/MultiSelect screens,
> |   ColorSwatch, column confirm dialogs
> | - board_trail_view.py: pure trail rendering - trail cards/columns, trail
> |   modals (TrailDetailScreen, TrailSelectScreen, summary), TRAIL_CSS
> | - board_trail_screen.py: TrailScreenMixin (all By-Trail actions),
> |   TRAIL_BINDINGS, TrailHost protocol, TRAIL_ACTION_CAPABILITIES
> | - trails_app.py: the new stand-alone `ait trails` TUI, hosting the same mixin
> | 
> | Rules a change to these files must keep (full text: contracts C1-C3 in
> | aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md; note that the
> | line ranges in that plan's "Target file map" are PRE-split mono-file anchors,
> | not current ones):
> | 1. Flat imports between board/*.py (`import board_x`), never `board.`-qualified.
> | 2. No board/*.py other than aitask_board.py reads TASKS_DIR / METADATA_FILE /
> |    etc. at import time - moved code receives paths by parameter.
> | 3. No board/*.py imports aitask_board.
> | All three are test-enforced (tests/test_board_package_contract.py,
> | tests/test_board_fixture_harness.py). Test patch targets follow the symbol:
> | patch board_task_manager.X (etc.), not aitask_board.X, for moved code.
> | 
> | Advisory, not an instruction: tree-relative claims above are as of the base
> | SHA this note records.
> | 
> | Your body (aitasks/t1710_archive_sh_pathspec_scope.md) cites stale line anchors: aitask_board.py:13718.
