---
Task: t1377_1_headless_board_column_seam.md
Parent Task: aitasks/t1377_minimonitor_pick_column_action_and_board_column_management.md
Sibling Tasks: aitasks/t1377/t1377_2_*.md, aitasks/t1377/t1377_3_*.md, aitasks/t1377/t1377_4_*.md, aitasks/t1377/t1377_5_*.md, aitasks/t1377/t1377_6_*.md
Archived Sibling Plans: aiplans/archived/p1377/p1377_*_*.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# p1377_1 — headless board-column seam

## Goal

A Textual-free, **root-scoped** module that can read the board's column list and
move a parent task into a column with a correctly gap-computed `boardidx`, plus a
thin shell wrapper so `monitor/` can call it as a subprocess.

## Why this shape (decided at parent planning, user-confirmed)

Three options were surveyed:

| Option | Why rejected / chosen |
|---|---|
| Extend `aitask_update.sh --boardcol` | Would re-implement `lib/board_ordering.py`'s gap arithmetic **in bash**, and the script is cwd-relative with no `--root`. Rejected. |
| Import `lib/board_columns.py` directly into minimonitor | Puts a task-file write on the TUI event loop and gives `monitor/` its first in-process file mutation. Rejected. |
| **New `lib/` module + thin `.sh` wrapper, called via subprocess** | Matches the one mutation `monitor/` already performs (`aitask_agent_marks.sh` via `_run_marks_cmd`). **Chosen.** |

## Steps

### 1. `.aitask-scripts/lib/board_columns.py` (new)

Public surface:

```python
DEFAULT_COLUMNS, DEFAULT_ORDER
UNORDERED_ID = "unordered"; UNORDERED_TITLE = "Unsorted / Inbox"

class ColumnIdError(ValueError): ...

def board_config_path(root: Path) -> Path
def load_columns(root: Path) -> tuple[list[str], dict[str, str]]
def column_indices(root: Path, col_id: str, exclude: str = "") -> list[int]
def move_task_to_column(root: Path, task_id: str, col_id: str) -> MoveOutcome
```

**Root-scoping is a hard rule.** Every entry point takes an explicit `root`. Do not
call `config_utils.task_dir()` / `metadata_dir()` — they read `TASK_DIR` / cwd
ambiently, and minimonitor's `target_root` (from `_root_for_snap`) may be a
different project entirely. Derive `<root>/aitasks/metadata/board_config.json` from
the argument.

Imports allowed: `config_utils`, `task_yaml`, `board_ordering`, `atomic_write`.
**Never** `aitask_board` — `tests/test_no_lib_to_tui_import.sh` freezes that
direction.

`MoveOutcome` — frozen dataclass, rich return, never a bare bool:

```python
@dataclass(frozen=True)
class MoveOutcome:
    moved: str | None = None          # filename
    col_id: str | None = None
    board_idx: int | None = None
    refused: tuple[tuple[str, str], ...] = ()   # (task_id, reason)
    @property
    def ok(self) -> bool: return not self.refused
```

Reasons: `unknown_column`, `not_found`, `not_a_parent_task`.

`move_task_to_column` order of operations:

1. `load_columns(root)`; accept `col_id` if configured **or** `UNORDERED_ID`.
   Otherwise refuse `unknown_column`. *(This is the validation
   `aitask_update.sh --boardcol` never performed.)*
2. Refuse `not_a_parent_task` for a child id (`<p>_<c>`) before any glob — matches
   `TaskManager._resolve_parents` and the board's "children cannot be moved" rule.
   Resolve `<root>/aitasks/t<id>_*.md`; refuse `not_found` on no match.
3. `idx = board_ordering.index_for_append(column_indices(root, col_id))`. Reuse the
   pure module — do not re-implement the arithmetic.
4. `parse_frontmatter` → set `boardcol` / `boardidx` → `serialize_frontmatter` →
   `atomic_write_text`.
5. Touch **only** `boardcol` and `boardidx`. Both are in `BOARD_LAYOUT_KEYS`, so
   this is a **layout write**: do **not** set `updated_at`. Never invent a key;
   never recreate a vanished file.

`column_indices` reads every `<root>/aitasks/t*.md` parent, coerces via
`normalize_board_idx` (the single coercion point — negative values are legal and
normal), and excludes `exclude` by filename.

**Module docstring must state the atomicity boundary.** `atomic_write_text` gives
*reader-visible atomicity*, not writer serialization: two concurrent
read-modify-writes each render from the same old text and the second replace
discards the first. `Task.reload_and_save_board_fields` is equally unserialized, so
this **matches** the existing seam rather than regressing it. Do not claim a lock
this seam does not take.

### 2. De-duplicate the column vocabulary

`DEFAULT_COLUMNS` / `DEFAULT_ORDER` exist in **two** places today
(`board/aitask_board.py`, `lib/work_report_gather.py`). Move both here, then:

- `work_report_gather.load_columns()` becomes a delegate that keeps its own
  `_die(..., EXIT_INFRA)` wrapper. The CLI's fail-closed protocol behaviour is
  unchanged; the **library** path raises `ColumnIdError` instead of `sys.exit`.
  That difference is exactly what makes the reader importable into a TUI.
- `aitask_board.py` imports the constants back — same pattern it already uses for
  `board_ordering` / `topic_semantics` (`# noqa: E402` after the sys.path setup).

### 3. `.aitask-scripts/aitask_board_column.sh` (new)

```
list-columns --root R      → COLUMN:<id>|<title>   (one per line)
move --root R --task N --column C
                           → MOVED:<task>|<col>|<idx>
                           → ERROR:<reason>        (non-zero exit)
```

`#!/usr/bin/env bash`, `set -euo pipefail`, per
`aidocs/framework/shell_conventions.md`.

**The wrapper writes nothing itself** — it is a thin CLI that execs the Python
module, which owns every file write via `atomic_write_text`. So it needs no
`lib/atomic_write.sh` sourcing and is out of scope for
`t1396_fix_remaining_shell_temp_write_defects`'s truncate-then-write sweep. Keep it
that way: if a shell-side write is ever added here, it becomes a t1396 surface.

Per `aidocs/framework/aitasks_extension_points.md`: **no `ait` dispatcher entry**
(the dispatcher is user-facing only; this is shelled out from a TUI) and **no
code-agent allowlist entries** in `.claude/settings.local.json` / `.codex/rules/` /
the three `seed/` mirrors — that 5-touchpoint checklist applies only to
*skill-invoked* helpers. Adding entries here would be dead weight advertising a
skill-facing surface that does not exist.

### 4. `aitask_update.sh --boardcol` validation

Today an unknown id silently produces a task that renders in **no** column — not
even `unordered`. Validate after `parse_args`, mirroring how `--anchor` is
normalised and existence-checked via `normalize_anchor_id`. Error message should
name the valid ids.

## Tests

`tests/test_board_columns_seam.py` — mirror `tests/test_board_manager_moves.py`
(patch module constants, no Textual Pilot) on `tests/lib/board_fixture.py`:

| Case | Assertion |
|---|---|
| single move | index is strictly greater than the destination max |
| K sequential moves | indices distinct and ascending |
| unknown column / child id / missing task | `refused` names it **and** `bf.snapshot` is byte-identical — nothing written |
| layout-write discipline | `updated_at` unchanged, **plus a negative control** naming a non-layout key that *does* stamp it |
| headless guard | module source has no `import textual` / `from textual` / `import aitask_board` (mirrors `SeamGuardTests`) |
| de-dup drift guard | `work_report_gather.load_columns()` and `board_columns.load_columns(root)` agree on the same tree |
| root-scoping | a move against a second fixture root writes **only** in that root |

`tests/test_board_column_cli.sh` — both subcommands, the `ERROR:` line, non-zero
exit on a bad column, and `--root` pointing at a non-cwd tree.

Plus an `aitask_update.sh --boardcol` rejection test.

`tests/test_board_persistence_seam.py`'s AST-parsed `EXPECTED_CALL_SITES` must stay
green **unedited** — this child adds no `reload_and_save_board_fields` call site and
moves none out of the board.

## Shared file: `lib/work_report_gather.py`

`t1243_8_boardgroup_field_and_model` (Ready) appends `"boardgroup"` to
`BOARD_KEYS`, which flows into that file's empty-metadata probe. This child edits
`load_columns()` and the `DEFAULT_COLUMNS` / `DEFAULT_ORDER` constants — different
functions, no semantic conflict, and the writer here names
`("boardcol", "boardidx")` explicitly so `BOARD_KEYS` growth cannot reach it.
Same-file rebase only.

## Verification

```bash
shellcheck .aitask-scripts/aitask_board_column.sh .aitask-scripts/aitask_update.sh
bash tests/test_board_column_cli.sh
bash tests/test_no_lib_to_tui_import.sh
bash tests/run_all_python_tests.sh    # read ONLY the last line
```

## Coordination

**`t1379` has landed** (Done, `a75127829`): `lib/atomic_write.sh`,
`lib/atomic_write.py`, an atomic `Task.save` and an atomic `write_task_file` are all
committed. Consume them — source `atomic_write.sh` in the wrapper; do not
open-code a temp-file dance.

The live conflict is `aitask_board.py` (this child touches only the
`DEFAULT_COLUMNS` / `DEFAULT_ORDER` constants). The t1243 chain is editing that file
concurrently — `t1243_6` in flight, `t1243_7` next — in different regions. Shared
checkout: grep for symbols instead of trusting line numbers, stage explicit paths,
check `git diff --cached`, never `git stash` / `git add -A`.

## Notes for sibling tasks

*(fill in at Step 8 — record the final module API, the wrapper's exact output
protocol, and anything t1377_2/t1377_3 must know to call it.)*
