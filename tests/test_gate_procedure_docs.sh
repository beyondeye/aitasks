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

# --- 4b. attempt advances by 1 per COMPLETED attempt (t1262) ----------------
# A completed attempt leaves TWO markers (running + terminal). Counting every
# marker made begin-procedure report 1 -> 3 -> 5 (observed live on t1255).
fx4="$(new_fixture)"; write_task "$fx4" 40 docs_updated
for want in 1 2 3; do
    bp="$(g "$fx4" begin-procedure 40 docs_updated)"
    rid="$(printf '%s\n' "$bp" | sed -n 's/^RUN_ID://p')"
    att="$(printf '%s\n' "$bp" | sed -n 's/^ATTEMPT://p')"
    assert_eq "begin-procedure reports attempt $want across full cycles" "$want" "$att"
    g "$fx4" append --only-if-running "$rid" 40 docs_updated fail \
        run="$rid" attempt="$att" type=machine >/dev/null
done
# Six markers collapse to three distinct attempt numbers: each running block and
# the terminal block that closes it share one — the ledger shape documented in
# aidocs/gates/aitask-gate-framework.md.
distinct="$(grep -o 'attempt=[0-9]*' "$fx4/aitasks/t40_x.md" | sed 's/attempt=//' \
            | sort -u | tr '\n' ' ' | sed 's/ $//')"
assert_eq "three completed attempts numbered 1,2,3 with no duplicates" "1 2 3" "$distinct"
assert_eq "running block and its closer share attempt=1" \
    "2" "$(grep -c 'attempt=1' "$fx4/aitasks/t40_x.md" || true)"

# --- 4c. single live run: a repeat begin-procedure ADOPTS it (t1262) --------
# A crash/resume re-dispatch (procedure-gates still lists a non-pass/skip gate)
# or a concurrent launch must not open a second live run for one gate.
fx5="$(new_fixture)"; write_task "$fx5" 50 docs_updated
bp1="$(g "$fx5" begin-procedure 50 docs_updated)"
rid1="$(printf '%s\n' "$bp1" | sed -n 's/^RUN_ID://p')"
att1="$(printf '%s\n' "$bp1" | sed -n 's/^ATTEMPT://p')"
bp2="$(g "$fx5" begin-procedure 50 docs_updated 2>/dev/null)"
rid2="$(printf '%s\n' "$bp2" | sed -n 's/^RUN_ID://p')"
att2="$(printf '%s\n' "$bp2" | sed -n 's/^ATTEMPT://p')"
assert_eq "repeat begin-procedure adopts the live run id" "$rid1" "$rid2"
assert_eq "repeat begin-procedure reports the same attempt" "$att1" "$att2"
assert_eq "repeat begin-procedure appends nothing (one running marker)" \
    "1" "$(grep -c 'status=running' "$fx5/aitasks/t50_x.md" || true)"
assert_contains "adoption is announced on stderr" "already has a live run" \
    "$(g "$fx5" begin-procedure 50 docs_updated 2>&1 >/dev/null)"
# Closing the adopted run frees the gate: the next begin is a NEW run, attempt 2.
g "$fx5" append --only-if-running "$rid1" 50 docs_updated fail \
    run="$rid1" attempt="$att1" type=machine >/dev/null
bp3="$(g "$fx5" begin-procedure 50 docs_updated)"
rid3="$(printf '%s\n' "$bp3" | sed -n 's/^RUN_ID://p')"
assert_eq "after the live run closes, the next begin is attempt 2" \
    "2" "$(printf '%s\n' "$bp3" | sed -n 's/^ATTEMPT://p')"
TOTAL=$((TOTAL + 1))
if [[ "$rid3" != "$rid1" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: attempt 2 reused attempt 1's run id ($rid3)"
fi

# --- 4cc. an adopted run must be CLOSEABLE (t1262) --------------------------
# `append --only-if-running <rid>` is a no-op unless <rid>'s LATEST marker is
# `running`, so the live-run scan must apply that same per-run-id rule. A
# `pending` marker for a live run id ends the window: a scan that ignored
# non-terminal statuses adopted a run whose closer silently did nothing, and the
# gate could never be closed. Both backends must agree on this history.
for backend in bash python; do
    fxa="$(new_fixture)"; write_task "$fxa" 55 docs_updated
    g "$fxa" append 55 docs_updated running run=r1 attempt=1 type=machine >/dev/null
    g "$fxa" append 55 docs_updated pending run=r1 type=human >/dev/null
    if [[ "$backend" == "python" ]]; then
        [[ -z "$PY" ]] && continue
        bpa="$(AIT_GATES_BACKEND=python g "$fxa" begin-procedure 55 docs_updated 2>/dev/null)"
    else
        bpa="$(g "$fxa" begin-procedure 55 docs_updated 2>/dev/null)"
    fi
    rida="$(printf '%s\n' "$bpa" | sed -n 's/^RUN_ID://p')"
    atta="$(printf '%s\n' "$bpa" | sed -n 's/^ATTEMPT://p')"
    TOTAL=$((TOTAL + 1))
    if [[ "$rida" != "r1" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1)); echo "FAIL[$backend]: adopted r1, whose latest marker is pending (uncloseable)"
    fi
    # The decisive assertion: whatever run it returned, the closer must close it.
    before="$(grep -c 'status=fail' "$fxa/aitasks/t55_x.md" || true)"
    g "$fxa" append --only-if-running "$rida" 55 docs_updated fail \
        run="$rida" attempt="$atta" type=machine >/dev/null
    assert_eq "[$backend] begin-procedure returns a run its closer can close" \
        "$((before + 1))" "$(grep -c 'status=fail' "$fxa/aitasks/t55_x.md" || true)"
done

# --- 4d. concurrent double-begin still opens exactly one run (t1262) --------
# The live-run check and the append must happen under ONE hold of the per-task
# lock, or two racing dispatches each open a run.
fx6="$(new_fixture)"; write_task "$fx6" 60 docs_updated
g "$fx6" begin-procedure 60 docs_updated >"$fx6/c1.out" 2>/dev/null &
g "$fx6" begin-procedure 60 docs_updated >"$fx6/c2.out" 2>/dev/null &
wait
assert_eq "concurrent begin-procedure opens exactly one running marker" \
    "1" "$(grep -c 'status=running' "$fx6/aitasks/t60_x.md" || true)"
assert_eq "both concurrent callers name the same run id" \
    "$(sed -n 's/^RUN_ID://p' "$fx6/c1.out")" "$(sed -n 's/^RUN_ID://p' "$fx6/c2.out")"

# --- 4e. full begin-to-close parity across backends (t1262) -----------------
# AIT_GATES_BACKEND=python must cover the RUNNING block too, not just the closer.
# The generated run id embeds a second-resolution timestamp, so the cross-fixture
# comparison masks it: everything behavioral survives (statuses, attempts, body
# lines, and the -<gate>-a<N> suffix that carries the attempt).
if [[ -n "$PY" ]]; then
    norm() { sed -n '/## Gate Runs/,$p' "$1" \
             | sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z/<TS>/g'; }
    lifecycle() {  # <fixture> <id>
        local d="$1" id="$2" bp rid att
        bp="$(g "$d" begin-procedure "$id" docs_updated 2>/dev/null)"
        rid="$(printf '%s\n' "$bp" | sed -n 's/^RUN_ID://p')"
        att="$(printf '%s\n' "$bp" | sed -n 's/^ATTEMPT://p')"
        printf '%s\n' "$bp"
        printf '%s\n' "$(g "$d" begin-procedure "$id" docs_updated 2>/dev/null)"   # adopt
        g "$d" append --only-if-running "$rid" "$id" docs_updated fail \
            run="$rid" attempt="$att" type=machine >/dev/null
        printf '%s\n' "$(g "$d" begin-procedure "$id" docs_updated 2>/dev/null)"
    }
    fx7="$(new_fixture)"; write_task "$fx7" 70 docs_updated
    fx8="$(new_fixture)"; write_task "$fx8" 70 docs_updated
    tr_bash="$(lifecycle "$fx7" 70)"
    tr_py="$(AIT_GATES_BACKEND=python; export AIT_GATES_BACKEND; lifecycle "$fx8" 70)"
    assert_eq "begin-to-close transcript parity (bash vs python)" \
        "$(printf '%s\n' "$tr_bash" | sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z/<TS>/g')" \
        "$(printf '%s\n' "$tr_py"   | sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z/<TS>/g')"
    assert_eq "begin-to-close ledger parity (bash vs python)" \
        "$(norm "$fx7/aitasks/t70_x.md")" "$(norm "$fx8/aitasks/t70_x.md")"
else
    echo "SKIP: no python interpreter resolved — skipping backend parity"
fi

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
