---
Task: t1846_register_test_board_detail_screen_in_migrated_modules.md
Branch: aitask/t1846_register_test_board_detail_screen_in_migrated_modules
Base branch: main
Output branch: main
---

# t1846 — Register `test_board_detail_screen.py` in `MIGRATED_MODULES`

## Context

`tests/test_board_detail_screen.py` (added by t1794_7) documents itself as held to
the strict fixture tier — its module docstring says it reaches the module only as
`self.ab.board_detail_screen`, "never by a canonical import (see `MIGRATED_MODULES`
in test_board_fixture_harness.py)". But it was never added to that tuple.

Every other extraction in the t1794 family registered its own pin test there
(`test_board_widgets.py`, `test_board_trail_view.py`, `test_board_task_manager.py`,
`test_trail_screen_host_protocol.py`, and `test_board_column_dialogs.py` from
t1794_8). t1794_7 is the only gap.

Consequence: the file can silently regain a canonical `aitask_board` import or a
chdir and the **tier-2** guard will not notice. It is a latent hole, not a current
failure — tier 1 still sweeps the file, but tier 1 is the weaker rule (it honours
per-module exemptions; tier 2 forbids *any* chdir and *any* canonical board
import, exemptions included).

Found while implementing t1794_8, which added its own entry and deliberately did
**not** fold this in: it is t1794_7's gap and needs its own red-then-green check
rather than riding along on an unrelated commit.

Outcome: the tuple names the file, and the entry is proven live by a control.

## Current state (verified)

- `tests/test_board_fixture_harness.py:350` — `MIGRATED_MODULES`, 23 entries,
  ordered by t1794 sub-task (`_1`, `_2`, `_3`, `_4`, `_5`, `_8`).
- `tests/test_board_detail_screen.py` already satisfies the tier-2 rule: no
  `chdir` of any kind, and its only imports are `inspect`, `sys`, `unittest`,
  `pathlib`, `unittest.mock`, and `board_fixture as bf`. So the entry must land
  **green**.
- Baseline recorded: `~/.aitask/venv/bin/python -m pytest
  tests/test_board_fixture_harness.py -q` → **53 passed**.
- `test_sweep_covers_more_than_the_migrated_set` needs
  `len(tier-1 glob) > len(MIGRATED_MODULES)`: 58 > 23 today, 58 > 24 after. Ample
  headroom.

## Key file to modify

- `tests/test_board_fixture_harness.py` — `MIGRATED_MODULES` (`:350`). One entry
  plus a one-line comment in the neighbours' style, inserted **between the
  t1794_5 and t1794_8 entries** to keep the tuple in ascending sub-task order:

  ```python
      # t1794_7: the task-editor re-export identity, injected-helper and
      # tasks_dir pins reach the board and `board_detail_screen` only as `ab.*`.
      "test_board_detail_screen.py",
  ```

## Implementation steps

1. **Baseline** — already recorded above (53 passed). Re-confirm nothing changed
   underneath if the tree has moved since.

2. **Add the entry** to `MIGRATED_MODULES` as shown, in ascending sub-task order.

3. **Re-run and require green:**
   ```bash
   ~/.aitask/venv/bin/python -m pytest tests/test_board_fixture_harness.py -q
   ```
   The point of the task is that this must **still be green** (54 expected
   subTests over the tuple, same 53 test methods). If it goes red, the file
   violates the tier it claims — **report that**, do not remove the entry.

4. **Prove the entry is live (red-then-green, with a control).**

   The task text prescribes a canonical `import aitask_board` probe. Verified
   refinement: `test_board_detail_screen.py` matches the **tier-1** glob
   `test_board_*.py`, so that probe trips `LiveTreeSweepTests` as well — "the
   harness goes red" would therefore prove nothing about the new tuple entry. The
   signal is isolated by running the **tier-2 class alone**, in two states:

   ```bash
   # probe: runtime-inert (never called), still seen by the AST guard
   # appended to tests/test_board_detail_screen.py
   def _t1846_probe():
       import aitask_board
   ```

   - **(A) control — probe present, tuple entry temporarily removed:**
     `MigratedModuleGuardTests` **passes** (the module is not in the tuple, so no
     subTest for it exists).
   - **(B) probe present, tuple entry present:**
     `MigratedModuleGuardTests.test_migrated_modules_have_no_live_tree_coupling`
     **fails**, its subTest naming `module='test_board_detail_screen.py'` and
     reporting `canonical import: import aitask_board`.

   The A→B delta is attributable to the new entry alone.

   ```bash
   ~/.aitask/venv/bin/python -m pytest tests/test_board_fixture_harness.py \
     -q -k MigratedModuleGuardTests
   ```

   Why a function-level import: `_canonical_board_imports` uses `ast.walk`, so it
   sees an `Import` node anywhere in the file, while a never-called function keeps
   the probe inert at runtime. This checkout is shared with concurrent sessions —
   a module-level import would load the real board into `sys.modules` for anyone
   who ran the file during the probe window.

5. **Revert the probe in place** — delete the appended function with an in-place
   edit. Do **not** use `git restore`: this checkout is shared and dirty.
   Then re-confirm step 3 is green before committing.

   The probe window is bounded to steps 4–5 and touches only the tier-2 class.

## Verification

- `~/.aitask/venv/bin/python -m pytest tests/test_board_fixture_harness.py tests/test_board_detail_screen.py -q` → green.
- The A/B control from step 4 recorded in the plan's Final Implementation Notes
  (both states, with the failing subTest name quoted).
- `git status` shows `tests/test_board_fixture_harness.py` as the **only**
  modified file (the probe is fully reverted).
- `bash tests/run_all_python_tests.sh` → last line `PYTHON SUITE: PASSED`.
  Read only that last line; do not pipe without `pipefail`.

## Step 9 (Post-Implementation)

Current-branch mode (profile `fast`, `create_worktree: false`) — nothing to merge.
Step 9 handles archival of the task and this plan.

## Risk

### Code-health risk: low
- The red-then-green probe temporarily edits a test file in a checkout shared with
  concurrent sessions, so a suite run during the window would see a false red ·
  severity: low · → mitigation: none needed (step 4 bounds the window to two
  tier-2-only runs and step 5 reverts in place immediately)

### Goal-achievement risk: low
- None identified. The change is one tuple entry; the file already satisfies the
  tier-2 rule (verified by reading its imports), and the A/B control proves the
  entry is enforced rather than inert.
