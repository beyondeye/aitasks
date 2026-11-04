#!/usr/bin/env bash
# Smoke tests for the stats_data module (extracted in t597_1; promoted from
# stats/ to the base layer lib/stats_data.py in t1235).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$REPO_ROOT/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
cd "$REPO_ROOT" || exit 1

# `mktemp_suffixed` (BSD-safe suffixed temp files, t1729) lives here.
source "$REPO_ROOT/.aitask-scripts/lib/terminal_compat.sh"

PASS=0
FAIL=0

assert_pass() {
    local name="$1"
    PASS=$((PASS + 1))
    echo "PASS: $name"
}

assert_fail() {
    local name="$1"
    local detail="$2"
    FAIL=$((FAIL + 1))
    echo "FAIL: $name"
    echo "  $detail"
}

# 1. Module imports cleanly and exposes expected symbols.
if python3 - <<'PY'
import sys
sys.path.insert(0, ".aitask-scripts/lib")
from stats_data import (
    StatsData,
    TaskRecord,
    ImplementationInfo,
    VerifiedRankingData,
    collect_stats,
    load_verified_rankings,
    parse_frontmatter,
    bucket_avg,
    chart_totals,
    build_chart_title,
)
PY
then
    assert_pass "stats_data imports and exposes core symbols"
else
    assert_fail "stats_data imports and exposes core symbols" "import failed"
fi

# 2. collect_stats() returns a StatsData instance against the real repo.
if python3 - <<'PY'
import sys
sys.path.insert(0, ".aitask-scripts/lib")
from datetime import date
from stats_data import collect_stats, StatsData
data = collect_stats(date.today(), 1)
assert isinstance(data, StatsData), f"expected StatsData, got {type(data).__name__}"
assert data.total_tasks >= 0
assert isinstance(data.csv_rows, list)
PY
then
    assert_pass "collect_stats() returns StatsData against real archive"
else
    assert_fail "collect_stats() returns StatsData against real archive" "exception raised"
fi

# 3. aitask_stats.py still re-exports the moved symbols (CLI test compatibility).
if python3 - <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("aitask_stats_py", ".aitask-scripts/aitask_stats.py")
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
for name in ("collect_stats", "StatsData", "TASK_DIR", "ARCHIVE_DIR",
             "load_verified_rankings", "bucket_avg", "parse_frontmatter"):
    assert hasattr(mod, name), f"aitask_stats missing re-export: {name}"
PY
then
    assert_pass "aitask_stats.py re-exports moved symbols"
else
    assert_fail "aitask_stats.py re-exports moved symbols" "missing re-export"
fi

# 4. CLI smoke: text report, --csv. (--plot removed in t597_5; confirm it is gone.)
if ./.aitask-scripts/aitask_stats.sh >/dev/null 2>&1; then
    assert_pass "ait stats (text report) exits 0"
else
    assert_fail "ait stats (text report) exits 0" "non-zero exit"
fi

CSV_OUT=$(mktemp_suffixed "${TMPDIR:-/tmp}/test_stats_data_XXXXXX.csv")
trap 'rm -f "$CSV_OUT"' EXIT
if ./.aitask-scripts/aitask_stats.sh --csv "$CSV_OUT" >/dev/null 2>&1 \
        && [ -s "$CSV_OUT" ]; then
    assert_pass "ait stats --csv writes a non-empty file"
else
    assert_fail "ait stats --csv writes a non-empty file" "csv missing or empty"
fi

if ./.aitask-scripts/aitask_stats.sh --help 2>&1 | grep -- "--plot" >/dev/null; then
    assert_fail "ait stats --help no longer advertises --plot" "flag still present"
else
    assert_pass "ait stats --help no longer advertises --plot"
fi

# 5. One shared recent-window helper (t2194): stats_data re-exports the
#    model_stats_windows implementation, and the picker's old copy is gone.
if python3 - <<'PY'
import sys
sys.path.insert(0, ".aitask-scripts/lib")
import model_stats_windows
import stats_data
assert stats_data.recent_aggregate is model_stats_windows.recent_aggregate
PY
then
    assert_pass "stats_data.recent_aggregate is the shared model_stats_windows helper"
else
    assert_fail "stats_data.recent_aggregate is the shared model_stats_windows helper" "not the same object"
fi

if grep -q "def _recent_aggregate\|def recent_aggregate" \
        .aitask-scripts/lib/agent_model_picker.py .aitask-scripts/lib/stats_data.py; then
    assert_fail "no private copy of recent_aggregate remains" "a copy is still defined"
else
    assert_pass "no private copy of recent_aggregate remains"
fi

# 6. Stale buckets are not "recent" (t2194): months-old month/prev_month/week
#    buckets keep counting all-time only.
STALE_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/test_stats_data_stale_XXXXXX")
trap 'rm -f "$CSV_OUT"; rm -rf "$STALE_ROOT"' EXIT
mkdir -p "$STALE_ROOT/aitasks/metadata"
cat > "$STALE_ROOT/aitasks/metadata/models_claudecode.json" <<'JSON'
{"models": [{"name": "opus4_8", "cli_id": "claude-opus-4-8", "usagestats": {"pick": {
  "all_time": {"runs": 303},
  "month": {"period": "2026-07", "runs": 47},
  "prev_month": {"period": "2026-06", "runs": 220},
  "week": {"period": "2026-W30", "runs": 27}}}}]}
JSON
if python3 - "$STALE_ROOT" <<'PY'
import sys
from datetime import date
from pathlib import Path
sys.path.insert(0, ".aitask-scripts/lib")
from stats_data import load_usage_rankings
w = load_usage_rankings(Path(sys.argv[1]), today=date(2026, 11, 4)).by_window["pick"]["claudecode"]
assert [e.runs for e in w["all_time"]] == [303], w["all_time"]
for win in ("recent", "month", "prev_month", "week"):
    assert w[win] == [], (win, w[win])
PY
then
    assert_pass "load_usage_rankings drops stale buckets from the dated windows"
else
    assert_fail "load_usage_rankings drops stale buckets from the dated windows" "stale bucket counted"
fi

echo
echo "Total: $((PASS + FAIL))   Passed: $PASS   Failed: $FAIL"
[ "$FAIL" -eq 0 ]
