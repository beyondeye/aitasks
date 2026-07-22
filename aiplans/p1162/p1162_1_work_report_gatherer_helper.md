---
Task: t1162_1_work_report_gatherer_helper.md
Parent Task: aitasks/t1162_add_manager_facing_work_report_skill_and_board_flow.md
Sibling Tasks: aitasks/t1162/t1162_2_work_report_codeagent_operation.md, aitasks/t1162/t1162_3_work_report_skill_and_wrappers.md, aitasks/t1162/t1162_4_board_w_work_report_flow.md, aitasks/t1162/t1162_5_work_report_documentation.md
Archived Sibling Plans: aiplans/archived/p1162/p1162_*_*.md
Worktree: aiwork/t1162_1_work_report_gatherer_helper
Branch: aitask/t1162_1_work_report_gatherer_helper
Base branch: main
---

# Plan: t1162_1 — Work-report gatherer helper + unit tests

## Context

Deterministic report-input layer for the t1162 work-report feature. Consumed
by the `/aitask-work-report` skill (t1162_3, interactive + arg paths) and the
board `w` flow (t1162_4, which passes `--columns`/`--tasks` args). The full
parent design lives in
`aiplans/p1162_add_manager_facing_work_report_skill_and_board_flow.md`
(t1162_1 section) — the contracts below are PINNED there and re-inlined here
so this plan is self-contained.

## Files

1. **`.aitask-scripts/aitask_work_report_gather.sh`** (new) — thin bash entry:
   `#!/usr/bin/env bash`, `set -euo pipefail`, resolve script dir, source
   `lib/python_resolve.sh`, `PYTHON="$(require_ait_python)"`, then
   `exec "$PYTHON" "$SCRIPT_DIR/lib/work_report_gather.py" "$@"`.
   Model: `.aitask-scripts/aitask_stats.sh` (same thin-exec shape).
2. **`.aitask-scripts/lib/work_report_gather.py`** (new) — implementation.
3. **`tests/test_work_report_gather.sh`** (new) — unit tests.

Read `aidocs/framework/shell_conventions.md` before writing the `.sh` file.

## PINNED output contract

Exit 0 for ALL validation outcomes (status via lines, like
`aitask_query_files.sh`). Nonzero exit only for genuine infrastructure/usage
errors (unreadable board config, bad flag).

```
COLUMN:<col_id>|<title>
TASK:<col_id>|<task_id>|<boardidx>|<status>|<priority>|<effort>|<pending_children>|<remaining_items>|<task_file_path>
VELOCITY:<window_days>|<completed_count>|<avg_per_day>
ERROR:unknown_column:<id>
ERROR:unknown_task:<id>
ERROR:task_not_in_selected_columns:<id>
ERROR:task_order_changed:<canonical_csv>
NO_TASKS
```

Rules (all PINNED — see parent plan):

- **One free-text field per record, always LAST** (`<title>` in `COLUMN:`,
  `<task_file_path>` in `TASK:`). Consumers split on `|` with
  `maxsplit = <fixed field count>`; no escaping engine. All other fields are
  pipe-free by construction (ids, enums, ints, floats).
- **Fail-closed:** if ANY validation error exists, emit ONLY `ERROR:` lines
  (all of them) — never partial `COLUMN:`/`TASK:` output.
- **`NO_TASKS`**: valid selection that yields zero tasks (e.g. all requested
  columns empty, or `--tasks` empty after dedup — decide and pin in tests).
- **CLI:**
  - `--list-columns` — enumeration mode: only `COLUMN:` lines; `unordered`
    first **iff it currently has ≥1 task**, then `column_order` left-to-right.
  - `--columns <csv>` (required otherwise), `--tasks <csv>` (optional subset).
  - `t` prefix normalization (`t42` ≡ `42`); duplicates deduped preserving
    first occurrence.
- **`--tasks` order is significant:** carries the board-reviewed sequence.
  After membership validation passes, compare the (post-dedup) given sequence
  with the canonical order (selected columns in board order, ascending
  `boardidx` within column, restricted to the given tasks). On mismatch emit
  `ERROR:task_order_changed:<canonical_csv>` (canonical csv = bare ids in
  canonical order) — fail-closed like all errors.
- **Fields:**
  - `pending_children` = `len(children_to_implement)` if the key exists, else 0.
  - `remaining_items` (decoupled from membership): key `children_to_implement`
    present → `len(...)` (so `[]` → 0); leaf → 0 if `status: Done` else 1.
- **Membership (must match board `TaskManager.get_column_tasks`)**: top-level
  `aitasks/t*.md` only (no `aitasks/archived/`, no `aitasks/t<N>/` children,
  skip `aitasks/metadata/`, `aitasks/new/`); **phantom stubs excluded** —
  mirror `_is_phantom_stub` (`.aitask-scripts/board/aitask_board.py:539-541`):
  metadata empty or keys ⊆ `{"boardcol", "boardidx"}`
  (`BOARD_KEYS`, `.aitask-scripts/board/task_yaml.py:44`); **no status
  filter**; `boardcol` default `"unordered"`; `boardidx` default `0`;
  tie-break: read `TaskManager.load_tasks` (`aitask_board.py:543`) and
  reproduce its ordering — the board stable-sorts `get_column_tasks` by
  `board_idx` over load order (glob order); pin the exact rule you implement
  (recommended: stable sort by `(boardidx, task_id)` ONLY if that matches the
  board; otherwise mirror glob order — the t1162_4 equivalence test is the
  oracle, note the chosen rule in Final Implementation Notes for t1162_4).
- **Ordering:** requested columns in `column_order` order; `unordered` is a
  valid requested id and, when it has tasks, is emitted FIRST (matches board
  pickers prepending it at index 0).
- **Velocity:** two lines per successful gather (windows 7 and 30):
  completions = archived tasks (parents AND children) with `completed_at`
  within the window ending at "now". Reuse the stats collection seam —
  **import from `.aitask-scripts/stats/stats_data.py`** (the archived-scan
  collection that populates `daily_counts` from `completed_at`, around
  `stats_data.py:992-1091`); do NOT parse `aitask_stats.sh` text output, do
  NOT write a parallel archive scan. `avg_per_day = round(count / window, 2)`.
  Zero history → `VELOCITY:<w>|0|0`.
- **Frozen-now seam:** accept `--now <YYYY-MM-DD[ HH:MM]>` (or env
  `WORK_REPORT_NOW`) used ONLY by tests for deterministic velocity windows;
  default = current date.

## Implementation steps

1. Bash entry script (above). `chmod +x`.
2. `work_report_gather.py`:
   - Read board config via `lib/config_utils.load_layered_config("aitasks/metadata/board_config.json", defaults=...)`
     with the board's `DEFAULT_COLUMNS`/`DEFAULT_ORDER` semantics
     (`aitask_board.py:134-139`) as defaults. Honor the dir-override env vars
     used by tests (config_utils reads relative paths — run with `cwd` set by
     the test tree, and honor `TASK_DIR` if `config_utils`/globbing needs it;
     match how existing Python helpers resolve `aitasks/` — check
     `config_utils.task_dir()`).
   - Frontmatter parse: minimal YAML frontmatter reader for the needed keys
     (`boardcol`, `boardidx`, `status`, `priority`, `effort`,
     `children_to_implement`); reuse an existing lib parser if one fits
     (check `lib/` before writing a new one; the board's `task_yaml.py`
     is board-internal — prefer a `lib/`-level reuse or a small local parser).
   - Validation pipeline: parse csvs → normalize/dedup → resolve columns
     (unknown → error) → build membership → resolve tasks (unknown → error;
     present but in a non-selected column → `task_not_in_selected_columns`) →
     order check (`task_order_changed`) → emit.
   - Emission order: `COLUMN:` lines (selected, ordered), `TASK:` lines
     (grouped by column in that order), `VELOCITY:` lines last.
3. Tests (`tests/test_work_report_gather.sh`, model
   `tests/test_query_files_inflight.sh`): isolated tree via `mktemp -d`,
   write `aitasks/metadata/board_config.json` fixture + task files, run the
   helper with `cd`/env pointing at the tree. Cover (one assert-block each):
   - ordering across 2+ columns; ascending `boardidx`; tie-break stability
   - subset `--tasks`; `t`-prefix normalization; duplicate dedup
   - unknown column / unknown task / moved task → exact `ERROR:` lines and
     absence of `COLUMN:`/`TASK:` lines (fail-closed)
   - reorder: `--tasks` in non-canonical order → `ERROR:task_order_changed:<canonical>`
   - `--list-columns` with and without Unsorted tasks; `unordered` requested
     explicitly
   - protocol round-trip: column title containing `|` and a task path
     containing `|` (create a fixture dir with a pipe in the name) parsed
     intact by a maxsplit-style consumer in the test
   - remaining-work semantics: Done leaf → 0; parent `children_to_implement: []`
     → 0; parent with 3 pending → 3; active leaf → 1
   - phantom stub (boardcol/boardidx-only frontmatter) excluded
   - velocity: archived fixtures with `completed_at` inside/outside 7/30-day
     windows under `--now`; zero-history → `VELOCITY:7|0|0` + `VELOCITY:30|0|0`
   - empty selections → `NO_TASKS`
4. `shellcheck .aitask-scripts/aitask_work_report_gather.sh`.

## Verification

- `bash tests/test_work_report_gather.sh` — all PASS.
- `shellcheck` clean.
- Whitelisting of the helper is t1162_2's job (do not do it here).

## Step 9 reference

Post-implementation: merge/cleanup + archival per task-workflow Step 9
(Post-Implementation).
