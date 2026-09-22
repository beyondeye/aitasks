---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [testing, test_infrastructure]
anchor: 1527
followup_kind: upstream_defect
created_at: 2026-08-25 18:46
updated_at: 2026-08-25 18:46
boardcol: now
boardidx: 7238
---

The Python test suite loads modules from `.aitask-scripts/lib/` under **more than
one module object**, so a test that patches a lib module by its own `import`
name can silently intercept nothing — and every assertion that was supposed to
observe the patch passes vacuously.

## Evidence (measured in t1527)

`tests/test_local_dep_parity.py` counter-wraps `gate_ledger.read_registry` and
`gate_ledger.code_digest` to prove the shared `DependentsEvaluator` really hoists
them out of a whole-tree scan. In isolation the test passed. Under
`bash tests/run_all_python_tests.sh` it failed with **`registry: 0`** — the patch
had intercepted nothing. Asserting module identity made the cause explicit:

```
AssertionError:
  <module 'gate_ledger' from '/…/.aitask-scripts/lib/gate_ledger.py'>
  is not
  <module 'gate_ledger' from '/…/.aitask-scripts/lib/gate_ledger.py'>
```

Two distinct module objects, same file. The test was fixed locally by patching
`dep_resolution.gate_ledger` (the object the code under test actually holds), but
that is a per-test workaround for a suite-wide hazard.

## Why it is dangerous

The failure mode is **silence in the passing direction**. A patch that
intercepts nothing does not raise; the counter simply stays at its initial
value, and a `assertLessEqual(counts["digest"], 1)`-shaped assertion is
*satisfied by zero*. Any test that patches a lib module to observe a call —
counting, faulting, stubbing a subprocess — can be inert and green. That is the
same class as t1207's subshell counters and the `|| echo SENTINEL` exit-0 trap:
the test reports success because the mechanism never ran.

## Likely cause

Suspected: `tests/lib/board_fixture.load_board_module()` imports
`aitask_board.py` under a synthetic module name via
`importlib.util.spec_from_file_location`, and the `sys.path` state at that
moment differs from a plain `import`, so the board's own `import gate_ledger`
resolves to a fresh object. Other candidates: test modules that `os.chdir` and
re-`sys.path.insert` the same directory under a different absolute/relative
spelling, and `.aitask-scripts` vs `.aitask-scripts/lib` both being on the path.
**Confirm before fixing** — the exact mechanism decides whether the fix is in
the fixture harness, in the path setup, or in a `conftest`.

## Scope

1. Identify how a second object is created (`sys.modules` census at suite start
   vs mid-suite, keyed by `module.__file__`).
2. Make lib imports single-instance, or — if a second object is unavoidable for
   the synthetic-board-module seam — make the hazard **loud**.
3. A guard is the point: a suite-level check that no two entries in
   `sys.modules` share a `__file__` under `.aitask-scripts/lib/`, failing with
   the duplicated names. This is what turns a silent vacuous pass into a test
   failure.

## Verification

- The guard must FAIL on today's tree (it is a real, present condition) and pass
  after the fix — demonstrate both, not just the second.
- A negative control: deliberately re-import a lib module under a second name
  inside a test and confirm the guard names it.
- Re-run `tests/test_local_dep_parity.py::EvaluatorFanOutTests` with its patch
  reverted to the local-import form and confirm it now fails loudly (it is the
  known instance of the hazard).
- `bash tests/run_all_python_tests.sh` stays green.

## Related

- **t1527** — surfaced this while single-sourcing local dependency resolution;
  its plan's "Issues encountered" records the measurement.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:10:04Z.5c72fe8d1c2465cc8a9e6f74 from=t1794_9 from_verified=yes at=2026-09-22T06:10:04Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
> | Specific to t1613: t1794_1 added source-level guards for the duplicate-module-identity hazard this task describes, for the board package: tests/test_board_package_contract.py (no `board.`-qualified imports, no board/*.py importing aitask_board, unique basenames across manifest dirs, bare-import pairing for patched modules) and the C2 guard in tests/test_board_fixture_harness.py. Re-check your remaining scope (the lib/ side) against them before planning.
