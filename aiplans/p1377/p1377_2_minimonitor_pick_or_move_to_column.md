---
Task: t1377_2_minimonitor_pick_or_move_to_column.md
Parent Task: aitasks/t1377_minimonitor_pick_column_action_and_board_column_management.md
Sibling Tasks: aitasks/t1377/t1377_3_*.md, aitasks/t1377/t1377_4_*.md, aitasks/t1377/t1377_5_*.md, aitasks/t1377/t1377_6_*.md, aitasks/t1377/t1377_7_*.md
Archived Sibling Plans: aiplans/archived/p1377/p1377_*_*.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-05 17:35
---

# p1377_2 — minimonitor: choose *pick* vs *move to column*

## Context

`ait minimonitor`'s `p` (pick-by-number) flow is a fixed 3-step chain:
`TaskNumberInputModal` → `TaskPickConfirmDialog` → `AgentCommandScreen`. This child
adds a **choice** at step 2: pick the task (today's path, unchanged) or move it to an
existing board column. Column *creation* is deliberately not here — that is t1377_3.

t1377_1 landed the headless seam it consumes (`lib/board_columns.py` +
`aitask_board_column.sh`, commit `6ce832a31`); this is its first consumer.

**Parent AC1 is the sharpest constraint: the pick path must be byte-for-byte
unchanged when chosen.**

## Verification pass (2026-08-05) — what this plan corrects

Re-verified against the current tree before implementation. Six material gaps found
and folded in below.

1. **Child task ids were unhandled.** `_PICK_TASK_ID_RE` (`minimonitor_app.py:95`) is
   `\d+(?:_\d+)?`, so `p` accepts `1377_2` — but the seam refuses child ids
   (`current-column --task 1377_2` → `ERROR:not_a_parent_task`, exit 1, verified
   live), because the board holds children in `child_task_datas`
   (`aitask_board.py:1116`) and never as column cards. **User decision: omit the
   "Move to column…" button entirely for a child id.**
2. **`sess` never reaches `_on_pick_confirmed`.** Its signature is
   `(result, target_id, target_root, pane_id)` (`:1461`), so the planned
   `self._task_cache.invalidate(target_id, sess)` had no `sess` in scope. The
   callback lambda at `:1434` must be widened.
3. **`_on_pick_confirmed` is a synchronous `push_screen` callback** but the seam call
   is async. It needs `self.run_worker(...)` (precedent: `:381`).
4. **`on_button_pressed` inverts on the OK id** — `if event.button.id !=
   "btn-pick-ok": self.dismiss(None)` (`:886`). A third button would silently cancel
   unless that becomes an explicit id branch.
5. **No colour-swatch helper exists anywhere in `monitor/`.** The precedent is the
   board's `ColumnSelectItem.render()` (`aitask_board.py:5748`),
   `  [{color}]██[/] {title} ({id})`. The colour is user config interpolated into
   Rich markup, so an unparseable value raises inside `render()`.
6. **Six existing tests encode the old `(True, kill)` tuple literally** and migrate
   with the contract (see Tests below).

Two plan-review rounds then raised four further gaps, all confirmed against the source
(and, where behavioural, against this checkout's interpreter) and addressed above:

7. **Escaping, not just colour validation.** Guarding only the colour left the row
   unsafe: titles and ids are interpolated into the same markup string, and the seam
   permits brackets in both. Verified in Rich — `Backlog [/]` **raises**, `a[b]c`
   silently renders `ac`. Every user-derived field is now escaped, at the row **and**
   at the modal's context line.
8. **The picker had no short-pane coverage.** The matrix asserted the confirm row at
   40×16 but the picker only "at 40 cols". The picker carries more vertical chrome
   (header + context + list + help + buttons ≈ 17 rows before any column is drawn), so
   it is the *more* likely to overflow. Now asserted at 40×20 and 40×16 too.
9. **The timeout test proved only caller handling.** It overrode
   `_run_board_column_cmd`, so an incomplete copy of the `_run_marks_cmd` body — kill
   without reap — would leak a child while every listed test passed. A direct helper
   test class now drives the real `create_subprocess_exec` and asserts `kill()` and an
   awaited `wait()` **separately**.
10. **A fatal import path (second round).** The colour guard was written as
   `from rich.errors import ColorParseError`; that name lives in **`rich.color`**, and
   `rich.errors` does not export it — verified in this checkout's interpreter. At
   `monitor_shared.py` module scope the `ImportError` would break `ait minimonitor`
   *and* `ait monitor` at startup, before any picker could run. Corrected to
   `from rich.color import Color, ColorParseError`. **Lesson for implementation:**
   resolve every third-party import against the real interpreter rather than from
   recall — the rest of this plan's Rich usage (`rich.markup.escape`,
   `rich.color.Color`) was checked the same way.

**User decision:** the picker lists `unordered` ("Unsorted / Inbox") and allows moving
to it. This is not optional polish — `current-column` reports `unordered` for any task
with no `boardcol` (verified: `--task 1377` → `CURRENT:1377|unordered`), so without it
the picker cannot mark the current column in the common case.

## Seam contract actually landed (t1377_1)

```
list-columns   --root R [--task-dir D] [--include-unordered]  → COLUMN:<id>|<colour>|<title>
current-column --root R [--task-dir D] --task N               → CURRENT:<task_id>|<col_id>
move           --root R [--task-dir D] --task N --column C    → MOVED:<filename>|<col>|<idx>
```
Refusals print `ERROR:<reason>` and exit 1; usage errors exit 2. Reason tokens are
stable: `unknown_column`, `malformed_task_id`, `not_a_parent_task`, `not_found`,
`ambiguous_task_id`, `unsafe_task_dir`, `unsupported_layout`, `vanished`. **Split
`COLUMN:` on the first two `|` only** (`split("|", 2)`) — the title is last precisely
because titles may contain a pipe. Colour may be empty.

## Steps

### Pre-phase (risk mitigations)

Gates the work below; must complete before the dismissal contract is touched.

1. `[sweep_dismissal_tuple_consumers]` Enumerate **every** consumer of
   `TaskPickConfirmDialog`'s dismissal value before changing its shape:
   `grep -rn 'TaskPickConfirmDialog\|_on_pick_confirmed' .aitask-scripts/ tests/`,
   plus every literal `(True, ` / `(True,` tuple fed to a pick-confirm callback in
   `tests/test_minimonitor_pick_by_number.py`. Record the resulting list in the Final
   Implementation Notes and check each site off after migration. The change is
   silent-by-construction — `True` and `"pick"` are both truthy, so a missed site
   binds `kill = None` and launches with the kill disabled rather than raising; the
   enumeration is what makes the migration provably complete rather than
   grep-and-hope.

### 1. `monitor_shared.py` — widen `TaskPickConfirmDialog`

It already dismisses a tuple, so this is an extension, not a rewrite:

| Result | Meaning |
|---|---|
| `("pick", kill_followed_agent)` | today's confirm path |
| `("column", None)` | new action |
| `None` | cancel |

- Add `_offers_column` derived from the id the dialog already holds:
  `"_" not in self._info.task_id`. This mirrors `NextSiblingDialog`'s existing
  `is_parent_with_children = "_" not in self._current_task_id` (`:1030`) — same
  parent/child test, same file, no new convention.
- In `compose()` (`:863`), inside `#pick-buttons`, between OK and Cancel:
  ```python
  if self._offers_column:
      yield Button("Move to column…", variant="default", id="btn-pick-column")
  ```
- Rewrite `on_button_pressed` (`:885`) to branch on the id explicitly — the current
  `!= "btn-pick-ok" → dismiss(None)` shortcut would swallow the new button:
  ```python
  def on_button_pressed(self, event: Button.Pressed) -> None:
      if event.button.id == "btn-pick-ok":
          kill = False
          if self._kill_target_label is not None:
              kill = self.query_one("#pick-kill", Checkbox).value
          self.dismiss(("pick", kill))
          return
      if event.button.id == "btn-pick-column":
          self.dismiss(("column", None))
          return
      self.dismiss(None)
  ```
- **`action_dismiss_dialog` keeps returning `None`** (`:894`). It is overridden
  precisely so the inherited `q`/Esc binding can never yield a truthy result.
- Update the class docstring's "Dismisses ``(True, kill_followed_agent)``" line.

**Narrow CSS.** `TaskPickConfirmDialog.narrow #pick-buttons` is already
`layout: vertical` with `Button { width: 1fr; height: 1; border: none; margin: 0 0 1 0 }`
(`:781-787`). Three buttons therefore cost 6 rows. `#pick-confirm-row { dock: bottom }`
(`:763`) is what makes the *body scroll* — not the buttons — give up space; that rule
must survive. Verify the fit at **40×16** (the existing `NarrowRenderTests` loop
already covers 40×50 / 40×20 / 40×16). If 40×16 overflows, tighten only the narrow
button margin to `margin: 0` — do not touch the dock rule.

### 2. `monitor_shared.py` — `ColumnPickerModal` + `_ColumnRow`

Model directly on `ChooseSiblingModal` (`:1123`) / `_SiblingRow` (`:1062`).

`_ColumnRow(Static)`:
- `can_focus = True`; `DEFAULT_CSS` with `height: 1; padding: 0 1` and
  `:focus { background: $accent 30%; }` — same as `_SiblingRow`.
- `__init__(self, col_id, title, color, current=False, **kwargs)`, exposing a
  `col_id` property.
- `render()` returns the swatch row, marking the task's **current** column. **Every
  user-derived field is escaped, and the colour is validated** — see "Markup safety"
  below; neither is optional hardening, both are correctness:
  ```python
  from rich.markup import escape

  mark = "●" if self._current else " "
  swatch = f"[{self._color}]██[/]" if self._color else "██"   # _color already validated
  return (f" {mark} {swatch} {escape(self._title)} "
          f"[dim]({escape(self._col_id)})[/]")
  ```

**Markup safety (load-bearing).** `Static.render()` returning a `str` is parsed as Rich
markup, and column titles/ids reach it straight from `board_config.json`. The seam does
**not** police brackets: `_line_safe` strips only CR/LF from the title, and
`ColumnIdError` rejects only `|`/CR/LF in an id. Verified against Rich:

| configured title | unescaped result |
|---|---|
| `Backlog [/]` | **raises `MarkupError`** — takes the modal down |
| `a[b]c` | silently renders `ac` — the title is corrupted, not just restyled |
| `Now [bold]` | silently renders `Now ` |

So:
- escape `title` and `col_id` with `rich.markup.escape` at **every** site they enter a
  markup string — the row above **and** the modal's context line in `compose()`;
- validate the colour at `__init__` (it is the one field interpolated as a *tag*, where
  escaping is not the right tool):
  ```python
  from rich.color import Color, ColorParseError

  def _safe_color(raw: str) -> str:
      if not raw:
          return ""
      try:
          Color.parse(raw)
      except ColorParseError:
          return ""
      return raw
  ```
  **Both names come from `rich.color`.** `ColorParseError` is **not** exported by
  `rich.errors` in this checkout — verified: `from rich.errors import ColorParseError`
  raises `ImportError`, and `rich.color.ColorParseError.__mro__` shows it derives
  straight from `Exception`, not from `rich.errors.ConsoleError`. Getting this wrong is
  not a local bug: the import sits at `monitor_shared.py` module scope, so it would
  break `ait minimonitor` **and** `ait monitor` at startup, before any picker exists.
  The invalid-colour test below pins the behaviour, and a wrong import fails the whole
  module's test collection rather than one case.

  Catch **only** `ColorParseError` — a broader except would hide real bugs, and the
  fallback (an unstyled swatch) is purely cosmetic so it cannot fail open into wrong
  behaviour.

`_SiblingRow.render()` (`monitor_shared.py:1088`) and the board's
`ColumnSelectItem.render()` (`aitask_board.py:5748`) interpolate their titles the same
unescaped way. **Do not fix them here** — record both in the Step 8 "Upstream defects
identified" bullet.
- `on_key` handling `enter` (dismiss the screen with `self._col_id`), `up`/`down` via
  `_focus_neighbor(±1)` — each with `event.prevent_default()` + `event.stop()`, and
  the same non-wrapping clamp `max(0, min(len(rows) - 1, idx + delta))` plus
  `.focus()` + `.scroll_visible()` only when the index actually changed.

`ColumnPickerModal(ModalScreen)`:
- `BINDINGS = [Binding("escape", "dismiss_dialog", "Close", show=False)]`.
- `__init__(self, task_id: str, columns: list[tuple[str, str, str]],
  current: str | None = None, narrow: bool = False)` — `columns` is
  `(col_id, colour, title)` in board order, `current` is the task's current column id.
  Positional-or-keyword `narrow`, matching `ChooseSiblingModal` / `NextSiblingDialog`.
- `compose()`: `if self._narrow: self.add_class("narrow")` as the **first statement**;
  then `#column-pick-dialog` containing header `Move to Column`, a context line
  (`Task: t<id>  ·  current: <escaped title>` — the current column's title is
  user-derived, so it is escaped here too), a
  `VerticalScroll(id="column-pick-list")` of rows, a help line
  `[↑/↓] navigate  [Enter/OK] select  [Esc] cancel` (escape the literal brackets as
  `\\[` exactly as `ChooseSiblingModal` does at `:1174`), and `#column-pick-buttons`
  with OK/Cancel.
- `on_mount()`: focus the row whose id equals `current`, else row 0.
- `on_button_pressed`: OK → focused `_ColumnRow`'s `col_id`, falling back to row 0,
  falling back to `None`; any other button → `None`. `action_dismiss_dialog` → `None`.
- `DEFAULT_CSS` ends with a commented narrow block. Start from `ChooseSiblingModal`'s
  single rule — `ColumnPickerModal.narrow #column-pick-dialog { width: 90%; min-width: 30; }`
  (two short buttons still fit horizontally) — but **the minimonitor pane is as short
  as the tmux window, not just narrow**. Header + context + list + help + buttons +
  padding + borders is ~17 rows before any column is drawn, so a 16-row pane
  overflows. Give the dialog `max-height: 80%` (as `ChooseSiblingModal` has) and, if
  the 40×16 assertion below fails, pull the same levers
  `TaskPickConfirmDialog.narrow` already pulls rather than inventing new ones:
  `#column-pick-list { min-height: 1 }`, and `Button { height: 1; border: none; }`.
  Verify with the composited-text tests — a region-fit check passes on an ellipsised
  label.

`narrow` is a **host-role flag, not a width test**
(`aidocs/framework/tui_conventions.md:163`) — do not route it through
`is_narrow_terminal`.

### 3. `minimonitor_app.py`

Module constants beside the existing `_PICK_TASK_ID_RE` (`:95`); `_SCRIPT_DIR` already
exists at `:23`:
```python
_BOARD_COLUMN_SH = _SCRIPT_DIR / "aitask_board_column.sh"
_BOARD_COLUMN_CMD_TIMEOUT = 20.0
```

**`_run_board_column_cmd(self, args: list[str]) -> tuple[int, str]`** — mirror
`AgentMarksMixin._run_marks_cmd` (`monitor_shared.py:275-319`) *exactly*: `proc = None`
pre-init, `asyncio.create_subprocess_exec` with `stderr=STDOUT`,
`asyncio.wait_for(proc.communicate(), timeout=_BOARD_COLUMN_CMD_TIMEOUT)`, on
`TimeoutError` `proc.kill()` + `await proc.wait()` inside a bare `except Exception:
pass` then return `(1, "ERROR:board column command timed out after …s")`, on `OSError`
return `(1, f"ERROR:cannot run {_BOARD_COLUMN_SH.name}: {exc}")`, else
`(proc.returncode or 0, out.decode("utf-8", "replace").strip())`. **Total by contract:
never raises, always terminates** — it runs off a keypress handler. This is the
injectable seam tests override.

**Widen the callback** at `:1434` to pass `sess` (gap 2):
```python
callback=lambda result: self._on_pick_confirmed(
    result, target_id, target_root, pane_id, sess
),
```

**`_on_pick_confirmed(self, result, target_id, target_root, pane_id, sess)`** —
branch on the action tag; the `"pick"` arm keeps today's body **verbatim**:
```python
if not result:
    return
action, payload = result
if action == "column":
    self.run_worker(
        self._open_column_picker(target_id, target_root, sess),
        exclusive=False, exit_on_error=False, group="board-column",
    )
    return
kill = payload
# ... today's body, unchanged ...
```

**`_open_column_picker(target_id, target_root, sess)`** (async):
1. `rc, out = await self._run_board_column_cmd(["list-columns", "--root", str(target_root), "--include-unordered"])`.
   Non-zero → `notify(f"Board columns unavailable: {first or f'exit {rc}'}", severity="warning")` and return.
   Parse `COLUMN:` lines with `line[len("COLUMN:"):].split("|", 2)`. No rows →
   warn and return.
2. `rc, out = await self._run_board_column_cmd(["current-column", "--root", str(target_root), "--task", target_id])`.
   Non-zero → warn naming the reason token and return. This is the defensive backstop
   for `not_a_parent_task` (the button is already omitted for child ids) and for
   `not_found` / `ambiguous_task_id`. Parse `CURRENT:<task_id>|<col_id>` with
   `rsplit("|", 1)`.
3. `self.push_screen(ColumnPickerModal(target_id, columns, current=current_col, narrow=True), callback=...)`.

   **Deliberately the callback form, not `push_screen_wait`.** Every modal hop in this
   app uses `push_screen(..., callback=...)`, and the existing test harness
   (`_mk_app`, which builds the app with `__new__` and stubs `push_screen`) can only
   drive that form. `push_screen_wait` would force every column test onto a real
   Textual `Pilot`.
4. Callback: `None` → return. Selected id == current → `notify(f"t{id} is already in {title}")`
   and return (no pointless write). Otherwise `run_worker(self._apply_column_move(...))`.

**`_apply_column_move(target_id, target_root, sess, col_id, title)`** (async):
`rc, out = await self._run_board_column_cmd(["move", "--root", str(target_root), "--task", target_id, "--column", col_id])`.
On `rc == 0` and a leading `MOVED:` → `self._task_cache.invalidate(target_id, sess)`
then `self.notify(f"Moved t{target_id} → {title}")`. Otherwise
`self.notify(f"Move failed: {first or f'exit {rc}'}", severity="warning")` and write
nothing. `TaskInfoCache`'s `(st_mtime_ns, st_size)` identity gate would reject the
stale entry anyway, but every explicit gesture in this flow invalidates first and the
sub-second same-size edge is real.

**Use `target_root`, never `self._project_root`** — `_root_for_snap` (`:593`) may
resolve a different project in multi-session mode. Leave `--task-dir` alone: a foreign
project's layout is not discoverable from here.

### Post-phase (risk mitigations)

1. `[prove_column_row_markup_guards]` The escaping and colour validation land in step 2
   as correctness. This phase proves each guard **discriminates**, so neither can be
   silently dropped later. One mutation per test — revert one guard at a time:

   - **escape guard.** A column titled `Backlog [/]` and one titled `a[b]c` both
     render with their titles intact (assert on composited screen text, not on the
     `render()` return — Rich swallows markup on the way to the terminal). Negative
     control: patch `_ColumnRow.render` to the unescaped form and assert the first
     case **raises `MarkupError`** and the second **loses the `[b]`** — two distinct
     failure modes, so one control cannot mask the other.
   - **colour guard.** A column whose colour is `notacolor` renders with an unstyled
     swatch and its title intact. Negative control: bypass `_safe_color` and assert
     compositing raises.
   - The context line carries the same escaping: a *current* column titled
     `Backlog [/]` renders the picker without raising.

   Each negative control must fail for the intended reason — assert on the exception
   type / the specific corrupted text, never on "some assertion failed".

## Tests — `tests/test_minimonitor_pick_by_number.py`

**Migrate the existing tuple literals** (gap 6): `ConfirmAndLaunchTests` (`:462`,
`:469`, `:472`, `:485`, `:492`), `SharedLaunchImplementationTests.drive_p` (`:560`),
and `ConfirmDialogDismissalTests`' OK assertion — `(True, X)` → `("pick", X)`.

`_mk_app` (`:130`) additionally stubs `run_worker` to drive the coroutine to
completion (`asyncio.run(coro)`) and record it, so the column path stays on the
no-Textual Style A harness.

| Case | Assertion |
|---|---|
| **AC1 anchor** | `SharedLaunchImplementationTests.test_n_and_p_build_the_same_launch_dialog` still passes with `("pick", False)` — extend that existing argument-for-argument comparison, do not write a looser one |
| `"column"` selected | `app.spy_launch == []` — no agent launched — and the seam is called with `list-columns` |
| **child id** | a confirm dialog for `1377_2` has **no** `#btn-pick-column`; the parent `1310` control **does** (the discriminating negative control) |
| defensive refusal | a `current-column` result of `ERROR:not_a_parent_task` surfaces a warning naming the token and pushes no picker |
| cross-project | the seam is invoked with `--root <target_root>` when the followed pane belongs to another session |
| `ERROR:` result | warning surfaced, `_task_cache.invalidated` unchanged |
| timeout (caller) | the overridden seam returns the timeout tuple → warning, nothing written |
| already-in-column | selecting the current column notifies and issues **no** `move` call |
| title with `\|` | a `COLUMN:c1\|red\|a\|b` line parses to title `a\|b` (splits on the first two only) |
| title with `[` | a `COLUMN:c1\|red\|Backlog [/]` line reaches the picker and the row renders with the title intact (the guard from the post-phase, driven end-to-end from the seam's own output rather than from a hand-built row) |
| narrow render — confirm row | the now-3-button row at 40×50 / 40×20 / **40×16** via the existing `_assert_controls_inside` (`:659`, which checks **both** axes) |
| narrow render — picker | `ColumnPickerModal` at 40×50, **40×20 and 40×16**, same two-axis `_assert_controls_inside` on composited screen text (`_screen_text` / `_flat`, `:584`/`:590`). The short sizes are the ones that matter: the picker has more vertical chrome than the confirm row (header + context + list + help + buttons), and a 40-column-only test would pass while the help line and buttons sit off-screen |
| narrow negative control | both dialogs re-run with `_drop_narrow_rules` (`:637`) applied to their `DEFAULT_CSS`, asserting `_assert_controls_inside` **raises** — the same construct the file already uses at `:807`, one dialog per test |

**Direct `_run_board_column_cmd` tests (new class).** The caller-side timeout row above
overrides the seam, so it proves only that the caller handles an error tuple — an
incomplete copy of the `_run_marks_cmd` body (killing without reaping, or omitting the
kill) would leave a child behind while every row above still passes. Drive the real
helper by patching `asyncio.create_subprocess_exec`, following the precedent in
`tests/test_shadow_seam.py:211-231`:

| Case | Assertion |
|---|---|
| timeout kills **and** reaps | fake proc whose `communicate()` awaits forever; patch `_BOARD_COLUMN_CMD_TIMEOUT` to ~0.01. Assert the return is `(1, "ERROR:…timed out…")`, that `kill()` was called, **and** that `wait()` was actually awaited — recorded separately, because asserting only `kill()` cannot tell a reaping implementation from a zombie-leaking one |
| `OSError` on spawn | `create_subprocess_exec` raising `OSError` returns `(1, "ERROR:cannot run aitask_board_column.sh: …")` and does not propagate |
| success passthrough | returncode 0 + stdout returns `(0, "<stripped text>")`, and the argv passed to `create_subprocess_exec` starts with `_BOARD_COLUMN_SH` followed by the caller's args verbatim |
| never raises | each of the three cases asserted via a plain `asyncio.run(...)` with no `try` — a propagating exception fails the test, which is the "total by contract" claim |

## Verification

```bash
python3 tests/test_minimonitor_pick_by_number.py
bash tests/run_all_python_tests.sh    # read ONLY the last line for the verdict
```

Plus a **read-only** live check (no live move — this checkout is worked on
concurrently): `./.aitask-scripts/aitask_board_column.sh list-columns --root . --include-unordered`
must reproduce the eight rows (7 configured + `unordered`). Finish with
`git status --porcelain` to confirm the verification run left nothing behind.

Step 9 (Post-Implementation) covers cleanup, archival and merge.

## Coordination

Depends on t1377_1's seam, committed in `6ce832a31`. Touches only `monitor/`, which no
other in-flight task is editing (last `monitor/` commits: `e2db6e3f6`, `95d2ba36f`,
`102aa6c44`). Live acceptance in a real ~40-column tmux pane is covered by the
aggregate manual-verification sibling t1377_7.

## Risk

### Code-health risk: medium

- `TaskPickConfirmDialog`'s dismissal contract changes shape — the first tuple element
  goes from `True` to `"pick"`. **Both are truthy**, so a consumer left on the old
  unpacking (`_ok, kill = result`) does not fail loudly: it would bind `kill = None`
  from `("column", None)` and launch an agent with the kill silently disabled. Six
  test call sites and one production consumer encode the old literal ·
  severity: medium (residual — the inline pre-phase enumerates every consumer so a
  missed site is caught before migration, but the contract change itself still ships) ·
  → mitigation: inline pre-phase sweep_dismissal_tuple_consumers
- The narrow confirm row grows to three stacked buttons (6 rows) in a docked
  `#pick-confirm-row` competing with the body scroll in a pane as short as 16 rows; a
  fit regression renders controls off-screen, which no region-fit check catches —
  only the composited-text assertion does · severity: medium · → mitigation: none
  (the 40×16 case is already a required row in the test table above)
- `_ColumnRow.render()` and the picker's context line interpolate **user-configured
  column titles, ids and colours** into Rich markup. Verified: a title of `Backlog [/]`
  raises `MarkupError` and takes the modal down in a pane the user cannot easily
  recover, and `a[b]c` renders as `ac` — silent title corruption, which is the worse
  half because nothing signals it. The seam does not police brackets in either field ·
  severity: medium (residual — step 2 escapes every user-derived field and validates
  the colour, and the inline post-phase proves each guard discriminates; the
  interpolation pattern itself remains, and two sibling renderers in the repo still
  carry the unguarded form) · → mitigation: inline post-phase prove_column_row_markup_guards
- This is the first file-mutating gesture in the `monitor/` package, and its async
  runner fires off a keypress handler; a partial copy of the `_run_marks_cmd` body
  (kill without reap) leaks a child process while every caller-level test still passes ·
  severity: low · → mitigation: none (the direct helper tests drive the real
  `create_subprocess_exec` and assert kill **and** awaited reap separately)

### Goal-achievement risk: low

- `ColumnPickerModal`'s constructor signature and dismissal contract are extended by
  t1377_3 with a "New column…" row; if the shape is wrong t1377_3 must reopen it.
  Reduced this pass by giving the constructor an explicit `(col_id, colour, title)`
  row tuple and a `current` marker rather than a bare id list · severity: low ·
  → mitigation: none

### Planned mitigations

- timing: pre-phase | name: sweep_dismissal_tuple_consumers | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the dismissal tuple's first element changes from True to "pick" and both are truthy, so a missed consumer fails silently | desc: Enumerate every production and test consumer of TaskPickConfirmDialog's dismissal value before changing its shape, record the list, and check each site off after migration.
- timing: post-phase | name: prove_column_row_markup_guards | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — user-configured column titles/ids/colours reach Rich markup, where `[/]` raises MarkupError and `[b]` silently corrupts the title | desc: Prove each markup guard discriminates — bracket-title and invalid-colour cases render intact, each with a one-mutation negative control asserting the specific failure (MarkupError / lost text) that the guard prevents.

**Post-inline reassessment (one pass).** With both mitigations inlined, code-health
stays **medium**: the consumer enumeration and the markup guards reduce the chance of
an *undetected* regression, but the dismissal-contract change, the three-button narrow
row and the markup-interpolation pattern all still ship, and the blast radius across
`monitor_shared.py` / `minimonitor_app.py` / the pick test module is unchanged.
Goal-achievement stays **low**. Neither inline phase introduces a new risk — the
pre-phase is read-only, and the post-phase adds only tests.
