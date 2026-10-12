---
Task: t1953_switcher_agent_dialogs_target_selected_session.md
Base branch: main
Output branch: main
---

# t1953 — Switcher agent dialogs target the selected session

## Context

In the TUI switcher (`j`), Left/Right selects another aitasks session, and every
direct launch (`_switch_to`, git, fire-and-forget explore, create) targets that
selected session (`self._session`) and then teleports the client there with
`_teleport_if_cross`. Two actions go through the shared `AgentCommandScreen`
dialog instead — `action_shortcut_explore_pick` (`X`) and
`action_shortcut_agent` (`e`) — and lose the selection:

1. The dialog's tmux tab preselects its session via `pick_initial_session`
   (per-project memory → configured `default_session` name if live → first
   live session). The switcher never passes its selected session, so the
   preselection can be another session, even another project's.
2. Neither dialog callback teleports after a successful tmux launch, so the
   agent starts in another session while the client stays put.

Outcome: both dialogs preselect the switcher's selected session, and a
cross-session tmux launch moves the client to the session the user confirmed.

## Implementation

### 1. `.aitask-scripts/lib/agent_command_screen.py`

- `pick_initial_session(sessions, default_from_config, last_for_project,
  explicit_session: str | None = None)` — new keyword arg, checked first:
  `if explicit_session and explicit_session in sessions: return explicit_session`.
  Update the docstring priority list (explicit caller intent → memory → config →
  first live → sentinel). Existing positional callers are unchanged.
- `AgentCommandScreen.__init__`: new kwarg `default_tmux_session: str | None =
  None`, placed next to `default_tmux_window`; store as
  `self._default_tmux_session`.
- Extract the call in `_populate_tmux_tab` into a small seam method so the
  wiring is testable without mounting widgets:
  ```python
  def _initial_session(self, sessions: list[str]) -> str:
      return pick_initial_session(
          sessions,
          self._tmux_defaults.get("default_session"),
          AgentCommandScreen._last_session_by_project.get(self._project_key),
          explicit_session=self._default_tmux_session,
      )
  ```
  `_populate_tmux_tab` calls `self._initial_session(sessions)`. The initial
  window list already flows from `initial_session` into
  `_compute_window_options(initial_session)`, so no change is needed there.
- No other caller passes the new kwarg (board, codebrowser, monitor,
  minimonitor, trails, syncer, `build_pick_screen`) → behaviour unchanged.

### 2. `.aitask-scripts/lib/tui_switcher.py`

- `_teleport_if_cross(self, session: str | None = None)`: target is
  `session or self._session`; no-op when the target equals
  `self._attached_session`; otherwise the same best-effort
  `switch-client -t tmux_session_target(target)`. Docstring updated. Existing
  no-arg callers keep their behaviour.
- `action_shortcut_explore_pick` and `action_shortcut_agent`: pass
  `default_tmux_session=self._session` to `AgentCommandScreen(...)`.
- In both `on_result` callbacks, TmuxLaunchConfig branch: after a launch with
  no `err` (after the minimonitor spawn), call
  `self._teleport_if_cross(result.session)` — `result.session` is what the user
  confirmed, not `self._session`. Skip it when `result.new_session`:
  `launch_in_tmux` already issues `switch-client` to a newly created session
  (`agent_launch_utils.py` new-session branch), so a second switch is redundant.
  Wrap in the same `(FileNotFoundError, OSError)` tolerance the helper already
  has (it swallows internally, so no extra try is needed).

## Verification

Tests (new cases in existing files):

- `tests/test_agent_command_dialog_default_session.py` (`PickInitialSessionTests`):
  - explicit session wins over memory and config when live;
  - explicit session not live → falls back to memory/config/first unchanged;
  - `None`/empty explicit → identical to today (existing cases stay green).
  - Screen seam: construct `AgentCommandScreen(..., default_tmux_session="s2")`
    with a remembered `_last_session_by_project` entry of `"s1"`, assert
    `_initial_session(["s1","s2"]) == "s2"`; and a screen without the kwarg
    keeps returning the remembered `"s1"` (negative control). Save/restore the
    class-level dict as `PickInitialWindowTests` does.
  - **Mounted-dialog wiring test** (new class, same file) — proves
    `_populate_tmux_tab` actually uses the resolved session for the displayed
    selector and the initial window lookup, so the two seam tests above cannot
    pass with the wiring disconnected. Reuse the harness shape of
    `tests/test_agent_command_open_debounce.py` (`_DialogHost` App pushing the
    real screen, `app.run_test(size=(120, 40))`, two `pilot.pause()`s) with
    patches on `acs.is_tmux_available` (True), `acs.get_tmux_sessions`
    (`["s1", "s2"]`), `acs.load_tmux_defaults` (`default_session: "s1"`), and a
    recording `acs.get_tmux_windows` returning per-session windows
    (`s1 → [("0","s1win")]`, `s2 → [("0","s2win")]`). Also seed
    `_last_session_by_project[<root>] = "s1"` (saved/restored), so both the
    memory and the config point at s1. Cases:
    - `default_tmux_session="s2"` → `#tmux_session_select` value is `"s2"`, the
      first `get_tmux_windows` call is for `"s2"`, and `#tmux_window_select`'s
      options include `"0: s2win"` and not `"0: s1win"`;
    - negative control, no kwarg → selector `"s1"`, windows from `s1`;
    - `default_tmux_session="gone"` (not live) → falls back to `"s1"`.
- `tests/test_tui_switcher_agent_launch.py`:
  - both dialog paths (`action_shortcut_agent`, `action_shortcut_explore_pick`)
    construct the screen with `_default_tmux_session` equal to the selected
    session (overlay `session="s1"`, `_selected_key="s2"` → `"s2"`);
  - with `_TMUX` patched: a cross-session result
    (`TmuxLaunchConfig("s2", …, new_window=True)`, attached `s1`) issues exactly
    one `switch-client -t =s2`; the target follows `result.session` even when it
    differs from the selected session (user changed it in the dialog);
  - same-session result → no `switch-client`; launch error → no
    `switch-client`; `new_session=True` → no extra `switch-client`.
- Existing: `bash tests/test_tui_switcher_multi_session.sh` (no-arg
  `_teleport_if_cross`), `tests/test_pick_command_screen.py` (golden unchanged),
  then `bash tests/run_all_python_tests.sh` and check the final verdict line.

## Post-implementation

Step 9 of the task workflow (review, commit, archival). Current-branch mode — no
worktree/merge.

## Risk

### Code-health risk: low
- Signature growth on two widely used helpers (`pick_initial_session`, `AgentCommandScreen.__init__`, `_teleport_if_cross`) · severity: low · → mitigation: none — keyword args defaulting to None; existing callers and the `build_pick_screen` golden are untouched and covered by existing tests.

### Goal-achievement risk: low
- A cross-session *split* into a non-active window teleports to the session, landing on its active window rather than the split window · severity: low · → mitigation: none — identical to a same-session split today and to `_teleport_if_cross` semantics the task asks to reuse; new-window launches select the new window, so the main path lands correctly.
