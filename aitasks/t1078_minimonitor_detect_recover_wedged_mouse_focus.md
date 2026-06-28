---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [aitask_monitormini, tmux, tui]
created_at: 2026-06-25 11:33
updated_at: 2026-06-25 11:33
boardidx: 170
---

Detect a **wedged tmux mouse/focus state** from inside the minimonitor and offer
a **mouse-clickable** recovery, since while wedged the keyboard cannot reach the
minimonitor.

## Context / the bug this addresses

Intermittently (observed repeatedly; reproduced live 2026-06-25), tmux enters a
state where its **own mouse bindings stop firing** — `select-pane` on click,
status-bar click to switch windows, and right-click context menu all go dead —
while **mouse forwarding to the focused pane's app still works**. Signature is a
**stuck mouse button / mid-drag state** in the client: a `MouseDown` whose
matching `MouseUp` was lost (common on Hyprland when the button is released
outside the terminal or focus is stolen mid-drag), leaving tmux's mouse state
machine mid-drag so it ignores clean clicks for its own bindings.

Concretely, in an agent + minimonitor split window: clicking the minimonitor
changes the list selection (mouse reaches the app) but the minimonitor pane never
becomes active, so **keyboard stays chained to the agent pane**.

Manual fix that works: `tmux set -g mouse off \; set -g mouse on \;
refresh-client` (re-emits mouse-enable sequences, clears the stuck state);
detach+reattach also works.

Framework config and clients are NOT the cause — `mouse on` and the default
bindings are intact, and the many `control-mode` clients are legit (one per live
monitor/minimonitor/applink TUI).

## Key constraint (drives the whole UX)

**While wedged, the keyboard cannot be directed to the minimonitor** (its pane
can't become active). The ONLY input channel that reaches the minimonitor is the
**forwarded mouse click**. Therefore the on-demand fix MUST be a **clickable
widget/button inside the minimonitor**, NOT a key binding. (A keyboard `M`
binding would land on the agent pane — useless here.)

## Detection heuristic

Interaction-driven (no idle polling; naturally scoped to "user is clicking the
minimonitor"):

- The minimonitor knows its own pane id (`$TMUX_PANE`).
- On a Textual mouse-click event, after a short debounce (~150-250ms, to clear the
  select-pane race), query `tmux display -p -t $TMUX_PANE '#{pane_active}'`.
- **Normal:** click -> pane becomes active (`1`). **Wedged:** click received but
  `pane_active=0` (another pane still active).
- Require **2-3 consecutive** clicked-but-not-active hits before concluding (avoid
  false positives). Reset the counter the moment a click DOES yield active=1.

Blind spot to document: the minimonitor only catches the wedge when the user
clicks the minimonitor itself (it can't observe dead status-bar/right-click). That
is acceptable — that's exactly when the user is trying to use it.

## Remediation UX (recommended scope)

1. **Advisory banner + clickable reset (primary, on-demand).** On confirmed
   detection, render a clickable banner/button in the minimonitor:
   "Mouse focus wedged — click to reset". Clicking it (mouse works) runs the reset.
2. **Reset action** (via the tmux gateway, NOT raw tmux):
   - Full reset: `set -g mouse off` -> `set -g mouse on` -> `refresh-client`.
   - Then optionally `select-pane -t $TMUX_PANE` so focus lands on the minimonitor
     the user just clicked. (Note: a programmatic `select-pane` is NOT a mouse
     event, so it should work even while the mouse bindings are wedged — consider a
     two-step remedy: lightweight `select-pane` to grab focus, full mouse toggle to
     clear the stuck drag globally.)
3. **Opt-in auto-reset (off by default).** A config flag (e.g.
   `minimonitor_auto_reset_mouse: false`) that auto-applies the reset on
   high-confidence detection. MUST be gated to **only the active minimonitor** and
   **rate-limited** (<=1 / 10s) to avoid a thundering herd across the several
   minimonitors/monitor a user typically has open, and because the mouse toggle is
   a **global/server-wide** side effect (affects all sessions). Default off because
   of that global side effect + false-positive flap risk.

## Risk notes (settled during design discussion)

- The reset is **global** (`mouse` is a server option — no per-client reset), so it
  briefly toggles mouse for every session/client. Brief/harmless single-user, but
  it's why auto-mode is opt-in.
- Detection is safe (read-only); acting automatically + globally is where the risk
  is — hence on-demand-click is the recommended default.

## Conventions / implementation notes

- Edits `.aitask-scripts/monitor/minimonitor_app.py`. **Read
  `aidocs/framework/tui_conventions.md` and `aidocs/framework/tmux_gateway.md`
  first.** All tmux calls (display/show-options/set/refresh-client/select-pane)
  MUST go through the sanctioned gateway (`lib/tmux_exec.py` / the minimonitor's
  existing `self._monitor.tmux_run`), never raw `tmux` (enforced by
  `tests/test_no_raw_tmux.sh`).
- Reuse the minimonitor's existing pane-id / `tmux_run` plumbing (see
  `_find_sibling_pane_id`, `_focus_sibling_pane`).

## Acceptance criteria

- Unit test for the detection heuristic (clicked-but-not-active, debounce +
  N-consecutive confirmation, counter reset on success) with the tmux query mocked.
- The reset action is a clickable widget reachable by **mouse only** (verify it
  does not depend on keyboard focus / the pane being active).
- Auto-reset is off by default; when enabled it is active-pane-scoped and
  rate-limited.
- No raw-tmux usage (passes `tests/test_no_raw_tmux.sh`).
- A manual-verification note for the live wedge -> click-to-reset flow (hard to
  unit-test the real wedge).

## Reference
- Live diagnosis session 2026-06-25 (this troubleshooting). The wedge signature,
  the working reset command, and the keyboard-unreachable constraint were all
  confirmed empirically on tmux 3.6b under Hyprland.
