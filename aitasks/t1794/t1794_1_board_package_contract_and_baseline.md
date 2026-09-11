---
priority: medium
effort: medium
depends: []
issue_type: test
status: Ready
labels: [aitask_board, tui, trails, python, refactor, test_infrastructure]
gates: [risk_evaluated]
anchor: 1794
created_at: 2026-09-11 15:08
updated_at: 2026-09-11 15:08
---

## Context

Child 1 of t1794 (split `.aitask-scripts/board/aitask_board.py` into a `board/`
package and carve the By-Trail screen out as the stand-alone `ait trails` TUI).
This child lands **before any code moves**: the package marker, the guard tests
that every later child must satisfy, the characterization test that makes
"the board behaves exactly as before" a checked claim, the footprint
measurement script with the recorded baseline, and the inventory of every
path-keyed manifest that names `board/aitask_board.py`.

**Read first:** the parent plan
`aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md` — sections
"Decisions", "Target file map", "Cross-child contracts" (C1–C10) are PINNED;
"Pre-phase (risk mitigations)" item 1 is realised by this child. Line numbers
in this description are anchors at `e2f12c499` (verified unchanged at
`c78deab36`); step 1 re-derives them.

Why the guards exist (measured, not guessed):
- `tests/lib/board_fixture.py:502–545` `load_board_module()` re-execs only
  `aitask_board.py` under a synthetic module name with `TASK_DIR` set and
  restores the env in `finally` (`:540–544`). A sibling module that binds
  `task_dir()`-derived paths at import time keeps the canonical value; one that
  calls `task_dir()` lazily at runtime reads the restored env. Both are wrong
  and both are silent (t1613 class).
- `lib/shortcut_scopes.py:83–89` puts every manifest module's directory on
  `sys.path` from a **set**; the docstring at `:80–81` states the "no colliding
  basenames" invariant. `brainstorm/widgets.py` exists — hence the `board_`
  prefix in the file map and the basename guard.
- A `board/*.py` that imports `aitask_board` under `load_board_module()`
  executes the *canonical* board while `TASK_DIR` is still set, rebinding
  `aitask_board.TASKS_DIR` to a temp tree (breaks
  `test_board_movement.IsolationNegativeControlTests`) and mints a second
  `KanbanApp`/`Task` identity.

## Key files to modify

- `.aitask-scripts/board/__init__.py` — NEW, docstring only (C1/C2 contract in
  prose; no code).
- `.aitask-scripts/board/aitask_board.py:17` — add
  `sys.path.insert(0, str(Path(__file__).resolve().parent))` beside the
  existing `lib` insert so flat sibling imports resolve under every loader.
- `tests/test_board_package_contract.py` — NEW (C1 guards).
- `tests/test_board_fixture_harness.py` — extend with the C2 guard (the parent
  acceptance criteria name this file) and widen `_canonical_board_imports`
  (`:479–493`) from the literal `"aitask_board"` to the full board module-name
  set (`board_widgets`, `board_trail_view`, `board_task_model`,
  `board_task_manager`, `board_workflow_phase`, `board_trail_screen`,
  `trails_app`, `board_detail_screen`, `board_column_dialogs`) so a fixture
  test that canonically imports a sibling is caught.
- `tests/test_board_keymap_characterization.py` — NEW (pre-phase mitigation
  `characterize_board_keymap_and_views`).
- `tests/perf/board_footprint.sh` — NEW (manual, not auto-run; bash tests are
  run individually and the Python runner globs `tests/test_*.py`).
- `aidocs/framework/python_tui_performance.md` — new section "t1794 baseline".

## Reference files for patterns

- `tests/test_board_fixture_harness.py` (self-test shape, negative controls,
  `_canonical_board_imports`).
- `tests/test_no_lib_to_tui_import.sh:46–49` (`TUI_PACKAGES` list; the
  layering guard this child does not change).
- `tests/test_record_protocol.py:133` (`DependencyFreeTests` — an `ast`-based
  structural guard; model the AST scans on it).
- `tests/test_task_dir_module_constants.py:67–71, 129–158` (subprocess loader
  with `PYTHONPATH` = `.aitask-scripts:lib:board:settings` — the positive
  control for `aitask_board.py`'s own constants; leave it as is).
- `aidocs/framework/python_tui_performance.md` "t718_6 Empirical Verification"
  (measurement protocol and reporting shape).
- `aidocs/framework/tmux_gateway.md` and `lib/tmux_exec.sh` — the footprint
  script must not call raw `tmux` (`tests/test_no_raw_tmux.sh` scans
  `.aitask-scripts` only, but use the gateway anyway).
- `tests/lib/board_fixture.py:1–100` docstring.

## Implementation plan

1. **Rebase check** (pre-phase `rebase_check_before_each_child`):
   `git log --oneline -20 -- .aitask-scripts/board/ tests/lib/board_fixture.py`
   since `c78deab36`; re-read `aitask_board.py:1–130` and
   `board_fixture.py:495–560`; `grep -l '^status: Implementing' aitasks/*.md
   aitasks/t*/*.md` ∩ the board regex (`aitask_board|ait board|By-Trail|
   bytrail|KanbanApp|TaskManager|TaskDetailScreen`). A foreign `Implementing`
   task on the board → stop at this child's plan checkpoint ("Approve and stop
   here") and say so.
2. `board/__init__.py` + the own-dir `sys.path` insert. Confirm
   `python .aitask-scripts/board/aitask_board.py --help`-free boot still works
   (`ait board` in a tmux pane, quit with `q`).
3. `tests/test_board_package_contract.py` (C1), each check with a negative
   control that feeds a synthetic offending source through the same checker:
   - no `board.`-qualified import (`import board.x` / `from board.x import`)
     under `.aitask-scripts/` and `tests/`;
   - no `import aitask_board` / `from aitask_board` in any `board/*.py` other
     than `aitask_board.py`;
   - basename uniqueness across the directories `KNOWN_BINDING_SOURCES`
     reaches (`lib/shortcut_scopes.py:47–65`) plus `board/`;
   - bare-import pairing: for every module `board/board_*.py` that defines a
     top-level name appearing in a `patch.object(<ref>, "<name>"` in `tests/`,
     `aitask_board.py` contains `import <module>` (start with an empty set —
     the check is data-driven and later children populate it).
4. C2 guard in `tests/test_board_fixture_harness.py`: AST scan of every
   `board/*.py` except `aitask_board.py` for a module-level `task_dir(` call or
   any of `TASKS_DIR`, `METADATA_FILE`, `GATES_REGISTRY_FILE`,
   `USERCONFIG_FILE`, `EMAILS_FILE`, `TASK_TYPES_FILE`; plus a runtime check
   after `load_board_module()` that no sibling module in `sys.modules` (names
   from the board module set) holds a `Path` attribute under the fixture tree.
   Negative control: a temp module written into a temp dir and scanned.
5. `tests/test_board_keymap_characterization.py`: with `board_fixture`,
   generate once and pin as a golden literal (a) the full `KanbanApp.BINDINGS`
   `(key, action, description, show)` table (`aitask_board.py:8796–8905`),
   (b) the `check_action(action, None)` result for every bound action across
   `base_filter ∈ {all, locked, free, inflight, bytopic, bytrail}` with no
   focused card and with a focused card (`:8982–9280`), and (c) the presence
   of `HeaderTitle`, `#trail_summary`, `#trail_summary_body`,
   `#board_container` and `LoadingOverlay` in the composed DOM / module. The
   golden is hand-reviewed and committed; a comment says children 5 and 6
   must keep it green **unchanged**. Negative control: a copy of the table
   with one binding removed fails the comparison.
6. `tests/perf/board_footprint.sh <module> <interpreter>`: spawns
   `python -c 'import <module>'` timing (cold-start, 5 reps median) and a
   real launch in a tmux pane via the gateway (`lib/tmux_exec.sh`) sampled at
   10 s idle for RSS (`/proc/<pid>/status VmRSS`); prints one line
   `<sha> <module> <interpreter> rss_mib=<n> coldstart_ms=<n>`. Run it for
   `aitask_board` under `~/.aitask/venv/bin/python` and
   `~/.aitask/pypy_venv/bin/python`, and the **ceiling**: a scratch module
   importing only `textual`, `rich`, `yaml` and the Textual widgets
   `board_trail_view` will use (`Static`, `VerticalScroll`, `Container`,
   `Label`, `Button`, `ModalScreen`, `Binding`). Record all lines in
   `python_tui_performance.md` "t1794 baseline" with the SHA and the task-tree
   size (parent task file count).
7. Inventory (C5) into this child's plan `## Notes for sibling tasks`: every
   path-keyed manifest/test naming `board/aitask_board.py` —
   `lib/shortcut_scopes.py:48`, `tests/test_mark_glyphs_single_source.py:82,117,132`,
   `tests/test_no_raw_tmux.sh:56`, `tests/test_board_reference_doc_literals.py`,
   `tests/test_record_protocol.py:14,133`, `tests/test_board_fixture_harness.py:479–493`,
   `tests/test_shortcuts_registry_coverage.sh:31` — re-grep to complete it.

## Verification steps

- `bash tests/run_all_python_tests.sh` → last line `PYTHON SUITE: PASSED`.
- `python -m pytest tests/test_board_package_contract.py
  tests/test_board_fixture_harness.py tests/test_board_keymap_characterization.py -q`
  green, and each negative control demonstrably fails when its guard is
  disabled (record the red run in the plan).
- `bash tests/test_no_lib_to_tui_import.sh`, `bash tests/test_no_raw_tmux.sh`,
  `python -m pytest tests/test_task_dir_module_constants.py -q` green.
- `tests/perf/board_footprint.sh` produces three lines (board × 2
  interpreters + ceiling) and they are in `python_tui_performance.md`.
- `ait board` boots in tmux and `q` quits.
