---
priority: medium
effort: low
depends: []
issue_type: refactor
status: Ready
labels: [codebrowser]
created_at: 2026-04-19 10:48
updated_at: 2026-04-19 10:48
---

Follow-up from t584 (reorder keybindings in codebrowser footer).

The initial implementation added a `ContextualFooter` in
`.aitask-scripts/codebrowser/codebrowser_app.py` with per-pane priority
maps (`PANE_ORDERS`) that move pane-relevant bindings to the front. The
current maps are a first pass and need UX refinement — in use, the
footer looks inconsistent because many keys shift position between
panes, so the eye can't anchor on a stable "most important" section.

## What to fix

1. **Stable primary slots.** A small set of high-importance bindings
   (candidates: `q`, `h`, `n`, `e`, maybe `g`) should always appear in
   the same order, regardless of which pane is focused. Reorder logic
   should layer pane-specific bindings *after* this fixed prefix, not
   mix them in.

2. **Per-pane relevance order.** Revisit each `PANE_ORDERS` entry:
   - `file_tree`: the tree-reset `R` and refresh `r` rarely deserve
     the #1 slot — primary actions first, then `R`/`r`.
   - `recent_files`: same idea — show common actions first; history
     uppercase `H` is a sub-action and should not be surfaced globally.
   - `file_search`: when the search input is focused, `Escape` and
     `Enter` are more relevant than listed bindings (though both are
     `show=False`); consider pruning this pane's map.
   - `code_viewer` and `detail_pane`: already reasonable; audit for
     the "primary slots" rule above.

3. **Avoid surfacing "sub-action" uppercase bindings (`H`, `D`, `R`)
   as top entries.** They are currently mostly rarely-used and should
   generally stay at the end of the list.

## Where to change

`.aitask-scripts/codebrowser/codebrowser_app.py` — edit the
`ContextualFooter.DEFAULT_ORDER` and `PANE_ORDERS` class attributes.
The compose / sort logic itself does not need to change. Optionally
refactor to a two-layer scheme:

```python
PRIMARY_ORDER = ["q", "h", "n", "e", "g"]  # stable across panes
PANE_SUFFIX_ORDERS = {
    "file_tree":    ["R", "r", ...],
    ...
}
```

and compose the final priority as `PRIMARY_ORDER + PANE_SUFFIX_ORDERS[pane]`.

## Verification

- `./ait codebrowser` — open a file, Tab through panes, verify the
  first N bindings stay put and only pane-specific bindings move.
- Also verify padding is unchanged (the t584 fix should still hold).

## Context files

- `.aitask-scripts/codebrowser/codebrowser_app.py` — the ContextualFooter class (~line 156–290 at t584 archival time)
- `aiplans/archived/p584_reorder_keybinding_in_footer_of_codebrowser.md` — design + final notes of t584
