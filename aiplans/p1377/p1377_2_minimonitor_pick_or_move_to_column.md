---
Task: t1377_2_minimonitor_pick_or_move_to_column.md
Parent Task: aitasks/t1377_minimonitor_pick_column_action_and_board_column_management.md
Sibling Tasks: aitasks/t1377/t1377_1_*.md, aitasks/t1377/t1377_3_*.md, aitasks/t1377/t1377_4_*.md, aitasks/t1377/t1377_5_*.md, aitasks/t1377/t1377_6_*.md
Archived Sibling Plans: aiplans/archived/p1377/p1377_*_*.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# p1377_2 — minimonitor: choose *pick* vs *move to column*

## Goal

At step 2 of the `p` pick-by-number flow, let the user choose between picking the
task (today's path) and moving it to an existing board column. Creating a column is
**not** here — that is t1377_3.

**Parent AC1 is the sharpest constraint: the pick path must be byte-for-byte
unchanged when chosen.**

## Steps

### 1. `monitor_shared.py` — widen `TaskPickConfirmDialog`

It already dismisses a tuple, so this is an extension:

| Result | Meaning |
|---|---|
| `("pick", kill_followed_agent)` | today's confirm path |
| `("column", None)` | new action |
| `None` | cancel |

Add `Button("Move to column…", id="btn-pick-column")` inside `#pick-buttons`.

Two things that must survive untouched:

- **`action_dismiss_dialog` keeps returning `None`.** It is overridden precisely so
  the inherited `q` / Esc binding can never yield a truthy result.
- **The `#pick-confirm-row { dock: bottom }` rule.** It is what makes the *body
  scroll* — not the buttons — give up space on a short pane; without it the buttons
  render off-screen entirely at ~20 rows. Re-verify it holds now that the row
  carries three buttons plus a checkbox.

`.narrow` CSS: `#pick-buttons` already stacks vertically; confirm three stacked
borderless `height: 1` buttons still fit alongside `#pick-kill`.

### 2. `monitor_shared.py` — `ColumnPickerModal` + `_ColumnRow`

Model directly on `ChooseSiblingModal` / `_SiblingRow`:

- `_ColumnRow(Static)`, `can_focus = True`, `:focus { background: $accent 30%; }`.
- `on_key` handling `enter` (dismiss with the id), `up` / `down` (`_focus_neighbor`
  with index clamping + `scroll_visible()`), each with `prevent_default()` +
  `stop()`.
- `render()` shows the colour swatch, title and id; the task's **current** column is
  marked.
- Modal: header, context line, `VerticalScroll` list, a help line
  (`[↑/↓] navigate  [Enter/OK] select  [Esc] cancel`), OK/Cancel.
- `on_mount` focuses the first row. Dismisses `col_id: str` or `None`.

**`.narrow` variant is mandatory** — every modal in this package has one.
Implement it the same three ways as every sibling:

1. `narrow: bool = False` ctor kwarg → `self._narrow`;
2. `if self._narrow: self.add_class("narrow")` as the **first statement** of
   `compose()`;
3. a commented `ColumnPickerModal.narrow #id { ... }` block at the bottom of the
   class's own `DEFAULT_CSS`.

`narrow` is a **host-role flag, not a width test**
(`aidocs/framework/tui_conventions.md`) — do not route it through
`is_narrow_terminal`.

### 3. `minimonitor_app.py`

- `_on_pick_confirmed` branches on the action tag. The `"pick"` arm keeps today's
  body verbatim; `"column"` fetches the list and pushes the picker.
- **`_run_board_column_cmd(args)`** — mirror `AgentMarksMixin._run_marks_cmd`
  exactly: `asyncio.create_subprocess_exec`, `asyncio.wait_for` with a hard timeout,
  kill-then-**reap** on timeout (so no zombie), `OSError` → `(1, "ERROR:…")`.
  **Total by contract: never raises, always terminates** — it runs off a keypress
  handler. Tests override this method; that is the injectable seam.
- **Use `target_root`, never `self._project_root`**, for both the list and the move.
  `_root_for_snap` may resolve a different project in multi-session mode.
- On success: `self._task_cache.invalidate(target_id, sess)` then
  `notify(f"Moved t{id} → {title}")`. The `(st_mtime_ns, st_size)` identity gate
  would reject the stale entry anyway, but every explicit gesture in this flow
  invalidates first and the sub-second same-size edge is real.
- On `ERROR:` / timeout: `notify(..., severity="warning")` and write nothing.

## Tests — extend `tests/test_minimonitor_pick_by_number.py`

| Case | Assertion |
|---|---|
| **AC1 anchor** | the `"pick"` arm builds the **same** `AgentCommandScreen` args as today — extend the existing `SharedLaunchImplementationTests` comparison, do not write a looser one |
| `"column"` selected | **no** agent launched |
| cross-project | the seam is invoked with `target_root` when the followed pane belongs to another session |
| `ERROR:` result | warning surfaced, nothing written |
| timeout | warning surfaced, child killed and reaped |
| narrow render | 3-button confirm row **and** the new picker at 40 cols, asserted on **composited screen text** (a region-fit check passes on an ellipsised label), each with the `.narrow`-removal negative control the file already uses |

## Verification

```bash
python3 tests/test_minimonitor_pick_by_number.py
bash tests/run_all_python_tests.sh    # read ONLY the last line
```

## Coordination

Depends on t1377_1's committed seam. Touches only `monitor/`, which no other
in-flight task is editing. Live acceptance in a real ~40-column tmux pane is covered
by the aggregate manual-verification sibling.

## Notes for sibling tasks

*(fill in at Step 8 — especially the exact `ColumnPickerModal` constructor signature
and dismissal contract, which t1377_3 extends with a "New column…" row.)*
