---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [aitask_board, tui]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5
created_at: 2026-07-26 00:19
updated_at: 2026-07-26 01:00
completed_at: 2026-07-26 01:00
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

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-25T21:44:05Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-25T21:57:18Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-25T22:00:02Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:8c5d728f572ae13b

> **✅ gate:risk_evaluated** run=2026-07-25T22:00:02Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1245/risk_evaluated_2026-07-25T22:00:02Z-risk_evaluated-a1.log`
