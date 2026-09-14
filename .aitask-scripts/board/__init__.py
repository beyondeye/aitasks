"""The `ait board` package (t1794).

Marks `board/` as a package like the other TUI directories. Nothing imports it
as `board`: every module here is imported by BARE name (`import
board_trail_view`), never `board.`-qualified, relative or dynamically, because
the board runs under several loaders that each put this directory on `sys.path`
— the launcher (`python board/aitask_board.py`), the test fixture
(`spec_from_file_location` under a synthetic name), the shortcut sweep
(`lib/shortcut_scopes.py`), the tests' canonical `import aitask_board`, and
subprocess loaders — and `aitask_board.py` inserts its own directory as well.

Contract (C1/C2 of aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md),
enforced by tests/test_board_package_contract.py and
tests/test_board_fixture_harness.py:

* C1 — flat bare-name imports only. New modules are `board_`-prefixed so no
  basename collides with another directory on the flat path, and no module
  other than aitask_board.py imports aitask_board.
* C2 — only aitask_board.py resolves the task directory (`task_dir()`,
  `metadata_dir()`, the `TASK_DIR` environment variable, the `TASKS_DIR`-derived
  constants). Every other module receives resolved paths as parameters and
  neither binds them at import nor looks them up lazily: under the test fixture
  both read the wrong tree, and neither fails loudly.

Keep this file free of code.
"""
