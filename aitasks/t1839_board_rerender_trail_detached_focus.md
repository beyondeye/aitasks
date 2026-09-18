---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_board, tui, trails, python]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1794
followup_kind: upstream_defect
created_at: 2026-09-18 12:47
updated_at: 2026-09-18 12:55
---

## Origin

Spawned from t1794_6 during Step 8b review.

## Upstream defect

- `.aitask-scripts/board/board_trail_screen.py:399-423 — _rerender_trail removes and re-mounts the lanes and queues the refocus with call_after_refresh; if that callback runs before the asynchronous mount lands, screen.focused can be left on a detached card (observed in TrailsApp under load; the board shares this code path and its _focused_card does not check attachment — suspected, not reproduced on the board)`

## Diagnostic context

While stabilising `tests/test_trails_app.py` under the parallel suite, a run
left `app.screen.focused` pointing at a `TrailGhostCard` that was **no longer
in the DOM** (`is_attached == False`, absent from `query(TaskCard)`), with
`'v' not in app.screen.active_bindings` — every App-level key was dead until
something re-anchored focus. The sequence: `_activate_trail` → drift worker →
`_on_trail_drift` → `_rerender_trail(<focused filename>)`, which calls
`container.remove_children()` and mounts fresh `TrailColumn`s (asynchronous),
then `call_after_refresh(apply_filter)` and `_queue_refocus(filename, col)`.
When the refocus callback ran before the mount landed, no card matched the
filename, nothing was focused, and Textual's own focus reset had left the
removed card as `screen.focused`.

`TrailsApp` (t1794_6) fixed its side: `_focused_card()` requires
`is_attached`, and `_refocus` / the focus rescue re-queue themselves (bounded)
until the re-mounted cards are queryable
(`.aitask-scripts/board/trails_app.py`, `_MOUNT_HOPS`). The board's
`KanbanApp._focused_card` is a bare `screen.focused` attribute read and its
`_refocus_card` does not re-queue, so the same race is plausible in the
board's By-Trail view after a drift callback — **not reproduced there**; the
first step is a Pilot repro on the board (`tests/test_board_bytrail_view.py`
idiom, `discover_trails` / `run_trail_drift` patched on `ab.board_trail_screen`,
force the drift callback's re-render, assert `screen.focused.is_attached`).

## Suggested fix

Either in the mixin (`_rerender_trail`: defer `_queue_refocus` until the mount
awaitable completes, or make the queued refocus re-queue while no card is
mounted, as `TrailsApp._refocus` does) or in the board's `_focused_card` /
`_refocus_card` (treat a detached card as "nothing focused" and fall back to
the column). Keep `tests/test_board_keymap_characterization.py` green.
