#!/usr/bin/env bash
# test_gate_procedure_docs.sh - Tests for procedure-backed gates (t635_19),
# using docs_updated as the concrete instance.
#
# Covers:
#   - read_registry parses `kind: procedure` (and absent => "" for command gates).
#   - The headless orchestrator DEFERS a procedure gate: reports "needs agent",
#     appends nothing, exits 0 (never shell-executes a verifier for it).
#   - archive-ready is fail-safe: BLOCKED until the gate records pass OR skip;
#     both pass and skip are terminal-satisfied => ALL_PASS.
#   - `procedure-gates` lists declared unmet procedure gates; empty once pass/skip.
#   - `begin-procedure` opens a running block + monotonic attempt; the skill's
#     `append --only-if-running` closes it to a single terminal entry.
#
# Run: bash tests/test_gate_procedure_docs.sh
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0; FAIL=0; TOTAL=0
CLEANUP_DIRS=()
GATE="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"
ORCH="$PROJECT_DIR/.aitask-scripts/lib/gate_orchestrator.py"
REG="$PROJECT_DIR/aitasks/metadata/gates.yaml"
PY="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null; resolve_python 2>/dev/null || echo python3)"

new_fixture() {
    local tmp
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/test_procgate_XXXXXX")"
    CLEANUP_DIRS+=("$tmp")
    mkdir -p "$tmp/aitasks/metadata"
    cp "$REG" "$tmp/aitasks/metadata/gates.yaml"
    echo "$tmp"
}

# write_task <dir> <id> <gates-csv>
write_task() {
    local dir="$1" id="$2" gates="$3"
    printf -- '---\nstatus: Implementing\ngates: [%s]\n---\nBody.\n' "$gates" \
        > "$dir/aitasks/t${id}_x.md"
}

# g <dir> <args...> — run aitask_gate.sh from the fixture root with TASK_DIR set.
g() { local d="$1"; shift; ( cd "$d" && TASK_DIR=aitasks "$GATE" "$@" ); }

cleanup() { local d; for d in "${CLEANUP_DIRS[@]}"; do rm -rf "$d"; done; }
trap cleanup EXIT

# --- 1. registry parse: kind ------------------------------------------------
out="$("$PY" -c "
import sys; sys.path.insert(0,'$PROJECT_DIR/.aitask-scripts/lib')
import gate_ledger as gl
r = gl.read_registry('$REG')
print(r['docs_updated']['kind'], '|', r['docs_updated']['type'], '|', r['build_verified']['kind'] or 'EMPTY')
")"
assert_eq "read_registry kind: procedure gate, command gate empty" \
    "procedure | machine | EMPTY" "$out"

# --- 2. orchestrator defers procedure gate as needs-agent -------------------
fx="$(new_fixture)"; write_task "$fx" 10 docs_updated
run_out="$( cd "$fx" && "$PY" "$ORCH" run aitasks/t10_x.md --registry aitasks/metadata/gates.yaml 2>&1 )"; rc=$?
assert_eq "orchestrator run exits 0 for a deferred procedure gate" "0" "$rc"
assert_contains "orchestrator reports needs-agent" "needs agent" "$run_out"
appends="$(grep -c 'gate:docs_updated' "$fx/aitasks/t10_x.md" || true)"
assert_eq "orchestrator appended nothing for the procedure gate" "0" "$appends"

# --- 3. archive-ready fail-safe (BLOCKED until pass/skip) --------------------
assert_eq "archive-ready BLOCKED before any run" "BLOCKED:docs_updated" "$(g "$fx" archive-ready 10)"
assert_eq "procedure-gates lists the unmet gate" "docs_updated" "$(g "$fx" procedure-gates 10)"

# --- 4. begin-procedure + skill append (pass) closes exactly one run --------
bp="$(g "$fx" begin-procedure 10 docs_updated)"
rid="$(printf '%s\n' "$bp" | sed -n 's/^RUN_ID://p')"
att="$(printf '%s\n' "$bp" | sed -n 's/^ATTEMPT://p')"
assert_eq "begin-procedure attempt = 1" "1" "$att"
assert_contains "running block opened" "running" "$(g "$fx" status 10)"
g "$fx" append --only-if-running "$rid" 10 docs_updated pass run="$rid" attempt="$att" type=machine verifier=aitask-gate-docs-updated result="updated docs" >/dev/null
# derived status = pass; exactly one *terminal* (pass) block for this gate
assert_contains "derived status pass after skill append" "docs_updated: pass" "$(g "$fx" status 10)"
term="$(grep -c 'status=pass' "$fx/aitasks/t10_x.md" || true)"
assert_eq "exactly one terminal pass block" "1" "$term"
assert_eq "archive-ready ALL_PASS after pass" "ALL_PASS" "$(g "$fx" archive-ready 10)"
assert_eq "procedure-gates empty after pass (not re-dispatched)" "" "$(g "$fx" procedure-gates 10)"

# --- 5. skip is terminal-satisfied too --------------------------------------
fx2="$(new_fixture)"; write_task "$fx2" 20 docs_updated
g "$fx2" append 20 docs_updated skip type=machine >/dev/null
assert_eq "archive-ready ALL_PASS after skip" "ALL_PASS" "$(g "$fx2" archive-ready 20)"
assert_eq "procedure-gates empty after skip" "" "$(g "$fx2" procedure-gates 20)"

# --- 6. a non-procedure task has no procedure gates -------------------------
fx3="$(new_fixture)"; write_task "$fx3" 30 risk_evaluated
assert_eq "procedure-gates empty for a task with only a command gate" "" "$(g "$fx3" procedure-gates 30)"

# --- summary ---------------------------------------------------------------
echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[ "$FAIL" -eq 0 ]
