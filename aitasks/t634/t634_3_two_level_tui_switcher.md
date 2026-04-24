---
priority: medium
effort: high
depends: [t634_1]
issue_type: feature
status: Implementing
labels: [tmux, tui_switcher]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-23 20:21
updated_at: 2026-04-24 11:15
---

## Context

Child of t634. Extend the TUI switcher overlay (`j` in most aitasks TUIs) so that when multiple aitasks tmux sessions are detected on the current server, the user can first pick a **session**, then pick a **window** within it. Selecting a window in another session teleports the attached tmux client to that window. Depends on t634_1 for `discover_aitasks_sessions()`.

Parallel to t634_2 (monitor) — no ordering dependency between _2 and _3 after _1 is done.

## Key Files to Modify

- `.aitask-scripts/lib/tui_switcher.py` — add session-picker state, render a top-row session selector when `>= 2` aitasks sessions exist, swap the ListView contents when the browsed session changes.
- `aitasks/metadata/project_config.yaml` (runtime) + `seed/project_config.yaml` — document `tmux.switcher.multi_session` config key.
- `website/content/docs/...` — user-facing doc for the feature (current-state only).
- `tests/test_tui_switcher_multi_session.py` — coverage for browsed-vs-current-session semantics.

## Reference Files for Patterns

- `.aitask-scripts/lib/tui_switcher.py:TuiSwitcherScreen` — the existing single-level switcher. `compose()` builds the TUI/Agent/Other groups; `on_mount()` populates them. Multi-session layout adds a horizontal session row above.
- `.aitask-scripts/lib/tui_switcher.py:_switch_to` — the current "run tmux to select or create window" path. For cross-session teleport, add a branch that routes through `switch_to_pane_anywhere(...)`-style logic (but using window id, not pane id — see Implementation Plan below).
- `.aitask-scripts/lib/tui_switcher.py:action_shortcut_*` — the keyboard shortcuts (`b`, `m`, `c`, `s`, `t`, `r`, `g`, `x`, `n`). **These MUST stay bound to the current session**, never the browsed session. Critical UX rule — see Gotchas.

## Implementation Plan

### Step 1 — Session enumeration on open

On `TuiSwitcherScreen.on_mount`:

```python
sessions = discover_aitasks_sessions()
self._all_sessions = sessions
self._current_session = _current_tmux_session()  # already exists
self._browsed_session = self._current_session
self._multi_mode = config_enabled and len(sessions) >= 2
```

If `_multi_mode` is False, render today's single-session layout.

If `_multi_mode` is True, render:

1. Top row: `Session: [*aitasks] aitasks_mob aitasks_cli` (current marked with `*`; browsed marked with background highlight).
2. ListView below shows windows from `_browsed_session` (using `get_tmux_windows(_browsed_session)` — already uses exact-match from t632).
3. Footer hint: `Left/Right cycle sessions · Enter switch · Shortcuts act on current session`.

### Step 2 — Session cycling bindings

Add `Binding("left", "prev_session", show=False, priority=True)` and `Binding("right", "next_session", show=False, priority=True)` to the switcher. Handlers update `_browsed_session` and repopulate the ListView.

**Priority binding guard** (see CLAUDE.md) — use `self.screen.query_one(...)` not `self.query_one(...)` to scope the guard to this screen. On miss, raise `textual.actions.SkipAction`.

### Step 3 — Cross-session Enter

In `_switch_to(name, running, window_index=None)`:

```python
if self._browsed_session != self._current_session:
    # Teleport path
    if running:
        subprocess.Popen(["tmux", "switch-client", "-t",
                          tmux_session_target(self._browsed_session)])
        subprocess.Popen(["tmux", "select-window", "-t",
                          tmux_window_target(self._browsed_session,
                                             window_index or name)])
    else:
        # Create the window in the browsed session, THEN teleport
        subprocess.Popen(["tmux", "new-window", "-t",
                          tmux_window_target(self._browsed_session, ""),
                          "-n", name, cmd])
        subprocess.Popen(["tmux", "switch-client", "-t",
                          tmux_session_target(self._browsed_session)])
else:
    # Today's same-session path — unchanged
    ...
```

### Step 4 — Shortcut keys stay on current session

The action_shortcut_* methods iterate self._running_names (the CURRENT session's windows, captured at compose time) and launch via the existing same-session path. They must NOT read `_browsed_session`. Add a code comment referencing this task so future editors don't "fix" the asymmetry.

### Step 5 — Minimonitor propagation

`maybe_spawn_minimonitor(session, window_name)` is per-session; when the switcher creates a window in a browsed session, the companion spawn must target that browsed session. The existing helper already accepts any session — pass `self._browsed_session` in the teleport path.

### Step 6 — Config

Add `tmux.switcher.multi_session: bool` (default false) to `project_config.yaml`. Independent from `tmux.monitor.multi_session` so users can opt into one without the other.

Consider a single umbrella `tmux.multi_session: bool` that enables both subsystems, with per-subsystem overrides. Prefer per-subsystem flags for clarity; add the umbrella only if a real use case emerges.

## Verification

Automated:

- Unit: mock `discover_aitasks_sessions` to return 2 fake sessions; construct `TuiSwitcherScreen`; assert `_multi_mode=True` and the session row widget is in the compose tree.
- Unit: with `_browsed_session` set to a non-current session, call `_switch_to("board", running=True, window_index="2")` and assert the subprocess calls include `switch-client` + `select-window` with `=<browsed>:2`.
- Unit: with `_browsed_session == _current_session`, same call takes today's single-session path (no `switch-client`).
- Unit: shortcut `action_shortcut_board()` launches into `_current_session`, NOT `_browsed_session`, regardless of the browsed state.
- Regression: with exactly 1 discovered session, UI and behavior are bit-identical to today.

Manual (aggregate sibling of t634):

- Two projects side-by-side. `tmux.switcher.multi_session: true` in both. Open switcher in project A via `j`. Top row shows both sessions. Left/Right cycle. Enter on a B-window teleports. Shortcut `b` from A's switcher opens `board` in A, not B.
- Verify `n` (new task) creates the window in the current session, not the browsed.
- Verify single-session mode (flag off or only 1 session detected) is bit-identical to today's switcher.
- Verify the priority-binding guard: push a modal on top of the switcher and confirm Left/Right in the modal is not consumed by the switcher.

## Gotchas to address during implementation

- **The "shortcut keys stay on current session" rule is the whole UX point.** Break it and users accidentally create windows in whichever session they were browsing. Test this explicitly.
- **Priority binding + App.query_one gotcha** (CLAUDE.md memory) — new Left/Right bindings on the switcher screen will conflict with any pushed dialog that also uses arrow keys. Use `self.screen.query_one(...)` guards and `SkipAction` on miss.
- **Switcher key `n` = create-task** (per CLAUDE.md TUI conventions) — do not repurpose `n` for "next session" or similar. Use Left/Right (or `Tab` / `Shift-Tab`) for session cycling.
- **The switcher is a modal ModalScreen** — dismiss semantics must return consistently. Cross-session Enter should still dismiss the overlay after firing the teleport, just like same-session Enter does today.
- **Session list sort order** — sort by name (current session first, then alphabetical) for stable display. `list-sessions` server order is not stable.
- **Registry timing** — `discover_aitasks_sessions()` may not see a brand-new project's session if `ait ide` hasn't yet populated `AITASKS_PROJECT_<sess>` (see t634_1). This is acceptable: a session with a running TUI window will be detected via pane-cwd anyway.
- **Detaching** — if the user detaches (Ctrl-b d) while the switcher is open, the teleport path tries to `switch-client` on a no-longer-attached client. Wrap in try/except, notify on failure, dismiss the overlay.
