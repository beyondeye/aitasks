---
Task: t634_3_two_level_tui_switcher.md
Parent Task: aitasks/t634_multi_session_tmux_support.md
Sibling Tasks: aitasks/t634/t634_4_minimonitor_multi_session.md, aitasks/t634/t634_5_docs_multi_session_polish.md
Archived Sibling Plans: aiplans/archived/p634/p634_1_discovery_and_focus_primitives.md, aiplans/archived/p634/p634_2_multi_session_monitor.md
Base branch: main
plan_verified: []
---

# p634_3 — Two-level TUI switcher (session → window)

## Context

t634_1 landed the shared primitives (`discover_aitasks_sessions()`, `switch_to_pane_anywhere(pane_id)`, the `AITASKS_PROJECT_<sess>` tmux-env registry populated by `ait ide`). t634_2 consumed them in `ait monitor`. This task extends the modal TUI switcher overlay (`j` in every aitasks TUI) with a two-level UI: when multiple aitasks tmux sessions are detected on the current server, a top row lets the user cycle through sessions with Left/Right; the ListView below shows windows from the selected session; Enter teleports the attached tmux client to a window in the selected session.

**Decisions (user-confirmed, supersede the task description):**

1. **No `tmux.switcher.multi_session` YAML key.** Multi-session layout activates automatically when `discover_aitasks_sessions()` returns ≥ 2 sessions — single-session users see today's UI bit-identically. Matches the shipped t634_2 precedent ("no config key; runtime toggle is the sole control") and avoids a new project_config + seed touchpoint.
2. **Shortcut keys act on the SELECTED (browsed) session, not the attached session.** Task description's Step 4 invariant is reversed: pressing `b` while browsing session B opens `board` in B (creating + teleporting if needed), identical to clicking/pressing Enter on the `board` row in B. The entire overlay operates on one "operating session" that mutates on Left/Right; the attached session is only consulted to decide whether a `switch-client` call is needed.

**Other invariants preserved:**
- **`n` stays bound to "new task"** (CLAUDE.md TUI convention) — session cycling uses Left/Right, not `n`/`p`.
- **Enter / shortcut dismiss the overlay** after firing; matches today's semantics.
- **Single-session path is bit-identical to today.** No session row, no Left/Right behavior, no cross-session branch.

## Key files

- `.aitask-scripts/lib/tui_switcher.py` — the only code file. Add multi-session state + rendering + cross-session teleport to `TuiSwitcherOverlay`. (The class is `TuiSwitcherOverlay`, not `TuiSwitcherScreen` as the task description mislabels it.)
- `tests/test_tui_switcher_multi_session.sh` — new; mirrors `tests/test_multi_session_monitor.sh` layout (bash + inline-python mocks, skip-on-no-tmux Tier 2, `TMUX_TMPDIR` isolation).
- `website/content/docs/tuis/_index.md:28` — extend the existing switcher paragraph with a one-sentence multi-session note. No new page.

No changes to `agent_launch_utils.py`, `project_config.yaml`, `seed/project_config.yaml`, `monitor_app.py`, or `minimonitor_app.py`.

## Reference files / patterns to reuse

- `.aitask-scripts/lib/tui_switcher.py:247` — `TuiSwitcherOverlay.__init__(session, current_tui)` — extend with new attrs.
- `.aitask-scripts/lib/tui_switcher.py:253` — `compose()` — add a `Label` above the ListView for the session row.
- `.aitask-scripts/lib/tui_switcher.py:263` — `on_mount()` — factor body into `_populate_list_for(session)` so Left/Right can recall it.
- `.aitask-scripts/lib/tui_switcher.py:439` — `_switch_to(name, running, window_index)` — add a cross-session teleport branch gated on `self._session != self._attached_session`.
- `.aitask-scripts/lib/agent_launch_utils.py:68` — `AitasksSession` dataclass (imported).
- `.aitask-scripts/lib/agent_launch_utils.py:248` — `discover_aitasks_sessions()` (already sorts by session name).
- `.aitask-scripts/lib/agent_launch_utils.py:29` / `:40` — `tmux_session_target(session)` → `"=sess"`, `tmux_window_target(session, window)` → `"=sess:win"`.
- `.aitask-scripts/board/aitask_board.py:2370-2378` — canonical `SkipAction` guard pattern (`self.screen.query_one(...)` + `raise SkipAction()` on miss). Copy for the Left/Right handlers.

## Implementation plan

### Step 1 — Rename semantics in `TuiSwitcherOverlay.__init__`

The existing attribute `self._session` is read in 10+ places as "the session to operate on" (shortcuts, `_switch_to`, `_launch_git_with_companion`, `action_shortcut_explore`, `action_shortcut_create`). Keep that attribute and its semantics; add `self._attached_session` for the immutable "which session is the tmux client actually attached to" used only to decide whether a `switch-client` is needed.

```python
def __init__(self, session: str, current_tui: str = "") -> None:
    super().__init__()
    # _session is the OPERATING session — what the overlay is currently
    # pointing at. Mutated by Left/Right. All shortcuts, _switch_to, and
    # the git companion launcher read this.
    self._session = session
    # _attached_session is the tmux client's current session — used only
    # to decide whether cross-session teleport (switch-client) is needed.
    self._attached_session = session
    self._current_tui = current_tui
    self._running_names: set[str] = set()          # windows in _session
    # multi-session state
    self._all_sessions: list[AitasksSession] = []
    self._multi_mode: bool = False
```

Callers in `TuiSwitcherMixin.action_tui_switcher` (line 541) pass `session=<current attached>` — already correct. Both attrs start equal.

Import `AitasksSession` and `discover_aitasks_sessions` from `agent_launch_utils` alongside the existing imports at line 38.

### Step 2 — Discover sessions and render session row in `compose`/`on_mount`

**compose() change (`.aitask-scripts/lib/tui_switcher.py:253`):** add a `Label` above the ListView that holds the session row. Always yield it — blank in single-session mode so dialog height stays stable.

```python
def compose(self):
    with Container(id="switcher_dialog"):
        yield Label("TUI Switcher", id="switcher_title")
        yield Label("", id="switcher_session_row")   # populated in on_mount
        yield _WrappingListView(id="switcher_list")
        yield Label(
            "[bold bright_cyan](b)[/]oard  ...  [bold bright_cyan](n)[/]ew task\n"
            "[bold bright_cyan]Enter[/] switch  [bold bright_cyan]←/→[/] session  [bold bright_cyan]j/Esc[/] close",
            id="switcher_hint",
        )
```

CSS: add `#switcher_session_row { text-align: center; padding: 0 0 1 0; color: $text; width: 100%; }` to `DEFAULT_CSS`.

**on_mount() change:** discover sessions, decide `_multi_mode`, delegate list-fill to a new helper `_populate_list_for(session)` so Left/Right can reuse it.

```python
def on_mount(self) -> None:
    sessions = discover_aitasks_sessions()
    self._all_sessions = sessions
    # _multi_mode True iff at least two aitasks sessions exist AND the
    # attached session is one of them. If the overlay was opened from a
    # non-aitasks session (no AITASKS_PROJECT_<sess> + no aitasks pane
    # cwd), fall back to today's single-session view.
    self._multi_mode = (
        len(sessions) >= 2
        and any(s.session == self._attached_session for s in sessions)
    )
    self._render_session_row()
    self._populate_list_for(self._session)
```

**`_render_session_row()`:** one-line summary. The session row shows all aitasks sessions; the attached one is marked with `▶`; the currently-selected (operating) one is reverse-highlighted. In single-session mode the Label stays empty.

```python
def _render_session_row(self) -> None:
    row = self.query_one("#switcher_session_row", Label)
    if not self._multi_mode:
        row.update("")
        return
    parts = []
    for s in self._all_sessions:
        name = s.session
        attached = name == self._attached_session
        selected = name == self._session
        prefix = "▶ " if attached else "  "
        if selected:
            parts.append(f"[reverse]{prefix}{name}[/]")
        else:
            parts.append(f"[dim]{prefix}{name}[/]")
    row.update("Session: " + "  ".join(parts))
```

**`_populate_list_for(session)`:** this is `on_mount`'s original body (lines 263–339), refactored to operate on an arbitrary session:

- Call `list_view.clear()` at the top so Left/Right swaps produce a clean list.
- Call `get_tmux_windows(session)` with the parameter, not `self._session`.
- Populate TUI items, brainstorm items, agents, others — same logic — against `self._running_names` computed for the passed session. (`self._running_names` IS updated on Left/Right; it always reflects the selected session.)
- Restore the first-selectable index as before.

### Step 3 — Left/Right cycle the selected (operating) session

Add two bindings to `TuiSwitcherOverlay.BINDINGS` (line 232):

```python
Binding("left", "prev_session", "Prev session", show=False, priority=True),
Binding("right", "next_session", "Next session", show=False, priority=True),
```

Handlers:

```python
def action_prev_session(self) -> None:
    self._cycle_session(-1)

def action_next_session(self) -> None:
    self._cycle_session(+1)

def _cycle_session(self, step: int) -> None:
    # Priority-binding guard (CLAUDE.md "Priority bindings + App.query_one"):
    # scope the guard to this screen via self.screen.query_one and
    # SkipAction on miss so underlying screens / multi-mode-off states
    # don't have their Left/Right consumed.
    from textual.actions import SkipAction
    try:
        self.screen.query_one("#switcher_list", _WrappingListView)
    except Exception:
        raise SkipAction()
    if not self._multi_mode or len(self._all_sessions) < 2:
        raise SkipAction()
    names = [s.session for s in self._all_sessions]
    try:
        idx = names.index(self._session)
    except ValueError:
        idx = 0
    self._session = names[(idx + step) % len(names)]  # MUTATE — everything else follows
    self._render_session_row()
    self._populate_list_for(self._session)
```

Why the guard: the SkipAction pattern in `aitask_board.py:2371-2378` shows that `priority=True` bindings can be consumed from the wrong screen when the App and a pushed Screen share an action name. Guarding with `self.screen.query_one(...)` scopes the guard to the active screen and `SkipAction` on miss lets the next priority binding fire. This is the CLAUDE.md rule.

### Step 4 — Cross-session teleport in `_switch_to`

Modify `_switch_to` (line 439). Today it uses `self._session` for targeting, which is exactly what we want — `self._session` is the selected session, i.e. the target session for BOTH Enter and shortcut paths. The only new requirement is: after/around issuing `select-window` or `new-window`, if `self._session != self._attached_session`, also issue `switch-client -t =<self._session>` so the tmux client lands there.

**Ordering (per `switch_to_pane_anywhere`'s precedent at `agent_launch_utils.py:332`):** target-window operation first, then `switch-client`. `new-window` by default makes the new window the active window in its session; `select-window -t =<sess>:<win>` sets that session's active window regardless of attachment. Then `switch-client -t =<sess>` teleports the client onto that active window.

```python
def _switch_to(self, name: str, running: bool, window_index: str | None = None) -> None:
    try:
        if running:
            target = tmux_window_target(
                self._session, window_index if window_index else name,
            )
            subprocess.Popen(
                ["tmux", "select-window", "-t", target],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        elif name == "git":
            # _launch_git_with_companion already uses self._session — no change needed.
            self._launch_git_with_companion()
        else:
            cmd = self._get_launch_command(name)
            subprocess.Popen(
                ["tmux", "new-window", "-t",
                 tmux_window_target(self._session, ""),
                 "-n", name, cmd],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        # Cross-session: also teleport the client to the selected session.
        if self._session != self._attached_session:
            subprocess.Popen(
                ["tmux", "switch-client", "-t", tmux_session_target(self._session)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    except (FileNotFoundError, OSError):
        self.app.notify(f"Failed to switch to {name}", severity="error")
        return
    self.dismiss(name)
```

Because every call site (Enter via `action_select_tui` / `on_list_view_selected`; shortcuts via `_shortcut_switch`) routes through this single method, the "shortcuts act on selected session" behavior and cross-session teleport work uniformly with no additional plumbing.

### Step 5 — Shortcut methods already correct

`_shortcut_switch` (line 365) reads `self._running_names` and calls `self._switch_to(...)`. With Step 2's change, `self._running_names` tracks the SELECTED session's windows; Step 4's `_switch_to` targets `self._session` (selected) and adds a teleport when cross-session. So `action_shortcut_board()` → `_shortcut_switch("board")` → `_switch_to("board", "board" in self._running_names)` does the right thing: opens / focuses board in the selected session, teleporting if needed.

**`action_shortcut_brainstorm` (line 386)** iterates `self._running_names` — already correct because `_running_names` now refers to the selected session.

**`action_shortcut_explore` / `action_shortcut_create`** pass `self._session` directly as the new-window target — already correct. They also call `maybe_spawn_minimonitor(self._session, ...)` — already correct (companion spawns in the selected session). They need the same teleport-on-cross-session call at the end:

```python
def action_shortcut_explore(self) -> None:
    ...
    try:
        subprocess.Popen(
            ["tmux", "new-window", "-t",
             tmux_window_target(self._session, ""),
             "-n", window_name, "ait codeagent invoke explore"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        from agent_launch_utils import maybe_spawn_minimonitor
        maybe_spawn_minimonitor(self._session, window_name)
        if self._session != self._attached_session:
            subprocess.Popen(
                ["tmux", "switch-client", "-t", tmux_session_target(self._session)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    except (FileNotFoundError, OSError):
        ...
```

Same pattern in `action_shortcut_create`. Factor the teleport call into a tiny helper `_teleport_if_cross()` to keep the three sites (Step 4 `_switch_to`, Step 5 explore, Step 5 create) consistent.

```python
def _teleport_if_cross(self) -> None:
    if self._session == self._attached_session:
        return
    try:
        subprocess.Popen(
            ["tmux", "switch-client", "-t", tmux_session_target(self._session)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, OSError):
        pass
```

### Step 6 — `_launch_git_with_companion` already correct

`_launch_git_with_companion` (line 465) reads `self._session` in four places (new-window target, `maybe_spawn_minimonitor` arg, pane-id capture, hook wiring). With `self._session` meaning "selected", this now correctly launches the git TUI + minimonitor companion in the selected session. Add `self._teleport_if_cross()` at the end (after the `set-hook` call).

### Step 7 — TuiSwitcherMixin: no change

`TuiSwitcherMixin.action_tui_switcher` (line 541) already passes the auto-detected attached session as `session=`. Both `self._session` and `self._attached_session` start equal; all existing behavior is preserved when `_multi_mode` is False.

### Step 8 — Website doc one-liner

In `website/content/docs/tuis/_index.md:28`, append to the switcher paragraph:

> When more than one aitasks tmux session is running on the same tmux server, the switcher also shows a session row at the top. Use **Left/Right** to pick another session; the list below updates to show that session's TUIs and windows. **Enter** (or any shortcut key like `b` for board) acts on the selected session, teleporting your tmux client there if it's a different session from the one you're currently attached to.

Per CLAUDE.md docs rule: current-state only, no "this used to…" framing.

### Step 9 — Tests (`tests/test_tui_switcher_multi_session.sh`)

Mirror the bash-plus-inline-python layout of `tests/test_multi_session_monitor.sh`. Tier 1 mock-based cases:

1. **Single-session fallback (regression):** monkey-patch `discover_aitasks_sessions` to return 1 session; construct `TuiSwitcherOverlay(session="s1")`; call `on_mount` via a logic-only path (patch `_render_session_row` and `_populate_list_for` to no-ops so no Textual runtime is needed, just test the state assignment). Assert `_multi_mode is False`, `_session == _attached_session == "s1"`.
2. **Multi-session activation:** patch `discover_aitasks_sessions` to return two `AitasksSession`s for `s1`, `s2`. With `session="s1"`, assert `_multi_mode is True`, `_session == _attached_session == "s1"` (initial state; Left/Right hasn't fired).
3. **Session cycle:** set `_multi_mode=True`, `_all_sessions=[s1, s2]`, `_session="s1"`, mock `_render_session_row` + `_populate_list_for`. Call `_cycle_session(+1)`. Assert `_session == "s2"`, `_populate_list_for` called once with `"s2"`, `_attached_session` unchanged (`"s1"`).
4. **Same-session Enter (regression):** overlay with `_session == _attached_session == "s1"`, `_running_names={"board"}`. Mock `subprocess.Popen`. Call `_switch_to("board", running=True, window_index="2")`. Assert exactly ONE Popen call: `select-window -t =s1:2`. No `switch-client`. Bit-identical to today.
5. **Cross-session Enter (running):** `_session="s2"`, `_attached_session="s1"`. Call `_switch_to("board", running=True, window_index="2")`. Assert two Popen calls: first `select-window -t =s2:2`, then `switch-client -t =s2`.
6. **Cross-session Enter (new window):** same setup, `_switch_to("codebrowser", running=False)`. Assert Popen calls in order: `new-window -t =s2: -n codebrowser ...`, then `switch-client -t =s2`.
7. **Shortcut acts on selected session:** `_session="s2"`, `_attached_session="s1"`, `_running_names={"board"}` (i.e., board IS running in s2). Mock Popen. Call `action_shortcut_board()`. Assert the two Popen calls: `select-window -t =s2:board`, then `switch-client -t =s2`. Confirms the user's stated requirement.
8. **Shortcut `n` acts on selected session:** same setup (`_session="s2"`, `_attached_session="s1"`). Call `action_shortcut_create()`. Assert a `new-window -t =s2:` + `-n create-task` call AND a `switch-client -t =s2` call.
9. **Priority-binding guard:** construct an overlay with `_multi_mode=False`. Call `_cycle_session(+1)`. Assert it raises `SkipAction`. Separately, temporarily break `self.screen.query_one` to raise — assert SkipAction is raised again.
10. **Rendering session row:** set `_multi_mode=True`, two sessions `s1`/`s2`, `_attached_session="s1"`, `_session="s2"`. Monkey-patch `self.query_one` to return a MagicMock capturing the update() call. Call `_render_session_row()`. Assert the captured text contains `▶ s1`, `reverse`-wrapped `  s2`, and the literal prefix `Session:`.

Tier 2 (gated on `command -v tmux`, `TMUX_TMPDIR` isolation, same skip pattern as `test_multi_session_primitives.sh`):

11. Create two temp dirs with `aitasks/metadata/project_config.yaml` stubs. Start two tmux sessions `${PFX}_a` and `${PFX}_b` rooted at each. Run a Python one-liner that imports `agent_launch_utils`, calls `discover_aitasks_sessions()`, and asserts both sessions appear. (This validates the primitive is wired; deeper UI coverage is manual-verification territory and is covered by t634's aggregate sibling.)

**Textual-free harness note:** Textual widgets fully mount inside an `App` run loop; unit tests skip that. Construct the overlay directly and test the logic-only methods (`_cycle_session`, `_switch_to`, `_shortcut_switch`, `action_shortcut_*`, `_teleport_if_cross`). For `on_mount`, skip it and set `_multi_mode` / `_all_sessions` / `_session` / `_attached_session` / `_running_names` by hand. Methods that query widgets (`_render_session_row`, `_populate_list_for`) are called with monkey-patched `self.query_one` returning a MagicMock, or skipped in Tier 1 and covered by manual verification.

### Step 10 — Post-implementation (shared workflow)

- Step 8 (user review) commits `.aitask-scripts/lib/tui_switcher.py`, `tests/test_tui_switcher_multi_session.sh`, and the website doc edit with `feature: Add two-level tmux TUI switcher (t634_3)`. Plan file commits separately via `./ait git`.
- Step 8c (manual-verification follow-up): accept the prompt if offered — the UX invariants here (Left/Right cycle, shortcut-on-selected, cross-session teleport, single-session bit-identicality) are exactly the kind of flow only human verification can cover. The parent t634 already owns an aggregate manual-verification sibling plan; this task's follow-up can extend that sibling with switcher-specific items.
- Step 9 archives t634_3. Parent t634 stays pending (children t634_4, t634_5 not yet implemented).

## Gotchas

- **`self._session` is now mutable** — it's the OPERATING / SELECTED session. It changes on Left/Right. Do not rename or add a second `_selected_session` alias; we reuse `_session` so all existing read sites (shortcuts, `_switch_to`, `_launch_git_with_companion`) work unchanged.
- **`self._attached_session` is immutable after construction.** Only `_render_session_row` (to mark the `▶`) and `_teleport_if_cross` (to decide whether to issue `switch-client`) read it.
- **Priority-binding + App.query_one (CLAUDE.md).** The Left/Right action handlers MUST guard with `self.screen.query_one("#switcher_list", _WrappingListView)` and `raise SkipAction()` on miss. Otherwise a pushed dialog using Left/Right gets its keys consumed by the switcher.
- **Detach during teleport.** If the user detaches between pressing Enter and the teleport subprocesses firing, `switch-client` fails silently. Wrap in the existing `try/except (FileNotFoundError, OSError)` and let `self.dismiss(name)` run regardless — consistent with today's failure semantics.
- **Brand-new sessions without TUI windows** may be invisible to `discover_aitasks_sessions()` if `ait ide` hasn't populated the registry AND no pane has `cd`'d into the project. Acceptable — the user opens the switcher from within an aitasks session, so at least one registered session exists. If only one survives discovery, `_multi_mode` is False and the overlay falls back to today's view.
- **Overlay opened outside an aitasks session.** If `_attached_session` is not in `_all_sessions` (e.g., the user launched the switcher from a shell in a non-registered session), `_multi_mode` is False — prevents showing a session row where the user's attached session is not even listed. They see today's single-session view of whatever `session=` they were constructed with.
- **Sort order.** `discover_aitasks_sessions()` already sorts by session name. Display order + cycle order both follow.
- **ListView clear-before-populate.** `_populate_list_for` must call `list_view.clear()` at the top so Left/Right refreshes produce a clean list and first-selectable-index accounting is correct.
- **Task description calls the class `TuiSwitcherScreen`.** The code name is `TuiSwitcherOverlay`. Use `TuiSwitcherOverlay` throughout.
- **Task description's Step 4 ("shortcuts stay on current session") is reversed.** The agreed behavior per user clarification: shortcuts act on the SELECTED session. Record the inversion inline in a short comment above `_shortcut_switch` referencing this task, and document it in the plan's "Final Implementation Notes" so the archived plan reflects the user's preference (otherwise future readers look at the task file and get confused).

## Verification

Automated:

```bash
bash tests/test_tui_switcher_multi_session.sh
shellcheck tests/test_tui_switcher_multi_session.sh
python3 -c 'import ast; ast.parse(open(".aitask-scripts/lib/tui_switcher.py").read())'
```

Regression (must keep passing):

```bash
bash tests/test_multi_session_primitives.sh
bash tests/test_multi_session_monitor.sh
bash tests/test_tmux_exact_session_targeting.sh
```

Manual (covered by the t634 aggregate manual-verification sibling — see Step 10):

1. Two aitasks projects side-by-side via `ait ide`. Open switcher in project A via `j`. Top row shows both sessions with A marked `▶` (attached) + `[reverse]` (selected).
2. Left/Right cycles the selected session; the `▶` stays on A but the reverse-highlight moves; list below updates to show the newly-selected session's windows.
3. Enter on a B-window teleports the client to B (attached session changes; targeted window selected).
4. **Shortcut `b` when browsing B opens board in B** (teleporting the client to B). This is the user-clarified requirement — test explicitly.
5. **Shortcut `n` when browsing B creates the new-task window in B** (teleporting the client to B). Also per user clarification.
6. Single-session mode (only one aitasks session on server, or overlay opened from non-aitasks session): UI bit-identical to today — no session row, no Left/Right effect, same dialog height.
7. Push a secondary modal on top of the switcher. Left/Right inside that modal is NOT consumed by the switcher.
8. Detach with `prefix + d` while switcher is open, re-attach, reopen. No crash, no stale state.

## Step 9 reference

Standard cleanup per `task-workflow/SKILL.md` — no worktree was created (profile `fast`, `create_worktree: false`), so merge is a no-op; archive via `./.aitask-scripts/aitask_archive.sh 634_3`. Parent t634 stays pending because children t634_4 and t634_5 are not yet implemented.

## Final Implementation Notes

- **Actual work done:** Implemented as planned. `TuiSwitcherOverlay.__init__` grew `_attached_session` (immutable), `_all_sessions`, and `_multi_mode`. `compose()` now yields a `#switcher_session_row` Label above the ListView and a blank `#switcher_hint` that `_render_hint()` fills in `on_mount()`. `on_mount` delegates to three new helpers — `_init_multi_state(sessions)`, `_render_session_row()`, and `_populate_list_for(session)` — which together replace the original monolithic body. `_cycle_session(step)` handles Left/Right with a `self.screen.query_one` + `SkipAction` guard (canonical pattern from `aitask_board.py:2370-2378`). `_switch_to` gained a trailing `_teleport_if_cross()` call that issues `tmux switch-client -t =<selected>` whenever the selected session differs from the attached one. `_shortcut_switch` and `action_shortcut_brainstorm` had their "already on this TUI" no-op guard narrowed to "attached-session AND same TUI name", so shortcuts teleport when the browsed session differs. `action_shortcut_explore` and `action_shortcut_create` call `_teleport_if_cross()` after their `new-window` + `maybe_spawn_minimonitor` calls.
- **Deviations from plan:**
  1. **Config surface.** User chose Option A (no YAML key; multi_mode auto-enabled when ≥2 aitasks sessions). This supersedes the archived task description's Step 6 proposal for `tmux.switcher.multi_session`.
  2. **Shortcut target.** Reversed the task description's Step 4. Shortcut keys act on the SELECTED session, not the attached one — identical behavior to pressing Enter on that TUI's row. User-confirmed during planning. A project memory was written (`project_tui_switcher_shortcuts_on_selected.md`) so future readers don't regress this when reviewing the archived task file.
  3. **Double-teleport guard.** Initial edit also called `_teleport_if_cross()` inside `_launch_git_with_companion()`, which was already being called by `_switch_to` after the branch. Removed the duplicate. `switch-client` is idempotent so there was no observable bug, but the intent is cleaner.
  4. **Hint text is dynamic.** `compose()` yields a blank `#switcher_hint` Label; `_render_hint()` populates it in `on_mount` with one of two variants (multi vs single). The plan proposed a static hint — this is mildly better UX because the `←/→ session` hint only shows when cycling is meaningful.
- **Issues encountered:**
  - Initial test harness tried to assign to `overlay.screen = MagicMock()`; this failed because `screen` is a read-only property on Textual's ModalScreen. Fixed by using `patch.object(TuiSwitcherOverlay, 'screen', new_callable=PropertyMock)` wrapped in a small `with_screen(ov)` helper in the test block.
  - All 37 Tier-1 tests pass; Tier-2 was exercised on Linux with tmux available and verified both fake aitasks sessions are discovered.
- **Key decisions:**
  - Kept `self._session` as the mutable "selected/operating" attribute so all 10+ existing read sites (shortcuts, `_switch_to`, `_launch_git_with_companion`, `action_shortcut_*`) continue to read it without rewrites. Added `self._attached_session` as the immutable second attribute for teleport-vs-no-teleport and the `▶` marker.
  - Priority-binding guard uses `self.screen.query_one(...)` (scoped to the active screen) + `SkipAction` on miss, per the board's established pattern. Raising SkipAction also covers the "not in multi mode" and "only one session" cases cleanly.
  - `_teleport_if_cross` does the minimum: one `switch-client` subprocess call, best-effort error handling, no logging. Consistent with every other tmux helper in this file.
- **Notes for sibling tasks:**
  - **t634_4 (minimonitor multi-session):** The same "selected session is the operating session" principle doesn't directly apply — minimonitor has no browse mode. But the switcher's `_attached_session` vs `_session` split is the canonical pattern for anywhere in the codebase that needs to distinguish "where the client IS" from "where the user is operating on". Reuse the naming if a similar need arises.
  - **t634_5 (docs polish):** This task added a one-paragraph section to `website/content/docs/tuis/_index.md`. The aggregate docs refresh from t634_5 should extend that section to cover minimonitor multi-session once t634_4 lands, and cross-link to the monitor's `M` binding for symmetry.
- **Verification run:** `bash tests/test_tui_switcher_multi_session.sh` → 37/37 pass (shellcheck clean). Regression: `test_multi_session_primitives.sh` 20/20, `test_multi_session_monitor.sh` 31/31, `test_tmux_exact_session_targeting.sh` 10/10, `test_git_tui_config.py` 16/16. `python3 -c 'import ast; ast.parse(open(".aitask-scripts/lib/tui_switcher.py").read())'` → parses cleanly. `PYTHONPATH=.aitask-scripts/lib python3 -c "import tui_switcher"` → imports cleanly.
