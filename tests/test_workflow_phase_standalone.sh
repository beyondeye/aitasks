#!/usr/bin/env bash
# Layering contract for the phase seam (t1467).
#
# `lib/workflow_phase.py` is a standalone CLI as well as a library: `ait gate
# workflow-phase` delegates to it, and it inserts ONLY its own `lib/` directory
# on sys.path. `monitor/` sits one layer up (monitor_core puts lib on the path
# and imports from it, never the reverse), so a lib module that imports from
# `monitor/` breaks the CLI for every caller outside a monitor process.
#
# t1467 moved the canonical pane->agent mapper into `lib/agent_keys.py` for
# exactly this reason; an earlier draft of the plan put it in
# `monitor/prompt_patterns.py`, which would have inverted the layering. These
# checks are what catch that class of mistake.
#
# Run: bash tests/test_workflow_phase_standalone.sh
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 1

# shellcheck source=tests/lib/asserts.sh
. "$REPO_ROOT/tests/lib/asserts.sh" 2>/dev/null || true

PASS=0; FAIL=0; TOTAL=0
check() {
    local name="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1)); echo "  PASS: $name"
    else
        FAIL=$((FAIL + 1))
        echo "  FAIL: $name"
        echo "        expected: $expected"
        echo "        actual:   $actual"
    fi
}

PHASE_PY="$REPO_ROOT/.aitask-scripts/lib/workflow_phase.py"
KEYS_PY="$REPO_ROOT/.aitask-scripts/lib/agent_keys.py"

echo "=== Guard 0: the lib modules exist ==="
check "workflow_phase.py present" "yes" \
    "$([[ -f "$PHASE_PY" ]] && echo yes || echo no)"
check "agent_keys.py present" "yes" \
    "$([[ -f "$KEYS_PY" ]] && echo yes || echo no)"

# shellcheck source=.aitask-scripts/lib/python_resolve.sh
. "$REPO_ROOT/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null || true
PY="$(resolve_python 2>/dev/null || true)"

if [[ -z "$PY" ]]; then
    echo "  SKIP: no python interpreter resolved"
else
    echo
    echo "=== Guard 1: the CLI runs standalone, outside the repo ==="
    # A scrubbed PYTHONPATH and a cwd outside the repo together reproduce the
    # bare invocation: nothing but the module's own sys.path insert is available.
    tmp="$(mktemp -d)"
    cat > "$tmp/t1.md" <<'EOF'
---
status: Implementing
---

body

## Gate Runs

> **✅ gate:plan_approved** run=2026-01-01T00:00:00Z status=pass attempt=1 type=human
EOF
    out="$(cd "$tmp" && env -u PYTHONPATH "$PY" "$PHASE_PY" signal "$tmp/t1.md" 2>&1)"
    rc=$?
    check "standalone CLI exits 0" "0" "$rc"
    check "standalone CLI emits a phase line" "IMPLEMENT" \
        "$(echo "$out" | grep -o '^PHASE:[A-Z]*' | cut -d: -f2)"

    # The same invocation with an agent, which is the path that reaches the
    # re-exported mapper — the import that would fail if it lived in monitor/.
    out2="$(cd "$tmp" && env -u PYTHONPATH "$PY" "$PHASE_PY" signal "$tmp/t1.md" \
        --pane-command codex 2>&1)"
    rc2=$?
    check "standalone CLI with --pane-command exits 0" "0" "$rc2"
    check "standalone CLI resolves the agent" "scoped" \
        "$(echo "$out2" | grep -o 'RESOLUTION:[a-z_]*' | cut -d: -f2)"
    rm -rf "$tmp"

    echo
    echo "=== Guard 2: no lib -> monitor imports, and ONE mapper ==="
    result="$("$PY" - "$REPO_ROOT" <<'PYEOF'
import ast
import sys
from pathlib import Path

root = Path(sys.argv[1])
lib = root / ".aitask-scripts" / "lib"

# AST rather than grep: a comment or a docstring mentioning `monitor` is not an
# import, and a grep would fail on this file's own explanatory prose.
offenders = []
for name in ("workflow_phase.py", "agent_keys.py"):
    tree = ast.parse((lib / name).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in ("monitor", "prompt_patterns"):
                    offenders.append(f"{name}:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".")[0]
            if mod in ("monitor", "prompt_patterns"):
                offenders.append(f"{name}:{node.module}")
print("MONITOR_IMPORTS:" + (",".join(offenders) if offenders else "-"))

sys.path.insert(0, str(lib))
sys.path.insert(0, str(root / ".aitask-scripts" / "monitor"))
import agent_keys
import workflow_phase
import prompt_patterns

# Identity, not equal behaviour on a sample: a forked reimplementation that
# happens to agree on today's fixtures must still fail.
same = (workflow_phase.agent_key_from_command
        is agent_keys.agent_key_from_command
        is prompt_patterns.agent_key_from_command)
print("ONE_MAPPER:" + ("1" if same else "0"))
print("AGENT_KEYS:" + ",".join(agent_keys.AGENT_KEYS))
PYEOF
)"
    check "no lib module imports from monitor/" "MONITOR_IMPORTS:-" \
        "$(echo "$result" | grep '^MONITOR_IMPORTS:')"
    check "all three public mappers are the same object" "ONE_MAPPER:1" \
        "$(echo "$result" | grep '^ONE_MAPPER:')"
    check "agent key set is pinned" "AGENT_KEYS:claude,codex,opencode" \
        "$(echo "$result" | grep '^AGENT_KEYS:')"

    echo
    echo "=== Guard 3: single derivation of the pane agent ==="
    # The key that scoped a pane's prompt matching is stamped on the snapshot
    # (`PaneSnapshot.agent_key`). Consumers must READ it, not re-derive it: a
    # second derivation can disagree with the one the kind was produced under.
    #
    # After t1467 the mapper is called from exactly two kinds of site:
    #   * the five classify call sites in monitor_core.py, which PRODUCE it;
    #   * two shadow-side sites in minimonitor_app.py, which have no snapshot
    #     to read (a shadow pane is not in the monitor's snapshot set).
    # Anything else is a re-derivation creeping back in.
    #
    # Hit COUNTS, never `grep -q`: a zero-match grep and a renamed symbol are
    # indistinguishable without the number.
    prod=$(grep -c 'agent_key_from_pane(pane.current_command' \
        "$REPO_ROOT/.aitask-scripts/monitor/monitor_core.py")
    check "five classify call sites resolve the agent" "5" "$prod"

    shadow=$(grep -c 'agent_key_from_command(shadow_command)' \
        "$REPO_ROOT/.aitask-scripts/monitor/minimonitor_app.py")
    check "two documented shadow-side sites" "2" "$shadow"

    # No OTHER site may derive the agent from a snapshot's pane command.
    strays=$(grep -rn 'agent_key_from_command(\s*$\|agent_key_from_command(snap' \
        "$REPO_ROOT/.aitask-scripts/monitor/" | grep -c . || true)
    check "no snapshot-side re-derivation" "0" "$strays"
fi

echo
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] && echo "All tests PASSED" || echo "SOME TESTS FAILED"
[[ "$FAIL" -eq 0 ]]
