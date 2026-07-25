---
Task: t1212_board_collapsed_placeholder_focus_shade.md
Base branch: main
plan_verified: []
---

# t1212 — Collapsed column placeholder must focus in the accent shade

## Context

`ait board` gives every column exactly one focus anchor: a `TaskCard`, or — when
the column shows no cards — a placeholder widget. There are two placeholder
classes and today they highlight differently when focused:

- `CollapsedColumnPlaceholder` (`.aitask-scripts/board/aitask_board.py:1370`)
  sets an **inline** `#444444` background in `on_focus` / `on_blur`. Inline
  styles beat CSS, so its own rule at line 5240 —
  `.collapsed-placeholder:focus { background: $primary 30%; }` — never applies.
  The presence of that unused rule shows the accent shade was the intent.
- `EmptyColumnPlaceholder` (added by t1209, line 1386) is CSS-only:
  `.empty-placeholder:focus { background: $primary 30%; }`, no inline override.

On a board with both a collapsed column and an empty column, arrowing between
them highlights one solid gray and the other in the theme accent. Focus
highlighting should use the accent shade, never flip to gray.

**Baseline measured on the real `KanbanApp` (Pilot probe, pre-fix):**

```
collapsed unfocused : Color(0, 0, 0, a=0)        # transparent
collapsed FOCUSED   : Color(68, 68, 68)          # #444444  ← the defect
empty     FOCUSED   : Color(1, 120, 212, a=0.3)  # $primary 30%
```

Outcome: both placeholders resolve to `Color(1, 120, 212, a=0.3)` when focused,
and the invariant is pinned by an automated test.

## Approach

Delete the inline override and let the existing CSS rule apply. No CSS change is
needed — the rule is already there and already correct.

### 1. `.aitask-scripts/board/aitask_board.py` — remove the inline override

Delete the two methods (lines 1379–1383), leaving the class body at
`__init__` only, exactly mirroring `EmptyColumnPlaceholder`:

```python
class CollapsedColumnPlaceholder(Static):
    """A focusable placeholder inside collapsed columns, enabling keyboard expand."""

    can_focus = True

    def __init__(self, col_id: str):
        super().__init__("···", classes="collapsed-placeholder")
        self.column_id = col_id
```

This is the only widget in the board that drives focus styling through an inline
`styles.background`; every other `on_focus` / `on_blur` pair either toggles a CSS
class (e.g. `add_class("dep-item-focused")`, line 2032) or sets a border, so the
deletion moves this widget onto the file's dominant pattern rather than away
from it.

### 2. `tests/test_board_empty_column_focus.py` — pin the invariant (new case 12)

That file already boots the real `KanbanApp` through `Pilot` over the synthetic
`Left(2) | Empty(0) | Right(2)` fixture, and case 5 already renders `zz_left`
collapsed — so the new case reuses `_synthetic_board` / `_settle` and adds no
scaffolding. Resolve `Color` in `setUpClass` (`from textual.color import Color`)
alongside the existing imports.

```python
def test_collapsed_placeholder_focus_uses_the_accent_shade(self):
    """Case 12: the collapsed placeholder highlights in the theme accent (t1212).

    An inline `#444444` background used to dead-letter the widget's own
    `.collapsed-placeholder:focus` rule, so a collapsed column highlighted
    gray while an empty column beside it highlighted in the accent.
    """

    async def go():
        app = self.KanbanApp()
        self._synthetic_board(app)
        app.manager.settings["collapsed_columns"] = ["zz_left"]
        async with app.run_test(size=(160, 48)) as pilot:
            await self._settle(pilot)
            collapsed = [w for w in app.query(self.CollapsedColumnPlaceholder)
                         if w.column_id == "zz_left"][0]
            idle = collapsed.styles.background

            collapsed.focus()
            await self._settle(pilot)
            focused = collapsed.styles.background
            self.assertNotEqual(
                focused, self.Color.parse("#444444"),
                "focus must not fall back to the inline gray override")

            # Ground truth: the sibling placeholder, styled by the equivalent
            # `.empty-placeholder:focus` rule, is what "the accent shade" means.
            empty = self._placeholder(app, "zz_empty")
            empty.focus()
            await self._settle(pilot)
            self.assertEqual(
                focused, empty.styles.background,
                "both placeholders must share one focus shade")
            self.assertEqual(
                collapsed.styles.background, idle,
                "blurring must restore the idle background")

    self._run(go())
```

`widget.styles` is Textual's `RenderStyles`, which returns the inline value when
one is set and the CSS-resolved value otherwise — so this assertion fails on the
current code (`Color(68, 68, 68)`) and passes after the deletion. The third
assertion covers the removal of `on_blur`: nothing is left to reset, so the idle
value must come back from CSS alone.

## Verification

1. **Prove the test fails first** (the deletion is the only thing that fixes it):
   run the new case against unmodified `aitask_board.py` and confirm it fails on
   the `#444444` assertion; then apply the deletion and confirm it passes.
   ```bash
   bash tests/run_all_python_tests.sh tests/test_board_empty_column_focus.py
   ```
2. Run the full board Pilot suite to confirm cases 1–11 (especially case 5 and
   case 11, which both focus the collapsed placeholder) still pass.
3. Visual check in `ait board`: collapse a column (`c`), arrow onto its `···`
   placeholder and onto an `(empty)` placeholder — both highlight in the same
   accent shade, and the highlight clears on blur.

## Risk

### Code-health risk: low

- The focus highlight changes from an opaque gray to a 30%-alpha accent wash,
  which is a subtler cue on some themes; this is the intended, already-shipped
  `EmptyColumnPlaceholder` appearance rather than a new design · severity: low ·
  → mitigation: none (covered by the visual check in Verification step 3)

### Goal-achievement risk: low

- None identified. The target CSS rule already exists and the fix is a pure
  deletion whose before/after values were measured on the real widget.

## Step 9 (Post-Implementation)

Merge, run the gate orchestrator (`risk_evaluated`), and archive per the shared
workflow.
