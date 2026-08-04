---
Task: t1377_3_minimonitor_create_new_column.md
Parent Task: aitasks/t1377_minimonitor_pick_column_action_and_board_column_management.md
Sibling Tasks: aitasks/t1377/t1377_1_*.md, aitasks/t1377/t1377_2_*.md, aitasks/t1377/t1377_4_*.md, aitasks/t1377/t1377_5_*.md, aitasks/t1377/t1377_6_*.md
Archived Sibling Plans: aiplans/archived/p1377/p1377_*_*.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# p1377_3 — minimonitor: create a new board column

## Goal

Let the user create a column from minimonitor and move the task into it, via a
headless `board_config.json` writer. Satisfies parent AC3.

## Steps

### 1. Extend `lib/board_columns.py`

```python
def generate_col_id(title: str, existing_ids: list[str]) -> str
PALETTE_COLORS: list[tuple[str, str]]              # (hex, label), 8 entries
def create_column(root: Path, title: str, color: str | None = None) -> str
_PROJECT_KEYS = {"columns", "column_order"}
_USER_KEYS = {"settings"}
```

`generate_col_id` is lifted verbatim from `ColumnEditScreen._generate_col_id`:
strip non-ASCII → lower → `[^a-z0-9]+` → `_` → trim `_` → truncate 20 → fallback
`"column"` → uniquify `_2`, `_3`, …

**That transform is load-bearing beyond cosmetics:** because it maps everything
outside `[a-z0-9]` to `_`, it can never emit `|`, CR or LF — the exact characters
`work_report_gather` treats as a fatal record-breaking error. Preserve the
property and assert it.

#### The layered write — the part that is easy to get wrong

`load_layered_config` returns the **merged** dict (project ← `.local`). Two failure
modes follow:

- writing that merged dict through `save_project_config` **leaks the user-level
  `settings` block into the tracked `board_config.json`**;
- mirroring `TaskManager.save_metadata()` — which writes **both** layers —
  **clobbers `board_config.local.json`**.

`create_column` touches `columns` + `column_order` only. So: load merged, mutate,
`split_config(merged, project_keys=_PROJECT_KEYS, user_keys=_USER_KEYS)`, and write
**only the project layer**. Leave the local file untouched on disk.

### 2. Single-source `_PROJECT_KEYS` / `_USER_KEYS`

Currently **triplicated**: `board/aitask_board.py`, `settings/settings_app.py`
(as `_BOARD_PROJECT_KEYS` / `_BOARD_USER_KEYS`) and `stats/stats_config.py`. Define
once here; all three import. Derive, don't duplicate.

### 3. Board re-imports

`aitask_board.py` imports `generate_col_id` and `PALETTE_COLORS` back (same pattern
as `board_ordering` / `topic_semantics`). `ColumnEditScreen` either delegates to the
import or drops its staticmethod — one implementation either way.

**Add the first tests for the slug generator** — it has none today.

### 4. Wrapper + UI

- `aitask_board_column.sh create --root R --title T [--color C]` →
  `CREATED:<col_id>|<title>` or `ERROR:<reason>`.
- `ColumnPickerModal` (t1377_2) gains a trailing `＋ New column…` row. Selecting it
  opens a title-entry modal (copy `TaskNumberInputModal`'s shape), then creates and
  moves in one gesture.
- **Empty / whitespace-only title is rejected in place** — warn and keep the modal
  mounted, mirroring `ColumnEditScreen.save`'s "Title is required" notify-and-return.
  Never silently dismiss.
- Every new modal ships a `.narrow` variant (ctor kwarg → `add_class("narrow")`
  first in `compose()` → `ClassName.narrow` CSS block).

### 5. `ait settings` stance — record, do not change

`settings_app.py` labels the Columns section "read-only — edit via board TUI". That
label was forced by capability; a headless writer now exists, so it is a stale claim
rather than a real limit.

**Flipping the settings TUI is out of scope for this child.** Record the decision
explicitly in the Final Implementation Notes. The change itself is already filed as
**t1404 `settings_columns_editable`** (`depends: [t1377_3]`), the confirmed `after`
risk-mitigation follow-up from parent planning.

Also note `aidocs/framework/tui_conventions.md`: a runtime TUI may **write**
project-level config but must never `git commit` / `./ait git push` from an event
handler.

## Tests

| Case | Assertion |
|---|---|
| slug generation | emoji/non-ASCII stripped; collisions uniquified; 20-char cap; empty → `"column"`; **no output can contain `\|`, CR or LF** |
| **layered round-trip** | seed `board_config.json` with an extra unrelated project key **and** `board_config.local.json` with a populated `settings` block (`collapsed_columns`, `auto_refresh_minutes`). After `create_column`: (a) new column in the project layer; (b) unrelated project key survives verbatim; (c) `settings` **absent** from the project file; (d) `board_config.local.json` **byte-identical** to before |
| narrow render | title modal at 40 cols on composited screen text, with the `.narrow`-removal negative control |
| empty title | modal stays mounted, warning emitted, **nothing created** |

The layered round-trip is the important one: a happy-path creation test passes even
when the split is wrong.

## Verification

```bash
shellcheck .aitask-scripts/aitask_board_column.sh
bash tests/test_board_column_cli.sh
bash tests/run_all_python_tests.sh    # read ONLY the last line
```

## Coordination

Depends on t1377_2. Touches `aitask_board.py` only for imports — small, but that
file is edited by other in-flight tasks. Re-read before editing; grep for symbols
rather than line numbers; stage explicit paths; never `git stash` / `git add -A`.

## Notes for sibling tasks

*(fill in at Step 8 — record where `_PROJECT_KEYS` / `_USER_KEYS` now live, since
t1404 imports them.)*
