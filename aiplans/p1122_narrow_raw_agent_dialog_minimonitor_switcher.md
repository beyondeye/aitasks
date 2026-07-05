---
Task: t1122_narrow_raw_agent_dialog_minimonitor_switcher.md
Worktree: (current branch — profile 'fast')
Branch: (current)
Base branch: main
---

# Plan: Narrow-adapt the raw-agent dialog in the minimonitor TUI switcher

## Context

In `ait minimonitor`, opening the TUI switcher (`j`) and pressing `e` ("Code
Agent") launches a **raw agent** — a bare code agent with no task / no
`/aitask-*` slash command. The dialog it opens (`AgentCommandScreen`) renders in
its **full-width** layout, which overflows the minimonitor's narrow pane. A
narrow, small-pane-adapted variant of that exact dialog already exists and is
used by minimonitor's *other* flows (pick / sibling / concern), which all pass
`narrow=True`. The raw-agent launch is the one call site that forgot it.

The fix is not simply "pass `narrow=True`": the TUI switcher is **shared across
all TUIs** via `TuiSwitcherMixin` (board, full monitor, minimonitor…), so the
dialog must adapt only when the switcher is hosted in a narrow pane. Passing
`narrow=True` unconditionally would wrongly stack the dialog in the wide TUIs.

## Approach: host-declared narrow hook (mirrors the existing `_switcher_selected_session` precedent)

The switcher already has an established pattern for host-specific customization:
`TuiSwitcherMixin._switcher_selected_session()` (default `None`) is **overridden
by minimonitor** and threaded into the `TuiSwitcherOverlay` constructor by
`action_tui_switcher`. We add a parallel `_switcher_narrow()` hook the same way —
explicit, host-declared, drift-resistant (a future narrow host opts in
explicitly), and free of any magic width threshold.

Flow: `MinimonitorApp._switcher_narrow() → True` → `action_tui_switcher` passes
`narrow=` into `TuiSwitcherOverlay(...)` → stored as `self._narrow` → consumed by
`action_shortcut_agent` when constructing `AgentCommandScreen(..., narrow=self._narrow)`.

## Changes

### 1. `.aitask-scripts/lib/tui_switcher.py`

**a. `TuiSwitcherMixin` — add the hook (near `_switcher_selected_session`, ~L1334):**
```python
def _switcher_narrow(self) -> bool:
    """Whether the switcher's dialogs should use the narrow (small-pane)
    layout. Override in subclasses hosted in a narrow tmux pane (minimonitor).
    Default False — the wide TUIs (board, full monitor) keep the full layout.
    """
    return False
```

**b. `TuiSwitcherMixin.action_tui_switcher` (~L1344) — thread it into the overlay,
exactly like `selected` is threaded today:**
```python
selected = self._switcher_selected_session()
narrow = self._switcher_narrow()
self.push_screen(TuiSwitcherOverlay(
    session=session, current_tui=current, selected_session=selected,
    narrow=narrow,
))
```

**c. `TuiSwitcherOverlay.__init__` (~L459) — accept & store the flag:**
- Add `narrow: bool = False` to the signature (after `selected_session`).
- Store `self._narrow = narrow` in the body (alongside `self._current_tui`, etc.).

**d. `TuiSwitcherOverlay.action_shortcut_agent` (~L1171) — pass it through:**
```python
screen = AgentCommandScreen(
    "Launch Code Agent (no task)",
    full_cmd,
    "",  # empty prompt — no task / no slash command
    default_window_name=window_name,
    project_root=project_root,
    operation="raw",
    operation_args=[],
    default_agent_string=agent_string,
    narrow=self._narrow,   # NEW — narrow layout when hosted in a small pane
)
```
This is the only in-pane dialog the switcher opens (explore/create fire-and-forget
via `_spawn_in_session`; git opens a separate window), so it is the only call site.

### 2. `.aitask-scripts/monitor/minimonitor_app.py`

Override the hook on `MinimonitorApp`, next to the existing
`_switcher_selected_session` override (~L852):
```python
def _switcher_narrow(self) -> bool:
    """Minimonitor lives in a narrow tmux pane — its switcher dialogs use
    the small-pane layout, matching the pick/sibling/concern dialogs."""
    return True
```

### 3. `tests/test_tui_switcher_agent_launch.py` — regression + negative control

Extend the existing construction-spy test (which already inspects the pushed
`AgentCommandScreen`). `AgentCommandScreen` stores `self._narrow` (agent_command_screen.py:397).

- **Regression (narrow host):** build the overlay with `narrow=True`
  (`ts.TuiSwitcherOverlay(session="s1", narrow=True)`), run `action_shortcut_agent`,
  assert the pushed `screen._narrow is True`.
- **Negative control (wide host):** default overlay (`narrow=False`), assert the
  pushed `screen._narrow is False` — proves the dialog does NOT stack for board /
  full monitor. This exercises both halves of the seam.
- **Seam oracle (both halves):** unit-assert `TuiSwitcherMixin._switcher_narrow`
  returns `False` for the base mixin and that `MinimonitorApp._switcher_narrow`
  returns `True`, and that `action_tui_switcher` threads the value into the
  overlay constructor (patch `push_screen`, assert the overlay it pushes carries
  `_narrow == _switcher_narrow()`). This pins the decision at the real entry point
  (`action_tui_switcher`), not just the leaf.

## Out of scope (noted, not fixed here)

- The switcher **overlay panel itself** (`#switcher_dialog { width: 44 }`,
  tui_switcher.py:401) is wider than the 40-col minimonitor target pane. That is a
  pre-existing, separate concern about the switcher list, not the raw-agent
  `AgentCommandScreen` this task targets. Not touched.

## Risk

### Code-health risk: low
- None identified. The change is an opt-in `narrow` param defaulting to `False`, so
  every existing call site and every other switcher host is behaviorally unchanged;
  it copies the proven `_switcher_selected_session` threading pattern (no new
  abstraction); blast radius is 3 files with a one-method/one-param addition each.

### Goal-achievement risk: low
- None identified. `AgentCommandScreen(narrow=...)` is the same, already-tested
  mechanism minimonitor's other dialogs use (test_agent_command_dialog_narrow.py),
  and the host-declared hook covers both required outcomes (narrow in minimonitor,
  wide elsewhere) with a direct test for each.

## Cross-agent note

Pure Python TUI change — no skill-markdown surface — so no Codex/OpenCode port is
needed.

## Verification

1. **Unit tests:**
   ```bash
   python3 tests/test_tui_switcher_agent_launch.py
   python3 tests/test_agent_command_dialog_narrow.py   # unchanged — sanity
   ```
2. **Lint / import sanity:**
   ```bash
   python3 -c "import sys; sys.path.insert(0, '.aitask-scripts/lib'); import tui_switcher"
   python3 -c "import sys; sys.path.insert(0, '.aitask-scripts/monitor'); sys.path.insert(0, '.aitask-scripts/lib'); import minimonitor_app"
   ```
3. **Live manual check (the true acceptance surface — TUI layout):**
   - In a minimonitor pane, press `j` then `e` → the "Launch Code Agent (no task)"
     dialog appears with rows **stacked vertically** (narrow layout), fitting the pane.
   - In a wide TUI (`ait board` or full `ait monitor`), press `j` then `e` → the
     dialog stays in its **full-width** layout (no regression).

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned. Added
  `TuiSwitcherMixin._switcher_narrow()` (default `False`), threaded
  `narrow=self._switcher_narrow()` through `action_tui_switcher` into
  `TuiSwitcherOverlay.__init__` (new `narrow` param, stored as `self._narrow`),
  and passed `narrow=self._narrow` to the raw-agent `AgentCommandScreen` in
  `action_shortcut_agent`. `MiniMonitorApp` overrides `_switcher_narrow()` → `True`.
- **Deviations from plan:** The plan referenced the class as `MinimonitorApp`;
  the real class is `MiniMonitorApp` (the code edit was content-anchored, so the
  source is correct — only the seam-oracle test's class reference was corrected).
- **Issues encountered:** `minimonitor_app.py` had a pre-existing, unrelated
  uncommitted change in the working tree (a `capture_all_async` None-guard,
  t1111_4) from a concurrent session. Staged only the `_switcher_narrow` hunk
  (via `git apply --cached` of that single hunk) so the t1122 commit did not
  sweep up the other session's in-progress work; the t1111_4 change remains
  unstaged in the working tree.
- **Key decisions:** Chose the host-declared hook over a magic width threshold —
  explicit, drift-resistant, and a direct mirror of the existing
  `_switcher_selected_session` threading.
- **Upstream defects identified:** None.

## Step 9 (Post-Implementation)

After implementation: run the verification above, then follow task-workflow Step 8
(commit) and Step 9 (review, merge to current branch is a no-op on `fast`, archive
the task + plan). Commit type: `bug`, message referencing `(t1122)`.
