---
Task: t944_kill_and_next_command_for_minimonitor.md
Worktree: (none — working on current branch, profile 'fast')
Branch: main
Base branch: main
---

# t944 — Kill & Next commands for the minimonitor, plus separated "followed agent" display

## Context

`ait minimonitor` runs as a narrow side-pane *inside an agent's own tmux
window*. Today it lists **all** code-agent panes in one flat list, including the
agent it is actually attached to — with no visual sign of which one that is. It
also lacks the `k`(ill) and `n`(ext sibling) actions that the full `ait monitor`
offers.

This task does two things:

1. **Separate the followed agent from the general list** — show the agent that
   shares the minimonitor's window in a dedicated **docked panel** at the top
   (fixed, non-scrolling), and remove it from the scrolling general list below.
2. **Add `k` (kill) and `n` (next sibling)** to the minimonitor, scoped
   **only** to the followed agent (never the focused card in the general list),
   mirroring the full monitor's behavior.

Decisions confirmed with the user:
- Followed-agent UI = **docked panel above the list**.
- Next-sibling kill heuristic = **mirror the full monitor** (kill current only
  when it is a parent-split-into-children / Done / archived task).

## Key architectural facts (from exploration)

- The followed agent = the `PaneCategory.AGENT` snapshot whose
  `pane.window_index == self._own_window_index` and `pane.session_name in ("", self._session)`.
  Minimonitor already uses this match in `_auto_select_own_window()`
  (`minimonitor_app.py:348`).
- `kill_agent_pane_smart()` (`tmux_monitor.py:694`) treats the minimonitor as a
  *companion process*, so killing the followed agent (the only non-companion
  pane in the window) collapses the **whole window** — taking the minimonitor
  with it. This is the natural/expected outcome of killing your followed agent.
- The kill dialog `KillConfirmDialog` already lives in `monitor_shared.py:489`
  (already importable). The next-sibling dialogs `NextSiblingDialog`,
  `_SiblingRow`, `ChooseSiblingModal` currently live in `monitor_app.py:265-454`.
- Sibling-resolution helpers `find_next_sibling`, `find_ready_siblings`,
  `get_parent_id` are methods on `TaskInfoCache` (`monitor_shared.py`) — already
  reachable via `self._task_cache`.
- Launch helpers `resolve_dry_run_command`, `resolve_agent_string`,
  `TmuxLaunchConfig`, `launch_in_tmux`, `maybe_spawn_minimonitor`
  (`agent_launch_utils.py`) and `AgentCommandScreen`, `resolve_skill_profile`
  (`agent_command_screen.py`) are the public launch surface the full monitor
  uses; the minimonitor will import the same ones.
- New `k`/`n` bindings auto-register under the `minimonitor` scope via
  `register_app_bindings()` in `ShortcutsMixin` — **no manual edits** to the
  keybinding registry are needed. `test_shortcuts_registry_coverage.sh` validates
  this.

## Implementation

### 1. Shared-dialog refactor — `monitor_shared.py` + `monitor_app.py`

Move `NextSiblingDialog`, `_SiblingRow`, and `ChooseSiblingModal` from
`monitor_app.py` into `monitor_shared.py` (next to the already-shared
`KillConfirmDialog`). This is a pure cut/paste — every dependency they use
(`Container`, `VerticalScroll`, `Button`, `Static`, `Binding`, `ModalScreen`,
`ComposeResult`) is already imported in `monitor_shared.py:23-27`.

- In `monitor_app.py`, delete the three class definitions and import them from
  `monitor_shared` instead (extend the existing
  `from monitor.monitor_shared import (...)` block at line 34).
- Verify no other references break (`grep NextSiblingDialog|ChooseSiblingModal|_SiblingRow`).

### 2. Minimonitor — `monitor/minimonitor_app.py`

**Imports** — add:
- From `monitor_shared`: `KillConfirmDialog`, `NextSiblingDialog`,
  `ChooseSiblingModal`.
- From `agent_launch_utils`: `resolve_dry_run_command`, `resolve_agent_string`,
  `TmuxLaunchConfig`, `launch_in_tmux`, `maybe_spawn_minimonitor`.
- From `agent_command_screen`: `AgentCommandScreen`, `resolve_skill_profile`.

**State** — store `self._project_root = project_root` in `__init__` (currently
only passed to `TaskInfoCache`); add a `_root_for_snap(snap)` helper mirroring
`monitor_app.py:873` (session→project mapping, fallback `self._project_root`).

**Bindings** — add to `BINDINGS`:
```python
Binding("k", "kill_own_agent", "Kill", show=False),
Binding("n", "pick_next_for_own", "Next", show=False),
```

**Layout** — in `compose()`, insert a docked panel between the session bar and
the pane list:
```python
yield Static(id="mini-session-bar")
yield VerticalScroll(id="mini-own-agent")   # docked top, fixed
yield VerticalScroll(id="mini-pane-list")
yield Static(... hints ..., id="mini-key-hints")
```
CSS: `#mini-own-agent { dock: top; height: auto; background: $boost; border-bottom: solid $primary; }`
plus a `.mini-own-header` style for the `── this agent ──` label.

**Card-text helper** — extract the inline card-text construction in
`_rebuild_pane_list` (lines ~445-474: dot, compare-mode glyph, truncated name,
status, optional task-title line) into `_agent_card_text(snap) -> str`, reused
by both the panel and the list.

**Followed-agent resolution** — add:
```python
def _find_own_agent_snapshot(self) -> PaneSnapshot | None:
    if not self._own_window_index:
        return None
    for snap in self._snapshots.values():
        if (snap.pane.category == PaneCategory.AGENT
                and snap.pane.window_index == self._own_window_index
                and snap.pane.session_name in ("", self._session)):
            return snap
    return None
```

**Panel rebuild** — add `_rebuild_own_agent_panel()` (async): clears the panel,
mounts a `[dim]── this agent ──[/]` header plus either a focusable
`MiniPaneCard` built from `_agent_card_text(own_snap)` or a
`[dim]no followed agent[/]` placeholder when none is detected.

**List exclusion** — in `_rebuild_pane_list`, exclude the followed agent's
`pane_id` from the general list so it shows only the *other* agents.

**Refresh wiring** — in `_refresh_data`, call `_rebuild_own_agent_panel()`
before `_rebuild_pane_list()`; keep focus restoration after both.

**Navigation/focus** — add `_all_cards()` returning
`[own panel card?] + [list cards]` in order; use it in `_nav` and
`_restore_focus`. Repoint `_auto_select_own_window()` to focus the docked
own-agent card (fallback: first list card). This keeps `i`/`d`/`s` working on
whatever card is focused (own or other) — no regression of existing per-card
actions.

**Kill action** (own agent only):
```python
def action_kill_own_agent(self):
    snap = self._find_own_agent_snapshot()
    if snap is None: notify("No followed agent in this window", warning); return
    task_info = <task_cache lookup by window name + session>
    push_screen(KillConfirmDialog(snap, task_info), callback=self._on_own_kill_confirmed)
```
`_on_own_kill_confirmed`: on confirm, `self._monitor.kill_agent_pane_smart(snap.pane.pane_id)`
— which collapses the window (and exits the minimonitor). Notify on the
non-collapse path; no refresh needed when the window goes away.

**Next-sibling action** (own agent only) — mirror `action_pick_next_sibling`
(`monitor_app.py:1794`) but resolve the target from `_find_own_agent_snapshot()`
instead of the focused card:
- `action_pick_next_for_own` → resolve own snap, task_id (notify if none),
  invalidate cache, read current info, `find_next_sibling`, push
  `NextSiblingDialog`.
- `_on_own_next_result` → on `("pick", id)` call `_launch_pick_for_own(id)`;
  on `("choose", parent_id)` push `ChooseSiblingModal(find_ready_siblings(...))`,
  then `_launch_pick_for_own` on selection.
- `_launch_pick_for_own(target_id)` → build `AgentCommandScreen` exactly as the
  full monitor does (operation `pick`, window `agent-pick-<id>`, profile/agent
  string via `resolve_skill_profile`/`resolve_agent_string`,
  root via `_root_for_snap`). **Ordering differs from the full monitor**: because
  killing the current agent collapses the minimonitor's *own* window, the
  callback must **launch first, then kill**:
  ```python
  def on_pick_result(pick_result):
      if isinstance(pick_result, TmuxLaunchConfig):
          launch_in_tmux(screen.full_command, pick_result)          # 1. new window
          if pick_result.new_window:
              maybe_spawn_minimonitor(pick_result.session, pick_result.window)
          is_parent = "_" not in task_id                            # 2. mirror heuristic
          if is_parent or not current_info or current_info.status == "Done":
              self._monitor.kill_agent_pane_smart(own_pane_id)       # collapses our window last
  ```
  (The full monitor kills *before* launch because it lives in a separate window
  and survives; the minimonitor cannot, so it inverts the order.)

**Key hints** — update the `#mini-key-hints` Static to advertise `k:kill` and
`n:next` (keep within the ~40-col width), e.g.:
```
tab:agent  s/↑↓:switch  i:info
k:kill  n:next  enter:send
j:jump  r:refresh  q:quit
m:full monitor  d:detect (≈ strip, = raw)
```

## Files to modify

- `.aitask-scripts/monitor/monitor_shared.py` — receive the 3 moved dialog classes.
- `.aitask-scripts/monitor/monitor_app.py` — remove the 3 classes; import from shared.
- `.aitask-scripts/monitor/minimonitor_app.py` — imports, bindings, layout/CSS,
  card-text helper, followed-agent panel, list exclusion, nav/focus, kill +
  next actions and their launch helpers, key hints.

No keybinding-registry or shortcut-label edits required (auto-registered).

## Verification

- `python -c "import ast; ast.parse(open(f).read())"` for the three edited files
  (quick syntax gate); then import-smoke each module under the repo's venv
  python with `PYTHONPATH` set as the tests do.
- `bash tests/test_shortcuts_registry_coverage.sh` — confirms the new
  `minimonitor` `k`/`n` bindings register and the suite still passes.
- `bash tests/test_kill_agent_pane_smart.sh` — unchanged behavior of the kill
  helper.
- `bash tests/test_multi_session_minimonitor.sh` — minimonitor still classifies/
  counts agents correctly after the display change.
- `shellcheck` is N/A (Python-only change); run the above bash tests instead.
- **Manual (TUI) verification** — launch `ait minimonitor` inside an agent
  window and confirm: (a) the followed agent appears in the docked top panel and
  is absent from the general list; (b) `k` prompts and kills the followed agent
  (window collapses); (c) `n` offers the next sibling / chooser and launches it
  in a new window, killing the current window only per the mirror heuristic;
  (d) `k`/`n` target the followed agent regardless of which general-list card is
  focused. (A manual-verification follow-up task may be offered at Step 8c.)

## Risk

### Code-health risk: medium
- Moving the three next-sibling dialog classes out of `monitor_app.py` into
  `monitor_shared.py` is a cross-file refactor that the full monitor also
  depends on — a missed reference or import would break `ait monitor`. ·
  severity: medium · → mitigation: TBD (covered by import-smoke + the existing
  monitor test suite; no separate task warranted).
- The minimonitor additions are largely additive (new panel, new actions) and
  reuse existing, tested helpers, keeping the blast radius contained. ·
  severity: low · → mitigation: none.

### Goal-achievement risk: low
- Requirements are explicit and both design decisions are user-confirmed; the
  approach mirrors proven full-monitor patterns. The only residual uncertainty
  is interactive TUI behavior (docked-panel focus, launch-then-kill ordering),
  which is validated by manual verification — not a goal-shape risk. · severity:
  low · → mitigation: manual verification at Step 8c.

_No before/after risk-mitigation tasks warranted — the medium code-health risk
is mitigated inline by running the existing monitor test suite + import-smoke._

## Post-implementation

Follows shared workflow Step 8 (user review) → Step 9 (post-implementation,
archival via `aitask_archive.sh 944`). No branch/worktree cleanup (working on
current branch).
