---
Task: t732_1_cluster_a_textual_tui_api_drift.md
Parent Task: aitasks/t732_fix_failing_pre_existing_test_suite.md
Sibling Tasks: aitasks/t732/t732_*.md
Archived Sibling Plans: aiplans/archived/p732/p732_*.md
Worktree: (current branch — fast profile sets create_worktree:false)
Branch: (current branch)
Base branch: main
---

# p732_1 — Cluster A: Textual / Python 3.14 TUI API drift

## Goal

Make `tests/test_multi_session_minimonitor.sh` and `tests/test_tui_switcher_multi_session.sh` pass on `main` (today: `74c59788`) without regressing live TUI behavior.

## Confirmed failures (today)

- **multi_session_minimonitor**: `AttributeError: 'MiniMonitorApp' object has no attribute '_thread_id'` at `textual/dom.py:525` + `RuntimeWarning: coroutine 'MiniMonitorApp._start_monitoring.<locals>._connect_control_client' was never awaited`.
- **tui_switcher_multi_session**: `textual.css.query.NoMatches: No nodes match '#switcher_desync' on TuiSwitcherOverlay()` at `lib/tui_switcher.py:483` (`_render_desync_line` queries before mount).

## Steps

1. Read `aitasks/t732/t732_1_cluster_a_textual_tui_api_drift.md` for full failure context.
2. `~/.aitask/venv/bin/python -m pip show textual` to learn installed version.
3. Locate `MiniMonitorApp`: `grep -rn 'class MiniMonitorApp' .aitask-scripts/`.
4. Patch `_thread_id` reference in MiniMonitorApp to use the current Textual API; ensure `_connect_control_client` is properly awaited (`asyncio.create_task` or similar).
5. Patch `lib/tui_switcher.py:483` `_render_desync_line`: replace `query_one('#switcher_desync')` with mount-guard (`if self.is_mounted:`) or `query` (zero-or-more) + early return when empty.
6. Reference `CLAUDE.md` "Priority bindings + `App.query_one` gotcha" entry for the established pattern.
7. Run both tests: `bash tests/test_multi_session_minimonitor.sh && bash tests/test_tui_switcher_multi_session.sh`.
8. Smoke `./ait minimonitor` in a real tmux session (manual sanity check).

## Verification

- Both originally-failing tests pass.
- `for t in tests/test_*tui*.sh tests/test_*monitor*.sh; do bash "$t" >/dev/null 2>&1 || echo "FAIL: $t"; done` reports nothing new.
- Live TUI smoke test passes.

## Step 9 (Post-Implementation)

Per `task-workflow/SKILL.md` Step 9, archive via `./.aitask-scripts/aitask_archive.sh 732_1`. The parent t732 will auto-archive once all 7 children are Done.
