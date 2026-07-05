---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_monitormini, agent_chooser]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-05 10:34
updated_at: 2026-07-05 10:55
---

## Problem

In `ait minimonitor`, opening the TUI switcher (`j`) and pressing `e` ("Code
Agent") launches a **raw agent** (a bare code agent with no task / no
`/aitask-*` slash command). The agent-command dialog it opens is **not** the
narrow, small-pane-adapted variant, so it renders in the full-width layout and
overflows / looks wrong inside the minimonitor's narrow pane.

A narrow-adapted version of this exact dialog already exists and is used by
minimonitor's other flows — so this is a missing `narrow=True` on one call
site, plus the plumbing to decide narrowness only when appropriate.

## Root cause

`action_shortcut_agent` in `.aitask-scripts/lib/tui_switcher.py` (~line 1135)
builds the shared `AgentCommandScreen(...)` at ~line 1171 **without**
`narrow=True`. The `e` key is bound to `shortcut_agent` in the switcher overlay
(`tui_switcher.py:379`, action tuple at `:230`).

By contrast, minimonitor already passes `narrow=True` to the same screen and to
sibling dialogs:
- `_launch_pick_for_own` → `AgentCommandScreen(..., narrow=True)` (`minimonitor_app.py:1026`)
- `ChooseSiblingModal(..., narrow=True)` (`minimonitor_app.py:984`)
- `ConcernPickerModal(..., narrow=True)` (`minimonitor_app.py:1331`)

`narrow=True` simply adds a `narrow` CSS class that stacks the dialog's rows
vertically (`.aitask-scripts/lib/agent_command_screen.py:369`, `:397-402`).

## Blast radius / scoping constraint

The TUI switcher is **shared across all TUIs** via `TuiSwitcherMixin`
(`TuiSwitcherOverlay` is a `ModalScreen`). It is opened via `j` from board,
full monitor, minimonitor, etc. Passing `narrow=True` unconditionally would
wrongly stack the dialog in the wide TUIs. So the raw-agent dialog must adapt
**dynamically**, only when the switcher is hosted in a narrow pane.

## Fix options (decide in planning)

1. **Width-based detection:** pass `narrow = self.app.size.width <= <threshold>`
   in `action_shortcut_agent`. Minimonitor already tracks `_target_width`
   (`minimonitor_app.py:346`); reuse/share that threshold rather than a new
   magic number. Self-contained, one call site.
2. **Host-declared narrow hook (preferred):** `TuiSwitcherMixin` exposes an
   overridable narrow property/method (default `False`); minimonitor overrides
   it to `True` (using its target-width knowledge). More explicit than a magic
   width threshold and drift-resistant — only minimonitor among switcher hosts
   is narrow today, and a new narrow host opts in explicitly.

Whichever is chosen, keep the identity of the launched agent unchanged; only
the dialog's layout should differ.

## Acceptance criteria

- Pressing `e` in the switcher while in the minimonitor pane opens the
  **narrow** agent-command dialog (rows stacked vertically), matching
  minimonitor's pick/sibling dialogs.
- Pressing `e` in the switcher while in a wide TUI (board, full monitor)
  keeps the **wide** dialog — no regression.
- The narrowness decision lives in one place (no per-host duplicated
  threshold), consistent with the existing `_target_width` convention.

## Notes

- Cross-agent: this is a Python TUI change (no skill-markdown surface), so no
  Codex/OpenCode port is needed.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-05T07:55:16Z status=pass attempt=1 type=human
