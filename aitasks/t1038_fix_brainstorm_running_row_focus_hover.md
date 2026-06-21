---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [brainstorming, tui, ait_brainstorm]
anchor: 1018
created_at: 2026-06-21 13:38
updated_at: 2026-06-21 13:38
---

## Origin

Spawned from t1018_3 during Step 8b review.

## Upstream defect

- `.aitask-scripts/brainstorm/brainstorm_app.py:4954-4977` — `AgentStatusRow` /
  `ProcessRow` (and peer Running-tab rows) share the same equal-specificity
  `:focus` / `:hover` CSS where `:hover` is declared after `:focus`, so a
  focused **and** hovered row flips to the gray hover background
  (`$surface-lighten-1`) instead of staying in the focus accent. They lack the
  `:focus:hover` accent rule that t1018_3 added to `GroupRow`. Pre-existing
  cosmetic inconsistency.

## Diagnostic context

t1018_3 added Running-tab GroupRow double-click + focus-preservation. During
review the user noticed hovering the focused operation group flipped its
background from the focus orange to gray. Root cause: `GroupRow:focus`
(`background: $accent`) and `GroupRow:hover` (`background: $surface-lighten-1`)
are equal-specificity single-pseudo rules; `:hover` (declared later) overrides
`:focus`. t1018_3 fixed it for `GroupRow` only (a `GroupRow:focus:hover` rule
with `$accent-lighten-1`), scoped to the operation group per the user's request.
The sibling row widgets in the same CSS block share the identical pattern and
the same confusing behavior.

## Suggested fix

Add a `:focus:hover { background: $accent-lighten-1; color: $text; }` rule for
each peer Running-tab row type that has both a `:focus` ($accent) and a `:hover`
($surface-lighten-1) rule — `AgentStatusRow`, `ProcessRow`, and any others with
the same pattern (e.g. `OperationRow`, `NodeRow`, `DimensionRow`, `StatusLogRow`
if they exhibit it). Mirror the `GroupRow:focus:hover` rule from t1018_3.
Consider whether a shared CSS class would reduce duplication.
