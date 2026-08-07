---
Task: t1377_7_manual_verification_column_features.md
Parent Task: aitasks/t1377_minimonitor_pick_column_action_and_board_column_management.md
Sibling Tasks: (all archived — t1377_1 … t1377_6)
Archived Sibling Plans: aiplans/archived/p1377/p1377_*_*.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# p1377_7 — manual-verification auto-execution record

Autonomous whole-checklist run (`aitask-pick 1377_7`, profile `fast`,
auto-verify = autonomous). 20 items: **18 pass, 2 fail, 0 skip, 0 defer**.

## Method

No item was accepted on unit-test evidence alone. The three surfaces were
driven the way a user drives them:

- **Headless seam** (`aitask_board_column.sh`, `lib/board_columns.py`) against
  throwaway fixture repos under `${TMPDIR}/auto_verify_1377_7/`.
- **Merge engine** (`TaskManager.merge_columns`) driven in-process against
  real files in a fixture repo, then **re-read from disk** with a second
  `TaskManager` so every assertion is about persisted state.
- **Live TUIs** in real tmux panes on a throwaway per-run socket: `ait board`
  at 150×40 and `ait minimonitor` at **40×45** (the companion width the
  checklist names), both against an isolated copy of the framework
  (`ait` + `.aitask-scripts` + a synthetic `aitasks/`), so no user-owned
  config was ever mutated. Focus was read from the composited frame's SGR
  attributes (`capture-pane -pe`), not inferred.

Two fixture projects (`projA`, `projB`) each carrying a **task `t7` with the
same id but different content and different columns** made the multi-session
item (6) a discriminating test rather than a smoke test.

## Execution Log

### Item 1 — three buttons at ~40 cols
- Approach: live minimonitor, 40×45 companion split.
- Action: `p` → `1` → Enter.
- Output: `OK` / `Move to column` / `Cancel` stacked, all fully inside the
  dialog border; narrow variant applied.
- Verdict: **pass**

### Item 2 — pick path unchanged
- Approach: live dialog + diff review.
- Action: chose `OK`; `AgentCommandScreen` rendered with Profile, Agent
  (`claudecode/opus5`), Command (`claude --model claude-opus-5 …`),
  Direct/Tmux, Session, and **Window na(m)e `agent-pick-7`**. Cancelled with
  Esc — no agent was launched.
- `git show f3dbf175b -- monitor/minimonitor_app.py` removes only
  `AgentMarksMixin`, the old `_on_pick_confirmed` signature and `_ok, kill =
  result`; `_launch_pick` is untouched and the pick branch still ends in
  `self._launch_pick(target_id, target_root, kill_pane_id)`.
- Verdict: **pass**

### Item 3 — column picker navigation
- Action: `Move to column` → picker; Up/Down walked
  `Edited → Backlog → Zulu Lane`; `Enter` performed the move; a separate run
  cancelled with `Esc`.
- Output: current column marked `●`; header `Task: t1 · now in: Edited`;
  after Esc the task file was byte-identical.
- Verdict: **pass**

### Item 4 — task lands at the BOTTOM
- Action: `move --task 3 --column backlog` (residents at idx 100, 200) →
  `MOVED:t3_charlie.md|backlog|1224`; pressed `r` on the live board.
- Output: board rendered t4, t5, **t3** — t3 last.
- Verdict: **pass**

### Item 5 — `updated_at` not stamped
- Action: compared frontmatter before/after a seam move and after a real
  minimonitor move.
- Output: `updated_at: 2026-08-01 10:00` in both cases; only `boardcol` /
  `boardidx` changed.
- Verdict: **pass**

### Item 6 — multi-session writes into the followed agent's project
- Setup: sessions `projA` (root `liveboard`) and `projB` (root `liveboard2`),
  both holding a `t7`; companion split into **projB's** window while invoked
  as `liveboard/ait minimonitor`, so `self._project_root` was projA.
- Output: detail dialog showed **"t7: projb task"**; picker listed
  **B-Todo / B-Doing** (projB's columns); after the move
  `liveboard2/…/t7_projb_task.md` had `boardcol: doing`, and projA's
  same-id decoy was **byte-identical** (md5 compared).
- Note: `p` targets `_find_own_agent_snapshot()` — the agent in the
  companion's own window — not the highlighted row. Verified both layouts.
- Verdict: **pass**

### Item 7 — wrapper failure is warned, not fatal
- Action A: `aitask_board_column.sh` moved aside → toast
  `ERROR:cannot run aitask_board_column.sh: …`.
- Action B: wrapper rigged to `exit 3` with garbage on stderr for `move` →
  toast `Move failed: boom: unexpected garbage on stderr`; the task file was
  not modified.
- Output: `grep -ci 'Traceback\|Exception'` over 2000 lines of scrollback =
  **0**; `p` reopened the modal after each failure.
- Verdict: **pass**

### Item 8 — new-column modal at 40 cols
- Action: picker → `＋ New column…`.
- Output: `New Board Column` with input and stacked `Create` / `Cancel`, all
  within the border.
- Verdict: **pass**

### Item 9 — empty / whitespace title refused
- Action: submitted empty, then four spaces.
- Output: both kept the modal open and raised `Title is required`; the
  project config's column list was unchanged.
- Verdict: **pass**

### Item 10 — emoji / non-ASCII title
- Action: created `🚀 Spät Lane` from minimonitor; also exercised the seam
  with `🚀 Ünder Wäy / Ready?`, `🚀🔥` and `Проверка`.
- Output: ids `spt_lane`, `nder_wy_ready`, `column`, `column_2` — all
  non-empty, unique and free of `|`/CR/LF (`generate_col_id` strips non-ASCII
  and falls back to `column`). The column rendered in `ait board` with the
  moved task inside it.
- Verdict: **pass**

### Item 11 — layered write stays clean
- Action: created a column from minimonitor with a populated
  `board_config.local.json` (`settings.collapsed_columns`, `auto_refresh`).
- Output: local file **byte-identical**; project file gained only
  `{"id": "spt_lane", …}` plus its `column_order` entry; top-level keys stayed
  exactly `["column_order", "columns"]` — no `settings` leak.
- Verdict: **pass**

### Item 12 — `e` opens the dialog and is in the footer
- Output: footer row 3 reads `X Collapse Col  e Columns  O Options`;
  `e` opened *Manage columns — shift+↑/↓ reorder, Enter edit, Esc close* with
  every column, its position, colour, id and task count, plus
  Add/Edit/Delete/Merge.
- Verdict: **pass**

### Item 13 — `e` hidden in derived views
- Output: present in All; **absent** from the In-Flight, By-Topic and
  By-Trail footers (as are `X`, `^→`, `^←`). Pressing `e` in By-Trail opened
  nothing — Textual treats `check_action() is False` as *disabled and not
  shown* (`screen.py:473-478`), so the gate hides *and* blocks dispatch.
- Verdict: **pass**

### Item 14 — reorder persists
- Action: `shift+Down` on `Now`; quit with `q`; relaunched.
- Output: `column_order` became `['next','now','backlog']` on the spot and the
  relaunched board rendered `Next | Now | Backlog`.
- Verdict: **pass**

### Item 15 — merge semantics
- Action: `merge_columns(['alpha','beta'], 'dest')`; reloaded from disk.
- Output: `dest` = 7000 (resident), **8024, 9048, 10072, 11096** — all below
  the resident, `alpha`'s pair before `beta`'s, each source's internal order
  preserved; both sources removed from `columns` **and** `column_order`.
- Verdict: **pass**

### Item 16 — collapsed-state migration
- Output: `collapsed_columns` `['alpha','dest']` → `['dest']`. Collapsed
  **source** cleared; collapsed **destination** retained.
- Verdict: **pass**

### Item 17 — `unordered` as merge source
- Output: `MergeResult(merged=('t2_u2.md','t3_u3.md'), failed=(),
  sources_removed=('unordered',), refused=())`; tasks landed at 1424/2448
  below the resident 400; `board_config.json` still valid and unchanged
  (the synthetic lane is not in `columns`/`column_order`).
- Verdict: **pass**

### Item 18 — add / edit / delete through the dialog — **FAIL**
- `Add` works (created `Zulu Lane` → `zulu_lane`, persisted).
- `Edit` works **only** via `Enter` on a focused row (renamed `Now`, id
  preserved).
- The **`Edit` and `Delete` buttons are dead**: `action_edit` / `action_delete`
  resolve their target with `_focused_item()` → `self.screen.focused`, but
  activating a Button *is* what focuses it, so the lookup always returns
  `None`. Live: `Select a column to delete` / `Select a column to edit`,
  nothing removed.
- **Delete has no other path in the dialog** (`BINDINGS` = escape/shift+up/
  shift+down; `ColumnManageItem.on_key` handles `enter` only), so deleting a
  column through the new dialog is impossible. It still works from Ctrl+P.
- Missed by `tests/test_board_column_dialog.py:741`, which focuses a row and
  calls `screen.action_delete()` directly, bypassing the button press.
- Follow-up: **t1454** (carries the full diagnosis and a fix direction).
- Verdict: **fail**

### Item 19 — palette parity
- Output: searching `olum` returned all **8** column commands including
  `Merge Columns`; `discover()` and `search()` both iterate the single
  `_COMMANDS` through `_resolved()` (`aitask_board.py:6600-6646`);
  `CommandPaletteParityTests` — 5 passed.
- Verdict: **pass**

### Item 20 — docs match shipped behaviour — **FAIL**
- `minimonitor/how-to.md` (lines 135, 140, 273) is **accurate** — checked
  clause by clause against the live runs above.
- `board/how-to.md` has three wrong statements, all authored by t1377_6
  (`e8e782300d`): the `Delete column` row (line 91) and the `(or **Edit**)`
  alternative (line 90) document the dead buttons from item 18, and line 85
  says the palette is **Ctrl+Backslash** when it is **Ctrl+P** (verified live:
  `C-\` did nothing, `C-p` opened it, footer reads `^p palette`).
- Also noted, pre-existing (`633f73bc13`): line 102 claims collapse state is
  saved in `board_config.json`; it is saved in `board_config.local.json`
  (verified — collapsing left the project file byte-identical).
- Follow-up: **t1455**.
- Verdict: **fail**

## Baseline test evidence (context, not a substitute)

- `tests/test_board_columns_seam.py`, `test_board_column_manage.py`,
  `test_board_column_dialog.py`, `test_board_columns_reconcile.py` —
  **174 passed**.
- `tests/test_board_column_cli.sh` — **102/102 passed**.

## Cleanup

Performed:

- All throwaway tmux servers killed and their stale sockets removed
  (`/tmp/tmux-1000/ait_av*` → 0 remaining).
- The rigged wrapper was restored inside the fixture; the **real**
  `.aitask-scripts/aitask_board_column.sh` was never modified.
- Scratch tree `${TMPDIR}/auto_verify_1377_7/` (fixture repos `repo`,
  `merge`, `merge2`, `liveboard`, `liveboard2` and driver scripts) removed.
- No file under this repo's `aitasks/` or `aiplans/` was touched other than
  the checklist itself, the two generated follow-ups, and this plan.

## Final Implementation Notes

- **Actual work done:** Verification only — no production code was changed.
  All 20 checklist items were driven to a terminal state (18 pass, 2 fail).
  Two follow-up bug tasks were created: **t1454** (dead Edit/Delete buttons in
  `ColumnManageScreen`) and **t1455** (stale board documentation).
- **Deviations from plan:** None; the autonomous strategy covered every item,
  so nothing fell through to the interactive loop and nothing was deferred.
- **Issues encountered:**
  - `ait minimonitor` auto-closes when it is the only pane in its window
    (`_check_auto_close`, t1446). Correct behaviour, but it means a live
    fixture must **split the companion into a window that already holds an
    agent pane** rather than giving it its own window.
  - Redirecting the TUI's stderr (`2>file`) makes the pane capture blank —
    Textual's driver writes the rendered frame there. Live tmux fixtures for
    these TUIs must leave both streams on the tty.
  - Session discovery requires `aitasks/metadata/project_config.yaml` in the
    fixture root; without it no session is "aitasks-like" and `target_root`
    silently falls back to the companion's own project.
  - The board's `p`-flow targets `_find_own_agent_snapshot()` — the agent in
    the companion's **own window** — not the highlighted row. The first
    multi-session attempt tested the wrong thing until this was pinned down.
- **Key decisions:**
  - Isolated the live TUI runs in a copied framework tree
    (`ait` + `.aitask-scripts` + synthetic `aitasks/`) rather than running
    against this repo, because items 14 and 18 mutate `board_config.json`.
    `ait` roots itself at its own directory, which makes that copy a complete
    project.
  - Gave both fixture projects a task with the **same id** so item 6 could
    distinguish "wrote to the right tree" from "wrote somewhere plausible".
  - Read focus from `capture-pane -pe` SGR attributes rather than inferring
    it from key counts — the tab order through the dialog is not what it
    looks like, and two early readings were wrong.
- **Upstream defects identified:**
  - `.aitask-scripts/board/aitask_board.py:6469,6475` — `action_edit` /
    `action_delete` resolve their target via `self.screen.focused`, which the
    button press itself overwrites, so the dialog's `Edit` and `Delete`
    buttons can never act; `Delete` has no other in-dialog path. Tracked as
    **t1454**.
  - `website/content/docs/tuis/board/how-to.md:102` — claims collapse state
    is saved in `board_config.json`; it is saved in
    `board_config.local.json`. Pre-existing (`633f73bc13`), outside t1377's
    scope; folded into **t1455** as a same-pass cleanup.
- **Notes for sibling tasks:** All t1377 siblings are archived, so this is the
  last of the group. The reusable finding for future board/minimonitor
  verification is the live-fixture recipe above (isolated framework copy,
  companion split beside an agent pane, no stderr redirect, SGR-based focus
  reading) — and the reminder that a test calling `screen.action_x()`
  directly proves nothing about the button wired to it.
