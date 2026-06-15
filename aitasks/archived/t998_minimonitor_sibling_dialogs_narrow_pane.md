---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [aitask_monitormini, tui, tmux]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-15 12:44
updated_at: 2026-06-15 14:42
completed_at: 2026-06-15 14:42
---

## Goal

Fix the rendering of the two modal dialogs that the minimonitor's **`n`
(Next)** shortcut opens, so they display correctly inside the narrow
companion pane (default `target_width` = **40 cols**).

## Symptom

In `ait minimonitor`, pressing `n` on a followed agent (live example: agent
pick `t983_2`) opens **`NextSiblingDialog`**. In the limited-width companion
pane the dialog is too narrow — buttons are clipped / not all correctly
shown. The follow-on **`ChooseSiblingModal`** (opened by the *Choose sibling*
button) has the same problem and must also render correctly in the narrow
pane.

## Root cause

Both dialogs live in `.aitask-scripts/monitor/monitor_shared.py`:

- **`NextSiblingDialog`** (lines ~250–310): `#next-sib-dialog { width: 70%;
  padding: 1 2; }`. At a 40-col pane, 70% ≈ 28 cols, minus padding ≈ 24
  usable. It has **three** buttons in a **horizontal** row
  (`#next-sib-buttons { layout: horizontal }`): `Pick t<id>`,
  `Choose sibling`, `Cancel` — which need ~35+ cols, so they overflow / clip.
- **`ChooseSiblingModal`** (lines ~374–429): same `#choose-sib-dialog {
  width: 70%; }`; `OK` / `Cancel` buttons also horizontal.

## Precedent / approach

`KillConfirmDialog` in the same file (lines ~167–183) was already adapted for
narrow panes (t994 / t995): `width: 80%; min-width: 28;` and
`#kill-buttons Button { width: auto; min-width: 10; }`. The two sibling
dialogs never got the same treatment.

Suggested fix (confirm during planning):

1. **`NextSiblingDialog`** — widen (`width: 80%` + a sensible `min-width`)
   and switch the 3-button row to a **vertical** layout (`layout: vertical`,
   full-width buttons) so all three render regardless of pane width.
2. **`ChooseSiblingModal`** — apply the same width/`min-width` treatment so
   the downstream choose dialog also fits the narrow pane; verify the
   `OK` / `Cancel` row and the scrollable sibling list render correctly.

## Verification

- Launch `ait minimonitor` against a window running a child-task agent (e.g.
  `t983_2`), press `n`, and confirm `NextSiblingDialog` shows all buttons
  fully within the ~40-col companion pane.
- Press *Choose sibling* and confirm `ChooseSiblingModal` (header, context
  line, sibling rows, OK/Cancel) renders correctly in the same narrow pane.
- Re-check with a wider pane to ensure no regression in normal-width
  rendering.
