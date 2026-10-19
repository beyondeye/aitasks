#!/usr/bin/env bash
# test_fixture_root.sh - fixture factories must not lose their cleanup
# registration in a `$( )` subshell (t2055).
#
# t2031 found a factory that appended its temp dir to CLEANUP_DIRS and was
# called as `d="$(factory)"`: the append died with the subshell, the suite's
# cleanup never saw the dir, and the suite leaked while reporting green. t2055
# found the same shape in 20 more suites and moved them onto
# tests/lib/fixture_root.sh (one root per suite, registered in the top-level
# shell; every fixture lives under it).
#
# This file checks:
#   1. the library: root creation and registration, fail-closed fixture_mktemp_d,
#      a custom array name, and assert_fixture_registered's negative cases;
#   2. end to end, with a probe TMPDIR: `$(factory)` on the library leaves
#      nothing behind, the old shape leaks (so the probe can see a leak), and a
#      root created after a SKIP exit does not leak on that exit;
#   3. a guard over tests/*.sh and tests/lib/*.sh: no function that appends to
#      a cleanup array (*CLEANUP*, *TMPDIRS*) is called inside `$( )`, plus
#      scanner controls.
#
# Run: bash tests/test_fixture_root.sh

# The negative controls deliberately run assertions in subshells with their own
# counters (SC2030/SC2031); generated suites are single-quoted code (SC2016).
# shellcheck disable=SC2030,SC2031,SC2016
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/scratch_cwd.sh disable=SC1091
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
# shellcheck source=lib/asserts.sh disable=SC1091
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/fixture_root.sh disable=SC1091
. "$PROJECT_DIR/tests/lib/fixture_root.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()
cleanup() {
    local d
    for d in "${CLEANUP_DIRS[@]:-}"; do
        [[ -n "$d" && -d "$d" ]] && rm -rf "$d"
    done
}
trap cleanup EXIT

# assert_fixture_registered run in a subshell with its own counters; prints the
# FAIL count it recorded (1 = the assertion rejected the case).
registered_fails() {
    ( PASS=0; FAIL=0; TOTAL=0; assert_fixture_registered "control" "$1" >/dev/null; printf '%s' "$FAIL" )
}

# ===========================================================================
echo "=== 1. library ==="

fixture_root_init
assert_dir_exists "fixture_root_init creates FIXTURE_ROOT" "$FIXTURE_ROOT"
assert_eq "FIXTURE_ROOT is a physical path" "$(cd "$FIXTURE_ROOT" && pwd -P)" "$FIXTURE_ROOT"
assert_eq "FIXTURE_ROOT is the one entry in CLEANUP_DIRS" "$FIXTURE_ROOT" "${CLEANUP_DIRS[*]}"
assert_eq "FIXTURE_ROOT_ARRAY defaults to CLEANUP_DIRS" "CLEANUP_DIRS" "$FIXTURE_ROOT_ARRAY"

new_probe() {
    local d
    d="$(fixture_mktemp_d test_fxroot)" || return 1
    printf '%s' "$d"
}
d1="$(new_probe)"
assert_fixture_registered "a \$( )-made fixture is registered through the root" "$d1"
assert_contains "fixture_mktemp_d keeps the prefix" "/test_fxroot_" "$d1"

assert_eq "rejects an empty path (vacuous-membership trap)" "1" "$(registered_fails "")"
assert_eq "rejects a missing dir" "1" "$(registered_fails "$FIXTURE_ROOT/nope")"
outside="$(mktemp -d "${TMPDIR:-/tmp}/ait_fxroot_outside_XXXXXX")"
CLEANUP_DIRS+=("$outside")
assert_eq "rejects a dir outside FIXTURE_ROOT (the pre-t2055 shape)" "1" "$(registered_fails "$outside")"
dropped="$( CLEANUP_DIRS=(); registered_fails "$d1" )"
assert_eq "rejects a root that is not in the cleanup array" "1" "$dropped"
unset_root="$( unset FIXTURE_ROOT; registered_fails "$d1" )"
assert_eq "rejects when FIXTURE_ROOT is unset" "1" "$unset_root"

err="$( unset FIXTURE_ROOT; fixture_mktemp_d x 2>&1 >/dev/null )"
out="$( unset FIXTURE_ROOT; fixture_mktemp_d x 2>/dev/null )"; mk_rc=$?
assert_eq "fixture_mktemp_d without a root fails" "1" "$mk_rc"
assert_eq "fixture_mktemp_d without a root prints no path" "" "$out"
assert_contains "fixture_mktemp_d names the missing call" "fixture_root_init" "$err"

custom="$(
    unset FIXTURE_ROOT FIXTURE_ROOT_ARRAY
    TMPDIRS=()
    fixture_root_init TMPDIRS
    ( PASS=0; FAIL=0; TOTAL=0
      assert_fixture_registered "custom" "$(new_probe)" >/dev/null
      printf '%s|%s|%s' "$FAIL" "${#TMPDIRS[@]}" "$FIXTURE_ROOT_ARRAY" )
    rm -rf "$FIXTURE_ROOT"
)"
assert_eq "a custom array name (TMPDIRS) registers and verifies" "0|1|TMPDIRS" "$custom"

# Under `set -e`, a membership check whose last comparison is false must not end
# the suite: the root is often followed by other entries (later registrations,
# or a second root-registered fixture). Both orders, in an errexit child.
errexit_membership() {  # <root_first|root_last> -> "rc|stdout"
    local order="$1" script out rc
    script="$(fixture_mktemp_d errexit)/s.sh"
    sed 's/^|//' > "$script" <<EOF
|set -e
|. "$PROJECT_DIR/tests/lib/asserts.sh"
|. "$PROJECT_DIR/tests/lib/fixture_root.sh"
|PASS=0; FAIL=0; TOTAL=0
|CLEANUP_DIRS=("/nonexistent/first_entry")
|fixture_root_init
|f="\$(fixture_mktemp_d x)"
|[[ "$order" == root_first ]] && CLEANUP_DIRS=("\${CLEANUP_DIRS[@]}" "/nonexistent/later_entry")
|assert_fixture_registered "mixed" "\$f"
|echo "reached PASS=\$PASS FAIL=\$FAIL"
|rm -rf "\$FIXTURE_ROOT"
EOF
    out="$(bash "$script" 2>&1)"; rc=$?
    printf '%s|%s' "$rc" "$out"
}
assert_eq "set -e: root followed by another entry still asserts and continues" \
    "0|reached PASS=1 FAIL=0" "$(errexit_membership root_first)"
assert_eq "set -e: root as the last entry asserts and continues" \
    "0|reached PASS=1 FAIL=0" "$(errexit_membership root_last)"

bad_rc=0
bad_out="$( fixture_root_init 'x;y' 2>&1 )" || bad_rc=$?
assert_eq "an invalid array name is refused" "1" "$bad_rc"
assert_contains "the refusal names the bad array" "invalid array name" "$bad_out"

# ===========================================================================
echo "=== 2. end to end: probe TMPDIR leftovers ==="

# gen_suite <file> <variant>: write a tiny suite. Lines are '|'-prefixed in this
# file so the guard below never reads them as real definitions.
gen_suite() {
    local file="$1" variant="$2" body
    case "$variant" in
        new) body='|mk() { local d; d="$(fixture_mktemp_d e2e)" || return 1; printf "%s" "$d"; }
|fixture_root_init' ;;
        old) body='|mk() {
|    local d; d="$(mktemp -d)"
|    CLEANUP_DIRS+=("$d")
|    printf "%s" "$d"
|}' ;;
    esac
    sed 's/^|//' > "$file" <<EOF
|. "$PROJECT_DIR/tests/lib/asserts.sh"
|. "$PROJECT_DIR/tests/lib/fixture_root.sh"
|PASS=0; FAIL=0; TOTAL=0
|CLEANUP_DIRS=()
|trap 'for d in "\${CLEANUP_DIRS[@]}"; do rm -rf "\$d"; done' EXIT
$body
|a="\$(mk)"; b="\$(mk)"; c="\$(mk)"
|[[ -d "\$a" && -d "\$b" && -d "\$c" ]] || exit 3
EOF
}

# gen_skip_suite <file> <init_before_skip:yes|no>: footer-only cleanup, SKIP exit.
gen_skip_suite() {
    local file="$1" early="$2" early_line="" late_line="|fixture_root_init"
    if [[ "$early" == "yes" ]]; then early_line="|fixture_root_init"; late_line=""; fi
    sed 's/^|//' > "$file" <<EOF
|. "$PROJECT_DIR/tests/lib/asserts.sh"
|. "$PROJECT_DIR/tests/lib/fixture_root.sh"
|PASS=0; FAIL=0; TOTAL=0
|CLEANUP_DIRS=()
$early_line
|[[ -n "\${FORCE_SKIP:-}" ]] && { echo "SKIP: prerequisite missing"; exit 0; }
$late_line
|for d in "\${CLEANUP_DIRS[@]}"; do rm -rf "\$d"; done
EOF
}

# leftovers <script> [env...]: run it under an empty probe TMPDIR; print "rc|count".
leftovers() {
    local script="$1" probe rc n
    shift
    probe="$(fixture_mktemp_d probe)"
    env "$@" TMPDIR="$probe" bash "$script" >/dev/null 2>&1
    rc=$?
    n="$(find "$probe" -mindepth 1 -maxdepth 1 | wc -l | tr -d ' ')"
    printf '%s|%s' "$rc" "$n"
}

gen_dir="$(fixture_mktemp_d gen)"
gen_suite "$gen_dir/new.sh" new
gen_suite "$gen_dir/old.sh" old
assert_eq "\$(factory) on the library: three fixtures, nothing left behind" "0|0" "$(leftovers "$gen_dir/new.sh")"
assert_eq "control: the old shape leaks all three (the probe can see a leak)" "0|3" "$(leftovers "$gen_dir/old.sh")"

gen_skip_suite "$gen_dir/skip_late.sh" no
gen_skip_suite "$gen_dir/skip_early.sh" yes
assert_eq "root created after the SKIP exit: SKIP path leaves nothing" "0|0" "$(leftovers "$gen_dir/skip_late.sh" FORCE_SKIP=1)"
assert_eq "root created after the SKIP exit: full run leaves nothing" "0|0" "$(leftovers "$gen_dir/skip_late.sh")"
assert_eq "control: root created before a footer-only SKIP exit leaks it" "0|1" "$(leftovers "$gen_dir/skip_early.sh" FORCE_SKIP=1)"

# ===========================================================================
echo "=== 3. guard: no cleanup registration inside \$( ) ==="

# Two passes per file. Pass 1: functions defined at column 0 whose body appends
# to a *CLEANUP* / *TMPDIRS* array; a body runs to the next column-0 '}', and a
# one-line definition with balanced braces is its own body. Pass 2: every
# non-comment line calling one of them as `$( name`.
# shellcheck disable=SC2016
SCANNER='
FNR == 1 { infn = "" }
NR == FNR {
    if (match($0, /^(function[ \t]+)?[A-Za-z_][A-Za-z0-9_]*[ \t]*\(\)[ \t]*\{/)) {
        line = $0; name = $0
        sub(/^function[ \t]+/, "", name); sub(/[ \t]*\(.*/, "", name)
        o = gsub(/\{/, "{", line); c = gsub(/\}/, "}", line)
        if (o == c) { if ($0 ~ REG) reg[name] = 1; infn = ""; next }
        infn = name; next
    }
    if (infn != "" && $0 ~ /^}/) { infn = ""; next }
    if (infn != "" && $0 ~ REG) reg[infn] = 1
    next
}
$0 ~ /^[ \t]*#/ { next }
{
    for (n in reg) {
        if ($0 ~ ("\\$\\([ \t]*" n "([^A-Za-z0-9_]|$)")) printf "%s:%d: %s\n", FILENAME, FNR, n
    }
}'
scan() {
    local f
    for f in "$@"; do
        awk -v REG='[A-Z_]*(CLEANUP|TMPDIRS)[A-Z0-9_]*\\+=\\(' "$SCANNER" "$f" "$f"
    done
}

hits="$(scan "$PROJECT_DIR"/tests/*.sh "$PROJECT_DIR"/tests/lib/*.sh)"
assert_eq "live tree: no cleanup-registering function is called inside \$( )" "" "$hits"
if [[ -n "$hits" ]]; then
    echo "  Each hit registers its temp dir inside a subshell, so the registration is"
    echo "  lost and the dir leaks. Create the dir with fixture_mktemp_d under a root"
    echo "  from fixture_root_init (tests/lib/fixture_root.sh)."
fi

ctl="$(fixture_mktemp_d scanctl)"
sed 's/^|//' > "$ctl/old.sh" <<'EOF'
|old() {
|    local d; d="$(mktemp -d)"
|    CLEANUP_DIRS+=("$d")
|    echo "$d"
|}
|x="$(old)"
EOF
sed 's/^|//' > "$ctl/tmpdirs.sh" <<'EOF'
|mk() {
|    local d; d="$(mktemp -d)"
|    TMPDIRS+=("$d")
|    echo "$d"
|}
|r="$( mk yes )"
EOF
sed 's/^|//' > "$ctl/direct.sh" <<'EOF'
|reg_here() {
|    CLEANUP_DIRS+=("$1")
|}
|d="$(mktemp -d)"
|reg_here "$d"
EOF
sed 's/^|//' > "$ctl/oneliner.sh" <<'EOF'
|bcrt() { ( cd "$B" && bash create.sh "$@" ); }
|x="$(bcrt --batch)"
|E="$(mktemp -d)"
|CLEANUP_DIRS+=("$E")
|later() {
|    :
|}
EOF
sed 's/^|//' > "$ctl/comment.sh" <<'EOF'
|make_fixture() {
|    _FIXTURE_DIR="$(mktemp -d)"
|    CLEANUP_DIRS+=("$_FIXTURE_DIR")
|}
|# Call it directly, never as `$(make_fixture)`.
|make_fixture
EOF
assert_eq "scanner flags the old shape" "$ctl/old.sh:6: old" "$(scan "$ctl/old.sh")"
assert_eq "scanner flags the TMPDIRS variant" "$ctl/tmpdirs.sh:6: mk" "$(scan "$ctl/tmpdirs.sh")"
assert_eq "scanner ignores a directly-called registering helper" "" "$(scan "$ctl/direct.sh")"
assert_eq "scanner ignores a one-liner followed by a top-level registration" "" "$(scan "$ctl/oneliner.sh")"
assert_eq "scanner ignores a comment that mentions \$(helper)" "" "$(scan "$ctl/comment.sh")"

# ---------------------------------------------------------------------------
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
