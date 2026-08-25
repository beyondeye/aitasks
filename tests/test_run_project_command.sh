#!/usr/bin/env bash
# test_run_project_command.sh - Tests for .aitask-scripts/aitask_run_project_command.sh
# (t1610): the legacy build-verification helper that runs one project_config.yaml
# command key under the gate exit contract WITHOUT touching a gate ledger.
#
# Four layers, each answering a different question:
#
#   1. The exit table          -- does the helper itself grade a command right?
#   2. Cross-path parity       -- does it agree with the gate verifier, for the
#                                 same fixture? (This is the whole point of the
#                                 task: one rule, two paths, no divergence.)
#   3. End-to-end decision flow -- does the invocation block the PROCEDURE
#                                 documents actually yield those verdicts, run
#                                 from inside a `set -euo pipefail` script? The
#                                 helper can be perfect and the wiring still
#                                 wrong; exit 1/2 are ordinary outcomes here, so
#                                 a naive capture kills the caller.
#   4. Single canonical place  -- is the rule stated once, and is the helper
#                                 reachable from every agent's permission policy?
#
# Heuristic-inert: fixtures are plain temp dirs with no git repo and no task file.
# The helper needs neither.
#
# Run: bash tests/test_run_project_command.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

HELPER="$PROJECT_DIR/.aitask-scripts/aitask_run_project_command.sh"
BUILD="$PROJECT_DIR/.aitask-scripts/aitask_gate_build.sh"
PROC="$PROJECT_DIR/.claude/skills/task-workflow/build-verification.md"

# --- fixture helpers -------------------------------------------------------

new_fixture() {  # [config body]
    local tmp
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/test_runprojcmd_XXXXXX")"
    CLEANUP_DIRS+=("$tmp")
    mkdir -p "$tmp/aitasks/metadata"
    [[ $# -eq 0 ]] || printf '%b' "$1" > "$tmp/aitasks/metadata/project_config.yaml"
    echo "$tmp"
}

# Run the helper with cwd = fixture. Sets RC and OUT (stdout only -- stderr is
# deliberately NOT merged, exactly as the procedure instructs callers).
run_helper() {  # <dir> <args...>
    local dir="$1"; shift
    OUT="$( cd "$dir" && "$HELPER" "$@" 2>/dev/null )"
    RC=$?
}

# Extract one KEY:value line from OUT.
field() {  # <KEY>
    printf '%s\n' "$OUT" | sed -n "s/^$1://p"
}

# ============================================================
# Test 1: the exit table, one row at a time
# ============================================================
test_exit_table() {
    echo "=== Test 1: verdict per command exit code ==="
    local d

    # (A) nothing configured -> skip, and REASON is the ONLY thing separating
    # this from a command-driven skip.
    d="$(new_fixture)"
    run_helper "$d" verify_build
    assert_eq "A: absent key -> rc 2" "2" "$RC"
    assert_eq "A: absent key -> VERDICT skip" "skip" "$(field VERDICT)"
    assert_eq "A: absent key -> REASON none_configured" "none_configured" "$(field REASON)"

    # (B) exit 0 -> pass
    d="$(new_fixture 'verify_build: "true"\n')"
    run_helper "$d" verify_build
    assert_eq "B: exit 0 -> rc 0" "0" "$RC"
    assert_eq "B: exit 0 -> VERDICT pass" "pass" "$(field VERDICT)"
    assert_eq "B: exit 0 -> REASON all_passed" "all_passed" "$(field REASON)"

    # (C) THE REJECTION PROBE: exit 1 under an opt-in is still a fail. If the
    # opt-in ever widened from "the documented skip code" to "non-zero", this is
    # the assertion that catches it.
    d="$(new_fixture 'verify_build: "exit 1"\ngate_command_exit_contract: [verify_build]\n')"
    run_helper "$d" verify_build
    assert_eq "C: exit 1 under opt-in -> rc 1" "1" "$RC"
    assert_eq "C: exit 1 under opt-in -> VERDICT fail" "fail" "$(field VERDICT)"
    assert_eq "C: exit 1 under opt-in -> REASON command_failed" "command_failed" "$(field REASON)"

    # (D) exit 1 without the opt-in -> fail (the opt-in changes nothing here)
    d="$(new_fixture 'verify_build: "exit 1"\n')"
    run_helper "$d" verify_build
    assert_eq "D: exit 1 without opt-in -> rc 1" "1" "$RC"
    assert_eq "D: exit 1 without opt-in -> VERDICT fail" "fail" "$(field VERDICT)"

    # (E) exit 2 WITH the opt-in -> skip, distinguished by REASON
    d="$(new_fixture 'verify_build: "exit 2"\ngate_command_exit_contract: [verify_build]\n')"
    run_helper "$d" verify_build
    assert_eq "E: exit 2 under opt-in -> rc 2" "2" "$RC"
    assert_eq "E: exit 2 under opt-in -> VERDICT skip" "skip" "$(field VERDICT)"
    assert_eq "E: exit 2 under opt-in -> REASON command_skipped" "command_skipped" "$(field REASON)"

    # (F) exit 2 WITHOUT the opt-in -> fail. The negative control for (E): the
    # contract must be opt-in, or `verify_build: make` would launder real build
    # failures into skips.
    d="$(new_fixture 'verify_build: "exit 2"\n')"
    run_helper "$d" verify_build
    assert_eq "F: exit 2 without opt-in -> rc 1" "1" "$RC"
    assert_eq "F: exit 2 without opt-in -> VERDICT fail" "fail" "$(field VERDICT)"

    # (G) an unexpected non-zero is never laundered into a skip
    d="$(new_fixture 'verify_build: "exit 3"\ngate_command_exit_contract: [verify_build]\n')"
    run_helper "$d" verify_build
    assert_eq "G: exit 3 under opt-in -> rc 1" "1" "$RC"
    assert_eq "G: exit 3 under opt-in -> VERDICT fail" "fail" "$(field VERDICT)"

    # (G2) a command that cannot be PARSED never ran, so it must never reach a
    # skip -- bash exits 2 on a syntax error, which collides with the skip code
    # (t1609). Pinned here too because the helper is a second consumer of that
    # guard and would silently inherit a regression in it.
    # The reachable shape from t1609: an inline flow item containing a comma is
    # split, leaving unbalanced-quote fragments that cannot parse.
    d="$(new_fixture)"
    cat > "$d/aitasks/metadata/project_config.yaml" <<'EOF'
verify_build: ["pytest -k 'slow,net'"]
gate_command_exit_contract: [verify_build]
EOF
    run_helper "$d" verify_build
    assert_eq "G2: unparseable under opt-in -> rc 1" "1" "$RC"
    assert_eq "G2: unparseable -> VERDICT fail" "fail" "$(field VERDICT)"
    assert_eq "G2: unparseable -> REASON command_malformed" "command_malformed" "$(field REASON)"
}

# ============================================================
# Test 2: aggregation over a command list
# ============================================================
test_aggregation() {
    echo "=== Test 2: list aggregation (a skip does not short-circuit) ==="
    local d

    # (H) skip THEN fail -> fail. The skip must not stop the list, or a real
    # failure after it would never be seen.
    d="$(new_fixture)"
    cat > "$d/aitasks/metadata/project_config.yaml" <<'EOF'
verify_build:
  - "exit 2"
  - "exit 1"
gate_command_exit_contract: [verify_build]
EOF
    run_helper "$d" verify_build
    assert_eq "H: skip then fail -> rc 1" "1" "$RC"
    assert_eq "H: skip then fail -> VERDICT fail" "fail" "$(field VERDICT)"

    # (I) skip among passes -> skip, and the later command really ran
    d="$(new_fixture)"
    cat > "$d/aitasks/metadata/project_config.yaml" <<'EOF'
verify_build:
  - "exit 2"
  - "touch RAN_AFTER_SKIP"
gate_command_exit_contract: [verify_build]
EOF
    run_helper "$d" verify_build
    assert_eq "I: skip then pass -> rc 2" "2" "$RC"
    assert_eq "I: skip then pass -> VERDICT skip" "skip" "$(field VERDICT)"
    assert_eq "I: the command after the skip actually ran" \
        "ran" "$([[ -f "$d/RAN_AFTER_SKIP" ]] && echo ran || echo missing)"
}

# ============================================================
# Test 3: NOTE, usage errors, and the log
# ============================================================
test_note_usage_and_log() {
    echo "=== Test 3: NOTE line, usage errors, log capture ==="
    local d

    # (J) a bogus opt-in entry is reported but changes no verdict
    d="$(new_fixture 'verify_build: "exit 2"\ngate_command_exit_contract: [tests_command, verify_build]\n')"
    run_helper "$d" verify_build
    assert_eq "J: bogus opt-in entry does not change the verdict" "skip" "$(field VERDICT)"
    assert_contains "J: NOTE names the unrecognized key" "tests_command" "$(field NOTE)"

    # (J2) with no bogus entry there is no NOTE line at all
    d="$(new_fixture 'verify_build: "true"\n')"
    run_helper "$d" verify_build
    assert_not_contains "J2: no NOTE line when the opt-in list is clean" "NOTE:" "$OUT"

    # (K) a bad config key is a USAGE error: rc 3 and NO verdict line. That is
    # how a caller tells "could not evaluate" from any verdict -- an unknown key
    # must never come back as a quiet "nothing configured" skip.
    d="$(new_fixture 'verify_build: "true"\n')"
    run_helper "$d" not_a_real_key
    assert_eq "K: unknown config key -> rc 3" "3" "$RC"
    assert_not_contains "K: unknown config key prints NO VERDICT line" "VERDICT:" "$OUT"

    # (K2) no argument at all is the same usage error
    d="$(new_fixture)"
    run_helper "$d"
    assert_eq "K2: missing config key -> rc 3" "3" "$RC"
    assert_not_contains "K2: missing config key prints NO VERDICT line" "VERDICT:" "$OUT"

    # (K3) a task id that is not a task id never reaches a filesystem path
    d="$(new_fixture 'verify_build: "true"\n')"
    run_helper "$d" verify_build --task-id "../../escape"
    assert_eq "K3: malformed --task-id -> rc 3" "3" "$RC"
    assert_not_contains "K3: malformed --task-id prints NO VERDICT line" "VERDICT:" "$OUT"

    # (L) the command's own output lands in the log, not on stdout
    d="$(new_fixture 'verify_build: "echo HELLO_FROM_BUILD"\n')"
    run_helper "$d" verify_build
    assert_not_contains "L: command output does not pollute stdout" "HELLO_FROM_BUILD" "$OUT"
    assert_contains "L: command output is captured in the log" \
        "HELLO_FROM_BUILD" "$(cd "$d" && cat "$(field LOG)")"

    # (L2) --task-id places the log beside that task's gate logs
    d="$(new_fixture 'verify_build: "true"\n')"
    run_helper "$d" verify_build --task-id 16_2
    assert_contains "L2: --task-id places the log under .aitask-gates/<id>/" \
        ".aitask-gates/16_2/" "$(field LOG)"

    # (M) A log that cannot be created is an INFRASTRUCTURE error, never a
    # verdict. The LOG: path is part of the contract -- the fail branch sends the
    # agent to it for diagnostics -- so reporting any verdict alongside a log
    # that holds nothing is worse than reporting nothing.
    #
    # It is also not merely a missing-diagnostics problem: the runner's parse
    # check redirects to the same file (`bash -n -c "$c" 2>>"$log"`), so an
    # unwritable log makes bash fail on the REDIRECTION and a perfectly valid
    # command is misgraded `command_malformed`. Both fixtures below produced a
    # confident wrong verdict before this guard.
    d="$(new_fixture 'verify_build: "echo DIAG; exit 1"\n')"
    run_helper "$d" verify_build --log /proc/aitask-no-such-dir/output.log
    assert_eq "M: uncreatable log parent -> rc 3" "3" "$RC"
    assert_not_contains "M: uncreatable log prints NO VERDICT line" "VERDICT:" "$OUT"

    # (M2) parent exists but the file cannot be written
    d="$(new_fixture 'verify_build: "echo DIAG; exit 1"\n')"
    run_helper "$d" verify_build --log /proc/output.log
    assert_eq "M2: unwritable log file -> rc 3" "3" "$RC"
    assert_not_contains "M2: unwritable log prints NO VERDICT line" "VERDICT:" "$OUT"

    # (M3) positive control: the SAME command against a writable log grades
    # correctly. Without this, M/M2 would also pass if the helper had simply
    # stopped working -- and it pins the specific misgrade (command_malformed on
    # a valid command) that the redirection failure used to produce.
    d="$(new_fixture 'verify_build: "echo DIAG; exit 1"\n')"
    run_helper "$d" verify_build --log "$d/sub/dir/out.log"
    assert_eq "M3: writable log -> the command is graded normally" "1" "$RC"
    assert_eq "M3: a valid command is NOT misreported as malformed" \
        "command_failed" "$(field REASON)"
    assert_contains "M3: the created log really holds the output" \
        "DIAG" "$(cat "$d/sub/dir/out.log")"
}

# ============================================================
# Test 4: cross-path parity with the gate verifier
# ============================================================
# The acceptance criterion this task exists for, asserted DIRECTLY rather than
# inferred from shared code: for one fixture, the gate verifier and the legacy
# helper must reach the same verdict. If someone re-implements either side, this
# is what fails.
test_cross_path_parity() {
    echo "=== Test 4: gate verifier and legacy helper agree ==="
    local d gate_rc

    _parity() {  # <label> <config-body> <expected-verdict> <expected-rc>
        local label="$1" body="$2" want="$3" want_rc="$4" dd
        dd="$(new_fixture "$body")"
        printf -- '---\nstatus: Implementing\n---\nBody.\n' > "$dd/aitasks/t70_x.md"
        ( cd "$dd" && TASK_DIR="$dd/aitasks" "$BUILD" 70 1 "rparity" ) >/dev/null 2>&1
        gate_rc=$?
        run_helper "$dd" verify_build
        assert_eq "parity($label): gate verifier exit" "$want_rc" "$gate_rc"
        assert_eq "parity($label): helper exit" "$want_rc" "$RC"
        assert_eq "parity($label): helper verdict" "$want" "$(field VERDICT)"
        # The gate side records the same word in its ledger block.
        assert_contains "parity($label): ledger records the same status" \
            "status=$want" "$(cat "$dd/aitasks/t70_x.md")"
    }

    _parity "opted-in exit 2" \
        'verify_build: "exit 2"\ngate_command_exit_contract: [verify_build]\n' skip 2
    _parity "exit 1" \
        'verify_build: "exit 1"\ngate_command_exit_contract: [verify_build]\n' fail 1
    _parity "exit 0" \
        'verify_build: "true"\ngate_command_exit_contract: [verify_build]\n' pass 0
    _parity "exit 2 without opt-in" \
        'verify_build: "exit 2"\n' fail 1
}

# ============================================================
# Test 5: end-to-end decision flow, via the DOCUMENTED invocation
# ============================================================
# Tests 1-4 prove the helper grades correctly; the render tests prove the prose
# references the procedure. Neither exercises the path an agent walks. This does:
# it runs the exact block build-verification.md renders, from inside a
# `set -euo pipefail` script, and asserts the values an agent branches on.
#
# The strict shell is the point, not decoration. `out="$(cmd)"; rc=$?` under
# errexit dies AT THE ASSIGNMENT when cmd exits non-zero -- and exit 1/2 are
# ordinary outcomes here -- so the rejected capture shape cannot reach the second
# line. REACHED_END below is what makes that failure loud instead of a silently
# shorter result set.
DOC_INVOCATION='if bv_out="$(./.aitask-scripts/aitask_run_project_command.sh verify_build --task-id <task_id>)"; then'

test_documented_flow() {
    echo "=== Test 5: end-to-end flow through the documented invocation ==="
    local d driver out

    # The pin: the procedure must document the very shape this test runs. One
    # rendered line, so it cannot be defeated by wrapping.
    assert_contains "flow: procedure documents the if-form capture" \
        "$DOC_INVOCATION" "$(cat "$PROC")"
    assert_contains "flow: procedure names the rejected shape as WRONG" \
        'Do not write `bv_out="$(…)"; bv_rc=$?`' "$(cat "$PROC")"

    _flow() {  # <label> <config-body> <want_rc> <want_verdict> <want_reason>
        local label="$1" body="$2" want_rc="$3" want_v="$4" want_r="$5" dd res
        dd="$(new_fixture "$body")"
        cat > "$dd/driver.sh" <<'DRIVER'
#!/usr/bin/env bash
set -euo pipefail
if bv_out="$(./.aitask-scripts/aitask_run_project_command.sh verify_build --task-id 42)"; then
  bv_rc=0
else
  bv_rc=$?
fi
bv_verdict="$(printf '%s\n' "$bv_out" | sed -n 's/^VERDICT://p')"
bv_reason="$(printf '%s\n' "$bv_out" | sed -n 's/^REASON://p')"
bv_log="$(printf '%s\n' "$bv_out" | sed -n 's/^LOG://p')"
echo "RC=$bv_rc VERDICT=${bv_verdict:-<none>} REASON=${bv_reason:-<none>} LOG=${bv_log:+set}"
echo "REACHED_END"
DRIVER
        chmod +x "$dd/driver.sh"
        mkdir -p "$dd/.aitask-scripts"
        cp "$HELPER" "$dd/.aitask-scripts/"
        cp -r "$PROJECT_DIR/.aitask-scripts/lib" "$dd/.aitask-scripts/"
        res="$( cd "$dd" && ./driver.sh 2>/dev/null )"
        # An errexit regression kills the driver before REACHED_END, which is
        # exactly the failure this row must surface rather than swallow.
        assert_contains "flow($label): driver survived under set -euo pipefail" \
            "REACHED_END" "$res"
        assert_contains "flow($label): rc/verdict/reason as documented" \
            "RC=$want_rc VERDICT=$want_v REASON=$want_r LOG=set" "$res"
    }

    _flow "absent"          ''                                                                2 skip none_configured
    _flow "opted-in exit 2" 'verify_build: "exit 2"\ngate_command_exit_contract: [verify_build]\n' 2 skip command_skipped
    _flow "exit 1"          'verify_build: "exit 1"\ngate_command_exit_contract: [verify_build]\n' 1 fail command_failed

    # skip-then-fail through the documented block: the aggregation rule survives
    # the wiring, not just the helper's unit test.
    d="$(new_fixture)"
    cat > "$d/aitasks/metadata/project_config.yaml" <<'EOF'
verify_build:
  - "exit 2"
  - "exit 1"
gate_command_exit_contract: [verify_build]
EOF
    driver="$d/driver.sh"
    cat > "$driver" <<'DRIVER'
#!/usr/bin/env bash
set -euo pipefail
if bv_out="$(./.aitask-scripts/aitask_run_project_command.sh verify_build --task-id 42)"; then
  bv_rc=0
else
  bv_rc=$?
fi
bv_verdict="$(printf '%s\n' "$bv_out" | sed -n 's/^VERDICT://p')"
echo "RC=$bv_rc VERDICT=$bv_verdict"
echo "REACHED_END"
DRIVER
    chmod +x "$driver"
    mkdir -p "$d/.aitask-scripts"
    cp "$HELPER" "$d/.aitask-scripts/"
    cp -r "$PROJECT_DIR/.aitask-scripts/lib" "$d/.aitask-scripts/"
    out="$( cd "$d" && ./driver.sh 2>/dev/null )"
    assert_contains "flow(skip-then-fail): driver survived" "REACHED_END" "$out"
    assert_contains "flow(skip-then-fail): a skip does not hide a later fail" \
        "RC=1 VERDICT=fail" "$out"

    # Negative control: the SHAPE the procedure rejects must actually break, or
    # the warning above it is decoration and the if-form proves nothing.
    d="$(new_fixture 'verify_build: "exit 2"\ngate_command_exit_contract: [verify_build]\n')"
    cat > "$d/bad_driver.sh" <<'DRIVER'
#!/usr/bin/env bash
set -euo pipefail
bv_out="$(./.aitask-scripts/aitask_run_project_command.sh verify_build --task-id 42)"; bv_rc=$?
echo "RC=$bv_rc"
echo "REACHED_END"
DRIVER
    chmod +x "$d/bad_driver.sh"
    mkdir -p "$d/.aitask-scripts"
    cp "$HELPER" "$d/.aitask-scripts/"
    cp -r "$PROJECT_DIR/.aitask-scripts/lib" "$d/.aitask-scripts/"
    out="$( cd "$d" && ./bad_driver.sh 2>/dev/null )"
    assert_not_contains "flow(negative control): the rejected capture shape DOES die on a skip" \
        "REACHED_END" "$out"
}

# ============================================================
# Test 6: the rule is stated once, and the helper is reachable
# ============================================================
test_single_canonical_place() {
    echo "=== Test 6: single canonical place + allowlist coverage ==="
    local f src

    # The three legacy prose sites must reference the procedure, not restate the
    # run-and-branch rules. "stop on first failure" is the exact wording each of
    # them carried before t1610; its return would mean someone re-inlined the rule.
    for src in \
        ".claude/skills/task-workflow/SKILL.md" \
        ".claude/skills/aitask-pickrem/SKILL.md.j2" \
        ".claude/skills/aitask-pickweb/SKILL.md.j2"
    do
        assert_contains "canonical: $src references the shared procedure" \
            "build-verification.md" "$(cat "$PROJECT_DIR/$src")"
        assert_not_contains "canonical: $src no longer restates the run loop" \
            "stop on first failure" "$(cat "$PROJECT_DIR/$src")"
    done

    # The exit table itself must live in exactly one source file.
    local table_sites
    table_sites=$(grep -rl "key opted in" "$PROJECT_DIR/.aitask-scripts" 2>/dev/null | wc -l)
    assert_eq "canonical: the command-exit table appears in exactly one script" \
        "1" "$table_sites"

    # An unwhitelisted helper does not fail -- it STALLS the consuming procedure
    # on a permission prompt, which is invisible until someone runs it.
    for f in \
        ".claude/settings.local.json" \
        "seed/claude_settings.local.json" \
        "seed/opencode_config.seed.json" \
        ".codex/rules/default.rules" \
        "seed/codex_rules.default.rules"
    do
        TOTAL=$((TOTAL + 1))
        if grep -q "aitask_run_project_command.sh" "$PROJECT_DIR/$f" 2>/dev/null; then
            PASS=$((PASS + 1))
        else
            FAIL=$((FAIL + 1))
            echo "FAIL: aitask_run_project_command.sh missing from allowlist $f"
        fi
    done
}

# --- Run ---
echo "=== test_run_project_command.sh ==="
echo ""

test_exit_table
test_aggregation
test_note_usage_and_log
test_cross_path_parity
test_documented_flow
test_single_canonical_place

for dir in "${CLEANUP_DIRS[@]}"; do rm -rf "$dir"; done

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
