---
Task: t726_keep_current_agent_selection_in_monitor.md
Base branch: main
plan_verified: []
---

# t726 — Keep current agent selection visible in monitor when preview pane is focused

## Context

In `ait monitor` the user can press Tab to move keyboard focus from the agent
list pane to the agent preview pane (and back). When focus moves to the
preview pane, the previously-focused `PaneCard` (the agent whose content is
shown in the preview) loses **all** visual indication: no highlight, no
border, nothing telling the user which agent the current preview belongs to.

That's a UX regression — Textual stops rendering the focused-card style
because the card is no longer technically focused, but conceptually it is
still the "selected" item. We want a non-focus visual indicator that
persists while focus lives on the preview pane.

The fix is purely cosmetic state on the existing PaneCard widget: a CSS class
that follows `_focused_pane_id` regardless of which zone currently owns
keyboard focus.

## Files to change

- `.aitask-scripts/monitor/monitor_app.py` — the only file touched.

## Approach

`MonitorApp` already maintains `self._focused_pane_id` as the canonical
"currently selected pane" value — it tracks which agent the preview belongs
to even after Tab moves keyboard focus to `PreviewPanel` (see
`on_descendant_focus` at line 1282 — only the `PaneCard` branch updates
`_focused_pane_id`; switching to `PreviewPanel` leaves it unchanged). All we
need is to surface that state visually on the matching card.

Implementation: add a `selected` CSS class that is applied to the PaneCard
whose `pane_id == self._focused_pane_id`, and let the existing
`PaneCard:focus` rule take precedence when the card actually has focus.

### 1. CSS rule (line ~396–404 of monitor_app.py)

Add a `.selected` rule for `PaneCard` and keep `:focus` after it so the
focused-card style still wins when both apply:

```css
PaneCard.selected {
    background: $accent 30%;
}

PaneCard:focus {
    background: $accent;
    color: $text;
}
```

Rationale for `$accent 30%`: gives a clearly visible but muted highlight
that matches the existing accent-color theme used by `:focus`,
`#pane-list.zone-active`, and `#content-section.zone-active`. Distinct
enough from the full `$accent` so the user can tell which pane currently
holds keyboard focus vs. which agent's preview is being shown.

### 2. Helper to sync the class

Add a small helper method on `MonitorApp` that toggles the class on each
PaneCard:

```python
def _update_selected_card_indicator(self) -> None:
    """Mark the PaneCard matching _focused_pane_id with the 'selected' class.

    Provides a persistent visual hint of which agent's preview is shown,
    even when keyboard focus has moved to the PreviewPanel.
    """
    for card in self.query("#pane-list PaneCard"):
        card.set_class(card.pane_id == self._focused_pane_id, "selected")
```

This mirrors the pattern used by `_update_zone_indicators` (line 1155),
which already uses `widget.set_class(...)` against `Zone` state.

### 3. Call sites

Three places need to re-sync the indicator. All are existing methods —
add a single call to `_update_selected_card_indicator()` at the right
spot in each:

1. **`_update_zone_indicators`** (around line 1167 — right after the
   refresh-bindings/preview-update block) — fires on Tab/Shift+Tab, so the
   indicator is correct as soon as the zone changes.

2. **`on_descendant_focus`** (around line 1289) — fires when the user
   arrow-navigates to a different PaneCard (so the previous card loses
   `.selected` and the new one gains it). Add inside the `PaneCard` branch
   after `self._focused_pane_id = widget.pane_id`. The `PreviewPanel`
   branch does not need a call — `_focused_pane_id` doesn't change there,
   so the previous card already has `.selected`. (`_update_zone_indicators`
   is also already called in this branch, but adding the explicit helper
   call makes the contract clearer and is defensive against future
   refactors of `_update_zone_indicators`.)

3. **`_restore_focus`** (around line 855, just before the final
   `self._update_content_preview()`) — fires after `_rebuild_pane_list`
   replaces the cards. Without this call the freshly-mounted PaneCards
   would never receive `.selected` when the user is sitting in
   `Zone.PREVIEW` during a refresh tick.

No changes needed in `_focus_first_in_zone` — focusing a card triggers
`on_descendant_focus`, which now covers the indicator.

## Why no other call sites are needed

- `_switch_zone` calls `_focus_first_in_zone` then `_update_zone_indicators`,
  so it's covered by call sites 1 and 2.
- `_nav_within_zone` focuses a card via `card.focus()`, triggering
  `on_descendant_focus` → call site 2.
- The PreviewPanel-focus branch of `on_descendant_focus` does not change
  `_focused_pane_id`, so the previously-marked card stays correct.
- `_refresh_data` schedules `_restore_focus` via `call_after_refresh`, so
  call site 3 covers periodic ticks.

## Verification (manual)

1. `ait monitor` (must be inside tmux with at least one agent pane).
2. Verify default state: an agent card is highlighted with full accent
   background (`PaneCard:focus`).
3. Press Tab → focus moves to the preview pane border (`#content-section`
   gets the warning border) and **the previously-focused PaneCard now shows
   the muted `$accent 30%` background** instead of disappearing.
4. Press Tab again → focus returns to the PaneCard, full accent restored,
   muted background gone.
5. Use arrow keys to move between PaneCards → muted/full highlight follows
   the focused card; only the focused card is highlighted at a time.
6. Move to preview pane (Tab), then trigger a refresh tick by waiting (the
   built-in periodic refresh) → muted highlight persists across refreshes
   on the same card.
7. With focus on preview, switch agent via `s`/auto-switch (if applicable)
   → muted highlight tracks the new `_focused_pane_id`.

No automated tests — `monitor_app.py` is a Textual TUI and the project has
no pytest harness for it (the only existing tests are bash + tmux integration
shell scripts, which don't drive the keyboard).

## Step 9 — Post-Implementation

Standard archival flow. No worktree was created (profile `fast` =
`create_worktree: false`), so the merge step is skipped — go straight to
`./.aitask-scripts/aitask_archive.sh 726` after Step 8 commit.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned. Three additions to
  `.aitask-scripts/monitor/monitor_app.py`:
  1. CSS rule `PaneCard.selected { background: $accent 30%; }` inserted
     between the existing `PaneCard {…}` and `PaneCard:focus {…}` blocks
     (so the `:focus` rule still wins via source order on the focused
     card).
  2. New helper `_update_selected_card_indicator(self)` that iterates
     `#pane-list PaneCard` and toggles the `selected` class against
     `card.pane_id == self._focused_pane_id`.
  3. Two call sites — at the end of `_update_zone_indicators()` (covers
     Tab/Shift+Tab and arrow-key card navigation, since
     `on_descendant_focus` already invokes `_update_zone_indicators`), and
     at the end of `_restore_focus()` (covers post-rebuild ticks).
- **Deviations from plan:** Skipped the third "explicit defensive call" in
  `on_descendant_focus` that the plan flagged as optional. Reasoning: the
  `PaneCard` branch already calls `_update_zone_indicators()` (which now
  calls the helper), and the `PreviewPanel` branch does not change
  `_focused_pane_id`, so the indicator on the previously-marked card is
  still correct. Adding a duplicate call would be redundant —
  KISS/YAGNI.
- **Issues encountered:** Plan externalization auto-scan returned
  `MULTIPLE_CANDIDATES` because `~/.claude/plans/` had several stale
  files; resolved by passing `--internal <path>` explicitly. No
  application issues.
- **Key decisions:** Used `$accent 30%` for the muted highlight (matches
  existing accent-color theme; visually distinct from full `$accent` so
  the user can still tell which pane currently holds keyboard focus).
  Relied on CSS source-order precedence (`.selected` rule before `:focus`
  rule) so both rules can stay simple with no `:not(:focus)` qualifier.
- **Upstream defects identified:** None.
