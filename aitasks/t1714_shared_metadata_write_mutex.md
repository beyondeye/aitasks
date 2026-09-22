---
priority: medium
effort: high
depends: []
issue_type: enhancement
status: Ready
labels: [git, task_metadata, robustness]
anchor: 1599
followup_kind: risk_mitigation
created_at: 2026-09-04 16:56
updated_at: 2026-09-04 16:56
---

## Origin

Risk-mitigation ("after") follow-up for t1704, created at Step 8d after implementation landed.

## Risk addressed

`addresses: goal-achievement — the compare-and-commit guard detects and refuses
but does not exclude, so a concurrent edit in the target makes the push fail
rather than succeed`

From p1704's `## Risk`:

> The compare-and-commit guard detects and refuses but does not exclude: the
> destination's own writers take no lock, so a residual same-process window
> remains in which a concurrent edit is neither published nor overwritten but
> the push simply fails · severity: medium

## Goal

Upgrade the cross-repo push from **detect-and-refuse** to real **mutual
exclusion**, by making every metadata writer in a destination repo take a shared
`lib/stale_lock.sh` lock around write-and-commit.

t1704 closed the outcome that matters — the framework never publishes bytes it
did not write, and never silently discards an edit it found — but it cannot
*prevent* the collision, only detect it. The residual is a real user-visible
cost: a concurrent edit makes the push **fail** rather than succeed, and the
user has to notice and retry.

**Read p1704's "What this does not buy, stated plainly" section before
planning** — it states the reasoning this task exists to overturn, including why
a lock taken *only* by the push would be worse than none (it would serialize
push-against-push while leaving push-against-local-edit exactly as it is).

The writers that must all participate — a lock only some of them take is not a
mutex — at minimum:

- that repo's own Settings TUI (`settings/settings_app.py` — `save_codeagent`,
  `save_board`, `save_project_settings`, `save_profile`, `delete_profile`,
  `_handle_import`)
- board column CRUD (`board/aitask_board.py::save_metadata`,
  `aitask_board_column.sh`)
- the chatlink wizard (`chatlink/wizard.py::_do_save`)
- `ait setup`'s populate-missing / backfill passes
- `cross_repo_settings.py::apply_push` itself

Derive that list from `tests/test_metadata_writer_inventory.py`'s `WIRED` set
rather than from this bullet, which will drift.

## Hard parts (name them in the plan)

- **The lock lifecycle straddles a Python/shell boundary.** The write happens in
  Python; the commit happens in a shell helper. The lock must span both, and
  must survive a killed process — `lib/stale_lock.sh` already has the fail-safe
  owner-token model, so reuse it rather than inventing a second.
- **It is a lock in ANOTHER repo**, taken by a session that repo does not know
  about. Decide what a stale lock there means and who may break it.
- **It is framework-wide**, so it is a behaviour change for every metadata
  writer, not just the push. Every one of them is a TUI event handler, so a
  blocking acquisition on the UI thread is not acceptable — measure the
  availability, do not assume it.
- **Do not remove the compare-and-commit guard.** A mutex makes the race rare,
  not impossible (an unlocked writer, a broken lock, a repo mid-upgrade), and
  the guard is what keeps the failure fail-safe. It stays as defence in depth.

## Verification

- two concurrent pushes into the same destination serialize rather than one
  refusing
- a push and a local Settings-TUI save in the destination serialize
- a killed lock holder does not wedge the destination permanently
- the existing t1704 race tests still pass unchanged — the guard is still there
- negative control: with the lock removed, the concurrent cases return to
  `commit_raced`

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:10:18Z.0f2a751e72ce54c06cb036e3 from=t1794_9 from_verified=yes at=2026-09-22T06:10:18Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
