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
GATE_SH="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"
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

gate_sh() {  # <dir> <verb> <task-id>
    local dir="$1"; shift
    ( cd "$dir" && TASK_DIR="$dir/aitasks" "$GATE_SH" "$@" 2>/dev/null )
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
# Test 1b: config-value FORMS survive the shared resolver
# ============================================================
# _gate_config_values is the one reader on the code path of all three gates
# (t1605 pre-phase mitigation `pin_command_resolution`). Test 1 above only
# exercises the bare-scalar form, so the two forms an extraction could silently
# drop -- a QUOTED scalar and a BLOCK list -- are pinned here.
test_config_value_forms() {
    echo "=== Test 1b: quoted-scalar and block-list command forms ==="
    local d

    # quoted scalar
    d="$(new_fixture)"; write_task "$d" 14
    printf 'verify_build: "true"\n' | write_config "$d"
    run_verifier "$d" "$BUILD" 14 1 "rquoted"
    assert_eq "forms: quoted scalar resolves and passes" "0" "$RC"
    assert_contains "forms: quoted scalar ledger pass" "status=pass" "$(cat "$d/aitasks/t14_x.md")"

    # block list
    d="$(new_fixture)"; write_task "$d" 15
    cat > "$d/aitasks/metadata/project_config.yaml" <<'EOF'
verify_build:
  - "true"
  - "true"
EOF
    run_verifier "$d" "$BUILD" 15 1 "rblock"
    assert_eq "forms: block list resolves and passes" "0" "$RC"
    assert_contains "forms: block list ledger pass" "status=pass" "$(cat "$d/aitasks/t15_x.md")"
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

# ============================================================
# Test 7: gate_command_exit_contract - a command's exit 2 means "did not run"
# ============================================================
# t1605. Opt-in PER CONFIG KEY: exit 2 is a skip only for a key listed in
# project_config.yaml's gate_command_exit_contract. Rows a-e run per verifier
# with that verifier's OWN key, because each wrapper passes its own <config_key>
# into run_command_gate and the opt-in match is against that argument -- a
# wrapper-specific key or invocation slip would otherwise leave test_command
# recording `fail` while the shared build path passes.
test_command_exit_contract() {
    echo "=== Test 7: exit-2 skip contract (per verifier) ==="
    # rows: <label> <verifier> <own-key> <gate-name> <a-different-valid-key>
    local rows=(
        "build|$BUILD|verify_build|build_verified|test_command"
        "tests|$TESTS|test_command|tests_pass|lint_command"
        "lint|$LINT|lint_command|lint|verify_build"
    )
    local row label v key gate other d
    for row in "${rows[@]}"; do
        IFS='|' read -r label v key gate other <<<"$row"

        # (a) exit 2 with NO opt-in -> fail (today's behaviour preserved)
        d="$(new_fixture)"; write_task "$d" 70
        printf '%s: "exit 2"\n' "$key" | write_config "$d"
        run_verifier "$d" "$v" 70 1 "rnoopt"
        assert_eq "$label a: exit 2 without opt-in -> exit 1" "1" "$RC"
        assert_contains "$label a: ledger fail" "status=fail" "$(cat "$d/aitasks/t70_x.md")"

        # (b) exit 2 WITH opt-in -> skip
        d="$(new_fixture)"; write_task "$d" 71
        printf '%s: "exit 2"\ngate_command_exit_contract: [%s]\n' "$key" "$key" | write_config "$d"
        run_verifier "$d" "$v" 71 1 "ropt"
        assert_eq "$label b: exit 2 with opt-in -> exit 2" "2" "$RC"
        assert_contains "$label b: ledger skip" "status=skip" "$(cat "$d/aitasks/t71_x.md")"
        assert_contains "$label b: result names the exit code" "exit 2" "$(cat "$d/aitasks/t71_x.md")"
        assert_contains "$label b: result is command-driven, not 'no command'" \
            "command reported skip" "$(cat "$d/aitasks/t71_x.md")"

        # (c) opt-in lists a DIFFERENT valid key -> no opt-in for this one
        d="$(new_fixture)"; write_task "$d" 72
        printf '%s: "exit 2"\ngate_command_exit_contract: [%s]\n' "$key" "$other" | write_config "$d"
        run_verifier "$d" "$v" 72 1 "rother"
        assert_eq "$label c: opt-in is per key -> exit 1" "1" "$RC"
        assert_contains "$label c: ledger fail" "status=fail" "$(cat "$d/aitasks/t72_x.md")"

        # (d) exit 1 under opt-in still fails (reachable rejection probe)
        d="$(new_fixture)"; write_task "$d" 73
        printf '%s: "exit 1"\ngate_command_exit_contract: [%s]\n' "$key" "$key" | write_config "$d"
        run_verifier "$d" "$v" 73 1 "rone"
        assert_eq "$label d: exit 1 under opt-in -> exit 1" "1" "$RC"
        assert_contains "$label d: ledger fail" "status=fail" "$(cat "$d/aitasks/t73_x.md")"

        # (e) an unexpected non-zero is NOT laundered into a skip
        d="$(new_fixture)"; write_task "$d" 74
        printf '%s: "exit 3"\ngate_command_exit_contract: [%s]\n' "$key" "$key" | write_config "$d"
        run_verifier "$d" "$v" 74 1 "rthree"
        assert_eq "$label e: exit 3 under opt-in -> exit 1" "1" "$RC"
        assert_contains "$label e: ledger fail" "status=fail" "$(cat "$d/aitasks/t74_x.md")"
        assert_eq "$label e: no skip recorded" "0" "$(count_status "$d" 74 skip)"
    done
}

# ============================================================
# Test 8: multi-command aggregation under the exit contract
# ============================================================
# any fail -> fail (short-circuits); else any skip -> skip; else pass.
#
# NOTE on the fixtures: a BLOCK list's items keep their surrounding quotes
# (read_yaml_list strips them only on the inline [a, b] form), so a
# multi-word command is written unquoted here -- `- "exit 2"` would reach
# bash as the single word `exit 2` and die with 127. Single-word items such
# as `- "false"` are unaffected. See t1605's Final Implementation Notes.
test_exit_contract_aggregation() {
    echo "=== Test 8: skip/fail aggregation over a command list ==="
    local d ran

    # (f) skip among passes -> skip, and it does NOT short-circuit
    d="$(new_fixture)"; write_task "$d" 80
    cat > "$d/aitasks/metadata/project_config.yaml" <<'EOF'
verify_build:
  - "true"
  - exit 2
  - touch RAN_THIRD
gate_command_exit_contract: [verify_build]
EOF
    run_verifier "$d" "$BUILD" 80 1 "ragg1"
    assert_eq "f: skip among passes -> exit 2" "2" "$RC"
    assert_contains "f: ledger skip" "status=skip" "$(cat "$d/aitasks/t80_x.md")"
    ran="$([[ -f "$d/RAN_THIRD" ]] && echo ran || echo stopped)"
    assert_eq "f: a skip does NOT short-circuit the list" "ran" "$ran"

    # (g) a fail AFTER a skip still wins
    d="$(new_fixture)"; write_task "$d" 81
    cat > "$d/aitasks/metadata/project_config.yaml" <<'EOF'
verify_build:
  - exit 2
  - "false"
gate_command_exit_contract: [verify_build]
EOF
    run_verifier "$d" "$BUILD" 81 1 "ragg2"
    assert_eq "g: fail beside a skip -> exit 1" "1" "$RC"
    assert_contains "g: ledger fail" "status=fail" "$(cat "$d/aitasks/t81_x.md")"
    assert_eq "g: no skip recorded" "0" "$(count_status "$d" 81 skip)"

    # (h) a fail still short-circuits
    d="$(new_fixture)"; write_task "$d" 82
    cat > "$d/aitasks/metadata/project_config.yaml" <<'EOF'
verify_build:
  - "false"
  - touch RAN_SECOND
gate_command_exit_contract: [verify_build]
EOF
    run_verifier "$d" "$BUILD" 82 1 "ragg3"
    assert_eq "h: fail first -> exit 1" "1" "$RC"
    ran="$([[ -f "$d/RAN_SECOND" ]] && echo ran || echo stopped)"
    assert_eq "h: a fail still short-circuits" "stopped" "$ran"

    # (i) the two skips stay distinguishable in result=
    d="$(new_fixture)"; write_task "$d" 83
    run_verifier "$d" "$BUILD" 83 1 "rnone"
    assert_eq "i: no command configured -> exit 2" "2" "$RC"
    assert_contains "i: result says 'no verify_build configured'" \
        "no verify_build configured" "$(cat "$d/aitasks/t83_x.md")"
    assert_not_contains "i: not the command-driven wording" \
        "command reported skip" "$(cat "$d/aitasks/t83_x.md")"

    # (j) BLOCK-list opt-in form (items keep their quotes -> normalization)
    d="$(new_fixture)"; write_task "$d" 84
    cat > "$d/aitasks/metadata/project_config.yaml" <<'EOF'
verify_build: "exit 2"
gate_command_exit_contract:
  - "verify_build"
EOF
    run_verifier "$d" "$BUILD" 84 1 "rblockopt"
    assert_eq "j: block-list opt-in -> exit 2" "2" "$RC"
    assert_contains "j: ledger skip" "status=skip" "$(cat "$d/aitasks/t84_x.md")"
}

# ============================================================
# Test 9: an unrecognized opt-in key is ignored BUT reported
# ============================================================
# A typo such as `tests_command` must not look identical to "not opted in":
# under contention that is the hardest state to diagnose. It never changes a
# verdict, and it is surfaced as a `Note:` on the appended gate-run block.
test_exit_contract_unknown_key() {
    echo "=== Test 9: unrecognized gate_command_exit_contract key ==="
    local d note="unrecognized key(s): tests_command"

    # (k) one typo alongside a valid entry: the valid one still works
    d="$(new_fixture)"; write_task "$d" 90
    printf 'verify_build: "exit 2"\ngate_command_exit_contract: [tests_command, verify_build]\n' \
        | write_config "$d"
    run_verifier "$d" "$BUILD" 90 1 "runk1"
    assert_eq "k: valid entry still opts in -> exit 2" "2" "$RC"
    assert_contains "k: ledger skip" "status=skip" "$(cat "$d/aitasks/t90_x.md")"
    assert_contains "k: typo reported on the block" "$note" "$(cat "$d/aitasks/t90_x.md")"

    # (l) ONLY a typo: no opt-in (fail), and the diagnostic is present -- this is
    #     precisely the state otherwise indistinguishable from "not opted in"
    d="$(new_fixture)"; write_task "$d" 91
    printf 'verify_build: "exit 2"\ngate_command_exit_contract: [tests_command]\n' \
        | write_config "$d"
    run_verifier "$d" "$BUILD" 91 1 "runk2"
    assert_eq "l: typo does not opt in -> exit 1" "1" "$RC"
    assert_contains "l: ledger fail" "status=fail" "$(cat "$d/aitasks/t91_x.md")"
    assert_contains "l: typo reported on the block" "$note" "$(cat "$d/aitasks/t91_x.md")"

    # (m) a VALID key another verifier owns is NOT reported as unknown
    d="$(new_fixture)"; write_task "$d" 92
    printf 'test_command: "exit 2"\ngate_command_exit_contract: [verify_build]\n' \
        | write_config "$d"
    run_verifier "$d" "$TESTS" 92 1 "runk3"
    assert_eq "m: other verifier's key -> no opt-in here, exit 1" "1" "$RC"
    assert_not_contains "m: no unknown-key note" "unrecognized key" \
        "$(cat "$d/aitasks/t92_x.md")"
}

# ============================================================
# Test 10: GATE_COMMAND_KEYS must not drift from the wrappers
# ============================================================
# The constant is what decides whether an opt-in entry is a typo. A fourth
# verifier added without extending it would silently REJECT a legitimate opt-in,
# so derive the truth from the wrappers and compare.
test_gate_command_keys_no_drift() {
    echo "=== Test 10: GATE_COMMAND_KEYS matches the wrappers ==="
    local constant declared
    constant="$(
        SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
        # shellcheck disable=SC1090
        . "$PROJECT_DIR/.aitask-scripts/lib/gate_verifier_lib.sh"
        printf '%s\n' $GATE_COMMAND_KEYS | sort | tr '\n' ' '
    )"
    declared="$(grep -h '^run_command_gate ' "$PROJECT_DIR"/.aitask-scripts/aitask_gate_*.sh \
                | awk '{print $3}' | sort -u | tr '\n' ' ')"
    assert_eq "drift: constant equals the wrappers' config keys" "$declared" "$constant"
}

# ============================================================
# Test 11: a command-driven skip unblocks dependents (end-to-end)
# ============================================================
# Through the REAL entry point (the orchestrator) on `tests_pass` -- the gate
# this is actually about (blocks_dependents: true, max_retries: 1). `skip` is in
# gate_ledger.SATISFIED_STATUSES, so dependents unblock and archival is not held.
test_exit_contract_unblocks_dependents() {
    echo "=== Test 11: exit-2 skip unblocks dependents (tests_pass) ==="
    local d out
    _mk() {  # <id> <test_command-value> [opt-in-line]
        d="$(new_fixture)"
        cat > "$d/aitasks/metadata/gates.yaml" <<'EOF'
gates:
  tests_pass:
    type: machine
    verifier: aitask-gate-tests-pass
    blocks_dependents: true
    max_retries: 1
EOF
        write_task "$d" "$1" "tests_pass"
        { printf 'test_command: "%s"\n' "$2"; [[ -n "${3:-}" ]] && printf '%s\n' "$3"; } \
            > "$d/aitasks/metadata/project_config.yaml"
    }

    # command declares "did not run" -> skip, no retry, dependents released
    _mk 110 "exit 2" "gate_command_exit_contract: [test_command]"
    out="$(orch "$d" 110)"
    assert_contains "e2e skip: orchestrator reports skip" "tests_pass: skip" "$out"
    assert_eq "e2e skip: exactly one terminal skip" "1" "$(count_status "$d" 110 skip)"
    assert_eq "e2e skip: never retried into a fail" "0" "$(count_status "$d" 110 fail)"
    assert_eq "e2e skip: dependents released" "SATISFIED" "$(gate_sh "$d" deps-unblock 110)"
    assert_eq "e2e skip: archival not held" "ALL_PASS" "$(gate_sh "$d" archive-ready 110)"

    # NEGATIVE CONTROL: a real failure still blocks both
    _mk 111 "exit 1" "gate_command_exit_contract: [test_command]"
    orch "$d" 111 >/dev/null
    assert_eq "e2e fail: no skip recorded" "0" "$(count_status "$d" 111 skip)"
    assert_eq "e2e fail: dependents blocked" "BLOCKED:tests_pass" "$(gate_sh "$d" deps-unblock 111)"
    assert_eq "e2e fail: archival blocked" "BLOCKED:tests_pass" "$(gate_sh "$d" archive-ready 111)"
}

# ============================================================
# Test 12: recorded status and returned exit code always agree
# ============================================================
# t1605 post-phase mitigation `pin_status_exitcode_agreement`. The orchestrator
# treats the exit code as authoritative and appends an `error` correction when a
# verifier's own appended status disagrees with it. Drive the check from the
# RECORDED PAIR so a future edit that records `skip` while returning 1 fails
# here rather than silently tripping that path on a blocks_dependents gate.
test_status_exitcode_agreement() {
    echo "=== Test 12: appended status agrees with returned exit code ==="
    # rows: <label> <config-body> ; each exercises one of the four outcomes
    local d recorded expected
    _agree() {  # <label> <id> <expected-status>
        recorded="$(grep -o 'status=[a-z]*' "$d/aitasks/t${2}_x.md" | tail -1)"
        recorded="${recorded#status=}"
        case "$RC" in
            0) expected=pass ;;
            1) expected=fail ;;
            2) expected=skip ;;
            *) expected="<unmapped:$RC>" ;;
        esac
        assert_eq "$1: map_exit($RC) == recorded status" "$expected" "$recorded"
    }

    d="$(new_fixture)"; write_task "$d" 120
    printf 'verify_build: "true"\n' | write_config "$d"
    run_verifier "$d" "$BUILD" 120 1 "ra1"; _agree "agree pass" 120

    d="$(new_fixture)"; write_task "$d" 121
    printf 'verify_build: "false"\n' | write_config "$d"
    run_verifier "$d" "$BUILD" 121 1 "ra2"; _agree "agree fail" 121

    d="$(new_fixture)"; write_task "$d" 122
    run_verifier "$d" "$BUILD" 122 1 "ra3"; _agree "agree skip(no command)" 122

    d="$(new_fixture)"; write_task "$d" 123
    printf 'verify_build: "exit 2"\ngate_command_exit_contract: [verify_build]\n' | write_config "$d"
    run_verifier "$d" "$BUILD" 123 1 "ra4"; _agree "agree skip(command-driven)" 123
}

# --- Run ---
test_each_verifier
test_config_value_forms
test_command_list
test_sidecar_capture
test_orchestrator_integration
test_seam_primitive
test_workflow_wiring_text
test_command_exit_contract
test_exit_contract_aggregation
test_exit_contract_unknown_key
test_gate_command_keys_no_drift
test_exit_contract_unblocks_dependents
test_status_exitcode_agreement

for dir in "${CLEANUP_DIRS[@]}"; do rm -rf "$dir"; done

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
