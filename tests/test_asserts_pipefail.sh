#!/usr/bin/env bash
# test_asserts_pipefail.sh - the fixed-string / case-insensitive / regex
# containment helpers in tests/lib/asserts.sh give the right verdict under
# `set -o pipefail`, and keep their exact matching semantics (t2215).
#
# WHY THIS FILE EXISTS
#
# The helpers used to run `printf '%s' "$haystack" | grep -q… -- "$needle"`.
# Under pipefail, with a haystack larger than the pipe buffer, `grep -q` exits on
# its first match, printf dies of SIGPIPE, and the pipeline fails: a needle that
# IS present was reported missing, and `assert_not_contains` silently passed.
#
# The fix reads the haystack through process substitution, which hands grep the
# same bytes but keeps the writer out of the pipeline status. A here-string
# would also cure SIGPIPE but appends a newline, which changes two verdicts the
# old helpers gave; the byte-exactness pins below hold both.
#
# HOW IT TESTS
#
# Each case runs ONE helper call in a child `bash` that sources asserts.sh and
# prints its counters as `COUNTS:<pass>/<fail>`; the parent compares that line.
# A helper under test must not judge itself.
#
# RED PROOFS: AIT_ASSERTS_LIB=<path> points the children at a mutated copy of
# asserts.sh (old pipe body, here-string body, a dropped -i / -E / -F flag) so
# each mutant can be shown to turn its own cases red.
#
# Run: bash tests/test_asserts_pipefail.sh

# Case bodies are single-quoted on purpose: the CHILD shell expands them.
# shellcheck disable=SC2016
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_DIR/.." && pwd)"

# shellcheck source=lib/scratch_cwd.sh
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

ASSERTS_UNDER_TEST="${AIT_ASSERTS_LIB:-$PROJECT_DIR/tests/lib/asserts.sh}"
[[ -r "$ASSERTS_UNDER_TEST" ]] || { echo "FAIL: cannot read $ASSERTS_UNDER_TEST"; exit 1; }

WORK="$(mktemp -d "${TMPDIR:-/tmp}/ait_asserts_pipefail_XXXXXX")" \
    || { echo "FAIL: mktemp"; exit 1; }
trap 'rm -rf "$WORK"' EXIT

# 2 MB on one line after the needle line: far past any pipe buffer, so grep -q
# is guaranteed to exit while the writer still has data to send.
BIG_FILE="$WORK/big.txt"
{ printf 'NEEDLE\n'; head -c 2000000 /dev/zero | tr '\0' 'x'; } > "$BIG_FILE"

# child <body> -> prints the child's COUNTS:<pass>/<fail> value, or the
# child's exit status when it printed none (a crash must not read as a verdict).
child() {
    local body="$1" out rc=0
    out="$(ASSERTS_UNDER_TEST="$ASSERTS_UNDER_TEST" BIG_FILE="$BIG_FILE" bash -c '
        . "$ASSERTS_UNDER_TEST"
        PASS=0; FAIL=0; TOTAL=0
        '"$body"'
        echo "COUNTS:$PASS/$FAIL"
    ' 2>/dev/null)" || rc=$?
    local line
    line="$(grep '^COUNTS:' <<<"$out" | tail -n1)"
    if [[ -n "$line" ]]; then
        printf '%s\n' "${line#COUNTS:}"
    else
        printf 'no-counts(rc=%s)\n' "$rc"
    fi
}

# expect <desc> <pass/fail> <body>
expect() {
    assert_eq "$1" "$2" "$(child "$3")"
}

echo "--- 1. pipefail + a 2 MB haystack, needle on line 1 ---"
P='set -o pipefail; big="$(cat "$BIG_FILE")"; '
expect "1a assert_contains finds a present needle"          1/0 "$P"'assert_contains d NEEDLE "$big"'
expect "1b assert_not_contains rejects a present needle"    0/1 "$P"'assert_not_contains d NEEDLE "$big"'
expect "1c assert_contains_ci finds a present needle"       1/0 "$P"'assert_contains_ci d needle "$big"'
expect "1d assert_not_contains_ci rejects a present needle" 0/1 "$P"'assert_not_contains_ci d needle "$big"'
expect "1e assert_contains_re finds a present pattern"      1/0 "$P"'assert_contains_re d "NEE+DLE" "$big"'
expect "1f assert_not_contains_re rejects a present pattern" 0/1 "$P"'assert_not_contains_re d "NEE+DLE" "$big"'

echo "--- 2. pre-fix control: the old pipe really misreports on this fixture ---"
# An inline copy of the pre-t2215 helper body. If this ever stops misreporting,
# section 1 no longer proves anything about SIGPIPE.
misses="$(BIG_FILE="$BIG_FILE" bash -c '
    set -o pipefail
    big="$(cat "$BIG_FILE")"
    n=0
    for _ in 1 2 3 4 5; do
        printf "%s" "$big" | grep -qF -- NEEDLE || n=$((n + 1))
    done
    echo "$n"
' 2>/dev/null)"
if [[ "$misses" =~ ^[1-5]$ ]]; then
    assert_record_pass
else
    assert_record_fail
    echo "FAIL: 2 the old printf|grep -q pipe misreported 0/5 times (got '$misses') - fixture no longer reaches SIGPIPE"
fi

echo "--- 3. byte-exactness pins: verdicts a here-string would flip ---"
# grep sees exactly the haystack's bytes: no line is added for an empty
# haystack, and no empty line after a trailing newline.
expect "3a empty needle in an empty haystack is not found"        0/1 'set -o pipefail; assert_contains d "" ""'
expect "3b ... and its negative form passes"                      1/0 'set -o pipefail; assert_not_contains d "" ""'
expect "3c ^\$ does not match a haystack ending in one newline"   0/1 'set -o pipefail; assert_contains_re d "^\$" $'"'"'abc\n'"'"
expect "3d ... and its negative form passes"                      1/0 'set -o pipefail; assert_not_contains_re d "^\$" $'"'"'abc\n'"'"

echo "--- 4. sanity without pipefail ---"
expect "4a present needle found"       1/0 'assert_contains d foo "a foo b"'
expect "4b absent needle not found"    0/1 'assert_contains d bar "a foo b"'
expect "4c absent needle: negative ok" 1/0 'assert_not_contains d bar "a foo b"'
expect "4d present needle: negative fails" 0/1 'assert_not_contains d foo "a foo b"'

echo "--- 5. matching modes stay distinct ---"
# Case: only the _ci pair ignores case.
expect "5a _ci matches across case"                 1/0 'assert_contains_ci d world "Hello WORLD"'
expect "5b _ci negative rejects across case"        0/1 'assert_not_contains_ci d world "Hello WORLD"'
expect "5c plain fixed-string is case-sensitive"    0/1 'assert_contains d world "Hello WORLD"'
expect "5d plain negative passes on a case miss"    1/0 'assert_not_contains d world "Hello WORLD"'
# Regex: the pattern text is not literally in the haystack.
expect "5e _re matches a regex"                     1/0 'assert_contains_re d "c[0-9]+" "abc123"'
expect "5f _re negative rejects a regex match"      0/1 'assert_not_contains_re d "c[0-9]+" "abc123"'
expect "5g plain treats the same text literally"    0/1 'assert_contains d "c[0-9]+" "abc123"'
expect "5h plain negative passes on a literal miss" 1/0 'assert_not_contains d "c[0-9]+" "abc123"'
# Fixed-string: a regex metacharacter is literal for the plain and _ci pairs.
expect "5i plain: . is literal"                     0/1 'assert_contains d "a.c" "abc"'
expect "5j plain negative: . is literal"            1/0 'assert_not_contains d "a.c" "abc"'
expect "5k _ci: . is literal"                       0/1 'assert_contains_ci d "a.c" "abc"'
expect "5l _ci negative: . is literal"              1/0 'assert_not_contains_ci d "a.c" "abc"'
expect "5m control: _re reads . as a regex"         1/0 'assert_contains_re d "a.c" "abc"'

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
