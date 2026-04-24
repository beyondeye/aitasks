---
Task: t634_4_minimonitor_multi_session.md
Parent Task: aitasks/t634_tui_session_switcher.md (archived: aitasks/archived/t634/)
Sibling Tasks: aitasks/t634/t634_5_docs_multi_session_polish.md
Archived Sibling Plans: aiplans/archived/p634/p634_1_discovery_and_focus_primitives.md, aiplans/archived/p634/p634_2_multi_session_monitor.md, aiplans/archived/p634/p634_3_two_level_tui_switcher.md
Worktree: (none — working on current branch per profile `fast`)
Branch: main
Base branch: main
---

# p634_4 — Minimonitor multi-session awareness

## Context

t634_2 taught `ait monitor` to observe every active code agent across every aitasks tmux session on the box — one unified list, `── <session> ──` divider row before each session group, `M` runtime toggle, 10 s sessions cache. The per-window minimonitor (`.aitask-scripts/monitor/minimonitor_app.py:190`) was deliberately pinned to `multi_session=False` at that time so the shared `TmuxMonitor` default (`True`) wouldn't silently change minimonitor behavior before this task landed.

This task lifts the pin, adds the `M` keyboard shortcut with identical semantics to the main monitor, and emits a session divider row before each session group — so both TUIs show the same "all active code agents on the box" view. t634_5 follows up with docs.

## Rendering decision (confirmed with user)

Minimonitor multi-session rendering uses **session-divider headers only**, no inline `[project]` tag prefix, and agent rows stay in default color:

```
── projectA ──
 ● agent-t42 (0)  Active
 ● agent-t43 (0)  IDLE 12s
── projectB ──
 ● agent-t10 (0)  Active
```

This is simpler than the main monitor (which also emits an inline magenta tag on each row). Since the tag-prefix machinery (`_build_session_tags`, `_session_tag_prefix`, `_SESSION_TAG_COLOR`) is not needed here, we do **not** touch `monitor_shared.py` or refactor `monitor_app.py`. A future task may do the extraction if/when another TUI needs the tag prefix.

## Files to modify

1. `.aitask-scripts/monitor/minimonitor_app.py` — drop the `multi_session=False` pin, add `M` binding + action, emit session divider rows in the pane list, extend the session bar, update the key hints footer, narrow `_auto_select_own_window` to the own session.
2. `tests/test_multi_session_minimonitor.sh` — new, mock-based Tier 1 only.

No changes to `tmux_monitor.py`, `monitor_app.py`, `monitor_shared.py`, config files, `aitask_ide.sh`, `seed/`, or website docs (t634_5 handles docs).

No config key (matches t634_2 — `M` is the only user-facing control).

---

## Step 1 — Drop the `multi_session=False` pin

`.aitask-scripts/monitor/minimonitor_app.py` at the `_start_monitoring` call site (~lines 187–196):

```python
# BEFORE
# Minimonitor intentionally stays session-local until t634_5 adds its
# own multi-session support. Pin the flag off so the shared TmuxMonitor
# default (True) doesn't silently change behavior here.
self._monitor = TmuxMonitor(
    session=self._session,
    capture_lines=self._capture_lines,
    idle_threshold=self._idle_threshold,
    multi_session=False,
    **kwargs,
)
```

```python
# AFTER — inherit the TmuxMonitor default (True); obsolete comment removed
self._monitor = TmuxMonitor(
    session=self._session,
    capture_lines=self._capture_lines,
    idle_threshold=self._idle_threshold,
    **kwargs,
)
```

## Step 2 — Add the `M` binding + action

Extend `BINDINGS` (line 97):

```python
BINDINGS = [
    Binding("tab", "focus_sibling_pane", "Focus agent", show=False),
    Binding("enter", "send_enter_to_sibling", "Send Enter", show=False),
    Binding("j", "tui_switcher", "TUI switcher", show=False),
    Binding("q", "quit", "Quit", show=False),
    Binding("s", "switch_to", "Switch", show=False),
    Binding("i", "show_task_info", "Task Info", show=False),
    Binding("r", "refresh", "Refresh", show=False),
    Binding("m", "switch_to_monitor", "Full Monitor", show=False),
    Binding("M", "toggle_multi_session", "Multi", show=False),  # NEW
]
```

Textual treats bindings case-sensitively — uppercase `M` (Shift+m) does not collide with lowercase `m` (`action_switch_to_monitor`).

Add the action next to the other `action_*` methods (e.g., immediately after `action_refresh`, around line 495):

```python
def action_toggle_multi_session(self) -> None:
    """Flip the multi-session view ON/OFF in memory.

    Mirrors MonitorApp.action_toggle_multi_session exactly: in-memory only
    (no config write, per the CLAUDE.md runtime TUI rule), invalidates the
    session cache so the first post-toggle refresh re-discovers, and
    schedules a refresh to repaint.
    """
    if self._monitor is None:
        return
    self._monitor.multi_session = not self._monitor.multi_session
    self._monitor.invalidate_sessions_cache()
    state = "ON" if self._monitor.multi_session else "OFF"
    self.notify(f"Multi-session {state}", timeout=3)
    self.call_later(self._refresh_data)
```

Minimonitor does not need a mirror `self._multi_session` attribute — `self._monitor.multi_session` is the single source of truth throughout the codepath (simpler than main monitor, which holds both for constructor-time seeding).

## Step 3 — `_rebuild_pane_list` sort + session dividers

Replace the current body (line 305) with a version that sorts by `(session_name, window_index, pane_index)` and emits a `── <session> ──` divider row before each new session group in multi mode:

```python
async def _rebuild_pane_list(self) -> None:
    container = self.query_one("#mini-pane-list", VerticalScroll)
    await container.remove_children()

    agents = [
        s for s in self._snapshots.values()
        if s.pane.category == PaneCategory.AGENT
    ]
    # Sort by session first so grouping is stable across refreshes. In
    # single-session mode all snapshots share the same session_name, so the
    # key degrades to the legacy (window_index, pane_index) order.
    agents.sort(
        key=lambda s: (s.pane.session_name, s.pane.window_index, s.pane.pane_index)
    )

    multi_mode = bool(self._monitor and self._monitor.multi_session)
    widgets: list = []
    current_session: str | None = None

    for snap in agents:
        # Emit a session divider before each new session group (multi only).
        if multi_mode and snap.pane.session_name != current_session:
            current_session = snap.pane.session_name
            label = current_session or "?"
            widgets.append(Static(
                f"[dim]── {label} ──[/]",
                classes="mini-session-divider",
            ))

        if snap.is_idle:
            idle_s = int(snap.idle_seconds)
            dot = "[yellow]●[/]"
            status = f"[yellow]IDLE {idle_s}s[/]"
        else:
            dot = "[green]●[/]"
            status = "[green]ok[/]"

        name = snap.pane.window_name
        max_name = 22
        if len(name) > max_name:
            name = name[:max_name - 1] + "…"

        line1 = f"{dot} {name}  {status}"

        task_id = self._task_cache.get_task_id(snap.pane.window_name)
        if task_id:
            info = self._task_cache.get_task_info(task_id)
            if info:
                title = info.title
                if len(title) > 30:
                    title = title[:29] + "…"
                line1 += f"\n  [dim]{title}[/]"

        widgets.append(MiniPaneCard(snap.pane.pane_id, line1))

    if widgets:
        await container.mount_all(widgets)
```

Two important correctness notes:

- `container.mount_all` accepts a heterogeneous `list[Widget]` — mixing `Static` dividers with `MiniPaneCard`s is supported.
- Focus navigation (`_nav`, `_restore_focus`, `_auto_select_own_window`, `on_descendant_focus`) uses the selector `"#mini-pane-list MiniPaneCard"`, which excludes the `Static` dividers. Arrow-nav / Tab / focus restoration still work correctly — no divider gets focused and no card is skipped.

Add matching CSS to the `CSS` class constant (around line 64, alongside the existing selectors) so dividers align with the card indentation:

```css
.mini-session-divider {
    height: 1;
    padding: 0 1;
    color: $text-muted;
}
```

## Step 4 — `_rebuild_session_bar` — compact multi-mode title

Replace the current body (line 291):

```python
def _rebuild_session_bar(self) -> None:
    agents = [
        s for s in self._snapshots.values()
        if s.pane.category == PaneCategory.AGENT
    ]
    total = len(agents)
    idle_count = sum(1 for a in agents if a.is_idle)
    idle_str = f" [yellow]{idle_count} idle[/]" if idle_count > 0 else ""
    bar = self.query_one("#mini-session-bar", Static)

    if self._monitor is not None and self._monitor.multi_session:
        sessions = {
            s.pane.session_name for s in agents if s.pane.session_name
        }
        n = len(sessions) if sessions else 1
        bar.update(f"multi: {n}s · {total}a{idle_str}")
    else:
        bar.update(
            f"{self._session}  {total} agent{'s' if total != 1 else ''}{idle_str}"
        )
```

Multi-mode examples at ~40-col width: `multi: 2s · 5a  1 idle` / `multi: 1s · 0a`. The counter reflects unique sessions visible in the snapshot, not the discovery cache, so the bar stays consistent with the pane list even right after a session appears/disappears.

## Step 5 — Key hints footer

Current (line 138):

```python
yield Static(
    "tab:agent  s/↑↓:switch  i:info\n"
    "j:jump     r:refresh  q:quit  enter:send\n"
    "m:full monitor",
    id="mini-key-hints",
)
```

Append `M:multi` on the last line:

```python
yield Static(
    "tab:agent  s/↑↓:switch  i:info\n"
    "j:jump     r:refresh  q:quit  enter:send\n"
    "m:full monitor  M:multi",
    id="mini-key-hints",
)
```

Last line is `m:full monitor  M:multi` = 22 chars — fits the ~40-col layout comfortably.

## Step 6 — Harden `_auto_select_own_window` against cross-session window_index collisions

Current (line 273):

```python
def _auto_select_own_window(self) -> None:
    if not self._own_window_index:
        return
    for card in self.query("#mini-pane-list MiniPaneCard"):
        snap = self._snapshots.get(card.pane_id)
        if snap and snap.pane.window_index == self._own_window_index:
            card.focus()
            return
```

In multi mode, two sessions could each have a pane at `window_index=1`, and the first match would win. Narrow the match to the minimonitor's own session:

```python
def _auto_select_own_window(self) -> None:
    if not self._own_window_index:
        return
    for card in self.query("#mini-pane-list MiniPaneCard"):
        snap = self._snapshots.get(card.pane_id)
        if (
            snap
            and snap.pane.window_index == self._own_window_index
            and snap.pane.session_name in ("", self._session)
        ):
            card.focus()
            return
```

The `in ("", self._session)` check: `session_name == ""` preserves legacy / non-multi paths that don't populate session (e.g., `discover_window_panes` in older code paths — though t634_2 already populates it there too); `session_name == self._session` matches the minimonitor's own session in multi mode.

## Step 7 — `m` handoff to full monitor is unchanged

Per the task's open-implementation-question recommendation: pressing `m` (lowercase, "switch to full monitor") must not mutate the main monitor's `multi_session` flag. The existing `action_switch_to_monitor` already satisfies this — it only sets a tmux env var and selects the monitor window. No code change.

## Step 8 — Tests (`tests/test_multi_session_minimonitor.sh`)

Mock-based Tier 1 only — real-tmux aggregation is covered by `test_multi_session_monitor.sh` (the `TmuxMonitor` aggregation path is identical for both TUIs).

Skeleton (copy `assert_eq` / `assert_contains` from `test_multi_session_monitor.sh`):

```bash
#!/usr/bin/env bash
# test_multi_session_minimonitor.sh — Verify the minimonitor multi-session
# extensions added in t634_4.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LIB_DIR="$PROJECT_DIR/.aitask-scripts/lib"
MONITOR_DIR="$PROJECT_DIR/.aitask-scripts/monitor"

PASS=0; FAIL=0; TOTAL=0
assert_eq() { ...; }
assert_contains() { ...; }
```

Test cases:

1. **`M` binding registered + action exists.**
   ```python
   import minimonitor_app as mm
   keys = [getattr(b, "key", None) or (b[0] if isinstance(b, tuple) else None)
           for b in mm.MiniMonitorApp.BINDINGS]
   print("M_IN_BINDINGS:" + str("M" in keys))
   print("HAS_ACTION:" + str(hasattr(mm.MiniMonitorApp, "action_toggle_multi_session")))
   print("LOWER_M_PRESERVED:" + str("m" in keys))
   ```

2. **Action flips state and invalidates cache.** Use `__new__` + a lightweight fake-monitor stand-in:
   ```python
   class FakeMon:
       multi_session = True
       invalidated = 0
       def invalidate_sessions_cache(self):
           FakeMon.invalidated += 1
   app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
   app._monitor = FakeMon()
   # notify / call_later must not crash when self.app is unbound — patch them
   app.notify = lambda *a, **k: None
   app.call_later = lambda fn: None
   app.action_toggle_multi_session()
   print("AFTER_FLIP:" + str(app._monitor.multi_session))       # False
   print("INVALIDATED:" + str(FakeMon.invalidated))             # 1
   app.action_toggle_multi_session()
   print("BACK_ON:" + str(app._monitor.multi_session))          # True
   print("INVALIDATED_TOTAL:" + str(FakeMon.invalidated))       # 2
   ```

3. **`_start_monitoring` no longer pins `multi_session=False`.** Patch `TmuxMonitor` in `minimonitor_app`'s namespace with a recording stub; construct a `MiniMonitorApp` via `__new__`, minimally populate attributes needed by `_start_monitoring`, invoke it, and assert the recorded kwargs do not contain `multi_session=False`:
   ```python
   recorded = {}
   class RecMon:
       def __init__(self, **kwargs):
           recorded.update(kwargs)
   mm.TmuxMonitor = RecMon
   app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
   app._session = "x"
   app._capture_lines = 30; app._idle_threshold = 5.0
   app._agent_prefixes = None; app._tui_names = None
   app.call_later = lambda fn: None
   app.set_interval = lambda *a, **k: None
   app._refresh_seconds = 3
   app._start_monitoring()
   print("HAS_FALSE_PIN:" + str(recorded.get("multi_session") is False))
   print("NOT_PASSED:" + str("multi_session" not in recorded))
   ```
   Assert `HAS_FALSE_PIN:False` and `NOT_PASSED:True` (preferred — inheriting the default).

4. **`_auto_select_own_window` narrows to own session.** Build two fake snapshots (same window_index, different `session_name`), one matching `self._session`, one not. Using Textual's widget query in a unit test is fragile, so we test the matching predicate in isolation rather than driving the widget tree:
   ```python
   from types import SimpleNamespace
   def would_match(own_window_index, own_session, snap_window_index, snap_session):
       snap = SimpleNamespace(pane=SimpleNamespace(
           window_index=snap_window_index, session_name=snap_session,
       ))
       return (snap.pane.window_index == own_window_index
               and snap.pane.session_name in ("", own_session))
   print("OWN:"        + str(would_match("1", "sA", "1", "sA")))   # True
   print("CROSS:"      + str(would_match("1", "sA", "1", "sB")))   # False
   print("LEGACY_EMPTY:" + str(would_match("1", "sA", "1", "")))   # True
   print("DIFF_INDEX:" + str(would_match("1", "sA", "2", "sA")))   # False
   ```
   The real method body uses the same predicate — a regression-sensitive copy suffices to guard the logic without mocking Textual.

5. **`_rebuild_pane_list` emits a divider row per session group.** Non-trivial because the method is `async` and touches the Textual DOM. Pragmatic approach: stand up a minimal mount-recorder that captures everything passed to `mount_all`, stub the container via `app.query_one`, and invoke the coroutine with `asyncio.run`:
   ```python
   import asyncio
   from types import SimpleNamespace
   calls = []
   class FakeContainer:
       async def remove_children(self): pass
       async def mount_all(self, widgets): calls.append(list(widgets))
   app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
   app.query_one = lambda *a, **k: FakeContainer()
   app._task_cache = SimpleNamespace(get_task_id=lambda w: None, get_task_info=lambda t: None)
   app._monitor = SimpleNamespace(multi_session=True)
   # Two agents in two sessions — expect 4 widgets: [divA, cardA, divB, cardB]
   def mk_snap(sess, wi, pi, pid, name):
       pane = SimpleNamespace(
           category=mm.PaneCategory.AGENT, session_name=sess,
           window_index=wi, pane_index=pi, pane_id=pid, window_name=name,
       )
       return SimpleNamespace(pane=pane, is_idle=False, idle_seconds=0.0)
   app._snapshots = {
       "%1": mk_snap("sA", "1", "0", "%1", "agent-t1"),
       "%2": mk_snap("sB", "2", "0", "%2", "agent-t2"),
   }
   asyncio.run(app._rebuild_pane_list())
   widgets = calls[0]
   print("COUNT:" + str(len(widgets)))                                      # 4
   from textual.widgets import Static
   print("DIV0_IS_STATIC:" + str(isinstance(widgets[0], Static)))          # True
   print("DIV0_NOT_CARD:" + str(not isinstance(widgets[0], mm.MiniPaneCard)))
   print("CARD1:"       + str(isinstance(widgets[1], mm.MiniPaneCard)))
   print("DIV2_IS_STATIC:" + str(isinstance(widgets[2], Static)))
   print("CARD3:"       + str(isinstance(widgets[3], mm.MiniPaneCard)))
   # Single-session mode: no dividers
   app._monitor.multi_session = False
   calls.clear()
   asyncio.run(app._rebuild_pane_list())
   widgets = calls[0]
   print("SINGLE_COUNT:" + str(len(widgets)))                               # 2
   print("SINGLE_NO_DIV:" + str(all(isinstance(w, mm.MiniPaneCard) for w in widgets)))
   ```
   If Textual's `Static` constructor has onerous runtime requirements that break in a headless unittest, fall back to checking `widgets[0].__class__.__name__ == "Static"` and `hasattr(widgets[0], "pane_id") is False`.

6. **Session-bar text reflects multi mode.** Construct an app via `__new__`, populate `_snapshots` + `_monitor`, stub `query_one` to return a capture object, call `_rebuild_session_bar()`, assert the captured text starts with `"multi:"` when `multi_session=True` and with `self._session` otherwise.

Target: 8–12 assertions across the cases above. Zero tmux required.

## Verification

Automated:

```bash
bash tests/test_multi_session_minimonitor.sh
bash tests/test_multi_session_monitor.sh      # regression — must keep passing
bash tests/test_multi_session_primitives.sh   # regression
bash tests/test_tui_switcher_multi_session.sh # regression
shellcheck tests/test_multi_session_minimonitor.sh
python3 -c 'import ast; ast.parse(open(".aitask-scripts/monitor/minimonitor_app.py").read())'
```

Manual (task description §Verification):

1. Start two aitasks projects via `ait ide` — two tmux sessions registered.
2. Inside one project, open a minimonitor (auto-spawned alongside an agent window).
3. Observe: agents from both sessions appear in one list, separated by `── <session> ──` divider rows. Session bar reads `multi: 2s · Na[...]`.
4. Press `M` → notify "Multi-session OFF"; list collapses to own-session agents, no dividers. Session bar reverts to `<session>  N agents`.
5. Press `M` again → "Multi-session ON"; two-session layout restored.
6. Press `m` → switches to the full monitor window. Full monitor's `multi_session` state is unchanged (no implicit toggle). Full monitor still independently controllable via its own `M` binding.
7. Tab/Enter/s/i/r/q all still work as before in both single and multi modes.
8. With the main monitor open in the same session: both TUIs show the same cross-session agent set when their respective `M` toggles are ON.

## Decisions & notes

- **No inline tag prefix, no row coloring.** User-confirmed: minimonitor uses header-only rendering, matching the archived t634_2 notes' lead: "[divider] formatting should be kept consistent if minimonitor adds its own divider rendering." Divider style `[dim]── <label> ──[/]` matches the main monitor's style.
- **Using `session_name` as the divider label** (not `project_name`) — matches what the main monitor emits in `mount_with_session_dividers` today. If the user later prefers prettier project names, that's a coordinated change across both TUIs in a separate task.
- **No shared helpers refactor.** Since the tag-prefix machinery is not used here, we skip the `monitor_shared.py` extraction recommended in the t634_2 post-implementation notes. If a future TUI wants the inline tag, extract then — keeps this change minimal and focused on minimonitor.
- **No new config key** (matches t634_2). `M` is the only user-facing control; built-in default is `True`.
- **Minimonitor does not mirror `_multi_session` on the app.** `self._monitor.multi_session` is the only source of truth — simpler than main monitor, which carries both for constructor-time seeding.
- **`m` handoff to main monitor is untouched** per the task brief's recommended answer to its open implementation question: "only switch focus" — no cross-TUI state mutation.

## Step 9 — Post-implementation

Per the shared workflow:

- Step 8 — `git diff --stat` for review. Commit source files with subject `feature: Add multi-session support to minimonitor (t634_4)`; commit the plan separately via `./ait git`.
- Step 8c — offer a manual-verification follow-up covering the TUI flow (steps 1–8 above).
- Step 9 — archive via `./.aitask-scripts/aitask_archive.sh 634_4`. Parent t634 stays pending until t634_5 (docs polish) also completes; the archive script will auto-archive the parent then.
