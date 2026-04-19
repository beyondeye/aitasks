---
Task: t586_refine_codebrowser_context_binding_order.md
Base branch: main
plan_verified: []
---

# t586 — Refine codebrowser `ContextualFooter` priority maps

## Context

t584 added `ContextualFooter` to `.aitask-scripts/codebrowser/codebrowser_app.py`,
which reorders footer bindings per-pane by consulting a single
`PANE_ORDERS` map (full binding list per pane) with a `DEFAULT_ORDER`
fallback. In use, the footer feels unstable: the first few slots shift
too much as focus moves between panes, there is no fixed "primary
actions" anchor, and several rarely-used uppercase sub-action keys
(`R`, `H`, `D`) are surfaced near the top of some panes. `q` is missing
from every map and therefore falls to the very end.

The task asks for:

1. A **stable primary prefix** of high-importance bindings that stays in
   the same order regardless of focus.
2. Revised per-pane orderings for file_tree, recent_files, file_search,
   code_viewer, detail_pane that put primary actions first and keep
   rarely-used sub-actions at the end.
3. Sub-action uppercase bindings (`H`, `D`, `R`) should not appear near
   the top — they belong at the end.

Only two class attributes on `ContextualFooter` change plus a tiny tweak
to `_ordering()`. No binding set changes, no `compose()` changes.

## Approach

Replace the single-list-per-pane scheme with a **two-layer scheme**:

```python
PRIMARY_ORDER = ["q", "h", "n", "e", "g"]           # stable prefix
PANE_SUFFIX_ORDERS = {
    "file_tree":    ["d", "c", "r", "R"],
    "recent_files": ["d", "c"],
    "file_search":  [],                              # pruned (see notes)
    "code_viewer":  ["w", "c", "t", "d", "r"],
    "detail_pane":  ["d", "c", "D", "H"],
}
```

`_ordering()` becomes `PRIMARY_ORDER + PANE_SUFFIX_ORDERS.get(pane, [])`.
Keys not in the resulting list fall to the end in their original
`active_bindings` order (sort is stable), which is exactly the existing
behaviour — so `R` on code_viewer, `H`/`D` on file_tree, etc., still
render but stay at the tail.

Removing `DEFAULT_ORDER` is cleaner than redefining it: when no pane
matches (rare — only before first focus), `_ordering()` returns just
`PRIMARY_ORDER`, which is fine.

### Design rationale (per the task's guidance)

- **PRIMARY_ORDER = `q, h, n, e, g`** — the set explicitly listed in the
  task. `q` (quit) is currently missing everywhere and ends up last; it
  belongs at the front. `h` (history), `n` (new task), `e` (explain) are
  globally useful. `g` (go to line) is frequent enough to keep in the
  stable prefix even though it's meaningful mainly in the code viewer.
- **file_tree suffix `[d, c, r, R]`** — primary tree actions (selecting
  files) are the implicit Enter/arrow keys (`show=False`). `d`/`c` are
  generically useful; `r` (refresh annotations) and `R` (reset tree) are
  demoted from the leading slot to the tail of the listed suffix.
- **recent_files suffix `[d, c]`** — `H` (history-for-task) is a
  sub-action and intentionally omitted from the listed suffix so it
  drops to the tail. The pane's main "action" is selecting a recent file
  (Enter, `show=False`).
- **file_search suffix `[]`** — when the search input is focused, the
  primary interactions (`Escape`, `Enter`, typing) are all `show=False`.
  No listed keys are more relevant than `PRIMARY_ORDER` for this pane,
  so the map is pruned to empty.
- **code_viewer suffix `[w, c, t, d, r]`** — code-specific actions come
  after `PRIMARY_ORDER`. `R` is dropped from the listed suffix (falls to
  the tail). Current ordering already had these in roughly this order.
- **detail_pane suffix `[d, c, D, H]`** — `D` (expand) and `H`
  (history-for-task) are uppercase sub-actions that only make sense on
  the detail pane, so they remain in the listed suffix but at the tail
  of the listed suffix, not at slots #2/#3 as today.

## Files to Modify

- `.aitask-scripts/codebrowser/codebrowser_app.py` — the
  `ContextualFooter` class at lines 161–193.
  - Replace the `DEFAULT_ORDER` + `PANE_ORDERS` class attributes with
    `PRIMARY_ORDER` + `PANE_SUFFIX_ORDERS`.
  - Update `_focused_pane_id()` to look at `PANE_SUFFIX_ORDERS` keys
    (rename the map consulted) so pane resolution still works.
  - Update `_ordering()` to return
    `PRIMARY_ORDER + PANE_SUFFIX_ORDERS.get(pane, [])`.
  - `compose()` is unchanged — it already consults `_ordering()`.

## Concrete diff sketch

```python
class ContextualFooter(Footer):
    """Footer whose visible bindings are reordered based on which pane has focus.

    Layout is a stable PRIMARY_ORDER prefix followed by a per-pane
    suffix. Keys not listed in either layer fall to the end in their
    original active_bindings order (stable sort).
    """

    PRIMARY_ORDER = ["q", "h", "n", "e", "g"]

    PANE_SUFFIX_ORDERS = {
        "file_tree":    ["d", "c", "r", "R"],
        "recent_files": ["d", "c"],
        "file_search":  [],
        "code_viewer":  ["w", "c", "t", "d", "r"],
        "detail_pane":  ["d", "c", "D", "H"],
    }

    def _focused_pane_id(self) -> str | None:
        w = self.screen.focused
        while w is not None:
            if getattr(w, "id", None) in self.PANE_SUFFIX_ORDERS:
                return w.id
            w = w.parent
        return None

    def _ordering(self) -> list[str]:
        pane = self._focused_pane_id()
        suffix = self.PANE_SUFFIX_ORDERS.get(pane, [])
        return self.PRIMARY_ORDER + suffix
```

The compose() method body is unchanged.

## Verification

Manual (no TUI tests):

1. `./ait codebrowser` — open a file.
2. Observe the footer leads with `q h n e g …` regardless of which pane
   currently has focus.
3. Tab-cycle through panes and confirm:
   - **file_tree**: `q h n e g` then `d c r R …` — `R`/`r` no longer
     occupy the #1/#2 slots.
   - **recent_files**: `q h n e g` then `d c …` — `H` no longer appears
     near the top.
   - **file_search**: `q h n e g …` — map is pruned, remainder falls
     through in original order.
   - **code_viewer**: `q h n e g` then `w c t d r …`.
   - **detail_pane** (press `d` to show, Tab to focus): `q h n e g` then
     `d c D H …` — `D` and `H` are at the tail of the listed suffix.
4. Confirm every binding still works (trigger `q`, `n`, `e`, `g`, `h`,
   `R`, `w`, `D`, `H` from various panes).
5. Confirm t584's padding fix still holds — the compose() body is
   unchanged, so `fk.compact = fk_compact` continues to apply.

## Step 9 reminder

After implementation & review, proceed to Step 9 (Post-Implementation):
archive via `./.aitask-scripts/aitask_archive.sh 586` and push.

## Final Implementation Notes

- **Actual work done:** In `.aitask-scripts/codebrowser/codebrowser_app.py`
  replaced the single `DEFAULT_ORDER` + `PANE_ORDERS` attributes on
  `ContextualFooter` with a two-layer scheme: a stable `PRIMARY_ORDER =
  ["q", "h", "n", "e", "g"]` prefix and a pane-specific
  `PANE_SUFFIX_ORDERS` map. `_focused_pane_id()` now consults
  `PANE_SUFFIX_ORDERS` keys, and `_ordering()` returns
  `PRIMARY_ORDER + PANE_SUFFIX_ORDERS.get(pane, [])`. `compose()`
  unchanged — it already consumes `_ordering()`.
- **Deviations from plan:** None. Landed exactly as sketched.
- **Issues encountered:** None.
- **Key decisions:**
  - Empty suffix for `file_search` (`[]`) — matches the task guidance
    that the search-input's primary interactions are `show=False`, so
    `PRIMARY_ORDER` alone is the right display.
  - `DEFAULT_ORDER` removed (not kept as a synonym for `PRIMARY_ORDER`)
    — the fallback is now "just `PRIMARY_ORDER` with empty suffix",
    which is already what `_ordering()` returns when `pane` is `None`.
  - Uppercase sub-actions (`H`, `D`) retained in `detail_pane` suffix
    but at its tail (slots #3-#4 of the suffix), honouring the task's
    rule that they stay near the end. `R` dropped from every pane's
    listed suffix except `file_tree` (where it's still at the tail).
- **Verification performed:** `python -c "ast.parse(...)"` confirms the
  edited file parses cleanly. Runtime TUI verification (Tab-cycling
  through panes, triggering demoted bindings) is deferred to the user
  per the task's Verification section — no automated tests exist for
  codebrowser footer ordering.
