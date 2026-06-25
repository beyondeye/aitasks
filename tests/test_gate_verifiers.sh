#!/usr/bin/env bash
# test_gate_verifiers.sh - Tests for the project-command machine-gate verifiers
# (t635_12): aitask_gate_build.sh / aitask_gate_tests_pass.sh / aitask_gate_lint.sh
# and the shared lib/gate_verifier_lib.sh.
#
# Covers, per verifier: command pass (exit 0), command fail (exit 1), command
# absent/null (exit 2 = skip), a list of commands stopping at the first failure,
# and sidecar-log capture. Plus the Step-9 SEAM primitive the task-workflow verify
# branch keys on: `ait gates run` prints the `No gates declared` sentinel and
# appends nothing for an undeclared task, records a real verifier run for a
# declared one, exhausts the retry budget on repeated failure (durable contract:
# two terminal fails + gate unsatisfied), and exits NONZERO on an infrastructure
# failure (missing task file) without printing the sentinel.
#
# Heuristic-inert: fixtures are NON-git dirs, so code_digest -> None and the
# stopping heuristic stays inert -> the retry budget governs deterministically.
#
# Run: bash tests/test_gate_verifiers.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

ORCH="$PROJECT_DIR/.aitask-scripts/lib/gate_orchestrator.py"
BUILD="$PROJECT_DIR/.aitask-scripts/aitask_gate_build.sh"
TESTS="$PROJECT_DIR/.aitask-scripts/aitask_gate_tests_pass.sh"
LINT="$PROJECT_DIR/.aitask-scripts/aitask_gate_lint.sh"
PY="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null; resolve_python 2>/dev/null || echo python3)"

# --- fixture helpers -------------------------------------------------------

new_fixture() {
    local tmp
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/test_gatever_XXXXXX")"
    CLEANUP_DIRS+=("$tmp")
    mkdir -p "$tmp/aitasks/metadata"
    echo "$tmp"
}

write_task() {  # <dir> <id> [gates-csv]
    local dir="$1" id="$2" gates="${3:-}"
    if [[ -n "$gates" ]]; then
        printf -- '---\nstatus: Implementing\ngates: [%s]\n---\nBody.\n' "$gates" \
            > "$dir/aitasks/t${id}_x.md"
    else
        printf -- '---\nstatus: Implementing\n---\nBody.\n' > "$dir/aitasks/t${id}_x.md"
    fi
}

write_config() {  # <dir> ; config body piped on stdin
    cat > "$1/aitasks/metadata/project_config.yaml"
}

# Run a verifier with cwd = fixture (so it reads the fixture's project_config.yaml
# and writes .aitask-gates/ there) and TASK_DIR set (so aitask_gate.sh resolves
# the task file). Echoes nothing; sets global RC.
run_verifier() {  # <dir> <verifier> <task-id> <attempt> <run-id>
    local dir="$1" v="$2"; shift 2
    ( cd "$dir" && TASK_DIR="$dir/aitasks" "$v" "$@" )
    RC=$?
}

orch() {  # <dir> <id> [flags...]
    local dir="$1" id="$2"; shift 2
    ( cd "$dir" && TASK_DIR="$dir/aitasks" "$PY" "$ORCH" run "$dir/aitasks/t${id}_x.md" \
        --task-id "$id" --registry "$dir/aitasks/metadata/gates.yaml" "$@" 2>&1 )
}

count_status() {  # <dir> <id> <status-token>
    local c; c="$(grep -c "status=$3" "$1/aitasks/t${2}_x.md" 2>/dev/null)"
    echo "${c:-0}"
}

# ============================================================
# Test 1: per-verifier pass / fail / skip (parametrized)
# ============================================================
test_each_verifier() {
    echo "=== Test 1: build/tests/lint pass, fail, skip ==="
    # rows: <label> <verifier> <config-key> <gate-name>
    local rows=(
        "build|$BUILD|verify_build|build_verified"
        "tests|$TESTS|test_command|tests_pass"
        "lint|$LINT|lint_command|lint"
    )
    local row label v key gate d task
    for row in "${rows[@]}"; do
        IFS='|' read -r label v key gate <<<"$row"

        # pass: command exits 0
        d="$(new_fixture)"; write_task "$d" 10
        printf '%s: "true"\n' "$key" | write_config "$d"
        run_verifier "$d" "$v" 10 1 "rpass"
        assert_eq "$label pass: exit 0" "0" "$RC"
        assert_contains "$label pass: ledger pass" "status=pass" "$(cat "$d/aitasks/t10_x.md")"
        task="$([[ -f "$d/.aitask-gates/10/${gate}_rpass.log" ]] && echo yes || echo no)"
        assert_eq "$label pass: sidecar log written" "yes" "$task"

        # fail: command exits non-zero
        d="$(new_fixture)"; write_task "$d" 11
        printf '%s: "false"\n' "$key" | write_config "$d"
        run_verifier "$d" "$v" 11 1 "rfail"
        assert_eq "$label fail: exit 1" "1" "$RC"
        assert_contains "$label fail: ledger fail" "status=fail" "$(cat "$d/aitasks/t11_x.md")"

        # skip: key absent (no project_config.yaml at all)
        d="$(new_fixture)"; write_task "$d" 12
        run_verifier "$d" "$v" 12 1 "rskip"
        assert_eq "$label skip(absent): exit 2" "2" "$RC"
        assert_contains "$label skip(absent): ledger skip" "status=skip" "$(cat "$d/aitasks/t12_x.md")"
        assert_contains "$label skip(absent): log says not applicable" "not applicable" \
            "$(cat "$d/.aitask-gates/12/${gate}_rskip.log")"

        # skip: key present but null
        d="$(new_fixture)"; write_task "$d" 13
        printf '%s: null\n' "$key" | write_config "$d"
        run_verifier "$d" "$v" 13 1 "rnull"
        assert_eq "$label skip(null): exit 2" "2" "$RC"
        assert_contains "$label skip(null): ledger skip" "status=skip" "$(cat "$d/aitasks/t13_x.md")"
    done
}

# ============================================================
# Test 2: list of commands stops at first failure (build, representative)
# ============================================================
test_command_list() {
    echo "=== Test 2: list stops at first failure ==="
    local d; d="$(new_fixture)"; write_task "$d" 20
    cat > "$d/aitasks/metadata/project_config.yaml" <<'EOF'
verify_build:
  - "true"
  - "false"
  - "touch SHOULD_NOT_RUN"
EOF
    run_verifier "$d" "$BUILD" 20 1 "rlist"
    assert_eq "list: exit 1 (second cmd failed)" "1" "$RC"
    assert_contains "list: ledger fail" "status=fail" "$(cat "$d/aitasks/t20_x.md")"
    local ran; ran="$([[ -f "$d/SHOULD_NOT_RUN" ]] && echo ran || echo stopped)"
    assert_eq "list: third command did NOT run" "stopped" "$ran"
}

# ============================================================
# Test 3: sidecar log captures command output
# ============================================================
test_sidecar_capture() {
    echo "=== Test 3: sidecar log captures output ==="
    local d; d="$(new_fixture)"; write_task "$d" 30
    printf 'verify_build: "echo HELLO_MARKER"\n' > "$d/aitasks/metadata/project_config.yaml"
    run_verifier "$d" "$BUILD" 30 1 "rlog"
    assert_eq "sidecar: exit 0" "0" "$RC"
    assert_contains "sidecar: captures stdout" "HELLO_MARKER" \
        "$(cat "$d/.aitask-gates/30/build_verified_rlog.log")"
}

# ============================================================
# Test 4: integration through the orchestrator (real verifier resolved)
# ============================================================
test_orchestrator_integration() {
    echo "=== Test 4: orchestrator runs the real build verifier ==="
    # pass
    local d; d="$(new_fixture)"
    cat > "$d/aitasks/metadata/gates.yaml" <<'EOF'
gates:
  build_verified:
    type: machine
    verifier: aitask-gate-build
    max_retries: 1
EOF
    write_task "$d" 40 "build_verified"
    printf 'verify_build: "true"\n' > "$d/aitasks/metadata/project_config.yaml"
    local out; out="$(orch "$d" 40)"
    assert_contains "integration pass: reported pass" "build_verified: pass" "$out"
    assert_contains "integration pass: ledger pass" "status=pass" "$(cat "$d/aitasks/t40_x.md")"

    # retry exhaustion — DURABLE contract: two terminal fails, gate unsatisfied.
    # (NON-git fixture => digest None => retry budget alone governs.)
    d="$(new_fixture)"
    cat > "$d/aitasks/metadata/gates.yaml" <<'EOF'
gates:
  build_verified:
    type: machine
    verifier: aitask-gate-build
    max_retries: 1
EOF
    write_task "$d" 41 "build_verified"
    printf 'verify_build: "false"\n' > "$d/aitasks/metadata/project_config.yaml"
    orch "$d" 41 >/dev/null
    assert_eq "retry: exactly two terminal fail runs" "2" "$(count_status "$d" 41 fail)"
    assert_eq "retry: gate never passed" "0" "$(count_status "$d" 41 pass)"
}

# ============================================================
# Test 5: Step-9 SEAM primitive (sentinel discriminator + exit-status guard)
# ============================================================
test_seam_primitive() {
    echo "=== Test 5: Step-9 seam primitive ==="
    # (a) no gates declared -> sentinel + NO append
    local d; d="$(new_fixture)"
    echo "gates: {}" > "$d/aitasks/metadata/gates.yaml"
    write_task "$d" 50            # no `gates:` frontmatter
    local before out; before="$(cat "$d/aitasks/t50_x.md")"
    out="$(orch "$d" 50)"
    assert_contains "seam: undeclared prints sentinel" "No gates declared; nothing to do." "$out"
    assert_eq "seam: undeclared appends nothing" "$before" "$(cat "$d/aitasks/t50_x.md")"

    # (b) declared gate -> orchestrator records a run (no sentinel)
    d="$(new_fixture)"
    cat > "$d/aitasks/metadata/gates.yaml" <<'EOF'
gates:
  build_verified:
    type: machine
    verifier: aitask-gate-build
EOF
    write_task "$d" 51 "build_verified"
    printf 'verify_build: "true"\n' > "$d/aitasks/metadata/project_config.yaml"
    out="$(orch "$d" 51)"
    assert_not_contains "seam: declared has no sentinel" "No gates declared" "$out"
    assert_contains "seam: declared records a run" "status=pass" "$(cat "$d/aitasks/t51_x.md")"

    # (c) infrastructure failure -> NONZERO exit, no sentinel (Step A guard)
    d="$(new_fixture)"
    echo "gates: {}" > "$d/aitasks/metadata/gates.yaml"
    out="$( cd "$d" && TASK_DIR="$d/aitasks" "$PY" "$ORCH" run "$d/aitasks/t999_missing.md" \
            --task-id 999 --registry "$d/aitasks/metadata/gates.yaml" 2>&1 )"
    local rc=$?
    assert_eq "seam: infra failure exits nonzero" "1" "$rc"
    assert_not_contains "seam: infra failure prints no sentinel" "No gates declared" "$out"
}

# ============================================================
# Test 6: task-workflow Step 9 wires to the SAME engine sentinel
# ============================================================
# Test 5(a) pins the engine's exact sentinel output. This pins the consumer side:
# the task-workflow source must dispatch `ait gates run` and branch on that exact
# literal, so the instructions and the engine can never silently drift apart.
test_workflow_wiring_text() {
    echo "=== Test 6: Step 9 wiring references the engine seam ==="
    local wf="$PROJECT_DIR/.claude/skills/task-workflow/SKILL.md" body
    body="$(cat "$wf")"
    assert_contains "Step 9 dispatches the orchestrator" "ait gates run" "$body"
    assert_contains "Step 9 branches on the exact engine sentinel" \
        "No gates declared; nothing to do." "$body"
}

# --- Run ---
test_each_verifier
test_command_list
test_sidecar_capture
test_orchestrator_integration
test_seam_primitive
test_workflow_wiring_text

for dir in "${CLEANUP_DIRS[@]}"; do rm -rf "$dir"; done

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
