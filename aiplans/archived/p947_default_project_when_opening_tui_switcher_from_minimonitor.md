---
Task: t947_default_project_when_opening_tui_switcher_from_minimonitor.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Default TUI-switcher project to the followed agent in minimonitor (t947)

## Context

When you press `j` to open the TUI switcher from `ait minimonitor`, the
switcher opens with an initially-selected project/repo tmux context. That
default is meant to save the user a Left/Right cycle to reach the project they
care about (t836).

Today the minimonitor derives that default from
`_switcher_selected_session()` (`minimonitor_app.py:702`), which returns the
session of the **focused general-list card** — whichever agent row currently
has keyboard focus. This is wrong for the minimonitor's UX: the minimonitor is
a companion pane that *follows one specific agent* (its own-window agent), and
since t944 that followed agent is shown in a **separate, static, unselectable
docked panel** (`#mini-own-agent`) — it is no longer even in the focusable
general list. The general-list cards are *other* agents the user is merely
glancing at. Keying the switcher's default project off the transiently-focused
card gives an unpredictable / wrong initial project.

The task asks: when opening the switcher from the minimonitor, default the
selected project to the one belonging to the **followed agent** (the docked
panel's agent), not the currently-focused list card.

## How the value flows (verified)

`MiniMonitorApp._switcher_selected_session()` →
`TuiSwitcherMixin.action_tui_switcher()` (`tui_switcher.py:1131`) passes it as
`selected_session=` → `TuiSwitcherOverlay.__init__` sets `self._session =
selected_session or session` (`tui_switcher.py:455`) →
`_project_root_for_session()` (`tui_switcher.py:487`) resolves the initial
project root / desync context. So changing the returned session is sufficient
to change the switcher's default project; no switcher-side change is needed.

The followed agent is already resolvable via the existing helper
`_find_own_agent_snapshot()` (`minimonitor_app.py:372`), which matches the
AGENT pane sharing this minimonitor's tmux window, scoped to the own session
(returns `None` when no followed agent is detected). It is the same helper used
by the docked panel (`_maybe_build_own_agent_panel`), the kill (`k`) and next
(`n`) actions — so reusing it keeps "what the switcher defaults to" consistent
with "what the docked panel shows".

## Change

**File: `.aitask-scripts/monitor/minimonitor_app.py`** — rewrite
`_switcher_selected_session()` (lines 702–717) to resolve from the followed
agent instead of the focused card:

```python
def _switcher_selected_session(self) -> str | None:
    """Pre-select the followed agent's session in the TUI switcher.

    The minimonitor follows one specific agent — the one sharing its tmux
    window, shown in the static, unselectable docked panel
    (``#mini-own-agent``). The switcher should open with *that* agent's
    project as the default, not whichever general-list card happens to be
    focused: the focused card cycles as the user navigates and is an agent
    the user is only glancing at, so keying the default project off it gave
    an unpredictable initial selection (t947). Returns ``None`` (attached
    session) when no followed agent is detected.
    """
    snap = self._find_own_agent_snapshot()
    if snap is None:
        return None
    return snap.pane.session_name or None
```

Notes:
- The category check in the old body is dropped because
  `_find_own_agent_snapshot()` already filters on
  `category == PaneCategory.AGENT`.
- `_get_focused_pane_id()` is no longer used by this method; it remains used
  elsewhere (e.g. `on_descendant_focus`), so nothing else changes.
- Empty `session_name` → `None`, which falls back to the attached session
  (the minimonitor's own session) — the safe, pre-t836 default.

## Tests

**File: `tests/test_multi_session_minimonitor.sh`** — extend the existing
Tier 1g scaffold (it already builds an app via `make_app` with a followed
agent `%1` in session `sA` window 1, and another agent `%2` in window 2). Add
a small "Tier 1h" block asserting `_switcher_selected_session()`:

- returns the **followed** agent's session (`"sA"`), driven by
  `_find_own_agent_snapshot()` and independent of any focused card;
- returns `None` when there is no followed agent (`app._own_window_index =
  None`).

The `make_app` helper and `mk_snap` builder already in the file are reused;
add matching `assert_contains` lines alongside the existing Tier 1g asserts.

## Risk

### Code-health risk: low
- Single-method rewrite that delegates to an existing, well-tested helper
  (`_find_own_agent_snapshot`); blast radius is one method in one TUI, no
  switcher-side or cross-session changes · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- The value flow from `_switcher_selected_session` to the switcher's initial
  project is verified end-to-end; the followed-agent helper is the exact
  source the task names ("the separate unselectable pane") · severity: low ·
  → mitigation: TBD

## Verification

1. Run the unit/integration test for the minimonitor:
   ```bash
   bash tests/test_multi_session_minimonitor.sh
   ```
   Expect all asserts (including the new Tier 1h) to PASS.
2. (Manual, optional) In a multi-window tmux session with two agents, launch
   `ait minimonitor` in one agent's window. Focus a *different* agent's card
   in the general list, press `j` — the switcher should open with the
   **followed** (own-window, docked) agent's project selected, not the
   focused card's project.

## Post-Implementation

Follow Step 9 (Post-Implementation) of the task-workflow: commit code and plan
separately, then archive task t947.

## Final Implementation Notes

- **Actual work done:** Rewrote `MiniMonitorApp._switcher_selected_session()`
  (`.aitask-scripts/monitor/minimonitor_app.py`) to resolve the switcher's
  default session from `_find_own_agent_snapshot()` (the followed/docked agent)
  instead of `_get_focused_pane_id()` (the focused general-list card). Dropped
  the now-redundant `PaneCategory.AGENT` check since the helper already filters
  on it. Added a "Tier 1h" test block to
  `tests/test_multi_session_minimonitor.sh` asserting the default keys off the
  followed agent (independent of focus) and returns `None` when no followed
  agent exists.
- **Deviations from plan:** None. Implemented exactly as planned.
- **Issues encountered:** None. The value flow (`_switcher_selected_session` →
  `selected_session` → `TuiSwitcherOverlay._session` →
  `_project_root_for_session`) was confirmed during planning; no switcher-side
  change was needed.
- **Key decisions:** Reused the existing `_find_own_agent_snapshot()` helper
  rather than introducing new resolution logic, keeping the switcher default
  consistent with the docked-panel agent shown by `_maybe_build_own_agent_panel`
  and the `k`/`n` actions.
- **Upstream defects identified:** None.
