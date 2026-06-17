---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [ui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-17 10:31
updated_at: 2026-06-17 10:44
---

## Problem

In `ait brainstorm`, when a `CycleField` is focused, its inherited
near-white text becomes almost unreadable against the orange focus
background. The user first noticed this on the **Launch mode** line of the
operation-definition wizard, but it affects every `CycleField` in the app.

## Root cause

`.aitask-scripts/brainstorm/brainstorm_app.py:3311`:

```css
CycleField:focus {
    background: $accent;   /* orange */
}
```

The rule sets the orange `$accent` background but omits `color:`, so the
focused field keeps the inherited light text → white-on-orange, unreadable.

Every other full-strength `$accent` focus rule in the same stylesheet pairs
the background with an explicit contrasting text color `color: $text`:

- `DimensionRow:focus` (line 2482)
- `GroupRow:focus` (line 3198)
- `AgentStatusRow:focus` (line 3222)
- `ProcessRow:focus` (line 3236)
- `OperationRow:focus` (line 3297)
- `NodeRow:focus` (line 3492)

`CycleField:focus` is the only one missing it. (`StatusLogRow:focus` at line
3760 uses a 20%-tint `$accent 20%` background, so it is not affected.)

## Fix

Add `color: $text;` to the `CycleField:focus` rule, matching the six sibling
row rules:

```css
CycleField:focus {
    background: $accent;
    color: $text;
}
```

## Blast radius / why this is the only place

`CycleField` is the shared widget behind multiple wizard fields, so this
single CSS fix restores readability for all of them:

- the **Launch mode** field (`id="launch-mode-field"`, brainstorm_app.py:7600)
- the **Parallel explorers** count field (line 7113)
- the **module merge destination** field (line 7530)
- the generic config-step `CycleField` (line 7316)

A full sweep of the brainstorm stylesheet confirmed no other widget sets a
full-strength bright background on a focused/selected state without a
contrasting `color:`. The defect is isolated to the one `CycleField:focus`
rule.

## Acceptance criteria

- `CycleField:focus` sets a `color:` that contrasts with the `$accent`
  background (use `color: $text` to match sibling rules).
- Focusing any `CycleField` (Launch mode, Parallel explorers, module merge
  destination, config step) shows readable text.
- No other brainstorm focus/selected rule regresses.

## Verification

- Visual: launch `ait brainstorm`, open the operation-definition wizard,
  Tab/focus the Launch mode field and confirm the text is legible; repeat
  for the other CycleField sites.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-17T07:44:19Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-17T07:44:21Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-17T07:48:24Z status=pass attempt=1 type=human
