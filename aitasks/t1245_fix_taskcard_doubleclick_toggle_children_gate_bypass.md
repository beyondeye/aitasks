---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_board, tui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-26 00:19
updated_at: 2026-07-26 00:26
---

## Origin

Spawned from t1210_4 during Step 8b review.

## Upstream defect

- `.aitask-scripts/board/aitask_board.py:1337` — `TaskCard.on_click` double-click calls `action_toggle_children()` directly, bypassing its `check_action` gate. In the By-Topic view (where `check_action` hides `toggle_children` because every relevant card is rendered directly), double-clicking a collapsed parent card with children still mutates `expanded_tasks` and triggers a refresh, even though the action is deliberately unavailable there.

## Diagnostic context

Found while building the By-Trail view (t1210_4): the new `TrailTaskCard`/`TrailGhostCard` had to override `on_click` specifically to avoid inheriting this bypass (double-click now routes to `action_view_details` in By-Trail). The base `TaskCard.on_click` path predates t1210_4 and still bypasses the gate in By-Topic:

```python
def on_click(self, event):
    self.focus()
    if event.chain == 2:
        if not self.is_child:
            task_num, _ = TaskCard._parse_filename(self.task_data.filename)
            children = self.manager.get_child_tasks_for_parent(task_num)
            if children and self.task_data.filename not in self.app.expanded_tasks:
                self.app.action_toggle_children()   # no check_action consult
                return
        self.app.action_view_details()
```

`action_toggle_children` itself has no internal view guard (`def action_toggle_children(self): self._toggle_expand()`), so the `check_action` exclusion (`base_filter in ("inflight", "bytopic", "bytrail") → False`) protects only the keyboard/footer surface, not the mouse path.

## Suggested fix

Guard the double-click branch on the same predicate `check_action` uses (or call `check_action("toggle_children", None)` before dispatching); alternatively add the derived-view guard inside `action_toggle_children` itself so every dispatch surface is covered. Add a Pilot regression: double-click a collapsed parent in By-Topic → `expanded_tasks` unchanged.
