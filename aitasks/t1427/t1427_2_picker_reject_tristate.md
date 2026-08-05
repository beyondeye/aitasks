---
priority: high
effort: high
depends: [t1427_1]
issue_type: feature
status: Implementing
labels: [shadow, aitask_monitormini, aitask_monitor]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1159
created_at: 2026-08-05 17:18
updated_at: 2026-08-05 23:52
---

Picker-side reject action for t1427. Depends on t1427_1 (the store helper
`aitask_shadow_rejected.sh` exists and is tested). Parent plan
`aiplans/p1427_reject_shadow_concerns_suppress_next_round.md` is binding.

## Context

`ConcernPickerModal` (`.aitask-scripts/monitor/monitor_shared.py`) currently
only forwards concerns; there is no reject. This child adds the per-row
tri-state, persists rejections through the t1427_1 helper, adds the
rejected-store view with un-reject, and changes the dismiss contract. User
decisions (binding): the `a`/`A` bulk shortcuts are REMOVED ENTIRELY (per-row
actions only, so rejection state is never bulk-overridden); un-reject is
TUI-only; no stale-data conflict handling or refresh behavior for pre-fetched
store entries (concurrent cross-session editing is out of scope).

## Key changes

1. `_ConcernRow` (monitor_shared.py ~1218-1353): replace `_selected: bool`
   with a mutually-exclusive tri-state none/forward/rejected. Glyphs: `☐`
   none, `[bold yellow]☑[/]` forward, `[red]✗[/]` rejected (single-width —
   keeps `_NARROW_PREFIX_COLS = 8` valid). New CSS class `rejected`
   (muted/dim red). `Space` toggles forward (clears rejected); `r` toggles
   rejected (clears forward) — both in `_ConcernRow.on_key` (which currently
   handles space/down/up).
2. Remove bulk actions: `a` (`action_toggle_all`) and `A` (`action_copy_all`)
   BINDINGS, action methods, their help-string entries, and their tests
   (`test_copy_all_dismisses_with_every_concern`, the toggle-all suite).
3. New `ConcernPickResult` NamedTuple in monitor_shared.py:
   `forwarded: list[Concern]`, `rejected: list[Concern]`,
   `unrejected: tuple[str, ...]` (store entry ids). Modal dismisses with
   `ConcernPickResult | None` (None on Esc/Cancel). Update the class
   docstring (~1460-1486, states the old contract) and all remaining dismiss
   sites (`action_confirm`, `action_dismiss_dialog`, `on_button_pressed`).
4. Rejected-store view: apps pre-fetch
   `aitask_shadow_rejected.sh list --machine <task_id>` at
   `action_pick_concerns` time (subprocess off the event loop) and pass parsed
   entries into `ConcernPickerModal`. `R` pushes a new `RejectedStoreModal` on
   the App (pattern: `action_inspect_unrecovered` / `ConcernBlockInspectModal`
   ~1396-1456) listing persisted entries with a per-row un-reject toggle; its
   dismissal feeds the picker's `_unreject_ids`, returned in the final result.
   Modal stays pure-UI — all disk I/O app-side. Machine lines parse with
   `split('|', 3)` (marker line last, contains `|`).
5. Both `_on_concerns_picked` callbacks (`monitor_app.py` ~2936,
   `minimonitor_app.py` ~1745): switch `if not selected:` to explicit
   `is None`; forwarded → clipboard payload + notify (unchanged, via
   `copy_to_system_clipboard`, never `app.copy_to_clipboard`); rejected →
   resolve `task_id = self._task_cache.get_task_id_for_pane(snap.pane)`
   (idiom used ~11x in monitor_app.py) and invoke helper `add` with marker
   lines on stdin; unrejected → helper `remove`. UNRESOLVABLE TASK ID IS A
   VISIBLE REFUSAL, never silent: notify "Rejections not persisted — no task
   id for this pane"; the `R` view shows a "no task id" notice.
6. Extract `concern_marker_line(c)` in `concern_parser.py` — the single
   canonical `- [{priority} | {region}] {body}` renderer, used by both
   `build_clipboard_payload` (~539-553, currently inlines it) and the
   persistence path. Uses `.body` (canonical), not `display_body()`.
7. Help strings `_CONCERN_HELP_FULL` / `_CONCERN_HELP_COMPACT` (~1384-1393):
   drop a/A, add `r` reject + `R` rejected-view; keep readable down to 24
   cols (the width test pins this).

## Reference tests to update

- `tests/test_concern_picker_modal.py` — dismiss-contract tests (~187-227)
  now assert `ConcernPickResult`; delete copy-all/toggle-all tests; add
  tri-state glyph/partition tests and `RejectedStoreModal` tests; width-tier
  suite re-tuned.
- `tests/test_monitor_concern_action.py` / 
  `tests/test_minimonitor_concern_action.py` — callbacks invoked with
  `ConcernPickResult`; [rejections_only_result_negative_control] each suite
  MUST assert a result with EMPTY `forwarded` and non-empty `rejected` still
  triggers rejection persistence (pins the `is None` check against a
  truthiness regression); add task-id-refusal notice tests; persistence
  subprocess is spied, not executed.
- `tests/test_concern_body_display_contract.py` freezes `display_body()`
  (DISPLAY) vs `.body` (FORWARD) roles — keep both intact through the
  `concern_marker_line` extraction.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` (verdict = last
  stderr line, check `PIPESTATUS[0]`).
- Live: open minimonitor against a shadow with concerns, reject one with `r`,
  confirm `.aitask-shadow/<task_id>/rejected.md` gains the entry; press `R`,
  un-reject it, confirm removal.
