---
Task: t1245_fix_taskcard_doubleclick_toggle_children_gate_bypass.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main (current branch)
Base branch: main
---

# p1245 — Fix TaskCard double-click `toggle_children` gate bypass

## Context

`TaskCard.on_click` (`.aitask-scripts/board/aitask_board.py:1652`) implements a
double-click shortcut: on a collapsed parent card with children it calls
`self.app.action_toggle_children()` instead of opening the detail modal. That
call goes **straight to the action**, never consulting `KanbanApp.check_action`
— the single gate that decides whether `toggle_children` is available.

`check_action` hides `toggle_children` in the derived views (`aitask_board.py:5521-5534`):

```python
elif action == "toggle_children":
    if self.base_filter in ("inflight", "bytopic", "bytrail"):
        return False
```

because In-Flight / By-Topic / By-Trail render every relevant card (children
included) directly — there is nothing to expand. But `action_toggle_children`
(`:7394`) is a bare `self._toggle_expand()` with no view guard, so the mouse
path still mutates `app.expanded_tasks` and fires a `refresh_column` in views
where the action is deliberately unavailable.

Affected surfaces today:
- **By-Topic** — `TopicColumn` mounts plain `TaskCard`s (`:1771`) → bypass live.
- **In-Flight** — `InFlightTaskCard` (`:1665`) subclasses `TaskCard` and does
  **not** override `on_click` → bypass live there too (not noted in the task).
- **By-Trail** — already immune: `TrailTaskCard`/`TrailGhostCard` (`:1838`,
  `:1884`) override `on_click` specifically to dodge this bypass (t1210_4).

Intended outcome: `toggle_children` becomes unreachable from *every* dispatch
surface wherever the gate says it is unavailable, and a double-click in a
derived view does the sensible thing instead — open the details modal, matching
the By-Trail precedent.

## Approach

Two layers, mirroring the existing convention in this file where view-scoped
actions re-assert their own guard (`action_sort_topic` `:6054`,
`action_trail_task` `:6930` both re-check `base_filter` internally):

1. **Structural guard in the action** — `action_toggle_children` consults
   `check_action` itself, so *any* dispatch surface (present or future,
   keyboard, mouse, programmatic) is covered. This is the fix for the bypass.
2. **Gate consult in `on_click`** — so a double-click in a derived view falls
   through to `action_view_details()` rather than becoming a dead click.

`check_action` stays the single source of truth; no predicate is duplicated.

## Changes

### 1. `.aitask-scripts/board/aitask_board.py` — `action_toggle_children` (`:7394`)

```python
    def action_toggle_children(self):
        # Every dispatch surface routes through here — the footer/keyboard
        # binding (which Textual already gates) and TaskCard's double-click.
        # Re-assert the gate so no caller can bypass the derived-view
        # exclusion (In-Flight / By-Topic / By-Trail render children directly).
        if self.check_action("toggle_children", None) is not True:
            return
        self._toggle_expand()
```

`is not True` matches Textual's own binding dispatch semantics (`None` = shown
but disabled ⇒ not runnable); the board's `check_action` only ever returns
`True`/`False` for this action.

### 2. `.aitask-scripts/board/aitask_board.py` — `TaskCard.on_click` (`:1652`)

```python
    def on_click(self, event):
        self.focus()
        if event.chain == 2:
            # Collapsed parent with children → expand instead of opening
            # details, but only where toggle_children is actually available:
            # check_action hides it in the derived views, and the mouse path
            # must honor the same gate (otherwise it silently mutates
            # expanded_tasks there). Falls through to details when gated off.
            if not self.is_child and \
                    self.app.check_action("toggle_children", None) is True:
                task_num, _ = TaskCard._parse_filename(self.task_data.filename)
                children = self.manager.get_child_tasks_for_parent(task_num)
                if children and self.task_data.filename not in self.app.expanded_tasks:
                    self.app.action_toggle_children()
                    return
            self.app.action_view_details()
```

Focus ordering is unchanged: the first click of the chain already focused the
card (Textual defers `focus()` via `call_next`), so `check_action`'s
`_focused_card()` resolves to this card — the same card `_toggle_expand()`
already acts on.

### 3. `.aitask-scripts/board/aitask_board.py` — `TrailTaskCard.on_click` comment (`:1838-1840`)

The `TrailTaskCard` / `TrailGhostCard` overrides are **kept** (explicit By-Trail
intent, and `TrailGhostCard` carries `manager=None`, so never reaching the
base's `get_child_tasks_for_parent` is a real safety property). Only the now
stale comment ("the base handler calls action_toggle_children directly,
bypassing its check_action gate") is corrected to say the base is now gated and
these overrides state the By-Trail behavior explicitly.

### 4. New test — `tests/test_board_toggle_children_gate.py`

Pilot tests driving the real `KanbanApp` against the live repo, in the style of
`tests/test_board_topic_view.py` (same `setUpClass` / `_run` / `_enter_bytopic`
harness) and `tests/test_board_footer_visibility.py`:

- `test_bytopic_double_click_does_not_expand` — enter By-Topic, pick the first
  non-child `TaskCard`, patch `manager.get_child_tasks_for_parent` to report
  children (so the card is exactly the "collapsed parent with children" shape
  that triggered the bug regardless of repo contents), stub
  `app.action_view_details` with a `Mock`, `await pilot.click(card, times=2)`.
  Assert `app.expanded_tasks` is unchanged **and** `action_view_details` was
  called once (the fall-through).
- `test_all_view_double_click_still_expands` — **positive control** proving the
  assertion above is not vacuous: identical double-click in the default `all`
  view on a real parent-with-children card adds its filename to
  `expanded_tasks` (skip if the repo has no such card on the board).
- `test_action_toggle_children_is_noop_in_derived_view` — **negative control**
  for the structural guard: in By-Topic, focus a card and call
  `app.action_toggle_children()` directly (the non-mouse dispatch surface);
  assert `expanded_tasks` is unchanged.

The file is auto-discovered by `tests/run_all_python_tests.sh`; it guards
against zero collection by asserting at least one card exists before the
click (t1229 convention).

## Verification

```bash
bash tests/run_all_python_tests.sh -k toggle_children_gate   # new tests
python3 -m pytest tests/test_board_topic_view.py tests/test_board_bytrail_view.py \
    tests/test_board_footer_visibility.py tests/test_board_inflight_view.py -v
```

Harness-can-fail proof: temporarily revert the `action_toggle_children` guard
and confirm `test_action_toggle_children_is_noop_in_derived_view` exits 1;
revert the `on_click` gate and confirm
`test_bytopic_double_click_does_not_expand` exits 1. The positive control must
keep passing in both cases (it proves the click machinery works).

Manual (optional): `ait board` → `y` (By-Topic) → double-click a parent card →
detail modal opens, no lane re-render; `a` (All) → double-click a collapsed
parent → children expand as before.

## Risk

### Code-health risk: low
- None identified.

### Goal-achievement risk: low
- None identified.

## Step 9 — Post-Implementation

Standard: commit code (`bug: … (t1245)`) + plan via `./ait git`, then merge
approval, gate run, and archival per `task-workflow` Step 9. No worktree/branch
cleanup (profile `fast` works on the current branch).
