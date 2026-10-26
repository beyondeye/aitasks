#!/usr/bin/env bash
# test_goengines_dashcheck.sh - goengines/ci/dashcheck.sh: the verdict protocol
# (PASS / FAIL:<step> / NOT_RUN never a pass), the step ordering, and the
# container arguments that make it a dash-parity run of the suite (t2154).
# Stub-driven: needs neither docker nor Go. The real run is documented in
# goengines/README.md ("Dash parity").
# Run: bash tests/test_goengines_dashcheck.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0
. "$PROJECT_DIR/tests/lib/asserts.sh"

DASHCHECK="$PROJECT_DIR/goengines/ci/dashcheck.sh"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
BIN="$TMP/bin"
LOG="$TMP/calls.log"
mkdir -p "$BIN"

# Each stub logs one line per invocation (argv, %q-quoted); STUB_* knobs pick
# exit codes and the /bin/sh the probe reports.
cat > "$BIN/go" <<'EOF'
#!/usr/bin/env bash
{ printf 'go'; printf ' %q' "$@"; printf '\n'; } >> "$STUB_LOG"
case "$1" in
    env)
        if [[ -n "${STUB_GOENV_SHORT:-}" ]]; then printf 'linux\n'; exit 0; fi
        printf '%s\n' "${STUB_GOHOSTOS:-linux}" "$STUB_ROOT/goroot" "${STUB_GOCACHE:-$STUB_ROOT/gocache}" "$STUB_ROOT/gomodcache" ;;
    mod) exit "${STUB_MOD_RC:-0}" ;;
esac
EOF
cat > "$BIN/docker" <<'EOF'
#!/usr/bin/env bash
{ printf 'docker'; printf ' %q' "$@"; printf '\n'; } >> "$STUB_LOG"
case "$1" in
    info)  exit "${STUB_INFO_RC:-0}" ;;
    image) exit "${STUB_INSPECT_RC:-0}" ;;
    build) cat > /dev/null; exit "${STUB_BUILD_RC:-0}" ;;
    run)
        case "$*" in
            *"readlink -f /bin/sh"*) echo "${STUB_SH:-/usr/bin/dash}"; echo "go version stub"; exit "${STUB_PROBE_RC:-0}" ;;
            *./ci/preflight.sh*) exit "${STUB_PREFLIGHT_RC:-0}" ;;
            *) exit "${STUB_SUITE_RC:-0}" ;;
        esac ;;
esac
EOF
chmod +x "$BIN/go" "$BIN/docker"

# run_dc <script> [args...]: run it with the stubs plus the STUB_ENV
# assignments; sets out (stdout), rc and resets LOG.
STUB_ENV=()
run_dc() {
    local script="$1"
    shift
    : > "$LOG"
    rc=0
    out="$(env STUB_LOG="$LOG" STUB_ROOT="$TMP" PATH="$BIN:$PATH" \
        AIT_DASHCHECK_DOCKER="${DOCKER_CMD:-$BIN/docker}" ${STUB_ENV[@]+"${STUB_ENV[@]}"} \
        bash "$script" "$@" 2>"$TMP/err")" || rc=$?
}
runs()       { grep -c '^docker run' "$LOG" || true; }
suite_line() { grep '^docker run' "$LOG" | grep -v 'readlink\|preflight\.sh' || true; }

# --- NOT_RUN: exit 3, never PASS, nothing run ------------------------------------
DOCKER_CMD="$TMP/no-such-docker" run_dc "$DASHCHECK"
assert_eq "no docker: verdict" "DASHCHECK:NOT_RUN:no-docker" "$out"
assert_eq "no docker: exit 3" "3" "$rc"
assert_eq "no docker: nothing run" "0" "$(runs)"

STUB_ENV=(STUB_INFO_RC=1); run_dc "$DASHCHECK"
assert_eq "daemon unreachable: verdict" "DASHCHECK:NOT_RUN:docker-unreachable" "$out"
assert_eq "daemon unreachable: exit 3" "3" "$rc"

STUB_ENV=(STUB_GOHOSTOS=darwin); run_dc "$DASHCHECK"
assert_eq "non-linux Go: verdict" "DASHCHECK:NOT_RUN:not-linux" "$out"
assert_eq "non-linux Go: exit 3" "3" "$rc"
assert_eq "non-linux Go: nothing run" "0" "$(runs)"

STUB_ENV=(STUB_GOENV_SHORT=1); run_dc "$DASHCHECK"
assert_eq "short go env output: verdict" "DASHCHECK:NOT_RUN:no-go" "$out"
assert_eq "short go env output: exit 3" "3" "$rc"

: > "$TMP/cache-is-a-file"
STUB_ENV=(STUB_GOCACHE="$TMP/cache-is-a-file"); run_dc "$DASHCHECK"
assert_eq "GOCACHE is a regular file: verdict" "DASHCHECK:NOT_RUN:cache-unusable" "$out"
assert_eq "GOCACHE is a regular file: exit 3" "3" "$rc"
assert_eq "GOCACHE is a regular file: nothing run" "0" "$(runs)"

STUB_ENV=(STUB_MOD_RC=1); run_dc "$DASHCHECK"
assert_eq "modules unavailable: verdict" "DASHCHECK:NOT_RUN:modules-unavailable" "$out"
assert_eq "modules unavailable: exit 3" "3" "$rc"

STUB_ENV=(STUB_INSPECT_RC=1 STUB_BUILD_RC=1); run_dc "$DASHCHECK"
assert_eq "image build fails: verdict" "DASHCHECK:NOT_RUN:image-build-failed" "$out"
assert_eq "image build fails: exit 3" "3" "$rc"
assert_eq "image build fails: nothing run" "0" "$(runs)"
assert_contains_re "image tag is content-addressed" "build -t aitasks-dashcheck:[0-9a-f]{12} -" "$(cat "$LOG")"

STUB_ENV=(STUB_INSPECT_RC=1); run_dc "$DASHCHECK"
assert_eq "image missing: built, then PASS" "DASHCHECK:PASS" "$out"
STUB_ENV=(); run_dc "$DASHCHECK"
assert_not_contains "image present: no build" "docker build" "$(cat "$LOG")"

# --- FAIL: exit 1, later steps not run -------------------------------------------
STUB_ENV=(STUB_SH=/usr/bin/bash); run_dc "$DASHCHECK"
assert_eq "/bin/sh not dash: verdict" "DASHCHECK:FAIL:probe:0" "$out"
assert_eq "/bin/sh not dash: exit 1" "1" "$rc"
assert_eq "/bin/sh not dash: only the probe ran" "1" "$(runs)"

STUB_ENV=(STUB_PROBE_RC=127); run_dc "$DASHCHECK"
assert_eq "probe fails: verdict" "DASHCHECK:FAIL:probe:127" "$out"
assert_eq "probe fails: only the probe ran" "1" "$(runs)"

STUB_ENV=(STUB_PREFLIGHT_RC=1); run_dc "$DASHCHECK"
assert_eq "preflight fails: verdict" "DASHCHECK:FAIL:preflight:1" "$out"
assert_eq "preflight fails: exit 1" "1" "$rc"
assert_eq "preflight fails: suite not run" "" "$(suite_line)"

STUB_ENV=(STUB_SUITE_RC=2); run_dc "$DASHCHECK"
assert_eq "suite fails: verdict" "DASHCHECK:FAIL:suite:2" "$out"
assert_eq "suite fails: exit 1" "1" "$rc"

# --- PASS and the container arguments ---------------------------------------------
STUB_ENV=(); run_dc "$DASHCHECK"
assert_eq "pass: verdict" "DASHCHECK:PASS" "$out"
assert_eq "pass: exit 0" "0" "$rc"
assert_eq "pass: probe, preflight, suite" "3" "$(runs)"
suite="$(suite_line)"
module="$(cd "$PROJECT_DIR/goengines" && pwd -P)"
assert_contains "suite: --init" " --init " "$suite"
assert_contains "suite: no network" " --network none " "$suite"
assert_contains "suite: non-root uid" " --user $(id -u):$(id -g) " "$suite"
assert_contains "suite: module mounted read-only" " -v $module:$module:ro " "$suite"
assert_contains "suite: real tools required" " -e AIT_TESTMAP_REQUIRE_REAL_TOOLS=1 " "$suite"
assert_contains "suite: no toolchain download" " -e GOTOOLCHAIN=local " "$suite"
assert_contains_re "suite: -count=1 then the default ./..." " go test -count=1 \./\.\.\.$" "$suite"
assert_not_contains "suite: no --cpus without --stress" "--cpus" "$suite"
assert_contains "preflight runs in the container" "./ci/preflight.sh" "$(grep '^docker run' "$LOG" | sed -n 2p)"

run_dc "$DASHCHECK" -run X ./internal/procsup/ -count=5
assert_contains_re "user args after -count=1, in order" " go test -count=1 -run X \./internal/procsup/ -count=5$" "$(suite_line)"
assert_not_contains "user args replace ./..." "./..." "$(suite_line)"

run_dc "$DASHCHECK" --stress 2 -- -run X
suite="$(suite_line)"
assert_contains "stress: one cpu" " --cpus 1 " "$suite"
assert_contains_re "stress: 2 loops, then go test -count=1" " dashcheck-stress 2 go test -count=1 -run X$" "$suite"

run_dc "$DASHCHECK" --stress 99
assert_contains "stress: 99 is the largest count" " dashcheck-stress 99 go test" "$(suite_line)"

# 18446744073709551616 wraps to 0 in bash arithmetic: it must be refused
# before any, not run as an unstressed PASS.
for bad in "--stress 0" "--stress x" "--stress" "--stress 100" "--stress 18446744073709551616" "--stress 07"; do
    # shellcheck disable=SC2086  # split on purpose
    run_dc "$DASHCHECK" $bad
    assert_eq "usage: $bad exits 2" "2" "$rc"
    assert_eq "usage: $bad runs nothing" "0" "$(runs)"
done

# --- an unforeseen error still prints a verdict --------------------------------------
# A failing sha256sum stops the image-tag pipeline under errexit, a path no
# explicit verdict covers: the exit trap must report it, never stay silent.
mkdir -p "$TMP/badbin"
printf '#!/usr/bin/env bash\nexit 1\n' > "$TMP/badbin/sha256sum"
chmod +x "$TMP/badbin/sha256sum"
STUB_ENV=(PATH="$TMP/badbin:$BIN:$PATH"); run_dc "$DASHCHECK"
assert_eq "internal error: verdict" "DASHCHECK:FAIL:internal:1" "$out"
assert_eq "internal error: exit 1" "1" "$rc"
assert_eq "internal error: nothing run" "0" "$(runs)"
STUB_ENV=()

# Negative control for the -count=1 assertion: a scratch copy without it must
# fail the same check (the copy needs a ci/ dir of its own; everything is stubbed).
mkdir -p "$TMP/ctl/ci"
sed 's/go test -count=1 /go test /' "$DASHCHECK" > "$TMP/ctl/ci/dashcheck.sh"
assert_eq "control copy was actually patched" "0" "$(grep -c 'go test -count=1' "$TMP/ctl/ci/dashcheck.sh" || true)"
run_dc "$TMP/ctl/ci/dashcheck.sh"
assert_eq "control: still passes" "DASHCHECK:PASS" "$out"
if [[ "$(suite_line)" =~ \ go\ test\ -count=1\ \./\.\.\.$ ]]; then ctl=matched; else ctl=unmatched; fi
assert_eq "control: the -count=1 check catches its removal" "unmatched" "$ctl"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]] || exit 1
