---
Task: t1248_board_column_scroll_jump_on_focus_visible.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
---

# t1248 — Board column scroll jumps to top when focus-driven `scroll_visible` fires mid wheel-scroll

## Context

In `ait board`, wheel-scrolling a task column occasionally snaps back to the top
of the column and scrolling then resumes from there — the user loses their
place. It reproduces only inside tmux; a plain terminal never shows it.

Root cause, established from a 4118-event trace of the real app during a live
mouse session (9 occurrences) and since reduced to a deterministic headless
repro:

1. Wheel scrolling itself is healthy — `KanbanColumn._scroll_to(animate=False)`
   walks `scroll_y` 2, 4, … 158 with `scroll_y == scroll_target_y` throughout.
2. Mid-scroll, a stray `down` / `up` key reaches the app (tmux's
   alternate-screen wheel → cursor-key emulation). The board binds those with
   `priority=True` (`aitask_board.py:5411-5414`), so Textual resolves them at App
   level (`textual/app.py:4137`) and runs `action_nav_down`
   (`aitask_board.py:6422-6435`).
3. `action_nav_down` steps from the **currently focused** card — which is far
   off-screen, because the user scrolled away from it — to `cards[idx + 1]`, a
   card near the top of the column.
4. `TaskCard.on_focus` (`aitask_board.py:1672-1674`) calls `self.scroll_visible()`
   with Textual's defaults `animate=True, immediate=False`. That defers the
   scroll through `call_after_refresh`; it lands mid-scroll and drives the
   column's `scroll_target_y` back to the focused card (target = 8, then 0,
   while `scroll_y` is still 158).
5. The next wheel tick computes `scroll_target_y + scroll_sensitivity_y`
   (`textual/widget.py:3301`), so it resumes from the poisoned target and the
   column snaps to 2.

**Deterministic repro (confirmed against current `main`):** focus the first card
of a column, wheel down 40 ticks (`scroll_y` = 80), press `down` once →
`scroll_y` = 0, next wheel tick → `scroll_y` = 2.

Two distinct defects, both need fixing: change 1 removes the **corruption** (the
stale `scroll_target_y` that makes scrolling resume from the top), change 2
removes the **teleport** (the view dragged back to an off-screen cursor).

## Approach

### 1. Make the focus-driven scroll synchronous — `aitask_board.py:1674`

```python
def on_focus(self):
    self.styles.border = ("double", "cyan")
    self.scroll_visible(animate=False, immediate=True)
```

`immediate=True` removes the `call_after_refresh` deferral, so the scroll can
never land behind input the user has already produced. `animate=False` makes
`scroll_target_y` and `scroll_y` move together, so a subsequent wheel tick —
which reads `scroll_target_y` — always resumes from where the view actually is.

This is the only `scroll_visible` call site in the whole 8400-line file; all four
`TaskCard` subclasses (`InFlightTaskCard:1697`, `TrailTaskCard:1839`,
`TrailGhostCard:1879`) inherit it, so one edit covers every board view.

`scroll_visible` keeps its own pre-layout guard (`if self._size: … else:
parent.call_after_refresh(…)`), so the `_refocus_card` / `_queue_refocus` path
(`:5854`, `:5867`) still defers correctly for freshly-mounted cards.

**Ancestor effect — measured, not assumed.** `scroll_to_widget` walks every
ancestor, including `HorizontalScroll(id="board_container")` (`:5649`), so
lateral navigation scrolls the board horizontally through the same call. I
measured both variants at `size=(120, 50)` (narrow enough that the board
scrolls: `max_scroll_x` = 181): after four `right` presses, current defaults and
`animate=False, immediate=True` both leave `scroll_x = 96.0` with
`scroll_x == scroll_target_x`, before and after settling — **no difference at any
seam a test can observe.** A sub-frame visual difference in the horizontal glide
may still exist; it is accepted as cosmetic, pinned by test 9 below and listed in
the manual-verification checklist. (An earlier draft of this plan asserted the
glide "snaps" after the change — that claim was wrong and is retracted.)

### 2. Nav keys re-anchor to the viewport

New private helpers next to `_visible_column_cards` (`aitask_board.py:6354`):

```python
def _column_widget(self, col_id):
    """The scroll container for a column id, resolved by identity — not by
    walking the DOM (an expanded child card sits inside a Horizontal
    .child-wrapper, and VerticalScroll is also used for modal bodies)."""

def _card_fully_visible(self, card) -> bool:
    """True when the card's rows lie wholly inside its column's
    scrollable_content_region. VERTICAL AXIS ONLY: that region shrinks by one
    column on the right the moment the vertical scrollbar appears, and a
    `width: 1fr` child card can round a cell wide, so an x-axis test yields
    permanent false negatives. Fails OPEN (True) when either region is
    unlaid-out, so a pre-layout or hidden card never triggers a re-anchor."""

def _viewport_anchor(self, cards, focused):
    """The card to re-anchor onto.

    Candidates: cards fully inside the viewport; when there are NONE — a short
    pane where every card is clipped — fall back to cards merely OVERLAPPING
    the viewport. Without that fallback the anchor would be None and the caller
    would step normally, reproducing the very snap-back this fixes.

    Side, not key: focus above the viewport -> first candidate; below -> last.
    Choosing by key direction is wrong (an `up` key with focus above the
    viewport would land on the bottom-most visible card, moving the selection
    forward). Returns None when the side is undeterminable or no candidate
    exists."""
```

Then in `action_nav_up` (`:6406`) and `action_nav_down` (`:6422`), immediately
after `cards = self._visible_column_cards(...)`:

```python
if not self._card_fully_visible(focused):
    anchor = self._viewport_anchor(cards, focused)
    if anchor is not None and anchor is not focused:
        anchor.focus()
        return
    # anchor is the focused card itself, or undeterminable -> fall through to
    # normal index stepping, so a nav key is never a dead end.
```

**Why the overlap fallback is mandatory (measured).** With cards 5-8 rows tall,
the count of *fully* visible cards in the first column is 5 at terminal height
50, 1 at height 24, and **0 at heights 18, 14, 12 and 11** — ordinary sizes for a
split tmux pane. Measured at height 18 with the focus scrolled off-screen:

| | `down` | `up` |
|---|---|---|
| current `main` | **-53 rows** | **+55 rows** |
| fully-visible candidates only | -53 / +55 (anchor is None → steps normally) | |
| **with the overlap fallback** | **0 rows** | **+6 rows** |

So the residual in the worst layout is a **bounded nudge of at most one card
height** (the anchor card is clipped, so bringing it into view costs ≤ its own
height), against a 50+ row rewind today. That bound is pinned by test 4.

### 3. `_nav_lateral` — same rule, explicit scope addition

`_nav_lateral` (`:6470`) carries the focused card's **index** into the target
column (`old_pos` → `_column_focus_target`, `:6377`), so after wheel-scrolling,
`left`/`right` teleports the *target* column to that index. It is the identical
defect one step removed, and leaving it out would read as "the bug is still there
when I press right".

Fix: when the focused card is not fully visible, compute `old_pos` from the
viewport anchor instead of from the focused card. Two lines, reusing the helpers.

**This is beyond the literal wording of the task's acceptance criteria** (which
name only the wheel-scrolled column). Recorded here as an explicit scope
decision; the task's AC gets a matching line added post-approval in Step 7.

### Deliberately not changed

- **No filtering of tmux's synthetic cursor keys.** They are byte-identical to
  real key presses, so any filter is a heuristic that also suppresses genuine
  input. A recency guard (ignore nav within ~200 ms of a wheel event) is
  feasible — but `VerticalScroll._on_mouse_scroll_down` calls `event.stop()`, so
  it would need an override on all four column classes or a `Screen._forward_event`
  hook. More invasive; the re-anchor is the safer first cut and the two are
  compatible. Closes the task's AC item 5.
- **Accepted residual:** a stray key still *moves the selection* (to a visible
  card), so a following `shift+up` / `enter` acts on a different task than
  intended. Much safer than before — the newly selected card is on screen with
  its cyan focus border — but not eliminated. **Tracked as t1256** (created at
  review time; an earlier draft left this as an untracked "candidate follow-up",
  which is not durable tracking).
- **Known uncovered sibling:** `_start_auto_refresh_timer` (`:5685-5691`) →
  `refresh_board` → `_queue_refocus` → `_refocus_card` → `focus()` also yanks the
  column back to the focused card, discarding a wheel position. Different
  trigger, not covered here (`auto_refresh_minutes` is `0` in this repo).
  **Tracked as t1257** (same note as above).

### Docs

`website/content/docs/tuis/board/how-to.md` navigation prose is generic ("Focus
the task card using arrow keys" line 14, "Use **Up/Down** arrows to move between
child cards" line 188) and stays accurate under the re-anchor. No doc change
needed; `docs_updated` is not a declared gate on this task.

## Files to modify

| File | Change |
|---|---|
| `.aitask-scripts/board/aitask_board.py` | `:1674` `scroll_visible(animate=False, immediate=True)`; three helpers near `:6354`; re-anchor guard in `action_nav_up` (`:6406`) and `action_nav_down` (`:6422`); `old_pos` from the anchor in `_nav_lateral` (`:6470`) |
| `tests/test_board_scroll_focus_jump.py` | **new** — Pilot regression suite |

## Tests — `tests/test_board_scroll_focus_jump.py`

Board test conventions: `unittest.TestCase`, `os.chdir(REPO_ROOT)` in
`setUpClass` **before** importing `aitask_board`, `sys.path` inserts for
`.aitask-scripts/board` and `.aitask-scripts/lib`, `async def go()` + `self._run`,
a `_settle(pilot)` helper, and the standard docstring with the
`Run: bash tests/run_all_python_tests.sh` block. Modelled on
`tests/test_board_empty_column_focus.py`; reuse its `_synthetic_board` technique
(in-memory `app.manager` mutation with `save_metadata` stubbed) so the suite does
not depend on how many tasks the repo holds, and `skipTest` when it cannot supply
enough cards.

Wheel input has no Pilot helper in Textual 8.2.7, so a local `_wheel()` helper
posts `events.MouseScrollDown` / `Up` through `app.screen._forward_event` — the
same path the driver uses. A comment records why (first such use in `tests/`).

**Drain discipline (every scroll assertion).** The pre-fix scroll is deferred via
`call_after_refresh` *and* animated, so an assertion that runs too early could
see the un-rewound value and pass against unmodified `main`. Each test therefore
drains explicitly — `_settle(pilot)` plus `await pilot.wait_for_scheduled_animations()`
— and asserts **both** `scroll_y` and `scroll_target_y`, since the poisoned
target is the actual carrier of the bug. (Measured: the baseline rewind is
already complete after 0, 1, 2, 3, 5 and 8 `pilot.pause()` calls, so the proof is
not timing-dependent today; the explicit drain keeps it that way if Pilot's
internal settling changes.)

1. `test_stray_nav_key_does_not_rewind_wheel_scroll` — **the regression.** Focus
   the first card, wheel down 40 ticks, record `scroll_y`/`scroll_target_y`,
   `pilot.press("down")`, drain, send one more wheel tick; assert neither value
   ever decreased. Fails on `main` (80 → 0 → 2).
2. `test_stray_nav_key_up_does_not_rewind` — mirror at the bottom of the column.
3. `test_anchor_side_is_chosen_by_focus_position_not_key` — focus above the
   viewport + `up` must land on the **first** visible card, not the last.
   Assertion form matters: capture the set of fully visible cards *before* the
   key and assert the newly focused card is a member of it (and is its first
   element). Asserting only "focus == first visible card *now*" is not
   discriminating — after `main` rewinds the column, the focused card can
   coincidentally sit at the top of the new viewport; the pre-key membership
   form fails on `main` by construction rather than by luck.
4. `test_short_viewport_nudge_is_bounded_by_one_card` — `size=(200, 18)`, where
   **no** card is fully visible. Assert the post-key movement is ≤ the tallest
   card height (measured ≤ 6 rows) and not the ~53-row rewind `main` produces.
   Pins the overlap fallback and its stated bound.
5. `test_nav_never_dead_ends_on_oversized_card` — card taller than the viewport:
   `down` must still advance the focus (pins the fall-through).
6. `test_focus_scroll_is_immediate_and_unanimated` — construction spy wrapping
   `TaskCard.scroll_visible`, asserting `on_focus` passes
   `animate=False, immediate=True`. Deterministic pin for change 1.
7. `test_nav_from_visible_card_still_steps_one` — negative control: focused card
   on screen → `down` moves to the immediately following card.
8. `test_nav_scrolls_offscreen_card_into_view` — negative control for what
   `on_focus` exists to provide: repeated `down` past the fold leaves the focused
   card fully inside the viewport with `scroll_y` increased.
9. `test_lateral_nav_still_reaches_the_target_column` — `size=(120, 50)` so the
   board scrolls horizontally; four `right` presses must leave
   `board_container.scroll_x` at the same offset as before the change, with
   `scroll_x == scroll_target_x`. Guards the ancestor effect of change 1.
10. `test_lateral_nav_uses_viewport_anchor` — after wheel-scrolling away, `right`
    lands near the viewport position, not the off-screen index.

**Harness proof (required before pinning).** The suite has two kinds of test and
only one kind can prove the regression:

- **Regression pins — MUST fail on unmodified `main`:** tests **1, 2, 3, 4, 6,
  10**. Run the new file against `main` first and confirm each of these fails and
  the runner exits non-zero; only then apply the fix and confirm the whole suite
  passes.
- **Guards — MUST pass in BOTH states:** tests **5, 7, 8, 9**. Test 5 guards a
  dead-end that only the *new* re-anchor code could introduce (`main` already
  advances the focus from an oversized card, so it passes there); tests 7 and 8
  are negative controls for existing navigation behaviour; test 9 pins that the
  ancestor effect of change 1 leaves lateral navigation where it was. Requiring
  any of these to fail on `main` would make the proof step unachievable, so they
  are deliberately excluded from the failure set — but a guard that passes in
  both states still earns its place: it is what catches the fix breaking
  something that used to work.

## Verification

```bash
bash tests/run_all_python_tests.sh -k board     # new suite + no board regressions
bash tests/run_all_python_tests.sh              # full python suite
```

Manual checklist (the environment where it actually bites), covered by the
confirmed risk mitigation below — the Step 8c generic manual-verification offer
will be declined to avoid a duplicate:

- wheel-scroll the Unsorted column both ways for ~30 s in tmux: never snaps back;
- same in a short split pane (≤ 18 rows): at most a one-card nudge;
- keyboard `up`/`down` still walks cards and scrolls them into view, including
  right after wheel-scrolling away from the cursor;
- `left`/`right` between columns still feels the same as before.

## Risk

### Code-health risk: low

- Three new private helpers plus a short guard in two sibling actions and one
  `old_pos` computation, in a file with no uncommitted changes and no in-flight
  branch touching it (HEAD `edeafab5f`). The `scroll_visible` edit is the only
  such call site in the file. · severity: low · → mitigation: none needed
- `animate=False, immediate=True` propagates up the ancestor chain to the
  horizontal board container. · severity: low · → mitigation: none needed —
  measured as no observable change, pinned by test 9
- `t1243` (board task groups and fast reordering) is `Implementing` against the
  same file and may conflict textually. · severity: low · → mitigation: none
  needed — a conflict would be a trivial textual merge

### Goal-achievement risk: medium

- The *trigger* — that tmux emits a cursor key during wheel scrolling — is
  inferred, not directly observed: priority bindings are consumed at App level
  before any seam this session could instrument, so the key itself was never
  captured. The inference is strong (focus advanced by exactly one card in the
  scroll direction across 9 episodes, and `action_nav_up/down` is the only code
  path that does that), and the fix neutralises *any* focus change during an
  active scroll rather than that one trigger — but if the real trigger is
  something else entirely, the symptom could survive. · severity: medium ·
  → mitigation: manual_verification_board_scroll_jump_fix
- In panes too short to show one whole card, the fix leaves a bounded one-card
  nudge rather than zero movement. · severity: low · → mitigation: none needed —
  quantified above and pinned by test 4
- The re-anchor changes keyboard navigation semantics: after scrolling away with
  the wheel, the first `up`/`down` press moves the cursor to the viewport instead
  of stepping from where it was. Intended, and matches how list UIs behave, but a
  user-visible change. · severity: low · → mitigation: none needed — covered by
  tests 3, 7 and 8

### Planned mitigations
- timing: after | name: manual_verification_board_scroll_jump_fix | type: manual_verification | priority: medium | effort: low | addresses: goal-achievement — the tmux cursor-key trigger is inferred, not captured | desc: In a real tmux session work the manual checklist above — wheel-scroll board columns both directions for ~30s confirming no snap-back, repeat in a short split pane, then verify keyboard up/down and left/right still behave

## Step 9 (Post-Implementation)

Profile `fast` works on the current branch, so there is no worktree/branch merge
step. Step 9 runs `./ait gates run 1248` (active set: `risk_evaluated`), then
`./.aitask-scripts/aitask_archive.sh 1248`.

## Final Implementation Notes

- **Actual work done:** Both planned changes landed as designed, plus the
  explicitly-scoped `_nav_lateral` addition. `TaskCard.on_focus`
  (`aitask_board.py:1672`) now calls `scroll_visible(animate=False,
  immediate=True)`. Six new private helpers sit next to `_visible_column_cards`:
  `_column_widgets`, `_column_widget`, `_rows_inside`, `_card_fully_visible`,
  `_viewport_anchor`, `_reanchor_to_viewport`. `action_nav_up` / `action_nav_down`
  call `_reanchor_to_viewport` before stepping; `_nav_lateral` derives `old_pos`
  from the viewport anchor when the focused card is off-screen;
  `_get_visible_col_ids` now derives from `_column_widgets` instead of repeating
  the four-class union. New suite: `tests/test_board_scroll_focus_jump.py`
  (10 tests). Net +114/-8 in the board, one new test file.

- **Deviations from plan:** One, mid-implementation and behaviour-neutral. The
  plan specified `_card_fully_visible` and `_viewport_anchor` as separate
  helpers, which duplicated the row-containment comparison in both. Extracted it
  into a `_rows_inside(viewport, region)` staticmethod so the geometry lives in
  one place and the *fail-open* semantics (`_card_fully_visible` returns True for
  an unlaid-out card) stay visibly separate from it — `_viewport_anchor` must not
  inherit that fail-open behaviour when selecting candidates. The new suite was
  re-run after the refactor (10/10), and the full suite was re-run clean on the
  final code because the first full run had straddled the edit.

- **Issues encountered:**
  - The root cause was not reproducible by any synthetic input. Injected SGR
    wheel sequences — slow ticks, 8-tick bursts, 300-event bursts, both
    directions, with and without a focused card, on the real PyPy runtime in a
    real terminal — scrolled perfectly monotonically. It only reproduced under a
    real mouse, which is what identified the stray cursor key as the trigger.
  - An intermediate diagnosis (a ~40-card "jump back" observed by scraping the
    tmux pane) was wrong and was retracted: task cards render dependency lines
    (`🔗 t1186`), so "first task id in the column" sometimes matched a dependency
    rather than a card title. Fixed by instrumenting the app itself
    (`Widget._scroll_to` / `scroll_visible` / `_size_updated` on `KanbanColumn`)
    instead of reading the screen.
  - The stray key itself was never captured: priority-bound keys are resolved at
    App level (`textual/app.py:4137`) *before* `Screen._forward_event`, so
    screen-level input logging cannot see them. The trigger is therefore inferred
    (focus advanced by exactly one card in the scroll direction across 9 live
    episodes; `action_nav_up/down` is the only path that does that). The fix
    neutralises any focus change during a scroll rather than that one trigger,
    but the inference is the reason goal-achievement risk was rated medium and a
    manual-verification mitigation was attached.
  - A design review caught four defects in the first plan draft, all fixed before
    implementation: an x-axis containment test that would dead-end navigation
    whenever the vertical scrollbar appeared; an anchor chosen by key direction
    instead of by which side the focus fell off; a missing fall-through that
    would have made `up`/`down` a permanent no-op on a card taller than the
    viewport; and a missing overlap fallback.
  - Review of the plan caught that requiring the oversized-card guard to fail on
    unmodified `main` was impossible (it guards a failure mode only the new code
    can produce), so the harness proof was split into regression pins vs guards.

- **Key decisions:**
  - Fix the amplifier, not the trigger. tmux's synthetic cursor keys are
    byte-identical to real ones, so any input-level filter would also suppress
    genuine navigation. Recorded in the plan under "Deliberately not changed";
    the alternative is now tracked as t1256 with a real decision to make.
  - Vertical-axis-only visibility: the columns scroll vertically, and
    `scrollable_content_region` shrinks horizontally the moment a scrollbar
    appears, so an x test carries no information but plenty of false negatives.
  - Bounded, not perfect: in a pane too short to show one whole card (measured:
    zero fully-visible cards at heights 18/14/12/11) the overlap fallback leaves
    a ≤ one-card nudge instead of zero movement, against a ~53-row rewind before.
    The bound is stated in the plan and pinned by a test rather than left
    implicit.
  - `_nav_lateral` was pulled into scope during planning and the task's AC was
    amended (item 6) rather than the widening being left silent.

- **Upstream defects identified:**
  - `aitask_board.py:5685-5691` — `_start_auto_refresh_timer` → `refresh_board`
    → `_queue_refocus` → `_refocus_card` → `focus()` pulls a wheel-scrolled
    column back to the focused card, discarding the user's scroll position. A
    second, independent route to this task's reported symptom, latent here only
    because `auto_refresh_minutes` defaults to `0`. Pre-existing and out of scope
    for this fix; **already tracked as t1257** (created at review time — no
    further follow-up task needed).
