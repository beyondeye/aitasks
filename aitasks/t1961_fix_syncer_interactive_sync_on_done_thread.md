---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1911
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-12 21:46
updated_at: 2026-10-12 22:23
---

## Origin

Spawned from t1955 during Step 8b review.

## Upstream defect

- `.aitask-scripts/syncer/syncer_app.py:2453 — _run_interactive_sync_shared passes on_done=lambda: self.call_from_thread(self._tick_refresh), but the async worker and run_interactive_sync's inline (no-terminal) completion callback both run on the app thread, so a successful inline ./ait sync resumes the terminal and then raises RuntimeError (call_from_thread must run in a different thread); pre-existing in HEAD, the real helper's completion callback is untested`

## Diagnostic context

Found during the t1955 Step 8 review (commit 4acd6253a), which put `_run_interactive_sync_shared` under the new `_task_data_guard`. The worker is `@work(exclusive=True, group="syncer-action")` and **async**, so it runs on the app thread. `run_interactive_sync` (`.aitask-scripts/lib/sync_action_runner.py`) either spawns a terminal (fire-and-forget, `on_done` never called) or suspends the app, runs `./ait sync` inline, and then calls `on_done()` synchronously in the same thread. With no terminal, `on_done` therefore runs `self.call_from_thread(...)` on the app thread, and Textual raises `RuntimeError: The call_from_thread method must run in a different thread from the app`. The reviewer reproduced this through the real helper and `App.suspend` with a fake driver. The t1955 coordination lock still releases correctly (the guard's `finally`), but the post-sync refresh never happens and the worker errors.

The board's twin (`KanbanApp._run_interactive_sync_shared`) passes a plain `reload` callable and is unaffected.

The t1955 tests stub `run_interactive_sync` entirely (`tests/test_syncer_rows.py`, `StraySyncTests` / `DataConflictAgentTests.agent_seams`), so nothing exercises the real helper's completion callback.

## Suggested fix

Call `self._tick_refresh()` directly in `on_done` (or `self.call_later(self._tick_refresh)`), since the callback already runs on the app thread. Add a test that drives the REAL `run_interactive_sync` through `App.suspend` with a suspend-capable fake driver (see `_fake_driver` in `tests/test_board_run_editor.py`), `find_terminal` returning None and `subprocess.call` stubbed, then asserts that the refresh ran and the worker did not error.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-12T19:23:22Z status=pass attempt=1 type=human
