#!/usr/bin/env bash
# Smoke tests for the stats.stats_data module (extracted in t597_1).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

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
sys.path.insert(0, ".aitask-scripts")
from stats.stats_data import (
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
    assert_pass "stats.stats_data imports and exposes core symbols"
else
    assert_fail "stats.stats_data imports and exposes core symbols" "import failed"
fi

# 2. collect_stats() returns a StatsData instance against the real repo.
if python3 - <<'PY'
import sys
sys.path.insert(0, ".aitask-scripts")
from datetime import date
from stats.stats_data import collect_stats, StatsData
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

# 4. CLI smoke: text report, --csv, --plot --help (avoid running --plot interactively).
if ./.aitask-scripts/aitask_stats.sh >/dev/null 2>&1; then
    assert_pass "ait stats (text report) exits 0"
else
    assert_fail "ait stats (text report) exits 0" "non-zero exit"
fi

CSV_OUT=$(mktemp "${TMPDIR:-/tmp}/test_stats_data_XXXXXX.csv")
trap 'rm -f "$CSV_OUT"' EXIT
if ./.aitask-scripts/aitask_stats.sh --csv "$CSV_OUT" >/dev/null 2>&1 \
        && [ -s "$CSV_OUT" ]; then
    assert_pass "ait stats --csv writes a non-empty file"
else
    assert_fail "ait stats --csv writes a non-empty file" "csv missing or empty"
fi

if ./.aitask-scripts/aitask_stats.sh --help 2>&1 | grep -q -- "--plot"; then
    assert_pass "ait stats --help still advertises --plot (kept until t597_5)"
else
    assert_fail "ait stats --help still advertises --plot (kept until t597_5)" "missing flag"
fi

echo
echo "Total: $((PASS + FAIL))   Passed: $PASS   Failed: $FAIL"
[ "$FAIL" -eq 0 ]
