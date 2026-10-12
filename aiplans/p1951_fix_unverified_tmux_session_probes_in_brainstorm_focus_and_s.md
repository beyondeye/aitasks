---
Task: t1951_fix_unverified_tmux_session_probes_in_brainstorm_focus_and_s.md
Base branch: main
Output branch: main
---

# t1951 — Fix unverified tmux session probes in brainstorm focus and switcher

## Context

t1946 fixed `ait board`'s pick/resume "focus an existing agent window" lookup.
The lookup now lives in `agent_launch_utils.focus_existing_agent_window`. It is
socket-verified through `current_tmux_session()` and ownership-checked through
`_sessions_owned_by(project_root)`. Two callers still use the old, unverified
pattern:

1. `KanbanApp._launch_brainstorm` (`.aitask-scripts/board/aitask_board.py:4962`):
   - It probes `#S` with raw ambient `tmux` (`_current_tmux_session`), or uses
     the configured `default_session` name.
   - It looks up `brainstorm-<num>` in that session and selects it with a raw
     `subprocess.Popen(["tmux", "select-window", …])`.
   - Window names carry only the task number, and one gateway server hosts every
     project. So the lookup can switch to another project's same-numbered
     brainstorm window and suppress this project's launch.
2. `tui_switcher._detect_current_session` (`.aitask-scripts/lib/tui_switcher.py:142`):
   - It sends a bare `display-message -p '#S'` to the gateway.
   - From a pane on a different server, tmux answers with its "best" session. So
     `action_tui_switcher` treats an unrelated session as the attached one.

## Coordination with t1950 (resolved by order: t1950 landed first)

t1950 replaced the whole-server ownership scan with candidate-only attribution.
It landed as `ce52aac6a` while this plan was under review. What changed:

- `_sessions_owned_by(project_root, candidates)` now attributes only the named
  candidates, through `_collect_live_roots(…, only=names)`.
- `focus_existing_agent_window` builds the candidates first and passes them in.
- Its tests now stub `alu._collect_live_roots` instead of
  `discover_aitasks_sessions`.

This plan is rebased onto that committed version. The factoring below moves
t1950's candidate-and-ownership lines **intact** into `owned_lookup_session`,
and does not touch `_sessions_owned_by` / `_collect_live_roots`. t1950 has
finished implementing, so no seam note is needed.

The review concern was uncommitted edits made by a concurrent session in the
shared checkout, which neither `git log` nor task status reveals. It is covered
by the pre-phase guard below. That guard works on pending diffs, not only on
commits, and it covers every session.

## Implementation

### Pre-phase (risk mitigations)

1. [t1950_rebase_check] Shared-checkout guard on the six files this task edits
   (`agent_launch_utils.py`, `aitask_board.py`, `tui_switcher.py`,
   `test_pick_command_screen.py`, `test_board_dialog_run_dispatch.py`,
   `test_tui_switcher_agent_launch.py`):
   - **Before the first edit:**
     - run `git status --short -- <files>` and `git log ce52aac6a..HEAD -- <files>`;
     - read t1950's status.
     - A pending diff in any of them belongs to another session. **Stop and ask
       the user** to sequence; never edit over it.
     - A new commit means re-reading that file before editing it.
   - **After my edits, and again immediately before the Step 8 commit:**
     - `git diff -- <files>` must contain only this task's hunks. Save my diff to
       the scratchpad right after implementing and compare it with
       `diff <(git diff -- <files>) <scratch>/t1951.diff`.
     - Any foreign hunk means **stop and ask**. `git commit -- <paths>` takes the
       whole worktree file, so a foreign hunk would ride along under this task's
       message.
     - Also re-run `git log <start>..HEAD -- <files>`. A file committed by
       someone else under my edits fails the comparison too.

### 1. `.aitask-scripts/lib/agent_launch_utils.py`

Split the current (post-t1950) `focus_existing_agent_window` into three
functions:

```python
def owned_lookup_session(project_root: Path) -> str | None:
    """The one session a same-project window lookup may search, or None.

    The caller's own session when current_tmux_session() verifies it, else the
    configured default_session — each only if discovery roots it in
    project_root (one gateway hosts every project; every project defaults to
    `aitasks`). Only those two candidates are attributed (t1950). None means:
    search nothing, let the caller launch.
    """
    candidates = (current_tmux_session(),
                  load_tmux_defaults(project_root)["default_session"])
    owned = _sessions_owned_by(project_root, candidates)
    return next((c for c in candidates if c and c in owned), None)


def focus_existing_window(window_names, project_root: Path) -> bool:
    """Select the first of window_names running in owned_lookup_session(),
    through the gateway. True when one exists; select-window is best-effort."""
    session = owned_lookup_session(project_root)
    if session is None:
        return False
    for name in window_names:
        existing = find_window_by_name(name, session)
        if existing:
            sess, idx = existing
            _TMUX.run(["select-window", "-t", tmux_window_target(sess, idx)])
            return True
    return False


def focus_existing_agent_window(task_id: str, project_root: Path) -> bool:
    # docstring kept (trimmed to the agent-specific part)
    return focus_existing_window(
        (f"agent-pick-{task_id}", f"agent-resume-{task_id}"), project_root)
```

The docstring rationale (why a launch is preferred over a cross-project
suppression) moves to `owned_lookup_session`. Behaviour of
`focus_existing_agent_window` stays the same, call for call. The existing
`FocusExistingAgentWindowTests` patch `alu.find_window_by_name`,
`alu._collect_live_roots` (t1950's stub), `alu.load_tmux_defaults` and `alu._TMUX.run`.
All four are still resolved through the module namespace, so those tests stay
green unchanged.

### 2. `.aitask-scripts/board/aitask_board.py` — `_launch_brainstorm`

Replace the session probe, `find_window_by_name` and the raw `Popen` with:

```python
window_name = f"brainstorm-{num}"
if focus_existing_window((window_name,), Path.cwd()):
    self.notify(f"Switched to existing brainstorm for t{num}")
    self.refresh_board(refocus_filename=filename)
    return
```

`Path.cwd()` is the same root `_focus_existing_agent_window` passes. Add
`focus_existing_window` to the line-28 import. Drop the `find_window_by_name`
and `tmux_window_target` imports only if no other use remains (grep shows none
after this change). Leave `_current_tmux_session` in place: it still feeds the
detail screen's codebrowser launch (see "Out of scope").

### 3. `.aitask-scripts/lib/tui_switcher.py` — `_detect_current_session`

- Delete `_detect_current_session`.
- Import `current_tmux_session` from `agent_launch_utils`.
- In `action_tui_switcher`, call `session = current_tmux_session()`. The
  `default_session` fallback stays unchanged.
- Decision: the switcher wants **the caller's verified session**, not project
  ownership. The overlay's `session` is the *attached* session: it decides
  whether a selection needs `switch-client` and where the "attached" marker
  goes. That is a property of the caller's client, not of a project.
  - A caller sitting in another project's session legitimately operates on that
    session, and the overlay already offers cross-session navigation.
  - The defect is only the unverified probe, which `current_tmux_session()`
    fixes: a pane on a different server now gets `None` and falls back to the
    configured session, as before.
- Remove `import subprocess` only if nothing else uses it. It is still used
  (lines 669, 757, 904, …), so keep it.

### 4. Tests

- `tests/test_board_dialog_run_dispatch.py` `BrainstormBranchTests`: patch
  `ab.focus_existing_window` (return False) instead of `_current_tmux_session`
  and `find_window_by_name`.
- Add a board wiring test in the same file:
  - When `focus_existing_window` returns True, `_launch_brainstorm` notifies and
    pushes no screen.
  - It is called with `(("brainstorm-42",), Path.cwd())`.
- `tests/test_tui_switcher_agent_launch.py`: change the
  `patch.object(ts, "_detect_current_session", …)` target to
  `ts.current_tmux_session`. Add a test that `action_tui_switcher` falls back to
  the configured `default_session` when `current_tmux_session` returns None.
- `tests/test_pick_command_screen.py`:
  - Unit test for `focus_existing_window` with brainstorm names. It reuses the
    `FocusExistingAgentWindowTests` setUp: an owned session holding
    `brainstorm-42` is selected through the gateway, and another project's is
    not.
  - `LiveTwoServerTests` additions, in the same style as the existing tests:
    - (a) A caller in project B's gateway session where B holds `brainstorm-42`:
      `focus_existing_window(("brainstorm-42",), root_a)` is False and B's
      active window stays `main`.
    - (b) A caller on the other server: the switcher's `current_tmux_session()`
      is None, so it never adopts the gateway's "best" session `projB`. This
      exercises the switcher's actual input.
    - (c) Positive control: an owned `projA` with `brainstorm-42` becomes
      active.

### Post-phase (risk mitigations)

1. [switcher_ownership_confirm] Add a live test to `LiveTwoServerTests`
   (`tests/test_pick_command_screen.py`) that pins the switcher's decision:
   - setup: the caller is a verified gateway pane in project B's session
     (`projB`), and the configured default is `projA`;
   - expected: `tui_switcher.TuiSwitcherMixin.action_tui_switcher` (with
     `push_screen` / `notify` mocked and `ts._TMUX` rebuilt onto the private
     socket) pushes an overlay whose `_attached_session == "projB"`. The
     attached session is the caller's client session, not the project-owned
     one.
   - A companion assertion with the caller on the other server shows the
     overlay attached to the configured `projA`, never the gateway's "best"
     `projB`.

## Verification

- `python3 -m pytest tests/test_pick_command_screen.py tests/test_board_dialog_run_dispatch.py tests/test_tui_switcher_agent_launch.py -q`
  (or `bash tests/run_all_python_tests.sh --test-dir …`).
- `bash tests/test_no_raw_tmux.sh` (board's raw `select-window` is gone; still passes).
- `bash tests/test_tui_switcher_brainstorm_session.sh`.
- Full `bash tests/run_all_python_tests.sh`; read only the last banner line.

## Out of scope (record as upstream defect in Final Notes)

- `aitask_board.py:1174` `_current_tmux_session` (raw ambient `#S`) still feeds
  `TaskDetailScreen`'s codebrowser `launch_or_focus_codebrowser(session, …)`.
  That path has the same unverified-session class of defect. Changing it alters
  codebrowser launch semantics for off-gateway callers, so it is not part of
  this task.

## Step 9

Current-branch profile (fast): no merge. Commit code (`bug: … (t1951)`) and the
plan separately, then archive via `aitask_archive.sh 1951`.

## Risk

### Code-health risk: low
- Shared checkout: another session (t1950 was one; it has now landed as `ce52aac6a`) can hold uncommitted edits in the files this task edits. Those edits would be overwritten, or absorbed by the path-scoped commit, and neither `git log` nor task status reveals them. · severity: low (residual — addressed by inline pre-phase t1950_rebase_check: pending-diff check before editing, foreign-hunk diff comparison before committing) · → mitigation: inline pre-phase t1950_rebase_check
- Patch-point drift: existing tests patch `ab._current_tmux_session` / `ab.find_window_by_name` / `ts._detect_current_session`. `patch.object` on a removed attribute raises, so the drift fails loudly; step 4 updates those patches. · severity: low · → mitigation: none

### Goal-achievement risk: low
- The switcher deliberately takes "caller's verified session" without project ownership. If ownership were wanted there, the fix would be partial. The rationale is recorded in step 3. · severity: low (residual — pinned by inline post-phase switcher_ownership_confirm) · → mitigation: inline post-phase switcher_ownership_confirm

### Planned mitigations
- timing: pre-phase | name: t1950_rebase_check | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — concurrent edits in the shared checkout | desc: before editing, refuse to edit over pending diffs or unseen commits in the touched files; before committing, verify the diff holds only this task's hunks
- timing: post-phase | name: switcher_ownership_confirm | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — switcher session semantics | desc: live test pinning that the switcher's attached session is the caller's verified session, and the configured fallback when the caller is off-gateway
