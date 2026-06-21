---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: enhancement
status: Implementing
labels: [brainstorming, tui, ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
anchor: 1018
implemented_with: claudecode/opus4_8
created_at: 2026-06-21 10:19
updated_at: 2026-06-21 13:16
---

## Context
Child of t1018. Two tightly-coupled UX changes to the **Running tab** of
`ait brainstorm`. Independent of the other children (no shared binding surface),
so it carries no sibling dependency.

**Scope (narrowed from the umbrella body, user-confirmed during planning):**
- **Running-tab operation (GroupRow) only.** The Browse `NodeRow` / DAG-node
  double-click in the original "Child 2" umbrella text is **dropped** from
  t1018_3 (possible later follow-up).
- **Double-click toggles expand/collapse** of the operation group (mirrors the
  `Enter` toggle) — it does **not** open `OperationDetailScreen`.

### Change 1 — Double-click an operation group → expand/collapse
Mouse users had no way to expand a Running-tab group (single-click only focused
it; `Enter` toggled). Double-click now toggles, reusing the Enter path.

### Change 2 (bug fix) — Preserve focus across status refresh
The Running tab rebuilds its rows on a 30 s timer and after every agent action
(`_refresh_status_tab` → `container.remove_children()` → re-mount). The focused
GroupRow was destroyed and focus lost mid-operation. Expansion already survived
via `self._expanded_groups`; focus now survives too. (Coupled with Change 1:
double-clicking to toggle is pointless if the next refresh steals focus.)

### Reference patterns
- `board/aitask_board.py:1263-1273` (`TaskCard.on_click`) — the only
  `event.chain == 2` use in the repo; mirror for the double-click.
- `aitask_board.py` `_refocus_card` — save focused identifier before
  `remove_children()`, re-focus by match after (via `call_after_refresh`).

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` — extract a shared
  `_toggle_group(name)` (repoint the `Enter` handler at it); chain-aware
  `GroupRow.on_click` + `GroupRow.ToggleRequested` message + App handler;
  focus capture/restore in `_refresh_status_tab` + `_refocus_group` helper.

## Implementation Plan (detail in aiplans/p1018/p1018_3_*.md)
1. Capture the focused group's `group_name` before `_refresh_status_tab`'s
   `remove_children()`; restore via `call_after_refresh(self._refocus_group, …)`
   after the rows re-mount (best-effort — no-op if the group vanished).
2. Extract `_toggle_group(name)` (`_expanded_groups` add/discard +
   `_refresh_status_tab`); point the `Enter` handler at it.
3. Chain-aware `GroupRow.on_click`: `chain == 2` posts `GroupRow.ToggleRequested`
   → App `_toggle_group`; single-click only focuses.
4. Out of scope: `OperationDetailScreen` on double-click, Browse `NodeRow` /
   DAG-node double-click, `OperationRow.on_click`.

## Verification
- Pilot tests (`tests/test_brainstorm_group_dblclick_focus.py`): synthetic
  `Click` `chain == 2` on a GroupRow toggles `_expanded_groups`; `chain == 1`
  only focuses; `Enter` still toggles (extraction regression); focus survives a
  `_refresh_status_tab` rebuild; a vanished focused group degrades gracefully.
- Full brainstorm suite green.
- **Live verification** (real terminal mouse double-click through tmux; focus
  retained across a real status refresh) is covered by the aggregate **t1018_4**
  manual-verification sibling — synthetic `Click` events in the headless driver
  do not exercise real terminal→tmux mouse delivery.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-21T10:16:11Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-21T10:16:13Z status=pass attempt=1 type=machine
