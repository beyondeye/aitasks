---
Task: t1282_minimonitor_i_task_info_shortcut_cant_reach_pinned_own_agent.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1282 — minimonitor: reach the pinned followed agent's task info

## Context

In `ait minimonitor`, `i` opens the task detail dialog for an agent. Since the
refactor that moved the **followed** agent (the code agent sharing the
minimonitor's tmux window) out of the selectable list into the pinned,
non-focusable `#mini-own-agent` panel, there is no way to see task info for that
agent — the only workaround is switching to another code-agent window and
selecting it from there.

`action_show_task_info` (`.aitask-scripts/monitor/minimonitor_app.py:1506`)
resolves its target only through `_get_focused_pane_id()` (`:838`), which returns
a pane id only when `self.focused` is a `MiniPaneCard`. `_rebuild_pane_list`
(`:692`) explicitly excludes the own pane from the cards (`:703-709`) and
`_maybe_build_own_agent_panel` (`:670`) renders it as plain, non-focusable
`Static`s — so focus can never resolve the followed agent.

**A "no card focused" fallback would not fix this.** `_auto_select_own_window()`
(`:538`) focuses the first list card on mount, on refresh-restore and on
`on_app_focus`, so whenever any other agent exists a list card is always focused;
the fallback would only ever fire in the single-agent case. The fix therefore
needs its own target, not a fallback: **a dedicated key that is always scoped to
the followed agent** — the same shape as `k` (`action_kill_own_agent`, `:879`)
and `n` (`action_pick_next_for_own`, `:921`), and the same lower/upper pairing as
`e` / `E` (shadow / shadow-with-picker).

Outcome: `I` (Shift+i) shows task info for the followed agent, from anywhere;
`i` keeps its focused-card semantics unchanged and the pinned panel stays
non-selectable.

## Approach

### 1. `.aitask-scripts/monitor/minimonitor_app.py`

**Binding** — add next to the existing `i` row (`:197`):

```python
Binding("i", "show_task_info", "Task Info", show=False),
Binding("I", "show_own_task_info", "Task Info (followed)", show=False),
```

**Extract the shared dialog body** from `action_show_task_info` (`:1506`) so both
actions use one path (cache invalidate → `get_task_info` → `push_screen`), and
neither duplicates the "no task id" / "not found" warnings:

```python
def _show_task_info_for(self, snap: PaneSnapshot) -> None:
    """Open the task detail dialog for `snap`'s pane, refreshing the cache.

    Shared by `i` (focused list card) and `I` (followed agent) — same dialog,
    two different target resolutions.
    """
    task_id = self._task_cache.get_task_id_for_pane(snap.pane)
    if not task_id:
        self.notify("No task ID in window name", severity="warning")
        return
    sess = snap.pane.session_name
    self._task_cache.invalidate(task_id, sess)   # force-refresh for latest content
    info = self._task_cache.get_task_info(task_id, sess)
    if not info:
        self.notify(f"Task t{task_id} not found", severity="error")
        return
    self.push_screen(TaskDetailDialog(info))
```

`action_show_task_info` keeps its current resolution and warning verbatim, then
delegates. The new action mirrors `action_kill_own_agent`'s resolution and
warning wording:

```python
def action_show_own_task_info(self) -> None:
    """Show task info for the agent this minimonitor follows.

    The followed agent lives in the static, non-focusable #mini-own-agent
    panel, so the focus-scoped `i` can never reach it (t1282). Scoped to the
    followed agent regardless of which list card is focused — same resolution
    as action_kill_own_agent / action_pick_next_for_own.
    """
    snap = self._find_own_agent_snapshot()
    if snap is None:
        self.notify("No followed agent in this window", severity="warning")
        return
    self._show_task_info_for(snap)
```

**Key-hints panel** (`compose`, `:269-277`) — the hint block is a hard-coded
`Static`; add `I` to it. Insert as its own short row rather than extending the
25-char first row, so nothing wraps in the narrow (~38 usable cols) side column:

```
"i:info  q:quit  tab:agent\n"
"I:info (followed agent)\n"
"s/↑↓:switch  enter:send\n"
...
```

The exact wording is confirmed against the live widget render at the configured
width during implementation (`_target_width` default 40, padding `0 1`), not
assumed.

No changes to focus handling, `_rebuild_pane_list`, the own-agent panel, or
`action_switch_to` — `s` on the followed agent would switch to the window the
minimonitor already lives in, so it stays focus-scoped.

### 2. `tests/test_minimonitor_task_info_fallback.py` (new)

Mock-based, no live tmux — same style as `tests/test_minimonitor_shadow_pick.py`
(real class via `MiniMonitorApp.__new__`, stub `_task_cache`, spy `notify` /
`push_screen`). Auto-discovered by `tests/run_all_python_tests.sh`. Cases:

1. **Binding registered** — `("I", "show_own_task_info")` is in `BINDINGS`, and
   the `("i", "show_task_info")` row is still present (negative control).
2. **`I` reaches the followed agent** — own snapshot resolvable while a
   *different* list card is focused → `push_screen` gets a `TaskDetailDialog`
   built from the **own** pane's task id. This is the regression the task
   describes; the distinct focused card is what proves focus doesn't win.
3. **`i` unchanged** — focused card → dialog for the focused pane, not the own
   agent (asserted via distinct task ids per pane).
4. **No followed agent** — `_find_own_agent_snapshot()` returns `None` →
   "No followed agent in this window" warning, nothing pushed.
5. **Followed pane has no task id** → "No task ID in window name" warning.
6. **Hint-panel render** — assert the rendered `#mini-key-hints` text advertises
   `I` and that no line exceeds the usable width at `_target_width` 40 (render
   `.plain`, per the repo's TUI render-level verification practice).

Negative control: after the tests pass, temporarily point `action_show_own_task_info`
back at `_get_focused_pane_id()` with Edit and confirm case 2 fails, then restore
with Edit (never `git checkout --`, which would wipe uncommitted work).

Existing suites that must stay green: `tests/test_shortcuts_registry_coverage.sh`
(auto-covers the new binding's registration + coherence lint; `show_own_task_info`
is a new action id, not in `SHARED_ACTION_IDS`, so no cross-scope conflict) and
`tests/test_minimonitor_concern_action.py` / `_shadow_pick.py`.

### 3. `website/content/docs/tuis/minimonitor/how-to.md`

- "How to Show Task Info for an Agent" (`:100`) — document both keys: `i` for the
  selected card, `I` for the followed agent pinned at the top (which is never
  selectable, hence its own key).
- Key Bindings Quick Reference (`:207`) — add an `I` row under the `i` row.

## Verification

- `python3 tests/test_minimonitor_task_info_fallback.py` — new test passes.
- `bash tests/run_all_python_tests.sh` — no regressions.
- `bash tests/test_shortcuts_registry_coverage.sh` — new binding registered, lint clean.
- Manual (real tmux pane): launch `ait minimonitor` in an agent window with at
  least one other agent running; press `I` → task detail dialog for the pinned
  agent regardless of which card is highlighted; press `i` → the highlighted
  card's task info; check the hint panel reads correctly without wrapping.

## Risk

### Code-health risk: low
- None identified. The change adds one action + one binding and factors the
  existing dialog body into a shared helper; it reuses `_find_own_agent_snapshot()`
  and the warning wording already established by two sibling own-agent handlers,
  and touches no focus, list-rebuild or panel code.

### Goal-achievement risk: low
- None identified. The premise correction (a list card is always focused, so a
  fallback would be dead code in the general case) is settled, the key choice was
  confirmed with the user, and the regression is directly assertable headlessly
  with a focused *other* card present.
