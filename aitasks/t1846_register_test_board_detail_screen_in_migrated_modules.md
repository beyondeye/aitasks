---
priority: low
effort: low
depends: []
issue_type: chore
status: Implementing
labels: [python, testing]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1794
followup_kind: review_finding
created_at: 2026-09-20 11:14
updated_at: 2026-09-20 11:20
---

## Context

`tests/test_board_detail_screen.py` (added by t1794_7) documents itself as held
to the strict fixture tier — its module docstring says:

> Reaches the module only as `self.ab.board_detail_screen` … never by a
> canonical import (see `MIGRATED_MODULES` in test_board_fixture_harness.py).

But it was never added to that tuple. Every other extraction in the t1794 family
registered its own pin test there (`test_board_widgets.py`,
`test_board_trail_view.py`, `test_board_task_manager.py`,
`test_trail_screen_host_protocol.py`, and `test_board_column_dialogs.py` added
by t1794_8). t1794_7 is the only gap.

Consequence: the file can silently regain a canonical `import aitask_board` or
a chdir and the tier-2 guard will not notice — the exact drift the tuple exists
to prevent. It is a latent hole, not a current failure.

Found while implementing **t1794_8**, which added its own entry and
deliberately did **not** fold this in: it is t1794_7's gap and needs its own
red-then-green check rather than riding along on an unrelated commit.

## Key files to modify

- `tests/test_board_fixture_harness.py` — `MIGRATED_MODULES` (around `:350`).
  Add `"test_board_detail_screen.py"` with a one-line comment in the same style
  as the neighbouring entries (`# t1794_7: …`).

## Implementation plan

1. Run `python -m pytest tests/test_board_fixture_harness.py -q` first and
   record it green (baseline).
2. Add the entry.
3. Re-run. **The point of the task is that it must still be green**: the tier-2
   rule is "no chdir of any kind and no canonical `aitask_board` import", and
   `test_board_detail_screen.py` already satisfies both (it loads the board
   through `board_fixture`). If it goes red, the file violates the tier it
   claims — report that rather than removing the entry.
4. Prove the entry is live (red-then-green): temporarily add a canonical
   `import aitask_board` to `test_board_detail_screen.py`, confirm the harness
   goes red naming that file, then revert the probe. Do **not** use
   `git restore` to revert it — this checkout is shared by concurrent sessions;
   undo the edit in place.

## Verification steps

- `python -m pytest tests/test_board_fixture_harness.py tests/test_board_detail_screen.py -q` green.
- The red-then-green probe recorded in the plan's implementation notes.
- `bash tests/run_all_python_tests.sh` → last line `PYTHON SUITE: PASSED`.
