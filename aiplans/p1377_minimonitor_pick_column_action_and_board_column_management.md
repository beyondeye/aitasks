---
Task: t1377_minimonitor_pick_column_action_and_board_column_management.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# t1377 — minimonitor pick/column action + board column management

## Context

Two related deliverables that share one missing foundation.

**Deliverable 1.** `ait minimonitor`'s `p` (pick-by-number) flow is a fixed
3-step chain — `TaskNumberInputModal` → `TaskPickConfirmDialog` → `AgentCommandScreen`
(`minimonitor_app.py:1137-1258`, `:1079-1135`). The user wants a *choice* at step 2:
pick the task (today's path) **or** move it to a board column.

**The blocker is real and verified.** `grep -rn boardcol .aitask-scripts/monitor/`
returns zero hits. The only mutation the whole `monitor/` package performs is an
`asyncio` subprocess to `aitask_agent_marks.sh` (`monitor_shared.py:275-320`);
everything else is read-only. Neither existing option works:

- `ait update --batch N --boardcol C` (`aitask_update.sh:350`) **never computes
  `boardidx`** and **never validates the column id** — the task keeps its old
  index and can land anywhere in the destination, or tie at 0. It is also
  cwd-relative, and minimonitor resolves a per-pane `target_root`
  (`_root_for_snap`, `minimonitor_app.py:527-535`) that may be a *different project*.
- `TaskManager` is a tested headless API, but `aitask_board.py` imports Textual at
  module scope (`:53-62`) and `TASKS_DIR`/`METADATA_FILE` are module-level and
  cwd-relative (`:66-67`).

**Deliverable 2.** `ait board` already has add / edit / delete / reorder / collapse,
but **no key is bound to add, edit or delete** — they are command-palette-only
(`KanbanCommandProvider:5577`). And **merge does not exist**. The gap is
discoverability plus merge, not raw capability.

Outcome: one Textual-free, root-scoped board-column seam under `lib/`; a
minimonitor action choice built on it; and a single discoverable column-management
dialog in the board that adds merge.

## Decisions taken (user-confirmed at planning)

| Question | Decision |
|---|---|
| Headless seam shape | New `lib/board_columns.py` + thin `aitask_board_column.sh` wrapper; minimonitor calls it via subprocess, mirroring `_run_marks_cmd` |
| Merge arity | **N→1** multi-select (`SelectionList`, `WorkReportColumnSelectScreen:4278` precedent) |
| Create-new-column from minimonitor | **In scope**, as its own child sequenced after move-to-existing |
| Deliverable 2 vs t1243 Workstream C (`boardgroup`) | **Land before it**, with a documented migration + a reverse note into `t1243_10` |

## Decomposition — 7 children, serial

```
1 (seam) ─┬─ 2 (minimonitor action) ── 3 (create column) ─┐
          └─ 4 (merge engine) ──────── 5 (board dialog) ──┴─ 6 (docs) ── 7 (manual verify)
```

`depends` is declared strictly serial (`1→2→3→4→5→6→7`) so a fresh context always
has one unambiguous next child, matching the t1243 convention.

---

### t1377_1 — headless board-column seam  ·  `feature` / high / medium

**New `.aitask-scripts/lib/board_columns.py` — Textual-free, root-scoped.**
Every entry point takes an explicit `root: Path`; nothing reads `task_dir()` /
`metadata_dir()` ambiently, because minimonitor's `target_root` can be another
project. `tests/test_no_lib_to_tui_import.sh` already freezes the `lib/` → TUI
direction, so this module may import `config_utils`, `task_yaml`,
`board_ordering`, `atomic_write` — never `aitask_board`.

```python
DEFAULT_COLUMNS, DEFAULT_ORDER          # hoisted here (see de-dup below)
UNORDERED_ID = "unordered"; UNORDERED_TITLE = "Unsorted / Inbox"

class ColumnIdError(ValueError): ...     # '|', CR or LF in a configured id

def board_config_path(root)             -> Path
def load_columns(root)                  -> (ordered_ids, {id: title})
def column_indices(root, col_id, exclude="") -> list[int]
def move_task_to_column(root, task_id, col_id) -> MoveOutcome
```

`MoveOutcome` is a frozen dataclass `(moved: str|None, col_id, board_idx,
refused: tuple[tuple[str,str],...])` — a rich return naming *which* item failed and
*why* (`unknown_column`, `not_found`, `not_a_parent_task`), never a bare bool.

`move_task_to_column` must:
1. Validate `col_id` against `load_columns(root)` (plus the synthetic `unordered`) —
   this is the gap `aitask_update.sh --boardcol` leaves open.
2. Resolve `<root>/aitasks/t<id>_*.md`; **refuse child ids** (`t<p>_<c>`), matching
   `TaskManager._resolve_parents` and the board's "children cannot be moved" rule.
3. `board_idx = board_ordering.index_for_append(column_indices(root, col_id))` —
   reuse the pure module, do **not** re-implement the arithmetic.
4. `parse_frontmatter` → set `boardcol`/`boardidx` → `serialize_frontmatter` →
   `atomic_write.atomic_write_text`.
5. Write **only** `boardcol` + `boardidx`. Both are in `BOARD_LAYOUT_KEYS`
   (`task_yaml.py:55`), so this is a *layout* write: **it must not bump
   `updated_at`**, and its merge conflicts resolve silently local-wins. Coerce any
   read index through `normalize_board_idx` — never re-implement int parsing.
6. Never invent a key, never recreate a file that has vanished.

**Atomicity boundary — state it, don't overclaim.** `atomic_write_text` gives
reader-visible atomicity, *not* writer serialization: two concurrent
read-modify-writes can each render from the same old text and the second replace
discards the first. The board's own `reload_and_save_board_fields` is equally
unserialized (its docstring says so), so this **matches** the existing seam rather
than regressing it. Document the RMW boundary in the module docstring; do not
claim a lock this seam does not take.

**De-duplicate, don't fork** (`planning_conventions.md`, "Refactor duplicates
before adding to them"). `DEFAULT_COLUMNS`/`DEFAULT_ORDER` exist twice today
(`aitask_board.py:142-147`, `work_report_gather.py:55-60`) and the column reader
exists once (`work_report_gather.load_columns`, `:221`). Move both here and:
- have `work_report_gather.load_columns()` delegate, keeping its own `_die(...,
  EXIT_INFRA)` wrapper — the CLI's fail-closed protocol behaviour is unchanged, but
  the library path raises `ColumnIdError` instead of calling `sys.exit`, which is
  what makes it safe to import into a TUI;
- have `aitask_board.py` import the constants back (precedent: it already
  re-imports `topic_semantics` at `:436` and `board_ordering` at `:445`).

**New `.aitask-scripts/aitask_board_column.sh`** — thin CLI over the module:
```
aitask_board_column.sh list-columns --root R      # COLUMN:<id>|<title>
aitask_board_column.sh move --root R --task N --column C
                                                  # MOVED:<task>|<col>|<idx>
                                                  # or ERROR:<reason>
```
Per `aitasks_extension_points.md`: **no `ait` dispatcher entry** (the dispatcher is
user-facing only; this exists to be shelled out from a TUI) and **no code-agent
allowlist entries** (the whitelist applies only to skill-invoked helpers).
Follow `shell_conventions.md` — `#!/usr/bin/env bash`, `set -euo pipefail`.

**Consume t1379's writers, don't reinvent them.** `t1379_atomic_task_file_writes`
is `Implementing` **in this checkout right now**: `Task.save` already routes through
`atomic_write_text` in the working tree, and a new **`lib/atomic_write.sh`** is
present (untracked) for shell writers. `aitask_board_column.sh` must source that
helper rather than open-code a `$TMPDIR`+`mv` dance, and the `aitask_update.sh`
`--boardcol` validation lands on top of whatever t1379 leaves that file. Re-read
both before implementing; if t1379 has not committed yet, coordinate rather than
write over it.

**Also in this child:** add column-id validation to `aitask_update.sh --boardcol`
(parse site `:350`). Today an unknown id yields a task that
renders in no column at all. Validate after `parse_args`, exactly as `--anchor`
already does (`normalize_anchor_id`, `:2213`), and fail with a clear message.

**Tests** — `tests/test_board_columns_seam.py`, mirroring
`tests/test_board_manager_moves.py` (which patches module constants rather than
booting Textual) and using `tests/lib/board_fixture.py`:
- happy path: single move appends past the destination max; K sequential moves get
  distinct ascending indices;
- refusal cases (unknown column, child id, missing task) each assert a
  **byte-identical tree snapshot** (`bf.snapshot` / `bf.diff_snapshots`) — nothing
  written;
- `updated_at` is **unchanged** by a move, with a negative control that names a
  non-layout key and *does* stamp it (proves the assertion discriminates);
- a **headless guard** mirroring `SeamGuardTests`
  (`test_board_manager_moves.py:529`): `board_columns.py` source contains no
  `import textual` / `from textual` / `import aitask_board`;
- a drift guard that `work_report_gather.load_columns()` and
  `board_columns.load_columns(root)` agree on the same tree (the de-dup is real,
  not two implementations that happen to match today);
- `tests/test_board_column_cli.sh` for the wrapper: both subcommands, the
  `ERROR:` line, and a non-zero exit on a bad column.
- `aitask_update.sh --boardcol` rejection test.

`tests/test_board_persistence_seam.py`'s AST-parsed `EXPECTED_CALL_SITES` table is
**not** touched: this child adds no `reload_and_save_board_fields` call site and
moves none out of the board.

---

### t1377_2 — minimonitor: choose *pick* vs *move to column*  ·  `feature` / high / medium

**`monitor_shared.py`**
- `TaskPickConfirmDialog` (`:714-870`) widens its dismissal from `(True, kill)` to a
  tagged tuple: `("pick", kill)` / `("column", None)` / `None`. The class already
  dismisses a tuple, and `NextSiblingDialog` (`:963-1033`) is the exact three-button
  precedent (`("pick", id)` / `("choose", parent)` / `None`).
- Add `Button("Move to column…", id="btn-pick-column")` inside `#pick-buttons`.
  `action_dismiss_dialog` must keep returning `None` — the override at `:868-870`
  exists precisely so `q`/Esc can never yield a truthy result.
- **Narrow CSS**: `#pick-buttons` already stacks vertically under `.narrow`, but the
  row now holds three buttons plus a checkbox in a ~40-col × short pane. The
  `#pick-confirm-row { dock: bottom }` rule (`:737-742`) is what keeps the body
  scroll — not the buttons — giving up space; verify it still holds at 3 buttons.
- **New `ColumnPickerModal` + `_ColumnRow`**, modelled on `ChooseSiblingModal` /
  `_SiblingRow` (`:1036-1175`): focusable rows, ↑/↓/Enter, OK/Cancel, a help line,
  `VerticalScroll` list, and a `.narrow` variant. Rows render `██ title (id)` with
  the column colour, and mark the task's *current* column.
- Every new minimonitor modal ships a `.narrow` variant — a hard convention here,
  implemented the same three ways as every sibling: `narrow: bool = False` ctor
  kwarg → `add_class("narrow")` as the first statement of `compose()` → a
  `ClassName.narrow #id` block at the bottom of that class's `DEFAULT_CSS`.
  (`narrow` is a **host-role flag**, not a width test — `tui_conventions.md`.)

**`minimonitor_app.py`**
- `_on_pick_confirmed` (`:1239-1258`) routes on the action tag. The `"pick"` branch
  is byte-for-byte today's body (AC1); `"column"` opens the picker.
- New `_run_board_column_cmd(args)` mirroring `AgentMarksMixin._run_marks_cmd`
  (`monitor_shared.py:275-320`): `asyncio.create_subprocess_exec`, a hard timeout,
  kill-then-reap on timeout, `OSError` → `(1, "ERROR:…")`. **Total by contract —
  never raises, always terminates**; the caller treats the result as data and
  `notify()`s. This is the injectable seam the tests override.
- Column list and the move are both fetched for **`target_root`**, not
  `self._project_root` — cross-project correctness.
- After a successful move: `self._task_cache.invalidate(target_id, sess)` then
  `notify(f"Moved t{id} → {title}")`. Strictly, `TaskInfoCache`'s
  `(st_mtime_ns, st_size)` identity gate would reject the stale entry anyway, but
  every explicit gesture in this flow invalidates first (`:1001`, `:1179`, `:1196`)
  and the sub-second same-size edge is real.

**Tests** — extend `tests/test_minimonitor_pick_by_number.py`:
- action routing: `"pick"` builds the **same** `AgentCommandScreen` args as today
  (the existing `SharedLaunchImplementationTests:521` comparison is the anchor for
  AC1); `"column"` launches **no** agent;
- the seam is called with `target_root` when the followed pane belongs to another
  session — a cross-project negative control;
- `ERROR:` / timeout from the seam surfaces a warning and writes nothing;
- narrow render at 40 cols for the 3-button confirm row and the new picker,
  asserted on **composited screen text** (a region-fit check passes on an ellipsised
  label), each with the `.narrow`-removal negative control the file already uses.

---

### t1377_3 — minimonitor: create a new column  ·  `feature` / medium / medium

Column creation exists **only** inside the board TUI, so this needs a headless
config-writer before any UI.

- Extend `lib/board_columns.py`: `generate_col_id(title, existing_ids)` (lift
  `ColumnEditScreen._generate_col_id`, `aitask_board.py:5361` — it already strips
  non-ASCII and maps `[^a-z0-9]+`→`_`, so it can never emit `|`/CR/LF),
  `PALETTE_COLORS` (from `:5297`), and `create_column(root, title, color=None)`
  writing through `config_utils.load_layered_config` → `split_config` →
  `save_project_config` with the **project/user key split**.

  **The write must not flatten the layers.** `load_layered_config` returns the
  *merged* dict — project ← `.local` — so writing that merged dict back through
  `save_project_config` would leak the user-level `settings` block into the tracked
  `board_config.json`, and a careless mirror of `save_metadata()` (`:1051`, which
  writes *both* layers) would clobber `board_config.local.json`. `create_column`
  touches `columns` + `column_order` only: run `split_config(merged,
  project_keys=_PROJECT_KEYS, user_keys=_USER_KEYS)` and write **only** the project
  layer, leaving the local file untouched on disk.
- `_PROJECT_KEYS`/`_USER_KEYS` are currently triplicated (`aitask_board.py:68-69`,
  `settings_app.py:103-104`, `stats_config.py:34`). Define them once here and have
  all three import — derive, don't duplicate.
- The board re-imports `generate_col_id` / `PALETTE_COLORS` back (same precedent as
  `board_ordering`). Add the first tests for `_generate_col_id`, which has none.
- `aitask_board_column.sh` gains `create --root R --title T [--color C]`.
- minimonitor: a `＋ New column…` row at the tail of `ColumnPickerModal` → a title
  input modal (`TaskNumberInputModal` is the shape to copy) → create → move. All
  with `.narrow` variants. Empty/whitespace title is **rejected in place** with a
  warning and the modal stays open — mirroring `ColumnEditScreen.save`'s
  "Title is required" notify-and-return (`:5404`), never a silent dismiss.

**Tests** — beyond id generation:
- **Layered round-trip fixture**: seed a tree whose `board_config.json` carries an
  extra unrelated project key and whose `board_config.local.json` carries a
  populated `settings` block (e.g. `collapsed_columns`, `auto_refresh_minutes`).
  After `create_column`, assert (a) the new column is in the project layer, (b) the
  unrelated project key survives verbatim, (c) `settings` did **not** appear in the
  project file, and (d) `board_config.local.json` is **byte-identical** to before.
  A happy-path creation test alone passes even when the split is wrong.
- **Narrow render of the title modal** at 40 columns, asserted on composited screen
  text with the `.narrow`-removal negative control the minimonitor suite already
  uses — plus the empty-title path: submitting blank keeps the modal mounted, emits
  the warning, and creates nothing.
- **`ait settings` stance:** `settings_app.py:2375` labels columns
  "read-only — edit via board TUI". A headless writer now exists, so record the
  decision explicitly in this child's Final Implementation Notes. Flipping the
  settings TUI to editable is **out of scope** (the user scoped this child to
  minimonitor); if it should change, file a standalone follow-up rather than
  widening here.
- Note the project/user split matters: `columns`/`column_order` are project-level
  (tracked). `tui_conventions.md` forbids a runtime TUI *auto-committing* project
  config — write only; never `git commit` / `ait git push` from an event handler.

---

### t1377_4 — column merge engine + rename migration  ·  `feature` / high / medium

Headless-first so the engine is testable before any dialog exists.

- **`TaskManager.merge_columns(source_ids, dest_id)`** in `aitask_board.py`,
  returning a `MoveResult`-shaped report. All-or-nothing: resolve and validate every
  id first (unknown id, `dest in sources`, empty sources) and write nothing on
  refusal — the invariant `MoveResult` already documents (`:987`).

  **Pass filenames, not `Task` objects.** `get_column_tasks(col_id)` (`:1211`)
  returns `list[Task]`, but `move_tasks_to_column` (`:1562`) routes through
  `_resolve_parents` (`:1539`), which does `self.task_datas.get(name)` against a
  `dict[str, Task]` keyed by **filename** (`:1010`). Handing it `Task` objects makes
  every lookup return `None`, so the whole batch is `refused` as
  `not_a_parent_task` and **nothing is written** — a silent no-op merge, not a
  crash. The call is therefore:

  ```python
  names = [t.filename for t in self.get_column_tasks(src)]
  result = self.move_tasks_to_column(names, dest_id)
  ```

  Note the asymmetry that makes this easy to get wrong: `update_column`'s rename
  path (`:1686`) iterates `get_column_tasks()` and assigns `task.board_col`
  **directly**, never touching `_resolve_parents` — so the `Task`-object shape is
  correct *there* and wrong *here*.

  Then drop each source from `columns` and `column_order`, prune its
  `settings.collapsed_columns` entry, and `save_metadata()`. Sources are processed
  in `column_order` order so the destination's resulting sequence is deterministic.
  - This is the `boardidx` collision answer: members of A get **fresh appended**
    indices in B via `index_for_append`, never their old ones, and relative order
    within each source is preserved.
  - **Never call `respace_column` from this path** — appending past the destination
    maximum is unbounded and cannot exhaust an interval. `test_board_movement.py`
    ships a `respace_after_move` negative control that fails if a movement path
    respaces.

- **`unordered` semantics — define them explicitly.** `unordered` is a *synthetic*
  column: it is absent from both `columns` and `column_order` (verified against the
  live `board_config.json`), exists only as a rendered lane for tasks with no
  `boardcol`, and is hand-injected wherever a picker needs it (see
  `action_collapse_column`). Decision:
  - **As destination: allowed.** `move_tasks_to_column(names, "unordered")` is
    exactly what `delete_column` (`:1727`) already does.
  - **As source: allowed, with the config-removal step skipped.** "Empty the inbox
    into Backlog" is a meaningful merge, and there is no `columns` /
    `column_order` entry to remove — the removal must be conditional, not assumed.
    A blind `column_order.remove("unordered")` would raise `ValueError`.
  - `dest_id == source_id` is refused, as is a source list containing duplicates.
  - The source multi-select in t1377_5 lists `unordered` only when it holds tasks,
    matching how the board surfaces it elsewhere.

- **Fix `update_column`'s rename path** (`:1686`, rename branch `:1694-1702`): it
  migrates `column_order` and every member's `boardcol`, but **not**
  `settings.collapsed_columns` — a rename orphans the collapsed entry. The path is
  currently dead in the UI (`_handle_column_edit_result` passes `col_id` twice); the
  dialog in t1377_5 makes it live, so fix it here.
- `EXPECTED_CALL_SITES` in `test_board_persistence_seam.py` is an AST-parsed frozen
  table. `merge_columns` composes `move_tasks_to_column` and adds **no** new
  `reload_and_save_board_fields` call site — assert that; if the implementation
  drifts to a direct call, the table must be edited in the same commit.

- **Partial-merge contract — the merge is NOT transactional, and must say so.**
  `MoveResult`'s all-or-nothing guarantee covers *input resolution* only: it
  resolves every name before the first write, so a bad id writes nothing. It says
  nothing about I/O. `merge_columns` writes one task file per member and calls
  `save_metadata()` at the end, so an `OSError`, a full disk, or a `SIGINT` between
  writes leaves a **partially merged** state. Per-file writes are atomic
  (`Task.save` → `atomic_write_text`), so no file is ever corrupt — but the
  multi-file operation is not. Match the framework's existing non-transactional
  model rather than inventing a journal, and make the partial state safe,
  self-describing and recoverable:

  1. **Ordering is the safety property.** Task writes first, config removal
     **last**. A failure then leaves the source column still present holding its
     unmoved members — never tasks pointing at a column that no longer exists.
     Removing the config first would orphan them into a lane that renders nowhere.
  2. **Do not remove a source whose move did not fully succeed.** Per-source, catch
     `OSError` from the write loop, record it, and skip that source's config
     removal. Other sources that completed cleanly are still removed.
  3. **Report it in a distinct field — do not overload `refused`.** `MoveResult`'s
     docstring guarantees *"`refused` non-empty always means NOTHING was written"*;
     stuffing write failures in there makes that invariant a lie for every existing
     consumer. Return a separate `MergeResult`:

     ```python
     @dataclass(frozen=True)
     class MergeResult:
         merged: tuple[str, ...] = ()          # filenames actually moved
         failed: tuple[tuple[str, str], ...] = ()   # (filename, reason)
         sources_removed: tuple[str, ...] = ()
         refused: tuple[tuple[str, str], ...] = ()  # input validation, nothing written
         @property
         def complete(self) -> bool: return not (self.failed or self.refused)
     ```
  4. **Recovery is re-running the merge, and that is convergent.** A member already
     moved is no longer in the source column, so a second run moves only the
     remainder and then removes the now-empty source. Document this idempotence in
     the method docstring as the retry contract — it is what makes "leave it
     partial" an acceptable answer.
  5. **The UI must never imply success on a partial merge.** t1377_5's callback
     branches on `result.complete`: complete → `notify("Merged N tasks into
     <dest>")`; partial → `severity="warning"` naming the counts and the retry,
     e.g. `"Merged 7 of 9 into Backlog — 2 failed, re-run to finish"`. A bare
     "Merged" toast on a partial merge is the specific failure this clause exists
     to prevent.

**Tests** — `tests/test_board_column_manage.py`, patching `B.TASKS_DIR` /
`B.METADATA_FILE` (no Pilot), per `test_board_manager_moves.py`:
- **The real merge call path, asserted on on-disk effect.** The primary test drives
  `merge_columns` end-to-end and asserts the destination's member set and the
  **re-read** `boardcol` values actually changed — not just the returned object.
  `MoveResult.ok` is `not refused`, so it does surface the `Task`-object bug *if*
  the inner result is propagated; the failure mode to guard is a `merge_columns`
  that **swallows** the per-source `MoveResult` and returns its own success. So
  test both halves: the composed method must propagate inner `refused` upward
  (feed it one bad source and assert the refusal reaches the caller), and the happy
  path must show `len(get_column_tasks(dest))` grown by the expected count with the
  sources emptied on disk.
- N→1 merge: every member's `boardcol` is the destination, indices are distinct and
  ascending, relative order within each source is preserved, sources are gone from
  **both** `columns` and `column_order`;
- `unordered` as source (config-removal skipped, no `ValueError`, tasks move) and as
  destination (tasks land there, nothing removed from config);
- collapsed-state: a collapsed source's entry is removed; a collapsed *destination*
  stays collapsed;
- refusal cases (unknown id, `dest in sources`, empty sources) each assert a
  byte-identical tree snapshot;
- **partial-merge recovery**, by injecting an `OSError` on the Nth
  `reload_and_save_board_fields` (the `_apply_mutation` patch style
  `test_board_movement.py` already uses): assert (a) members 1..N-1 are moved on
  disk and the rest are not, (b) the failing source is **still present** in both
  `columns` and `column_order`, (c) `result.complete` is `False` and `result.failed`
  names the file, (d) a **second run with the injection removed completes the
  merge** and only then removes the source — the convergence claim, tested rather
  than asserted in prose;
- a partial merge does **not** report success through the dialog: assert the
  warning-severity notification path is taken (t1377_5 test);
- rename migrates the collapsed entry, **with a negative control** that reverts only
  the migration line and shows the test failing (a passing negative control means
  the test discriminates nothing);
- `FLIP_TABLE` in `test_board_movement.py` must stay green **unedited**.

---

### t1377_5 — board ad-hoc column-management dialog  ·  `feature` / high / medium

**Step 1 — de-duplicate first (non-optional).** `KanbanCommandProvider` duplicates
its seven-command list verbatim between `discover()` (`:5580`) and `search()`
(`:5618`). Adding a command to one and not the other silently breaks discovery
or search. Collapse both onto a single `_COMMANDS` tuple of
`(display, action_attr, help)` **before** adding anything, plus a guard test
asserting the two methods expose the same command set.

This is t1243_7 §1's mandate. t1243_7 is `Ready` behind `t1243_4→5→6`, so it has not
landed and this child does it. **Drop a reverse note into
`aitasks/t1243/t1243_7_move_to_column_command.md` under `## Notes for sibling
tasks`** saying the de-dup landed in t1377_5 and t1243_7 should consume `_COMMANDS`
rather than redo it.

**Step 2 — one dialog behind one key.** `ColumnManageScreen`, bound to **`e`**
(verified free in `KanbanApp.BINDINGS:5891`; `m` is reserved by t1243_7, `G` by
t1243_12). Footer-visible with a short label, gated in `check_action` to the
kanban views (hidden in In-Flight / By-Topic / By-Trail, which render derived lanes,
not columns) — mirroring how `w` is column-scoped.

Contents, reusing what exists (AC7 — **no second picker inside the board**):
- the column list in `column_order`, with ↑/↓ to reorder (rewrites `column_order`
  wholesale + `save_metadata()`, generalising the one-step `_shift_column:8890`);
- **Add** / **Edit** → `ColumnEditScreen` (`:5345`) via `_handle_column_edit_result`;
- **Delete** → `DeleteColumnConfirmScreen` (`:5428`);
- **Merge** → a `SelectionList` multi-select of sources (the
  `WorkReportColumnSelectScreen:4278` shape) → `ColumnSelectScreen` (`:5552`) for
  the destination → `merge_columns`, with a confirm naming the task count.
- Keep the palette entries working (they now route through `_COMMANDS`), and add
  "Manage Columns" / "Merge Columns" there too.
- Style with the existing `#column_edit_dialog` / `.picker-dialog` ids
  (`KanbanApp.CSS:5653`); `.picker-dialog` already carries the t1366 scroll/focus
  fix. The new modal lives inside an already-manifested module, so
  `register_all_known_bindings()` picks up its scope automatically — no
  `KNOWN_BINDING_SOURCES` edit.

**Workstream C migration (documented, per the user's decision).** `boardgroup` does
not exist yet — `BOARD_KEYS == BOARD_LAYOUT_KEYS == ("boardcol","boardidx")` today.
When t1243_10 lands, `settings.collapsed_groups` holds composite `"<col>/<slug>"`
keys whose column half must be rewritten on rename and re-pointed on delete/merge,
and t1243_10 already owns that five-owner lifecycle. Record the migration in the
plan **and drop a reverse note into
`aitasks/t1243/t1243_10_group_collapse_and_filtering.md`** naming
`merge_columns` and the fixed `update_column` as two additional owners of the
collapsed-key lifecycle. Do not pre-build group handling here.

**Merge-conflict surface.** `t1243_4` is `Implementing` right now in
`aitask_board.py` (`apply_filter`, `refresh_git_status`) — a different region from
column management, but this child edits `BINDINGS`, `CSS` and
`KanbanCommandProvider`. Re-read `aitask_board.py` immediately before implementing
and rebase onto t1243_4 if it has landed.

**Tests**: `_COMMANDS` parity guard; dialog reorder persists `column_order`; merge
flow end-to-end through the real `KanbanApp` on the fixture harness; footer
visibility per view (`check_action`), including a view where `e` must be hidden.

---

### t1377_6 — documentation  ·  `documentation` / medium / low

Docs are a first-class child, not a verification afterthought
(`planning_conventions.md`). Current-state prose only — no version history.
- `website/content/docs/tuis/board/how-to.md` — "How to Customize Columns" table
  (`:33-42`) gains the `e` dialog row and **Merge**; the notes block (`:46-49`)
  gains merge index/collapse semantics.
- `website/content/docs/tuis/board/reference.md` — Column Operations table
  (`:64-73`), the dialogs table (`:368-370`), and the `boardcol`/`boardidx`
  descriptions (`:331-339`).
- `website/content/docs/tuis/minimonitor/how-to.md` — "How to Pick a Task by Number"
  (`:117-127`) gains the pick-vs-move choice and create-column; Key Bindings Quick
  Reference (`:250`) updated.
- Genericise any example project names; never reference `aidocs/framework/` internals
  from user-facing docs.

---

### t1377_7 — aggregate manual verification  ·  `manual_verification` / medium / low

Live checklist over t1377_2/3/5: the `p` action choice in a real ~40-column
minimonitor pane, a cross-project move, the board dialog's reorder/delete/merge,
footer visibility, and `.narrow` rendering. Seeded from each child plan's
`## Verification` section, prefixed `[t1377_N]`.

---

## ⚠ Shared checkout is actively changing — re-verify anchors before implementing

Observed **during this planning session**, not hypothetically:

- `main` advanced three commits mid-session (`6c487b8be` → `c235928b7`).
- `.aitask-scripts/board/aitask_board.py` carries **200 uncommitted insertions /
  37 deletions** in this working tree — t1243_4 (`Implementing`) is being written
  right now, along with `tests/lib/board_fixture.py`, `tests/test_board_movement.py`
  and a new `tests/test_board_render_scoping.py`.
- `.aitask-scripts/aitask_update.sh` is **also uncommitted-dirty** — and t1377_1
  plans to edit it.

Consequences that are part of this plan, not caveats to it:

1. **Every `aitask_board.py:NNNN` anchor below was re-derived after that drift and
   will drift again.** Anchors in this plan are navigational, not contractual —
   each child must `grep` for the named symbol (`def merge_columns`,
   `_resolve_parents`, `KanbanCommandProvider`, …) rather than trusting a number.
2. **Do not stash or revert in this checkout.** Another session's in-flight edits
   live here; `git stash`, `git checkout --`, and `git revert` of a swept-in commit
   would destroy them. Stage explicit paths only, and check `git diff --cached`
   before every commit — never `git add -A`.
3. **t1377_1's `aitask_update.sh` edit and t1377_5's `aitask_board.py` edits are
   direct collision surfaces** with in-flight work. Both children must re-read the
   file at implementation time and, if the conflicting work is still uncommitted,
   coordinate rather than write over it.

## Cross-cutting constraints

- **Contracts that must not break**: `reload_and_save_board_fields(fields)` — name
  exactly what you mutated; `BOARD_LAYOUT_KEYS` writes are silent-local-wins and do
  not stamp `updated_at`; `normalize_board_idx` is the only coercion point;
  `respace_column` is the exhaustion remedy only; a `column_order` entry with no
  `columns` entry is silently dropped by both the renderer and `load_columns()`;
  column ids containing `|`/CR/LF are fatal in the work-report protocol.
- **Negative `boardidx` values are normal** (every "move to top" produces one).
  Nothing may assume positivity, contiguity, or a spacing of 10.
- **Concurrency**: `aitasks/`/`aiplans/` live on the `aitask-data` branch — use
  `./ait git` for them and plain `git` for code, never mixed in one `git add`.
  Another session may hold a staged index; stage explicit paths.
- **t1369** (`move_tasks_to_column` is O(K×(N+K))) is `Ready` and unlanded. t1377_4's
  merge is the first large-K consumer. K is bounded by one column's task count, so
  this is not a correctness issue — but note it in t1377_4 and re-check against
  t1369's result if it lands first.

## Verification

```bash
shellcheck .aitask-scripts/aitask_board_column.sh .aitask-scripts/aitask_update.sh
bash tests/run_all_python_tests.sh          # read ONLY the last line for the verdict
bash tests/test_board_column_cli.sh
bash tests/test_no_lib_to_tui_import.sh
bash tests/test_no_raw_tmux.sh
```
Per-child, the narrower loop is `bash tests/run_all_python_tests.sh --test-dir tests`
plus the specific module. `FLIP_TABLE` (`test_board_movement.py`) and
`EXPECTED_CALL_SITES` (`test_board_persistence_seam.py`) must stay green **unedited**
by children 1–3; child 4 may only edit them consciously.

Live acceptance (child 7): run `ait board` and `ait minimonitor` in a real tmux pane
— a screenshot/capture is the only proof of a visibility claim.

## Risk

### Code-health risk: medium
- Three surfaces gain a board-column reader/writer where one exists today; if the
  de-dup in t1377_1 is skipped, `lib/board_columns.py` and
  `work_report_gather.load_columns` become two implementations that agree only by
  luck · severity: medium · → mitigation: the delegation + drift guard are named
  deliverables of t1377_1, not follow-ups.
- `aitask_board.py` is edited by t1377_5 while `t1243_4` is `Implementing` and
  `t1243_5` will later rewrite movement actions to async — merge-conflict and
  rework surface · severity: medium · → mitigation: t1377_5 keeps the new UI
  strictly above the render layer and re-reads the file before implementing.
- Two frozen test tables (`FLIP_TABLE`, `EXPECTED_CALL_SITES`) can be silently
  satisfied by a wrong-shaped change · severity: medium · → mitigation: children
  1–4 each assert the tables are untouched, and t1377_4's rename test ships a
  negative control.
- The new writer is atomic but not serialized; a concurrent `ait board` move can
  still lose it · severity: low · → mitigation: documented explicitly as matching
  (not regressing) `reload_and_save_board_fields`; task-file write *locking*
  remains unowned by any task — atomicity is not serialization.
- A merge writes many files without a transaction, so an I/O error leaves it
  partial · severity: medium · → mitigation: the partial-merge contract in t1377_4
  (config-removal last, per-source failure isolation, a distinct `failed` field, a
  tested convergent retry, and a warning-severity UI path).
- **This checkout is shared with an in-flight session**: `main` moved three commits
  and `aitask_board.py` / `aitask_update.sh` carry uncommitted work *during
  planning*. A careless `git stash` / `git add -A` would destroy another session's
  edits, and every line anchor here is perishable · severity: medium ·
  → mitigation: the "Shared checkout is actively changing" section above is a
  standing instruction for every child, not a note.
- `merge_columns` composes an API whose resolution shape (`filename` strings, not
  `Task` objects) is the opposite of the neighbouring `update_column` rename path,
  and a composed method that swallows the inner `MoveResult` reports success while
  writing nothing · severity: medium · → mitigation: both the call shape and the
  propagation test are named deliverables of t1377_4.

### Goal-achievement risk: medium
- Deliverable 2 lands before the `boardgroup` model, so a later Workstream C child
  must extend merge/delete for composite collapse keys · severity: medium ·
  → mitigation: user-confirmed sequencing; migration recorded plus a reverse note
  into `t1243_10`.
- Creating columns headlessly softens the deliberate "columns are board-TUI-only"
  stance that `ait settings` advertises · severity: medium · → mitigation:
  `settings_columns_editable`
- `p`'s pick path must be byte-for-byte unchanged (AC1) while its dialog's
  dismissal shape changes · severity: low · → mitigation: the existing
  `SharedLaunchImplementationTests` equality anchors it.

### Planned mitigations
- timing: after | name: settings_columns_editable | type: enhancement | priority: medium | effort: medium | addresses: goal-achievement — `ait settings` advertises a columns-are-read-only stance the framework no longer holds once t1377_3 lands a headless `board_config.json` writer | desc: Flip the settings TUI's Columns section (`settings_app.py:2375`) from read-only to editable on top of `lib/board_columns.create_column`, so board, minimonitor and settings agree on one stance.

**Creation timing — this parent decomposes, so Step 8d never runs here.** The
`after` mitigation above must be created during the post-approval decomposition
step, alongside the children, as an **independent follow-up task** (not a child —
it targets a different TUI and is not bounded by this parent's goal). It carries
`depends: [1377_3]`, and its id is back-filled into the `→ mitigation:` bullet and
into `risk_mitigation_tasks` at creation.

### How the remaining mitigations are discharged

Every other `→ mitigation` above is a **named deliverable or guard test inside a
child**, not a separate task — putting each in child scope is what makes it real
rather than deferred.

Two adjacent risks are already owned by existing tasks, so no new task is warranted:
`t1379_atomic_task_file_writes` (the **atomicity** sweep — `Implementing` now, and a
dependency of t1377_1's shell helper) and
`t1369_board_batch_move_linear_index_arithmetic` (large-K `move_tasks_to_column`).
t1377_1 and t1377_4 name them respectively. Task-file write *serialization* (a
lock) is owned by neither and stays out of scope here — this plan matches the
framework's current non-transactional model rather than pre-building one.

## Post-implementation

Each child follows task-workflow Step 9: merge to `main`, `ait gates run <id>`
(`risk_evaluated` is the enforced active gate), then `aitask_archive.sh`. This
parent archives automatically once every child completes.
