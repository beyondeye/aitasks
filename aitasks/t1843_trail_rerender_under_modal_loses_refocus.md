---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_board, tui, trails, python]
anchor: 1794
followup_kind: upstream_defect
created_at: 2026-09-18 16:24
updated_at: 2026-09-18 16:24
---

## Origin

Spawned from t1839 during Step 8b review.

## Upstream defect

- `.aitask-scripts/board/board_trail_screen.py:771-783 — _on_trail_drift (and _on_trail_reload → _rerender_trail) re-render By-Trail while a modal may be open; the refocus target is read via _focused_card(), which reads self.screen (the MODAL's focus) and so is empty, and the queued refocus queries the active screen (the modal) — after dismissal the board has no card focused`

## Diagnostic context

Found while fixing t1839 review feedback. The async drift/reload callbacks
check only generation / view / handle, never `_modal_is_active()`. When a
By-Trail modal (e.g. the `v` trail summary, `TrailSummaryScreen`) is up:

- `_on_trail_drift` computes `focused = self._focused_card()` →
  `self.screen.focused` is the modal's focus → `None` → refocus filename `""`.
- `_rerender_trail` computes `refocus_col_id = self._get_focused_col_id()` —
  same problem, empty.
- The queued `_refocus_card` / `_refocus_column` run `self.query(...)`, whose
  DOM base is `app.screen` — the modal — so they find nothing even when given a
  target.
- Textual's `_prune` resets the board screen's focus to some remaining
  focusable (a container), so keys are not dead — but no CARD is focused after
  the modal closes, and every card-scoped binding (`enter`, `T`, arrows'
  origin, …) is off until the user presses an arrow.

t1839 added, on the board only, a board-screen-aware watch that restores the
card when the focus is left **detached** (`KanbanApp._rerender_trail`
override, `_board_screen()`, `_detached_focus_pending`,
`BoardScreen.on_screen_resume` → `_resume_detached_focus`). It deliberately
does NOT fix the plain lost-refocus case above (attached-but-not-a-card focus).
`TrailsApp` has a resume rescue (`TrailsScreen.on_screen_resume` →
`apply_filter`) that focuses the *first* card, not the previous one.

Repro idea (Pilot, `tests/test_board_bytrail_view.py` idiom): enter
`_enter_synthetic_bytrail` with `_ghost_doc()`, focus the second ghost card,
`action_trail_summary_expand()`, call `app._on_trail_drift(app._trail_gen,
"art:trail-test", "CURRENT", [])`, `pop_screen()`, assert the focused widget is
the same card (today: not a TaskCard).

## Suggested fix

Either defer the re-render while a modal is active (store the drift/reload
result and re-render on board-screen resume), or have the re-render capture the
refocus target from the board screen (`screen_stack[0]`) and queue the refocus
until that screen is active again — reusing t1839's `_board_screen()` /
`on_screen_resume` plumbing so there is one resume path. Consider TrailsApp
parity in the same task.
