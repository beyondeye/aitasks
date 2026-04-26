---
Task: t649_wrong_project_parent_repo_when_spawing_tuis.md
Base branch: main
plan_verified: []
---

# t649 — Fix wrong project parent repo when spawning TUIs cross-session from TUI switcher

## Context

After multi-session support was added to the TUI switcher (t634_3), users can browse other aitasks tmux sessions via Left/Right and launch TUIs there. But the launched TUI runs in the **attached session's** project directory rather than the **selected session's** project directory.

Concretely, with two sessions running:
- `aitasks` → `~/Work/aitasks`
- `aitasks_mob` → `~/Work/aitasks_mobile`

If the user is attached to `aitasks`, opens the switcher (`j`), arrows over to `aitasks_mob`, and presses `b` (board), the new tmux window IS created in `aitasks_mob` — but it inherits the calling pane's cwd (`~/Work/aitasks`), so `ait board` resolves to the **wrong** project's `.aitask-scripts/aitask_board.sh` and shows `~/Work/aitasks` tasks. Same bug for codebrowser, settings, stats, brainstorm, git, explore, new-task, and the companion minimonitor.

Root cause: every `tmux new-window` / `tmux split-window` call in `tui_switcher.py` and the cross-session callsites in `agent_launch_utils.py:maybe_spawn_minimonitor` omits the `-c <start-directory>` flag, so the new pane inherits the calling pane's cwd instead of starting in the target session's project root.

`AitasksSession.project_root` (already populated by `discover_aitasks_sessions()` from pane-cwd walk-up or the `AITASKS_PROJECT_<sess>` registry entry) gives us exactly the path we need; it just isn't threaded through to the spawn calls.

## Approach

Thread the **selected session's project_root** through every tmux spawn the switcher makes, and pass it to tmux as `-c <project_root>`. Also pass it to `maybe_spawn_minimonitor` so its `project_config.yaml` reads and its `tmux split-window` use the right directory.

Single-session mode is unaffected by behavior (calling pane's cwd already equals the project root), but we still pass `-c` for consistency. Falls back to `Path.cwd()` when no session match is found (defensive, preserves single-session behavior).

## Files to modify

### 1. `.aitask-scripts/lib/tui_switcher.py`

**a) Add a `_project_root_for_session()` helper** on `TuiSwitcherOverlay` that returns the absolute project_root for a given session name:
- Look up `session` in `self._all_sessions` (list of `AitasksSession`).
- If found → return `s.project_root`.
- If not found (single-session mode where `_all_sessions` may be empty, or unrecognized session) → return `Path.cwd()`.

**b) Add `-c <project_root>` to every `tmux new-window` call**, and refactor to use a small `_spawn_in_session(window_name, cmd, *, capture_pane_id=False)` helper that resolves the project_root via `_project_root_for_session(self._session)` and assembles the full argv. Call sites:
- `_switch_to()` — `tui_switcher.py:589` (new-window for non-running TUI).
- `action_shortcut_explore()` — `tui_switcher.py:542`.
- `action_shortcut_create()` — `tui_switcher.py:559`.
- `_launch_git_with_companion()` — `tui_switcher.py:631` (must keep the `-P -F #{pane_id}` flags + `subprocess.run` for stdout capture; the helper takes a `capture_pane_id` flag).

**c) Pass the project_root to `maybe_spawn_minimonitor()`** in all three callsites (`action_shortcut_explore`, `action_shortcut_create`, `_launch_git_with_companion`). The new keyword arg threads through to `tmux split-window -c` and `project_config.yaml` reads.

**d) Make `_build_tui_list()` accept a project_root** (default `None` → `Path.cwd()` for backward compat), and pass `_project_root_for_session(self._session)` from `_populate_list_for()` so the `git_tui` entry comes from the SELECTED session's config (matters when sessions have different `git_tui` settings). Also update `_get_launch_command()` to accept a project_root for the same reason; thread it through from `_switch_to` and `_launch_git_with_companion`.

### 2. `.aitask-scripts/lib/agent_launch_utils.py`

**Add an optional `project_root: Path | None = None` keyword arg to `maybe_spawn_minimonitor()`** (`agent_launch_utils.py:432`):
- When `None` → keep current behavior (`Path.cwd()` for config reads, no `-c` on `split-window`).
- When set → read `project_config.yaml` from `<project_root>/aitasks/metadata/` and pass `-c <project_root>` to `tmux split-window`.

This is purely additive — none of the other 8 existing callers (`codebrowser`, `monitor`, `agentcrew_runner`, `board`, `history_screen`) need to change because they're already operating on the current project's session.

### 3. `tests/test_tui_switcher_multi_session.sh`

Extend the Tier 1 logic tests to assert `-c <project_root>` is in the argv:

- **`_switch_to` cross-session new-window** (existing `CROSS_NEW_POPEN_*` block) — set `ov._all_sessions` with two `AitasksSession` entries, assert `-c /p2` appears in the new-window argv when targeting `s2`.
- **`action_shortcut_create` cross-session** (existing `SHORTCUT_N_*` block) — assert `-c /p2` in the new-window argv.
- **`action_shortcut_explore` cross-session** (new test block, mirrors the create test) — assert the new-window argv contains `-c /p2` and `-n agent-explore-1`.
- **Same-session regression** (existing `SAME_POPEN_*` block) — `select-window` path is unchanged; no new assertion needed there. Add a single `new-window` same-session assertion that `-c /p1` is present (defensive — proves the helper falls back gracefully).

The existing tests already mock `Popen`, so the additions are pure assertion extensions on already-captured argv lists.

## Verification

1. **Unit tests** — `bash tests/test_tui_switcher_multi_session.sh` should pass with the new `-c` assertions.
2. **Lint** — `shellcheck tests/test_tui_switcher_multi_session.sh` (only if shell additions); skip for python-only changes.
3. **Manual smoke test** (matches the bug report exactly):
   - Have two aitasks projects open in two tmux sessions named `aitasks` and `aitasks_mob`, on different project_roots.
   - Attach to `aitasks`, open `ait board`, press `j` (switcher), Right to `aitasks_mob`, press `b` (board).
   - Expected: a new window named `board` appears in the `aitasks_mob` session, running `ait board` against `~/Work/aitasks_mobile`'s tasks (verify by checking that the visible task list matches `aitasks_mob` not `aitasks`).
   - Repeat with `c` (codebrowser), `s` (settings), `t` (stats), `g` (git → lazygit/etc. should open the `aitasks_mob` git repo), `x` (explore), `n` (new task → `ait create` from `aitasks_mob` should land the new task in `aitasks_mob/aitasks/`).
   - Verify the spawned `agent-explore-N` and `create-task` windows correctly auto-spawn a minimonitor pane that reads `aitasks_mob`'s `project_config.yaml` (e.g., honors any `aitasks_mob`-specific `tmux.minimonitor.width`).
4. **Single-session regression** — In a project with only the `aitasks` session, repeat any of the actions above; confirm everything still works (the `-c <cwd>` fallback should make this a no-op behavior change).

## Step 9 follow-up

Standard archival flow per `.claude/skills/task-workflow/SKILL.md` Step 9 (push, archive, satisfaction feedback). No special considerations.

## Final Implementation Notes

- **Actual work done:** Threaded the SELECTED session's `project_root` through every cross-session tmux spawn in the TUI switcher.
  - `tui_switcher.py`: added `_project_root_for_session()` (looks up `self._all_sessions`, falls back to `Path.cwd()`) and a `_spawn_in_session()` helper that always passes `-c <project_root>` to `tmux new-window`. Refactored `_switch_to`, `action_shortcut_explore`, `action_shortcut_create`, `_launch_git_with_companion` to use the helper. `_get_launch_command` and `_build_tui_list` now take an optional `project_root` so the dynamic Git entry comes from the SELECTED session's `project_config.yaml`.
  - `agent_launch_utils.py`: added optional `project_root: Path | None = None` kwarg to `maybe_spawn_minimonitor()`. When set, reads `project_config.yaml` from that root and passes `-c <project_root>` to `tmux split-window`. Default `None` preserves legacy behavior for the 8 other callers (codebrowser, monitor, board, agentcrew_runner, history_screen).
  - `tests/test_tui_switcher_multi_session.sh`: extended Tier 1 logic tests with 8 new assertions covering `-c /p2` in cross-session new-window argv (`_switch_to` codebrowser path, `action_shortcut_create`, `action_shortcut_explore`), `-c <cwd>` fallback in single-session mode, and `project_root=/p2` threading into `maybe_spawn_minimonitor` for both create and explore. Added a new `SHORTCUT_X_*` block for explore (no prior coverage existed).
- **Deviations from plan:** None.
- **Issues encountered:** None — `discover_aitasks_sessions()` already populated `AitasksSession.project_root` from pane-cwd walk-up + `AITASKS_PROJECT_<sess>` registry, so the data was ready to consume.
- **Key decisions:**
  - Added `_spawn_in_session()` helper rather than inlining `-c` at each callsite — keeps the four spawn paths consistent and concentrates future tmux flag changes.
  - Made `project_root` an optional kwarg on `maybe_spawn_minimonitor` (rather than positional) so the existing 8 callers don't change. This preserves the encapsulation contract for non-switcher callers that already operate in the right cwd.
  - `_build_tui_list(project_root)` now reads the SELECTED session's `git_tui` so the displayed Git entry matches what would launch — covers the corner case of two projects with different `git_tui` configs.
  - Single-session fallback uses `Path.cwd()` (defensive); behaviorally identical to the pre-fix path because the calling pane's cwd was already the project root in single-session mode.
- **Verification:** `bash tests/test_tui_switcher_multi_session.sh` → 45/45 pass (37 prior + 8 new). Related multi-session suites also clean: `test_multi_session_minimonitor.sh` 24/24, `test_multi_session_monitor.sh` 27/27, `test_multi_session_primitives.sh` 20/20, `test_git_tui_config.py` 16/16. Manual smoke test (per plan §Verification) deferred to user — requires two real aitasks sessions on different project roots.
