#!/usr/bin/env bash
# test_syncer_upgrade_handoff.sh - Launcher-side upgrade handoff (t1223_3).
#
# `ait syncer` cannot upgrade its own repo by spawning: the upgrade replaces
# .aitask-scripts/ underneath the running TUI. Instead the app writes a request
# and exits, and aitask_syncer.sh runs the upgrade afterwards. That request
# crosses a Python -> shell boundary and ends in a command that rewrites
# framework files, so this suite treats it as untrusted input: every case below
# asserts either a refusal (non-zero exit, `ait` never invoked) or an ordering /
# cleanup property the design depends on.
#
# The script under test has no --source-only guard, so it is exercised
# end-to-end with a stubbed interpreter (via AIT_PYTHON, the first candidate in
# resolve_python) and a stub `ait` in a fake repo.
#
# Run: bash tests/test_syncer_upgrade_handoff.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SYNCER="$PROJECT_DIR/.aitask-scripts/aitask_syncer.sh"

PASS=0; FAIL=0; TOTAL=0
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

REAL_PYTHON="$(command -v python3)"
[[ -n "$REAL_PYTHON" ]] || { echo "python3 not found"; exit 1; }

SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT

# --- fixtures -------------------------------------------------------------

# A believable aitasks project root: the wrapper's revalidation requires the
# canonical marker file plus an executable ./ait.
REPO="$SCRATCH/fake_repo"
mkdir -p "$REPO/aitasks/metadata"
printf 'name: fake\n' > "$REPO/aitasks/metadata/project_config.yaml"

# Stub `ait`: records that it ran, and captures the two properties the design
# promises hold by the time it executes.
cat > "$REPO/ait" <<'AIT'
#!/usr/bin/env bash
{
    echo "AIT $*"
    if [[ -n "${AIT_SYNCER_HANDOFF:-}" && -e "$AIT_SYNCER_HANDOFF" ]]; then
        echo "REQUEST_STILL_PRESENT"
    fi
    if [[ -n "${AIT_SYNCER_HANDOFF:-}" && -d "$(dirname "$AIT_SYNCER_HANDOFF")" ]]; then
        echo "HANDOFF_DIR_STILL_PRESENT"
    fi
    if [[ -f "$AIT_TEST_SCRATCH/app_done" ]]; then
        echo "AFTER_APP_EXIT"
    else
        echo "BEFORE_APP_EXIT"
    fi
} >> "$AIT_TEST_LOG"
exit 0
AIT
chmod +x "$REPO/ait"

# Stub interpreter. Delegates every real `-c` job to the system python3 (the
# version probe and the wrapper's own JSON parse must genuinely work), pretends
# the TUI dependencies are installed, and stands in for the app itself.
mkdir -p "$SCRATCH/bin"
cat > "$SCRATCH/bin/python" <<STUB
#!/usr/bin/env bash
if [[ "\$1" == "-c" ]]; then
    case "\$2" in
        *"import textual"*|*"import yaml"*) exit 0 ;;
        *no_dupes*)
            # The wrapper's handoff parse. An optional pause widens the window
            # between "request read into memory" and "upgrade exec'd" so a test
            # can land a signal inside it deterministically.
            if [[ -n "\${AIT_TEST_PARSE_SLEEP:-}" ]]; then
                touch "\$AIT_TEST_SCRATCH/parsing"
                sleep "\$AIT_TEST_PARSE_SLEEP"
            fi
            exec "$REAL_PYTHON" "\$@"
            ;;
        *) exec "$REAL_PYTHON" "\$@" ;;
    esac
fi
case "\$*" in
    *syncer_app.py*)
        echo "APP" >> "\$AIT_TEST_LOG"
        if [[ -n "\${AIT_TEST_REQUEST:-}" ]]; then
            printf '%s' "\$AIT_TEST_REQUEST" > "\$AIT_SYNCER_HANDOFF"
        fi
        # Recorded so a test can assert the private dir is gone afterwards.
        echo "\$AIT_SYNCER_HANDOFF" > "\$AIT_TEST_SCRATCH/handoff_path"
        if [[ -n "\${AIT_TEST_APP_SLEEP:-}" ]]; then sleep "\$AIT_TEST_APP_SLEEP"; fi
        # Last action before exiting: the stub \`ait\` checks for this marker to
        # prove the upgrade ran only after Python was gone.
        touch "\$AIT_TEST_SCRATCH/app_done"
        exit "\${AIT_TEST_APP_RC:-0}"
        ;;
esac
exec "$REAL_PYTHON" "\$@"
STUB
chmod +x "$SCRATCH/bin/python"

# --- harness --------------------------------------------------------------

LOG=""
RUN_RC=0

# run_syncer <request-json-or-empty> [extra env assignments...]
run_syncer() {
    local request="$1"; shift || true
    rm -f "$SCRATCH/app_done" "$SCRATCH/handoff_path"
    LOG="$SCRATCH/run.log"
    : > "$LOG"
    RUN_RC=0
    env AIT_PYTHON="$SCRATCH/bin/python" \
        AIT_TEST_LOG="$LOG" \
        AIT_TEST_SCRATCH="$SCRATCH" \
        AIT_TEST_REQUEST="$request" \
        "$@" \
        bash "$SYNCER" >/dev/null 2>&1 || RUN_RC=$?
}

log_text() { cat "$LOG"; }

# A request whose root/version are the fixture's, i.e. the happy path.
valid_request() {
    printf '{"root": "%s", "version": "latest"}' "$REPO"
}

echo "=== syncer upgrade handoff ==="

# --- 1. no request: clean exit, no upgrade, status propagated -------------

run_syncer ""
assert_eq "no request: wrapper exits 0" "0" "$RUN_RC"
assert_not_contains "no request: ait is never invoked" "AIT" "$(log_text)"

run_syncer "" AIT_TEST_APP_RC=3
assert_eq "no request: the app's exit status propagates" "3" "$RUN_RC"

# --- 2. happy path --------------------------------------------------------

run_syncer "$(valid_request)"
assert_contains "valid request runs ait upgrade" "AIT upgrade latest" "$(log_text)"
assert_not_contains "request file is unlinked before the upgrade runs" \
    "REQUEST_STILL_PRESENT" "$(log_text)"
assert_not_contains "private handoff dir is removed before the upgrade runs" \
    "HANDOFF_DIR_STILL_PRESENT" "$(log_text)"
assert_contains "the upgrade runs only after the app process exited" \
    "AFTER_APP_EXIT" "$(log_text)"
HANDOFF_PATH="$(cat "$SCRATCH/handoff_path")"
assert_file_not_exists "request file is gone after the run" "$HANDOFF_PATH"
assert_dir_not_exists "private handoff dir is gone after the run" \
    "$(dirname "$HANDOFF_PATH")"

# The wrapper owns the path: it must be inside a private 0700 dir, not a
# location the app or an attacker chose.
run_syncer "" AIT_TEST_APP_RC=0
HANDOFF_PATH="$(cat "$SCRATCH/handoff_path")"
assert_contains "handoff path is wrapper-chosen" "/request.json" "$HANDOFF_PATH"

# --- 3. inbound AIT_SYNCER_HANDOFF is overwritten, never read -------------

ATTACKER="$SCRATCH/attacker.json"
valid_request > "$ATTACKER"
run_syncer "" AIT_SYNCER_HANDOFF="$ATTACKER"
assert_not_contains "an inbound AIT_SYNCER_HANDOFF is ignored, not read" \
    "AIT" "$(log_text)"
assert_file_exists "the attacker-named file is left untouched" "$ATTACKER"
HANDOFF_PATH="$(cat "$SCRATCH/handoff_path")"
assert_not_contains "the app is handed the wrapper's path, not the inbound one" \
    "attacker.json" "$HANDOFF_PATH"

# --- 4. revalidation: bad root -------------------------------------------

NOT_A_REPO="$SCRATCH/not_a_repo"
mkdir -p "$NOT_A_REPO"
run_syncer "$(printf '{"root": "%s", "version": "latest"}' "$NOT_A_REPO")"
assert_exit_nonzero_rc "root without the project marker is refused" "$RUN_RC"
assert_not_contains "refused root: ait is never invoked" "AIT" "$(log_text)"

run_syncer '{"root": "relative/path", "version": "latest"}'
assert_exit_nonzero_rc "non-absolute root is refused" "$RUN_RC"
assert_not_contains "relative root: ait is never invoked" "AIT" "$(log_text)"

# A root that looks right but has no executable ./ait.
NO_AIT="$SCRATCH/no_ait"
mkdir -p "$NO_AIT/aitasks/metadata"
printf 'name: x\n' > "$NO_AIT/aitasks/metadata/project_config.yaml"
run_syncer "$(printf '{"root": "%s", "version": "latest"}' "$NO_AIT")"
assert_exit_nonzero_rc "root without an executable ait is refused" "$RUN_RC"
assert_not_contains "no ait binary: nothing is invoked" "AIT" "$(log_text)"

# --- 5. revalidation: bad version ----------------------------------------

CANARY="$SCRATCH/pwned"
rm -f "$CANARY"
run_syncer "$(printf '{"root": "%s", "version": "; touch %s"}' "$REPO" "$CANARY")"
assert_exit_nonzero_rc "injected version is refused" "$RUN_RC"
assert_file_not_exists "injected version does not execute" "$CANARY"
assert_not_contains "injected version: ait is never invoked" "AIT" "$(log_text)"

run_syncer "$(printf '{"root": "%s", "version": "v1.2.3"}' "$REPO")"
assert_exit_nonzero_rc "a leading v is refused (upgrade takes bare semver)" "$RUN_RC"

run_syncer "$(printf '{"root": "%s", "version": "1.2.3"}' "$REPO")"
assert_contains "a pinned version is accepted" "AIT upgrade 1.2.3" "$(log_text)"

# --- 6. the request is data, never code ----------------------------------

# If any part of the pipeline sourced or evaled the request text, this root
# value would create the canary.
CANARY2="$SCRATCH/sourced_canary"
rm -f "$CANARY2"
run_syncer "$(printf '{"root": "%s\\"; touch %s; \\"", "version": "latest"}' "$REPO" "$CANARY2")"
assert_file_not_exists "request content is never sourced or evaled" "$CANARY2"
assert_exit_nonzero_rc "a bogus root is refused, not merely inert" "$RUN_RC"
assert_not_contains "bogus root: ait is never invoked" "AIT" "$(log_text)"

# --- 7. strict shape (contract B: exactly two members) --------------------

# Proving nothing was executed is NOT the same as proving the input was
# refused: each of these must exit non-zero with ait untouched.
refuse_shape() {
    local label="$1" request="$2"
    run_syncer "$request"
    assert_exit_nonzero_rc "$label is refused" "$RUN_RC"
    assert_not_contains "$label: ait is never invoked" "AIT" "$(log_text)"
}

refuse_shape "an extra member" \
    "$(printf '{"root": "%s", "version": "latest", "extra": 1}' "$REPO")"
refuse_shape "a missing version" "$(printf '{"root": "%s"}' "$REPO")"
refuse_shape "a missing root" '{"version": "latest"}'
refuse_shape "a duplicate key" \
    "$(printf '{"root": "%s", "root": "/etc", "version": "latest"}' "$REPO")"
refuse_shape "a non-string version" "$(printf '{"root": "%s", "version": 1.2}' "$REPO")"
refuse_shape "a newline in root" \
    "$(printf '{"root": "%s\\nX", "version": "latest"}' "$REPO")"
refuse_shape "a JSON array" '["root", "version"]'
refuse_shape "malformed JSON" '{"root": '

# Positive control for the whole group: the exact two-member object works.
run_syncer "$(valid_request)"
assert_contains "positive control: the exact two-member request is accepted" \
    "AIT upgrade latest" "$(log_text)"

# --- 8. cleanup on signal -------------------------------------------------

rm -f "$SCRATCH/app_done" "$SCRATCH/handoff_path"
: > "$SCRATCH/run.log"
env AIT_PYTHON="$SCRATCH/bin/python" \
    AIT_TEST_LOG="$SCRATCH/run.log" \
    AIT_TEST_SCRATCH="$SCRATCH" \
    AIT_TEST_REQUEST="" \
    AIT_TEST_APP_SLEEP=5 \
    bash "$SYNCER" >/dev/null 2>&1 &
SYNCER_PID=$!
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    [[ -s "$SCRATCH/handoff_path" ]] && break
    sleep 0.2
done
kill -INT "$SYNCER_PID" 2>/dev/null || true
wait "$SYNCER_PID" 2>/dev/null || true
sleep 0.3
if [[ -s "$SCRATCH/handoff_path" ]]; then
    assert_dir_not_exists "the private handoff dir is removed after SIGINT" \
        "$(dirname "$(cat "$SCRATCH/handoff_path")")"
else
    FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
    echo "FAIL: could not capture the handoff dir for the SIGINT case"
fi

# --- 9. a signal after the request is read must CANCEL, not upgrade -------

# The dangerous window is between "request read into memory" and "upgrade
# exec'd": deleting the request file there cleans up nothing that still
# matters, so a trap that merely tidies up and returns would let bash carry on
# into the upgrade — turning a cancellation into a framework rewrite. The
# signal is sent to the wrapper alone (not the process group) so the parse it
# is waiting on completes normally and the request really is in memory.
rm -f "$SCRATCH/app_done" "$SCRATCH/handoff_path" "$SCRATCH/parsing"
: > "$SCRATCH/run.log"
env AIT_PYTHON="$SCRATCH/bin/python" \
    AIT_TEST_LOG="$SCRATCH/run.log" \
    AIT_TEST_SCRATCH="$SCRATCH" \
    AIT_TEST_REQUEST="$(valid_request)" \
    AIT_TEST_PARSE_SLEEP=2 \
    bash "$SYNCER" >/dev/null 2>&1 &
SYNCER_PID=$!
for _ in $(seq 1 50); do
    [[ -f "$SCRATCH/parsing" ]] && break
    sleep 0.1
done
SIGNALLED_RC=0
if [[ -f "$SCRATCH/parsing" ]]; then
    kill -TERM "$SYNCER_PID" 2>/dev/null || true
    wait "$SYNCER_PID" 2>/dev/null || SIGNALLED_RC=$?
    assert_not_contains "SIGTERM after the request is read never runs the upgrade" \
        "AIT" "$(cat "$SCRATCH/run.log")"
    assert_eq "SIGTERM exits 143 rather than resuming" "143" "$SIGNALLED_RC"
    if [[ -s "$SCRATCH/handoff_path" ]]; then
        assert_dir_not_exists "the handoff dir is removed on the signalled path" \
            "$(dirname "$(cat "$SCRATCH/handoff_path")")"
    fi
else
    kill -TERM "$SYNCER_PID" 2>/dev/null || true
    wait "$SYNCER_PID" 2>/dev/null || true
    FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
    echo "FAIL: could not reach the parse window for the signal case"
fi

# --- summary --------------------------------------------------------------

echo ""
echo "=== Results ==="
echo "PASS: $PASS / $TOTAL"
if [[ $FAIL -gt 0 ]]; then
    echo "FAIL: $FAIL"
    exit 1
fi
echo "All tests passed."
exit 0
