---
Task: t1019_brainstorm_focused_cyclefield_contrast.md
Worktree: (none — profile 'fast' works on current branch)
Branch: main
Base branch: main
---

# Plan: Fix unreadable focused CycleField contrast in brainstorm TUI

## Context

In `ait brainstorm`, focusing a `CycleField` (first noticed on the **Launch
mode** line of the operation-definition wizard) renders near-white text on the
orange `$accent` focus background — practically unreadable. The defect is a
single missing `color:` declaration in the focus style rule. Every other
full-strength `$accent` focus rule in the same stylesheet pairs the background
with an explicit `color: $text`; `CycleField:focus` is the only one that omits
it. Because `CycleField` is the shared widget behind several wizard fields, the
one-line fix restores readability everywhere the widget is used.

## Root cause

`.aitask-scripts/brainstorm/brainstorm_app.py:3311-3313`:

```css
CycleField:focus {
    background: $accent;
}
```

No `color:` is set, so the focused field keeps the inherited light text →
white-on-orange.

Sibling focus rules (all set `color: $text`): `DimensionRow:focus` (2482),
`GroupRow:focus` (3198), `AgentStatusRow:focus` (3222), `ProcessRow:focus`
(3236), `OperationRow:focus` (3297), `NodeRow:focus` (3492).
(`StatusLogRow:focus` at 3760 uses a 20%-tint background and is unaffected.)

## Implementation

**Single edit** in `.aitask-scripts/brainstorm/brainstorm_app.py`, the
`CycleField:focus` rule (~line 3311):

```css
CycleField:focus {
    background: $accent;
    color: $text;
}
```

Adding `color: $text;` mirrors the six sibling row rules and uses Textual's
auto-contrasting text token, so it stays correct across themes.

## Blast radius

`CycleField` is the shared widget; the single rule fix covers all instances:
- Launch mode field (`id="launch-mode-field"`, ~line 7600) — the reported case
- Parallel explorers count field (~line 7113)
- Module merge destination field (~line 7530)
- Generic config-step CycleField (~line 7316)

No other brainstorm focus/selected rule has the missing-contrast pattern
(verified by a full stylesheet sweep), so no other change is required.

## Verification

- `grep -n -A2 'CycleField:focus' .aitask-scripts/brainstorm/brainstorm_app.py`
  confirms `color: $text;` is present alongside `background: $accent;`.
- Visual (manual): launch `ait brainstorm`, open the operation-definition
  wizard, Tab/focus the **Launch mode** field — text is legible. Repeat for the
  Parallel explorers and module-merge-destination CycleFields.
- No regression: the six sibling `:focus` rules are untouched.

## Risk

### Code-health risk: low
- None identified. Single CSS declaration added to one rule, mirroring an
  established convention used by six sibling rules; no logic, no blast radius
  beyond the shared widget's appearance. · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- None identified. Root cause is unambiguous and the fix directly removes it;
  the auto-contrasting `$text` token guarantees readable contrast against
  `$accent`. · severity: low · → mitigation: TBD

## Step 9 (Post-Implementation)

Standard cleanup/archival per task-workflow Step 9: review & commit (Step 8),
then merge/archive. Profile 'fast' works on the current branch, so there is no
worktree to remove.
