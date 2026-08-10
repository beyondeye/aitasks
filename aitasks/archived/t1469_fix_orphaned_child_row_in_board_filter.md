---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [aitask_board, tui, python]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5
created_at: 2026-08-10 09:03
updated_at: 2026-08-10 15:16
completed_at: 2026-08-10 15:16
---

## Origin

Spawned from t1243_9 during Step 8b review.

## Upstream defect

- `.aitask-scripts/board/aitask_board.py:231,7873 — apply_filter can leave an
  expanded child card visible under a parent it hid, because
  Task.search_haystack is "<filename> <metadata>" and a parent's corpus never
  contains its children's text; the result is an orphaned "↳" row with no parent
  above it. Predates groups and is independent of them — fixing it would change
  apply_filter semantics for every ungrouped board.`

## Diagnostic context

Surfaced while designing t1243_9's group-header visibility rule
(`_group_header_matches`). The chain of reasoning:

1. `apply_filter`'s unit loop iterates `_filter_units`, which yields
   `self.query(TaskCard)` filtered by the `column_id` **attribute**. Expanded
   child cards carry `column_id` too, so they are evaluated as independent units.
2. Each unit is decided by `task_matches_filter(unit.task_data, ...)` against its
   OWN `search_haystack`, which `Task.search_haystack` (`:231`) builds as
   `f"{self.filename} {self.metadata}".lower()`.
3. A parent's metadata does not contain its children's filenames or text. So a
   search matching only a child's text hides the parent card while leaving the
   child card visible — the child's `.child-wrapper` row remains, rendering a
   bare `↳ t<parent>_<n> …` line under nothing.

Verified live in `tests/test_board_group_focus.py::GroupFilteringTests::test_child_only_match_keeps_the_header_visible`,
whose control asserts exactly this: searching `childone` leaves the child card
visible (`display != "none"`) while the parent card is hidden (`display == "none"`).

t1243_9 worked around the *group* consequence only — a `GroupHeader` is visible
iff >= 1 member **or >= 1 member's child** matches, so a header is never hidden
above a visible child row. The underlying ungrouped case was deliberately left
alone: it predates groups, and changing it alters `apply_filter` semantics for
every board.

## Suggested fix

Two candidate directions, to be decided in planning:

1. **Hide the orphan** — when a parent card is hidden, hide its `.child-wrapper`
   rows too. Cheapest, and consistent with `set_unit_display`, which already
   hides a wrapper when its own child is hidden. But it makes a matching child
   unfindable by search, which is arguably a worse failure.
2. **Show the parent** — treat a child match as a parent match, i.e. make the
   parent's effective corpus include its children's. Matches what a user
   searching for a child almost certainly wants, and matches the rule t1243_9
   already applies to group headers. Costs a child lookup per parent on the
   filter pass, so it should reuse a per-pass index — `_children_by_parent`
   (added in t1243_9) is exactly that seam, built once per pass.

Option 2 is the more likely intent; it also makes the group-header rule and the
parent-card rule consistent instead of divergent. Note the memoization
constraint documented on `Task.search_haystack`: the memo is invalidated at an
enumerated set of sites, so widening the corpus must not introduce a new
staleness path (a parent's memo would then depend on its children's state).

## Verification

- A search matching only a child's text leaves no bare `↳` row: either the child
  is hidden with its parent, or the parent is shown with the child (per the
  option chosen).
- Negative control: the pre-fix behaviour is reproducible (parent hidden, child
  visible) so the test discriminates.
- `tests/test_board_group_focus.py` must stay green — its group-header case pins
  the child-aware rule and must not regress.
- No new whole-board query or per-parent child scan on the `apply_filter` hot
  path; reuse the per-pass index.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-10T11:24:54Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-10T12:12:02Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-10T12:16:15Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:7ded3168da137a6d

> **✅ gate:risk_evaluated** run=2026-08-10T12:16:15Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1469/risk_evaluated_2026-08-10T12:16:15Z-risk_evaluated-a1.log`
