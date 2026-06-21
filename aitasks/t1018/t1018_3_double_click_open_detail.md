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
Child of t1018. Add **double-click → open detail** on operation/node rows in
`ait brainstorm`. Independent of the other children (no shared binding surface),
so it carries no sibling dependency.

Today detail opens only via keys: `o` opens the `OperationDetailScreen`, and (on
a NodeRow) `Enter` opens the **NodeHub** modal. There is **no double-click
handler** anywhere in the brainstorm TUI.

### Verified current state (post-t983)
- `OperationDetailScreen` (`brainstorm_app.py:1601`) is pushed via the
  `OperationOpened` message, posted by `NodeRow.action_open_operation`
  (`:2553-2574`, bound to `o` at `:2522-2524`) and by
  `DAGDisplay.action_open_operation` (`brainstorm_dag_display.py:816`); App
  handlers at `brainstorm_app.py:8062-8069` (NodeRow) and `:8007-8014` (DAG).
- **`Enter` and `o` now diverge** (the umbrella body predates this): on a NodeRow,
  `Enter` → `action_open_node_detail` (`:6024-6040`) opens the **NodeHub** modal
  (which itself offers Operations/Compare); `o` → `OperationDetailScreen`. On a
  Running-tab `GroupRow`, `Enter` only **expand/collapses** (`:5838-5847`) — no
  detail. On a `StatusLogRow`, `Enter` opens `LogDetailModal` (`:5848-5852`).
- `NodeRow` has **no `on_click`** (inherits default Static focus). `OperationRow`
  has an `on_click` (`:2808-2812`) that posts `Activated` (single-click only, no
  `chain` inspection; used in wizard/session-lifecycle lists, not Browse).
  `DAGDisplay._handle_click` (`brainstorm_dag_display.py:675-705`) single-click
  focuses a node; `_DAGStatic.on_click` forwards coords (`:456-460`).
- **Reference double-click pattern:** the ONLY `event.chain == 2` use in the
  codebase is `board/aitask_board.py:1263-1273` (`TaskCard.on_click`:
  double-click expands, single-click opens details). Mirror it.

## Per-surface behavior (decide/confirm in plan)
Because `Enter` and `o` diverge, "match the Enter/o behavior" must be resolved
per surface. Recommended:
- **Browse NodeRow / DAG node** → double-click opens the **NodeHub** (matches
  `Enter`, the node's primary detail entry). Add `NodeRow.on_click` (new) and
  extend `DAGDisplay._handle_click` to check `event.chain == 2`.
- **Running-tab GroupRow** → double-click opens the **OperationDetailScreen**
  (the detail that `Enter` does NOT open — `Enter` only expand/collapses).
Single-click behavior (focus / expand-collapse) is unchanged.

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` — add `NodeRow.on_click`
  (chain-aware), `GroupRow.on_click` (chain-aware → OperationDetailScreen);
  reuse the existing `OperationOpened` / NodeHub / OperationDetailScreen push
  paths rather than duplicating.
- `.aitask-scripts/brainstorm/brainstorm_dag_display.py` — extend `_handle_click`
  (`:675-705`) to detect `event.chain == 2` and post the detail-open message;
  ensure single-click focus still works.

## Reference Files for Patterns
- `board/aitask_board.py:1263-1273` — the canonical `event.chain == 2` pattern.
- `aidocs/framework/tui_conventions.md`, `aidocs/framework/tmux_gateway.md`.

## Implementation Plan (detail in aiplans/p1018/p1018_3_*.md)
1. Add chain-aware `on_click` to `NodeRow`: `chain == 2` → post the same message
   `Enter` triggers (NodeHub); else default focus.
2. Add chain-aware `on_click` to `GroupRow`: `chain == 2` → open
   OperationDetailScreen for the group's operation; else preserve focus/expand.
3. Extend `DAGDisplay._handle_click` for `chain == 2` on a node box → same as
   NodeRow double-click; single-click still focuses.
4. Keep `OperationRow.on_click` single-click semantics unchanged (out of scope).

## Verification
- `pilot.press`/click-simulation tests: synthesize a `Click` with `chain == 2`
  on NodeRow / GroupRow / DAG node and assert the correct screen/modal is pushed;
  `chain == 1` preserves focus/expand. Follow the board double-click test if one
  exists.
- Full brainstorm suite green.
- **Live mouse double-click verification** (real terminal mouse events through
  tmux) is covered by the aggregate **t1018_4** manual-verification sibling —
  synthetic `Click` events in the headless driver do not exercise real
  terminal→tmux mouse delivery.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-21T10:16:11Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-21T10:16:13Z status=pass attempt=1 type=machine
