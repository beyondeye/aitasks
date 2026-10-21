---
Task: t2089_fix_trails_parent_card_double_click_crash.md
Base branch: main
Output branch: main
---

# t2089 — Fix the trails parent-card double-click crash

## Context

Double-clicking a live **parent** card (one whose children the manager has loaded)
in stand-alone `ait trails` crashes with
`AttributeError: 'TrailsApp' object has no attribute 'expanded_tasks'`.

Root cause (verified against Textual 8.2.7 `MessagePump._get_dispatch_methods`):
Textual yields `on_<event>` for **every class in the MRO** and stops only when
`message._no_default_action` is set, i.e. after `event.prevent_default()`.
`TrailTaskCard.on_click` / `TrailGhostCard.on_click` never call it, so the base
`TaskCard.on_click` (`board_widgets.py:499`) runs too. In `TrailsApp`,
`check_action("toggle_children")` falls through to `return True`, so the base
handler reads `self.app.expanded_tasks` → crash. In `ait board`'s By-Trail view
(and on TrailsApp leaf / ghost cards) the base handler instead calls
`action_view_details()` a **second** time; it is a no-op only because the
modal is already on top and `_focused_card()` returns None.

Note: `prevent_default()` also skips `Widget._on_click` for the card itself
(text select-all on a double-click landing on the card's own border cell, and
`broker_event("click")` for `@click` meta). Trail cards carry no `@click`
markup and their Labels dispatch their own `Widget._on_click` before the
bubble reaches the card, so nothing observable is lost.

## Implementation

### 1. `.aitask-scripts/board/board_trail_view.py`
- `TrailTaskCard.on_click` (~line 525): call `event.prevent_default()` first;
  replace the now-wrong comment ("The base handler now consults check_action …
  so this override only states that behavior explicitly") with: Textual runs
  `on_click` for every class in the MRO; only `prevent_default()` keeps the base
  `TaskCard.on_click` (expand-children / second detail open) from running too.
- `TrailGhostCard.on_click` (~line 583): same `event.prevent_default()` plus a
  one-line comment pointing at the TrailTaskCard note.

### 2. `.aitask-scripts/board/trails_app.py` — `check_action` (~line 774)
Add `toggle_children` to the always-False group next to
`("trail_move_wave", "trail_sync")` (own branch with its own comment: no such
binding here, no children to expand, so the gate must not answer True).

### 3. `.aitask-scripts/board/board_widgets.py`
- `CardHost` docstring (~line 110): replace "`action_toggle_children` is reached
  only from `TaskCard.on_click`, which the trail cards override" with the true
  rule: it is reached only from `TaskCard.on_click`; overriding `on_click` does
  NOT stop it (Textual dispatches every MRO handler) — the trail cards call
  `event.prevent_default()`, and that is what keeps a host mounting only trail
  cards from touching `marked` / `expanded_tasks` / `action_toggle_children`.
- Leave `TaskCard.on_click`'s own comment as is (it is accurate).
- `tests/test_board_widgets.py:~130` (`test_a_host_missing_a_member_is_reported`)
  is a generic Protocol-checker test; its SimpleNamespace is not a claim about
  TrailsApp, so it stays unchanged.

### 4. Regression tests

**`tests/test_trails_app.py`** — new `TrailCardDoubleClickTests(TrailsAppTestBase)`.
The default fixture's first member `t9000_parent.md` has children `9000_1`/`9000_2`;
the second (`t9001`) is a leaf; `99999` is a ghost.

- helper `_double_click(app, pilot, card)`: `await pilot.click(card, times=2)` then settle.
- `test_parent_card_double_click_opens_one_detail`: boot + select; precondition
  assert (anti-vacuity) `app.manager.get_child_tasks_for_parent("9000")` is non-empty;
  wrap `app.action_view_details` with a counting pass-through to the real method;
  double-click the parent card; wait for `TrailDetailScreen`; assert call count == 1
  and exactly one `TrailDetailScreen` in `app.screen_stack`; no exception
  (run_test re-raises a handler exception at block exit).
- `test_base_card_click_handler_never_runs_for_trail_cards`: patch
  `board_widgets.TaskCard.on_click` with a recording spy and `app.action_view_details`
  with a counting no-op; double-click parent, leaf and ghost cards in turn; assert
  the spy recorded nothing and each double-click produced exactly one view_details call.
- `test_toggle_children_is_gated_off`: `app.check_action("toggle_children", None) is False`.
- Negative controls (durable, in-file, not hand mutants):
  - `test_control_without_prevent_default_double_opens`: patch
    `TrailTaskCard.on_click` with the pre-fix body (focus + view_details, no
    `prevent_default`); same parent scenario → view_details count == 2 (so the
    main test's `== 1` assertion is what would fail).
  - `test_control_pre_fix_crashes`: pre-fix body AND `TrailsApp.check_action`
    patched to answer True for `toggle_children` → `assertRaises(AttributeError)`
    around the run_test block, message mentions `expanded_tasks`. Proves the
    fixture really reaches the original crash path.

**`tests/test_board_bytrail_view.py`** — one test in `ByTrailPilotTests`:
`test_double_click_runs_only_the_trail_card_handler`: `KanbanApp`,
`_enter_synthetic_bytrail` with `_wave_doc(["9000", "9001", "99999"])`, spy
`TaskCard.on_click` + counting no-op `app.action_view_details`; double-click each
card (live parent, live leaf, ghost) → spy empty, one call per double-click.
Pre-fix this sees 2 calls per card (board's `check_action` hides toggle_children,
so the base handler falls through to view_details).

## Verification
- `~/.aitask/venv/bin/python -m pytest tests/test_trails_app.py tests/test_board_bytrail_view.py tests/test_board_widgets.py -q`
- Red proof: before steps 1–2 land, run the new tests and confirm they fail
  (count 2 / AttributeError); after, they pass.
- `bash tests/run_all_python_tests.sh` — read the last line verdict.

## Step 9 (Post-Implementation)
Commit code (`bug: … (t2089)`), plan via `aitask_task_commit.sh`, then archive per
the workflow's Step 9.

## Risk

### Code-health risk: low
- `prevent_default()` also suppresses `Widget._on_click` on the card itself (select-all on a card-border double-click, `@click` meta broker); trail cards use neither · severity: low · → mitigation: None needed (documented in Context)

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** As planned. `TrailTaskCard.on_click` / `TrailGhostCard.on_click` call `event.prevent_default()` (comment explains MRO dispatch); `TrailsApp.check_action` answers False for `toggle_children`; the `CardHost` docstring now states that only `prevent_default()` keeps the base handler out. Tests: `TrailCardDoubleClickTests` in `tests/test_trails_app.py` (parent single-detail, base-handler-never-runs over parent/leaf/ghost, gate-off, two in-file negative controls) and `test_double_click_runs_only_the_trail_card_handler` in `tests/test_board_bytrail_view.py`.
- **Deviations from plan:** None in substance. The test helper derives the child-lookup key with `TaskCard._parse_filename` (`t9000`, not `9000`) — `get_child_tasks_for_parent` matches the `t<N>_` prefix, and the anti-vacuity precondition caught the bare-number mistake.
- **Issues encountered:** None beyond the above. Red proof before the fix: the main test raised the reported `AttributeError: 'TrailsApp' object has no attribute 'expanded_tasks'`; the base-handler spy recorded 6 calls (2 clicks × 3 cards) in both the TrailsApp and the board By-Trail tests. After the fix: 306 passed across the four affected modules; full suite `PYTHON SUITE: PASSED (runner=pytest, exit=0)`.
- **Key decisions:** Negative controls are durable in-file tests (patching the pre-fix handler / gate) rather than hand mutants. The double-open control asserts `view_details` count == 2 — a screen-stack count alone cannot catch the regression, because the second call is a no-op once the modal is on top (`_focused_card()` returns None).
- **Upstream defects identified:** None
