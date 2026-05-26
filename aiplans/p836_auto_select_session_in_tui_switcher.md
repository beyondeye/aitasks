---
Task: t836_auto_select_session_in_tui_switcher.md
Base branch: main
plan_verified: []
---

# t836 — Auto-select session in TUI switcher

## Context

In `ait monitor` and `ait minimonitor`, pressing `j` opens the TUI switcher
overlay (`TuiSwitcherOverlay`). Today the overlay always opens with its
selected/operating session (`_session`) equal to the **attached** tmux
session — what `tmux display-message #S` reports for the user's client.

When the user is running multiple aitasks sessions and has highlighted (in
the monitor's pane list) a code-agent that lives in a different tmux
session, opening the switcher still pre-selects the attached session
instead of the agent's session. The user then has to press `→` to cycle
sessions before any shortcut/action lands on the right session.

Goal: when the focused row in `monitor` / `minimonitor` is a code-agent
pane belonging to session **A**, the switcher must open with session **A**
already selected (i.e. `_session = A`, while `_attached_session` remains
the actual client session — so the existing teleport logic and `▶`
attached-marker still work).

Single-session and non-agent-focus cases must remain bit-identical to
today.

## Approach

`TuiSwitcherOverlay` already has the right shape: `_session` is the
*selected/operating* session and `_attached_session` is the *client*
session. The constructor currently collapses them to one value. We add a
new optional `selected_session` parameter, and a hook on the mixin that
monitor / minimonitor override to supply the focused agent's session.

### Files to modify

#### 1. `.aitask-scripts/lib/tui_switcher.py`

**`TuiSwitcherOverlay.__init__`** — accept an extra optional
`selected_session: str | None = None`. Keep the existing `session` arg as
the *attached* session.

```python
def __init__(
    self,
    session: str,
    current_tui: str = "",
    selected_session: str | None = None,
) -> None:
    super().__init__()
    # _session is the OPERATING / SELECTED session ...
    self._session = selected_session or session
    # _attached_session is the tmux client's current session ...
    self._attached_session = session
    ...
```

No other field needs to change here. The existing multi-state init,
session-row render, cycle-session logic, and `_teleport_if_cross` already
treat `_session` and `_attached_session` as separate concepts — they just
happen to start equal today.

**Sanity-fallback in `_init_multi_state`**: if `self._session` is not in
the discovered `sessions` list (e.g. caller passed a name that died
between focus and overlay push), reset `self._session = self._attached_session`.
This keeps `_cycle_session`'s `names.index(self._session)` from raising
and the session-row `▶`/`[reverse]` markers consistent.

```python
def _init_multi_state(self, sessions: list[AitasksSession]) -> None:
    self._all_sessions = sessions
    self._multi_mode = (
        len(sessions) >= 2
        and any(s.session == self._attached_session for s in sessions)
    )
    if sessions and not any(s.session == self._session for s in sessions):
        self._session = self._attached_session
```

**`TuiSwitcherMixin`** — add a hook the subclasses can override, and call
it from `action_tui_switcher`:

```python
class TuiSwitcherMixin:
    SWITCHER_BINDINGS = [...]

    def _switcher_selected_session(self) -> str | None:
        """Override in subclasses to pre-select a non-attached session.

        Return None to use the attached session (default behavior).
        """
        return None

    def action_tui_switcher(self) -> None:
        if not os.environ.get("TMUX"):
            self.notify("TUI switcher requires tmux", severity="warning")
            return
        session = _detect_current_session()
        if session is None:
            defaults = load_tmux_defaults(Path.cwd())
            session = defaults.get("default_session", "aitasks")
        current = getattr(self, "current_tui_name", "")
        selected = self._switcher_selected_session()
        self.push_screen(TuiSwitcherOverlay(
            session=session,
            current_tui=current,
            selected_session=selected,
        ))
```

#### 2. `.aitask-scripts/monitor/monitor_app.py`

Override the hook on `MonitorApp` to return the focused agent pane's
session when the focused row is an agent card:

```python
def _switcher_selected_session(self) -> str | None:
    pid = self._focused_pane_id
    if not pid:
        return None
    snap = self._snapshots.get(pid)
    if snap is None:
        return None
    if snap.pane.category != PaneCategory.AGENT:
        return None
    sess = snap.pane.session_name
    return sess or None
```

Place it near the other action helpers (e.g. just above
`action_tui_switcher` would be inherited; place this near the focus-
tracking helpers around line ~900). Only AGENT-category panes trigger the
override — non-agent rows (TUIs, "other") fall through to the default
attached-session behavior, matching the task wording ("if the selected
coding agent (if any is selected)").

#### 3. `.aitask-scripts/monitor/minimonitor_app.py`

Add the same hook. Minimonitor only shows AGENT panes
(`_rebuild_pane_list` filters to `PaneCategory.AGENT`), so the category
check is mostly defensive but still appropriate:

```python
def _switcher_selected_session(self) -> str | None:
    pid = self._get_focused_pane_id()
    if not pid:
        return None
    snap = self._snapshots.get(pid)
    if snap is None or snap.pane.category != PaneCategory.AGENT:
        return None
    sess = snap.pane.session_name
    return sess or None
```

(`_get_focused_pane_id()` already exists on `MiniMonitorApp` and reads
the currently focused `MiniPaneCard`.)

### Why a hook on the mixin, not custom `action_tui_switcher` overrides

Both monitor TUIs reach the switcher through the inherited
`TuiSwitcherMixin.action_tui_switcher`. Duplicating the whole mixin body
in each subclass just to swap one line would force any future change to
mixin (e.g. CSS, fallback session resolution, new args) to be made in
three places. The hook keeps the orchestration in one place and lets each
subclass answer one focused question.

## Tests

Existing test file `tests/test_tui_switcher_multi_session.sh` already
covers `_init_multi_state`, `_cycle_session`, and `_switch_to` behavior.
Extend it (Tier-1 logic-level Python block) with cases:

- `make_overlay(session="s1", selected_session="s2")` →
  `_session == "s2"`, `_attached_session == "s1"`.
- `make_overlay(session="s1")` (no `selected_session`) → behaves as
  today: `_session == _attached_session == "s1"`.
- After `_init_multi_state([sess("s1"), sess("s3")])` with
  `_session="s2"` (unknown to the discovered list): `_session` is reset
  to `_attached_session`.
- `TuiSwitcherMixin._switcher_selected_session()` default returns `None`.

No new dedicated test for `MonitorApp._switcher_selected_session` /
`MiniMonitorApp._switcher_selected_session` is needed at the unit level
beyond the existing test patterns — the hook is a 5-line read from
`self._snapshots`. Manual verification (below) covers the integrated
behavior.

## Verification

Manual (multi-session; requires two aitasks tmux sessions):

1. Start two aitasks tmux sessions, each with a code-agent window
   (e.g. `aitasks` and a second `aitasks-foo` from a registered project).
2. Attach to session `aitasks` and run `ait monitor` in multi-session
   mode (`M` to toggle if needed). Confirm both sessions' agents appear
   in the pane list.
3. Use Up/Down to focus an agent card belonging to `aitasks-foo`. Press
   `j`. **Expected:** the switcher opens with `Session: ▶ aitasks   [reverse]aitasks-foo[/]`
   — i.e. the `▶` marker is on `aitasks` (attached), but `aitasks-foo` is
   the reversed/selected one. Shortcut keys (e.g. `b`) act on
   `aitasks-foo` and trigger a `switch-client` teleport.
4. Focus an agent card in the attached `aitasks` session. Press `j`.
   **Expected:** identical to today — `aitasks` is both attached and
   selected.
5. Single-session sanity: kill all but the attached aitasks session.
   Repeat — the session row stays hidden (`display=False`); behavior is
   bit-identical to current.
6. Repeat steps 2–4 with `ait minimonitor` instead.

Tests:

```bash
bash tests/test_tui_switcher_multi_session.sh
bash tests/test_tui_switcher_footer_fit.sh
bash tests/test_tui_switcher_brainstorm_session.sh
```

(The latter two should be unaffected; running them guards against
regressions in the multi-state init path.)

Linting:

```bash
shellcheck .aitask-scripts/aitask_*.sh   # untouched by this task, but free
```

## Step 9 reference

After approval and implementation, follow the shared workflow's Step 9
(post-implementation): commit code + plan separately, archive via
`./.aitask-scripts/aitask_archive.sh 836`, push.
