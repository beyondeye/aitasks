#!/usr/bin/env bash
# test_gate_cli_wiring.sh - Tests the `ait gate` / `ait gates` dispatcher wiring
# and the new helper scripts (t635_11). No agents; read-only / dry-run paths.
#
# Run: bash tests/test_gate_cli_wiring.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

AIT="$PROJECT_DIR/ait"

new_fixture() {
    local tmp; tmp="$(mktemp -d "${TMPDIR:-/tmp}/test_gatecli_XXXXXX")"
    CLEANUP_DIRS+=("$tmp")
    mkdir -p "$tmp/aitasks/metadata"
    cp "$PROJECT_DIR/ait" "$tmp/ait"
    ln -s "$PROJECT_DIR/.aitask-scripts" "$tmp/.aitask-scripts"
    echo "$tmp"
}

echo "=== Test 1: ait gates / ait gate help ==="
out="$("$AIT" gates --help 2>&1)"
assert_contains "ait gates --help lists subcommands" "run | unlocked | list | status" "$out"
out="$("$AIT" gate --help 2>&1)"
assert_contains "ait gate --help lists subcommands" "append" "$out"
assert_contains "ait gate --help lists fail" "fail" "$out"
assert_contains "ait gate --help lists log" "log" "$out"

echo "=== Test 2: unknown subcommands error ==="
"$AIT" gates bogus >/dev/null 2>&1; rc=$?
assert_eq "ait gates bogus exits nonzero" "1" "$rc"
"$AIT" gate bogus >/dev/null 2>&1; rc=$?
assert_eq "ait gate bogus exits nonzero" "1" "$rc"

echo "=== Test 3: ait gates run dispatches to the orchestrator ==="
d="$(new_fixture)"
cat > "$d/aitasks/metadata/gates.yaml" <<EOF
gates:
  g:
    type: machine
    verifier: ""
EOF
printf -- '---\nstatus: Implementing\ngates: [g]\n---\nB\n' > "$d/aitasks/t1_x.md"
# empty verifier -> no auto-run -> "blocked: no verifier configured"
out="$( cd "$d" && ./ait gates run 1 2>&1 )"
assert_contains "ait gates run reaches the engine (reports the gate)" "g:" "$out"

echo "=== Test 4: ait gates unlocked dispatches ==="
out="$( cd "$d" && ./ait gates unlocked 1 2>&1 )"
assert_eq "ait gates unlocked prints the runnable gate" "g" "$out"

echo "=== Test 5: ait gate append / status / fail / log wiring ==="
d2="$(new_fixture)"
printf -- '---\nstatus: Implementing\ngates: [g]\n---\nB\n' > "$d2/aitasks/t2_x.md"
( cd "$d2" && ./ait gate append 2 g running run=rid1 >/dev/null 2>&1 )
out="$( cd "$d2" && ./ait gates status 2 2>&1 )"
assert_contains "ait gate append -> ait gates status shows it" "g: running" "$out"
# ait gate fail
( cd "$d2" && ./ait gate fail 2 g --reason "manual reject" >/dev/null 2>&1 )
out="$( cd "$d2" && ./ait gates status 2 2>&1 )"
assert_contains "ait gate fail records a fail" "g: fail" "$out"
# ait gate log (no sidecar -> friendly message, exit 0)
out="$( cd "$d2" && ./ait gate log 2 g 2>&1 )"; rc=$?
assert_eq "ait gate log exits 0 with no sidecar" "0" "$rc"
assert_contains "ait gate log reports missing sidecar gracefully" "no sidecar log" "$out"

for dir in "${CLEANUP_DIRS[@]}"; do rm -rf "$dir"; done

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
