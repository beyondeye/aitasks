#!/usr/bin/env bash
# test_cd_guard_lint.sh - every cd/pushd in a bash test must be unable to fall
# through into the wrong directory (t1826).
#
# t1815 found fixture task files and commits in the live repository: a test ran
# `cd "$fixture"` with no guard, the cd failed, and the relative writes and
# `git commit` after it ran in the invoking directory. The rule and its accepted
# forms live in tests/lib/cd_guard_scan.py; the start-cwd second layer lives in
# tests/lib/scratch_cwd.sh; the convention is documented in
# aidocs/framework/testing_conventions.md ("Every cd in a bash test is
# exit-guarded").
#
# This file checks three things:
#   1. the live tree: no violation in tests/*.sh or tests/lib/*.sh, and every
#      file that changes its cwd calls enter_scratch_cwd before its first cd,
#      after any $(pwd) capture and before no relative BASH_SOURCE derivation;
#   2. the scanner itself, against synthetic sites -- including the forms that
#      LOOK guarded but fall through (`if cd`, `! cd`, `|| return`, `{ cd && }`),
#      each paired with a check that the form really leaks, so the rule is
#      grounded in behavior rather than in the scanner's opinion;
#   3. the helper: read-only empty cwd, refusal inside a repository, refusal when
#      non-empty, bounded retention, and a leak control that re-enters a stand-in
#      "live repo" and then fails a fixture cd.
#
# Run: bash tests/test_cd_guard_lint.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/scratch_cwd.sh disable=SC1091
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

# shellcheck source=lib/asserts.sh disable=SC1091
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

SCAN="$PROJECT_DIR/tests/lib/cd_guard_scan.py"
HELPER="$PROJECT_DIR/tests/lib/scratch_cwd.sh"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/ait_cd_guard_XXXXXX")" || { echo "FAIL: mktemp"; exit 1; }
# Canonicalize: macOS TMPDIR ends in '/', so the raw path contains '//', and
# assertions below compare paths derived from $TMP against real `pwd` output.
TMP="$(cd "$TMP" && pwd -P)" || { echo "FAIL: canonicalize $TMP"; exit 1; }
# Fixture scratch dirs are made 0555 by the helper; restore write bits so rm works.
trap 'chmod -R u+w "$TMP" 2>/dev/null; rm -rf "$TMP"' EXIT

# class_at <file> <line> -> the scanner's class for the first site on that line
class_at() {
    python3 "$SCAN" --json "$1" | python3 -c '
import json, sys
want = int(sys.argv[1])
for l in sys.stdin:
    o = json.loads(l)
    if o["line"] == want:
        print(o["class"]); break
else:
    print("NO_SITE")' "$2"
}

# ---------------------------------------------------------------------------
echo "=== 1. live tree ==="

live_out="$(python3 "$SCAN" --check "$PROJECT_DIR"/tests/*.sh "$PROJECT_DIR"/tests/lib/*.sh 2>&1)"
live_rc=$?
assert_eq "no cd/pushd guard violations in tests/ (see testing_conventions.md)" "0" "$live_rc"
[[ -z "$live_out" ]] || printf '%s\n' "$live_out"

order_out="$(python3 "$SCAN" --helper-order "$PROJECT_DIR"/tests/*.sh 2>&1)"
assert_eq "every cwd-changing test calls enter_scratch_cwd first" "" "$order_out"

# ---------------------------------------------------------------------------
echo "=== 2. scanner self-controls ==="

cat > "$TMP/cases.sh" <<'EOF'
cd "$PROJECT_DIR" || exit 1
cd "$fixture"
REPO="$TMP/repo"; cd "$REPO"
(cd "$X" && a; b)
cd "$X" && cmd
cd $x || exit 1
cd "$x" || return 1
cd "$x" || true
if cd "$x"; then :; fi
while cd "$x"; do :; done
! cd "$x"
{ cd "$x" && a; }
cd "$x" || { echo e; [[ -n "$y" ]] && exit 1; }
d="$(cd "$d" && pwd)"
(cd "$x" && a && b)
cd "$x" || { echo e; exit 1; }
cd "$x"  # cd-guard: cleanup removes absolute paths only
cat <<'H'
cd "$inside_heredoc"
H
pushd "$local_dir" > /dev/null
echo "cd is only a word here"
SD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
(cd "$FIX" && "$PY" - <<'PY'
cd "$inside_heredoc_too"
PY
)
(cd "$X" && git log | head -1)
(cd "$X" && a || b)
(cd "$dir" && cd "$ans" && pwd -P)
cd -- $x || exit 1
cd -P $x || exit 1
pushd -- "$x" >/dev/null || exit 1
cd -P -- "$x" 2>/dev/null || exit 1
cd "$x" || { echo "x; exit 1"; }; echo CONTINUED
cd "$x" || exit 1 | cat; echo CONTINUED
cd "$x"; echo '# cd-guard: harmless'; echo CONTINUED
cd 2>& 1 $x || exit 1
cd "$x" || { echo e; exit 1; } | cat
cd "$x" || exit 1 &
cd "$x" || exit 1 >&2
cd "$x" || {
    echo "cannot enter"
    exit 1
}
cd "$x" || { echo "a}"; exit 1; }
cd "$x" || { echo error; exit 1; } >/dev/null | cat
cd "$x" || exit 1 >/nonexistent/probe/log
cd "$x" || exit"_missing" 1
cd "$x" || exit 1 && echo ok
cd "$x" || exit
cd "$x" || exit $?
cd "$x" || exit 1 && echo ok & wait
cd "$x" || exit 1 && echo ok; echo next
( cd "$x" || exit 1 && echo ok ) &
EOF

check_class() {  # <line> <expected> <description>
    assert_eq "scanner: $3" "$2" "$(class_at "$TMP/cases.sh" "$1")"
}
check_class 2  unguarded            "re-entry then unguarded fixture cd is a violation (target-agnostic)"
check_class 3  unguarded            "a \$REPO fixture target is not exempt by name"
check_class 4  unconfined-andchain  "(cd X && a; b) runs b in the old cwd"
check_class 5  unconfined-andchain  "top-level cd X && cmd protects only that line"
check_class 6  unquoted             "unquoted \$x target"
check_class 7  weak-or              "|| return relies on the caller"
check_class 8  weak-or              "|| true swallows the failure"
check_class 9  conditional          "if cd ...; then ...; fi"
check_class 10 conditional          "while cd ...; do ... done"
check_class 11 conditional          "! cd turns failure into success"
check_class 12 unconfined-andchain  "{ cd X && a; } shares the caller's cwd"
check_class 13 weak-or              "exit that is not the last command of the braces"
check_class 1  guarded              "cd ... || exit 1"
check_class 14 subshell-andchain    "\$(cd d && pwd)"
check_class 15 subshell-andchain    "(cd x && a && b)"
check_class 16 guarded              "cd ... || { echo; exit 1; }"
check_class 17 exempt               "# cd-guard: exemption"
check_class 19 NO_SITE              "cd inside a heredoc body is text"
check_class 21 unguarded            "pushd with a redirection"
check_class 22 NO_SITE              "cd inside a quoted string is text"
check_class 23 subshell-andchain    "nested \$(dirname) inside a path derivation"
check_class 24 subshell-andchain    "group closed after a heredoc body"
check_class 28 subshell-andchain    "a pipeline inside one && element"
check_class 29 unconfined-andchain  "(cd X && a || b) runs b in the old cwd"
check_class 31 unquoted             "unquoted target after -- (empty -> \$HOME, rc 0)"
check_class 32 unquoted             "unquoted target after -P"
check_class 33 guarded              "quoted target after --"
check_class 34 guarded              "quoted target after -P -- and a redirection"
check_class 35 weak-or              "an exit inside a quoted string in the braces is not a command"
check_class 36 weak-or              "|| exit 1 | cat exits only the pipeline subshell"
check_class 37 unguarded            "a cd-guard marker inside a string is not an exemption"
check_class 38 unquoted             "separated descriptor redirection (2>& 1) then an unquoted target"
check_class 39 weak-or              "a guard group that is itself piped"
check_class 40 weak-or              "a backgrounded exit"
check_class 41 weak-or              "a redirection on the exit can fail before it runs"
check_class 42 guarded              "multi-line guard group ending in exit"
check_class 46 guarded              "a quoted } inside the guard group"
check_class 47 weak-or              "a guard group with a redirection AND a pipeline"
check_class 48 weak-or              "exit with a redirection that can fail before it runs"
check_class 49 weak-or              "exit\"_missing\" concatenates into another command name"
check_class 50 guarded              "&& after exit is dead code, so the exit still terminates"
check_class 51 guarded              "bare exit"
check_class 52 guarded              "exit \$?"
check_class 53 guarded              "a backgrounded list still cannot leak (the cd runs in that subshell too)"
check_class 54 guarded              "the same chain kept synchronous (control)"
check_class 55 guarded              "a backgrounded SUBSHELL never moved the caller's cwd"
assert_eq "scanner: a later cd inside a confined && chain is accepted" \
    "subshell-andchain subshell-andchain" \
    "$(python3 "$SCAN" --json "$TMP/cases.sh" | python3 -c 'import json,sys; print(" ".join(o["class"] for o in map(json.loads, sys.stdin) if o["line"] == 30))')"

check_rc_out="$(python3 "$SCAN" --check "$TMP/cases.sh")"
assert_exit_nonzero_rc "scanner: --check exits non-zero on violations" "$?"
assert_contains "scanner: --check names file:line:class" "cases.sh:9:conditional:" "$check_rc_out"

# The "looks guarded but is not" forms really do leak. A stand-in live repo is
# the cwd; the failing cd targets a directory that does not exist.
LIVE="$TMP/live"
mkdir -p "$LIVE" || { echo "FAIL: mkdir"; exit 1; }
leak_probe() {  # <description> <script body>; body runs with cwd = $LIVE
    rm -f "$LIVE/leaked"
    ( cd "$LIVE" || exit 1; eval "$2" ) >/dev/null 2>&1
    assert_file_exists "form really leaks: $1" "$LIVE/leaked"
}
leak_probe "if cd"       'if cd /nonexistent/ait-probe; then :; fi; : > leaked'
leak_probe "while cd"    'while cd /nonexistent/ait-probe; do break; done; : > leaked'
leak_probe "! cd"        '! cd /nonexistent/ait-probe; : > leaked'
leak_probe "|| true"     'cd /nonexistent/ait-probe || true; : > leaked'
leak_probe "{ cd && }"   '{ cd /nonexistent/ait-probe && :; }; : > leaked'
leak_probe "|| return"   'f() { cd /nonexistent/ait-probe || return 1; }; f; : > leaked'
leak_probe "(cd && a || b)" '(cd /nonexistent/ait-probe && : || : > leaked)'
# An unquoted empty target defeats even an exit guard: cd goes to $HOME, rc 0.
# HOME is pointed at the stand-in so the probe never writes the real one.
# The probe bodies are single-quoted on purpose: they must expand inside the
# eval'd probe, not here.
# shellcheck disable=SC2016
leak_probe "cd -- \$empty || exit 1" 'HOME="$PWD"; e=; cd /; cd -- $e || exit 1; : > leaked'
# shellcheck disable=SC2016
leak_probe "cd 2>& 1 \$empty || exit 1" 'HOME="$PWD"; e=; cd /; cd 2>& 1 $e || exit 1; : > leaked'
leak_probe "exit inside a quoted string" 'cd /nonexistent/ait-probe || { echo "x; exit 1"; }; : > leaked'
leak_probe "|| exit 1 | cat" 'cd /nonexistent/ait-probe || exit 1 | cat; : > leaked'
leak_probe "cd-guard marker inside a string" "cd /nonexistent/ait-probe; echo '# cd-guard: harmless'; : > leaked"
leak_probe "guard group redirected and piped" 'cd /nonexistent/ait-probe || { echo error; exit 1; } >/dev/null | cat; : > leaked'
leak_probe "exit whose redirection fails first" 'cd /nonexistent/ait-probe || exit 1 >/nonexistent/ait-probe/log; : > leaked'
leak_probe "exit\"_missing\" is a different command name" 'cd /nonexistent/ait-probe || exit"_missing" 1; : > leaked'

# Backgrounding cannot defeat an exit guard: `&` puts the whole list, cd
# included, in a subshell, so the exit ends it before anything else runs and the
# parent's cwd never moved. Measured, not assumed -- the control below leaks.
no_leak_probe() {  # <description> <script body>; body runs with cwd = $LIVE
    rm -f "$LIVE/leaked"
    ( cd "$LIVE" || exit 1; eval "$2" ) >/dev/null 2>&1
    assert_file_not_exists "guard holds: $1" "$LIVE/leaked"
}
no_leak_probe "backgrounded AND/OR list" 'cd /nonexistent/ait-probe || exit 1 && : > leaked & wait'
no_leak_probe "backgrounded list with a compound command" 'cd /nonexistent/ait-probe || exit 1 && if true; then : > leaked; fi & wait'
no_leak_probe "backgrounded list continued across a newline" 'cd /nonexistent/ait-probe || exit 1 &&
: > leaked & wait'
leak_probe "the same shape unguarded (control)" 'cd /nonexistent/ait-probe; : > leaked & wait'
rm -f "$LIVE/leaked"
( cd "$LIVE" || exit 1; ( cd /nonexistent/ait-probe || exit 1; : > leaked ) ) >/dev/null 2>&1
assert_file_not_exists "accepted form does not leak: (cd || exit 1; write)" "$LIVE/leaked"

# The live-tree helper-order check can fail.
mkdir -p "$TMP/order" || { echo "FAIL: mkdir"; exit 1; }
# shellcheck disable=SC2016  # literal shell text for the synthetic files
printf 'cd "$x" || exit 1\n' > "$TMP/order/no_helper.sh"
# shellcheck disable=SC2016
printf 'cd "$x" || exit 1\nenter_scratch_cwd\n' > "$TMP/order/late_helper.sh"
# shellcheck disable=SC2016
printf 'ORIG_DIR="$(pwd)"\nenter_scratch_cwd\ncd "$x" || exit 1\n' > "$TMP/order/early_capture.sh"
# shellcheck disable=SC2016
printf 'enter_scratch_cwd\ncd "$x" || exit 1\n' > "$TMP/order/ok.sh"
# shellcheck disable=SC2016
printf 'enter_scratch_cwd\nSD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\ncd "$x" || exit 1\n' > "$TMP/order/late_derive.sh"
# shellcheck disable=SC2016
printf 'cat <<EOF\nenter_scratch_cwd\nEOF\ncd "$x" || exit 1\n' > "$TMP/order/heredoc_call.sh"
order_neg="$(python3 "$SCAN" --helper-order "$TMP"/order/*.sh)"
assert_exit_nonzero_rc "helper order: --helper-order exits non-zero on problems" "$?"
assert_contains "helper order: missing call is flagged" "no_helper.sh: no enter_scratch_cwd" "$order_neg"
assert_contains "helper order: call after first cd is flagged" "late_helper.sh: enter_scratch_cwd at line 2" "$order_neg"
assert_contains "helper order: earlier \$(pwd) capture is flagged" "early_capture.sh: line 1 captures" "$order_neg"
assert_contains "helper order: a relative BASH_SOURCE derivation after the call is flagged" "late_derive.sh: line 2 derives" "$order_neg"
assert_contains "helper order: a call inside a heredoc does not count" "heredoc_call.sh: no enter_scratch_cwd" "$order_neg"
assert_not_contains "helper order: correct file is clean" "ok.sh" "$order_neg"

# ---------------------------------------------------------------------------
echo "=== 3. enter_scratch_cwd ==="

H_TMP="$TMP/htmp"
mkdir -p "$H_TMP" || { echo "FAIL: mkdir"; exit 1; }

out="$(TMPDIR="$H_TMP" bash -c '. "$1"; enter_scratch_cwd; pwd; echo "ENTRIES=$(ls -A | wc -l | tr -d " ")"; [[ -w . ]] && echo WRITABLE || echo READONLY' _ "$HELPER" 2>&1)"
rc=$?
assert_exit_zero_rc_out "helper: enters the scratch cwd" "$rc" "$out"
assert_contains "helper: cwd is the per-user dir" "$H_TMP/ait-test-cwd-$(id -u)" "$out"
assert_contains "helper: cwd is empty" "ENTRIES=0" "$out"
if [[ "$(id -u)" -ne 0 ]]; then
    assert_contains "helper: cwd is not writable" "READONLY" "$out"
fi

# (e) bounded retention: a second call reuses the one directory.
TMPDIR="$H_TMP" bash -c '. "$1"; enter_scratch_cwd' _ "$HELPER" >/dev/null 2>&1
n_dirs="$(find "$H_TMP" -maxdepth 1 -name 'ait-test-cwd-*' | wc -l | tr -d ' ')"
assert_eq "helper: repeated calls keep exactly one scratch dir" "1" "$n_dirs"

# (b) exported GIT_DIR makes every directory a repository -> refuse.
SENT="$TMP/sentinel"
git init -q "$SENT" || { echo "FAIL: git init"; exit 1; }
out="$(GIT_DIR="$SENT/.git" TMPDIR="$H_TMP" bash -c '. "$1"; enter_scratch_cwd; echo ENTERED' _ "$HELPER" 2>&1)"
rc=$?
assert_exit_nonzero_rc "helper: refuses under an exported GIT_DIR" "$rc"
assert_contains "helper: GIT_DIR refusal names the reason" "resolves to a git repository" "$out"
assert_not_contains "helper: GIT_DIR refusal happens before entering" "ENTERED" "$out"

# (c) TMPDIR inside a repository -> refuse.
mkdir -p "$SENT/tmp" || { echo "FAIL: mkdir"; exit 1; }
out="$(TMPDIR="$SENT/tmp" bash -c '. "$1"; enter_scratch_cwd; echo ENTERED' _ "$HELPER" 2>&1)"
rc=$?
assert_exit_nonzero_rc "helper: refuses when TMPDIR is inside a repository" "$rc"
assert_contains "helper: TMPDIR refusal names the reason" "resolves to a git repository" "$out"

# (d) a non-empty scratch dir -> refuse and name it.
NE_TMP="$TMP/netmp"
mkdir -p "$NE_TMP/ait-test-cwd-$(id -u)" || { echo "FAIL: mkdir"; exit 1; }
: > "$NE_TMP/ait-test-cwd-$(id -u)/stray"
out="$(TMPDIR="$NE_TMP" bash -c '. "$1"; enter_scratch_cwd; echo ENTERED' _ "$HELPER" 2>&1)"
rc=$?
assert_exit_nonzero_rc "helper: refuses a non-empty scratch dir" "$rc"
assert_contains "helper: non-empty refusal names the dir" "ait-test-cwd-$(id -u)' is not empty" "$out"

# (f) leak control: re-enter a stand-in live repo, then fail a fixture cd.
leak_control() {  # <guard text> -> prints sentinel porcelain + commit count
    local s="$TMP/lc_repo" script="$TMP/lc_script.sh"
    chmod -R u+w "$s" 2>/dev/null; rm -rf "$s"
    git init -q "$s" || { echo "FAIL: git init"; exit 1; }
    git -C "$s" -c user.email=t@t -c user.name=t commit -q --allow-empty -m base || { echo "FAIL: base commit"; exit 1; }
    cat > "$script" <<EOF
. "$HELPER"
enter_scratch_cwd
cd "$s" || exit 1
(
    cd "/nonexistent/ait-leak-probe" $1
    mkdir -p aitasks
    : > aitasks/t1_alpha.md
    git add -A && git -c user.email=t@t -c user.name=t commit -q -m leak
)
EOF
    TMPDIR="$H_TMP" bash "$script" >/dev/null 2>&1
    printf '%s|%s' "$(git -C "$s" status --porcelain)" "$(git -C "$s" rev-list --count HEAD)"
}
assert_eq "leak control: guarded fixture cd after re-entry leaves the repo untouched" \
    "|1" "$(leak_control '|| exit 1')"
assert_eq "leak control: the same script unguarded DOES leak (control can fail)" \
    "|2" "$(leak_control '')"

# ---------------------------------------------------------------------------
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
