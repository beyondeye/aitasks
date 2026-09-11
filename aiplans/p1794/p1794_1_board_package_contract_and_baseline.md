---
Task: t1794_1_board_package_contract_and_baseline.md
Parent Task: aitasks/t1794_split_board_monofile_and_standalone_trail_tui.md
Sibling Tasks: aitasks/t1794/t1794_2_*.md … aitasks/t1794/t1794_11_*.md
Archived Sibling Plans: aiplans/archived/p1794/p1794_*_*.md
Base branch: main
Output branch: main
---

# p1794_1 — Board package contract, characterization test and footprint baseline

Parent plan: `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
(contracts C1–C10 are PINNED). The task body carries the full step list; this
plan pins the deliverables, the order and the evidence.

## Deliverables

1. `.aitask-scripts/board/__init__.py` (docstring only) and the own-directory
   `sys.path` insert in `aitask_board.py` next to the `lib` insert (`:17`).
2. `tests/test_board_package_contract.py` — C1 guards (AST): no `board.`-
   qualified import under `.aitask-scripts/` or `tests/`; no `aitask_board`
   import in any other `board/*.py`; unique `*.py` basenames across the
   `KNOWN_BINDING_SOURCES` directories + `board/`; bare-import pairing for
   every `board_*` module that defines a `patch.object`-targeted name. Each
   check has a negative control fed a synthetic offending source.
3. `tests/test_board_fixture_harness.py` — C2 guard (AST + runtime after
   `load_board_module()`), widened `_canonical_board_imports` (`:479–493`) to
   the full board module set.
4. `tests/test_board_keymap_characterization.py` — golden literal of
   `KanbanApp.BINDINGS` (`:8796–8905`), the `check_action` matrix over the
   six `base_filter` values with/without a focused card (`:8982–9280`), and
   the trail view's widget contract (`HeaderTitle`, `#trail_summary`,
   `#trail_summary_body`, `#board_container`, `LoadingOverlay`). Children 5
   and 6 keep it green unchanged. Negative control: a one-row-removed copy
   fails.
5. `tests/perf/board_footprint.sh <module> <interpreter>` (tmux via the
   gateway, RSS at 10 s idle, import cold-start median of 5) and the
   "t1794 baseline" section in `aidocs/framework/python_tui_performance.md`:
   `aitask_board` under both interpreters + the ceiling (textual/rich/yaml +
   the trail view's widget imports), with SHA and task-tree size.
6. `## Notes for sibling tasks` below: the C5 inventory.

## Order

Rebase check (parent pre-phase 2) → 1 → 2, 3 (guards red on synthetic
offenders, green on the tree) → 4 (generate, hand-review, pin) → 5 (measure,
record) → 6.

## Notes for sibling tasks

C5 inventory (complete it by re-grepping `board/aitask_board.py` in `tests/`
and `lib/`): `lib/shortcut_scopes.py:48`;
`tests/test_mark_glyphs_single_source.py:82,117,132`; `tests/test_no_raw_tmux.sh:56`;
`tests/test_board_reference_doc_literals.py`; `tests/test_record_protocol.py:14,133`;
`tests/test_board_fixture_harness.py:479–493`;
`tests/test_shortcuts_registry_coverage.sh:31`;
`tests/test_task_dir_module_constants.py:67–71,129–158`.

## Verification

- `bash tests/run_all_python_tests.sh` last line `PYTHON SUITE: PASSED`.
- The three new/extended test modules green; each negative control recorded
  red once with its guard disabled.
- `bash tests/test_no_lib_to_tui_import.sh`, `bash tests/test_no_raw_tmux.sh`
  green; `python -m pytest tests/test_task_dir_module_constants.py -q` green.
- `tests/perf/board_footprint.sh` emits three lines and they are in the aidoc.
- `ait board` boots in tmux and `q` quits.

## Post-implementation

Task-workflow Step 9: commit code + this plan path-scoped, run gates, archive
`t1794_1`.
