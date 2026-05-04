---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Implementing
labels: [tui, scripts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-04 10:13
updated_at: 2026-05-04 10:29
---

## Goal

Hide context-irrelevant keyboard shortcuts from the `ait syncer` TUI footer
based on which row is currently selected (`main` vs `aitask-data`), so the
footer shows only the operations that are actionable in the current context.

## Motivation

Today the syncer footer always shows all five action bindings (`r`, `s`, `u`,
`p`, `f`), even though `s` (Sync data), `u` (Pull), and `p` (Push) are
context-dependent: each action handler guards itself with a row-name check and
emits a notify warning ("Sync (s) is for aitask-data only", etc.) when invoked
on the wrong row. The intent is already row-scoped — the footer just doesn't
reflect it, so users see five operations, press one that doesn't apply, and
get a corrective toast. Hiding the inapplicable bindings makes the actionable
set obvious without a press-and-correct cycle.

## Per-row applicability

| Binding | Action          | Applies to              |
|---------|-----------------|-------------------------|
| `r`     | refresh         | always                  |
| `s`     | sync_data       | only when `aitask-data` row is selected |
| `u`     | pull            | only when `main` row is selected        |
| `p`     | push            | only when `main` row is selected        |
| `f`     | toggle_fetch    | always                  |
| `q`     | quit            | always                  |
| `j`     | tui_switcher    | always (already `show=False`)           |
| `a`     | agent_resolve   | already `show=False` (only enabled when there's a recent failure) |

## Implementation Sketch

Files: `.aitask-scripts/syncer/syncer_app.py`

1. **Add `check_action(action, parameters) -> bool | None`** to `SyncerApp`,
   following the canonical Textual idiom already used in `monitor_app.py:1256`
   and `aitask_board.py:3333`. Return `None` to hide the binding from the
   footer (and prevent firing). Logic:

   ```python
   def check_action(self, action: str, parameters) -> bool | None:
       selected = self._selected_ref_name()
       if action == "sync_data" and selected != "aitask-data":
           return None
       if action in ("pull", "push") and selected != "main":
           return None
       return True
   ```

2. **Refresh bindings on row change** — extend `on_data_table_row_highlighted`
   (line 243) to call `self.refresh_bindings()` after `self._refresh_detail()`,
   matching the pattern in `monitor_app.py:1242`.

3. **Drop the now-dead notify guards** inside `action_sync_data` (250),
   `action_pull` (258), and `action_push` (267). When `check_action` returns
   `None` for a binding, Textual prevents the action from firing, so the
   `if self._selected_ref_name() != …` blocks become unreachable. The action
   bodies should reduce to the worker-launch line (e.g.,
   `self._sync_data_worker()`), with a comment noting that row-scoping is
   enforced by `check_action`.

4. **Initial render** — `on_mount` already calls `self.action_refresh` via
   `self.call_later`. After mount, the DataTable cursor lands on row 0
   (`main`); confirm `check_action` evaluates correctly on the first footer
   render. If the footer renders before `on_mount` completes, add a
   `self.refresh_bindings()` at the end of `on_mount`.

## Acceptance

- Launch `ait syncer`. Footer on `main` row shows: Refresh, Pull, Push,
  Fetch on/off, Quit (no Sync). Footer on `aitask-data` row shows: Refresh,
  Sync (data), Fetch on/off, Quit (no Pull/Push).
- Switching rows with ↑/↓ updates the footer immediately.
- The dead notify-warnings ("Sync (s) is for aitask-data only" etc.) are gone
  from the source.
- No regressions: refresh, fetch toggle, sync data, pull, push, quit, and the
  `j` TUI switcher all continue to work for their applicable rows.

## Testing

Manual TUI verification (the syncer is a Textual TUI; existing aitasks tests
do not cover footer rendering). Spot-check the four scenarios above. No
automated test required unless a snapshot test for the footer is straight-
forward to add — defer that to a sibling refactor task if so.

## Out of Scope

- The `a` (agent_resolve) binding is already correctly gated via
  `show=False` and only made meaningful when `_last_failure` is set. No
  change needed there.
- The behavior of the action handlers themselves — only the row-context
  guard cleanup is in scope.
- Snapshot tests for footer state — defer if not trivial.
