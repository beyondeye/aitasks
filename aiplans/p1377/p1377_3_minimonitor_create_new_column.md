---
Task: t1377_3_minimonitor_create_new_column.md
Parent Task: aitasks/t1377_minimonitor_pick_column_action_and_board_column_management.md
Sibling Tasks: aitasks/t1377/t1377_4_column_merge_engine.md, aitasks/t1377/t1377_5_board_column_management_dialog.md, aitasks/t1377/t1377_6_column_features_documentation.md, aitasks/t1377/t1377_7_manual_verification_column_features.md
Archived Sibling Plans: aiplans/archived/p1377/p1377_1_headless_board_column_seam.md, aiplans/archived/p1377/p1377_2_minimonitor_pick_or_move_to_column.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-05 23:43
---

# p1377_3 — minimonitor: create a new board column

## Context

t1377_2 landed "move a task to an **existing** board column" from minimonitor.
This child adds **create a new column**, satisfying parent **AC3** (the user chose
to build it rather than take the documented-deferral escape hatch).

It is sequenced last of the three for a reason: column creation exists **only**
inside the board TUI today, so it needs a headless `board_config.json` **writer**
before any UI — and that writer is the first write to a *tracked project config*
from outside `ait board`.

Two seams already exist and are consumed, not rebuilt: `lib/board_columns.py` +
`aitask_board_column.sh` (t1377_1, commit `6ce832a31`) and `ColumnPickerModal` /
`_ColumnRow` in `monitor/monitor_shared.py` (t1377_2, commit `f3dbf175b`).

## Verification pass (2026-08-05) — what this plan corrects

Re-verified against the current tree before implementation. Seven material
findings, all confirmed against source and folded in below.

1. **The key sets are duplicated TWICE, not three times — and the third "copy"
   is a name collision.** `stats/stats_config.py:34` defines
   `_USER_KEYS = ("active", "days", "week_start", "custom")` — the *stats* TUI's
   own user-layer keys, a tuple, nothing to do with board columns. Importing the
   board key sets there would be actively wrong. The real duplication is
   `board/aitask_board.py:70-71` and `settings/settings_app.py:103-104`
   (`_BOARD_PROJECT_KEYS` / `_BOARD_USER_KEYS`). `tests/test_board_config_split.py:31-32`
   keeps its own literal **deliberately** — independent ground truth, the same
   call t1377_1 made. So step 2 has **two** edit sites, not three.
2. **`ColumnPickerModal` dismisses from THREE places, not one.** As landed:
   `_ColumnRow.on_key` (`monitor_shared.py:1312`, `self.screen.dismiss(self._col_id)`),
   `ColumnPickerModal.on_button_pressed` (`:1444-1456`, focused row → first row →
   `None`), and `action_dismiss_dialog` (`:1458`). Any change to the dismissal
   shape must land at all three, plus the single production consumer
   (`minimonitor_app._on_column_chosen`, reached through the lambda at `:1598`)
   and the test sites. This is exactly t1377_2's pre-phase lesson, and it is why
   the sweep below is a gate, not a formality.
3. **The board NEVER reloads `board_config.json` after startup.**
   `TaskManager.load_metadata()` has exactly one call site — `__init__`
   (`aitask_board.py:1046`); `refresh_board` / `action_refresh_board` reload
   *tasks*, not metadata. So a column created from minimonitor while `ait board`
   is open is invisible there **and is silently dropped** the next time the board
   calls `save_metadata()` (any add/edit/delete/collapse writes the stale
   in-memory `self.columns` over the file). This is a genuine lost update, new
   with *this* child — t1377_2's move writes a task file, which the board does
   reload. **Closed in this task** by pre-phase 2, which gates the UI step — see
   the risk section.
4. **t1433 landed `lib/record_protocol.py`.** `board_columns.py` already imports
   `has_record_breaking` / `sanitize_last_field` / `sanitize_middle_field` from
   it and no longer carries private `_line_safe` / `_field_safe` copies. Assert
   the slug's `|`/CR/LF-freedom with `has_record_breaking`, not a hand-rolled
   regex — same predicate the report protocol actually enforces.
5. **`load_layered_config` returns the merged dict *including the local layer*.**
   Beyond the two failure modes the previous draft named, there is a third,
   subtler one: if a user's `board_config.local.json` overrides `columns`, the
   merged value is the *local* one and writing the project layer **promotes a
   user-local override into the tracked file**. `TaskManager.save_metadata`
   (`:1066-1075`) has the identical behaviour, so this is board parity, not a
   regression — **document it in the docstring, do not "fix" it here.**
6. **Colour policy decided this pass (user).** A minimonitor-created column takes
   the **first `PALETTE_COLORS` entry not already used** by an existing column,
   falling back to `PALETTE_COLORS[len(existing) % 8]` when all eight are taken.
   No colour UI in the 40-column pane — one title prompt and done. Rejected:
   always-red (board's preselected `PALETTE_COLORS[0]`), and a swatch row in the
   modal (a second control in a dialog that must fit 40×16).
7. **Two narrow-CSS gotchas inherited from t1377_2, both load-bearing.**
   Textual's `Button` defaults to `min-width: 16`, so a narrow variant needs
   `min-width: 0` or two buttons overflow a 32-cell content box; and a CSS
   comment must **never contain the lowercase word "narrow"** — the test helper
   `_drop_narrow_rules` (`tests/test_minimonitor_pick_by_number.py:669`) skips
   any line containing it and then eats lines to the next `}`, silently deleting
   the following real rule and erroring the negative control on malformed CSS.

Two smaller confirmations: `config_utils._prepare_atomic` does
`path.parent.mkdir(parents=True, exist_ok=True)` (`:181`), so a missing
`metadata/` directory is not a special case; and `settings_app.py` already puts
`.aitask-scripts/lib` on `sys.path` (`:20`), so it can import `board_columns`
without new wiring.

## Steps

### Pre-phase (risk mitigations)

Gates the work below; must complete before the dismissal contract is touched.

1. `[sweep_column_picker_dismissal_consumers]` Enumerate **every** consumer of
   `ColumnPickerModal`'s dismissal value before changing its shape:
   `grep -rn 'ColumnPickerModal\|_ColumnRow\|_on_column_chosen' .aitask-scripts/ tests/`,
   plus every assertion in `tests/test_minimonitor_pick_by_number.py` that reads
   `_PickerHost.results` or feeds a value into the picker's `push_screen`
   callback. The list must name all **three** in-modal dismissal sites
   (`_ColumnRow.on_key`, `ColumnPickerModal.on_button_pressed`,
   `action_dismiss_dialog`), the single production consumer and its lambda, and
   each test site. Record the resulting list in the Final Implementation Notes
   and check each site off after migration. The change is
   silent-by-construction — `("existing", "now")` is truthy, so a missed site
   falls through `if not col_id` and then looks a tuple up in `titles`,
   notifying a stringified tuple rather than raising. **Exclude look-alikes
   deliberately and say so**: t1377_2's equivalent sweep found one
   (`_FakeMonitor.kill_agent_pane_smart`'s unrelated tuple) that a blind
   find-and-replace would have corrupted. The enumeration is what makes the
   migration provably complete rather than grep-and-hope.

2. `[reconcile_external_columns_at_save]` **Close the stale-board overwrite
   before minimonitor ever exposes `＋ New column…`.** Today
   `TaskManager.load_metadata()` runs once (`aitask_board.py:1046`) and the board
   writes its startup-era `self.columns` on every `save_metadata()`, so a column
   created by the new headless writer while a board is open is silently
   destroyed. Shipping the UI without this would mean shipping a feature whose
   result a running board deletes.

   **Hard performance constraint — this must not slow `ait board` down.** The
   reload goes **only** at the top of `TaskManager.save_metadata()`. It must
   never be reachable from `refresh_board`, `action_refresh_board`, the
   auto-refresh timer, `compose`/`render`, or any per-frame or per-poll path. No
   polling loop, no watcher, no render-path I/O. This is affordable precisely
   because `save_metadata()` has **10 call sites and every one is a discrete user
   gesture** — column add/edit/delete/collapse (`:1704`, `:1723`, `:1742`,
   `:1761`), sort-mode change (`:7186`), type-filter dismissal (`:7215`,
   `:7223`), settings dismissal (`:9698`), the by-trail write (`:9542`), and the
   first-run write in `load_metadata` (`:1064`).

   **Reconciliation behaviour.** Read **only** the current project
   `board_config.json` immediately before the board writes — never
   `board_config.local.json`, and never through `load_layered_config` (which
   would merge the local layer back in and defeat the project/local split step 1
   establishes). Add a raw project-layer reader to `lib/board_columns.py`:

   ```python
   def project_columns_at(config_path) -> tuple[list[dict], list[str]]
   ```

   It `json.load`s the project file alone, returns `(columns, column_order)` as
   raw dicts for verbatim merging, and returns `([], [])` for a missing or
   unparseable file — catching `OSError` / `json.JSONDecodeError` **narrowly**.
   Failing that way loses only the merge (the pre-existing behaviour), never the
   board's own save, which is the safe direction inside a write path.

   **Track what this board instance already knew.** `load_metadata` seeds
   `self._known_col_ids = {c["id"] for c in self.columns}`, and `save_metadata`
   refreshes it from the columns it just wrote. That set is what distinguishes an
   **external addition** from a **board-side deletion**, so an intentional delete
   is never resurrected. Per on-disk column id:

   | on disk | in `_known_col_ids` | in `self.columns` | action |
   |---|---|---|---|
   | X | yes | yes | board's in-memory version wins (board-side edit/reorder) |
   | X | yes | no | **board deleted it — do not resurrect** |
   | X | no | no | **genuine external addition — merge** |
   | X | no | yes | **id collision — warn, do not silently choose** |

   **Merge only truly external additions.** Keep the board's in-memory
   definitions and order for every known column; append the external ones in
   their **on-disk order** (order taken from `column_order`, with any column
   missing from it appended after), and extend `self.column_order` to match. The
   board never reorders or rewrites its own entries as a side effect of merging.

   **Collision policy (the fourth row).** Two independent creations can slug to
   the same id (both "Spikes" → `spikes`). If the definitions are byte-equal,
   merge silently — there is nothing to choose. If they differ, **do not silently
   pick**: keep this board's version (the user is actively editing here, so
   dropping it would destroy live work), and emit a **visible** warning naming
   the id and both titles, telling the user to reconcile manually. The louder
   alternative — aborting the whole save — was considered and rejected: it would
   discard the user's board-side edit and re-fire on every subsequent save with
   no way forward.

   Warnings reach the user through **one** wiring point: `TaskManager` gains a
   keyword-only `on_warning=None` callback, passed as `TaskManager(on_warning=self.notify)`
   at the app's single construction site (`aitask_board.py:6198`); all ~20 test
   constructions keep working unchanged. Warnings are **also** appended to
   `self.reconcile_warnings`, which is the assertion surface for the tests below.

   **Verify before moving on** — this phase is not done until every item is green:

   - the five reconciliation tests and the AST call-site scan listed under
     *Tests → reconciliation* below;
   - the benchmark under *Verification* recording the measured per-save cost,
     held **under 1 ms**. If the merge cannot meet that budget, **stop and
     confirm with the user** rather than shipping a slower board.

### 1. Extend `lib/board_columns.py` (the headless writer)

Additive only — every existing symbol keeps its contract.

```python
PALETTE_COLORS: list[tuple[str, str]]              # (hex, label), 8 entries
PROJECT_KEYS = {"columns", "column_order"}         # public: settings_app imports
USER_KEYS = {"settings"}

def generate_col_id(title: str, existing_ids) -> str
def next_palette_color(existing_colors) -> str
def create_column(root, title, color=None, *, task_dir=DEFAULT_TASK_DIR) -> CreateOutcome
def project_columns_at(config_path) -> tuple[list[dict], list[str]]   # pre-phase 2
```

`generate_col_id` is lifted **verbatim** from `ColumnEditScreen._generate_col_id`
(`aitask_board.py:5568-5585`): strip non-ASCII → `.strip().lower()` →
`[^a-z0-9]+` → `_` → `strip('_')` → `[:20]` → fallback `"column"` → uniquify
`_2`, `_3`, …. Preserve its quirks, including that the `_2` suffix is appended
**after** the 20-char truncation (so a collided id may exceed 20).

**That transform is load-bearing beyond cosmetics:** because it maps everything
outside `[a-z0-9]` to `_`, it can never emit `|`, CR or LF — the exact characters
`record_protocol.has_record_breaking` treats as fatal for a `COLUMN:` record.
Preserve the property and assert it directly.

`next_palette_color(existing_colors)` returns the first `PALETTE_COLORS` hex not
present in `existing_colors`, else `PALETTE_COLORS[len(existing_colors) % 8][0]`.
Pure, total, deterministic — unit-testable without touching disk.

`CreateOutcome` is a frozen dataclass `(col_id, title, color, refused)` with an
`ok` property, mirroring `MoveOutcome` — a rich return naming which item failed
and why, never a bare bool. Reasons: the existing `unsafe_task_dir` /
`unsupported_layout`, plus **`empty_title`** (blank or whitespace-only) and
**`invalid_column_id`** (defensive: a configured id already in the file breaks
the record protocol; `column_records_at` raises `ColumnIdError` and we surface
its `.reason` rather than letting it escape a writer).

#### The layered write — the part that is easy to get wrong

`load_layered_config` returns the **merged** dict (defaults ← project ← local).
Three failure modes follow, and only the third is new:

- writing that merged dict straight through `save_project_config` **leaks the
  user-level `settings` block into the tracked `board_config.json`**;
- mirroring `TaskManager.save_metadata()`, which writes **both** layers,
  **clobbers `board_config.local.json`** (the user's collapsed columns and
  auto-refresh interval);
- a user-local `columns` override is **promoted** into the tracked file. This is
  board parity (`save_metadata` does the same) — state it in the docstring and
  leave it.

So `create_column` touches `columns` + `column_order` only:

```python
cfg = load_layered_config(str(board_config_path(root, task_dir)),
                          defaults={"columns": DEFAULT_COLUMNS,
                                    "column_order": DEFAULT_ORDER})
columns = list(cfg.get("columns", DEFAULT_COLUMNS))
order = list(cfg.get("column_order", DEFAULT_ORDER))
col_id = generate_col_id(title, [c.get("id") for c in columns if isinstance(c, dict)])
color = color or next_palette_color([c.get("color") for c in columns ...])
cfg["columns"] = columns + [{"id": col_id, "title": title, "color": color}]
cfg["column_order"] = order + [col_id]
project_data, _user_data = split_config(cfg, project_keys=PROJECT_KEYS,
                                        user_keys=USER_KEYS)
save_project_config(str(board_config_path(root, task_dir)), project_data)
```

**Write only the project layer. Never touch the local file** — not even to
rewrite it identically. `split_config` sends any key in neither set to the
project dict, which is what preserves an unrelated project key verbatim;
`_user_data` is deliberately discarded, and that discard is the whole point.

`title` is stored **verbatim** (a `|` is legal there — the emitter puts title
last precisely so it survives; CR/LF are stripped by `sanitize_last_field` on
emit). Do **not** add a stricter rule at this entry point than the medium
enforces: a hand-edited config can already contain one, and the read path is
already tested for it.

#### `color` is validated at the write site — deliberately stricter than the reader

`color` is the opposite case from `title`, and the asymmetry is intentional.
A colour **cannot** round-trip the way a title can, and it reaches three sinks
this module does not control:

- it is emitted as the **middle** field of `COLUMN:`, where `sanitize_middle_field`
  strips `|`/CR/LF — so a stored `|` is **silently mangled on read**, which is
  undecidable for the reader and therefore has to be prevented on write;
- it is interpolated as a rich-markup **tag** (`[{color}]██[/]`) in
  `_ColumnRow.render()` — guarded by `_safe_column_color` — and in the board's
  `ColumnSelectItem.render()` and `ColorSwatch.render()`, which are **not**
  guarded (a known upstream defect recorded by t1377_2). A colour containing `]`
  closes the tag early and injects markup; one containing `[/]` raises
  `MarkupError` inside a render path.

So `create_column` **refuses** rather than stores. Validation is dependency-free
— **do not reach for `rich.Color.parse` here**: `board_columns.py` deliberately
imports only stdlib and `lib/` siblings, and rich would reject the seam's own
stock `UNORDERED_COLOR = "gray"` (rich has `grey0`…`grey100`, no bare `gray`),
i.e. the validator would refuse a value this very module ships.

```python
_COLOR_RE = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$"
                       r"|^[a-z][a-z0-9_]{0,31}$")
```

Accepts the two shapes the framework actually uses — a palette-style hex, or a
lowercase style-name token — and refuses everything else with the new reason
**`invalid_color`**. Whitespace is stripped first; the value is otherwise stored
verbatim (no case normalization — `PALETTE_COLORS` is uppercase hex and there is
no reason to rewrite it).

Three-way argument handling, mirroring the `--task` precedent already in this
module (`is None` ≠ `""`):

| `color` | meaning | result |
|---|---|---|
| omitted / `None` | "pick one for me" | `next_palette_color(...)` |
| `""` | "explicitly colourless" | the entry is created with **no** `color` key; `list-columns` emits an empty middle field, which the readers already handle |
| any other value | explicit choice | validated by `_COLOR_RE`, else refused `invalid_color` |

**The reader keeps its tolerant stance** — `column_records_at` still accepts
whatever a hand-edited `board_config.json` contains, and `_safe_column_color`
still degrades an unparseable one to an unstyled swatch. Writers refuse; readers
degrade. Both are correct, and the tests below pin each so a later edit cannot
collapse them into one stance.

Order of operations: `_require_tree` (containment + layout) → title validation →
read → mutate → split → write. Every refusal happens before the write.

**Concurrency, stated honestly in the docstring:** `save_project_config` is
atomic for readers (`_atomic_write` → temp + `os.replace`) but takes no lock, and
`ait board` holds `self.columns` in memory from startup and never re-reads. A
column created here while a board is open would be dropped by that board's next
`save_metadata()` — which is why pre-phase 2 reconciles at save time. State what
this seam does **not** guarantee even so: it takes no lock, so two simultaneous
writers still lose one update. Do not claim a guarantee this seam does not have.

### 2. Single-source the board key sets (two sites)

Define `PROJECT_KEYS` / `USER_KEYS` **once** in `lib/board_columns.py` (public
names, since `settings_app` imports them and t1404 will too). Then:

- `board/aitask_board.py` — drop the `_PROJECT_KEYS` / `_USER_KEYS` literals at
  `:70-71` and take them from the existing `from board_columns import (…)` block
  at `:445-448`, aliasing to the private names so the `save_metadata` call site
  (`:1072`) is untouched.
- `settings/settings_app.py` — drop `:103-104` and import, aliasing to
  `_BOARD_PROJECT_KEYS` / `_BOARD_USER_KEYS` so `save_board` (`:499-505`) is
  untouched.

**Do NOT touch `stats/stats_config.py`** (finding 1) or
`tests/test_board_config_split.py:31-32` (independent ground truth).

`settings_app.py`'s import sits at module scope, so a wrong module or symbol name
breaks `ait settings` at startup — **resolve it against the real interpreter**,
which is the t1377_2 `rich.errors` lesson.

### 3. Board re-imports the slug generator and the palette

`aitask_board.py` extends its existing `from board_columns import (…)` block
(`:445-448`) with `generate_col_id` and `PALETTE_COLORS`, the same idiom already
used for `board_ordering` / `topic_semantics`. `ColumnEditScreen._generate_col_id`
becomes a thin `@staticmethod` delegate (keeps `self._generate_col_id(...)` at
`:5620` working, and keeps the board the semantic owner in prose) and the
module-level `PALETTE_COLORS` literal at `:5505-5514` is deleted in favour of the
import. One implementation either way.

**These are the first tests for the slug generator** — it has none today
(`grep -rn _generate_col_id tests/` is empty).

The board's `TaskManager.add_column` (`:1700`) is **not** rerouted through
`create_column`: it mutates in-memory state the board then re-renders, and
unifying the writer would mean reshaping `save_metadata`. Vocabulary is shared;
the two writers stay separate. Recorded as a decision, not an oversight.

### 4. Wrapper: `aitask_board_column.sh create`

Add a fourth verb to `board_columns.main()` and the wrapper's header comment:

```
create --root R [--task-dir D] --title T [--color C]
                    -> CREATED:<col_id>|<color>|<title>
                    -> ERROR:<reason>            (exit 1)
```

Same field discipline as `list-columns`: **title last** (`sanitize_last_field`),
colour in the middle (`sanitize_middle_field`), so one parser handles both
records. `--title` omitted entirely is a **usage** error (`parser.error`, exit 2);
`--title ''` falls through to the seam and refuses `ERROR:empty_title` — the same
`is None` vs `""` distinction `current-column` already draws for `--task`.

`--color` uses the same three-way handling: **omitted** → auto-assign from the
palette; `--color ''` → colourless; anything else → validated, with a malformed
value refused as `ERROR:invalid_color` (exit 1, nothing written). The refusal
happens in the seam, not in argparse, so the Python API and the CLI cannot drift
apart. Add `invalid_color` to the wrapper header's list of stable reason tokens
alongside `empty_title`, so callers keep branching on tokens rather than prose.
This is a **public** surface — `aitask_update.sh` already probes it and t1404 /
t1377_5 will reuse it — which is exactly why it validates rather than trusting
its caller.

The wrapper stays write-free (the Python module owns every write) — do not source
`lib/atomic_write.sh`, per its own header comment.

### 5. UI: the `＋ New column…` row and the title modal

**5a. Dismissal contract (`monitor_shared.py`).** `ColumnPickerModal` currently
dismisses `col_id: str | None`. Widen it to a tagged tuple, the shape t1377_2's
notes say scaled:

| Result | Meaning |
|---|---|
| `("existing", col_id)` | move to an already-configured column |
| `("new", None)` | user picked `＋ New column…` |
| `None` | cancel |

A sentinel `col_id` string is **rejected**: it would flow into `titles.get(...)`
and could reach the seam as a real column id, and magic values are exactly what
the tagged tuple exists to avoid.

Implementation keeps **one** place that knows the shape:

- `_ColumnRow.pick_result()` returns `("existing", self._col_id)`;
- `_NewColumnRow(_ColumnRow)` overrides `pick_result()` → `("new", None)` and
  `render()` → `" ＋ New column…"` (no swatch, no id). Subclassing is what keeps
  `_focus_neighbor`'s `isinstance(w, _ColumnRow)` scan and `on_mount`'s focus
  loop working unchanged;
- `_ColumnRow.on_key` (enter) and `ColumnPickerModal.on_button_pressed` (OK) both
  dismiss `row.pick_result()`;
- `action_dismiss_dialog` and every cancel path keep returning `None`.

`ColumnPickerModal.__init__` gains `allow_new: bool = False` (default off, so the
constructor stays backward-compatible for any caller that does not want it);
`compose()` appends the `_NewColumnRow` **after** the configured rows when set.

**5b. `NewColumnTitleModal` (`monitor_shared.py`).** Copy
`TaskNumberInputModal`'s shape verbatim (`:672-741`): `#new-col-dialog` with a
header, one `Input`, a help line, OK/Cancel; `Binding("escape", …)`;
`on_input_submitted`; `narrow` ctor kwarg with `add_class("narrow")` as the
**first statement** of `compose()`; and a `.narrow` CSS block widening the dialog
and stacking the buttons with `min-width: 0`.

- Dismisses the raw title string, or `None`.
- **Empty / whitespace-only title is rejected in place**: `notify("Title is
  required", severity="warning")` and **return without dismissing**, mirroring
  `ColumnEditScreen.save` (`aitask_board.py:5613-5616`). Never silently dismiss.
  Both the OK button and Enter route through the same guard.
- The CSS comment must not contain the lowercase word "narrow" (finding 7).

**5c. `minimonitor_app.py`.** `_open_column_picker` passes `allow_new=True`.
`_on_column_chosen` branches on the tag:

```python
if not result:
    return
action, col_id = result
if action == "new":
    self.push_screen(NewColumnTitleModal(narrow=True),
                     callback=lambda title: self._on_new_column_title(
                         title, target_id, target_root, sess))
    return
# ... today's existing-column body, unchanged ...
```

`_on_new_column_title` returns early on `None` / blank, else
`run_worker(self._create_and_move(...), group="board-column")`.

`_create_and_move(target_id, target_root, sess, title)`:

1. `rc, out = await self._run_board_column_cmd(["create", "--root", str(target_root), "--title", title])`
   — reuse the existing injectable seam; do not add a second subprocess helper.
2. Non-zero or no leading `CREATED:` → `notify(f"Create failed: {first or f'exit {rc}'}", severity="warning", markup=False)` and return.
3. Parse with `line[len("CREATED:"):].split("|", 2)` — the same first-two-separators
   rule, because the title is last.
4. Delegate the move to the **existing** `_apply_column_move(target_id,
   target_root, sess, new_col_id, new_title)`. Do not re-implement it.
5. If the move fails after a successful create, `_apply_column_move` already
   surfaces `Move failed: …`; additionally notify that the column **was** created
   (`markup=False`), so the user is not left thinking nothing happened.

**Every notification carrying a title or subprocess text passes `markup=False`.**
This is not optional: `App.notify` parses its message as markup by default,
`Backlog [/]` raises `MarkupError`, and `a[b]c` is silently swallowed to `ac`.
t1377_2's notes say to assume a fourth sink exists — the create toasts are it.

### 6. `ait settings` stance — record the decision, do not change it

`settings_app.py:2374-2375` labels the Columns section
`"read-only — edit via board TUI"`. That label was forced by capability; a
headless writer now exists, so it becomes a stale claim rather than a real limit.

**Flipping the Settings TUI to editable is out of scope for this child** (the
user scoped it to minimonitor). Record the decision explicitly in the Final
Implementation Notes. The change is already filed as **t1404
`settings_columns_editable`** (`depends: [t1377_3]`), the confirmed `after`
risk-mitigation follow-up from parent planning — and it imports `PROJECT_KEYS` /
`USER_KEYS` from the home step 2 gives them, so record that path in the Notes.

Also note `aidocs/framework/tui_conventions.md`: a runtime TUI may **write**
project-level config, but must never `git commit` / `./ait git push` from an
event handler. This flow writes and stops; the user commits.

### Post-phase (risk mitigations)

1. `[prove_layer_split_isolation]` The project/local split lands in step 1 as
   correctness. This phase proves each half **discriminates**, so neither can be
   silently dropped later. **One mutation per test — revert one side at a time**,
   and assert the specific corruption each guard prevents, never "some assertion
   failed":

   - **`settings` must not leak into the tracked layer.** Negative control:
     patch `create_column` to pass the merged dict straight to
     `save_project_config` (skipping `split_config`) and assert
     `"settings" in json.load(board_config.json)` — the leak, named exactly.
   - **`board_config.local.json` must not be rewritten.** Negative control:
     patch `create_column` to also `save_local_config(local_path_for(...),
     user_data)` — the `save_metadata` mirror — and assert the local file's
     bytes **changed**. Assert the mutation-free run's byte-identity via
     `bf.diff_snapshots`, whose snapshot already covers `board_config*.json`.
   - These two need **separate** controls: skipping `split_config` does not
     touch the local file, and mirroring `save_metadata` does not leak
     `settings` into the project file. One control cannot stand in for both.
   - Assert **before** the mutating step as well as after, so a control that
     fails because the fixture was already dirty is distinguishable from one
     that fails because the guard is live.

## Tests

`tests/test_board_columns_seam.py` (extend — fixture columns are `c0`…`c4`, and
`build_fixture_tree` already writes a populated `board_config.local.json`):

| Case | Assertion |
|---|---|
| slug generation | emoji/non-ASCII stripped; `strip().lower()`; collisions uniquify `_2`/`_3`; 20-char cap applied pre-suffix; empty/`"🙂"` → `"column"` |
| **slug is protocol-safe** | `has_record_breaking(generate_col_id(t, []))` is `False` for a title carrying `\|`, CR, LF and an emoji — asserted with the **real** predicate from `record_protocol`, not a local regex |
| palette rotation | first unused hex is chosen; with all 8 used the fallback indexes by count; existing non-palette colours never suppress a palette entry |
| **layered round-trip** | seed an extra unrelated project key **and** a populated local `settings` (`collapsed_columns`, `auto_refresh_minutes`). After `create_column`: (a) the new column is in the project layer; (b) the unrelated project key survives verbatim; (c) `settings` is **absent** from the project file; (d) `board_config.local.json` is **byte-identical** — assert via `bf.diff_snapshots`, which already covers `board_config*.json` |
| refusals write nothing | `""` / `"   "` → `empty_title`; a bad `task_dir` → `unsafe_task_dir`; no tree → `unsupported_layout`; each with `assert_untouched()` |
| **colour refusals** | `"not a color"`, `"#GG0000"`, `"#FF55"`, `"red] [/"`, `"Red"` (uppercase name), and a `\|`/CR/LF-bearing value each refuse `invalid_color` with `assert_untouched()` |
| **colour acceptances — the discriminating cases** | `"#FF5555"` and `"#abc"` accepted; **`"gray"` accepted** — the seam's own `UNORDERED_COLOR`, which `rich` cannot parse, so this is the row that fails if the validator is ever "improved" into `Color.parse` |
| colour three-way | omitted → a palette hex; `""` → the entry has **no** `color` key and `list-columns` emits an empty middle field; explicit → stored verbatim, case preserved |
| **writer refuses, reader degrades** | hand-write a `board_config.json` whose colour is `"not a color"` and assert `column_records_at` still **returns** it (reader tolerance preserved) while `create_column` would have refused it — the two stances pinned in one test so neither can be collapsed into the other |
| **negative control for the colour guard** | bypass `_COLOR_RE` and create with a `\|`-bearing colour; assert it reaches storage and is then **silently mangled** by `list-columns`' middle-field sanitizer — the exact undecidable-on-read corruption the write-site refusal exists to prevent |
| append semantics | the new id lands **last** in `column_order`, and existing columns keep their order and colours |
| missing config file | with no `board_config.json`, creating yields stock `now`/`next`/`backlog` **plus** the new column — board parity with `load_metadata`, pinned because it is surprising |
| headless guard | the new symbols keep `SeamGuardTests`' no-Textual / no-`aitask_board` assertions green |
| de-dup guard | `_PROJECT_KEYS` / `_USER_KEYS` literals are **gone** from `aitask_board.py` and `settings_app.py` source and imported instead; `PALETTE_COLORS` / the slug body are gone from `aitask_board.py` — mirroring the existing `DedupDriftTests` |
| **de-dup discrimination** | `stats_config._USER_KEYS` is asserted **unchanged** and unequal to `board_columns.USER_KEYS` — the negative control for finding 1, so a future sweep cannot "unify" a name collision |

**Reconciliation** — `tests/test_board_columns_reconcile.py` (new; drive a real
`TaskManager` on `tests/lib/board_fixture.py` via `load_board_module` /
`enter_fixture_tree`, the harness the other board-manager tests already use, so
the class under test is the real one rather than a replica):

| Case | Assertion |
|---|---|
| **1. external addition survives** | build a `TaskManager`, then call `board_columns.create_column` on the same tree, then trigger an ordinary board save (`manager.toggle_column_collapsed(...)` — a real gesture, not a direct `save_metadata()` call). Assert the externally-created column is present in the written `board_config.json`, with its title and colour verbatim |
| **2. board-side deletion is not resurrected** | `manager.delete_column("c1")` (which saves). Assert `c1` is **absent** from the written file even though it was on disk when the reconciliation read it — the `_known_col_ids` discriminator. Negative control: clear `_known_col_ids` before the delete and assert `c1` **comes back**, proving the tracking is what prevents it |
| **3. board-side reorder/edit survives an external append** | reorder in memory and edit a column's title, create an external column, save. Assert the board's order and edited title are intact **and** the external column is appended last in both `columns` and `column_order` |
| **4. local layer untouched** | `board_config.local.json` is **byte-identical** across the whole scenario, asserted with `bf.diff_snapshots`; and the reconciliation never opens it — assert via a `mock.patch` on the reader that no call names a `.local.json` path |
| **5. call-site scan** | AST-parse `aitask_board.py` and assert `_reconcile_external_columns` (and `project_columns_at`) are called from **`save_metadata` only** — never from `refresh_board`, `action_refresh_board`, any `on_mount`/`compose`/`render`, or a timer callback. Mirror `tests/test_board_persistence_seam.py`'s `EXPECTED_CALL_SITES` shape. Negative control: inject a synthetic call inside `refresh_board`'s AST and assert the scan **fails** |
| id collision, equal definition | merged silently, no warning recorded |
| id collision, differing definition | the board's version is written, `manager.reconcile_warnings` names the id and both titles, and the `on_warning` callback fired |
| unreadable / missing project config | reconciliation is a no-op, the save still succeeds, no exception escapes |

`tests/test_board_column_cli.sh` (extend, house harness):

- `create --root R --title "My Col"` exits 0 and emits `CREATED:my_col|<hex>|My Col`;
- the column is then visible to `list-columns` and is a legal `move --column` target
  (the round trip is what proves the write is real);
- a title containing `|` round-trips through the **last** field;
- `--title ''` → `ERROR:empty_title`, non-zero exit, tree checksum unchanged;
- `--title` omitted → exit **2** (usage), distinct from the refusal above;
- `--task-dir /etc` → `ERROR:unsafe_task_dir` and a canary outside `--root` untouched;
- `--color '#FF5555'` honoured verbatim and round-trips through the middle field;
  `--color gray` accepted; `--color` omitted auto-assigns a palette hex;
  `--color ''` yields an empty middle field;
- `--color 'not a color'` and `--color 'red] [/'` each print `ERROR:invalid_color`,
  exit non-zero, and leave the tree checksum unchanged — the CLI is where an
  operator or another tool actually supplies this value, so a Python-only test
  would not cover the real entry point (the same argument t1377_1 made for
  `--task-dir` containment).

`tests/test_minimonitor_pick_by_number.py` (extend; reuse `_mk_app`'s
`column_cmd_results` queue and `run_worker` stub — do not build a parallel harness):

| Case | Assertion |
|---|---|
| **migrated dismissals** | every existing picker assertion moves to the tagged tuple: `test_enter_dismisses_with_the_focused_column` → `[("existing", "now")]`; `test_escape_cancels` stays `[None]` |
| new row present / absent | `allow_new=True` renders `New column` as the **last** row; `allow_new=False` (default) does not — the discriminating negative control |
| `("new", None)` path | choosing it pushes `NewColumnTitleModal` and issues **no** seam call |
| create + move in one gesture | a scripted `CREATED:spikes\|#8BE9FD\|Spikes` then `MOVED:…` produces exactly one `create` and one `move` argv, and `_task_cache.invalidate` fires once |
| create fails | `ERROR:empty_title` → warning surfaced, **no** `move` issued, nothing invalidated |
| move fails after create | both toasts fire; the user is told the column exists |
| `CREATED:` with a `\|` title | parsed with `split("\|", 2)` so the title survives |
| **empty-title path** | submitting blank keeps `NewColumnTitleModal` mounted (`isinstance(app.screen, NewColumnTitleModal)` after Enter), emits the warning, and dismisses nothing — driven on a real `Pilot`, because "still mounted" is not observable on the `__new__` harness |
| **narrow render** | `NewColumnTitleModal` at 40×50 / 40×20 / **40×16** via `_assert_controls_inside` on composited screen text, plus the picker re-checked at the same sizes with the extra row |
| **narrow negative control** | `_drop_narrow_rules(NewColumnTitleModal.DEFAULT_CSS)` makes `_assert_controls_inside` **raise** — and assert the stripped CSS still contains a non-narrow rule, proving the helper did not eat the whole block |
| toast markup | every create/move notification passes `markup=False`, asserted on the recorded kwarg (`spy_notify_kwargs`), with a bracket-bearing title carried verbatim |

## Verification

```bash
shellcheck .aitask-scripts/aitask_board_column.sh
bash tests/test_board_column_cli.sh
python3 tests/test_minimonitor_pick_by_number.py
bash tests/test_no_lib_to_tui_import.sh
bash tests/run_all_python_tests.sh    # read ONLY the last line for the verdict
```

Plus a **read-only** live check — this checkout is worked on concurrently, so
**no live create**:

```bash
./.aitask-scripts/aitask_board_column.sh list-columns --root . --include-unordered
python3 -c "import sys; sys.path.insert(0, '.aitask-scripts/lib'); \
  import board_columns as b; print(b.generate_col_id('Spikes 🚀', ['spikes']))"
```

The first must still reproduce the 8 rows (7 configured + `unordered`); the
second must print `spikes_2` without touching disk.

**Reconciliation benchmark (required by pre-phase 2).** Time the reload-and-merge
helper against the real config and the fixture tree, and **record the number in
the Final Implementation Notes**:

```bash
python3 - <<'PY'
import sys, timeit
sys.path.insert(0, '.aitask-scripts/lib')
import board_columns as bc
p = 'aitasks/metadata/board_config.json'
n = 500
t = timeit.timeit(lambda: bc.project_columns_at(p), number=n)
print(f'project_columns_at: {t/n*1000:.4f} ms/call')
PY
```

One denominator: **milliseconds added per `save_metadata()` call**, which is
milliseconds per discrete user gesture — not per frame and not per refresh.
Budget: **< 1 ms**. Baseline for comparison, measured this planning pass on the
real 815-byte `board_config.json`: the *layered* `load_layered_config` (two files
plus a deep merge — strictly more work than the project-only reader) costs
**0.056 ms/call**, so the budget has ~18× headroom. If the measured merge misses
it, stop and confirm with the user.

Finish with `git status --porcelain` to confirm the verification run left nothing
behind.

Step 9 (Post-Implementation) covers cleanup, archival and merge.

## Coordination

Depends on t1377_2 (archived, `f3dbf175b`) and t1377_1 (archived, `6ce832a31`).

- **`aitask_board.py` is edited by other in-flight tasks.** This child touches it
  in five places: the widened import block, the deleted key-set literals, the
  deleted `PALETTE_COLORS`, the slug body turned delegate, and the new
  reconciliation in `save_metadata` / `load_metadata`. Re-read before editing, **grep for
  symbols rather than trusting line numbers**, stage explicit paths, and never
  `git stash` / `git add -A` in this shared checkout.
- **t1377_5 (`board_column_management_dialog`)** adds board-side column
  add/edit/delete/merge behind one dialog — every one of those paths calls
  `save_metadata()` and therefore runs the reconciliation pre-phase 2 installs.
  Record the seam in this plan's `## Notes for sibling tasks` (what
  `_known_col_ids` means, why the merge is save-time only, and the sub-1 ms
  budget) so t1377_5 extends it rather than rediscovering or bypassing it. **A
  merge implemented there must keep the reload off every continuous board path.**
- **t1404 (`settings_columns_editable`, `depends: [t1377_3]`)** consumes
  `PROJECT_KEYS` / `USER_KEYS` from their new home — record the exact import path
  in the Final Implementation Notes.
- Live acceptance in a real ~40-column tmux pane is covered by the aggregate
  manual-verification sibling **t1377_7**.

## Risk

### Code-health risk: medium

- **First write to a tracked project config from outside `ait board`.** The
  project/local split is easy to get wrong in three distinct ways (leak
  `settings` into the tracked file, clobber `board_config.local.json`, promote a
  user-local `columns` override), and a happy-path creation test passes under
  all three · severity: medium (residual — the inline post-phase proves each
  half of the split discriminates, but the layered write itself still ships) ·
  → mitigation: inline post-phase prove_layer_split_isolation
- **`ColumnPickerModal`'s dismissal contract changes shape** (`str | None` → a
  tagged tuple) across **three** in-modal dismissal sites, one production
  consumer and several test call sites. `("existing", "now")` is truthy, so a
  missed consumer does not raise: it falls through `if not col_id` and then
  looks a tuple up in `titles`, notifying a stringified tuple instead of failing
  loudly · severity: medium (residual — the inline pre-phase enumerates every
  consumer so a missed site is caught before migration, but the contract change
  still ships) · → mitigation: inline pre-phase
  sweep_column_picker_dismissal_consumers
- **The board never reloads `board_config.json`** (`load_metadata()` only in
  `TaskManager.__init__`), so a column created from minimonitor while a board is
  open would be invisible there and **silently dropped** by that board's next
  `save_metadata()`. **This task closes that hole before exposing
  `＋ New column…` in minimonitor** — the save-time reconciliation lands as
  pre-phase 2, gating the UI step, so the feature never ships against a board
  that destroys its result · severity: low (residual — the stale-board overwrite
  is closed and call-site-scanned; what remains is that the board now merges
  foreign state at save time, a new behaviour with its own five tests) ·
  → mitigation: inline pre-phase reconcile_external_columns_at_save
- **Concurrent simultaneous writers remain unsolved, and the reconciliation must
  not be read as solving them.** It narrows the *stale-reader* window — a board
  that loaded before the external write now merges instead of clobbering — but it
  takes **no lock**, so two processes whose read→modify→`os.replace` cycles
  interleave still lose one update. `save_project_config` gives reader-visible
  atomicity, not writer serialization. **Intended policy, stated deliberately:
  accept last-writer-wins and document it**, matching the boundary
  `lib/board_columns.py`'s module docstring already declares and
  `Task.reload_and_save_board_fields`'s "best-effort, not atomic". Anything
  stronger needs a lock file over `board_config.json` and is out of scope here ·
  severity: low (the window is milliseconds wide between two interactive
  gestures, and the loss is one column definition, not task data) ·
  → mitigation: none (accepted policy — record it in the docstring and the Final
  Implementation Notes, do not imply the reconciliation covers it)
- **`create` makes `aitask_board_column.sh` a public *write* surface for a value
  that is later interpolated into rich markup.** A malformed `--color` would be
  stored, then silently mangled by the protocol's middle-field sanitizer and
  injected into three markup sites — one guarded (`_ColumnRow`), two not
  (`ColumnSelectItem`, `ColorSwatch`, the upstream defect t1377_2 recorded). The
  plan validates at the write site and keeps the reader tolerant, which is the
  right split, but it does introduce a stricter stance than any other field in
  this module carries · severity: low · → mitigation: none (the colour-refusal
  rows, the `"gray"` acceptance row, and the mangling negative control pin all
  three stances; the unguarded board renderers stay recorded as an upstream
  defect rather than being fixed here)
- The de-dup edits `settings_app.py` at **module scope**, where a wrong module or
  symbol name breaks `ait settings` at startup rather than at the Columns tab —
  the same class of failure as t1377_2's `rich.errors` import · severity: low ·
  → mitigation: none (covered by the de-dup guard test, which fails collection on
  a bad import)
- `aitask_board.py` is a hot file with other in-flight edits, and this task now
  touches it in **five** places — three deletions (key-set literals,
  `PALETTE_COLORS`, the slug body), the widened import block, and the new
  reconciliation inside `save_metadata` / `load_metadata`. That is a wider
  conflict surface than the plan originally carried · severity: low ·
  → mitigation: none (the Coordination rules — grep for symbols, re-read before
  editing, stage explicit paths — are the standing remedy)

### Goal-achievement risk: low

- The approach is the one t1377_1 pre-designed for this child (`generate_col_id`,
  `PALETTE_COLORS`, `create_column`, a `create` verb), and both consuming seams
  are landed and tested. Parent AC3 and AC6 (`.narrow` variant) are directly
  addressed · severity: low · → mitigation: none
- The one open design choice — colour selection in a pane too small for a swatch
  palette — was decided by the user this pass (next unused palette entry), so the
  plan no longer carries an unstated assumption · severity: low ·
  → mitigation: none

### Planned mitigations

- timing: pre-phase | name: sweep_column_picker_dismissal_consumers | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — ColumnPickerModal's dismissal value changes from a col_id string to a tagged tuple and both are truthy, so a missed consumer fails silently | desc: Enumerate every production and test consumer of ColumnPickerModal's dismissal value (all three in-modal dismissal sites, the production consumer and its lambda, every test call site) before changing its shape, record the list, deliberately exclude look-alikes, and check each site off after migration.
- timing: post-phase | name: prove_layer_split_isolation | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — create_column is the first write to the tracked board_config.json from outside the board, and a happy-path test passes under all three split failure modes | desc: Prove each half of the project/local split discriminates with its own one-mutation negative control — merged-dict write leaks `settings` into the tracked file; a save_metadata mirror rewrites board_config.local.json — asserting the specific corruption each guard prevents.
- timing: pre-phase | name: reconcile_external_columns_at_save | type: bug | priority: high | effort: medium | inline_risk: medium | added_complexity: medium | addresses: code-health — the board never reloads board_config.json after startup, so it would silently destroy a column created through this task's own headless writer | desc: Reconcile externally-added columns at the top of TaskManager.save_metadata before the board writes — project layer only, merging genuine external additions while `_known_col_ids` keeps a board-side deletion from being resurrected and an id collision with a differing definition warns instead of silently choosing. HARD CONSTRAINT — must not slow `ait board` down: reachable ONLY from save_metadata (AST call-site scan), never from refresh_board, the auto-refresh timer or any render path, with no polling loop and no render-path I/O; measured per-save cost recorded and held under 1 ms (baseline 0.056 ms for the strictly heavier layered load on the real 815-byte config). Inlined as a pre-phase rather than spawned so the hole is closed before this same task exposes `＋ New column…`.

**Post-inline reassessment (one pass).** With all three phases inlined,
code-health stays **medium**, but for a different reason than before: the
stale-board overwrite is no longer a shipped risk — it is closed in-task and
gated ahead of the UI, dropping that bullet to residual/low. What keeps the level
at medium is the breadth of what still ships: the first tracked-config write from
outside the board, the dismissal-contract change, and now a **new behaviour in
`TaskManager.save_metadata` itself** — a board that merges foreign state at save
time, on the write path of a hot file that other in-flight tasks are editing.
That is a genuine new risk introduced by the inline phase, and it is why the
phase carries an AST call-site scan, a negative control on the deletion
discriminator, and a measured performance budget rather than only a happy-path
test. Goal-achievement stays **low** and is arguably better than before: the
feature no longer depends on a follow-up task landing to be correct in the
presence of a running board. The other two inline phases add no new risk — the
consumer sweep is read-only, and the split controls are tests whose mutations are
in-process patches that restore themselves.
