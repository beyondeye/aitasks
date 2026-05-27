---
Task: t840_improve_dialog_for_next_in_monitor.md
Base branch: main
plan_verified: []
---

# t840 — Implement "Choose sibling" picker in `ait monitor`

## Context

In `ait monitor`, the `n` shortcut opens `NextSiblingDialog`
(`.aitask-scripts/monitor/monitor_app.py:250`) which suggests the next READY
sibling task and offers three buttons: "Pick t<N>", "Choose child", "Cancel".

The "Choose child" button is a stub today
(`monitor_app.py:304-305`): it dismisses with `("choose", parent_id)`, so
`_on_next_sibling_result` ends up launching `/aitask-pick <parent_id>`
instead of letting the user pick a specific sibling. There is no UI to
browse / select among siblings.

The task is to give that button a proper picker: a vertical list of
**all not-yet-implemented siblings with status `Ready`**, each row showing
the sibling's name and a visual indicator if it is blocked by another
sibling (via `depends`), navigable with up/down arrows, confirmed with
Enter or an OK button, cancelled with Esc.

## Approach

1. Add a `find_ready_siblings()` method to `TaskInfoCache` in
   `.aitask-scripts/monitor/monitor_shared.py`, mirroring the existing
   `find_next_sibling()` but returning the **full** list of pending Ready
   siblings (excluding the current task), each annotated with whether it is
   blocked by another *sibling under the same parent*.

2. Add a new `ChooseSiblingModal(ModalScreen)` class to
   `.aitask-scripts/monitor/monitor_app.py`, modeled after
   `codebrowser/history_detail.py:481` (`SiblingPickerModal`) but trimmed
   for this use case (no fuzzy search, since the list is at most a handful
   of siblings; OK/Cancel buttons added per the user's request).

3. Rewire `_on_next_sibling_result()` so that when the user picks
   "Choose sibling", the new modal is pushed; on confirmation, the
   existing launch logic (already in `_on_next_sibling_result`) runs with
   the user-selected sibling id as `target_id`.

4. Relabel the button from "Choose child" → "Choose sibling" to match the
   dialog title ("Pick Next Sibling") and the new task's wording.

## Changes

### File 1 — `.aitask-scripts/monitor/monitor_shared.py`

Add a new method to `TaskInfoCache` (after `find_next_sibling`, around
line 225). It parses every sibling file once, captures `(child_num,
sib_id, title, status, depends_set)`, then in a second pass computes
per-sibling "blocked by sibling" indicators by intersecting `depends` with
the set of non-Done sibling ids:

```python
def find_ready_siblings(
    self, task_id: str, session_name: str = ""
) -> list[tuple[str, str, list[str]]]:
    """List pending Ready siblings of `task_id`.

    Returns rows of (sib_id, title, blocking_sibling_ids).
    `blocking_sibling_ids` lists sibling ids under the same parent that
    appear in this sibling's `depends` field and are not yet `Done` —
    so the caller can show a "blocked by tX" hint while still allowing
    the user to pick the row.

    Same parent/exclude rules as `find_next_sibling`.
    """
```

Implementation notes:
- Parent + exclude logic copied from `find_next_sibling` (lines 177-183).
- Walk siblings with the same `child_re` and `sorted(...glob(...))`.
- Track sibling status in a map `{sib_id: status}` so the second pass can
  compute "blocking" without re-reading files.
- A blocker is a `depends` entry whose **bare numeric id** matches a
  sibling whose status is not `"Done"`. Normalize `depends` values via
  `str(d).lstrip('t')` so both `42` and `"t42"` are handled.
- The current sibling (`exclude_id`) is **not** returned in the list, but
  it is allowed to appear as a `blocking_sibling_ids` element if other
  siblings depend on it (rare; the user wants visibility either way).
- Return rows sorted by child number ascending (same convention as
  `find_next_sibling`).

No changes required in the public interface of `find_next_sibling` — the
new method is additive and reuses no shared state.

### File 2 — `.aitask-scripts/monitor/monitor_app.py`

#### 2a. Add `Input` to widget imports

Update line 51 to include `Input`:
```python
from textual.widgets import Button, Footer, Header, Input, Label, Static  # noqa: E402
```
(`Input` is imported defensively in case we later add a filter; current
plan does not use it — see "Question" below. If unused, leave the import
out of this PR.) **Default: do not add the import; no search field in
v1.**

#### 2b. Add `_SiblingRow` + `ChooseSiblingModal`

Insert immediately after `NextSiblingDialog` (after current line 310).

`_SiblingRow(Static)` — one focusable row per sibling. Renders:
```
  t<id>  <name>  [bold red]⛔ blocked by t<x>[/]?
```
with the blocked-by hint emitted only when `blocking_ids` is non-empty.
Up/down arrows move focus to neighbor `_SiblingRow`s; Enter dismisses the
modal with this sibling's id. Pattern mirrors
`codebrowser/history_detail.py:422-478` but adapted (no `CompletedTask`
dependency, no fuzzy filter, no return-to-search behavior for Up at the
top — top item simply stops at top, same as the OK button focus).

`ChooseSiblingModal(ModalScreen[str | None])` — dialog itself:
- Constructor: `__init__(self, parent_id, siblings)` where `siblings` is
  the list returned by `find_ready_siblings`.
- `compose()`:
  - `Static("[bold yellow]Choose Sibling[/]")` header
  - `Static` line giving parent context
    (`Parent: t<parent_id>  ·  <N> ready siblings`)
  - `VerticalScroll` containing one `_SiblingRow` per sibling
  - Horizontal `Container` with `Button("OK", id="btn-ok", variant="primary")`
    and `Button("Cancel", id="btn-cancel")`
  - `Static` help line: `[dim][↑/↓] navigate  [Enter/OK] select  [Esc] cancel[/]`
- `BINDINGS = [Binding("escape", "dismiss_modal", "Close")]`
- `DEFAULT_CSS`: borrow the visual idiom from `NextSiblingDialog`
  (`.thick $warning` border) but use `$accent` border (matches the
  codebrowser picker so it reads as a *picker*, not a confirmation).
  Self-contained — modals pushed by `monitor_app` do not inherit App-level
  CSS. Set `max-height: 80%` on the dialog and `height: 1fr` on the list
  scroll so long sibling lists scroll instead of overflowing.
- `on_mount()`: focus first `_SiblingRow` (or OK button if list is empty;
  but the modal is never pushed when the list is empty — see 2c).
- `on_button_pressed`: OK uses the currently focused `_SiblingRow` to
  dismiss with its id; Cancel dismisses with `None`. If OK is pressed
  while focus is not on a row (focus on OK button), fall back to the
  first row's id.
- Edge case: if `siblings` is empty the modal still composes politely
  ("No other Ready siblings found"), but we avoid this by guarding in 2c.

#### 2c. Rewire `_on_next_sibling_result`

Current flow (around line 1684-1744):
```python
def _on_next_sibling_result(self, result):
    if result is None: return
    action, target_id = result
    # ... resolves pane, then launches /aitask-pick target_id
```

Change:
- Split into two helpers: keep the current body as a private helper
  `_launch_pick_for_sibling(self, target_id, action_was_choose=False)`
  that takes the resolved sibling id and runs the kill/launch logic.
  (Behavioral note: today the kill heuristic is `is_parent_with_children
  or not current_info or current_info.status == "Done"`. That heuristic
  is correct for both `"pick"` and `"choose"` since it's keyed off the
  *current* task being replaced — keep as-is.)
- New `_on_next_sibling_result`:
  ```python
  if result is None: return
  action, payload = result
  if action == "pick":
      self._launch_pick_for_sibling(payload)
      return
  # action == "choose": payload is the parent_id
  pane_id = self._focused_pane_id
  snap = self._snapshots.get(pane_id) if pane_id else None
  task_id = self._task_cache.get_task_id(snap.pane.window_name) if snap else None
  if not task_id:
      return
  sess = snap.pane.session_name
  siblings = self._task_cache.find_ready_siblings(task_id, sess)
  if not siblings:
      self.notify("No Ready siblings to choose from", severity="warning")
      return
  self.push_screen(
      ChooseSiblingModal(payload, siblings),
      callback=lambda sib_id: self._launch_pick_for_sibling(sib_id) if sib_id else None,
  )
  ```

#### 2d. Rename "Choose child" button label

In `NextSiblingDialog.compose` (line 298):
```python
yield Button("Choose sibling", variant="primary", id="btn-choose-sibling")
```
Update the `id` here and the corresponding branch in `on_button_pressed`
(line 304) to `btn-choose-sibling`. The dismiss payload stays
`("choose", self._parent_id)` for backward compatibility with the
existing callback shape.

## Verification

Manual TUI flow (no automated test infrastructure exists for the monitor
TUI):

1. Have at least two pending Ready child tasks under the same parent
   (e.g. on a recent multi-child parent). Pick one of them so an agent
   pane is running (`/aitask-pick <parent>_<n>`).
2. In the monitor, focus that agent pane and press `n`.
3. The existing `NextSiblingDialog` appears — confirm the relabeled
   "Choose sibling" button is present (not "Choose child").
4. Press "Choose sibling" → new `ChooseSiblingModal` opens listing all
   other Ready siblings. Verify:
   - The current sibling is not in the list.
   - Each row shows `t<id>  <name>`.
   - A sibling whose `depends` references another not-Done sibling shows
     `⛔ blocked by t<x>` in red.
   - Up/Down arrow navigation moves focus between rows.
   - Enter on a row launches `/aitask-pick <chosen_sibling_id>` in a new
     window (existing launch path is reused — same notify message as
     "Pick t<N>" gives today).
   - Pressing the OK button with a row focused does the same.
   - Esc / Cancel dismisses without launching anything.
5. Edge cases:
   - Only one Ready sibling (the current one) → pressing "Choose sibling"
     shows a `notify` warning and the modal does not open.
   - Sibling depending on a sibling that *is* Done → no blocked indicator
     shown.

After implementation, follow Step 8 (review) → Step 9 (merge to main,
archive). Refer to the shared workflow for the canonical archival steps.

## Files Modified

- `.aitask-scripts/monitor/monitor_shared.py` — add
  `TaskInfoCache.find_ready_siblings`.
- `.aitask-scripts/monitor/monitor_app.py` — add `_SiblingRow` +
  `ChooseSiblingModal`; refactor `_on_next_sibling_result` into a
  `_launch_pick_for_sibling` helper plus a thin dispatcher; relabel the
  button.

## Open Question

Should the list support **typing-to-filter** (like the codebrowser
`SiblingPickerModal`)? The user's spec doesn't ask for it and most
parents have ≤10 children, so v1 omits it. If you want it, we add an
`Input` widget at the top and an `on_input_changed` filter pass —
trivial extension on top of this plan. Asked below.
