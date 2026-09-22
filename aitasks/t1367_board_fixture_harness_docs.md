---
priority: low
effort: low
depends: []
issue_type: documentation
status: Ready
labels: [test, tui, board]
gates: [risk_evaluated]
anchor: 1111
followup_kind: risk_mitigation
created_at: 2026-08-02 12:15
updated_at: 2026-08-13 23:06
boardidx: 10240
---

## Origin

Risk-mitigation ("after") follow-up for t1354_2, created at Step 8d after
implementation landed.

## Risk addressed

Code-health, from t1354_2's `## Risk`:

> Editing the shared `tests/lib/board_fixture.py` touches 4 already-green files
> (`bytrail_view`, `work_report`, `movement`, `persistence_seam`), two of which
> pin `DEFAULT_TOPOLOGY` byte-for-byte, and the contracts those files rely on
> exist only in one module docstring · severity: medium

After t1354_2, **19** test modules depend on that harness, and its five
load-bearing contracts are documented only inside
`tests/lib/board_fixture.py`'s own docstring. Nothing points a reader there.

## Goal

Add a pointer + trap summary for the board fixture harness to
`aidocs/framework/tui_conventions.md`, per the "Read X when editing Y" pointer
convention already used throughout `CLAUDE.md`.

t1354_1 explicitly deferred this decision to t1354_2:

> "the harness is currently documented only in its own docstring. If t1354_2
> finds that insufficient while migrating 9 modules, a pointer in
> `aidocs/framework/tui_conventions.md` would be the natural home —
> deliberately not added here, as it was outside this task's approved scope."

t1354_2 migrated 15 modules and hit one of the traps as a real 3-test failure
(the missing `metadata/gates.yaml` silently reclassifying a human gate), which
answers the question: the docstring alone was not sufficient.

## Contracts to summarise (do not restate in full — link to the docstring)

1. `TASK_DIR` must be the relative literal `"aitasks"` with cwd inside the tree;
   an absolute value silently zeroes `TaskManager.is_modified`.
2. Every fixture task needs >=1 non-board metadata key or `_is_phantom_stub`
   drops it and assertions pass vacuously.
3. `metadata/project_config.yaml` is mandatory for trail refs, else every
   `aitasks#<id>` renders as a cross-repo ghost.
4. `metadata/gates.yaml` is staged from the shipped reference; without it a
   `review_approved` task reclassifies from `human` to `agent` and
   `unresolved_local_deps` fails closed.
5. `lock_map` is always empty under the fixture (the lock helper is absent by
   design); busy-ness must come from `status: Implementing` or an injected
   `lock_map` entry.

Also mention the fail-closed regression guard in
`tests/test_board_fixture_harness.py`: adding a new `tests/test_board_*.py`
file now requires a decision, because any chdir or canonical `aitask_board`
import must either go away or be pinned in an allowlist with a reason.

## Verification Steps

- The new pointer follows the existing `aidocs/` cross-reference style.
- Bidirectional: the `board_fixture.py` docstring points back at the aidocs
  page, so neither can be found without the other.
- No content duplicated from the docstring beyond the one-line trap names
  (the docstring stays the source of truth; see the "derive, don't duplicate"
  convention).

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:09:12Z.46b819c4803f71f01a739303 from=t1794_9 from_verified=yes at=2026-09-22T06:09:12Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
> | Your body (aitasks/t1367_board_fixture_harness_docs.md) cites symbols you name -> current module: TaskManager -> board_task_manager.py.
