---
Task: t1377_1_headless_board_column_seam.md
Parent Task: aitasks/t1377_minimonitor_pick_column_action_and_board_column_management.md
Sibling Tasks: aitasks/t1377/t1377_2_*.md, aitasks/t1377/t1377_3_*.md, aitasks/t1377/t1377_4_*.md, aitasks/t1377/t1377_5_*.md, aitasks/t1377/t1377_6_*.md
Archived Sibling Plans: aiplans/archived/p1377/p1377_*_*.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-05 11:43
---

# p1377_1 — headless board-column seam

## Context

Deliverable 1 of t1377 needs `ait minimonitor` to move a task to a board column.
It cannot today: `grep -rn boardcol .aitask-scripts/monitor/` returns **zero**
hits — the whole `monitor/` package is read-only over tmux plus task files, and
its only mutation is an `asyncio` subprocess to `aitask_agent_marks.sh`.

Neither existing path works. `aitask_update.sh --boardcol` writes the column but
never computes `boardidx` and never validates the column id, so a bad id yields a
task that renders in **no** column at all; it is also cwd-relative, while
minimonitor resolves a per-pane `target_root` that may be a different project.
Importing `TaskManager` is impossible from `monitor/`: `aitask_board.py` imports
Textual at module scope and its `TASKS_DIR` / `METADATA_FILE` are module-level and
cwd-relative.

This child builds the missing seam. It is the foundation for t1377_2 (minimonitor
action) and is extended again by t1377_3 (column creation).

**User-confirmed at parent planning:** a new `lib/` module plus a thin `.sh`
wrapper, with minimonitor calling it via subprocess — not an in-process import,
not an extension of `aitask_update.sh`.

## Verification pass (2026-08-05) — what this plan corrects

This plan was re-verified against the current tree before implementation. Seven
material drifts were found and are folded in below:

1. **Coordination was stale.** t1243_5, t1243_6, t1243_7, t1369, t1371 and t1379
   have all landed and archived. The "live conflict / t1243 chain in flight"
   warning no longer applies.
2. `index_for_append([])` returns **`STEP` (1024)**, not `0`.
3. `UNORDERED_ID` / `UNORDERED_TITLE` **already exist** (`work_report_gather.py:62-63`)
   — this is a *move*, not a creation.
4. `load_columns()` already returns a `titles` dict that **includes** `unordered`,
   so "validate against the list *plus* the synthetic unordered" is one lookup,
   not two.
5. `_resolve_parents` (`aitask_board.py:1551`) **conflates** a child id and an
   unknown filename into the single reason `not_a_parent_task`. Our finer
   three-reason set is a deliberate improvement, not parity.
6. `aitask_work_report_gather.sh --list-columns` runs a **full `scan_tasks()`**
   (glob + parse of every task file) just to decide whether to prepend
   `unordered` — so it must **not** be used as the validation oracle for
   `--boardcol`.
7. **User decisions this pass:** the read surface gains colour and a
   current-column verb (t1377_2's picker needs both); the de-dup sweep also
   folds `UNORDERED_ID` / `UNORDERED_TITLE` and the bare `"unordered"` literal at
   `aitask_board.py:357`. The `tests/test_board_config_split.py` fixture literal
   is deliberately **left alone** — a fixture that derives from the code under
   test is weaker as independent ground truth.

Plan review then raised five further gaps, all confirmed against the source and
addressed above:

8. **Task-id resolution was underspecified** — an untrusted `--task` reached a
   glob. Now regex-gated to `^\d+$`, with `ambiguous_task_id` for multiple
   matches (the existing `cmd_resolve` mishandles this; it is not a precedent).
9. **Root scoping vs `TASK_DIR`** — `task_dir` is now an explicit parameter and
   the layout is *enforced* (`unsupported_layout`) instead of silently degrading
   to stock defaults via `load_layered_config`'s missing-file behaviour.
10. **Deletion race** — `atomic_write.commit` is an unconditional `os.replace`,
    so it **recreates** a file deleted after parsing. Replaced the one-shot
    helper with `prepare` / identity-check / `commit`, and narrowed the docstring
    promise to what the writer can actually guarantee.
11. **Board parity** — `column_indices` now applies the board's phantom-stub /
    unparseable eligibility rule (`aitask_board.py:1097`), so an invisible file
    cannot inflate the append index.
12. **Live smoke test** — narrowed to read-only; all mutation coverage stays in
    fixtures so the shared checkout is never dirtied.

A second review round raised two more, both confirmed:

13. **`--task-dir` containment** — the new parameter was user-controlled but
    unconstrained, and `Path("/proj") / "/etc"` evaluates to `/etc`, so an
    absolute or `../` value escaped the root-scoped mutation boundary entirely.
    Now rejected as `unsafe_task_dir` (non-absolute, no `..`, and resolved-path
    containment), tested at **both** the Python API and the shell CLI.
14. **The vanished-file test was wrong** — patching `atomic_write.commit` places
    the deletion *after* `_assert_same_file`, so it would have characterized the
    residual race while appearing to test the guard. The guard test now wraps
    `atomic_write.prepare` (which runs strictly before the check); the `commit`
    variant is kept as an explicitly-labelled characterization of the known
    micro-race, and doubles as the negative control for the guard test.

## Why this shape (decided at parent planning, user-confirmed)

| Option | Why rejected / chosen |
|---|---|
| Extend `aitask_update.sh --boardcol` | Would re-implement `lib/board_ordering.py`'s gap arithmetic **in bash**, and the script is cwd-relative with no `--root`. Rejected. |
| Import `lib/board_columns.py` directly into minimonitor | Puts a task-file write on the TUI event loop and gives `monitor/` its first in-process file mutation. Rejected. |
| **New `lib/` module + thin `.sh` wrapper, called via subprocess** | Matches the one mutation `monitor/` already performs (`aitask_agent_marks.sh` via `_run_marks_cmd`). **Chosen.** |

## Steps

### Pre-phase (risk mitigations)

Both steps gate the work below and must pass before any de-dup or validation
edit lands.

1. `[characterize_work_report_columns]` Before touching
   `work_report_gather.load_columns()`, add a characterization test that pins the
   **current** behaviour of the report protocol's column surface:
   `aitask_work_report_gather.sh --list-columns` stdout (the exact
   `COLUMN:<id>|<title>` lines, board order, `unordered` prepended only when a
   task sits there), **exit code 3** on a column id containing `|`/CR/LF, and the
   literal `work_report_gather:` stderr message prefix. Run it green against the
   pre-change tree, then keep it green after the delegation — that is what proves
   the de-dup is behaviour-preserving rather than merely compiling. Include a
   negative control that mutates the expected prefix and confirms the test fails,
   so a vacuous pass is impossible.

2. `[audit_boardcol_callers]` Before making `--boardcol` validation fatal,
   enumerate **every** call site: `grep -rn -- '--boardcol'` across
   `.aitask-scripts/`, `.claude/`, `.agents/`, `.opencode/`, `seed/`, `website/`
   and `aidocs/`, plus the cross-repo flag list in `aitask_update.sh:261-263`.
   For each, record whether it can pass an id absent from `board_config.json`.
   If **none** can, ship the fatal `die`. If **any** can, stop and decide
   warn-vs-die with the user before proceeding — do not silently break a caller.
   Record the enumeration and the decision in the Final Implementation Notes.

### 1. `.aitask-scripts/lib/board_columns.py` (new)

```python
DEFAULT_COLUMNS, DEFAULT_ORDER            # moved out of the two copies
UNORDERED_ID = "unordered"                # moved from work_report_gather
UNORDERED_TITLE = "Unsorted / Inbox"
UNORDERED_COLOR = "gray"                  # matches aitask_board.py:6819
DEFAULT_TASK_DIR = "aitasks"
_PARENT_ID_RE = re.compile(r"^\d+$")
_CHILD_ID_RE  = re.compile(r"^\d+_\d+$")

class ColumnIdError(ValueError): ...      # '|', CR or LF in a configured id

@dataclass(frozen=True)
class ColumnRecord:
    id: str
    title: str
    color: str | None = None

def tasks_dir(root: Path, task_dir: str = DEFAULT_TASK_DIR) -> Path
def board_config_path(root: Path, task_dir: str = DEFAULT_TASK_DIR) -> Path
def column_records(root, *, task_dir=DEFAULT_TASK_DIR, include_unordered=False) -> list[ColumnRecord]
def load_columns(root, *, task_dir=DEFAULT_TASK_DIR) -> tuple[list[str], dict[str, str]]
def column_indices(root, col_id, exclude="", *, task_dir=DEFAULT_TASK_DIR) -> list[int]
def task_column(root, task_id, *, task_dir=DEFAULT_TASK_DIR) -> ColumnQuery
def move_task_to_column(root, task_id, col_id, *, task_dir=DEFAULT_TASK_DIR) -> MoveOutcome
```

**Root-scoping is a hard rule.** Every entry point takes an explicit `root`. Do
**not** call `config_utils.task_dir()` / `metadata_dir()` — they read `TASK_DIR`
/ cwd ambiently, and minimonitor's `target_root` may be a different project
entirely.

**Task-directory layout is an explicit parameter, and the default is enforced.**
`TASK_DIR` is an **env-only** override with no per-project source (every script
does `TASK_DIR="${TASK_DIR:-aitasks}"`; nothing reads it from
`project_config.yaml`), so a *foreign* root's layout is undiscoverable — silently
inheriting this process's `TASK_DIR` would be actively wrong for another project.
Hence the explicit `task_dir` parameter defaulting to `aitasks`, with the
same-root override available to callers that do know (`aitask_update.sh` passes
its own `$TASK_DIR`).

**`task_dir` must be contained by `root` — it is user-controlled input into a
mutation boundary.** `Path.__truediv__` **discards the left operand when the
right is absolute** (`Path("/proj") / "/etc"` → `/etc`), and a `../` value
traverses out, so an unchecked `--task-dir` defeats root-scoping entirely.
`tasks_dir()` validates before returning, refusing `unsafe_task_dir`:

1. non-empty, and **not absolute** (`Path(task_dir).is_absolute()` → refuse; also
   reject a Windows-style drive/UNC form defensively);
2. no `..` component, lexically;
3. and the belt-and-braces check: `(root / task_dir).resolve()` must be
   `root.resolve()` **or beneath it** (`Path.is_relative_to`). Resolve **both**
   sides — `root` may itself be a symlink.

Step 3 is deliberately resolve-based rather than lexical-only, and it must be
verified against the **branch-mode layout**, where `aitasks/` is a symlink to
`.aitask-data/aitasks` (see `tests/lib/board_fixture.py:_layout`). That target
resolves to a path still beneath `root`, so the legitimate production layout
passes — do not "fix" a test failure here by dropping the check.

**Enforce the layout too — do not degrade silently.** `load_layered_config`
returns the stock defaults for a *missing* file, so a wrong layout would
otherwise make `list-columns` print a confident `now/next/backlog` for a project
that has neither. After the containment check, every entry point asserts
`tasks_dir(root, task_dir)` is a directory and refuses `unsupported_layout`
(naming the path it tried) when it is not.

Imports allowed: `config_utils`, `task_yaml`, `board_ordering`, `atomic_write` —
all lib/ siblings, so a **flat `from x import y`** with no `sys.path` setup
(follow `work_report_gather.py:44-52`, which documents why). **Never**
`aitask_board`: `tests/test_no_lib_to_tui_import.sh` freezes that direction.

**Readers.** `column_records` is the rich reader; `load_columns` is a narrow view
over it that returns **exactly** today's shape — `(configured ids in board order,
{col_id: title})` with `titles` additionally carrying the synthetic `unordered`
entry that is *not* in `configured`. Preserve `work_report_gather`'s three
behaviours verbatim: `.get(key, default)` rather than `or default` (a board
deliberately configured with no columns must stay empty); drop a `column_order`
entry with no matching `columns` definition; raise on a `|`/CR/LF column id.
Unlike `TaskManager.load_metadata`, this reader **must never write**
`board_config.json` when it is absent.

**One task-resolution rule, shared by `task_column` and `move_task_to_column`.**
Minimonitor's pick-by-number accepts child ids, and a `--task` value arrives from
a CLI, so the id is untrusted input that reaches a **glob**. Resolve in this
order, refusing before any filesystem access:

1. `_PARENT_ID_RE` (`^\d+$`) matches → proceed. This is what makes glob
   metacharacters inert: `*`, `1*`, `../x`, `t42`, `42.5` and `""` can never
   reach `Path.glob`. Do **not** rely on quoting.
2. Else `_CHILD_ID_RE` (`^\d+_\d+$`) matches → refuse `not_a_parent_task`
   (children are not board cards).
3. Else → refuse `malformed_task_id`.
4. Glob `tasks_dir(...)/t<id>_*.md`. **Zero matches** → refuse `not_found`.
   **Two or more matches** → refuse `ambiguous_task_id` listing the matches, and
   write nothing: the write target is genuinely undecidable, and
   `aitask_query_files.sh cmd_resolve` silently emits a multi-line `TASK_FILE:`
   in this case, which is a bug to avoid rather than a precedent to copy.

**`ColumnQuery`** is `(col_id: str | None, filename: str | None, refused: tuple[tuple[str, str], ...])`
with an `ok` property. A resolved task with **no** `boardcol` reports
`UNORDERED_ID`, matching `aitask_board.py:357`.

**`column_indices` must match what the board actually renders.** Enumerate
`tasks_dir(...)/t*.md`, but apply the board's **eligibility rule** before
counting: skip a file whose frontmatter fails to parse and one whose metadata
keys are a subset of `BOARD_KEYS` — the phantom-stub probe at
`aitask_board.py:1097`, mirrored at `work_report_gather.py:191`. (An unparseable
file lands in the same branch: `Task.load()` sets `metadata = {}`, so
`not task.metadata` catches it.) Without this, an invisible file carrying the
destination `boardcol` and a large `boardidx` inflates the computed maximum and
the seam appends past a card the board does not draw. Then coerce every raw index
through `task_yaml.normalize_board_idx` (the single coercion point; negative
values are legal), exclude `exclude` by filename, and — for `UNORDERED_ID` —
count tasks whose `boardcol` is missing entirely, since that is what the board
renders there.

**`MoveOutcome`** is a frozen dataclass
`(moved: str | None, col_id, board_idx, refused: tuple[tuple[str, str], ...])`
with an `ok` property — a rich return naming which item failed and why, never a
bare bool. Reasons: `unsafe_task_dir`, `unsupported_layout`, `unknown_column`,
`malformed_task_id`, `not_a_parent_task`, `not_found`, `ambiguous_task_id`,
`vanished`. Note this is **finer-grained than the board**, whose
`_resolve_parents` conflates a child id and an unknown filename into one
`not_a_parent_task`.

`move_task_to_column` order of operations:

1. Assert the layout (`unsupported_layout`), then look `col_id` up in
   `load_columns(...)`'s `titles` — one lookup, which already admits
   `unordered`. Otherwise refuse `unknown_column`. *(This is the validation
   `aitask_update.sh --boardcol` never performed.)*
2. Resolve the task by the shared rule above.
3. `idx = board_ordering.index_for_append(column_indices(root, col_id, exclude=<filename>))`.
   Reuse the pure module — do not re-implement the arithmetic. The `exclude` is
   load-bearing: a card already holding the column maximum would otherwise get
   `self + STEP` and not actually move. Empty column ⇒ `STEP` (1024), not 0.
4. `parse_frontmatter` → set `boardcol` / `boardidx` → `serialize_frontmatter` →
   write (see the identity guard below).
5. Touch **only** `boardcol` and `boardidx`. Both are in `BOARD_LAYOUT_KEYS`, so
   this is a **layout write**: do **not** set `updated_at`. Never invent a key.

**The vanished-file guard (and its honest limit).** `atomic_write_text` →
`commit()` is an **unconditional `os.replace`**, so a task archived or deleted
between the parse and the write is silently **recreated** — the exact failure the
board avoids with `if not self.load(): return`. Use the declared-stable two-phase
API instead of the one-shot helper:

```python
def _assert_same_file(path, st_before):
    """Raise OSError unless `path` is still the file we parsed."""
    st_now = os.stat(path)                    # FileNotFoundError if deleted
    if (st_now.st_dev, st_now.st_ino) != (st_before.st_dev, st_before.st_ino):
        raise FileNotFoundError(path)         # replaced by a different file

st_before = os.stat(resolved)                 # taken at parse time
tmp = atomic_write.prepare(resolved, render)
try:
    _assert_same_file(resolved, st_before)    # immediately before the rename
    atomic_write.commit(tmp, resolved)
except OSError:
    atomic_write.discard(tmp)
    return MoveOutcome(refused=((task_id, "vanished"),))
```

State the limit in the docstring rather than over-promising: this is a
**best-effort TOCTOU narrowing, not a guarantee** — a deletion landing between
`_assert_same_file` and `commit`'s `os.replace` still recreates the file. The
promise is "does not recreate a file that was already gone when we checked", not
"never recreates a vanished file". Both halves of that sentence are tested (see
the two vanished-file rows below), so the limitation stays a documented
characterization rather than an untested claim.

**Document the atomicity boundary in the module docstring.** `atomic_write`
gives *reader-visible atomicity*, **not** writer serialization: two concurrent
read-modify-writes each render from the same old text and the second replace
discards the first. `Task.reload_and_save_board_fields` documents itself as
"best-effort, not atomic" for the same reason, so this **matches** the existing
seam rather than regressing it. Do not claim a lock this seam does not take.

### 2. De-duplicate, don't fork

`DEFAULT_COLUMNS` / `DEFAULT_ORDER` are **byte-identical** in `aitask_board.py:143-148`
and `work_report_gather.py:55-60` (the latter carries a comment declaring the
manual-sync obligation — exactly the drift hazard being removed). Move both here,
then:

- `work_report_gather.load_columns()` **delegates**, keeping its own
  `_die(..., EXIT_INFRA)` wrapper so the CLI's fail-closed protocol behaviour is
  unchanged — while the library path raises `ColumnIdError` instead of calling
  `sys.exit`. That difference is what makes the reader importable into a TUI.
  **`_die` hard-codes the prefix `work_report_gather:`** — keep that prefix by
  catching `ColumnIdError` in the delegate and re-emitting through the existing
  `_die`, so no user-visible message changes.
- `work_report_gather` re-imports `UNORDERED_ID` / `UNORDERED_TITLE` from here.
- `aitask_board.py` imports `DEFAULT_COLUMNS` / `DEFAULT_ORDER` / `UNORDERED_ID`
  back, following the existing mid-file idiom at `:435-448` — a comment naming
  the extracted module, the reason, the owning task id and the "board stays the
  semantic owner" clause, then `# noqa: E402`.
- Replace the bare `"unordered"` literal in `Task.board_col`
  (`aitask_board.py:357`) with `UNORDERED_ID`.

`tests/test_board_config_split.py:24-29` keeps its own literal copy **on
purpose** (independent ground truth) — leave it.

### 3. `.aitask-scripts/aitask_board_column.sh` (new)

```
list-columns    --root R [--task-dir D] [--include-unordered]
                           → COLUMN:<id>|<color>|<title>   (one per line)
current-column  --root R [--task-dir D] --task N
                           → CURRENT:<task_id>|<col_id>
move            --root R [--task-dir D] --task N --column C
                           → MOVED:<filename>|<col>|<idx>
                           → ERROR:<reason>                (non-zero exit)
```

`--task-dir` defaults to `aitasks`. `<reason>` is the `MoveOutcome` /
`ColumnQuery` reason verbatim, so `ERROR:ambiguous_task_id`,
`ERROR:malformed_task_id`, `ERROR:unsupported_layout` etc. are all
machine-checkable by t1377_2 rather than free prose.

**Title goes last because titles may contain `|`** (`work_report_gather._free_text`
deliberately lets `|` survive in the final field). Colour sits in the middle, so
the emitter must strip `|`/CR/LF from it — **sanitize at this write site**, since
the delimited encoding is undecidable on read. Colour is cosmetic, so a bad value
degrades to empty; a bad **id** stays fatal, as today.

`#!/usr/bin/env bash`, `set -euo pipefail`, resolve `SCRIPT_DIR` from
`BASH_SOURCE`, source `lib/aitask_path.sh` + `lib/python_resolve.sh` and `exec`
the module — modelled on `aitask_work_report_gather.sh`, which is itself
**deliberately not wired into the `ait` dispatcher**.

**The wrapper writes nothing itself** — it is a thin CLI over the Python module,
which owns every file write via `lib/atomic_write.py`. So it needs **no**
`lib/atomic_write.sh` sourcing and is out of scope for t1396's truncate-then-write
sweep. Keep it that way: a shell-side write here would make it a t1396 surface.
*(This supersedes the task file's Coordination bullet, which says to source
`atomic_write.sh` — that was written before the wrapper was scoped as
write-free.)*

Per `aidocs/framework/aitasks_extension_points.md`: **no `ait` dispatcher entry**
(the dispatcher is user-facing only; this is shelled out from a TUI) and **no
code-agent allowlist entries** in `.claude/settings.local.json` / `.codex/rules/`
/ the `seed/` mirrors — that checklist applies only to *skill-invoked* helpers.
Entries here would be dead weight advertising a skill-facing surface that does
not exist.

### 4. `aitask_update.sh --boardcol` validation

Today an unknown id silently produces a task that renders in **no** column — not
even `unordered`. Mirror the `--anchor` precedent exactly (`aitask_update.sh:2199-2221`):
a block in `main()` **after `parse_args`, before the batch/interactive dispatch**,
guarded by `[[ "$BATCH_BOARDCOL_SET" == true && -n "$BATCH_BOARDCOL" ]]` so that
`--boardcol ""` remains a clearing operation that skips validation. Add
`normalize_board_column()` to `lib/task_utils.sh` beside `normalize_anchor_id`,
following its shape: shape-assert → existence-probe via a sibling helper → echo
the canonical value, `die` otherwise, with an explicit `*)` arm for an unexpected
probe result. The error message names the valid ids.

**Probe `aitask_board_column.sh list-columns --root . --task-dir "$TASK_DIR" --include-unordered`,
not the work-report gatherer** — the gatherer's `--list-columns` scans and parses
every task file just to decide whether to prepend `unordered`, which is O(all
tasks) per `ait update` call. The new verb reads only `board_config.json`.
Passing `$TASK_DIR` through is what keeps validation correct for a repo using a
non-default layout: without it a `TASK_DIR`-overridden repo would validate
against stock defaults and reject its own real columns.

## Tests

`tests/test_board_columns_seam.py` — mirror `tests/test_board_manager_moves.py`
(patch module constants, no Textual Pilot) on `tests/lib/board_fixture.py`
(`build_fixture_tree` → `root/"tree"`, `snapshot` = sha256 per `*.md` +
`board_config*.json`, `diff_snapshots`). Note the fixture's columns are `c0…c4`,
not `now`/`next`/`backlog`.

| Case | Assertion |
|---|---|
| single move | index is strictly greater than the destination max |
| K sequential moves | indices distinct and ascending |
| empty destination | first move lands on `STEP` (1024), not 0 |
| move off the column max | the mover is excluded from its own append, so it actually moves |
| missing `boardcol` | counted as `unordered` by `column_indices` |
| **phantom stub in the destination** | a file whose metadata keys ⊆ `BOARD_KEYS`, carrying the destination `boardcol` and a huge `boardidx`, is **ignored** — the append index is computed as if it were absent |
| **unparseable file in the destination** | same, via `t_unparseable.md` (already in `DEFAULT_TOPOLOGY`) |
| **malformed task id** | `*`, `1*`, `../etc`, `t42`, `42.5`, `""` each refuse `malformed_task_id` — asserted **before** any file exists that a glob could match, plus a positive control proving a real `*` in the tasks dir is never expanded |
| **ambiguous task id** | two files `t9100_a.md` / `t9100_b.md` refuse `ambiguous_task_id` and write nothing |
| **unsupported layout** | a root with no `aitasks/` refuses `unsupported_layout` rather than reporting the stock `now/next/backlog` defaults |
| **custom `task_dir`** | a tree laid out under `mytasks/` is read and written correctly when `task_dir="mytasks"` is passed |
| **`task_dir` containment** | `/etc`, `../sibling`, `a/../../b`, `""` each refuse `unsafe_task_dir`. Include the **positive control that motivates the check**: assert `root / "/etc"` really is `/etc` in pathlib, so the test documents *why* absolute is rejected. Plus a control that the branch-mode `aitasks → .aitask-data/aitasks` symlink **passes** |
| **vanished task file (guard fires)** | wrap `atomic_write.prepare` so it calls through and **then** unlinks the destination — that places the deletion strictly between the parse-time `stat` and `_assert_same_file`. Assert `refused == (("<id>", "vanished"),)`, the file is **not** recreated, and the staged temp is gone (no `.tmp` left in the dir) |
| **vanished task file (documented residual race)** | wrap `atomic_write.commit` to unlink first — deletion lands *after* the guard, so `os.replace` **does** recreate the file. Assert exactly that, named as the known limit. This is a characterization test: it pins the docstring's honesty, and it is the negative control proving the row above is not vacuous (patching the wrong seam gives the opposite outcome) |
| unknown column / child id / missing task | `refused` names it **and** `diff_snapshots` is `{changed:set(), added:set(), removed:set()}` — nothing written |
| layout-write discipline | `updated_at` unchanged, **plus a negative control** naming a non-layout key that *does* stamp it (proves the assertion discriminates) |
| headless guard | module source has no `import textual` / `from textual` / `import aitask_board` — mirrors `SeamGuardTests.test_board_ordering_is_headless` |
| de-dup guard | the moved symbols are **gone** from `aitask_board.py` / `work_report_gather.py` source and imported instead (mirrors `test_board_imports_board_ordering`) |
| drift guard | `work_report_gather.load_columns()` (chdir into the tree, `TASK_DIR` unset) and `board_columns.load_columns(root)` agree — proving the de-dup is real, not two implementations that agree today |
| root-scoping | a move against a second fixture root writes **only** in that root |
| colour sanitation | a `\|` planted in a colour is stripped on emit; the record still parses into 3 fields |

`tests/test_board_column_cli.sh` — follow the house harness (`set -uo pipefail`,
`SCRIPT_DIR`/`PROJECT_DIR` from `BASH_SOURCE`, source `tests/lib/asserts.sh`,
`PASS`/`FAIL`/`TOTAL`, `mktemp -d` + `trap … EXIT`, `Results:` footer). Cover all
three subcommands, the `ERROR:` line, non-zero exit on a bad column, a title
containing `|` splitting correctly on the **first two** delimiters, `--root`
pointing at a non-cwd tree, `--task-dir` against a non-default layout, and the
**same four identifier cases as the Python suite** — malformed (including
`--task '*'`, which must not expand), ambiguous (two matching files), child, and
missing — each asserting a non-zero exit and an unchanged tree.

Also assert `--task-dir` containment **at the CLI**, not only in the Python API:
`--task-dir /etc` and `--task-dir ../sibling` must each print
`ERROR:unsafe_task_dir`, exit non-zero, and leave a canary file planted outside
`--root` untouched. The shell layer is where an operator or a TUI actually
supplies this value, so a Python-only test would not cover the real entry point.

Plus an `aitask_update.sh --boardcol` rejection test, and a `--boardcol ""`
test proving clearing still works.

`tests/test_board_persistence_seam.py`'s AST-parsed `EXPECTED_CALL_SITES` must
stay green **unedited**: this child adds no `reload_and_save_board_fields` call
site and moves none out of the board. (That table is sorted by line number, so it
encodes source *order* — the constant/import edits here must not reorder any
existing call site.)

## Verification

```bash
shellcheck .aitask-scripts/aitask_board_column.sh .aitask-scripts/aitask_update.sh
bash tests/test_board_column_cli.sh
bash tests/test_no_lib_to_tui_import.sh
bash tests/run_all_python_tests.sh    # read ONLY the last line for the verdict
```

Plus a **read-only** live check against the real repo: `list-columns --root .`
must reproduce the seven columns in `aitasks/metadata/board_config.json`, and
`current-column --root . --task 1377` must report this task's actual column.

**No live move.** All mutation coverage stays in fixtures — a smoke move against
the shared checkout would dirty it or alter a real user task, and this repo is
worked on concurrently. Finish with `git status --porcelain` to confirm the
verification run left nothing behind.

## Coordination

All previously-named blockers have **landed and archived**: t1243_5, t1243_6,
t1243_7 (`8b0e63a3e`), t1369 (`a3f0494a3`), t1371 (`7c8eb061e`) and t1379
(`a75127829`). There is no in-flight edit of `aitask_board.py` to race, and
`lib/atomic_write.{py,sh}` are committed and tracked.

Still open, and both only same-file rebases:

- **`t1243_8_boardgroup_field_and_model`** (Ready) appends `"boardgroup"` to
  `BOARD_KEYS`, which flows into `work_report_gather`'s empty-metadata probe.
  This child edits `load_columns()` and the column constants — different
  functions, and the writer here names `("boardcol", "boardidx")` explicitly, so
  `BOARD_KEYS` growth cannot reach it.
- **`t1396_fix_remaining_shell_temp_write_defects`** (Ready) sweeps shell
  truncate-then-write defects. The wrapper is write-free by design, so it adds no
  surface.

Shared checkout hygiene: grep for symbols rather than trusting line numbers,
stage explicit paths, check `git diff --cached` before committing, and never
`git stash` / `git add -A`.

## Risk

### Code-health risk: medium

- The de-dup rewires `work_report_gather.load_columns()`, a **fail-closed
  protocol path** consumed by `/aitask-work-report`; if `ColumnIdError` escapes
  as a traceback instead of the existing `_die(..., EXIT_INFRA)` exit 3, or the
  `work_report_gather:` message prefix changes, the report protocol breaks for
  callers that parse it · severity: low (residual — a regression is now caught
  before landing by inline pre-phase characterize_work_report_columns; the
  rewiring itself still ships) · → mitigation: inline pre-phase
  characterize_work_report_columns
- Adding validation to `aitask_update.sh --boardcol` is a **contract change**: a
  previously-accepted unconfigured id now aborts the command. `--boardcol` is on
  the documented cross-repo flag list, so an existing caller could start failing
  · severity: medium (residual — inline pre-phase audit_boardcol_callers
  *discovers* an affected caller and forces a warn-vs-die decision, but the
  contract change still ships) · → mitigation: inline pre-phase
  audit_boardcol_callers
- Replacing the bare `"unordered"` literal in `Task.board_col`
  (`aitask_board.py:357`) touches a property read by every board render path; a
  bad import ordering there fails the whole TUI at startup · severity: low ·
  → mitigation: none
- The same unvalidated-column hole remains in the board's own
  `TaskManager.move_tasks_to_column`, so the framework would be left with two
  different validation stances for one field · severity: low ·
  → mitigation: t1431

### Goal-achievement risk: low

- The seam's shape is consumed by two future siblings; if `MoveOutcome` /
  `ColumnQuery` are wrong, t1377_2 must reopen it. Reduced this pass by verifying
  the surface directly against p1377_2's stated needs (colour swatch,
  current-column marking), which is what added those two capabilities ·
  severity: low · → mitigation: none

### Planned mitigations

- timing: pre-phase | name: characterize_work_report_columns | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the work_report_gather delegation could silently break the fail-closed report protocol | desc: Characterization test pinning --list-columns stdout, exit 3 on a record-breaking id and the work_report_gather: message prefix, with a negative control, run green before and after the de-dup.
- timing: pre-phase | name: audit_boardcol_callers | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — making --boardcol validation fatal is a contract change that could break an existing caller | desc: Enumerate every --boardcol call site across scripts, agent trees, seed, docs and the cross-repo flag list; ship the fatal die only if none can pass an unconfigured id, else decide warn-vs-die with the user first.
- timing: after | name: board_move_column_validation | type: bug | priority: medium | effort: medium | inline_risk: low | added_complexity: medium | addresses: code-health — the board's own move path keeps the unvalidated-column hole this task closes in the CLI | desc: Validate new_col in TaskManager.move_task_to_column / move_tasks_to_column against the shared board_columns vocabulary, refusing unknown_column through the existing MoveResult, so board and CLI hold one stance. | created: t1431

**Post-inline reassessment (one pass).** With both pre-phases inlined, the
code-health level stays **medium**: the characterization test and the caller
audit reduce the chance of an *undetected* regression, but the delegation rewire
and the CLI contract change both still ship, and the blast radius across
`aitask_board.py` / `work_report_gather.py` / `aitask_update.sh` is unchanged.
Goal-achievement stays **low**. No new risks are introduced by the inline phases
themselves.

## Final Implementation Notes

- **Actual work done:** Both inline pre-phases ran first and gated the rest.
  `characterize_work_report_columns` landed as
  `tests/test_work_report_columns_characterization.py` (11 assertions pinning
  `--list-columns` stdout, board order, the conditional `unordered` prepend,
  exit 3 on a record-breaking id, and the `work_report_gather:` stderr prefix);
  it was green **before** the de-dup and stayed green after, which is what proves
  the delegation is behaviour-preserving. `audit_boardcol_callers` enumerated
  every `--boardcol` site (below). Then: new `lib/board_columns.py` (readers,
  `column_indices`, `task_column`, `move_task_to_column`, CLI `main()`), new
  `aitask_board_column.sh` shim, the vocabulary de-dup across
  `aitask_board.py` + `work_report_gather.py`, and `--boardcol` validation via a
  new `normalize_board_column()` in `lib/task_utils.sh`.
- **`audit_boardcol_callers` result (pre-phase 2, required record):** five hits
  total — `aitask_update.sh:226` (help text), `:262` (cross-repo flag list doc),
  `:350` (the parse arm), `tests/test_update_cross_repo.sh:121`, and
  `website/content/docs/commands/task-management.md:182` (doc table). **No
  framework code, skill, seed config or agent tree invokes `--boardcol`** — the
  board mutates the field in-process via `reload_and_save_board_fields`. The
  cross-repo test is unaffected because the `--project` redirect `exec`s at the
  **top of `main()`**, before `parse_args` and therefore before the validation
  block, so a cross-repo update validates against the **target** project's
  `board_config.json`. **Decision: ship the fatal `die`.**
- **Deviations from plan:**
  - The plan said the wrapper emits `COLUMN:<id>|<colour>|<title>` and that the
    emitter "must strip `|`/CR/LF" — applied literally that would have stripped
    `|` from **titles** too, corrupting them and defeating the whole reason
    title is the last field. Split into `_line_safe` (last field: CR/LF only,
    matching `work_report_gather._free_text`) and `_field_safe` (middle fields:
    also `|`). Caught by `tests/test_board_column_cli.sh` Test 1.
  - Added `ColumnQuery.filename` (not in the plan's sketch) so a caller that
    already asked for the current column need not re-resolve the file.
  - `DEFAULT_TASK_DIR` / `_PARENT_ID_RE` / `_CHILD_ID_RE` / `UNORDERED_COLOR`
    added as named constants rather than inline literals.
  - Kept `_has_record_breaking` private to `board_columns.py` instead of sharing
    `work_report_gather`'s copy: that predicate is also used there for bucket ids
    and free-text parts, so folding it in would have widened the approved de-dup
    scope. Noted as a candidate follow-up rather than taken silently.
- **Issues encountered:**
  - Two repo structural guards failed on the **new tests**, both correctly:
    `test_board_fixture_harness.LiveTreeSweepTests` rejected the `os.chdir` used
    to exercise the ambient reader, and
    `test_collection_structure.NoInheritedTestDuplicationTests` rejected
    `UnorderedPopulatedTests(UnorderedRowTests)`. Fixed **structurally** rather
    than allowlisted: the chdir became an absolute `TASK_DIR` (cwd untouched,
    which also makes it safe under `-n` parallelism), and the inheriting class
    became a sibling of `_GatherCase` with distinct, non-inverted test names.
  - `--task ''` originally hit argparse's "flag omitted" branch and reported a
    usage error instead of `malformed_task_id`. Now `is None` means omitted
    (usage) and `""` falls through to the seam (malformed) — the two are
    genuinely different errors.
  - Plan review flagged a stale `load_layered_config` import in
    `work_report_gather.py`. Confirmed dead, and a pyflakes sweep found **three
    more of the same defect that I had introduced**: `DEFAULT_COLUMNS`,
    `DEFAULT_ORDER` and `UNORDERED_TITLE` re-exported under a
    `# noqa: F401 - re-exported for existing importers` comment, when a grep
    showed **no such importers exist**. All four removed. The repo has no Python
    lint step, so nothing would have caught these automatically.
- **Key decisions:**
  - `task_dir` is an explicit parameter, not an ambient `TASK_DIR` read, because
    `TASK_DIR` is env-only with no per-project source — a foreign root's layout
    is undiscoverable, so inheriting this process's value would be actively
    wrong for another project. It is validated for containment (not absolute, no
    `..`, resolved-path under a resolved `root`), since `Path("/p") / "/etc"`
    is `/etc` and `task_dir` reaches the module from a CLI.
  - A missing layout is **refused** (`unsupported_layout`) rather than degraded:
    `load_layered_config` returns stock defaults for a missing file, so silence
    would report a confident `now/next/backlog` board for a project with none.
  - The vanished-file guard uses `prepare` → identity re-check → `commit` instead
    of the one-shot `atomic_write_text`, because `commit` is an unconditional
    `os.replace` that would recreate a deleted task. The docstring states the
    residual race honestly, and **both halves are tested** — one test proves the
    guard fires, its sibling characterizes the race that remains.
  - Every enforcement point carries a negative control proving it discriminates
    (parity filter, parse guard, id regex, vanished guard, `--boardcol`
    validation, and the characterization prefix). The parity and parse guards
    needed **separate** controls: disabling `_eligible` does not move the
    unparseable case, because that file is stopped earlier by the parse guard.
- **Upstream defects identified:**
  - `aitask_query_files.sh:402-407 — cmd_resolve emits a multi-line
    "TASK_FILE:<paths>" when a task number matches two or more files, instead of
    refusing an ambiguous id; a caller parsing one line silently gets a
    two-line value.` (`board_columns._resolve_task` deliberately refuses
    `ambiguous_task_id` rather than copying this shape.) Note the other
    adjacent gap — `TaskManager.move_task_to_column` / `move_tasks_to_column`
    never validate `new_col` — is **already assigned** to the confirmed
    `board_move_column_validation` "after" mitigation created at Step 8d, so it
    is not repeated here as a new follow-up candidate.
- **Notes for sibling tasks:**
  - **Module API** (`.aitask-scripts/lib/board_columns.py`, import flat from
    `lib/`): `column_records(root, *, task_dir, include_unordered) ->
    list[ColumnRecord(id, title, color)]`;
    `load_columns(root, *, task_dir) -> (configured_ids, titles)` where
    `titles` **also** carries `unordered` but `configured_ids` does not — that
    asymmetry is what makes `col_id in titles` the single "is this a legal move
    target" test; `column_indices(root, col_id, exclude="", *, task_dir)`;
    `task_column(root, task_id, *, task_dir) -> ColumnQuery(col_id, filename,
    refused)`; `move_task_to_column(root, task_id, col_id, *, task_dir) ->
    MoveOutcome(moved, col_id, board_idx, refused)`. Both outcome types expose
    `.ok`. Path helpers: `tasks_dir(root, task_dir)`,
    `board_config_path(root, task_dir)`. Config-path variants for ambient
    callers: `column_records_at(path, *, include_unordered)`,
    `load_columns_at(path)`. Errors: `BoardColumnsError` base with a `.reason`,
    subclasses `ColumnIdError`, `UnsafeTaskDirError`, `UnsupportedLayoutError`.
  - **Wrapper protocol** (`aitask_board_column.sh`, exit 0 / 1 refused / 2
    usage):
    `list-columns --root R [--task-dir D] [--include-unordered]` →
    `COLUMN:<id>|<colour>|<title>`;
    `current-column --root R [--task-dir D] --task N` → `CURRENT:<task_id>|<col_id>`;
    `move --root R [--task-dir D] --task N --column C` →
    `MOVED:<filename>|<col_id>|<board_idx>`; refusals → `ERROR:<reason>`.
  - **For t1377_2:** parse `COLUMN:` by splitting on the **first two** `|` only —
    the title is last precisely because titles may contain a pipe (this repo's
    own board has none today, but the fixture does). Colour may be empty. Branch
    on the stable reason tokens (`unknown_column`, `malformed_task_id`,
    `not_a_parent_task`, `not_found`, `ambiguous_task_id`, `unsafe_task_dir`,
    `unsupported_layout`, `vanished`), not on prose. `current-column` applies the
    **same** id rule as `move`, so a child id is refused identically by both —
    surface that refusal before opening the picker. Pass minimonitor's
    `target_root` as `--root`; leave `--task-dir` alone unless you know the
    foreign project's layout.
  - **For t1377_3:** extend this module additively —
    `generate_col_id`, `PALETTE_COLORS`, `create_column`, and a `create`
    wrapper verb. `UNORDERED_COLOR` ("gray") already exists here. Note the
    module currently reads config only; `create_column` introduces the first
    `board_config.json` **write**, so it must do the
    `load_layered_config` → mutate → `split_config` → **project layer only**
    dance described in p1377_3, and the layout/containment guards
    (`_require_tree`) already give it a safe root to write into.
