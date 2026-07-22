---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [reporting]
gates: [risk_evaluated]
anchor: 1162
created_at: 2026-07-22 10:45
updated_at: 2026-07-22 10:45
---

## Context

First child of t1162 (manager-facing work-report skill and board flow). Builds the deterministic report-input layer: a whitelisted internal helper that reads board configuration and active parent tasks and emits structured, validated, ordered data for the `/aitask-work-report` skill (t1162_3) and the board `w` flow (t1162_4). Parent plan: `aiplans/p1162_add_manager_facing_work_report_skill_and_board_flow.md` (see the t1162_1 section for the full PINNED contracts).

## Key Files to Create

- `.aitask-scripts/aitask_work_report_gather.sh` — thin bash entry (`#!/usr/bin/env bash`, `set -euo pipefail`), sources `lib/python_resolve.sh`, delegates to the Python module.
- `.aitask-scripts/lib/work_report_gather.py` — implementation: board config via `lib/config_utils.load_layered_config` (canonical layered-read seam), parent task frontmatter parsing, velocity via the stats collection seam (`.aitask-scripts/stats/stats_data.py` — import, do NOT parse `aitask_stats.sh` text output, do NOT reimplement the archive scan).
- `tests/test_work_report_gather.sh` — unit tests (isolated tree via `mktemp -d` + exported dir vars; model: `tests/test_query_files_inflight.sh`).

## PINNED output contract (exit 0 for all validation outcomes)

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

- Parsing rule: each record has exactly ONE free-text field, always LAST (title in COLUMN, path in TASK); consumers split on `|` with maxsplit — no escaping engine. All other fields pipe-free by construction.
- Fail-closed: any `ERROR:` line means no `COLUMN:`/`TASK:` lines are emitted; ALL errors are listed.
- CLI: `--list-columns` (enumeration mode: only COLUMN lines — `unordered` first when it currently has tasks, then `column_order` left-to-right); otherwise `--columns <csv>` required, `--tasks <csv>` optional. `t` prefixes normalized; duplicates deduped.
- `--tasks` order is SIGNIFICANT: it carries the board-reviewed sequence; after validation compare (post-dedup) with the current canonical order restricted to those tasks; mismatch → `ERROR:task_order_changed:<canonical_csv>`.
- `pending_children` = len(children_to_implement) (0 for leaf).
- `remaining_items` (decoupled from membership): task with a `children_to_implement` key → len(list) (`[]` → 0); leaf → 0 if status Done else 1.
- Membership (must match board `TaskManager.get_column_tasks` — equivalence test in t1162_4 is the oracle): top-level `aitasks/t*.md` only (no archived, no children); phantom stubs excluded (mirror `_is_phantom_stub`, `.aitask-scripts/board/aitask_board.py:539-541`: metadata empty or keys ⊆ `BOARD_KEYS = ("boardcol","boardidx")` from `board/task_yaml.py:44`); NO status filtering; `boardcol` default `"unordered"`; `boardidx` default `0`; tie-break must reproduce the board's stable-sort order (read `TaskManager.load_tasks` and pin the exact rule).
- Ordering: requested columns in board `column_order` left-to-right; `unordered` requestable, prepended when it has tasks; within column ascending `boardidx`.
- VELOCITY lines (windows 7 and 30) on every successful gather: completions from archived `completed_at` (includes archived children — same unit as remaining_items); avg rounded to 2 decimals; zero history → `VELOCITY:<w>|0|0`. Provide a frozen-"now" seam (env var or arg) for deterministic tests.
- Internal helper only — no new `ait` subcommand.

## Verification

`bash tests/test_work_report_gather.sh` covering: ordering, multi-column grouping, subsets, `t` prefixes, invalid/moved/missing tasks, Unsorted dynamics, duplicates, empty selections; stale-selection (archived/deleted → unknown_task; moved → task_not_in_selected_columns; reordered → task_order_changed); `--list-columns` with/without Unsorted tasks; protocol round-trips (pipe-bearing title and path); remaining-work semantics (Done leaf → 0, `[]` parent → 0, pending parent → count, active leaf → 1); phantom-stub exclusion; velocity windows with frozen now + zero history. Also `shellcheck .aitask-scripts/aitask_work_report_gather.sh`.
