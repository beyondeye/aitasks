---
Task: t545_monitor_arrow_key_lost_on_refresh_race.md
Worktree: (none — working on current branch per profile `fast`)
Branch: main
Base branch: main
---

# Plan: Monitor arrow-key loss on refresh race (t545)

## Context

`ait monitor` has a residual race, left over after t544's async-tmux fix: if the
user presses ↑/↓ at the exact moment a refresh tick fires, the keystroke is lost
and the selection does not move. The task file walks through the hypothesis in
detail — the short version is that `_rebuild_pane_list()` unconditionally
tears down every `PaneCard` and mounts fresh ones on every tick (`.aitask-scripts/monitor/monitor_app.py:636`),
so the currently-focused card is destroyed mid-dispatch and the subsequent
`call_after_refresh(self._restore_focus, ...)` (`monitor_app.py:522`) clobbers
any navigation that slipped through.

The fix candidate with the best risk/value ratio is the "diff-based rebuild"
from the task notes: **if the set and order of panes is unchanged** (the common
case — a 3-second tick on a stable tmux session), avoid DOM mutations entirely
and just update card text in place. The focused `PaneCard` persists across
refreshes, so arrow events dispatch against a stable list and cannot be lost.
When the pane set actually changes (new window, closed pane), we fall back to
the existing full rebuild — arrow loss in that rare window is tolerable.

Minimonitor (`.aitask-scripts/monitor/minimonitor_app.py:214`) demonstrates the
async alternative (`await remove_children` + `await mount_all`), but that only
narrows the window — it does not eliminate it, because the key event can still
dispatch between the two awaits onto a transient empty container. The in-place
fast path closes the window fully for the common case with less code.

## Files to modify

- `.aitask-scripts/monitor/monitor_app.py` — add helpers, add fast path, tighten
  `_restore_focus`. No other files are affected. No tests exist for monitor
  today (verified: `tests/test_*monitor*.sh` → none), so this is a manual-
  verification task.

## Implementation

### 1. Extract card-text builders into helpers

The text formatting currently lives inline inside `_rebuild_pane_list()` at
`monitor_app.py:654-683`. Extract two small helpers above `_rebuild_pane_list`,
keeping behavior identical:

```python
def _format_agent_card_text(self, snap: PaneSnapshot) -> str:
    if snap.is_idle:
        idle_s = int(snap.idle_seconds)
        dot = "[yellow]\u25cf[/]"
        status = f"[yellow]IDLE {idle_s}s[/]"
    else:
        dot = "[green]\u25cf[/]"
        status = "[green]Active[/]"
    text = (
        f" {dot} {snap.pane.window_index}:{snap.pane.window_name} "
        f"({snap.pane.pane_index})  {status}"
    )
    task_id = self._task_cache.get_task_id(snap.pane.window_name)
    if task_id:
        info = self._task_cache.get_task_info(task_id)
        if info:
            text += f"\n     [dim italic]t{task_id}: {info.title}[/]"
    return text

def _format_other_card_text(self, snap: PaneSnapshot) -> str:
    return (
        f" [dim]\u25cb[/] {snap.pane.window_index}:{snap.pane.window_name} "
        f"({snap.pane.pane_index})  [dim]{snap.pane.current_command}[/]"
    )
```

These helpers will be used by both the fast path and the slow path, so no
duplication.

### 2. Add fast path to `_rebuild_pane_list()` (`monitor_app.py:636`)

After categorizing and sorting `agents` / `others`, compute the desired pane-id
sequence and compare it with the currently-mounted cards. If they match, do
in-place `.update()` calls and return early:

```python
def _rebuild_pane_list(self) -> None:
    container = self.query_one("#pane-list", VerticalScroll)

    agents: list[PaneSnapshot] = []
    others: list[PaneSnapshot] = []
    for snap in self._snapshots.values():
        if snap.pane.category == PaneCategory.AGENT:
            agents.append(snap)
        elif snap.pane.category == PaneCategory.OTHER:
            others.append(snap)
    agents.sort(key=lambda s: (s.pane.window_index, s.pane.pane_index))
    others.sort(key=lambda s: (s.pane.window_index, s.pane.pane_index))

    # Fast path: same pane set and order → update text in place, no DOM churn.
    # This keeps the focused PaneCard alive across ticks so arrow keypresses
    # that arrive during a refresh still resolve against a stable card list.
    desired_ids = (
        [s.pane.pane_id for s in agents]
        + [s.pane.pane_id for s in others]
    )
    current_cards = [
        w for w in container.children if isinstance(w, PaneCard)
    ]
    current_ids = [c.pane_id for c in current_cards]
    if desired_ids and desired_ids == current_ids:
        # Header counts don't change (len matches), but the agents-section
        # header's AUTO tag can flip via action_toggle_auto_switch(). Update
        # the agents header text too so the "⟳ AUTO" indicator stays in sync.
        headers = [
            w for w in container.children
            if isinstance(w, Static) and not isinstance(w, PaneCard)
        ]
        if agents and headers:
            auto_label = (
                "  [bold yellow]⟳ AUTO[/]" if self._auto_switch else ""
            )
            headers[0].update(
                f"[bold]CODE AGENTS ({len(agents)})[/]{auto_label}"
            )
        by_id = {c.pane_id: c for c in current_cards}
        for snap in agents:
            by_id[snap.pane.pane_id].update(
                self._format_agent_card_text(snap)
            )
        for snap in others:
            by_id[snap.pane.pane_id].update(
                self._format_other_card_text(snap)
            )
        return

    # Slow path (structural change): full rebuild, unchanged from before —
    # arrow loss is tolerable here because the pane set actually changed.
    for widget in list(container.children):
        widget.remove()

    if agents:
        auto_label = "  [bold yellow]⟳ AUTO[/]" if self._auto_switch else ""
        container.mount(Static(
            f"[bold]CODE AGENTS ({len(agents)})[/]{auto_label}",
            classes="section-header",
        ))
        for snap in agents:
            container.mount(PaneCard(
                snap.pane.pane_id,
                self._format_agent_card_text(snap),
            ))

    if others:
        container.mount(Static(
            f"[bold]OTHER ({len(others)})[/]",
            classes="section-header",
        ))
        for snap in others:
            container.mount(PaneCard(
                snap.pane.pane_id,
                self._format_other_card_text(snap),
            ))
```

Notes:
- The slow path collapses to the exact existing body, just routed through the
  helpers for consistency.
- `headers[0]` is the CODE AGENTS header when `agents` is non-empty (mount
  order is agents-header, agent cards, others-header, other cards — confirmed
  by `container.children` mount-order semantics).
- The OTHER header's text is a pure function of `len(others)`, and if
  `len(others)` hasn't changed we would have already taken the fast path, so
  the others header does not need an in-place update here.
- The fast-path `return` skips unnecessary header recreation, which is the
  whole point — no widget is removed or mounted, and the focused card's
  identity is preserved.

### 3. Tighten `_restore_focus()` (`monitor_app.py:610`)

Two small hardening changes, borrowed from `minimonitor_app.py:251-261`:

```python
def _restore_focus(self, pane_id: str | None, zone: Zone) -> None:
    """Re-focus the previously focused widget after a rebuild."""
    if zone == Zone.PREVIEW:
        try:
            self.query_one("#content-preview", PreviewPanel).focus()
        except Exception:
            pass
        return
    # If the user already navigated to a valid PaneCard during this refresh
    # cycle, respect their selection instead of reverting to the saved id.
    focused = self.focused
    if (
        isinstance(focused, PaneCard)
        and focused.pane_id in self._snapshots
    ):
        self._focused_pane_id = focused.pane_id
        return
    if pane_id is None:
        return
    for card in self.query("#pane-list PaneCard"):
        if hasattr(card, "pane_id") and card.pane_id == pane_id:
            card.focus()
            # Widget.focus() is deferred; on_descendant_focus may not fire
            # before the next refresh tick. Set _focused_pane_id directly so
            # the next tick's saved_pane_id reflects the real state.
            self._focused_pane_id = card.pane_id
            return
```

Rationale:
- The "already-focused PaneCard" guard belongs here (not in `_refresh_data`)
  because the check needs to run at the moment focus would otherwise be
  clobbered — i.e. after any deferred handlers have run.
- The direct `self._focused_pane_id = card.pane_id` assignment removes a
  stale-state window that minimonitor already documents (`minimonitor_app.py:259-260`).
- `_refresh_data` itself is unchanged. We intentionally keep
  `call_after_refresh(self._restore_focus, ...)` for the slow-path case where
  the new cards really have just been mounted and need a post-layout tick
  before we can query them.

## Verification

1. **Smoke test the fast path (manual, required):**
   - Run `ait monitor` inside the `aitasks` tmux session (has multiple agent
     panes).
   - Hold ↓ for ~10 seconds, spanning several refresh ticks. The selection
     must advance on every keypress with no "stuck" frames.
   - Hold ↑ back to the top. Same check.
   - Toggle auto-switch with `a` while navigating — the "⟳ AUTO" tag in the
     agents header should appear/disappear correctly.

2. **Smoke test the slow path (manual):**
   - While `ait monitor` is running, open a new tmux window (`C-b c`). The
     new pane should appear in the OTHER section within ~3s.
   - Close the window. It should disappear within ~3s.
   - Selection should be preserved when the pane set is unchanged by the
     close (e.g., closing a pane that wasn't focused).

3. **No regressions in related features:**
   - Auto-switch (`a`): still moves focus to the most-idle agent on each tick.
   - Focus request from minimonitor (`m` from minimonitor): monitor still
     receives the focus-request and jumps to the target card on its next tick.
   - Preview zone Tab/Enter: unaffected (no path changes in these handlers).

4. **Static check:** `python -m py_compile .aitask-scripts/monitor/monitor_app.py`.

## Post-Implementation

Follow Step 9 of `.claude/skills/task-workflow/SKILL.md`:
- User review and approval (Step 8).
- Commit as `bug: Fix monitor arrow-key loss on refresh race (t545)`.
- Archive task via `./.aitask-scripts/aitask_archive.sh 545`.
- Push via `./ait git push`.
