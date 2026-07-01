#!/usr/bin/env bash
# test_gate_orchestrator.sh - Tests for the gate orchestrator engine (t635_11).
#
# Exercises lib/gate_orchestrator.py end-to-end with STUB verifier scripts (no
# real agents): unlocked-set DAG (linear default vs explicit unlocks vs the
# absent-vs-[] distinction), exit-code interpretation (incl. machine exit-4 ->
# error), skip-as-satisfied, retry budget, the stopping heuristic over the code
# change surface (staged/unstaged/untracked), parallel dispatch, dry-run,
# idempotent no-op, human read-side detection, status/exit mismatch, and --gate.
#
# Heuristic-inert tests run in a NON-git dir (code_digest -> None -> never
# stuck, so the retry budget governs); the stopping-heuristic test runs in a git
# fixture so the digest is real.
#
# Run: bash tests/test_gate_orchestrator.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

ORCH="$PROJECT_DIR/.aitask-scripts/lib/gate_orchestrator.py"
GATE="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"
PY="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null; resolve_python 2>/dev/null || echo python3)"

# --- fixture helpers -------------------------------------------------------

new_fixture() {
    local tmp
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/test_orch_XXXXXX")"
    CLEANUP_DIRS+=("$tmp")
    mkdir -p "$tmp/aitasks/metadata"
    echo "$tmp"
}

# make_stub <dir> <name> <exitcode> [append_status]
# Writes a stub verifier that optionally appends a terminal block, then exits.
make_stub() {
    local dir="$1" name="$2" code="$3" append="${4:-}"
    local f="$dir/$name.sh"
    {
        echo '#!/usr/bin/env bash'
        echo '# args: task-id attempt run-id'
        if [[ -n "$append" ]]; then
            echo "\"$GATE\" append \"\$1\" ${name#stub_} $append run=\"\$3\" attempt=\"\$2\" >/dev/null 2>&1 || true"
        fi
        echo "exit $code"
    } > "$f"
    chmod +x "$f"
    echo "$f"
}

write_task() {  # <dir> <id> <gates-csv>
    local dir="$1" id="$2" gates="$3"
    printf -- '---\nstatus: Implementing\ngates: [%s]\n---\nBody.\n' "$gates" \
        > "$dir/aitasks/t${id}_x.md"
}

orch() {  # <dir> <id> [flags...]
    # Run with cwd = the fixture dir so code_digest sees the fixture's git state
    # (or no git for heuristic-inert fixtures), NOT the surrounding aitasks repo.
    local dir="$1" id="$2"; shift 2
    ( cd "$dir" && TASK_DIR="$dir/aitasks" "$PY" "$ORCH" run "$dir/aitasks/t${id}_x.md" \
        --task-id "$id" --registry "$dir/aitasks/metadata/gates.yaml" "$@" 2>&1 )
}

status_of() {  # <dir> <id>
    TASK_DIR="$1/aitasks" "$GATE" status "$2" 2>/dev/null
}

count_status() {  # <dir> <id> <status-token>
    local c; c="$(grep -c "status=$3" "$1/aitasks/t${2}_x.md" 2>/dev/null)"
    echo "${c:-0}"
}

# ============================================================
# Test 1: no gates declared -> no-op
# ============================================================
test_no_gates() {
    echo "=== Test 1: no gates declared ==="
    local d; d="$(new_fixture)"
    printf -- '---\nstatus: Implementing\n---\nBody.\n' > "$d/aitasks/t10_x.md"
    echo "gates: {}" > "$d/aitasks/metadata/gates.yaml"
    local out; out="$(orch "$d" 10)"
    assert_contains "no gates -> nothing to do" "No gates declared" "$out"
}

# ============================================================
# Test 2 + 2b: unlocked-set DAG (linear / fan-out / absent-vs-[])
# ============================================================
test_unlocked_dag() {
    echo "=== Test 2: unlocked-set DAG ==="
    local d; d="$(new_fixture)"
    # linear default: a then b (no unlocks declared)
    cat > "$d/aitasks/metadata/gates.yaml" <<EOF
gates:
  a:
    type: machine
    verifier: x
  b:
    type: machine
    verifier: x
EOF
    write_task "$d" 20 "a, b"
    local u
    u="$(TASK_DIR="$d/aitasks" "$PY" "$ORCH" unlocked "$d/aitasks/t20_x.md" --registry "$d/aitasks/metadata/gates.yaml")"
    assert_eq "linear default: only first gate unlocked" "a" "$u"

    # explicit fan-out: a unlocks [b, c]
    cat > "$d/aitasks/metadata/gates.yaml" <<EOF
gates:
  a:
    type: machine
    verifier: x
    unlocks: [b, c]
  b:
    type: machine
    verifier: x
  c:
    type: machine
    verifier: x
EOF
    write_task "$d" 21 "a, b, c"
    TASK_DIR="$d/aitasks" "$GATE" append 21 a pass >/dev/null 2>&1
    u="$(TASK_DIR="$d/aitasks" "$PY" "$ORCH" unlocked "$d/aitasks/t21_x.md" --registry "$d/aitasks/metadata/gates.yaml" | sort | tr '\n' ' ')"
    assert_eq "fan-out: a-pass unlocks b and c together" "b c " "$u"

    echo "=== Test 2b: absent vs explicit [] ==="
    # 'a' has explicit unlocks: [] (terminal); 'b' absent (linear) -> b unlocks nothing-after either
    cat > "$d/aitasks/metadata/gates.yaml" <<EOF
gates:
  a:
    type: machine
    verifier: x
    unlocks: []
  b:
    type: machine
    verifier: x
EOF
    write_task "$d" 22 "a, b"
    # a is terminal (unlocks nothing); b is absent->linear but nothing precedes it via a.
    # So initially both a and b have no predecessors -> both unlocked? No: b's linear
    # predecessor is whatever lists b in unlocks. a declares []=terminal, so a does NOT
    # unlock b. b is absent so its successor is (nothing after b). Predecessors of b =
    # {p | b in successors(p)} = {} -> b has no predecessors -> unlocked. a unlocked too.
    u="$(TASK_DIR="$d/aitasks" "$PY" "$ORCH" unlocked "$d/aitasks/t22_x.md" --registry "$d/aitasks/metadata/gates.yaml" | sort | tr '\n' ' ')"
    assert_eq "explicit [] makes a terminal (does not gate b); both root-unlocked" "a b " "$u"
}

# ============================================================
# Test 3: exit-code interpretation (0/1/2/3) + machine exit 4 -> error
# ============================================================
test_exit_codes() {
    echo "=== Test 3: exit codes ==="
    local d; d="$(new_fixture)"
    local code status
    for pair in "0:pass" "1:fail" "2:skip" "3:error" "4:error"; do
        code="${pair%%:*}"; status="${pair##*:}"
        local stub; stub="$(make_stub "$d" "stub_g" "$code")"
        cat > "$d/aitasks/metadata/gates.yaml" <<EOF
gates:
  g:
    type: machine
    verifier: $stub
EOF
        write_task "$d" "3$code" "g"
        orch "$d" "3$code" >/dev/null
        assert_contains "machine exit $code -> $status" "g: $status" "$(status_of "$d" "3$code")"
    done
}

# ============================================================
# Test 3b: skip is terminal-satisfied (unlocks successors, archive ALL_PASS)
# ============================================================
test_skip_satisfied() {
    echo "=== Test 3b: skip is terminal-satisfied ==="
    local d; d="$(new_fixture)"
    local skipper passer
    skipper="$(make_stub "$d" "stub_a" 2)"   # a -> skip
    passer="$(make_stub "$d" "stub_b" 0)"    # b -> pass
    cat > "$d/aitasks/metadata/gates.yaml" <<EOF
gates:
  a:
    type: machine
    verifier: $skipper
  b:
    type: machine
    verifier: $passer
EOF
    write_task "$d" 30 "a, b"
    orch "$d" 30 >/dev/null
    assert_contains "skipped predecessor unlocks successor -> b ran (pass)" "b: pass" "$(status_of "$d" 30)"
    local ar; ar="$(TASK_DIR="$d/aitasks" "$GATE" archive-ready 30)"
    assert_eq "skip does not block archive" "ALL_PASS" "$ar"
}

# ============================================================
# Test 4: retry within budget (heuristic-inert in a non-git dir)
# ============================================================
test_retry_budget() {
    echo "=== Test 4: retry within budget (max_retries=2 -> 3 attempts) ==="
    local d; d="$(new_fixture)"   # NOT a git repo -> stopping heuristic inert
    local failer; failer="$(make_stub "$d" "stub_g" 1)"
    cat > "$d/aitasks/metadata/gates.yaml" <<EOF
gates:
  g:
    type: machine
    verifier: $failer
    max_retries: 2
EOF
    write_task "$d" 40 "g"
    orch "$d" 40 >/dev/null
    assert_eq "exactly max_retries+1 = 3 fail attempts" "3" "$(count_status "$d" 40 fail)"
}

# ============================================================
# Test 5: stopping heuristic over the code surface (git fixture)
# ============================================================
test_stopping_heuristic() {
    echo "=== Test 5: stopping heuristic (code surface: unstaged/staged/untracked) ==="
    local d; d="$(new_fixture)"
    ( cd "$d" && git init -q && git config user.email t@t && git config user.name t \
        && echo seed > code.txt && git add -A && git commit -qm init )
    local failer; failer="$(make_stub "$d" "stub_g" 1)"
    cat > "$d/aitasks/metadata/gates.yaml" <<EOF
gates:
  g:
    type: machine
    verifier: $failer
    max_retries: 20
EOF
    write_task "$d" 50 "g"
    # No code change -> heuristic stops at 2 fails per dispatch (NOT the budget).
    orch "$d" 50 >/dev/null
    assert_eq "deterministic fail stops at 2 (heuristic), not budget" "2" "$(count_status "$d" 50 fail)"

    # UNSTAGED code change flips the digest -> eligible again (+2 fails = 4).
    ( cd "$d" && echo change1 >> code.txt )
    orch "$d" 50 >/dev/null
    assert_eq "unstaged change re-enables the gate (4 fails)" "4" "$(count_status "$d" 50 fail)"

    # STAGED change flips the digest -> eligible again (+2 = 6).
    ( cd "$d" && echo change2 >> code.txt && git add code.txt )
    orch "$d" 50 >/dev/null
    assert_eq "staged change re-enables the gate (6 fails)" "6" "$(count_status "$d" 50 fail)"

    # NEW UNTRACKED file flips the digest -> eligible again (+2 = 8).
    ( cd "$d" && echo newfile > brand_new.txt )
    orch "$d" 50 >/dev/null
    assert_eq "untracked file re-enables the gate (8 fails)" "8" "$(count_status "$d" 50 fail)"

    # A pure gate-run append (the ledger churn) does NOT flip the digest: re-run
    # with no code change -> heuristic holds, still 8.
    orch "$d" 50 >/dev/null
    assert_eq "ledger-only churn does NOT re-enable (still 8)" "8" "$(count_status "$d" 50 fail)"
}

# ============================================================
# Test 6 + 6b + 6c: parallel dispatch, idempotent terminal, mismatch
# ============================================================
test_parallel_and_reconcile() {
    echo "=== Test 6: parallel dispatch ==="
    local d; d="$(new_fixture)"
    local p1 p2
    p1="$(make_stub "$d" "stub_x" 0)"; p2="$(make_stub "$d" "stub_y" 0)"
    cat > "$d/aitasks/metadata/gates.yaml" <<EOF
gates:
  x:
    type: machine
    verifier: $p1
    unlocks: [y]
  y:
    type: machine
    verifier: $p2
EOF
    write_task "$d" 60 "x, y"
    orch "$d" 60 --max-parallel 2 >/dev/null
    assert_contains "parallel: x passed" "x: pass" "$(status_of "$d" 60)"
    assert_contains "parallel: y passed" "y: pass" "$(status_of "$d" 60)"

    echo "=== Test 6b: idempotent terminal append (verifier self-appends) ==="
    local d2; d2="$(new_fixture)"
    local selfpass; selfpass="$(make_stub "$d2" "stub_g" 0 pass)"  # appends pass AND exits 0
    cat > "$d2/aitasks/metadata/gates.yaml" <<EOF
gates:
  g:
    type: machine
    verifier: $selfpass
EOF
    write_task "$d2" 61 "g"
    orch "$d2" 61 >/dev/null
    # Exactly one terminal pass block (engine's only-if-running no-ops).
    assert_eq "verifier self-append leaves exactly one pass block" "1" "$(count_status "$d2" 61 pass)"

    echo "=== Test 6c: status/exit mismatch -> error correction ==="
    local d3; d3="$(new_fixture)"
    local liar; liar="$(make_stub "$d3" "stub_g" 1 pass)"  # appends pass BUT exits 1
    cat > "$d3/aitasks/metadata/gates.yaml" <<EOF
gates:
  g:
    type: machine
    verifier: $liar
EOF
    write_task "$d3" 62 "g"
    local out; out="$(orch "$d3" 62)"
    assert_contains "mismatch derived status is error, not pass" "g: error" "$(status_of "$d3" 62)"
    assert_contains "mismatch is reported as malformed" "malformed" "$out"
}

# ============================================================
# Test 7: dry-run appends nothing
# ============================================================
test_dry_run() {
    echo "=== Test 7: dry-run ==="
    local d; d="$(new_fixture)"
    local p; p="$(make_stub "$d" "stub_g" 0)"
    cat > "$d/aitasks/metadata/gates.yaml" <<EOF
gates:
  g:
    type: machine
    verifier: $p
EOF
    write_task "$d" 70 "g"
    local before; before="$(md5sum "$d/aitasks/t70_x.md" 2>/dev/null || shasum "$d/aitasks/t70_x.md")"
    local out; out="$(orch "$d" 70 --dry-run)"
    local after; after="$(md5sum "$d/aitasks/t70_x.md" 2>/dev/null || shasum "$d/aitasks/t70_x.md")"
    assert_contains "dry-run reports the decision tree" "Dry run" "$out"
    assert_eq "dry-run appends nothing (file unchanged)" "$before" "$after"
}

# ============================================================
# Test 8: idempotent no-op on all-pass
# ============================================================
test_idempotent() {
    echo "=== Test 8: idempotent no-op on all-pass ==="
    local d; d="$(new_fixture)"
    local p; p="$(make_stub "$d" "stub_g" 0)"
    cat > "$d/aitasks/metadata/gates.yaml" <<EOF
gates:
  g:
    type: machine
    verifier: $p
EOF
    write_task "$d" 80 "g"
    orch "$d" 80 >/dev/null
    local n1; n1="$(grep -c 'gate:g' "$d/aitasks/t80_x.md")"
    local out; out="$(orch "$d" 80)"
    local n2; n2="$(grep -c 'gate:g' "$d/aitasks/t80_x.md")"
    assert_contains "all-pass reports ready for archive" "All gates satisfied" "$out"
    assert_eq "re-run on all-pass appends nothing" "$n1" "$n2"
}

# ============================================================
# Test 9: human gate read-side (pending -> pass), never self-signals
# ============================================================
test_human_gate() {
    echo "=== Test 9: human gate read-side detection ==="
    local d; d="$(new_fixture)"
    mkdir -p "$d/sig"
    cat > "$d/aitasks/metadata/gates.yaml" <<EOF
gates:
  review:
    type: human
    signal_target: "$d/sig/<task-id>-review.signed"
EOF
    write_task "$d" 90 "review"
    orch "$d" 90 >/dev/null
    assert_contains "absent signal -> pending" "review: pending" "$(status_of "$d" 90)"
    # engine never created the signal file:
    [[ -e "$d/sig/t90-review.signed" ]] && { echo "FAIL: engine self-signalled"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); } \
        || { PASS=$((PASS+1)); TOTAL=$((TOTAL+1)); }
    touch "$d/sig/t90-review.signed"
    orch "$d" 90 >/dev/null
    assert_contains "present signal -> pass" "review: pass" "$(status_of "$d" 90)"
}

# ============================================================
# Test 9b: human-gate signal FRESHNESS (code-bound witness) — t635_15
#   A witness carries the code_digest it was signed against. A witness whose
#   digest no longer matches the current code (stale) is re-pended, NOT passed;
#   a fresh witness passes and records a signed_digest note. Needs a git fixture
#   (real digest); the witness dir is gitignored (mirrors .aitask-gates/) so the
#   witness file itself does not perturb the digest.
# ============================================================
test_human_gate_freshness() {
    echo "=== Test 9b: human-gate signal freshness (code-bound) ==="
    local d; d="$(new_fixture)"
    ( cd "$d" && git init -q && git config user.email t@t && git config user.name t \
        && echo seed > code.txt && echo 'sig/' > .gitignore \
        && git add -A && git commit -qm init )
    mkdir -p "$d/sig"
    cat > "$d/aitasks/metadata/gates.yaml" <<EOF
gates:
  review:
    type: human
    signal_target: "$d/sig/<task-id>-review.signed"
EOF
    write_task "$d" 91 "review"
    local sig="$d/sig/t91-review.signed"
    local cur; cur="$( cd "$d" && "$PY" "$ORCH" code-digest )"

    # STALE witness (recorded digest != current) -> re-pend, NOT pass.
    printf 'signer=tester\ncode_digest=deadbeefdeadbeef\n' > "$sig"
    local out; out="$(orch "$d" 91)"
    assert_contains "stale witness -> pending" "review: pending" "$out"
    assert_contains "stale witness -> stale-signature note" "stale signature" "$out"
    assert_eq "stale witness -> no pass block" "0" "$(count_status "$d" 91 pass)"

    # FRESH witness (recorded digest == current) -> pass with signed_digest note.
    printf 'signer=tester\ncode_digest=%s\n' "$cur" > "$sig"
    orch "$d" 91 >/dev/null
    assert_contains "fresh witness -> pass" "review: pass" "$(status_of "$d" 91)"
    assert_contains "fresh pass records signed_digest note" "signed_digest:$cur" \
        "$(cat "$d/aitasks/t91_x.md")"
}

# ============================================================
# Test 9c: an already-recorded human pass is NOT re-pended (concern 3) — t635_15
#   A task with a direct ledger `pass` for a human gate and NO signal file must
#   not gain a spurious `pending` block on a subsequent `ait gates run` (a
#   satisfied gate is never re-observed).
# ============================================================
test_human_gate_no_repend() {
    echo "=== Test 9c: already-passed human gate is not re-pended ==="
    local d; d="$(new_fixture)"
    cat > "$d/aitasks/metadata/gates.yaml" <<EOF
gates:
  review:
    type: human
    signal_target: "$d/sig/<task-id>-review.signed"
EOF
    write_task "$d" 92 "review"
    # Simulate the attended direct-record: a human `pass` with no signal file.
    TASK_DIR="$d/aitasks" "$GATE" append 92 review pass type=human >/dev/null
    orch "$d" 92 >/dev/null
    assert_contains "already passed -> stays pass" "review: pass" "$(status_of "$d" 92)"
    assert_eq "no spurious pending appended" "0" "$(count_status "$d" 92 pending)"
}

# ============================================================
# Test 10: --gate force-run + predecessor guard
# ============================================================
test_gate_force() {
    echo "=== Test 10: --gate force-run ==="
    local d; d="$(new_fixture)"
    local p; p="$(make_stub "$d" "stub_g" 0)"
    cat > "$d/aitasks/metadata/gates.yaml" <<EOF
gates:
  g:
    type: machine
    verifier: $p
EOF
    write_task "$d" 100 "g"
    orch "$d" 100 >/dev/null   # g passes
    orch "$d" 100 --gate g >/dev/null   # force re-run a passed gate
    assert_eq "--gate force-runs a passed gate again (2 pass blocks)" "2" "$(count_status "$d" 100 pass)"

    # predecessor guard: b force-run refused when a (its predecessor) not satisfied
    local d2; d2="$(new_fixture)"
    local pb; pb="$(make_stub "$d2" "stub_b" 0)"
    cat > "$d2/aitasks/metadata/gates.yaml" <<EOF
gates:
  a:
    type: machine
    verifier: x
    unlocks: [b]
  b:
    type: machine
    verifier: $pb
EOF
    write_task "$d2" 101 "a, b"
    local out; out="$(orch "$d2" 101 --gate b)"
    assert_contains "--gate refuses when predecessor unsatisfied" "predecessors not satisfied" "$out"
    assert_eq "no b block was appended" "0" "$(count_status "$d2" 101 pass)"
}

# ============================================================
# Test 11: ait gates unlocked prints the unlocked set
# ============================================================
test_unlocked_cli() {
    echo "=== Test 11: unlocked CLI ==="
    local d; d="$(new_fixture)"
    cat > "$d/aitasks/metadata/gates.yaml" <<EOF
gates:
  g:
    type: machine
    verifier: x
EOF
    write_task "$d" 110 "g"
    local u; u="$(TASK_DIR="$d/aitasks" "$PY" "$ORCH" unlocked "$d/aitasks/t110_x.md" --registry "$d/aitasks/metadata/gates.yaml")"
    assert_eq "unlocked prints the runnable gate" "g" "$u"
}

# --- Run ---
test_no_gates
test_unlocked_dag
test_exit_codes
test_skip_satisfied
test_retry_budget
test_stopping_heuristic
test_parallel_and_reconcile
test_dry_run
test_idempotent
test_human_gate
test_human_gate_freshness
test_human_gate_no_repend
test_gate_force
test_unlocked_cli

for dir in "${CLEANUP_DIRS[@]}"; do rm -rf "$dir"; done

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
