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

## Final Implementation Notes

- **Actual work done:** Two minimal patches.
  1. `.aitask-scripts/lib/tui_switcher.py` — `_render_desync_line` now uses `self.query("#switcher_desync")` (zero-or-more) with an early-return on empty, instead of `self.query_one("#switcher_desync", Label)`. This makes the call safe when `_cycle_session` fires before mount — same defensive style as the `screen.query_one` guard at `_cycle_session:622-625`.
  2. `tests/test_multi_session_minimonitor.sh` — Tier 1c block now stubs `app.run_worker = lambda c, *a, **k: c.close()` alongside the existing `call_later` / `set_interval` stubs. Closing the coroutine doubles as the fix for the `RuntimeWarning: coroutine '_connect_control_client' was never awaited`.

  Both target tests pass: `test_multi_session_minimonitor` 24/24, `test_tui_switcher_multi_session` 45/45.

- **Deviations from plan:** None at the step level. The verify-mode diagnosis update (committed before implementation) corrected the original plan's hypothesis that `_thread_id` had been removed/renamed — Textual 8.1.1 still has it (set by `_thread_init()` at app launch). The actual cause was the test bypassing `App.__init__` via `MiniMonitorApp.__new__(...)`, leaving `_thread_id` unset.

- **Issues encountered:** None blocking. The `_thread_id` AttributeError and the unawaited-coroutine `RuntimeWarning` were two facets of the same root cause (test-side run_worker invocation on a non-initialized app); a single stub that closes the coroutine fixes both.

- **Key decisions:**
  1. Production-side fix in `tui_switcher.py` rather than test-side mocking. The `query_one` → `query` change is cheap, locally readable, and matches the existing defensive pattern in the same class. It also protects any other call site that might construct a switcher overlay before mount.
  2. Test-side fix in `test_multi_session_minimonitor.sh` (not production) for the `_thread_id` issue. Production code (`_start_monitoring` is called from `on_mount`) is correct — `App.run_async` calls `_thread_init()` before mounting. Adding any defensive shim in `_start_monitoring` would mask a real bug if a future refactor invoked it pre-mount.
  3. Used `c.close()` in the stub (not `lambda *a, **k: None`) to consume the coroutine and silence the `RuntimeWarning` cleanly.

- **Upstream defects identified:**
  - `tests/test_multi_session_monitor.sh:LINE — multi-session discover_panes aggregation is broken on main today` (6/43 failures: `multi-session discover_panes aggregates both sessions`, `panes from sessA are tagged`, `sessA panes come first after sort`, `companion filter still excludes companions in multi mode`, `non-companion pane survives`, `real tmux: sessB pane discovered`). This is a separate test (note the lack of `mini`) and was already failing on `main` before this task — confirmed by stashing my changes and re-running. NOT in t732's listed-scope failures. Same general theme as t732 Cluster A (multi-session TUI machinery), but a distinct test and distinct symptom (pane discovery rather than overlay query). Worth a standalone bug aitask.

- **Notes for sibling tasks:** The defensive `query` (zero-or-more) + early-return idiom is now used in `tui_switcher._render_desync_line` alongside the existing `screen.query_one` + `SkipAction` idiom in `_cycle_session`. Other Cluster A-adjacent bugs may benefit from the same pattern. For tests that construct Textual `App` subclasses via `__new__`, remember to stub `run_worker` (and any other method that touches `_thread_id`) in addition to `call_later` / `set_interval`.
