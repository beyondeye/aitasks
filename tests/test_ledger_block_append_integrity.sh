#!/usr/bin/env bash
# test_ledger_block_append_integrity.sh - The fail-closed write contract of
# ait_ledger_append_section, lib/ledger_block.sh, and of its three callers
# (t1741).
#
# THE INCIDENT. The seam had two independent defects that combined to destroy a
# live 11KB task file while `ait note` printed NOTE_APPENDED:
#
#   1. every write path did `producer > "$tmp"; mv "$tmp" "$file"` with NO status
#      check, and the two awk paths then `return 0` unconditionally — masking
#      even mv's own failure;
#   2. the marker and body reached awk through `-v`, which runs escape
#      processing and REJECTS a literal newline. BSD awk (macOS) exits 2 with
#      EMPTY output on a multiline body; that emptiness was then published over
#      the target.
#
# WHAT IS DISCRIMINATING ON WHICH AWK. GNU awk accepts a multiline `-v`, so the
# newline half of defect 2 cannot be reproduced on Linux. Its BACKSLASH half can:
# `-v body='C:\temp'` yields `C:<TAB>emp` on gawk too. Group A is therefore built
# on backslashes, not newlines — it fails on gawk pre-fix (corruption) and on
# BSD awk pre-fix (truncation), so this file is red on both platforms rather than
# vacuously green on the one it is written on.
#
# Coverage map:
#
#   A   byte fidelity, both awk branches      defect 2
#   B   producer failure, all branches        defect 1 (the BSD-awk shape)
#   C   rename failure, all branches          defect 1 (the masked `mv`)
#   D   positive controls + the CLI failure
#       contracts of the three callers        the typed-error half
#
# HOW FAULTS ARE INJECTED. Groups A-C source the library and call the function
# in-process (it takes no lock), shadowing `awk` / `cat` / `tail` / `mv` with a
# shell function inside a subshell — a shell function wins over an external
# command, and `producer > "$tmp"` still CREATES an empty tempfile, which is
# exactly the BSD-awk shape. Group D's callers are separate PROCESSES, which no
# in-shell shadow can reach, so they use the library's documented
# AIT_LEDGER_FAIL_APPEND seam instead.
#
# Every assertion stays in THIS shell, so the file-backed counters (CLAUDE.md /
# t1207) are not needed.
#
# Run: bash tests/test_ledger_block_append_integrity.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

LIB="$PROJECT_DIR/.aitask-scripts/lib"
. "$LIB/terminal_compat.sh"
. "$LIB/stale_lock.sh"
. "$LIB/ledger_block.sh"

FIX="$(mktemp -d "${TMPDIR:-/tmp}/test_ledger_append_XXXXXX")"
trap 'rm -rf "$FIX"' EXIT

HDR="## Inbox"
CMT="<!-- Appended by the note framework. Do not edit by hand. -->"
ANCHOR="## Gate Runs"
MK='> **📥 note:new** id=abc from=t9'

# A body that is BOTH multiline and backslash-bearing, so one fixture covers the
# gawk-visible half (escape rewriting) and the BSD-awk-visible half (newline
# rejection) of defect 2. Rendered the way aitask_note.sh renders one.
BODY='> | path is C:\temp\new and a literal \\ pair
> | second line, with a trailing backslash \
> | third line'

# --- fixture builders -------------------------------------------------------
#
# Three shapes, one per write path of ait_ledger_append_section:
#   anchor  -> '## Gate Runs' present, no '## Inbox'  => create_before branch
#   section -> '## Inbox' present                     => section_end branch
#   plain   -> neither                                => EOF branch

make_target() {
    local kind="$1" path="$2"
    {
        printf -- '---\nstatus: Implementing\n---\n\n'
        printf 'Body line one.\nBody line two.\n'
        case "$kind" in
            anchor)  printf '\n%s\n%s\n\n> **✅ gate:x** run=1 status=pass\n' \
                         "$ANCHOR" "<!-- gate -->" ;;
            section) printf '\n%s\n%s\n\n> **📥 note:new** id=old from=t1\n' \
                         "$HDR" "$CMT" ;;
            plain)   ;;
        esac
    } > "$path"
}

# The call shape each caller of the seam actually uses.
append_into() {
    local path="$1" body="$2"
    case "$3" in
        anchor|section) ait_ledger_append_section "$path" "$HDR" "$CMT" "$MK" \
                            "$body" "$ANCHOR" "section_end" ;;
        plain)          ait_ledger_append_section "$path" "$ANCHOR" "$CMT" "$MK" \
                            "$body" "" "eof" ;;
    esac
}

leftover_tmps() { find "$FIX" -maxdepth 1 -name '.aitask_ledger.*.tmp' | wc -l | tr -d ' '; }

echo "=== ait_ledger_append_section: fail-closed write contract (t1741) ==="

# =====================================================================
# Group A — byte fidelity through both awk branches.
#
# The pre-existing content must survive verbatim AND the body must round-trip
# verbatim. Pre-fix on gawk the backslashes are rewritten; pre-fix on BSD awk
# the whole file is truncated. Either way these fail.
# =====================================================================

for kind in anchor section; do
    f="$FIX/a_$kind.md"
    make_target "$kind" "$f"
    cp "$f" "$FIX/a_$kind.before"

    rc=0
    append_into "$f" "$BODY" "$kind" || rc=$?
    assert_eq "A/$kind. append succeeds" "0" "$rc"

    # Pre-existing content survives, line for line.
    assert_eq "A/$kind. original body lines survive" "2" \
        "$(grep -cE '^Body line (one|two)\.$' "$f")"
    assert_eq "A/$kind. frontmatter survives" "1" \
        "$(grep -cx 'status: Implementing' "$f")"

    # The body round-trips byte-for-byte. grep -F so the backslashes are data.
    while IFS= read -r want; do
        assert_eq "A/$kind. body line verbatim: ${want:0:28}…" "1" \
            "$(grep -cFx "$want" "$f")"
    done <<< "$BODY"

    # And the corruption shape specifically: no TAB may appear where a `\t`
    # would have been produced from `C:\temp`.
    # awk rather than `grep -P`, which is a GNU extension this repo cannot rely
    # on (aidocs/framework/sed_macos_issues.md) — and this file must run on the
    # macOS box that has the truncating awk.
    assert_eq "A/$kind. no awk escape-rewritten TAB in the body" "0" \
        "$(awk '/^> \| / && index($0, "\t") { c++ } END { print c+0 }' "$f")"

    assert_eq "A/$kind. no tempfile left behind" "0" "$(leftover_tmps)"
done

# =====================================================================
# Group B — producer failure, all three branches.
#
# `awk() { return 2; }` reproduces the BSD-awk shape exactly: non-zero exit with
# an EMPTY tempfile (the redirect creates it even though the stub writes
# nothing). `cat` is the EOF branch's producer; `tail` is its source read.
#
# Pre-fix: the awk branches truncate the target to 0 bytes and return 0; the EOF
# branch replaces the whole file with a lone marker block and returns 0 (its
# brace group reports only its LAST command's status); the tail case silently
# guesses and renames that guess over the target.
# =====================================================================

# stub_case <label> <kind> <stub-name> <stub-rc> [target-ends-without-newline]
stub_case() {
    local label="$1" kind="$2" stub="$3" strc="$4" nonl="${5:-}"
    local f="$FIX/b_${label}.md"
    make_target "$kind" "$f"
    if [[ -n "$nonl" ]]; then printf 'no trailing newline' >> "$f"; fi
    cp "$f" "$FIX/b_${label}.before"

    local rc=0
    ( eval "${stub}() { return ${strc}; }"; append_into "$f" "$BODY" "$kind" ) \
        2>/dev/null || rc=$?

    assert_exit_nonzero_rc "B/$label. returns non-zero when $stub fails" "$rc"
    if cmp -s "$FIX/b_${label}.before" "$f"; then
        assert_eq "B/$label. target left byte-for-byte untouched" "same" "same"
    else
        assert_eq "B/$label. target left byte-for-byte untouched" "same" \
            "CHANGED ($(wc -c < "$f") bytes, was $(wc -c < "$FIX/b_${label}.before"))"
    fi
    assert_eq "B/$label. no tempfile left behind" "0" "$(leftover_tmps)"
}

stub_case "awk_anchor"  anchor  awk  2
stub_case "awk_section" section awk  2
stub_case "cat_eof"     plain   cat  2
# The source read: a `tail` that FAILS is indistinguishable from a file that
# already ends in a newline, so the target must be one that does NOT.
stub_case "tail_eof"    plain   tail 3 nonewline

# =====================================================================
# Group C — rename failure, all three branches.
#
# The producer succeeds and only the swap fails, which Group B never reaches.
# Pre-fix the awk branches `return 0` regardless of mv's status, and all three
# leave the tempfile behind next to the task file.
# =====================================================================

for kind in anchor section plain; do
    f="$FIX/c_$kind.md"
    make_target "$kind" "$f"
    cp "$f" "$FIX/c_$kind.before"

    rc=0
    ( mv() { return 1; }; append_into "$f" "$BODY" "$kind" ) 2>/dev/null || rc=$?

    assert_exit_nonzero_rc "C/$kind. returns non-zero when mv fails" "$rc"
    if cmp -s "$FIX/c_$kind.before" "$f"; then
        assert_eq "C/$kind. target left byte-for-byte untouched" "same" "same"
    else
        assert_eq "C/$kind. target left byte-for-byte untouched" "same" "CHANGED"
    fi
    assert_eq "C/$kind. tempfile cleaned up after the failed rename" "0" \
        "$(leftover_tmps)"
done

# =====================================================================
# Group D1 — positive controls.
#
# Without these, Groups B and C would pass just as well against a seam that
# refuses every append. The EOF branch is exercised against BOTH trailing-newline
# shapes, because its final-byte read decides the blank line before the section
# header and that structure is what the guard sits on.
# =====================================================================

for kind in anchor section plain; do
    f="$FIX/d_$kind.md"
    make_target "$kind" "$f"
    rc=0
    append_into "$f" '> | ordinary single line' "$kind" || rc=$?
    assert_eq "D1/$kind. ordinary body still appends" "0" "$rc"
    assert_eq "D1/$kind. body landed" "1" \
        "$(grep -cFx '> | ordinary single line' "$f")"
    assert_eq "D1/$kind. marker landed" "1" "$(grep -cF "$MK" "$f")"
    assert_eq "D1/$kind. original content intact" "2" \
        "$(grep -cE '^Body line (one|two)\.$' "$f")"
done

# The no-trailing-newline shape: the appended section must still start on its own
# line, with the blank line the ensure-newline step exists to produce.
f="$FIX/d_nonl.md"
make_target plain "$f"
printf 'dangling' >> "$f"          # last byte is NOT a newline
rc=0
append_into "$f" '> | x' plain || rc=$?
assert_eq "D1/nonl. append succeeds on a file with no final newline" "0" "$rc"
assert_eq "D1/nonl. the dangling line keeps its own line" "1" \
    "$(grep -cx 'dangling' "$f")"
assert_eq "D1/nonl. section header is preceded by a blank line" "1" \
    "$(awk -v h="$ANCHOR" 'prev == "" && $0 == h { c++ } { prev = $0 } END { print c+0 }' "$f")"

# =====================================================================
# Group D2 — the CLI failure contracts of the three callers.
#
# Separate processes, so the fault comes through the library's documented
# AIT_LEDGER_FAIL_APPEND seam. What is asserted is the CALLER's translation: a
# failed write must become a typed error, never a success line and never a
# marker echoed for a block that was not written.
# =====================================================================

NOTE="$PROJECT_DIR/.aitask-scripts/aitask_note.sh"
GATE="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"

AITASKS_LOCK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/test_ledger_append_lock_XXXXXX")"
export AITASKS_LOCK_DIR

CODE="$FIX/code"
mkdir -p "$CODE"
git -C "$CODE" init -q -b main
git -C "$CODE" config user.email t@example.com
git -C "$CODE" config user.name Test
echo one > "$CODE/f.txt"
git -C "$CODE" add -A && git -C "$CODE" commit -qm first

DATA="$FIX/data"
mkdir -p "$DATA/aitasks/metadata"
git -C "$DATA" init -q -b main
git -C "$DATA" config user.email t@example.com
git -C "$DATA" config user.name Test
cat > "$DATA/aitasks/metadata/gates.yaml" <<'EOF'
gates:
  tests_pass:
    type: machine
    description: "Run project test suite; must all pass"
EOF

make_cli_task() {
    cat > "$DATA/aitasks/t${1}_x.md" <<EOF
---
status: Implementing
gates: [tests_pass]
---
Body for t${1}.
EOF
    # Commit it, so "did the failed append also COMMIT something?" is answerable.
    # `ait note` persists the task file path-scoped on success, so an unchanged
    # HEAD is the durable half of the fail-closed contract — the on-disk bytes
    # alone would not catch a writer that failed loudly and committed anyway.
    git -C "$DATA" add -A >/dev/null 2>&1
    git -C "$DATA" commit -qm "base t${1}" >/dev/null 2>&1
}

# `ait gate append` deliberately gets no HEAD assertion below: it does not commit
# at all (aitask_gate_record.sh owns persistence), so the check would be vacuous
# there rather than merely redundant. Verified, not assumed.

# -- D2a: `ait note` (write) --
make_cli_task 950
cp "$DATA/aitasks/t950_x.md" "$FIX/d2a.before"
head_before="$(git -C "$DATA" rev-parse HEAD)"
out="$( cd "$DATA" && AIT_DIR="$CODE" AIT_LEDGER_FAIL_APPEND=1 \
        "$NOTE" 950 --from 951 --text "hello" 2>/dev/null )"
rc=$?
assert_exit_nonzero_rc "D2a. ait note exits non-zero on a failed append" "$rc"
assert_eq "D2a. exactly one stdout line" "1" "$(printf '%s\n' "$out" | grep -c .)"
assert_eq "D2a. the typed pre-append error, not NOTE_APPENDED" \
    "NOTE_ERROR:append-write-failed" "$out"
assert_eq "D2a. the task file is untouched" "same" \
    "$(cmp -s "$FIX/d2a.before" "$DATA/aitasks/t950_x.md" && echo same || echo CHANGED)"
assert_eq "D2a. nothing was committed" "$head_before" "$(git -C "$DATA" rev-parse HEAD)"

# -- D2b: `ait note read` (receipt) --
# Land a real note first, so there is something to acknowledge, then fail the
# receipt append and assert the note is STILL unread (the fail-safe direction).
make_cli_task 951
( cd "$DATA" && AIT_DIR="$CODE" "$NOTE" 951 --from 950 --text "hi" ) >"$FIX/n.out" 2>/dev/null
note_id="$(sed -n 's/^NOTE_APPENDED:\([^|]*\)|.*/\1/p' "$FIX/n.out")"
assert_contains_re "D2b. precondition: a note landed" \
    "^[0-9]{4}-.*\\.[0-9a-f]{24}$" "$note_id"

cp "$DATA/aitasks/t951_x.md" "$FIX/d2b.before"
head_before="$(git -C "$DATA" rev-parse HEAD)"
out="$( cd "$DATA" && AIT_DIR="$CODE" AIT_LEDGER_FAIL_APPEND=1 \
        "$NOTE" read 951 --by t951 --ids "$note_id" --mode explicit 2>/dev/null )"
rc=$?
assert_exit_nonzero_rc "D2b. ait note read exits non-zero on a failed append" "$rc"
assert_eq "D2b. exactly one stdout line" "1" "$(printf '%s\n' "$out" | grep -c .)"
assert_eq "D2b. the typed read error, not READ_RECORDED" \
    "READ_ERROR:append-write-failed" "$out"
assert_eq "D2b. the task file is untouched" "same" \
    "$(cmp -s "$FIX/d2b.before" "$DATA/aitasks/t951_x.md" && echo same || echo CHANGED)"
assert_eq "D2b. no receipt was committed" "$head_before" "$(git -C "$DATA" rev-parse HEAD)"
# The whole point of failing closed here: the note must resurface.
assert_contains "D2b. the note is still unread" \
    "INBOX_UNREAD:951|$note_id" \
    "$( cd "$DATA" && "$PROJECT_DIR/.aitask-scripts/aitask_query_files.sh" inbox 951 2>/dev/null )"

# -- D2c: `ait gate append` --
make_cli_task 952
cp "$DATA/aitasks/t952_x.md" "$FIX/d2c.before"
out="$( cd "$DATA" && AIT_LEDGER_FAIL_APPEND=1 \
        "$GATE" append 952 tests_pass pass 2>/dev/null )"
rc=$?
assert_exit_nonzero_rc "D2c. ait gate append exits non-zero on a failed append" "$rc"
assert_not_contains "D2c. no marker echoed for a block that was not written" \
    '> **' "$out"
assert_eq "D2c. the task file is untouched" "same" \
    "$(cmp -s "$FIX/d2c.before" "$DATA/aitasks/t952_x.md" && echo same || echo CHANGED)"

# -- D2d: the seam is inert when unset (it must not break normal operation) --
#
# Also the POSITIVE CONTROL for the two "nothing was committed" assertions above.
# Without it they would pass just as well in a fixture where `ait note` never
# commits at all — an unchanged HEAD would then be the fixture's property, not
# the fail-closed contract's.
make_cli_task 953
head_before="$(git -C "$DATA" rev-parse HEAD)"
out="$( cd "$DATA" && AIT_DIR="$CODE" "$NOTE" 953 --from 950 --text "normal" 2>/dev/null )"
assert_contains "D2d. an ordinary note still lands with the seam unset" \
    "NOTE_APPENDED:" "$out"
assert_eq "D2d. a SUCCESSFUL note does advance HEAD in this fixture" "advanced" \
    "$([ "$(git -C "$DATA" rev-parse HEAD)" != "$head_before" ] && echo advanced || echo unchanged)"

rm -rf "$AITASKS_LOCK_DIR"

echo
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
[[ "$FAIL" -eq 0 ]]
