#!/usr/bin/env bash
# Regression test for t792: group-level aggregate progress.
#
# Verifies two pieces of TUI infrastructure added for parallel-explore
# progress visibility:
#   1. The pure ``_format_progress_bar()`` helper produces the expected
#      bar string for a range of inputs (and an empty string when
#      progress <= 0 or invalid).
#   2. The mean-of-agent-progress aggregation matches what
#      ``BrainstormApp._compute_group_progress`` computes for a synthetic
#      crew worktree.
#
# Pure Python — no Textual harness needed.

set -euo pipefail

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$THIS_DIR/.." && pwd)"
cd "$REPO_ROOT"

# Resolve the framework interpreter (prefers the aitask venv, which has textual
# and the yaml dependency brainstorm_session pulls in) instead of bare python3,
# which may skip cases 1/2 and fail case 3 on a venv-less system (t935).
# shellcheck source=.aitask-scripts/lib/python_resolve.sh
source "$REPO_ROOT/.aitask-scripts/lib/python_resolve.sh"
PY="$(require_ait_python)"

PASS=0
FAIL=0

# ---------------------------------------------------------------------------
# Case 1: _format_progress_bar() — pure function, run in-process.
# ---------------------------------------------------------------------------

format_test_out=$("$PY" - <<'PY'
import sys
sys.path.insert(0, '.aitask-scripts')

# Stub the Textual dependency tree before importing brainstorm_app
# (we only need _format_progress_bar; the rest is irrelevant here).
import importlib.util
spec = importlib.util.find_spec("textual")
if spec is None:
    print("SKIP_FORMAT:textual not installed")
    sys.exit(0)

from brainstorm.brainstorm_app import _format_progress_bar

cases = [
    (0, ""),
    (-5, ""),
    (None, ""),
    ("not-a-number", ""),
    (1, "░░░░░░░░░░ 1%"),   # filled = int(10*1/100) = 0
    (10, "█░░░░░░░░░ 10%"),
    (50, "█████░░░░░ 50%"),
    (100, "██████████ 100%"),
    (150, "██████████ 100%"),  # clipped
]
fails = 0
for inp, expected in cases:
    got = _format_progress_bar(inp)
    if got != expected:
        print(f"FAIL_CASE:input={inp!r} expected={expected!r} got={got!r}")
        fails += 1
print(f"FORMAT_FAILS:{fails}")
PY
)

if echo "$format_test_out" | grep -q "^SKIP_FORMAT:"; then
    echo "SKIP: _format_progress_bar (textual unavailable in this env)"
elif echo "$format_test_out" | grep -q "^FORMAT_FAILS:0$"; then
    echo "PASS: _format_progress_bar produces expected bars across the input range"
    PASS=$((PASS + 1))
else
    echo "FAIL: _format_progress_bar mismatches:"
    echo "$format_test_out" | sed 's/^/  /'
    FAIL=$((FAIL + 1))
fi

# ---------------------------------------------------------------------------
# Case 2: aggregation arithmetic — pure helper. We replicate the
# (mean → int(round())) reduction inline and assert it returns the
# values the GroupRow surfaces. Keeps the test independent of Textual.
# ---------------------------------------------------------------------------

agg_test_out=$("$PY" - <<'PY'
def mean_round(progresses):
    if not progresses:
        return None
    return int(round(sum(progresses) / len(progresses)))

cases = [
    ([], None),
    ([0, 0], 0),
    ([100, 100], 100),
    ([15, 60], 38),
    ([15, 85], 50),
    ([100, 0], 50),
    ([100, 50, 0], 50),
]
fails = 0
for ps, expected in cases:
    got = mean_round(ps)
    if got != expected:
        print(f"FAIL_AGG:input={ps} expected={expected} got={got}")
        fails += 1
print(f"AGG_FAILS:{fails}")
PY
)

if echo "$agg_test_out" | grep -q "^AGG_FAILS:0$"; then
    echo "PASS: aggregation arithmetic (mean → round → int) matches expected values"
    PASS=$((PASS + 1))
else
    echo "FAIL: aggregation arithmetic mismatches:"
    echo "$agg_test_out" | sed 's/^/  /'
    FAIL=$((FAIL + 1))
fi

# ---------------------------------------------------------------------------
# Case 3: _compute_group_progress reads real status YAMLs from a fake
# crew worktree. Exercises the integration (not just the math).
# ---------------------------------------------------------------------------

CREW=".aitask-crews/crew-brainstorm-999743"
cleanup_crew() { rm -rf "$CREW"; }
trap cleanup_crew EXIT
rm -rf "$CREW"
mkdir -p "$CREW"

cat > "$CREW/explorer_001a_status.yaml" <<'EOF'
agent_name: explorer_001a
agent_type: explorer
group: explore_001
status: Running
progress: 60
EOF

cat > "$CREW/explorer_001b_status.yaml" <<'EOF'
agent_name: explorer_001b
agent_type: explorer
group: explore_001
status: Running
progress: 15
EOF

integ_test_out=$("$PY" - "$CREW" <<'PY'
import sys
sys.path.insert(0, '.aitask-scripts')

try:
    import textual  # noqa: F401
except Exception:
    print("SKIP_INTEG:textual not installed")
    sys.exit(0)

from brainstorm.brainstorm_app import BrainstormApp

wt = sys.argv[1]
ginfo = {"agents": ["explorer_001a", "explorer_001b"]}

# Build an instance without running __init__'s full Textual setup:
# _compute_group_progress is a plain method that uses only wt + ginfo.
app = BrainstormApp.__new__(BrainstormApp)
got = app._compute_group_progress(wt, ginfo)
expected = 38  # mean(60, 15) = 37.5 → round → 38
print(f"INTEG:got={got}:expected={expected}")
PY
)

if echo "$integ_test_out" | grep -q "^SKIP_INTEG:"; then
    echo "SKIP: _compute_group_progress (textual unavailable)"
elif echo "$integ_test_out" | grep -q "^INTEG:got=38:expected=38$"; then
    echo "PASS: _compute_group_progress reads agent YAMLs and averages correctly"
    PASS=$((PASS + 1))
else
    echo "FAIL: _compute_group_progress integration:"
    echo "$integ_test_out" | sed 's/^/  /'
    FAIL=$((FAIL + 1))
fi

cleanup_crew
trap - EXIT

# ---------------------------------------------------------------------------
# Case 4: resolve_node_group defensive lookup. Exercises the three
# resolution paths (direct, nodes_created membership, suffix match)
# plus the unresolved case.
# ---------------------------------------------------------------------------

resolve_test_out=$("$PY" - <<'PY'
import sys
sys.path.insert(0, '.aitask-scripts')

try:
    import textual  # noqa: F401
except Exception:
    print("SKIP_RESOLVE:textual not installed")
    sys.exit(0)

from brainstorm.brainstorm_session import resolve_node_group

groups = {
    "explore_001": {
        "operation": "explore",
        "agents": ["explorer_001a", "explorer_001b"],
        "nodes_created": ["n002_good"],
    },
    "patch_002": {
        "operation": "patch",
        "agents": ["patcher_002"],
        "nodes_created": ["n003_patched"],
    },
}

cases = [
    # (node_id, stored_group, expected_resolved_name, expected_op)
    ("n002_good",   "explore_001",     "explore_001", "explore"),  # direct
    ("n002_good",   "op_explore_001",  "explore_001", "explore"),  # suffix
    ("n003_patched","operation_patch_002","patch_002", "patch"),   # suffix
    ("n002_good",   "garbage_value",   "explore_001", "explore"),  # nodes_created
    ("n_unknown",   "totally_unknown", "totally_unknown", "?"),    # no match
]
fails = 0
for node_id, stored, expected_name, expected_op in cases:
    name, info = resolve_node_group(node_id, stored, groups)
    op = info.get("operation", "?")
    if name != expected_name or op != expected_op:
        print(f"FAIL_RESOLVE:input=({node_id!r},{stored!r}) "
              f"expected=({expected_name!r},{expected_op!r}) "
              f"got=({name!r},{op!r})")
        fails += 1
print(f"RESOLVE_FAILS:{fails}")
PY
)

if echo "$resolve_test_out" | grep -q "^SKIP_RESOLVE:"; then
    echo "SKIP: resolve_node_group (textual unavailable)"
elif echo "$resolve_test_out" | grep -q "^RESOLVE_FAILS:0$"; then
    echo "PASS: resolve_node_group resolves direct + nodes_created + suffix drift"
    PASS=$((PASS + 1))
else
    echo "FAIL: resolve_node_group:"
    echo "$resolve_test_out" | sed 's/^/  /'
    FAIL=$((FAIL + 1))
fi

echo
echo "Total: $((PASS + FAIL))   Passed: $PASS   Failed: $FAIL"
[[ $FAIL -eq 0 ]]
