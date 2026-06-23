---
Task: t1060_brainstorm_tabswitch_keys_only_fire_from_browse_tab.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan: Fix brainstorm tab-switch keys firing only from the Browse tab (t1060)

## Context

In the `ait brainstorm` TUI the single-key tab switches (`b`/`g`/`d`/`s`/`r`)
only work while focus is on the **tab bar**. Once a tab switch lands focus
inside a pane's content (e.g. an `OperationRow` on Session, a `GroupRow` on
Running), the keys stop switching tabs and the user is stuck — they must use the
command palette to escape. The footer also keeps showing Browse-scoped labels
(`⏎ Open detail`, `A Node action`, `f Defer module`) on the wrong tab.

The task is **pre-existing** (reproduced on the pre-t1048 parent commit), not a
t1048 regression.

### Root causes (proven empirically via the Textual pilot harness)

Two **independent** defects, both in
`.aitask-scripts/brainstorm/brainstorm_app.py`:

1. **Focus-revert (breaks `g`/`d`/`s`/`r`, and `b` once #2 is fixed).**
   The `action_tab_*` handlers fire correctly and execute
   `self.query_one(TabbedContent).active = "<tab>"`, but Textual's
   `TabbedContent` **re-syncs `active` back** to the pane that owns the
   currently-focused widget on the next refresh. So when a focusable row in the
   *old* pane holds focus, the switch is silently reverted. Verified directly:
   setting `.active` with an `OperationRow` focused reverts after `pilot.pause()`;
   setting it with focus cleared/on the tab bar sticks. The binding *does* fire
   (`action_tab_running` was observed being called) — the active value just does
   not stick. This is why switching works *from the tab bar* (boot focus) but not
   once focus is inside content.

2. **`b` swallowed before its binding (breaks `b` on every tab).**
   `BrainstormApp.on_key` has a `if event.key == "b":` block (~line 2399) that
   shows the task brief and calls `event.stop()` **unconditionally on every
   tab**, so the `tab_browse` binding never runs. The brief is a Browse-only
   feature (it renders into the Browse detail pane), so on other tabs `b` should
   fall through to the tab switch.

The footer staleness is a *symptom* of #1: because `active` never actually
changes, `check_action` (which reads `TabbedContent.active`) keeps returning the
Browse-scoped verdicts. Once the switch sticks, the footer recomputes correctly
— no separate fix needed.

## Implementation

All edits are in `.aitask-scripts/brainstorm/brainstorm_app.py`.

### 1. Add a `_select_tab` helper that makes the switch durable

Reuse the existing tab-bar focus hook `_nav_tab_bar()` (line ~3148) — the same
widget RowNavMixin already hands focus back to when arrowing up past the first
row. Add near the `action_tab_*` block:

```python
def _select_tab(self, tab_id: str) -> None:
    """Activate a TabbedContent pane so the switch is not reverted (t1060).

    Setting ``TabbedContent.active`` alone does not stick when a focusable row
    in the *current* pane holds focus: Textual re-syncs ``active`` back to the
    pane owning the focused widget on the next refresh. Handing focus to the tab
    bar (its boot-time home, from which ``down`` re-enters content) makes the
    switch durable. We only refocus when the tab actually changes, so toggling
    the Browse view (``d``/``g``) from within Browse keeps the node cursor.
    """
    tabbed = self.query_one(TabbedContent)
    changed = tabbed.active != tab_id
    tabbed.active = tab_id
    if changed:
        bar = self._nav_tab_bar()
        if bar is not None:
            bar.focus()
```

### 2. Route all five tab-switch actions through the helper

Replace the bare `self.query_one(TabbedContent).active = "<tab>"` line in each
(keep the surrounding `ModalScreen` guard and any post-switch call):

- `action_tab_browse` (~2702): `self._select_tab("tab_browse")`
- `action_tab_dashboard` (~2712): `self._select_tab("tab_browse")` then
  `self._set_browse_view("list")`
- `action_tab_graph` (~2719): `self._select_tab("tab_browse")` then
  `self._set_browse_view("graph")`
- `action_tab_session` (~3061): `self._select_tab("tab_session")` then
  `self._refresh_session_tab()`
- `action_tab_running` (~3067): `self._select_tab("tab_running")`

### 3. Gate the `b` brief handler to the Browse tab

In `on_key` (~2399), change the guard so the brief only shows on Browse and
otherwise falls through to the `tab_browse` binding:

```python
# b: show task brief — Browse-tab only (t1060). On other tabs `b` falls
# through to the `tab_browse` binding so it switches back to Browse.
if event.key == "b" and tabbed.active == "tab_browse":
    ...  # unchanged body (show brief / notify), still ends with stop()+return
```

(`tabbed` is already bound at the top of `on_key`.)

## Tests

Add `tests/test_brainstorm_tab_switch.py` (mirrors the boot/teardown of the
existing `tests/test_brainstorm_binding_scope.py`, which already boots a live
`BrainstormApp` over a temp session). Drive **real keypresses** via
`pilot.press(...)` (the real entry point — not by setting `.active` directly,
which would bypass the bug):

1. **Switch from each tab with focus trapped in content.** For each source tab,
   switch to it, press `down` to move focus into a content row (the failing
   precondition), then press each tab key and assert
   `TabbedContent.active` becomes the expected target:
   - from Session/Running: `b`→browse, `g`→browse, `d`→browse, `s`→session,
     `r`→running.
   - Assert the focus-trapped case specifically (regression-proves #1): without
     the fix, `active` stays on the source tab.
2. **`b` switches from Session and Running** (regression-proves #2).
3. **Footer no longer leaks Browse labels:** after switching to Session/Running,
   assert `open_node_detail` / `node_action` / `toggle_deferred` are absent from
   `app.screen.active_bindings` (the surface `Footer.compose` iterates — same
   technique as `test_brainstorm_binding_scope.py`).

Run: `python3 tests/test_brainstorm_tab_switch.py` and the existing
`python3 tests/test_brainstorm_binding_scope.py` (guard against footer
regressions). Also re-run `python3 tests/test_brainstorm_session_tab.py` to
confirm the new tab-bar focus landing on Session doesn't break its assumptions.

## Risk

### Code-health risk: low
- Change is small and localized to one file: one new private helper plus
  one-line redirects in five existing actions and a one-condition guard tweak.
  It reuses the established `_nav_tab_bar()` focus hook rather than introducing
  a new pattern. · severity: low · → mitigation: TBD
- Minor behavior change: every keyboard tab switch now lands focus on the tab
  bar (then `down` re-enters content), instead of Textual's incidental
  landing on the first content row when switching to Session. This is *more*
  consistent (matches boot state) but a reviewer should confirm no test asserts
  post-switch focus is a content row. · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- Root cause was isolated empirically in the live pilot harness and the fix was
  validated end-to-end (`.active` sticks + focus lands on the tab bar) before
  planning, so the approach is confirmed to deliver the AC. · severity: low ·
  → mitigation: None identified.

## Post-Implementation

Follow shared **Step 9** for archival/merge (profile 'fast', current branch —
no worktree to clean up).
