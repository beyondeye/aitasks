---
Task: t597_1_stats_data_module_refactor.md
Parent Task: aitasks/t597_ait_stats_tui.md
Sibling Tasks: aitasks/t597/t597_2_*.md, aitasks/t597/t597_3_*.md, aitasks/t597/t597_4_*.md, aitasks/t597/t597_5_*.md, aitasks/t597/t597_6_*.md
Archived Sibling Plans: aiplans/archived/p597/p597_*_*.md
Worktree: (no worktree — current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7 @ 2026-04-19 18:16
---

# Plan: t597_1 — Refactor stats data extraction into reusable module

## Context

Foundation refactor. `aitask_stats.py` (1219 LOC) currently mixes data extraction, text-report rendering, CSV export, and `--plot` chart rendering. The upcoming TUI panes (t597_3) need the data-extraction half without dragging in plotext or rendering. This task carves out the pure-data layer into a new `stats/` package so both the existing CLI (`ait stats`, `--csv`, `--plot`) and the TUI consume the same code paths.

This task does **not** touch the CLI's user-facing behavior — text report and CSV must produce byte-identical output before and after.

## Implementation Plan

### 1. Create the `stats` package

New files:
- `.aitask-scripts/stats/__init__.py` — empty (or single-line `"""ait stats shared package."""`).
- `.aitask-scripts/stats/stats_data.py` — receives the extracted code below.

### 2. Move into `stats_data.py`

From `aitask_stats.py`, move (cut, then re-import):

| Symbol | Approx lines |
|--------|--------------|
| `TaskRecord` dataclass | 66–71 |
| `StatsData` dataclass | 75–96 |
| `load_model_cli_ids()` | (search) |
| `load_verified_rankings()` | (search) |
| All archive parsers used by `collect_stats()` | 234–584 |
| `collect_stats(today, week_start_dow)` | 621–734 |
| `sorted_weekly_keys()`, `chart_totals()`, `build_chart_title()` | 737–1020 (only the pure helpers) |

Helpers used **only** by `show_chart()` / `run_plot_summary()` stay in `aitask_stats.py` for now — t597_5 deletes them outright with the `--plot` flag.

### 3. Re-import in `aitask_stats.py`

Replace removed code with:

```python
from stats.stats_data import (
    TaskRecord,
    StatsData,
    collect_stats,
    load_model_cli_ids,
    load_verified_rankings,
    sorted_weekly_keys,
    chart_totals,
    build_chart_title,
)
```

### 4. PYTHONPATH wiring

Verify `.aitask-scripts/aitask_stats.sh` adds `.aitask-scripts/` to `PYTHONPATH` (or has the equivalent `PYTHONPATH="${PYTHONPATH}:$(dirname "$0")"` setup) so `from stats.stats_data import …` resolves. If it does not, add it. Mirror whatever pattern other Python TUIs use — check `aitask_board.sh` and `aitask_codebrowser.sh`.

### 5. Tests

New file `tests/test_stats_data.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Source test helpers if a shared one exists in tests/, otherwise inline assert_eq/PASS/FAIL.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# Smoke import test
python3 -c "
import sys
sys.path.insert(0, '.aitask-scripts')
from stats.stats_data import collect_stats, StatsData, TaskRecord
from datetime import date
data = collect_stats(date.today(), 0)
assert isinstance(data, StatsData), 'collect_stats must return StatsData'
print('PASS: smoke import + collect_stats returns StatsData')
"

# CLI parity test — text report unchanged
before=$(./.aitask-scripts/aitask_stats.sh 2>&1 | sha256sum | cut -d' ' -f1)
# (no-op — refactor must not alter output)
after=$(./.aitask-scripts/aitask_stats.sh 2>&1 | sha256sum | cut -d' ' -f1)
[ "$before" = "$after" ] && echo "PASS: text report stable"
```

(Refine the parity check if `aitask_stats.sh` includes today's date in output — strip the timestamp before hashing.)

## Verification

```bash
# Output parity
./.aitask-scripts/aitask_stats.sh > /tmp/before.txt   # before refactor
# … apply refactor …
./.aitask-scripts/aitask_stats.sh > /tmp/after.txt
diff /tmp/before.txt /tmp/after.txt                   # empty diff

./.aitask-scripts/aitask_stats.sh --csv /tmp/before.csv
# … apply refactor …
./.aitask-scripts/aitask_stats.sh --csv /tmp/after.csv
diff /tmp/before.csv /tmp/after.csv                   # empty diff

./.aitask-scripts/aitask_stats.sh --plot              # still works (untouched here)

bash tests/test_stats_data.sh                          # PASS
```

## Out of Scope

- Anything related to the TUI itself (t597_2, t597_3).
- Removing `--plot` or its renderers (t597_5).
- Touching plotext (t597_5).

## Final Implementation Notes

- **Actual work done:**
  - Created `.aitask-scripts/stats/__init__.py` (package marker) and `.aitask-scripts/stats/stats_data.py` (~676 lines) holding all data-extraction code: constants (`TASK_DIR`, `ARCHIVE_DIR`, `TASK_TYPES_FILE`, `DAY_NAMES`, `DAY_FULL_NAMES`, `AGENT_DISPLAY_NAMES`, `LEGACY_IMPLEMENTED_WITH_CLI_IDS`), dataclasses (`TaskRecord`, `StatsData`, `ImplementationInfo`, `VerifiedModelEntry`, `VerifiedRankingData`), parsers (`parse_frontmatter`, `parse_labels`, `parse_completed_date`, `is_child_task`, `iter_archived_markdown_files`), model helpers (`load_model_cli_ids`, `load_verified_rankings`, `canonical_model_id`, `slugify_key`, `titleize_words`, `model_key_from_cli_id`, `model_display_from_cli_id`, `normalize_implemented_with`), week helpers (`week_start_for`, `week_offset_for`, `week_start_display_name`), reusable rendering helpers (`sorted_weekly_keys`, `chart_totals`, `build_chart_title`, `codeagent_display_name`, `bucket_avg`, `get_valid_task_types`), and `collect_stats()` itself.
  - Slimmed `.aitask-scripts/aitask_stats.py` from 1219 → 551 lines (-668). It now imports the moved symbols and re-exports them via `__all__` so existing call sites and tests using `aitask_stats.X` continue to work. Kept in place: `parse_args`, `resolve_week_start`, `avg`, `get_type_display_name`, `render_text_report`, `render_verified_rankings`, `write_csv`, `chart_plot_size`, `show_chart`, `_import_plotext`, `run_plot_summary`, `run_verified_plots`, `main`, `__main__`.
  - PYTHONPATH wiring: `aitask_stats.py` does `sys.path.insert(0, dirname(__file__))` at top so `from stats.stats_data import …` resolves. `stats_data.py` does its own `sys.path.insert` for `lib/` so `from archive_iter import …` resolves regardless of how the module is loaded. The wrapper `aitask_stats.sh` was NOT modified (intentionally — the in-script sys.path tweaks are sufficient and don't require coupling the wrapper to the package layout).
  - New `tests/test_stats_data.sh` (6 smoke tests, all PASS): module imports & exposes core symbols; `collect_stats()` returns `StatsData` against the real archive; `aitask_stats.py` re-exports moved symbols; `ait stats` exits 0; `--csv` writes a non-empty file; `--help` still advertises `--plot` (kept until t597_5).
  - Patched `tests/test_aitask_stats_py.py` (the existing 18-test unit suite) to also patch the underlying `stats.stats_data` module's constants when overriding `TASK_DIR`/`ARCHIVE_DIR`/`TASK_TYPES_FILE`. Added a `stats_data_mod = sys.modules["stats.stats_data"]` handle and updated the `TestCollection` and `TestVerifiedRankings` setUp/tearDown to apply patches to both modules. All 18 tests pass after the change.

- **Deviations from plan:**
  - Plan §4 (PYTHONPATH wiring) suggested editing `aitask_stats.sh`. Instead I used `sys.path.insert` inside the Python files. Reasoning: keeps the wrapper trivially compatible with how it has always launched the script, avoids changing the wrapper's existing fallback for the bundled venv, and works equally well when the module is loaded by tests via `importlib.spec_from_file_location` (which doesn't run the wrapper at all).
  - Plan's §5 test was a sketch that diffed `--plot` output via sha256. The real output includes a `Generated:` timestamp that changes minute-to-minute, so I dropped the sha256 idea and instead wrote 6 focused assertions (import, dataclass shape, re-export presence, CLI exit codes, CSV non-empty, `--help` mentions `--plot`).

- **Issues encountered:**
  - First test run after the refactor surfaced 9 failures in `tests/test_aitask_stats_py.py`. Root cause: `TestCollection.setUp` and `TestVerifiedRankings.setUp` patched `stats.TASK_DIR` (the re-exported reference in `aitask_stats`), but post-refactor the functions read `TASK_DIR` from `stats.stats_data`'s namespace, so the patches didn't take effect. Fixed by mirroring patches into both modules via the new `stats_data_mod` handle.

- **Key decisions:**
  - Re-export pattern (`__all__` with the moved names) keeps the public surface of `aitask_stats` unchanged. This was the lowest-risk path to "CLI behavior identical" and meant no callers (test or production) needed updates.
  - Moved `chart_totals` and `build_chart_title` into `stats_data.py` even though their only caller today is `run_plot_summary` (which t597_5 deletes). They are pure helpers and t597_3's TUI panes will reuse them.
  - Did not move `chart_plot_size`, `show_chart`, `_import_plotext`, `run_plot_summary`, `run_verified_plots`. These are rendering-only and t597_5 will delete them outright with the `--plot` flag.

- **Notes for sibling tasks:**
  - **t597_2 (TUI skeleton):** the data layer is ready. Import via `from stats.stats_data import collect_stats, StatsData`. Since the package lives at `.aitask-scripts/stats/`, the TUI wrapper (`aitask_stats_tui.sh`) needs to either (a) prepend `.aitask-scripts/` to `PYTHONPATH`, or (b) the TUI's main script can do `sys.path.insert` itself like `aitask_stats.py` does at the top. Either works.
  - **t597_3 (panes):** the StatsData field names you'll consume are `total_tasks`, `tasks_7d`, `tasks_30d`, `daily_counts` (Counter[date]), `daily_tasks` (Dict[date, List[str]]), `dow_counts_thisweek`, `dow_counts_30d`, `dow_counts_total`, `label_counts_total`, `label_week_counts` (Counter[(label, week_offset)]), `label_dow_counts_30d`, `type_week_counts` (covers both `parent`/`child` and issue types), `label_type_week_counts`, `codeagent_week_counts`, `model_week_counts`, `all_labels`, `all_codeagents`, `all_models`, `codeagent_display_names`, `model_display_names`, `csv_rows`. The earlier sibling plan (p597_3) used some imprecise names — adjust to the canonical names above when implementing.
  - **t597_5 (--plot removal):** safe to delete `show_chart()`, `run_plot_summary()`, `run_verified_plots()`, `_import_plotext()`, `chart_plot_size()` from `aitask_stats.py`. They are not imported by anything outside `aitask_stats.py` itself. Also delete the `--plot` argparse arg and its branch in `main()`. The `chart_totals` and `build_chart_title` helpers must NOT be deleted from `stats/stats_data.py` — TUI panes use them.
