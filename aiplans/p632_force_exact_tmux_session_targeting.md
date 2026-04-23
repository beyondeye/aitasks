---
Task: t632_force_exact_tmux_session_targeting.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Force exact tmux session targeting (t632)

## Context

Running two aitasks projects side-by-side with distinct tmux session names (e.g. `aitasks` and `aitasks_mob`) currently cross-contaminates because `tmux -t <name>` is a prefix match by default — `-t aitasks` matches `aitasks_mob` when `aitasks` is not running yet. On top of that, `find_window_by_name()` iterates every running session, so even with prefix match fixed, brainstorm lookups can redirect into another project's window. `ait ide` is the most visible symptom (attaches to the wrong project's session), but every TUI launch, companion minimonitor spawn, and brainstorm switch inherits the bug.

The fix is two-pronged:

- **Part A** — prefix every tmux target that resolves to a session with `=` (exact-match form: `=<session>`, `=<session>:<window>`). Do it via small helpers so the change is uniform and future call sites use the same idiom.
- **Part B** — scope `find_window_by_name(name)` to a caller-supplied session; drop the whole-tmux-server scan.

Pane-id (`%...`) and window-id (`@...`) targets already bind by ID and do **not** need the `=` prefix. Only session-name and `<session>:<window-name>` / `<session>:<window-idx>` targets are affected.

## Part A — Exact-match helpers + site updates

### A1. Python helpers (in `.aitask-scripts/lib/agent_launch_utils.py`)

Add two small helpers near the top of the file (after the `KNOWN_GIT_TUIS` constant, before `TmuxLaunchConfig`):

```python
def tmux_session_target(session: str) -> str:
    """Return an exact-match tmux `-t` session target (``=<session>``)."""
    return f"={session}"


def tmux_window_target(session: str, window: str | int) -> str:
    """Return an exact-match tmux `-t` session:window target.

    Accepts window name or index. Only the session part is anchored; the
    window segment is passed through unchanged because window indices and
    names do not suffer tmux's session prefix-match behavior.
    """
    return f"={session}:{window}"
```

Rationale: two functions, not one with an `Optional[window]`, because the call-site intent (session-only vs session:window) reads more clearly and `tmux_window_target("foo", "")` for the "trailing colon" idiom (`"=foo:"`) is still ergonomic via `tmux_window_target(session, "")`. Caveat: since `tmux_window_target(session, "")` produces `=foo:` the helper also covers the new-window "trailing colon" idiom — callers don't need a third helper.

### A2. Python call sites to update

All sites below are session-denominated targets (not pane/window IDs). Each replaces an inline f-string with the new helper.

**`.aitask-scripts/lib/agent_launch_utils.py`:**
- Line 137 — `get_tmux_windows()`: `"-t", session` → `"-t", tmux_session_target(session)`
- Line 183 — `switch-client`: `"-t", config.session` → `"-t", tmux_session_target(config.session)`
- Line 187 — `new-window` trailing colon: `"-t", f"{config.session}:"` → `"-t", tmux_window_target(config.session, "")`
- Line 202 — `split-window`: `target = f"{config.session}:{config.window}"` → `target = tmux_window_target(config.session, config.window)` (variable `target` feeds both `split-window -t target` at 202 and `select-window -t target` at 211 — single substitution handles both)
- Line 219 — `_lookup_window_name()`: `"-t", session` → `"-t", tmux_session_target(session)`
- Line 310 — inline `list-windows` in `maybe_spawn_minimonitor`: `"-t", session` → `"-t", tmux_session_target(session)`
- Line 329 — `list-panes`: `f"{session}:{win_index}"` → `tmux_window_target(session, win_index)`
- Line 349 — `split-window -t`: `f"{session}:{win_index}"` → `tmux_window_target(session, win_index)`
- Line 357 — `select-pane`: `f"{session}:{win_index}.0"` → `f"{tmux_window_target(session, win_index)}.0"` (pane suffix appended to the window target)
- Line 381 — `set-environment -t`: `session` → `tmux_session_target(session)` (in `launch_or_focus_codebrowser`)
- Line 392 — `list-windows -t`: `session` → `tmux_session_target(session)`
- Line 405 — `select-window -t`: `f"{session}:{window_name}"` → `tmux_window_target(session, window_name)`
- Line 413 — `new-window -t`: `f"{session}:"` → `tmux_window_target(session, "")`

**`.aitask-scripts/monitor/monitor_app.py`:**
- Line 538 — `has-session -t`: `self._expected_session` → `tmux_session_target(self._expected_session)`
- Line 733 — `show-environment -t`: `self._session` → `tmux_session_target(self._session)`
- Line 753 — `set-environment -t`: `self._session` → `tmux_session_target(self._session)`
- Add `from agent_launch_utils import tmux_session_target` to the existing import block at line 39 (`from agent_launch_utils import ...`).

**`.aitask-scripts/monitor/minimonitor_app.py`:**
- Line 528 — `set-environment -t`: `self._session` → `tmux_session_target(self._session)`
- Line 543 — `list-windows -t`: `self._session` → `tmux_session_target(self._session)`
- Line 557 — `select-window -t`: `f"{self._session}:monitor"` → `tmux_window_target(self._session, "monitor")`
- Line 566 — `new-window -t`: `f"{self._session}:"` → `tmux_window_target(self._session, "")`
- Import the helpers from `agent_launch_utils`.

**`.aitask-scripts/monitor/tmux_monitor.py`:**
- Line 189 — `list-panes -s -t`: `self.session` → `tmux_session_target(self.session)`
- Line 201 — async `list-panes -s -t`: `self.session` → `tmux_session_target(self.session)`
- Line 378 — `select-window -t`: `f"{self.session}:{pane.window_index}"` → `tmux_window_target(self.session, pane.window_index)`
- Line 399 — `list-panes -t`: `f"{self.session}:{window_index}"` → `tmux_window_target(self.session, window_index)`
- Line 468 — `list-panes -t window_target`: reassign `window_target = tmux_window_target(self.session, pane.window_index)` at line 464
- Line 497 — `new-window -t`: `f"{self.session}:"` → `tmux_window_target(self.session, "")`
- Add import for the helpers. (Pane-id targets at lines 221, 284, 348, 362, 387, 423, 439 are unchanged — they already bind by ID.)

**`.aitask-scripts/agentcrew/agentcrew_runner.py`:**
- Line 480 — `pipe-pane -t`: `f"{session}:{win_idx}.0"` → `f"{tmux_window_target(session, win_idx)}.0"`
- Line 472 — `get_tmux_windows(session)` already routed through the A2 fix; no separate edit needed here.
- Add import.

**`.aitask-scripts/codebrowser/codebrowser_app.py`:**
- Line 511 — `show-environment -t`: `self._tmux_session` → `tmux_session_target(self._tmux_session)`
- Line 532 — `set-environment -t`: `self._tmux_session` → `tmux_session_target(self._tmux_session)`
- Add import.

**`.aitask-scripts/lib/tui_switcher.py`:**
- Line 406 — `new-window -t`: `f"{self._session}:"` → `tmux_window_target(self._session, "")`
- Line 421 — same as 406
- Line 436 — assemble `target = tmux_window_target(self._session, window_index if window_index else name)` (single expression covers both branches; already used by `select-window` at 438)
- Line 447 — `new-window -t`: `f"{self._session}:"` → `tmux_window_target(self._session, "")`
- Line 466 — `new-window -t`: `f"{self._session}:"` → `tmux_window_target(self._session, "")`
- Lines 487 and 496 (`set-option -p -t primary_pane`, `set-hook -p -t primary_pane`) are unchanged — `primary_pane` is a `%N` pane ID.
- Add import.

**`.aitask-scripts/board/aitask_board.py`:**
- Line 3881 — `select-window -t`: `f"{sess}:{idx}"` → `tmux_window_target(sess, idx)`
- Add import (`from agent_launch_utils import ... tmux_window_target, tmux_session_target`).

### A3. Shell fixes (`.aitask-scripts/aitask_ide.sh`)

Introduce a local `SESSION_T` variable right after `SESSION=$(resolve_session)` at line 74:

```bash
SESSION_T="=${SESSION}"
```

Then replace every session-denominated `-t` target:

- Line 87 — `exec tmux select-window -t "$SESSION:monitor"` → `exec tmux select-window -t "${SESSION_T}:monitor"`
- Line 93 — `if tmux has-session -t "$SESSION" 2>/dev/null; then` → `if tmux has-session -t "$SESSION_T" 2>/dev/null; then`
- Line 94 — `tmux list-windows -t "$SESSION"` → `tmux list-windows -t "$SESSION_T"`
- Line 95 — `tmux new-window -t "$SESSION:"` → `tmux new-window -t "${SESSION_T}:"`
- Line 97 — `exec tmux attach -t "$SESSION" \; select-window -t "$SESSION:monitor"` → `exec tmux attach -t "$SESSION_T" \; select-window -t "${SESSION_T}:monitor"`
- Line 100 — `tmux new-session -s "$SESSION"` is unchanged: `new-session -s` takes a session **name to create**, not a target to resolve, so the `=` prefix is inappropriate (and would create a session literally called `=aitasks`).

Other shell files (`aitask_companion_cleanup.sh`, `aitask_minimonitor.sh`) only use pane-id `-t` targets — no changes.

## Part B — Scope `find_window_by_name` to a single session

In `.aitask-scripts/lib/agent_launch_utils.py`:

```python
def find_window_by_name(name: str, session: str) -> tuple[str, str] | None:
    """Find a tmux window by name within a specific session.

    Returns (session, window_index) if found, None otherwise. The session
    parameter is required to prevent cross-project matches — the aitasks
    framework is designed to run one tmux session per project, so whole-
    server scans are always a bug.
    """
    for idx, win_name in get_tmux_windows(session):
        if win_name == name:
            return (session, idx)
    return None
```

Update the single caller in `.aitask-scripts/board/aitask_board.py:3877`:

```python
session = _current_tmux_session() or load_tmux_defaults(Path.cwd())["default_session"]
existing = find_window_by_name(window_name, session)
```

`_current_tmux_session()` already exists at `aitask_board.py:1171` and returns the current tmux session name when the board is running inside tmux (which is the normal case). `load_tmux_defaults` is the documented fallback for the edge case where the board is launched outside tmux.

Make the `session` parameter required (no default) — any future caller is forced to think about which session they mean.

## Part C — Tests

Add `tests/test_tmux_exact_session_targeting.sh`. It:

1. Skips cleanly if `tmux` is not installed (`command -v tmux >/dev/null || { echo "SKIP: tmux not installed"; exit 0; }`).
2. Uses a unique session prefix to avoid colliding with the developer's real sessions: `PFX="aittest_$$"`, sessions `${PFX}` and `${PFX}_mob`.
3. Registers a trap that `tmux kill-session -t =${PFX} 2>/dev/null; tmux kill-session -t =${PFX}_mob 2>/dev/null` so the test cleans up even on failure.
4. Starts both sessions detached: `tmux new-session -d -s "${PFX}_mob" -n stub 'sleep 300'` then `tmux new-session -d -s "${PFX}" -n stub 'sleep 300'`.
5. Sanity check: `tmux has-session -t "${PFX}"` returns 0 and the **prefix-match** behavior is demonstrable (i.e. before the fix, `has-session -t pfx_short_prefix` would succeed even with only `_mob` running — but this is a sanity property test on the helpers, not the bug repro, which requires killing one of the sessions and re-running).
6. Assertion 1 — helpers produce the right string: source no file, instead execute a tiny inline Python: `python3 -c "import sys; sys.path.insert(0, '.aitask-scripts/lib'); import agent_launch_utils as u; print(u.tmux_session_target('aitasks')); print(u.tmux_window_target('aitasks', 'monitor'))"` and assert outputs are `=aitasks` and `=aitasks:monitor`.
7. Assertion 2 — exact-match behavior on real tmux: kill `${PFX}` (leaving only `${PFX}_mob`), then:
   - `tmux has-session -t "=${PFX}" 2>/dev/null; rc=$?` — expect `rc != 0` (exact match must fail).
   - `tmux has-session -t "${PFX}" 2>/dev/null; rc=$?` — expect `rc == 0` (prefix match still wrongly succeeds — this is the tmux default we are guarding against).
   - Asserts together demonstrate that `=${PFX}` prevents the prefix-match collision.
8. Assertion 3 — run `.aitask-scripts/aitask_ide.sh --session "${PFX}_target_that_does_not_exist"` with `TMUX=` (unset) in a subshell and assert it reaches `new-session` path rather than wrongly attaching to `${PFX}_mob`. Implementation note: since `aitask_ide.sh` `exec`s the final tmux command, the test should invoke it with `--session "${PFX}"` knowing `${PFX}` was killed and `${PFX}_mob` still runs — and check that a brand new `${PFX}` session is spawned (`tmux has-session -t "=${PFX}"` returns 0 afterwards and the `-n monitor` window exists). The session command it launches (`ait monitor`) will fail fast outside a real project but the session itself is created first, so the assertion is still valid. To keep the test hermetic, override the command: add `--cmd` is not a feature of `aitask_ide.sh`, so instead use `TMUX_TMPDIR` + a helper that substitutes the "ait monitor" payload. Simpler alternative: skip the `aitask_ide.sh` end-to-end assertion and instead issue the same sequence of tmux commands the script runs (`has-session -t "=${PFX}"`, `new-session -d -s "${PFX}" -n stub 'sleep 300'`) directly; this tests the **targeting pattern** without depending on `ait monitor`.

Use `tests/test_archive_utils.sh` as the shellscript style template (sourcing helpers, `assert_eq`, PASS/FAIL summary).

## Post-Implementation

- Follow Step 8: `git status`, `git diff --stat`, review, request "Commit changes" approval.
- Commit code under `bug: Force exact-match tmux session targeting (t632)`.
- Commit the updated plan to `aiplans/p632_force_exact_tmux_session_targeting.md` separately via `./ait git`.
- Follow Step 9: no worktree, so skip worktree cleanup; run the archival script to mark t632 Done and push. `verify_build` is unset in `project_config.yaml` — skipped.

## Verification

Automated:
- `bash tests/test_tmux_exact_session_targeting.sh` — expect PASS.
- `shellcheck .aitask-scripts/aitask_*.sh` — expect no new warnings for `aitask_ide.sh`.
- `python3 -m py_compile .aitask-scripts/lib/agent_launch_utils.py .aitask-scripts/monitor/*.py .aitask-scripts/lib/tui_switcher.py .aitask-scripts/codebrowser/codebrowser_app.py .aitask-scripts/agentcrew/agentcrew_runner.py .aitask-scripts/board/aitask_board.py` — expect clean compile.

Manual (the bug repro from the task description, preserved verbatim):
1. `tmux kill-server`
2. `cd /home/ddt/Work/aitasks_mobile && ait ide` — starts `aitasks_mob` session with `monitor` window.
3. Detach (`Ctrl-b d`).
4. `cd /home/ddt/Work/aitasks && ait ide` — must start a new `aitasks` session, **not** attach to `aitasks_mob`.
5. `tmux list-sessions` shows both `aitasks` and `aitasks_mob`.
6. Switch TUIs (`j` in each project) — board/codebrowser/settings/monitor windows stay inside their own session.
7. Start a brainstorm in project A; in project B the `find_window_by_name` lookup must not see A's window.

## Risks & Considerations

- tmux semantics of `=` are documented in `tmux(1)` under "TARGETS"; the syntax has been stable since tmux 2.1.
- `tmux new-session -s <name>` creates a session literally named `<name>` — do not prefix `-s` args with `=`.
- The `rename-session` call at `monitor/monitor_app.py:232` (no `-t`) targets the current session implicitly; untouched.
- Pane-id targets (`%NN`) and window-id targets (`@NN`) are bound by ID and never matched by prefix; confirmed unchanged.
- Scope: listing-style tmux calls that don't use `-t` at all (`tmux list-sessions`, `tmux display-message`) are unaffected.

## Summary of files touched

- `.aitask-scripts/lib/agent_launch_utils.py` — add helpers, update ~14 call sites, tighten `find_window_by_name` signature.
- `.aitask-scripts/aitask_ide.sh` — add `SESSION_T` variable, update 5 call sites.
- `.aitask-scripts/monitor/monitor_app.py` — 3 call sites + import.
- `.aitask-scripts/monitor/minimonitor_app.py` — 4 call sites + import.
- `.aitask-scripts/monitor/tmux_monitor.py` — 6 call sites + import.
- `.aitask-scripts/agentcrew/agentcrew_runner.py` — 1 call site + import.
- `.aitask-scripts/codebrowser/codebrowser_app.py` — 2 call sites + import.
- `.aitask-scripts/lib/tui_switcher.py` — 5 call sites + import.
- `.aitask-scripts/board/aitask_board.py` — 1 call site + update `find_window_by_name` caller + import.
- `tests/test_tmux_exact_session_targeting.sh` — new.

Approx totals: ~42 session-target substitutions across 9 Python files and 1 shell file, 1 API change (`find_window_by_name`), 1 new shell test.
