---
Task: t634_1_discovery_and_focus_primitives.md
Parent Task: aitasks/t634_multi_session_tmux_support.md
Sibling Tasks: aitasks/t634/t634_2_multi_session_monitor.md, aitasks/t634/t634_3_two_level_tui_switcher.md
Archived Sibling Plans: (none — t634 has no completed siblings)
Worktree: (none — working on current branch per profile `fast`)
Branch: main
Base branch: main
---

## Context

t634 adds an **opt-in** multi-session layer on top of the single-session-per-project invariant established by t632. Two consumer features need to be built (t634_2: multi-session `ait monitor`; t634_3: two-level TUI switcher), and both need the same two primitives:

1. A way to enumerate "aitasks-like" tmux sessions on the current server.
2. A cross-session focus helper that teleports the attached tmux client to an arbitrary pane on the same server.

This task (t634_1) delivers both primitives plus a registry hook in `ait ide` and an integration test. It does **not** touch the monitor or switcher — those come after. The primitives live in `.aitask-scripts/lib/agent_launch_utils.py`, which is already the home for the related `tmux_session_target` / `tmux_window_target` / `find_window_by_name` helpers added in t632.

## Key Files to Modify

- `.aitask-scripts/lib/agent_launch_utils.py` — add `AitasksSession` dataclass, `discover_aitasks_sessions()`, `switch_to_pane_anywhere()`.
- `.aitask-scripts/aitask_ide.sh` — add `tmux set-environment -g "AITASKS_PROJECT_<session>" "$(pwd)"` on startup, in every path that reaches a resolved session (new-session, attach, inside-tmux select/new-window).
- `tests/test_multi_session_primitives.sh` — new; mirror the `TMUX_TMPDIR`-isolation pattern from `tests/test_tmux_exact_session_targeting.sh`.

## Reference Files (reused / cribbed from)

- `.aitask-scripts/lib/agent_launch_utils.py:455 load_tmux_defaults` — how to locate `aitasks/metadata/project_config.yaml` by walking up from a path.
- `.aitask-scripts/codebrowser/codebrowser_app.py:505 _consume_codebrowser_focus` — `tmux show-environment -t <sess> VAR` parse (`VAR=value`).
- `.aitask-scripts/monitor/tmux_monitor.py:187 discover_panes` — server-wide `list-panes -s` pattern (NOT reused for discovery, but we'll use a simpler per-session `list-panes` call of our own).
- `tests/test_tmux_exact_session_targeting.sh` — canonical test layout: `TMUX_TMPDIR` isolation, skip-on-no-tmux, Python-helper + runtime tiers, `cleanup` trap.

## Implementation Plan

### Step 1 — `AitasksSession` dataclass (in `agent_launch_utils.py`)

```python
@dataclass(frozen=True)
class AitasksSession:
    session: str          # tmux session name
    project_root: Path    # absolute path to the project root
    project_name: str     # basename(project_root), for display
```

Placed near the other public dataclasses (just below `TmuxLaunchConfig`).

### Step 2 — `discover_aitasks_sessions()`

Signature:

```python
def discover_aitasks_sessions() -> list[AitasksSession]:
```

Algorithm (all paths swallow tmux errors and skip gracefully):

1. `tmux list-sessions -F '#{session_name}'` → candidate session names. Empty/error → return `[]`.
2. For each session, try to resolve a `project_root` in priority order:
   a. **Pane-cwd walk-up:** `tmux list-panes -s -t =<session> -F '#{pane_current_path}'`. For each path, walk up ancestors until one contains `aitasks/metadata/project_config.yaml`. First hit wins for the session.
   b. **Registry fallback:** if no pane-cwd match, check the tmux global env for `AITASKS_PROJECT_<session>`. Parse `tmux show-environment -g AITASKS_PROJECT_<session>` (format: `AITASKS_PROJECT_<sess>=<path>`; absent/unset → ignored). If the path exists and contains `aitasks/metadata/project_config.yaml`, use it.
3. Build `AitasksSession(session, project_root, project_root.name)` and append.
4. Return the list in sorted-by-session-name order (stable UI display).

Details:

- Use a helper `_walk_up_to_aitasks(path: Path) -> Path | None` that iterates `path.parents` + `path` itself; checks `p / "aitasks" / "metadata" / "project_config.yaml"`.
- `tmux show-environment -g <VAR>` returns exit code 1 with no stdout when the var is unset — handle cleanly.
- Per-session subprocess failures (dead session between `list-sessions` and `list-panes`) are caught and the session is skipped.
- **No module-level cache** — callers get fresh data every call. A running monitor would get staleness bugs if we cached.

### Step 3 — `switch_to_pane_anywhere(pane_id: str) -> bool`

```python
def switch_to_pane_anywhere(pane_id: str) -> bool:
    """Teleport the attached tmux client to the given pane, regardless of session."""
```

Implementation: three separate `subprocess.run` calls, each fails cleanly.

1. `tmux display-message -p -t <pane_id> '#{session_name}'` → `sess` (or return False).
2. `tmux display-message -p -t <pane_id> '#{window_index}'` → `win` (or return False).
3. `tmux switch-client -t =<sess>` — return False on non-zero.
4. `tmux select-window -t =<sess>:<win>` — return False on non-zero.
5. `tmux select-pane -t <pane_id>` — return False on non-zero.
6. Return True.

Wraps each call in `try/except (subprocess.TimeoutExpired, FileNotFoundError, OSError)` returning False — matches the error semantics of the existing helpers in the file (e.g. `get_tmux_sessions`, `launch_or_focus_codebrowser`).

Uses existing `tmux_session_target()` / `tmux_window_target()` for the `=<...>` syntax.

### Step 4 — Registry hook in `aitask_ide.sh`

On every path that resolves a `$SESSION`, set the tmux global env var. Concretely, after `SESSION=$(resolve_session)` / `SESSION_T="=${SESSION}"` (line 74-77), and **before** any `exec tmux ...`, insert a setter that runs in all three paths:

```bash
set_project_registry() {
    # Non-fatal — tmux may not have a running server yet (new-session path
    # creates one). For new-session, do it after tmux is up. For attach/
    # inside-tmux, do it immediately.
    tmux set-environment -g "AITASKS_PROJECT_${SESSION}" "$(pwd)" 2>/dev/null || true
}
```

Wire it into each path:

- **Inside tmux (line 81-94):** call `set_project_registry` before the `exec tmux select-window` / `exec tmux new-window`.
- **Attach existing session (line 96-101):** call before `exec tmux attach`.
- **New session (line 103-105):** switch from `exec tmux new-session ...` to `tmux new-session -d -s "$SESSION" -n monitor 'ait monitor'` followed by `set_project_registry` then `exec tmux attach -t "$SESSION_T"`. The `-d` keeps the server-env write reachable before `exec`. Keeps semantics identical (user still lands attached in monitor window).

The variable name is namespaced per-session so two concurrent `ait ide` invocations in different projects don't collide. The value is the current working directory (project root), which matches the invariant that `ait` cd's to repo root before running scripts.

### Step 5 — Tests (`tests/test_multi_session_primitives.sh`)

Mirror the layout of `tests/test_tmux_exact_session_targeting.sh`:

**Tier 1 — Python helpers (always run):**

- Import `AitasksSession` and assert field names/types match the spec.
- Assert `switch_to_pane_anywhere` with `TMUX` unset and a bogus pane id returns False (no crash).
- Assert `discover_aitasks_sessions` is callable and returns a list (possibly empty).

**Tier 2 — Real tmux (skip cleanly if tmux missing):**

Set up isolated `TMUX_TMPDIR`, cleanup trap identical to the reference test.

1. Create a temp dir containing `aitasks/metadata/project_config.yaml` (stub). Start session `$PFX_a` with a shell rooted at that dir (`tmux new-session -d -s "$PFX_a" -c "$tmpdir_a" 'sleep 300'`). Call `discover_aitasks_sessions()` via a Python one-liner with `TMUX_TMPDIR` exported; assert `$PFX_a` appears with the correct project_root.
2. Start session `$PFX_b` in `/tmp` (no aitasks metadata). Assert it does **not** appear in the discovery result.
3. Export `AITASKS_PROJECT_${PFX_b}=$tmpdir_a` via `tmux set-environment -g`. Re-run discovery. Assert `$PFX_b` now appears (registry fallback) with project_root = `$tmpdir_a`.
4. `switch_to_pane_anywhere`: capture a pane id from `$PFX_a` via `tmux list-panes -a -F '#{pane_id}'`. Call the helper. Because the test runs with no attached client (`unset TMUX`), `switch-client` will fail — assert the return value is False and no crash. (Checking the positive path inside a test harness without an attached client is impractical; the unit-level assertion that the three tmux calls fire in order is sufficient — verified via a mock-based Python test, see below.)

**Tier 3 — Python-level mock test:**

A small Python block (using `unittest.mock.patch("subprocess.run")`) to assert that `switch_to_pane_anywhere("%1")` invokes, in order: `display-message` × 2, `switch-client`, `select-window`, `select-pane`. This catches regressions of call ordering without needing a live client.

### Step 6 — Verification

1. **Tier-1 helper tests pass on any machine** with Python 3 and the repo's `PYTHONPATH`.
2. **Tier-2 runs green** when tmux is installed (CI + developer local).
3. **Manual smoke test:**
   - Open two terminals, `ait ide --session aitasks_a` in one (from this repo), `ait ide --session aitasks_b` in a second aitasks project.
   - From a python shell inside one: `import agent_launch_utils as u; u.discover_aitasks_sessions()` — expect both sessions returned.
   - `tmux show-environment -g | grep AITASKS_PROJECT_` — expect two entries.
4. **Regression:** `bash tests/test_tmux_exact_session_targeting.sh` still passes (no signatures broken).
5. **shellcheck:** `shellcheck .aitask-scripts/aitask_ide.sh` still clean.

## Gotchas

- `tmux show-environment -g VAR` — returns stdout `VAR=value` on set, `-VAR` on unset-marker, or exit 1 with empty stdout if truly absent. Handle all three.
- `tmux set-environment -g` requires a running server. In the `ait ide` new-session path we switch to `new-session -d` + `set-environment` + `attach`, preserving a running server across the set call.
- `pane_current_path` walk-up: when the cwd is inside `aiplans/` / `aiwork/`, the walk-up still finds `aitasks/metadata/`. Good.
- Dead panes / sessions between `list-sessions` and per-pane `display-message`: caught per-session, session skipped.
- macOS BSD `mktemp` is fine in the test because we already use the template form `mktemp -d "${TMPDIR:-/tmp}/ait_..._XXXXXX"` (matches the reference test).
- No shell-quoting booby-traps: all tmux calls in the test use exec lists via `tmux` directly (no shell interpolation of pane ids).

## Non-goals (this task)

- No changes to `tmux_monitor.py`, `monitor_app.py`, or `tui_switcher.py`. Those land in t634_2 and t634_3.
- No `link-window` / cross-socket merging. Out of scope for the whole t634 chain.
- No persistent registry (no `~/.aitask/sessions.json`). Server-lifetime only, per the task's recommendation. If future work needs persistence, add it without breaking the current API.

## Notes for sibling tasks

- `AitasksSession` is the canonical return type — sibling tasks should sort/group by `session` or display `project_name`.
- `switch_to_pane_anywhere(pane_id)` is the ONLY blessed way to teleport across sessions. t634_2's `TmuxMonitor.switch_to_pane(prefer_companion=True)` should call this helper in multi-session mode instead of its in-session `select-window` / `select-pane` path.
- The registry fallback catches fresh sessions that have no TUI window yet. `ait ide` writes the entry on startup; if the user launches an aitasks TUI via a different path, that path must also write `AITASKS_PROJECT_<sess>` or the session won't be discoverable until a pane cd's into a real aitasks dir.

## Step 9 (Post-Implementation)

Standard cleanup per `task-workflow/SKILL.md` — merge is a no-op since we're working on `main`, then archive via `./.aitask-scripts/aitask_archive.sh 634_1`.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned in all three files.
  - `.aitask-scripts/lib/agent_launch_utils.py`: added `AitasksSession` (frozen dataclass), two internal helpers `_walk_up_to_aitasks()` and `_read_registry_entry()`, plus public `discover_aitasks_sessions()` and `switch_to_pane_anywhere()`. Module docstring updated to export the new symbols.
  - `.aitask-scripts/aitask_ide.sh`: added `set_project_registry()` shell function and wired it into all three startup paths (inside-tmux, attach-existing, new-session). The new-session path was restructured from `exec tmux new-session` to `tmux new-session -d` + `set_project_registry` + `exec tmux attach`, so the `set-environment -g` call runs while the server is up but before the shell is replaced.
  - `tests/test_multi_session_primitives.sh`: 20-assertion test with three tiers — Python shape checks, mock-based `switch_to_pane_anywhere` call-ordering verification, and real-tmux `TMUX_TMPDIR`-isolated discovery tests.
- **Deviations from plan:** None structural. One minor test-harness fix: the "tmux missing" case originally proposed `PATH=/nonexistent python3 ...` (which also hides python3). Replaced with a `unittest.mock.patch` that raises `FileNotFoundError` on `subprocess.run` — cleaner, same coverage.
- **Issues encountered:**
  - shellcheck flagged SC2329 on `cleanup()` (invoked via `trap`, false positive) — suppressed with an inline disable comment.
  - shellcheck flagged SC2046 on the final `exit $([[ ...]] && ... || ...)` idiom copied from the reference test — replaced with an explicit `if/else`.
  - Pre-existing SC1091 info on `aitask_ide.sh` (shellcheck can't follow `source "$SCRIPT_DIR/lib/terminal_compat.sh"` without `-x`) is unchanged and not introduced here.
- **Key decisions:**
  - Kept the no-caching semantics for `discover_aitasks_sessions()` — callers always get fresh state. A TTL cache would be the wrong default for long-running monitors.
  - Registry lookup uses `tmux show-environment -g <VAR>` per-session, not a single `show-environment -g` scan. Simpler and the cost is negligible (N sessions × one subprocess).
  - Registry entry is **validated** before being trusted (checks that the path still contains `aitasks/metadata/project_config.yaml`), so a stale entry pointing at a deleted project doesn't resurrect a non-aitasks session. Covered by Case 4 in the test.
  - `switch_to_pane_anywhere` issues `switch-client`, `select-window`, and `select-pane` as three separate subprocess calls (not one compound `tmux ... \; ... \; ...` invocation) so each failure surface is diagnosable and the helper matches the error semantics of every other tmux wrapper in the file.
- **Notes for sibling tasks:**
  - t634_2 (multi-session monitor) should call `switch_to_pane_anywhere(pane.pane_id)` inside `TmuxMonitor.switch_to_pane()` when `multi_session=True`. Do **not** try to extend the existing in-session `select-window` + `select-pane` path for cross-session focus — pane IDs alone aren't enough because tmux still needs the client to teleport sessions first.
  - t634_3 (two-level switcher) should prefer window-index targeting (`switch-client -t =sess` + `select-window -t =sess:N`) for Enter-to-teleport when the target is a window rather than a pane. `switch_to_pane_anywhere` is pane-oriented; for window-oriented navigation, duplicate the `switch-client` + `select-window` subset inline — don't retrofit the helper.
  - The `AITASKS_PROJECT_<sess>` registry is populated **only** by `ait ide`. If a user launches the first aitasks TUI via a different entry point (e.g., running `ait board` directly in a shell session that's already cd'd into the project), the pane-cwd heuristic already covers it, so this is not a gap — but if a future entry point spawns a TUI window in a fresh session whose panes never see the project dir, that entry point must also write the registry entry. Document explicitly in each consumer's plan.
- **Build verification:** `bash tests/test_multi_session_primitives.sh` → 20/20 pass. `bash tests/test_tmux_exact_session_targeting.sh` → 10/10 pass (regression). `shellcheck .aitask-scripts/aitask_ide.sh tests/test_multi_session_primitives.sh` → clean except pre-existing SC1091 info on `aitask_ide.sh`. `PYTHONPATH=.aitask-scripts/lib python3 -c "import agent_launch_utils"` → imports cleanly.
