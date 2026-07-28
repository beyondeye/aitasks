---
Task: t1213_manual_verification_board_focusable_empty_columns_followup.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1213 — Manual verification (auto-executed): board focusable empty columns

Verifies t1209 (`aiplans/archived/p1209_board_focusable_empty_columns.md`).

## Method

All nine items were driven against the **real** `ait board` TUI in a detached
tmux session (200x50), not against a test harness. Two things made that safe
and deterministic:

- **Sandbox `TASK_DIR`.** `.aitask-scripts/lib/config_utils.py:74` honours a
  `TASK_DIR` env override, so the board was launched with
  `TASK_DIR=<scratch>/aitasks ./ait board` against a synthetic tree
  (`Left(2) | Empty(0) | Right(2)`, one parent with two children). The live
  `aitasks/metadata/board_config.json` and `board_config.local.json` were never
  read or written — confirmed at the end with `git status --porcelain
  aitasks/metadata/` (clean). Column reorder and collapse **do** persist via
  `save_metadata()`, so this isolation is load-bearing, not cosmetic.
- **Focus read from the rendered pane, not from app state.** `tmux capture-pane
  -p -e` was parsed for SGR background runs: the focused placeholder renders at
  `bg=rgb(12,48,76)` (the `$primary 30%` accent) against the default
  `rgb(18,18,18)`, and a focused `TaskCard` switches from `┌─┐` to a `╔═╗`
  double border. Every "focus stayed on X" claim below is a pixel-level
  assertion about what the user actually sees.

## Execution Log

### Item 1 — empty column takes focus
- Item text: Create/keep a board column with no tasks; arrow onto it — a dim "(empty)" row takes focus
- Approach: TUI interaction (tmux)
- Action run: launch board → `Escape` (focus board, lands on first card) → `Right`
- Output (trimmed): `Empty (0)` column renders a centred `(empty)` row; after
  `Right`, that row carries `bg=48;2;12;48;76` while both card columns stay at
  `bg=48;2;18;18;18`
- Verdict: pass

### Item 2 — ctrl+left / ctrl+right move the empty column
- Item text: ctrl+left / ctrl+right move the empty column, and focus stays on it after each move
- Approach: TUI interaction + on-disk config assertion
- Action run: `C-Left`, then `C-Right` ×2, capturing the header row, the
  sandbox `board_config.json` `column_order`, and the accent bg after each
- Output (trimmed): order went `[zz_left, zz_empty, zz_right]` →
  `[zz_empty, zz_left, zz_right]` → `[zz_left, zz_empty, zz_right]` →
  `[zz_left, zz_right, zz_empty]`; `(empty)` held the accent bg at every step
- Verdict: pass

### Item 3 — X collapse/expand keeps the empty column focused
- Item text: X collapses/expands the empty column; it stays focused across the toggle
- Approach: TUI interaction
- Action run: `X` (collapse) → capture → `X` (expand) → capture
- Output (trimmed): collapsed narrow column renders `Empty / (0) / ▶ / ···`
  with `···` at `bg=48;2;12;48;76`; after re-expanding, `(empty)` carries the
  accent bg again
- Verdict: pass

### Item 4 — collapsed *populated* column can be reordered
- Item text: Collapse a populated column and reorder it with ctrl+arrow (previously impossible)
- Approach: TUI interaction + on-disk config assertion
- Action run: navigate to `Left(2)` (focused card shows `╔═╗`) → `X` → `C-Right`
- Output (trimmed): `collapsed_columns: ['zz_left']`; focus moved to that
  column's `···` (accent bg) on collapse; `C-Right` reordered to
  `[zz_right, zz_left, zz_empty]` with the `···` still accented. This is the
  case `_shift_column`'s old `_focused_card()` early-return made impossible.
- Verdict: pass

### Item 5 — no-match search
- Item text: Type a no-match string in the search box: every column shows "(empty)" and focus moves off the hidden card; clear it and focus returns to a card
- Approach: TUI interaction
- Action run: focus a card (`╔═╗` on `t3 charlie`) → `Tab` → type
  `zzznomatchzzz` → capture → `Escape` → capture → `Tab` → 13×`BSpace` →
  `Escape` → capture
- Output (trimmed): under the filter all three columns render `(empty)` and
  **zero** card rows survive; `Escape` puts the accent bg on the first
  column's placeholder (focus cannot be resting on a hidden card — none are
  rendered). After clearing, `t3 charlie` is drawn with the `╔═╗` focused
  border again and all placeholders drop back to `bg=None`.
- Verdict: pass

### Item 6 — `r` and the auto-refresh tick preserve focus
- Item text: Press r (and wait for an auto-refresh tick) while an empty/collapsed column is focused — focus is preserved
- Approach: TUI interaction ×2 (manual key + timer), second board instance
- Action run: (a) focus `(empty)` → `r`; (b) `X` to collapse → `r`;
  (c) second sandbox with `auto_refresh_minutes: 1`, focus `(empty)`, then
  **write a new task file into the sandbox** and wait ~70 s without touching
  the keyboard
- Output (trimmed): (a) and (b) both kept the accent bg on `(empty)` / `···`.
  (c) `Right (2)` became `Right (3)` with `t9 tickproof` rendered — proving
  `_auto_refresh_tick` → `_refresh_board_data()` actually fired rather than
  merely that time passed — and `(empty)` still carried the accent bg.
  The tick path is distinct from `action_refresh_board`, so it needed its own
  evidence.
- Verdict: pass

### Item 7 — no bare `↳` connector row survives a filter
- Item text: Expand a parent with children, then filter to no matches — no bare "↳" connector row survives
- Approach: TUI interaction
- Action run: focus parent `t1 alpha` → `x` (expand children) → confirm two
  `↳ ╏ t1_1 … ╏` / `↳ ╏ t1_2 … ╏` rows render → `Tab`, type `zzznomatchzzz`
- Output (trimmed): before the filter, 2 connector rows; after it,
  `grep -c '↳'` = 0 and `grep -c '╍'` (child-card border glyph) = 0
- Verdict: pass

### Item 8 — focus follows a moved card (partial-refresh regression)
- Item text: Move a task between columns / up / down — focus still follows the card (partial-refresh regression check)
- Approach: TUI interaction
- Action run: `S-Down` (vertical), `S-Right` (lateral, cross-column), `S-Up`
  (vertical in the new column), then `S-Right` on the *last* card of a column
- Output (trimmed): the moved card kept the `╔═╗` focused border after every
  move — including the cross-column move (`Right (2)`→`(1)`, `Left (2)`→`(3)`).
  Emptying a column outright (`Right (1)`→`(0)`) rendered its `(empty)`
  placeholder while focus followed `t4 delta` into the destination column —
  the `_refocus_card` → `_refocus_column` fallback behaving as designed.
- Verdict: pass

### Item 9 — end-to-end in tmux
- Item text: TODO: verify .aitask-scripts/board/aitask_board.py end-to-end in tmux
- Approach: TUI interaction + test suite
- Action run: the full session above (launch, lateral nav, column reorder,
  collapse/expand, search filter, child expand, task moves, manual and timed
  refresh) plus
  `python -m unittest tests.test_board_empty_column_focus -v`
- Output (trimmed): `Ran 12 tests … OK`; both panes' 2000-line scrollback
  contains no `Traceback` / `Exception` / `Error`; both board processes stayed
  alive for the whole run; `git status --porcelain aitasks/metadata/` clean
- Verdict: pass

## Observation outside this checklist (not a t1209 regression)

Switching to the **In-Flight** view (`i`) and back to **All** (`a`) leaves the
board with *no* focused widget — no card shows the `╔═╗` border and no
placeholder shows the accent bg — until the user presses `Escape`. The
In-Flight view composes its own lane layout (`Needs your action` /
`Agent can continue` / `Blocked`) whose empty state is a plain `No tasks`
`Static`, so it never had a focusable anchor for `refresh_board`'s
`refocus_col_id = … or self._get_focused_col_id() or ""` capture to latch onto;
the column identity is gone by the time the All view is rebuilt. This is
pre-existing and orthogonal to t1209 (which only ever promised an anchor for
*board* columns), and it is outside this checklist's scope — recorded here so
it is not lost.

## Cleanup

- tmux sessions `t1213board`, `t1213auto` — killed.
- Scratch trees `<scratchpad>/t1213_board`, `<scratchpad>/t1213_board_auto`,
  and `<scratchpad>/focusprobe.py` — removed.
- No files under `aitasks/` or `aiplans/` were mutated other than this plan and
  the t1213 checklist itself.
