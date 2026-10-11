---
Task: t1946_trails_pick_focused_task_shared_pick_launch.md
Base branch: main
Output branch: main
---

# t1946 — `p` (pick) in `ait trails` + one shared pick-launch builder

## Context

`ait trails` (`board/trails_app.py`) has no way to pick the focused task: `p` does
nothing there, while the same card in the board's By-Trail view opens the
`/aitask-pick <N>` dialog. The t1794 split kept TrailsApp to read-only flows plus
the `T` agent launch; pick is also an agent launch (the launched skill writes, the
TUI writes nothing), so adding it keeps the TUI read-only.

The `AgentCommandScreen("Pick Task t<N>", …)` construction is duplicated at 5
sites (board ×2, monitor ×2, minimonitor ×1), and the board does not even use the
shared `pick_launch_argv`. The board's "focus an existing `agent-pick-<N>` /
`agent-resume-<N>` window" check uses raw `tmux` and lives in `aitask_board.py`,
which trails may not import (C1). This task adds trails `p`, routes all pick
dialogs through one lib builder, moves the focus-existing check to shared,
gateway-based code, and makes `p` one shared Binding object.

Current-branch mode (profile `fast`) — no worktree.

### Pre-phase (risk mitigations)

1. [characterize_monitor_pick_sites] Before touching `monitor_app.py`, add
   `tests/test_monitor_pick_launch_sites.py` pinning the two monitor_app pick paths
   (no test pins them today): for `_launch_pick_for_sibling` and
   `_on_restart_confirmed`, called unbound on a `MagicMock` host with stubbed
   `_snapshots` / `_task_cache` / `_monitor` / `_root_for_snap`, assert
   (a) the exact `AgentCommandScreen` positional args + kwargs dict (no `narrow`
  key — the builder in step 1 omits it when false, so this pin survives unedited),
   (b) resolve failure → notify `"Failed to resolve pick command for t<id>"` (error),
   no kill, no push, (c) sibling path: the kill heuristic fires before
   `push_screen` and notifies `"Killed <window>"`; tmux result → `"Launched agent for
   t<id>"`; launch error → `"Launch failed: <err>"`, (d) restart path: kill runs
   inside the callback BEFORE `launch_in_tmux`, notify `"Restarted agent for
   t<id>"`. Patch the seams where the code reads them **today**
   (`monitor_app.pick_launch_argv` / `resolve_agent_string` /
   `resolve_skill_profile` / `AgentCommandScreen` / `launch_in_tmux` /
   `maybe_spawn_minimonitor`). Run it green against the unmodified code, then in
   step 4 re-point only the four construction seams to `agent_command_screen` —
   the assertions themselves must not change.

## Implementation

### 1. Shared builder — `lib/agent_command_screen.py`

Add `pick_launch_argv`, `resolve_agent_string` to the existing
`from agent_launch_utils import (...)` list (no cycle: `agent_launch_utils` never
imports this module). Add after `resolve_skill_profile`:

```python
def build_pick_screen(project_root: Path, task_id: str, *,
                      narrow: bool = False) -> "AgentCommandScreen | None":
    """The `/aitask-pick <task_id>` launch dialog every TUI opens (t1946).

    One construction for the board (Kanban + detail), the stand-alone trails
    TUI, monitor (sibling pick + restart) and minimonitor. Returns None when the
    pick command cannot be resolved; what to do then — and with the dialog's
    result — stays with each caller (fallback launch vs. error notify, kill
    ordering, notify wording). `pick_launch_argv` is called WITHOUT
    `agent_string`, so the configured pick agent is resolved, as every TUI site
    did before (tests/test_pick_launch_argv.py)."""
    full_cmd, window_name = pick_launch_argv(project_root, task_id)
    if not full_cmd:
        return None
    return AgentCommandScreen(
        f"Pick Task t{task_id}", full_cmd, f"/aitask-pick {task_id}",
        default_window_name=window_name,
        project_root=project_root,
        operation="pick",
        operation_args=[task_id],
        default_agent_string=resolve_agent_string(project_root, "pick"),
        skill_name="pick",
        default_profile=resolve_skill_profile("pick", project_root),
        # Passed only when set, so every non-narrow caller's construction stays
        # byte-identical to its pre-t1946 call (the characterization pins).
        **({"narrow": True} if narrow else {}),
    )
```
(The function body references `AgentCommandScreen` at call time, so defining it
before the class is fine; place it after the class if the module's layout reads
better.) Update the module docstring usage block with one line for it, and
`pick_launch_argv`'s docstring call-site list (`agent_launch_utils.py:341`) to say
the TUIs now reach it through `build_pick_screen` (+ `agent_restore`).

### 2. Shared focus-existing check — `lib/agent_launch_utils.py`

Add (gateway only, next to `find_window_by_name`):

```python
def current_tmux_session() -> str | None:
    """The caller's own session on the GATEWAY server, or None when the caller
    is not verifiably a pane of that server.

    A bare `display-message -p #S` sent to the gateway socket by a process whose
    `$TMUX` names a DIFFERENT server has no client to resolve against, so tmux
    answers with its "best" session — possibly another project's, whose
    `agent-pick-<id>` window would then be selected for a same-numbered task.
    So the probe targets the caller's own pane (`$TMUX_PANE`) and is trusted only
    when the answering server's `#{socket_path}` is the socket `$TMUX` names
    (pane ids are per-server: `%0` exists on every server)."""
    tmux_env = os.environ.get("TMUX", "")
    pane = os.environ.get("TMUX_PANE", "")
    if not tmux_env or not pane:
        return None
    own_socket = tmux_env.split(",", 1)[0]
    rc, out = _TMUX.run(["display-message", "-p", "-t", pane,
                         "#{socket_path}\t#{session_name}"])
    if rc != 0:
        return None
    sock, _, session = out.strip().partition("\t")
    if not sock or not own_socket or (
            os.path.realpath(sock) != os.path.realpath(own_socket)):
        return None
    return session or None


def focus_existing_agent_window(task_id: str, project_root: Path) -> bool:
    """Select an already-running `agent-pick-<id>` / `agent-resume-<id>` window
    instead of launching a duplicate (t1946; moved from the board). Looks in the
    current session, else the project's configured default session. True when
    such a window exists (the select is best-effort, as before)."""
    session = (current_tmux_session()
               or load_tmux_defaults(project_root)["default_session"])
    for name in (f"agent-pick-{task_id}", f"agent-resume-{task_id}"):
        existing = find_window_by_name(name, session)
        if existing:
            sess, idx = existing
            _TMUX.run(["select-window", "-t", tmux_window_target(sess, idx)])
            return True
    return False
```
Delta vs. the board's raw probe: the session is now resolved on the gateway
server (the one `find_window_by_name` already queries) and only when the caller
is verifiably on it; a caller on any other server (or outside tmux) searches the
project's configured `default_session` instead of an unrelated "best" session.
Identical to today whenever the board runs inside the ait tmux session.

### 3. Board — `board/aitask_board.py`

- Bindings: replace `Binding("p", "pick_task", "Pick")` (~:2301) with
  `PICK_BINDING` imported from `board_trail_screen` (step 5), keeping position
  and comment.
- `action_pick_task` (~:4720) and the detail `"pick"` branch (~:4558): replace the
  `_resolve_pick_command` + inline `AgentCommandScreen(...)` with
  `screen = build_pick_screen(Path("."), num)`; `None` → `run_aitask_pick(filename)`
  exactly as today. `on_pick_result` bodies unchanged (run → `run_dialog_command`,
  tmux → launch + minimonitor, always `refresh_board(refocus_filename=…)`).
- Delete now-unused `_resolve_pick_command` / `_resolve_pick_profile` (~:5217).
- `_focus_existing_agent_window(num)` (~:5235) becomes a thin wrapper:
  `focus_existing_agent_window(num, Path.cwd())` → on True notify
  `"Switched to existing agent window for t{num}"` and return True. Resume
  (`action_gate_resume`) keeps using it. `_current_tmux_session` stays (detail
  editor + brainstorm still use it). Remove imports that become unused.

### 4. Monitors — `monitor/monitor_app.py`, `monitor/minimonitor_app.py`

- monitor `_launch_pick_for_sibling` (~:3687): `screen = build_pick_screen(target_root, target_id)`;
  `None` → the existing error notify + return; then the existing kill heuristic;
  then `push_screen(screen, on_pick_result)` with the callback unchanged.
- monitor `_on_restart_confirmed` (~:3790): same substitution; callback unchanged
  (kill-before-launch stays inside it).
- minimonitor `_launch_pick` (~:3163): `build_pick_screen(target_root, target_id, narrow=True)`;
  `None` → existing notify; callback unchanged (kill only AFTER a successful launch).
- Import `build_pick_screen` from `agent_command_screen`; drop names left unused
  (`pick_launch_argv`, and `resolve_skill_profile` in minimonitor if nothing else
  uses it — verify with grep before removing).

### 5. Shared Binding — `board/board_trail_screen.py`

After `TRAIL_BINDING`, add with a short C10 comment:
```python
#: `p` — pick the focused task. Not a trail key, but declared by both hosts, so
#: the SAME object rides in both BINDINGS and a `shortcuts.board.pick_task`
#: override rebinds `ait board` and `ait trails` at once (t1946).
PICK_BINDING = Binding("p", "pick_task", "Pick")
```
Kept out of `TRAIL_BINDINGS` (the mixin does not implement `pick_task`; each host does).

### 6. Trails — `board/trails_app.py`

- `BINDINGS`: add `PICK_BINDING` right after `*TRAIL_BINDINGS`.
- Factor the live-member rule out of `_trail_task_target`:
  `_live_member_id() -> str` (focused `TrailTaskCard`, `not is_ghost`, `task_own_id`,
  else `""`). `_trail_task_target` keeps its exact behaviour/message.
- `check_action`: `elif action == "pick_task": if not self._live_member_id(): return False`
  (hidden on ghost and with no focus).
- `action_pick_task`: silent under a modal; no live member →
  `notify("Pick needs a live local task under focus", severity="warning")`, no
  launch (remapped key / command palette path). Else, with `root = Path(".")`:
  `focus_existing_agent_window(target, root)` → notify
  `"Switched to existing agent window for t{target}"` and return;
  `build_pick_screen(root, target)` is None → notify
  `"Could not resolve agent command — launching directly"` and
  `run_dialog_command(shlex.join([str(CODEAGENT_SCRIPT), "invoke", "pick", target]), refocus_filename=filename)`
  (the `T` fallback's shape); otherwise push the screen with a local callback:
  `"run"` → `run_dialog_command(screen.full_command, refocus_filename=filename)`
  (`_after_dialog_command` reloads); `TmuxLaunchConfig` → `launch_in_tmux`, error →
  notify error; success → `maybe_spawn_minimonitor` on a new window, then
  `refresh_board(refocus_filename=filename)`; cancel → nothing.
- Update the module docstring ("…and launch `/aitask-trail` or `/aitask-pick` for a
  live member") and the C10 paragraph to name `PICK_BINDING`.

### 7. Tests

New:
- `tests/test_pick_command_screen.py` — builder golden: positional args + full
  kwargs for `(root, "123_5")` with **no** `narrow` key, the `narrow=True` variant
  carrying `narrow: True`, unresolved → None and no screen/agent/profile
  resolution, `pick_launch_argv` receives no `agent_string`.
  `current_tmux_session` (real function, `_TMUX.run` stubbed): no `$TMUX` / no
  `$TMUX_PANE` → None without probing; probe targets `-t $TMUX_PANE`; matching
  socket (also via a symlinked path) → session; mismatching socket → None;
  rc≠0 / empty → None.
  `focus_existing_agent_window` (`current_tmux_session` NOT mocked): pick window
  wins → gateway `select-window -t =s:2`; resume window found; none → False, no
  select; socket mismatch → searches the configured `default_session` only.
- Live two-server test (same file, skipped without `tmux`; private `TMUX_TMPDIR`,
  gateway `_TMUX` rebuilt on a test socket per
  `tests/lib/tmux_socket_containment.py`): gateway server holds `projB` (with
  window `agent-pick-42`) and `projA` (the patched configured default, no agent
  window); the caller is a pane on a SECOND server whose pane id (`%0`) also exists
  on the gateway. Asserts `current_tmux_session()` is None and
  `focus_existing_agent_window("42", root)` is False with `projB`'s active window
  unchanged. Positive control: caller = a gateway pane in `projA`, `agent-pick-42`
  added there → session `projA`, True, and that window becomes active.
- `tests/test_monitor_pick_launch_sites.py` — the pre-phase file.
- `tests/test_trails_app.py` — `PickPolicyTests`: live member `p` → one dialog
  with `operation_args == [member_id]`; ghost → `check_action("pick_task")` False,
  invoking the action → exactly one "live local task" warning, no build; no focus →
  hidden + refusal; existing window → notify, no dialog; unresolved → direct-launch
  fallback through `run_dialog_command`. `PickCallbackTests` capture the pushed
  screen + callback (builder stubbed to a real-shaped screen), set
  `screen.full_command = OVERRIDE`, then drive: `"run"` →
  `run_dialog_command(OVERRIDE, refocus_filename=<member file>)`, no tmux launch;
  `TmuxLaunchConfig(new_window=True)` success → `launch_in_tmux(OVERRIDE, cfg)`,
  `maybe_spawn_minimonitor(session, window)` once, `refresh_board(refocus_filename=…)`;
  `new_window=False` success → launch, NO companion, refresh; launch error →
  one error notify with the message, no companion, no refresh; `None` (cancel) →
  no launch, no run, no companion, no refresh. `BindingOwnershipTests`: the `pick_task`
  row in `TrailsApp.BINDINGS` and `KanbanApp.BINDINGS` `is` `ts.PICK_BINDING`;
  `OverridePropagationTests`: `shortcuts.board.pick_task: o` rebinds both apps.

Re-pointed seams (assertions unchanged — only where the patched names now live):
- `tests/test_board_dialog_run_dispatch.py` — `_mock_app(pick_cmd=…)` patches
  `agent_command_screen.pick_launch_argv` / `resolve_agent_string` /
  `resolve_skill_profile` instead of `app._resolve_pick_command` / `_resolve_pick_profile`.
- `tests/test_board_detail_nested_actions.py` — stub `agent_command_screen.pick_launch_argv`
  instead of `app._resolve_pick_command`.
- `tests/test_board_inflight_view.py::test_existing_agent_window_guard_reuses_window` —
  patch `agent_launch_utils.current_tmux_session` / `find_window_by_name` / `_TMUX`
  and assert the gateway `select-window`.
- `tests/test_minimonitor_pick_by_number.py` (`SharedLaunchImplementationTests`) and
  `tests/test_minimonitor_pick_next_characterization.py` (`_Harness.run`) — move the
  `pick_launch_argv` / `resolve_agent_string` / `resolve_skill_profile` /
  `AgentCommandScreen` patches from `mm` to `agent_command_screen`; their golden kwargs
  (incl. `narrow: True`) stay byte-identical, which is the dedupe regression for
  minimonitor.
- `tests/test_pick_launch_argv.py` stays untouched.

### 8. Docs

- `website/content/docs/tuis/trails/reference.md` — key-table row after `T`:
  `p` | Open the `/aitask-pick` launch dialog for the focused task (or switch to its
  running agent window) — the launched workflow does the claiming | Focused live
  local card (hidden on a ghost card or with nothing focused).
- `_index.md` — read-only paragraph: name `p` as the other agent launch;
  relationship table: a `p` row (Yes | Yes — same dialog).
- `how-to.md` — short "How to Pick a Member" section after "How to Start a Trail".
- Run `python3 check_links.py --build` in `website/`.

## Verification

```bash
bash tests/test_no_raw_tmux.sh
python3 -m pytest -q tests/test_pick_command_screen.py tests/test_monitor_pick_launch_sites.py \
  tests/test_trails_app.py tests/test_board_dialog_run_dispatch.py \
  tests/test_board_detail_nested_actions.py tests/test_board_inflight_view.py \
  tests/test_board_inflight_planned_lane.py tests/test_minimonitor_pick_by_number.py \
  tests/test_minimonitor_pick_next_characterization.py tests/test_pick_launch_argv.py \
  tests/test_trail_screen_host_protocol.py tests/test_board_bytrail_view.py \
  tests/test_board_package_contract.py tests/test_shortcut_scopes.py tests/test_monitor_shadow_pick.py
bash tests/test_shortcuts_registry_coverage.sh; bash tests/test_keybinding_registry.sh
set -o pipefail; bash tests/run_all_python_tests.sh 2>&1 | tail -3
(cd website && python3 check_links.py --build)
```
Manual: `ait trails` → select a trail → `p` on a live card opens "Pick Task t<N>";
on a ghost card the footer hides `p`.

Step 9 (Post-Implementation): archival per the shared workflow.

## Risk

### Code-health risk: medium
- Refactor spans 3 TUIs + 2 lib modules and re-points 5 test files' seams; a re-pointed seam could hide a behaviour change (e.g. monitor sibling kill ordering, which no test pins today) · severity: low (residual — addressed by inline pre-phase characterize_monitor_pick_sites; blast radius itself keeps the dimension at medium) · → mitigation: inline pre-phase characterize_monitor_pick_sites
- Board focus-existing session probe moves from the ambient raw `tmux` to the gateway (ait socket); an unverified gateway probe could answer another project's session and select its same-numbered agent window · severity: low (residual — probe is pane-targeted and socket-verified, with a live two-server test) · → mitigation: none (design + tests in steps 2 and 7)

### Goal-achievement risk: low
None identified.

### Planned mitigations
- timing: pre-phase | name: characterize_monitor_pick_sites | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — re-pointed seams hiding a monitor pick behaviour change | desc: pin monitor_app's sibling-pick and restart dialog args, notify strings and kill order against pre-refactor code

## Post-review changes

1. **Plan review, before implementation.** Three changes:
   - `current_tmux_session` targets `$TMUX_PANE` and compares `#{socket_path}` with `$TMUX`.
   - The builder passes `narrow` only when set.
   - Trails callback tests were added.
2. **Implementation review 1.** A verified caller can still sit in ANOTHER project's session on the same gateway server. Fix: the caller's session is used only when `discover_aitasks_sessions` attributes it to `project_root`.
3. **Implementation review 2.** The configured `default_session` fallback is only a name, and every project defaults to `aitasks`. Fix: `_sessions_owned_by(project_root)`. A candidate (caller's session, then configured session) is searched only if owned. When neither is owned, nothing is searched and the caller launches.
4. **Implementation review 3 (follow-up).** `_sessions_owned_by` scans the whole server. That moves to t1950: a targeted per-session resolver reusing `_collect_live_roots`' rule.

## Final Implementation Notes
- **Actual work done:**
  - **Shared builder.** `agent_command_screen.build_pick_screen(project_root, task_id, *, narrow=False)` returns the configured `/aitask-pick` dialog, or None when unresolved. Board (Kanban + detail), trails, monitor (sibling + restart) and minimonitor all use it. Each caller keeps its own result policy.
  - **Shared focus helper.** `agent_launch_utils.focus_existing_agent_window` is gateway-routed and searches only sessions attributed to the project. It is built on `current_tmux_session` (pane-targeted, socket-verified) and `_sessions_owned_by`. The board's `_focus_existing_agent_window` became a thin wrapper that keeps its notify; resume uses it too.
  - **Shared binding.** `board_trail_screen.PICK_BINDING` is the one object both apps declare.
  - **Trails `p`.** `TrailsApp.action_pick_task` plus a `check_action` gate. The live-member rule is factored into `_live_member_id`, shared with `T`. A warning covers a remapped key or the palette. The unresolved fallback mirrors `T`'s direct launch.
  - **Docs.** The trails reference, overview and how-to pages cover `p`.
- **Deviations from plan:**
  - The focus helper goes beyond step 2: project-ownership checks on both candidate sessions (review rounds 2–3).
  - The removed `pick_launch_argv` / `resolve_skill_profile` imports in the monitors were confirmed unused before removal.
- **Issues encountered:**
  - The live tmux fixture needed the `-S` socket directory pre-created (mode 0700).
  - One full-suite run flaked in `test_minimonitor_bottom_pin_live.py` (scrollbar thumb press under load). It passed twice in isolation and in the next full run.
- **Key decisions:**
  - Construction seams in tests were re-pointed to `agent_command_screen`, with golden assertions unchanged. This is the dedupe regression for minimonitor and (via `test_monitor_pick_launch_sites.py`) monitor.
  - The monitor sibling kill now runs after the dialog is built rather than between resolve and build. It still runs before `push_screen`, and the pins prove it.
  - When no candidate session is owned, the helper returns False: a duplicate launch beats a launch silently suppressed by another project's window.
  - Verification: the pre-phase characterization was green before and after the refactor. Mutant probes (bare `#S`, pane-targeted without the socket check) both fail the live test. The ownership regressions were red before each fix. Full Python suite: 8610 passed.
- **Upstream defects identified:** None
