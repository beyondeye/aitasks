#!/usr/bin/env bash
# test_no_sed_hex_escape.sh — anti-regression guard for the BSD-sed \xNN trap.
#
# `\xNN` is a GNU extension. BSD sed / awk / tr (macOS) do NOT recognise it and
# match the literal characters instead, so an expression like
#     sed 's/\x1b\[[0-9;]*m//g'
# silently no-ops on macOS: no error, no diagnostic, the caller just receives an
# un-substituted string. The class has now been hit twice (t1641 in
# tests/test_task_lock.sh, t1646 in tests/test_sync_branch_mode_automerge.sh),
# both times found only because a human remembered to run the sweep that
# aidocs/framework/sed_macos_issues.md mandates. This test replaces that manual
# sweep with an enforced invariant.
#
# The fix is always to let BASH emit the byte instead of asking sed to interpret
# an escape:  sed $'s/\033\[[0-9;]*m//g'
#
# Detection scope (documented on purpose — a guard that overclaims is worse than
# one with a known boundary):
#   * MATCHES  — a COMMAND-POSITION `sed`/`awk`/`tr` followed by whitespace and,
#     later on the same line, a `\xNN` escape. Command position means: at the
#     start of a line, or after `;` `&` `|` `(` `{` `!` `` ` `` `$(`, or after
#     a command keyword (`exec` `eval` `if` `elif` `then` `else` `while` `until`
#     `do` `time` `nohup`). The `{` is load-bearing: a one-line helper body
#     `strip_ansi() { sed …; }` is the exact shape t1646 fixed, and an anchor
#     without it silently misses the very regression this guard exists to catch
#     (verified — the guard passed against a deliberately broken tree until `{`
#     was added). Anchoring here is what keeps the guard
#     off prose — `echo "Example: sed 's/\x1b//'"` is a diagnostic string, not a
#     command, and must not fail the repo-wide scan. (A bare word-boundary
#     anchor is NOT enough for that, though it does already exclude the word
#     "parsed", which the sweep in sed_macos_issues.md false-positives on.)
#   * SUPPRESSED — pure-comment lines, and `\xNN` appearing inside bash ANSI-C
#     quoting (`$'…'`), where the escape is expanded by BASH and is correct.
#     The suppression is SEGMENT-scoped, not line-scoped: a line-wide filter
#     would drop a genuinely unsafe command that merely shares a line with an
#     unrelated valid `$'…\xNN'` escape.
#   * NOT DETECTED — a `\xNN` separated from its `sed` by a pipe; an unsafe
#     expression in a trailing comment on a code line; and a `sed` reached
#     through a lead-in outside the set above (e.g. `xargs sed …`, or `sed`
#     passed as an argument to another command).
#   * Scope is every tracked `*.sh` file (`git ls-files`), which naturally
#     excludes website/node_modules and untracked scratch files.
#
# Run: bash tests/test_no_sed_hex_escape.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

# Stage-1 candidate pattern. The leading alternation is a COMMAND-POSITION
# anchor (line start, or after `;` `&` `|` `(` backtick `$(`, or after a
# keyword) — modelled on tests/test_no_raw_tmux.sh's SH_PATTERN. Without it a
# `sed …\xNN` quoted inside ordinary prose (`echo "Example: sed 's/\x1b//'"`)
# would fail the repo-wide scan, and it also excludes the word "par-sed-" that
# the sweep in sed_macos_issues.md false-positives on.
PATTERN='(^[[:space:]]*|[;&|(`{!][[:space:]]*|\$\([[:space:]]*|(exec|eval|then|else|do|if|elif|while|until|time|nohup)[[:space:]]+)(sed|awk|tr)[[:space:]][^|]*\\x[0-9a-fA-F]{2}'

# Blank every bash ANSI-C segment ($'…') in a line, so a \xNN inside one — where
# BASH expands it, making it correct — cannot mask an unsafe expression elsewhere
# on the same line.
#
# The replacement MUST be a plain space. Substituting an empty $'' instead would
# re-match the loop condition on the next iteration and spin forever.
scrub_ansic() {
    local s="$1" pre rest post
    while [[ "$s" == *\$\'*\'* ]]; do
        pre="${s%%\$\'*}"
        rest="${s#*\$\'}"
        post="${rest#*\'}"
        s="$pre $post"
    done
    printf '%s' "$s"
}

# scan_files — read NUL-separated paths on stdin, emit "<path>:<line>:<text>"
# for every unsafe hit. Two stages: a fast per-file grep for candidates, then a
# precise re-test of each candidate after comment/ANSI-C suppression.
scan_files() {
    local f n line trimmed
    while IFS= read -r -d '' f; do
        while IFS=: read -r n line; do
            trimmed="${line#"${line%%[![:space:]]*}"}"
            [[ "$trimmed" == '#'* ]] && continue
            if printf '%s' "$(scrub_ansic "$line")" | grep -qE "$PATTERN"; then
                printf '%s:%s:%s\n' "$f" "$n" "$line"
            fi
        done < <(grep -nE "$PATTERN" "$f" 2>/dev/null)
    done
    :
}

# --- Test 1: the real tree is clean ----------------------------------------
violations="$(cd "$PROJECT_DIR" && git ls-files -z '*.sh' | scan_files)"
TOTAL=$((TOTAL + 1))
if [[ -z "$violations" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: non-portable \\xNN escape(s) found in sed/awk/tr expressions:"
    printf '  HEX ESCAPE: %s\n' "$violations"
    echo "  -> BSD sed/awk/tr (macOS) do not understand \\xNN and will silently"
    printf '%s\n' "     no-op. Let bash emit the byte instead: sed \$'s/\\033\\[[0-9;]*m//g'"
    echo "     See aidocs/framework/sed_macos_issues.md."
fi

# --- Fixtures ---------------------------------------------------------------
# This file is itself scanned by Test 1 once it is tracked, so it must NEVER
# contain the forbidden sequence contiguously in a non-comment line. The
# fixtures therefore assemble it at runtime from a split token. Do not "tidy"
# this by inlining the literal — Test 2 below exists to catch exactly that.
X='x'
BAD="\\${X}1b"   # -> the escape this guard forbids

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

write_fixture() { printf '%s\n' "$2" > "$TMP/$1"; }
scan_fixture() { printf '%s\0' "$TMP/$1" | scan_files; }

# --- Test 2: the guard does not flag its own source -------------------------
# Pins the no-literal invariant rather than assuming it, so someone inlining a
# fixture literal gets a legible failure here instead of a puzzling Test 1 break
# on the NEXT commit (the file is only scanned by Test 1 once tracked).
self_hits="$(printf '%s\0' "${BASH_SOURCE[0]}" | scan_files)"
assert_eq "the guard's own source scans clean (no inlined literal)" "" "$self_hits"

# --- Negative controls: the guard actually catches a regression -------------
write_fixture unsafe_sed.sh "sed 's/${BAD}//'"
assert_contains "unsafe sed is flagged" "unsafe_sed.sh" "$(scan_fixture unsafe_sed.sh)"

# The exact shape of the real t1646 defect: sed reached through a PIPE inside a
# command substitution. The command-position anchor must not lose this — it is
# the single most important thing the guard has to catch.
write_fixture piped_sed.sh "int_clean=\$(printf '%s' \"\$int_out\" | sed 's/${BAD}\\[[0-9;]*m//g')"
assert_contains "the real t1646 shape (pipe lead) is flagged" \
    "piped_sed.sh" "$(scan_fixture piped_sed.sh)"

write_fixture subst_sed.sh "x=\$(sed 's/${BAD}//')"
assert_contains "sed in a command substitution is flagged" \
    "subst_sed.sh" "$(scan_fixture subst_sed.sh)"

# A one-line helper body — the exact shape of the t1646 fix site. `{` must be a
# recognised lead-in or the guard silently misses a real regression here.
write_fixture brace_body.sh "strip_ansi() { sed 's/${BAD}\\[[0-9;]*m//g'; }"
assert_contains "sed inside a one-line function body is flagged (\`{\` lead-in)" \
    "brace_body.sh" "$(scan_fixture brace_body.sh)"

write_fixture indented_sed.sh "    sed 's/${BAD}//'"
assert_contains "an indented sed is flagged" \
    "indented_sed.sh" "$(scan_fixture indented_sed.sh)"

write_fixture unsafe_awk.sh "awk '{gsub(/${BAD}/,\"\")}'"
assert_contains "unsafe awk is flagged" "unsafe_awk.sh" "$(scan_fixture unsafe_awk.sh)"

write_fixture unsafe_tr.sh "tr -d '${BAD}'"
assert_contains "unsafe tr is flagged (neither GNU nor BSD tr groks \\xNN)" \
    "unsafe_tr.sh" "$(scan_fixture unsafe_tr.sh)"

# The mixed line: a valid ANSI-C escape and an unsafe command on ONE line. A
# line-wide suppression would silently drop this, which is the whole reason the
# scrub is segment-scoped.
write_fixture mixed.sh "printf '%s' \$'${BAD}'; sed 's/${BAD}//' input"
assert_contains "unsafe sed sharing a line with a valid \$'…\\xNN' is still flagged" \
    "mixed.sh" "$(scan_fixture mixed.sh)"

write_fixture mixed_two.sh "a=\$'${BAD}'; b=\$'\\x07'; sed 's/${BAD}//'"
assert_contains "two ANSI-C segments then an unsafe sed is still flagged" \
    "mixed_two.sh" "$(scan_fixture mixed_two.sh)"

# --- Negative controls: the guard does NOT flag correct code ----------------
write_fixture safe_ansic.sh "sed \$'s/${BAD}//'"
assert_eq "bash ANSI-C \$'…\\xNN' is not flagged (bash expands it)" \
    "" "$(scan_fixture safe_ansic.sh)"

write_fixture safe_octal.sh "sed \$'s/\\033\\[[0-9;]*m//g'"
assert_eq "the documented \$'\\033' fix is not flagged" \
    "" "$(scan_fixture safe_octal.sh)"

write_fixture comment.sh "# sed 's/${BAD}//'  <- explanatory comment, not code"
assert_eq "a pure-comment line is not flagged" "" "$(scan_fixture comment.sh)"

write_fixture parsed_word.sh 'parsed = C.parse_snapshot("a\x1b]8;;u\x1b")'
assert_eq "the word 'parsed' is not flagged (word-boundary anchor)" \
    "" "$(scan_fixture parsed_word.sh)"

# Prose, not a command. Diagnostics and help text legitimately quote the very
# expression this guard forbids — including the failure message THIS file
# prints — so a guard that flags them would fail on unrelated doc changes.
write_fixture prose.sh "echo \"Example of the bug: sed 's/${BAD}//'\""
assert_eq "an unsafe expression quoted in prose is not flagged (command-position anchor)" \
    "" "$(scan_fixture prose.sh)"

write_fixture prose_mid.sh "warn \"do not write sed 's/${BAD}//' — it is GNU-only\""
assert_eq "prose mid-sentence is not flagged" "" "$(scan_fixture prose_mid.sh)"

# The pipe boundary is documented as NOT detected — pin it so the limitation is
# a known, tested fact rather than an accident of the regex.
write_fixture piped.sh "sed 's/a/b/' | grep '${BAD}'"
assert_eq "a \\xNN after a pipe is not attributed to the earlier sed (documented boundary)" \
    "" "$(scan_fixture piped.sh)"

# --- Summary ---------------------------------------------------------------
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
