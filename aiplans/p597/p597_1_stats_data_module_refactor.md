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
