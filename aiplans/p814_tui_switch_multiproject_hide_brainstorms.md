---
Task: t814_tui_switch_multiproject_hide_brainstorms.md
Base branch: main
plan_verified: []
---

# t814 — TUI switcher: brainstorm sessions mis-attributed across tmux sessions

## Context

In multi-session mode, the TUI switcher overlay (`TuiSwitcherOverlay`) lets the
user cycle between aitasks tmux sessions with Left/Right; the window list below
refreshes to the SELECTED session's windows. Task 814 reports two symptoms:

- **Bug 1:** Open the switcher from a window in `aitasks-mobile`, select the
  `aitasks` session → `aitasks`' brainstorm sessions are *not visible*.
- **Bug 2:** Open the switcher from a window in `aitasks`, the `aitasks`
  brainstorm shows up under *both* the `aitasks` and `aitasks-mobile` window
  lists.

### Root cause

`_discover_brainstorm_sessions()` (`.aitask-scripts/lib/tui_switcher.py:174`)
scans `Path(".aitask-crews")` — a path **relative to the running Python
process's cwd**, i.e. the attached session's project root. It takes no
session/project argument, so its result is identical no matter which session
is currently selected in the overlay.

`_populate_list_for(session)` correctly recomputes per-session state on every
Left/Right cycle — `get_tmux_windows(session)` for running windows and
`session_project_root = self._project_root_for_session(session)` (line 553) —
but at line 566 it calls `_discover_brainstorm_sessions()` with no argument, so
the on-disk brainstorm entries always come from the *attached* session's
`.aitask-crews/`.

This single defect explains both symptoms:
- Bug 1 — selecting `aitasks` from `aitasks-mobile` still scans
  `aitasks-mobile`'s crews dir, so `aitasks`' on-disk brainstorms are missed.
- Bug 2 — the attached session's crews-dir result is rendered unchanged for
  *every* selected session, so the `aitasks` brainstorm leaks into the
  `aitasks-mobile` view.

Running brainstorm *windows* are already attributed correctly: tmux scopes
`get_tmux_windows(session)` to the real session, and any `brainstorm-<N>`
window it returns is added via `self._running_names`. Only the **on-disk
discovery path** is broken.

## Fix

A focused change to make on-disk brainstorm discovery project-root-aware.

### 1. `.aitask-scripts/lib/tui_switcher.py` — `_discover_brainstorm_sessions` (line 174)

Add an optional `project_root` parameter and scan that project's
`.aitask-crews/` instead of the cwd. Mirrors the existing
`project_root or Path.cwd()` fallback pattern already used by `_build_tui_list`
and `_render_desync_line`.

```python
def _discover_brainstorm_sessions(project_root: Path | None = None) -> list[str]:
    """Scan a project's .aitask-crews/crew-brainstorm-*/ for brainstorm sessions.

    ``project_root`` selects which project's ``.aitask-crews/`` is scanned.
    Defaults to ``Path.cwd()`` for legacy callers; the cross-session switcher
    passes the SELECTED session's project_root so the listed brainstorm
    sessions match that session's project (not the attached session's).

    Returns list of task numbers with existing sessions.
    """
    crews_dir = (project_root or Path.cwd()) / ".aitask-crews"
    if not crews_dir.is_dir():
        return []
    ...  # rest unchanged
```

### 2. `.aitask-scripts/lib/tui_switcher.py` — `_populate_list_for` (line 566)

`session_project_root` is already computed at line 553. Pass it through:

```python
brainstorm_sessions = _discover_brainstorm_sessions(session_project_root)
```

No other callers exist (`grep` confirms line 566 is the only call site).

## Test

New file `tests/test_tui_switcher_brainstorm_session.sh`, following the
Tier-1 logic-test pattern of `tests/test_tui_switcher_multi_session.sh`
(sources `tests/lib/venv_python.sh` + `require_no_tmux.sh`, drives a Python
heredoc, parses `KEY:value` lines into an `R` map with `assert_eq`).

Coverage:
- Create two temp project dirs, each with
  `.aitask-crews/crew-brainstorm-<N>/br_session.yaml`.
- `_discover_brainstorm_sessions(proot_a)` returns project A's task nums;
  `_discover_brainstorm_sessions(proot_b)` returns project B's — proving the
  scan follows the passed root.
- `_discover_brainstorm_sessions()` (no arg) scans cwd — regression guard for
  legacy/single-session callers.
- `_populate_list_for("s2")` (selected ≠ attached) calls
  `_discover_brainstorm_sessions` with the selected session's `project_root`
  (`/p2`) — patch `tui_switcher._discover_brainstorm_sessions`,
  `get_tmux_windows`, `_build_tui_list`; mock the overlay's `query_one` to
  return a `MagicMock` list view. This is the end-to-end proof that bugs 1 & 2
  are fixed.

## Files modified

- `.aitask-scripts/lib/tui_switcher.py` — 2 edits (function signature/body +
  call site), plus docstring.
- `tests/test_tui_switcher_brainstorm_session.sh` — new test (executable).

No `.j2`/skill/golden changes (pure Python TUI lib fix) → no golden
regeneration. No new system lib → no `test_scaffold.sh` update.

## Verification

```bash
bash tests/test_tui_switcher_brainstorm_session.sh        # new test
bash tests/test_tui_switcher_multi_session.sh             # regression
bash tests/test_tui_switcher_footer_fit.sh                # regression
python -c "import ast; ast.parse(open('.aitask-scripts/lib/tui_switcher.py').read())"
```

Manual (optional, multi-session): with two aitasks tmux sessions each holding
an on-disk `.aitask-crews/crew-brainstorm-*`, open the switcher (`j`) and cycle
Left/Right — each session's brainstorm entries should appear only under that
session.

## Post-implementation

Per the shared task workflow Step 8 (review), Step 9 (archival), and Step 9b
(feedback).
