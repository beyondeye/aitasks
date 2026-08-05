---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [aitask_board, board_columns, python, bash_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1243
implemented_with: claudecode/opus5
created_at: 2026-08-04 09:54
updated_at: 2026-08-05 11:50
---

## Context

Deliverable 1 of t1377 needs minimonitor to move a task to a board column. It
cannot today: `grep -rn boardcol .aitask-scripts/monitor/` returns **zero** hits.
The whole `monitor/` package is read-only over tmux + task files; its only
mutation is an `asyncio` subprocess to `aitask_agent_marks.sh`.

Neither existing path works:

- **`aitask_update.sh --boardcol`** writes the column but **never computes
  `boardidx`** and **never validates the column id**. The task keeps its old index
  (or ties at 0), and a bad id yields a task that renders in no column at all. It
  is also cwd-relative, while minimonitor resolves a per-pane `target_root` that
  may be a **different project**.
- **Importing `TaskManager`** is impossible from `monitor/`: `aitask_board.py`
  imports Textual at module scope and its `TASKS_DIR` / `METADATA_FILE` are
  module-level and cwd-relative.

This child builds the missing seam. It is the foundation for t1377_2 (minimonitor
action) and is consumed again by t1377_3 (column creation).

**User-confirmed decision at planning:** a new `lib/` module plus a thin `.sh`
wrapper, with minimonitor calling it via subprocess — not an in-process import and
not an extension of `aitask_update.sh`.

## Key Files to Modify

- **`.aitask-scripts/lib/board_columns.py`** — NEW. Textual-free, root-scoped
  reader + writer.
- **`.aitask-scripts/aitask_board_column.sh`** — NEW. Thin CLI over the module.
- **`.aitask-scripts/lib/work_report_gather.py`** — `load_columns()` delegates to
  the new module; `DEFAULT_COLUMNS` / `DEFAULT_ORDER` move out.
- **`.aitask-scripts/board/aitask_board.py`** — import `DEFAULT_COLUMNS` /
  `DEFAULT_ORDER` back instead of defining them.
- **`.aitask-scripts/aitask_update.sh`** — add column-id validation to `--boardcol`.
- **`tests/test_board_columns_seam.py`**, **`tests/test_board_column_cli.sh`** — NEW.

## Reference Files for Patterns

- `.aitask-scripts/lib/board_ordering.py` — the pure gap-index arithmetic to reuse
  (`index_for_append`). Do **not** re-implement it.
- `.aitask-scripts/lib/task_yaml.py` — `parse_frontmatter` / `serialize_frontmatter`,
  `BOARD_LAYOUT_KEYS`, `normalize_board_idx` (the single coercion point).
- `.aitask-scripts/lib/atomic_write.py` (and `lib/atomic_write.sh`, added by t1379)
  — `atomic_write_text`. Do not open-code a `$TMPDIR`+`mv` dance.
- `.aitask-scripts/lib/work_report_gather.py` `load_columns()` — the existing column
  reader, including the `|`/CR/LF rejection this module must preserve.
- `.aitask-scripts/monitor/monitor_shared.py` `AgentMarksMixin._run_marks_cmd` — the
  subprocess-helper shape t1377_2 will use to call the wrapper.
- `tests/test_board_manager_moves.py` — the test style to mirror (patches module
  constants, no Textual Pilot), including its `SeamGuardTests` headless guard.
- `tests/lib/board_fixture.py` — `build_fixture_tree`, `snapshot`, `diff_snapshots`.

## Implementation Plan

### 1. `lib/board_columns.py`

Root-scoped: **every** entry point takes an explicit `root: Path`. Nothing may read
`task_dir()` / `metadata_dir()` ambiently — minimonitor's `target_root` can be
another project. `tests/test_no_lib_to_tui_import.sh` freezes the `lib/` -> TUI
direction, so import `config_utils`, `task_yaml`, `board_ordering`, `atomic_write`
— never `aitask_board`.

```python
DEFAULT_COLUMNS, DEFAULT_ORDER
UNORDERED_ID = "unordered"; UNORDERED_TITLE = "Unsorted / Inbox"

class ColumnIdError(ValueError): ...   # '|', CR or LF in a configured id

def board_config_path(root) -> Path
def load_columns(root) -> tuple[list[str], dict[str, str]]
def column_indices(root, col_id, exclude="") -> list[int]
def move_task_to_column(root, task_id, col_id) -> MoveOutcome
```

`MoveOutcome` is a frozen dataclass
`(moved: str|None, col_id, board_idx, refused: tuple[tuple[str,str],...])` — a rich
return naming which item failed and why (`unknown_column`, `not_found`,
`not_a_parent_task`). Never a bare bool.

`move_task_to_column` must:

1. Validate `col_id` against `load_columns(root)` plus the synthetic `unordered`.
2. Resolve `<root>/aitasks/t<id>_*.md`. **Refuse child ids** (`t<p>_<c>`) — matches
   `TaskManager._resolve_parents` and the board's "children cannot be moved" rule.
3. `board_idx = board_ordering.index_for_append(column_indices(root, col_id))`.
4. `parse_frontmatter` -> set `boardcol` / `boardidx` -> `serialize_frontmatter` ->
   `atomic_write_text`.
5. Write **only** `boardcol` + `boardidx`. Both are in `BOARD_LAYOUT_KEYS`, so this
   is a **layout** write: it must **not** bump `updated_at`, and its merge conflicts
   resolve silently local-wins. Coerce every read index through
   `normalize_board_idx`.
6. Never invent a key; never recreate a file that has vanished.

**Document the atomicity boundary in the module docstring.** `atomic_write_text`
gives reader-visible atomicity, **not** writer serialization: two concurrent
read-modify-writes can each render from the same old text and the second replace
discards the first. The board's `reload_and_save_board_fields` is equally
unserialized, so this matches the existing seam rather than regressing it. Do not
claim a lock this seam does not take.

### 2. De-duplicate, don't fork

`DEFAULT_COLUMNS` / `DEFAULT_ORDER` exist twice today (`aitask_board.py`,
`work_report_gather.py`). Move both into `lib/board_columns.py`, then:

- `work_report_gather.load_columns()` **delegates**, keeping its own
  `_die(..., EXIT_INFRA)` wrapper so the CLI's fail-closed protocol behaviour is
  unchanged — while the library path raises `ColumnIdError` instead of calling
  `sys.exit`. That difference is what makes it safe to import into a TUI.
- `aitask_board.py` imports the constants back. Precedent: it already re-imports
  `topic_semantics` and `board_ordering` with `# noqa: E402`.

### 3. `aitask_board_column.sh`

```
aitask_board_column.sh list-columns --root R      # COLUMN:<id>|<title>
aitask_board_column.sh move --root R --task N --column C
                                                  # MOVED:<task>|<col>|<idx>
                                                  # or ERROR:<reason>
```

Per `aidocs/framework/aitasks_extension_points.md`: **no `ait` dispatcher entry**
(the dispatcher is user-facing only; this exists to be shelled out from a TUI) and
**no code-agent allowlist entries** (the whitelist applies only to skill-invoked
helpers). Follow `aidocs/framework/shell_conventions.md`: `#!/usr/bin/env bash`,
`set -euo pipefail`. Source `lib/atomic_write.sh` if any shell-side write is needed.

### 4. `aitask_update.sh --boardcol` validation

Today an unknown id yields a task in no column at all. Validate after `parse_args`,
exactly as `--anchor` already does via `normalize_anchor_id`, and fail with a clear
message naming the valid ids.

### Shared file: `lib/work_report_gather.py`

`t1243_8_boardgroup_field_and_model` (Ready) also edits this file — it appends
`"boardgroup"` to `BOARD_KEYS`, which flows into the **empty-metadata probe**.
This child edits `load_columns()` and the `DEFAULT_COLUMNS` / `DEFAULT_ORDER`
constants. **Different functions, so no semantic conflict** — and this child's
writer names `("boardcol", "boardidx")` explicitly, so a growing `BOARD_KEYS`
cannot reach it. Purely a same-file rebase; re-read before editing.

## Verification Steps

```bash
shellcheck .aitask-scripts/aitask_board_column.sh .aitask-scripts/aitask_update.sh
bash tests/test_board_column_cli.sh
bash tests/test_no_lib_to_tui_import.sh
bash tests/run_all_python_tests.sh      # read ONLY the last line for the verdict
```

Tests to write in `tests/test_board_columns_seam.py`:

- happy path: one move appends past the destination max; K sequential moves get
  distinct ascending indices;
- refusal cases (unknown column, child id, missing task) each assert a
  **byte-identical tree snapshot** — nothing written;
- `updated_at` is **unchanged** by a move, **with a negative control** that names a
  non-layout key and does stamp it (proves the assertion discriminates);
- a **headless guard** mirroring `SeamGuardTests`: the module source contains no
  `import textual` / `from textual` / `import aitask_board`;
- a **drift guard** that `work_report_gather.load_columns()` and
  `board_columns.load_columns(root)` agree on the same tree — proving the de-dup is
  real, not two implementations that happen to match today;
- `aitask_update.sh --boardcol` rejects an unknown id.

`tests/test_board_persistence_seam.py`'s AST-parsed `EXPECTED_CALL_SITES` must stay
green **unedited**: this child adds no `reload_and_save_board_fields` call site and
moves none out of the board.

## Coordination — read before starting

**`t1379_atomic_task_file_writes` has LANDED** (Done/archived, commit
`a75127829`). Its helpers are committed and clean — there is no coordination left,
only consumption:

- `.aitask-scripts/lib/atomic_write.sh` exists — **source it** from
  `aitask_board_column.sh`; do not open-code a `$TMPDIR`+`mv` dance.
- `.aitask-scripts/lib/atomic_write.py` `atomic_write_text` is the Python writer.
- `Task.save` and `aitask_update.sh`'s `write_task_file` are already atomic, so the
  `--boardcol` validation lands on a clean file.

**The live conflict is `aitask_board.py`.** This child's only edit there is
replacing the `DEFAULT_COLUMNS` / `DEFAULT_ORDER` literals with an import. That
file is being edited concurrently by the t1243 chain (`t1243_6` in flight,
`t1243_7` next) in *different* regions (marking, command provider), so git should
auto-merge — but it is the same shared checkout. Grep for the symbols rather than
trusting line numbers, stage explicit paths, check `git diff --cached` before
committing, and never `git stash` / `git add -A` here.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-05T08:50:51Z status=pass attempt=1 type=human
