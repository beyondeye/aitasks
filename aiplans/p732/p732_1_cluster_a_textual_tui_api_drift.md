---
Task: t732_1_cluster_a_textual_tui_api_drift.md
Parent Task: aitasks/t732_fix_failing_pre_existing_test_suite.md
Sibling Tasks: aitasks/t732/t732_*.md
Archived Sibling Plans: aiplans/archived/p732/p732_*.md
Worktree: (current branch — fast profile sets create_worktree:false)
Branch: (current branch)
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-03 19:04
---

# p732_1 — Cluster A: Textual / Python 3.14 TUI API drift

## Goal

Make `tests/test_multi_session_minimonitor.sh` and `tests/test_tui_switcher_multi_session.sh` pass on `main` (today: `74c59788`) without regressing live TUI behavior.

## Confirmed failures (today)

- **multi_session_minimonitor**: `AttributeError: 'MiniMonitorApp' object has no attribute '_thread_id'` at `textual/dom.py:525` + `RuntimeWarning: coroutine 'MiniMonitorApp._start_monitoring.<locals>._connect_control_client' was never awaited`.
- **tui_switcher_multi_session**: `textual.css.query.NoMatches: No nodes match '#switcher_desync' on TuiSwitcherOverlay()` at `lib/tui_switcher.py:483` (`_render_desync_line` queries before mount).

## Verify-mode diagnosis update (2026-05-03)

The original plan hypothesized "Textual API drift" / "renamed `_thread_id`". Verification with Textual 8.1.1 (`/home/ddt/.aitask/venv/lib/python3.14/site-packages/textual/`) shows the actual root causes:

1. **`_thread_id` AttributeError is a test-setup artifact, NOT Textual drift.** Textual 8.1.1 still has both `_thread_id` and `_thread_init()` (textual/app.py:901-910). `_thread_init()` is what sets `_thread_id`, and it runs from `App.run_async()` (line 2229) — i.e., when the app is actually launched. The test (`tests/test_multi_session_minimonitor.sh:120-131`) constructs the app via `MiniMonitorApp.__new__(...)` (bypassing `App.__init__`), then calls `_start_monitoring()` directly. The test already stubs `call_later`/`set_interval` for the same reason but does NOT stub `run_worker`. Fix is test-side: add `app.run_worker = lambda c, *a, **k: c.close()` (closes the coroutine to suppress the unawaited-coroutine warning too).

   Production code in `monitor/minimonitor_app.py:188+214` is unchanged — `_start_monitoring` is called from `on_mount`, by which time `_thread_init()` has already run.

2. **`_render_desync_line` `query_one` failure is a real production-code issue** (also tripped by the test). At `lib/tui_switcher.py:483` it uses `self.query_one("#switcher_desync", Label)`. When called from `_cycle_session` before/outside `compose()`-mounted children exist, this raises `NoMatches`. Fix: convert to `query("#switcher_desync")` (zero-or-more) and early-return if empty. This matches the defensive pattern at `_cycle_session:622-625` (catch `Exception` from `screen.query_one` → `SkipAction`).

   The actual file path for `MiniMonitorApp` is `.aitask-scripts/monitor/minimonitor_app.py` (NOT `aitask_minimonitor.py` as the original plan guessed).

## Steps

1. **Fix `lib/tui_switcher.py:483`**: replace `query_one("#switcher_desync", Label)` with a zero-or-more query + early return:
   ```python
   line_widgets = self.query("#switcher_desync")
   if not line_widgets:
       return
   line_widget = line_widgets.first(Label)
   text = self._compute_desync_summary(project_root)
   line_widget.update(text)
   ```
2. **Fix `tests/test_multi_session_minimonitor.sh`** Tier 1c block (around line 128-129): add `app.run_worker = lambda c, *a, **k: c.close()` next to the existing `app.call_later` and `app.set_interval` stubs so the test can call `_start_monitoring()` on a `__new__`-constructed app without engaging Textual's threading machinery. Closing the coroutine also suppresses the `RuntimeWarning`.
3. Run both tests: `bash tests/test_multi_session_minimonitor.sh && bash tests/test_tui_switcher_multi_session.sh`.
4. Adjacent regression sweep: `for t in tests/test_*tui*.sh tests/test_*monitor*.sh; do bash "$t" >/dev/null 2>&1 || echo "FAIL: $t"; done` should report nothing new.
5. Smoke `./ait minimonitor` in a live tmux session (manual sanity check) — production `_start_monitoring` path is untouched, so this should remain working.

## Verification

- Both originally-failing tests pass.
- `for t in tests/test_*tui*.sh tests/test_*monitor*.sh; do bash "$t" >/dev/null 2>&1 || echo "FAIL: $t"; done` reports nothing new.
- Live TUI smoke test passes.

## Step 9 (Post-Implementation)

Per `task-workflow/SKILL.md` Step 9, archive via `./.aitask-scripts/aitask_archive.sh 732_1`. The parent t732 will auto-archive once all 7 children are Done.
