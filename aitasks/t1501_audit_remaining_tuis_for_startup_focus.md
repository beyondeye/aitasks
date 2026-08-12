---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [tui]
gates: [risk_evaluated]
anchor: 1449
followup_kind: carry_over
created_at: 2026-08-12 23:15
updated_at: 2026-08-12 23:15
---

## Origin

Spawned from t1495, which deliberately scoped its live audit to the four TUIs
that task named. These six were found unguarded during the same survey and were
explicitly recorded as **unaudited — not clear**.

## Scope

None of these sets `AUTO_FOCUS`, so each inherits `App.AUTO_FOCUS = "*"` and is
exposed to the same startup-focus defect t1491 fixed in the board and t1495
fixed in the codebrowser:

- `.aitask-scripts/monitor/minimonitor_app.py` — `MiniMonitorApp`
- `.aitask-scripts/syncer/syncer_app.py` — `SyncerApp`
- `.aitask-scripts/chatlink/chatlink_app.py` — `ChatlinkApp`
- `.aitask-scripts/applink/applink_app.py` — `ApplinkApp`
- `.aitask-scripts/diffviewer/diffviewer_app.py` — `DiffViewerApp`
- `.aitask-scripts/agentcrew/agentcrew_dashboard.py` — `AgentCrewDashboard`

Static reading suggests none mounts a text `Input` on its default screen, but
that is exactly the claim t1495 existed to stop taking on trust — a static read
is not a verdict.

## Why this was deferred rather than folded into t1495

Several of these need bespoke state before they will boot at all: a paired
applink, a live crew for the dashboard, a chatlink gateway session. Building
those fixtures is the bulk of the work, which is why it was split out.

## Method

The method, the fixture recipe and the audit table now live in
`aidocs/framework/tui_conventions.md`, section "Startup focus: `AUTO_FOCUS` can
hand the keyboard to a text `Input`". Follow it rather than re-deriving:

1. Trace, do not read the screen. Wrap `textual.screen.Screen._update_auto_focus`
   to log the resolved selector and the widget it leaves focused, inject it via
   a `sitecustomize.py` on `PYTHONPATH` (which preserves the real entry point),
   and run the TUI in an isolated `tmux -L <socket>` pane.
2. Pass env vars as an `env` PREFIX on the command. `tmux set-environment` only
   reaches panes tmux spawns itself, so a command typed with `send-keys` into an
   already-running shell inherits none of it. Getting this wrong produces an
   EMPTY trace while the TUI boots normally — which reads exactly like "nothing
   was picked".
3. Run a positive control first, against a TUI whose behaviour is already known
   (the board, or now the codebrowser). No "clean" verdict is admissible until
   the control produces a non-empty trace.
4. Take the behavioural signal (bare quit key with no prior Tab/Esc/click, then
   poll `#{pane_current_command}`) only when the **default screen** is the active
   screen. If a modal is on top, the reading is about the modal — see how t1495
   had to seed a real brainstorm session because `InitSessionModal`'s cancel path
   calls `self.exit()`.

## Acceptance criteria

- [ ] For each of the six, determine what auto-focus picks at compose, verified
      in a real pty — not headless.
- [ ] Fix each affected TUI using the two-layer shape (a `Screen` subclass with
      `AUTO_FOCUS = ""` from `get_default_screen()`, plus a deferred
      `_claim_startup_focus`), or record why it is not affected.
- [ ] Add a regression pin for each TUI that is fixed. Determine per app whether
      headless can fail on it: the board's could not, the codebrowser's could.
- [ ] Update the audit table in `aidocs/framework/tui_conventions.md`, moving
      each app out of the "unaudited" list.

## References

- t1495 — the codebrowser fix, its pins (`tests/test_codebrowser_startup_focus.py`,
  `tests/test_codebrowser_startup_focus_live.py`) and the audit table.
- t1491 — the board fix and the driver-divergence finding.
- t1486 — the same defect family fixed earlier in logview.
