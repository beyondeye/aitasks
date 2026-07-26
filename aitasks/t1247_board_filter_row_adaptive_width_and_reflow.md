---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask_board, tui]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1210
created_at: 2026-07-26 10:07
updated_at: 2026-07-26 10:08
---

## Symptom

In `ait board`, the search box at the top of the filter row partially covers /
truncates the base filter modes (`[a All | l Locked | f Free | i In-Flight |
y · By-Topic | z · By-Trail]   g Git   t Type`). The tail of the filter list is
not visible.

## Root cause

`.aitask-scripts/board/aitask_board.py:5597` composes the filter row as:

```python
with Horizontal(id="filter_area"):
    with Container(id="view_col"):          # <- fixed width
        yield Static("Task filter", id="view_label")
        yield ViewSelector(..., id="view_selector")
        yield Static("", id="type_filter_summary", classes="type-filter-summary hidden")
    yield Input(placeholder="Search tasks...", id="search_box")
```

with CSS at `:5227`:

```
#view_col { width: 78; height: auto; }
#view_selector { height: 1; padding: 0 1; }
```

`#view_col`'s width is a **hardcoded column count**. `#view_selector` is a
`Static` with no width rule, so it fills its parent (78) and its longer rendered
line is truncated at that boundary. The search box — which the board already
sizes with the global rule `Input { width: 1fr; }` (`:5232`) — then begins
exactly where the truncated filters end, producing the "search bar covers the
filters" appearance.

**Measured** (via `render_label(..., style="leading")` with the board's live
keys `a/l/f/i/y/z/g/t`):

| segment | rendered | cols |
|---|---|---|
| All | `a All` | 5 |
| Locked | `l Locked` | 8 |
| Free | `f Free` | 6 |
| In-Flight | `i In-Flight` | 11 |
| By-Topic | `y · By-Topic` | 12 |
| By-Trail | `z · By-Trail` | 12 |
| Git | `g Git` | 5 |
| Type | `t Type` | 6 |

Plus 2 brackets, 5×3 base separators, 2×3 addon gaps = **88 cols**, +2 from
`padding: 0 1` = **90** vs the 78 available → **12-column overflow**.
Without By-Trail the same computation gives 75 — which fit inside 78 with 3
columns to spare.

## Why this is recurring, not a one-off

`git log -L 5227,5227:.aitask-scripts/board/aitask_board.py` shows the width has
been hand-bumped on **every** prior filter addition:

- `26` — t273 (initial view mode filter)
- `36` — t645
- `48` — t850 (base radio + add-on toggles restructure)
- `62` — t635_9 (In-Flight)
- `78` — t1016_4 (By-Topic)
- *(missed)* — 03eade720 / t1210_4 (By-Trail)

The By-Trail commit added `("view_bytrail", "By-Trail", "bytrail")` to
`ViewSelector.BASES` (`:1429`) but did not bump the width. Beyond additions, the
number is **also** invalidated by user key rebinds: `render_label(style="leading")`
emits `k text` (key matches first letter) but `k · text` (+2 cols) otherwise and
`Ctrl+X · text` for a combo, and keys are rebindable via the `?` shortcut editor.
Any fixed number rots.

**Do not fix this by bumping 78 → 90.** The fix must make the geometry derive
itself.

## Required outcome

1. **Adaptive left column.** `#view_col` / `#view_selector` size to the actual
   rendered `ViewSelector` content (`width: auto`, or a width computed from the
   rendered string) so adding a base filter or rebinding a key never truncates
   the row again. No hardcoded column count may remain for this purpose.
2. **Adaptive search box.** `#search_box` keeps flexing into the remainder but
   gains a `min-width` so it stays usable, and never overlaps or visually
   consumes the filter segments.
3. **Row reflow.** Below the width where selector + minimum search box no longer
   fit side by side, the row must reflow (e.g. search box drops to its own line)
   rather than truncating either element.

## Implementation notes / constraints

- **`#type_filter_summary` blocks a naive `width: auto`.** It lives inside
  `#view_col` and renders `types: bug, enhancement, documentation, …`
  (`_refresh_type_filter_summary`, `:6017-6029`), which can be far wider than the
  selector and would then drive the container's auto-width. It needs a
  `max-width`, wrapping, or to move out of `#view_col`. Cover the many-types case.
- **Textual 8.2.7 `Horizontal` has no flex-wrap.** Reflow must be implemented as
  an `on_resize` / `events.Resize` handler toggling a CSS class that flips
  `#filter_area` to `layout: vertical` below a threshold.
- **The board currently has zero resize handling** (no `on_resize`, no
  `events.Resize`, no `self.size.width` reads). Follow the existing convention in
  `.aitask-scripts/monitor/monitor_app.py`,
  `.aitask-scripts/monitor/minimonitor_app.py`,
  `.aitask-scripts/codebrowser/codebrowser_app.py`,
  `.aitask-scripts/codebrowser/code_viewer.py`,
  `.aitask-scripts/diffviewer/diff_display.py`, and
  `.aitask-scripts/lib/numbered_source_view.py`.
- `ViewSelector.on_click` hit-tests against `self._click_targets` column offsets
  computed in `render()` and subtracts 1 for the `padding: 0 1` (`:1497-1499`).
  Verify click targeting still lands on the right segment after any width or
  padding change, and in the reflowed layout.

## Testing

No existing test covers filter-row geometry — `tests/test_board_view_filter.py`
and `tests/test_board_bytrail_view.py` do not reference `#view_col` or
`ViewSelector` sizing. Add regression coverage that would have caught this:

- A **structural guard** asserting the filter row is not truncated — i.e. that
  the container width is derived from, and is at least, the rendered
  `ViewSelector` width. Per the repo's render-level TUI convention, assert on
  `widget.render()` / measured content width rather than on a literal constant.
- A **negative control**: append a synthetic extra base filter (or rebind a key
  to a non-first-letter / multi-key form so a segment widens) and assert the
  layout still fits — proving the guard fails against the pre-fix hardcoded width.
- Coverage for the reflow threshold (wide terminal → side by side; narrow →
  reflowed) and for the long `types: …` summary not hijacking the width.

## Acceptance criteria

- [ ] All six base filters plus `g Git` / `t Type` are fully visible in `ait board`
      at a normal terminal width, with the search box beside them.
- [ ] No hardcoded filter-row column-count constant remains in the board CSS.
- [ ] Adding a base filter to `ViewSelector.BASES`, or rebinding a filter key to a
      non-first-letter or multi-key shortcut, requires no CSS change.
- [ ] The search box has a minimum usable width and never truncates the filters.
- [ ] The row reflows instead of truncating when the terminal is too narrow for both.
- [ ] A long `types: …` filter summary does not distort the filter-row width.
- [ ] Clicking each filter segment still activates the correct filter, in both the
      side-by-side and reflowed layouts.
- [ ] New tests pass and demonstrably fail against the pre-fix hardcoded width.
