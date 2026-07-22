---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [reporting]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1217]
assigned_to: dario-e@beyond-eye.com
anchor: 1162
implemented_with: claudecode/opus4_8
created_at: 2026-07-22 10:45
updated_at: 2026-07-22 16:21
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
VELOCITY_MODEL:<model_id>|<window_days>|<start_date>|<end_date>|<model_label>
VELOCITY:<bucket_id>|<observed_units>|<completed_count>|<avg_per_unit>|<bucket_label>
PROJECTION:<remaining_total>|<projected_date>|<days_ahead>|<basis_completions>|<caveat>
PROJECTION:<remaining_total>|none|insufficient_data|<basis_completions>|<caveat>
ERROR:unknown_column:<id>
ERROR:unknown_task:<id>
ERROR:task_not_in_selected_columns:<id>
ERROR:task_order_changed:<canonical_csv>
NO_TASKS
```

- Parsing rule: each record has at most ONE free-text field, always LAST (title in COLUMN, path in TASK, model_label in VELOCITY_MODEL, bucket_label in VELOCITY; PROJECTION has none); consumers split on `|` with maxsplit — no escaping engine.
- Fixed fields are pipe-free by ENFORCEMENT, not assumption (`col_id` comes from editable board JSON, `status`/`priority`/`effort` from editable YAML): `|`/CR/LF in a `--columns`/`--tasks` arg → usage error (nonzero); in a `col_id` → infrastructure error (nonzero + stderr); in `status`/`priority`/`effort` → value coerced to the literal `invalid`; in the free-text last field `|` is legal but CR/LF collapse to a space.
- `children_to_implement` type policy: list → len; bare `children_to_implement:` (None) → 0; any other type (str/int/mapping) → key ignored, task falls back to the leaf rule, warning on stderr.
- Fail-closed: any `ERROR:` line means no `COLUMN:`/`TASK:` lines are emitted; ALL errors are listed.
- CLI: `--list-columns` (enumeration mode: only COLUMN lines — `unordered` first when it currently has tasks, then `column_order` left-to-right); otherwise `--columns <csv>` required, `--tasks <csv>` optional. `t` prefixes normalized; duplicates deduped.
- `--tasks` order is SIGNIFICANT: it carries the board-reviewed sequence; after validation compare (post-dedup) with the current canonical order restricted to those tasks; mismatch → `ERROR:task_order_changed:<canonical_csv>`.
- `pending_children` = len(children_to_implement) (0 for leaf).
- `remaining_items` (decoupled from membership): task with a `children_to_implement` key → len(list) (`[]` → 0); leaf → 0 if status Done else 1.
- Membership (must match board `TaskManager.get_column_tasks`): top-level `aitasks/t*.md` only (no archived, no children); phantom stubs excluded by REUSING the board's own `parse_frontmatter` + `BOARD_KEYS` from `board/task_yaml.py` rather than mirroring them; NO status filtering; `boardcol` default `"unordered"`; `boardidx` default `0`. Equivalence is asserted **in this task** against `TaskManager.get_column_tasks` (importable headlessly); t1162_4's test remains the higher-level board-flow oracle.
- Ordering key: `(normalize_board_idx(boardidx), filename)`, shared by the board and the gatherer via one implementation in `board/task_yaml.py`. Sorting the raw value was unsafe twice over — a quoted `boardidx: "10"` sorted lexically before `"2"`, and a quoted/int mix raised `TypeError` and crashed the board — and stable-sorting on the index alone left ties in directory-enumeration order (verified: two tasks at `boardidx: 10` returned reverse-alphabetically), which is not durable across processes and would spuriously trip `ERROR:task_order_changed`. This task owns both halves.
- Ordering: requested columns in board `column_order` left-to-right; `unordered` requestable, prepended when it has tasks; within column ascending index, then filename.
- Board-parity edges (reproduce, don't re-derive): a task whose frontmatter fails to parse is DROPPED, never fatal (`Task.load()` swallows the error, so the board omits the card); an explicitly empty `columns`/`column_order` stays EMPTY rather than falling back to the stock Now/Next/Backlog board (`.get(key, default)`, not `or default`).
- Completion history follows `TASK_DIR`: `stats_data` resolves its archive through `config_utils.task_dir()` instead of a hardcoded `aitasks`, so membership and velocity can never come from two different task trees.
- Velocity (REPLACES the former 7/30-day blended `VELOCITY:<window_days>|<completed_count>|<avg_per_day>`): window = `W` calendar days ending at `--now` inclusive, `W` default 90 (`--velocity-window`). Default `dow` model emits one row per ISO weekday (Mon..Sun); `observed_units` counts weekday occurrences in the window **including zero-completion days**, `avg_per_unit = completed / observed_units`. `--now` is **date-only** (`YYYY-MM-DD`) because `collect_stats` subtracts `date` objects and `datetime - date` raises.
- Projection is **opt-in** (`--project`), never a default output: the models count tasks, so a projected date ignores task size (the `effort` field TASK rows already carry), blockers and capacity — an extrapolation of past throughput, not a delivery estimate. `<basis_completions>` reports how much history it rests on and `<caveat>` (`unweighted_task_counts`) names the limitation consumers MUST surface. Walk = Σ `remaining_items` burned down from `--now` inclusive at each day's modelled rate; first day the remainder hits ≤ 0 wins. Refused as `none|insufficient_data` when all averages are 0, when the walk passes the 3650-day bound, or when the window holds fewer than **10 completions** (confidence floor — one in-window completion otherwise manufactures a confident-looking date).
- The estimator is a swappable seam: a model implements `estimate(daily_counts, now, window_days) -> VelocityEstimate` exposing generic `buckets` + `rate_for(day)`. `rate_for` is the only thing the projection walk consumes and the walk lives in the caller — models supply rates, never policy. Swap = one class + one `VELOCITY_MODELS` entry, selected by `--velocity-model`. Two models ship (`dow` default, `flat` = the former blended rate) so swappability is demonstrated, not asserted.
- Internal helper only — no new `ait` subcommand.

## Verification

`bash tests/test_work_report_gather.sh` covering: ordering, multi-column grouping, subsets, `t` prefixes, invalid/moved/missing tasks, Unsorted dynamics, duplicates, empty selections; stale-selection (archived/deleted → unknown_task; moved → task_not_in_selected_columns; reordered → task_order_changed); `--list-columns` with/without Unsorted tasks; protocol round-trips (pipe-bearing title and path); delimiter-safety enforcement (one block per fixed-field class); `children_to_implement` type policy (None/str/dict); remaining-work semantics (Done leaf → 0, `[]` parent → 0, pending parent → count, active leaf → 1); phantom-stub exclusion; **board equivalence** vs `TaskManager.get_column_tasks` incl. a deliberate `boardidx` tie; velocity + projection (frozen date-only `--now`, zero-completion weekday still in `observed_units`, the worked Sunday→Monday example, `remaining_total 0`, zero history, the 3650-day bound at/over); and the **model-seam blocks** (same tree under `--velocity-model flat` changes only velocity/projection, `COLUMN:`/`TASK:` byte-identical). Also `shellcheck .aitask-scripts/aitask_work_report_gather.sh` and a regression run of `tests/test_board_*.py` for the `get_column_tasks` change.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-22T11:16:54Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-22T13:19:26Z status=pass attempt=1 type=human
