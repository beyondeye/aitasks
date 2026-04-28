#!/usr/bin/env bash
# Unit tests for the verified-rankings pane helpers (t603).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# shellcheck source=lib/venv_python.sh
. "$SCRIPT_DIR/lib/venv_python.sh"

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

# 1. _ops_sorted_by_runs orders by all_providers/all_time runs desc, tie-broken by name asc.
if "$AITASK_PYTHON" - <<'PY'
import sys
sys.path.insert(0, ".aitask-scripts")
from stats.stats_data import VerifiedRankingData, VerifiedModelEntry
from stats.panes.agents import _ops_sorted_by_runs

def mk(runs):
    return VerifiedModelEntry("cli", "Display", "all_providers", 0, runs)

vdata = VerifiedRankingData(
    by_window={
        "alpha": {"all_providers": {"all_time": [mk(5), mk(5)]}},       # 10 runs
        "bravo": {"all_providers": {"all_time": [mk(100)]}},            # 100 runs
        "charlie": {"all_providers": {"all_time": [mk(10)]}},           # 10 runs (ties with alpha)
        "delta": {"all_providers": {"all_time": []}},                   # 0 runs -> excluded
    },
    operations=["alpha", "bravo", "charlie", "delta"],
)
result = _ops_sorted_by_runs(vdata)
assert result == ["bravo", "alpha", "charlie"], f"got {result}"
PY
then
    assert_pass "_ops_sorted_by_runs orders runs desc, name asc, drops zero-run ops"
else
    assert_fail "_ops_sorted_by_runs orders runs desc, name asc, drops zero-run ops" "python assertion failed"
fi

# 2. Empty vdata yields empty list (no crash).
if "$AITASK_PYTHON" - <<'PY'
import sys
sys.path.insert(0, ".aitask-scripts")
from stats.stats_data import VerifiedRankingData
from stats.panes.agents import _ops_sorted_by_runs
assert _ops_sorted_by_runs(VerifiedRankingData(by_window={}, operations=[])) == []
PY
then
    assert_pass "_ops_sorted_by_runs handles empty data"
else
    assert_fail "_ops_sorted_by_runs handles empty data" "python assertion failed"
fi

# 3. VerifiedRankingsPane constructs without error and cycle_op wraps correctly.
#    (We bypass Textual's app runtime by driving cycle_op directly on a pane
#    whose _populate() is stubbed, since _populate() needs mounted widgets.)
if "$AITASK_PYTHON" - <<'PY'
import sys
sys.path.insert(0, ".aitask-scripts")
from stats.stats_data import VerifiedRankingData, VerifiedModelEntry
from stats.panes.agents import VerifiedRankingsPane

def mk(runs):
    return VerifiedModelEntry("cli", "Display", "all_providers", 0, runs)

vdata = VerifiedRankingData(
    by_window={
        "a": {"all_providers": {"all_time": [mk(10)]}},
        "b": {"all_providers": {"all_time": [mk(5)]}},
        "c": {"all_providers": {"all_time": [mk(1)]}},
    },
    operations=["a", "b", "c"],
)
pane = VerifiedRankingsPane(vdata)
assert pane._ops == ["a", "b", "c"], f"got {pane._ops}"
assert pane._op_idx == 0

# Stub _populate so cycle_op doesn't touch unmounted widgets.
pane._populate = lambda: None
pane.cycle_op(+1)
assert pane._op_idx == 1
pane.cycle_op(+1)
assert pane._op_idx == 2
pane.cycle_op(+1)
assert pane._op_idx == 0, "should wrap forward"
pane.cycle_op(-1)
assert pane._op_idx == 2, "should wrap backward"
PY
then
    assert_pass "VerifiedRankingsPane cycle_op wraps in both directions"
else
    assert_fail "VerifiedRankingsPane cycle_op wraps in both directions" "python assertion failed"
fi

# 4. Single-op edge case: cycle_op is a no-op.
if "$AITASK_PYTHON" - <<'PY'
import sys
sys.path.insert(0, ".aitask-scripts")
from stats.stats_data import VerifiedRankingData, VerifiedModelEntry
from stats.panes.agents import VerifiedRankingsPane

vdata = VerifiedRankingData(
    by_window={"only": {"all_providers": {"all_time": [VerifiedModelEntry("cli", "D", "all_providers", 0, 3)]}}},
    operations=["only"],
)
pane = VerifiedRankingsPane(vdata)
pane._populate = lambda: None
pane.cycle_op(+1)
pane.cycle_op(-1)
assert pane._op_idx == 0, "single-op pane should never advance index"
PY
then
    assert_pass "VerifiedRankingsPane single-op cycle_op is a no-op"
else
    assert_fail "VerifiedRankingsPane single-op cycle_op is a no-op" "python assertion failed"
fi

# 5. Smoke test: _render_verified invoked with a mock container does not raise.
#    (Container.mount() is mocked to avoid Textual app context.)
if "$AITASK_PYTHON" - <<'PY'
import sys
sys.path.insert(0, ".aitask-scripts")
from stats.stats_data import VerifiedRankingData
import stats.panes.agents as agents

# Force load_verified_rankings to return empty so we hit the empty-state path.
agents.load_verified_rankings = lambda: VerifiedRankingData(by_window={}, operations=[])

class FakeContainer:
    def __init__(self):
        self.mounted = []
    def mount(self, widget):
        self.mounted.append(widget)

c = FakeContainer()
agents._render_verified(None, c)
# empty_state mounts a Static — exactly one widget should appear.
assert len(c.mounted) == 1, f"expected 1 mount, got {len(c.mounted)}"
PY
then
    assert_pass "_render_verified empty-state path mounts without error"
else
    assert_fail "_render_verified empty-state path mounts without error" "python assertion failed"
fi

echo
echo "Passed: $PASS"
echo "Failed: $FAIL"
[ "$FAIL" -eq 0 ]
