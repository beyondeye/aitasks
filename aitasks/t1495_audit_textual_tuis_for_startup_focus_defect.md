---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tui]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1449
followup_kind: upstream_defect
created_at: 2026-08-12 14:39
updated_at: 2026-08-12 15:04
---

## Origin

Spawned from t1491 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/monitor_app.py`, `.aitask-scripts/codebrowser/codebrowser_app.py`,
  `.aitask-scripts/brainstorm/brainstorm_app.py`, `.aitask-scripts/settings/settings_app.py` —
  none sets `AUTO_FOCUS`, so each inherits `App.AUTO_FOCUS = "*"` and is exposed to the
  same startup-focus defect t1491 fixed in the board, wherever the TUI's first focusable
  widget in DOM order is a text `Input`. Not verified per-TUI.

## Context

`Screen._update_auto_focus` runs inside `Screen._compose` — before the app's `on_mount` —
and focuses the first focusable widget matching the selector. In the board that was
`Input#search_box`, which made every non-`priority` single-key binding (`q` included)
arrive as search text until the user pressed Tab/Esc or clicked.

t1491 fixed the board with a two-layer change (`.aitask-scripts/board/aitask_board.py`):

- `BoardScreen(Screen)` with `AUTO_FOCUS = ""`, returned from `get_default_screen()`.
  `""`, not `None` — `None` means "inherit `App.AUTO_FOCUS`" and disables nothing.
  Scoped to the default screen so pushed modals keep the app-level `"*"`.
- `_claim_startup_focus()`, deferred from `on_mount`, anchors focus on a real widget.

## Diagnostic method (important)

**A headless test cannot detect this.** `Screen._update_auto_focus` picks a different
widget per driver — measured on the board at the same size, a real terminal picked
`Input#search_box` while `App.run_test` picked `HorizontalScroll#board_container`, where
the quit key worked fine. Verify each TUI in a real pty:

1. Launch it in an isolated `-L <sock>` tmux pane against a synthetic fixture.
2. Send its quit key with no prior Tab/Esc/click; assert `#{pane_current_command}`
   returns to the shell.
3. Or trace directly: monkeypatch `textual.screen.Screen.set_focus` to log every call,
   run the TUI live, and read back which widget received focus at compose time.

## Acceptance criteria

- [ ] For each of the four TUIs, determine whether the first focusable widget in DOM
      order is a text `Input` (or otherwise swallows single-key bindings), verified in a
      real pty — not headless.
- [ ] Fix each affected TUI using the t1491 shape, or record why it is not affected.
- [ ] Add a live regression pin for each TUI that is fixed; a headless pin cannot fail
      on this defect.

## References

- t1491 — the board fix, its live pin (`tests/test_board_startup_focus_live.py`) and the
  structural `AUTO_FOCUS` pin (`tests/test_board_startup_focus.py`).
- t1486 — the same defect family fixed earlier in logview (`on_mount` focusing the
  RichLog so single-key bindings fire without a prior mouse click).
