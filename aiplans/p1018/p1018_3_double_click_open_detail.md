---
Task: t1018_3_double_click_open_detail.md
Parent Task: aitasks/t1018_brainstorm_op_restart_dblclick_footer_hygiene.md
Sibling Tasks: aitasks/t1018/t1018_*.md
Archived Sibling Plans: aiplans/archived/p1018/p1018_*_*.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-21 13:01
---

# p1018_3 — Running-tab op double-click expand + focus-preservation on refresh

Independent child of t1018. Two tightly-coupled changes to the **Running tab**
of `ait brainstorm` (`.aitask-scripts/brainstorm/brainstorm_app.py`):

1. **Double-click an operation (group) row → expand/collapse the group**
   collapsible (the same toggle `Enter` performs today). It does **not** open the
   operation detail screen.
2. **Fix:** the focused operation group **loses focus when its status
   refreshes** (every 30 s, and after agent mutations). Preserve focus across
   the refresh.

They are coupled: double-clicking a group to toggle it is pointless if the
periodic refresh keeps stealing focus right after.

## Context

The Running tab (post-t983 rename of the old Status tab) lists operation groups
as `GroupRow` widgets, each an expand/collapse collapsible toggled by `Enter`.
Mouse users have no way to expand a group — single-click only focuses it. The
user wants **double-click to toggle expand/collapse** (mirroring `Enter`).
Separately, the Running tab rebuilds its rows on a 30 s timer and after every
agent action, and the rebuild drops the user's focus — so position is lost
mid-operation.

**Scope decisions (explicit, user-confirmed):**
- **Running-tab GroupRow only.** The Browse `NodeRow` / DAG-node double-click in
  the original umbrella body (t1018 "Child 2") is **dropped** from t1018_3.
- **Double-click = expand/collapse**, *not* open `OperationDetailScreen`.
The task body AC is updated to match (Step 0) so neither narrowing is silent.

## Verified current state (line numbers current as of 2026-06-21)

- `GroupRow` class at `brainstorm_app.py:3122`. Its `on_click` (`:3175-3176`)
  currently is `def on_click(self) -> None: self.focus()` — **no `event`
  parameter**, so reading `event.chain` requires adding it. Stable identity:
  `self.group_name` (groups-dict key).
- **Enter toggle lives inline in the App's `on_key`** (`:5878-5889`): on a
  focused `GroupRow` it adds/discards `self.group_name` in `self._expanded_groups`
  (init `:5630`) and calls `self._refresh_status_tab()`. There is **no reusable
  toggle method yet** — Step 2 extracts one.
- **Refresh / focus loss:** `_refresh_status_tab()` (`:7450`) calls
  `container.remove_children()` (`:7464`, destroying the focused GroupRow) then
  re-mounts fresh `GroupRow`s (`:7566-7574`). It runs on a 30 s timer
  (`set_interval(30, self._refresh_runtime)`, `:6746`), on tab activation
  (`:7415`), and ~2 s after agent reset/retry/cleanup (`:7873`). Expansion
  survives because it is re-derived from `self._expanded_groups` (`:7561`); focus
  has no equivalent → it is dropped.
- Reference patterns:
  - Double-click: `board/aitask_board.py:1263-1273` (`TaskCard.on_click`,
    `if event.chain == 2:`). The **only** `chain == 2` use in the repo. Textual's
    `events.Click` carries `chain: int` (default 1).
  - Focus restore: `aitask_board.py` `_refocus_card` saves the focused identifier
    before `remove_children()`, re-focuses by match after.

## Implementation steps

### Step 0 — Update task AC to the narrowed scope (post-approval, before coding)
Edit `aitasks/t1018/t1018_3_double_click_open_detail.md`: replace the
three-surface / open-detail plan with "Running-tab GroupRow double-click toggles
expand/collapse + focus-preservation on refresh," so the task definition matches
what is built. Commit via `./ait git`.

### Step 1 — Preserve focus across Running-tab refresh
In `_refresh_status_tab()` (`:7450`):
1. **Before** `container.remove_children()` (`:7464`), capture the focused
   group's key:
   ```python
   focused_group = next(
       (row.group_name for row in self.query(GroupRow) if row.has_focus), None
   )
   ```
2. **After** the new `GroupRow`s are mounted (after the mount loop, ~`:7576`),
   re-focus the same group if it still exists — a tiny helper mirroring board's
   `_refocus_card`, parallel to the `_expanded_groups` preservation:
   ```python
   if focused_group is not None:
       for row in self.query(GroupRow):
           if row.group_name == focused_group:
               row.focus()
               break
   ```
   If the focused group disappeared from the rebuild, focus is simply not
   restored (acceptable — same as board).

### Step 2 — GroupRow double-click → expand/collapse (reuse the Enter toggle)
1. **Extract a shared toggle** on the App, e.g.
   `_toggle_group(self, name: str)` that does the `_expanded_groups`
   add/discard + `self._refresh_status_tab()` currently inlined at `:5882-5886`.
   Point the **Enter** handler (`:5880-5889`) at it so both paths share one
   implementation.
2. **Make `GroupRow.on_click` chain-aware.** Change its signature to
   `def on_click(self, event) -> None`. On `event.chain == 2`, request the
   toggle for `self.group_name`; otherwise `self.focus()` (single-click,
   unchanged — no `prevent_default`). Because the toggle lives on the App, post a
   small message (e.g. `GroupRow.ToggleRequested(self.group_name)`) and add an
   App handler `on_group_row_toggle_requested` that calls
   `self._toggle_group(event.group_name)` — mirroring how `OperationOpened` is
   routed. (Do **not** open `OperationDetailScreen`.)
3. Step 1's focus preservation keeps the group focused through the toggle's
   `_refresh_status_tab()` rebuild — the two steps reinforce each other.

### Out of scope (explicitly dropped from this task)
Opening `OperationDetailScreen` on double-click; Browse `NodeRow` double-click;
DAG-node double-click. Do not touch `NodeRow`, `_DAGStatic.on_click`,
`_handle_click`, or `OperationRow.on_click` (`:2815-2819`, wizard list only).

## Key files
- `.aitask-scripts/brainstorm/brainstorm_app.py` — `_refresh_status_tab()` focus
  capture/restore (Step 1); extract `_toggle_group()` + repoint Enter + chain-
  aware `GroupRow.on_click` + `ToggleRequested` message/handler (Step 2).
- `aitasks/t1018/t1018_3_*.md` — scope/AC update (Step 0).

## Risk

### Code-health risk: low
- Focus capture/restore is additive and mirrors an established pattern
  (`_refocus_card`, `_expanded_groups`). · severity: low · → mitigation: restore
  is best-effort (no-op if the group vanished); pilot test.
- Extracting `_toggle_group` and routing double-click through a message touches
  the Enter path; hazard is a behavior change to Enter or swallowing single-click
  focus. · severity: low · → mitigation: Enter keeps calling the same extracted
  logic; `on_click` single-click branch unchanged (no `prevent_default`); pilot
  tests cover Enter, single-click, double-click.

### Goal-achievement risk: low
- Headless tests can simulate a refresh and a `chain == 2` Click but cannot
  exercise the real 30 s timer or terminal→tmux mouse delivery. · severity: low ·
  → mitigation: live verification (double-click toggles a group; focus survives a
  real status refresh) is owned by the aggregate manual-verification sibling
  **t1018_4** — ensure its checklist has both lines (add during Step 8c follow-up
  if absent).

## Verification
- **Focus fix (pilot test):** mount the Running tab with ≥2 groups, focus one
  GroupRow, invoke `_refresh_status_tab()`, assert the same `group_name` row has
  focus afterward; assert a vanished focused group degrades gracefully (no
  crash).
- **Double-click toggle (pilot test):** construct a Textual `Click` with
  `chain == 2` on a GroupRow → assert its `group_name` membership in
  `_expanded_groups` toggled (and a re-render happened). Assert `chain == 1` only
  focuses (no toggle), and that `Enter` still toggles via the shared
  `_toggle_group` (regression check that the extraction preserved Enter).
- Full brainstorm suite green (`tests/test_brainstorm_*`).
- Live: double-click an op group → it expands/collapses; let the tab auto-refresh
  while a group is focused → focus retained. Covered by t1018_4.

## Step 9 — Post-implementation
Archive via `./.aitask-scripts/aitask_archive.sh 1018_3`. Parent stays active
until t1018_4 (the remaining sibling) lands.

## Post-Review Changes

### Change Request 1 (2026-06-21 13:34)
- **Requested by user:** Hovering the *focused* operation group flipped its
  background from the focus orange to the gray hover color — confusing. Hover
  over a focused group should read as a shade of the focus orange instead.
- **Root cause:** `GroupRow:focus` (`background: $accent`) and `GroupRow:hover`
  (`background: $surface-lighten-1`) are equal-specificity single-pseudo rules;
  `:hover` is declared after `:focus`, so a focused+hovered row took the gray.
- **Changes made:** Added a higher-specificity `GroupRow:focus:hover` rule
  (`background: $accent-lighten-1; color: $text;`) so hovering a focused group
  stays in the accent family. App still boots (CSS parses; pilot tests green).
- **Files affected:** `.aitask-scripts/brainstorm/brainstorm_app.py` (CSS block).
- **Note:** the sibling Running-tab rows (`AgentStatusRow`, `ProcessRow`, etc.)
  share the same `:focus`/`:hover` pattern; left unchanged per the user's
  operation-group-scoped request.

## Final Implementation Notes
- **Actual work done:** In `.aitask-scripts/brainstorm/brainstorm_app.py`:
  (1) `GroupRow` gained a `ToggleRequested` message and a chain-aware
  `on_click(self, event)` — `chain == 2` posts the message, single-click focuses;
  (2) extracted `_toggle_group(name)` (the `_expanded_groups` toggle + refresh)
  and repointed the `Enter` handler at it; added the App handler
  `on_group_row_toggle_requested`; (3) `_refresh_status_tab` now captures the
  focused group's `group_name` before `remove_children()` and restores it via
  `call_after_refresh(self._refocus_group, …)` (new helper) after re-mount;
  (4) added a `GroupRow:focus:hover` CSS rule (`$accent-lighten-1`) so a hovered
  focused row stays in the accent family. New test
  `tests/test_brainstorm_group_dblclick_focus.py` (5 tests).
- **Deviations from plan:** Scope was narrowed during planning (user-confirmed):
  Running-tab GroupRow only (Browse/DAG dropped), and double-click toggles
  expand/collapse rather than opening `OperationDetailScreen`. The
  `GroupRow:focus:hover` CSS fix was added during review (Post-Review Change 1),
  not in the original plan.
- **Issues encountered:** `GroupRow.on_click` previously took no `event`
  parameter; added one to read `event.chain`. No other surprises.
- **Key decisions:** Routed the double-click toggle through a `ToggleRequested`
  message (the toggle state lives on the App, not the row); deferred refocus via
  `call_after_refresh` (mirrors `aitask_board.py` `_refocus_card`); used
  `$accent-lighten-1` for hover-on-focus to keep the focused row recognizable.
- **Upstream defects identified:** `.aitask-scripts/brainstorm/brainstorm_app.py:4954-4977 — AgentStatusRow / ProcessRow (and peer Running-tab rows) share the same equal-specificity `:focus`/`:hover` CSS where `:hover` overrides `:focus`, so a focused+hovered row flips to gray; they lack the `:focus:hover` accent rule now added to GroupRow (pre-existing cosmetic inconsistency, left unchanged per the user's operation-group-only scope).`
- **Notes for sibling tasks:** Reusable patterns for t1018_4 / future children:
  the `_toggle_group` extraction (share one toggle impl across key + mouse), the
  focus-preservation pattern (capture `group_name` → `call_after_refresh(
  _refocus_group, …)`), the `GroupRow.ToggleRequested` message, and the
  `:focus:hover` accent CSS idiom. t1018_4 (manual verification) should add
  checklist lines for: live double-click toggles a group, focus survives a real
  Running-tab refresh, and hover-on-focused-group shows the accent shade.
