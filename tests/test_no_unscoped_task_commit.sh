#!/usr/bin/env bash
# test_no_unscoped_task_commit.sh — anti-regression guard for the t1599 sweep.
#
# `task_git commit -m "..."` with NO `--` pathspec commits the ENTIRE git index,
# not just the paths the script staged. On the shared task-data branch that means
# any file a concurrent session has staged at that instant lands in a commit whose
# message names a different task. t1599_1/2/3 fixed the three empirical sites;
# t1599_4 converted the remaining latent ones. This test stops new ones appearing.
#
# The cure is `task_git_commit_scoped` (lib/task_utils.sh), which carries the two
# non-obvious parts: the empty-pathspec guard (`git commit --` with no pathspec
# commits the whole index anyway) and a separately-captured `git status` exit, so
# a failing status reads as *unverified* rather than *clean*.
#
# Detection scope (documented on purpose — a guard that overclaims is worse than
# one with a known boundary):
#   * SCANNED: `.aitask-scripts/**/*.sh`. Logical lines are reassembled first, so
#     a command split across a `\` continuation is judged whole — two real,
#     correctly-scoped sites in aitask_note.sh are split exactly that way, and a
#     naive line-at-a-time grep reports them as violations.
#   * MATCHES: `task_git` followed by whitespace and `commit`. That deliberately
#     does NOT match `task_git_commit_scoped` (no space), which is the fix.
#   * A commit is considered scoped when the logical line contains `--` as a
#     standalone token OUTSIDE any quoted string. Escapes are collapsed before
#     quotes are removed, so `-m "… \" -- …"` does not read as a pathspec.
#   * FAILS CLOSED. A line whose quoting cannot be parsed (unbalanced quotes, a
#     quote arriving from an expansion) is reported, never assumed scoped —
#     under-detection here would be a silent index-wide commit.
#   * NOT scanned: comment lines; `tests/` (fixtures legitimately construct
#     unscoped argv to prove the defect); and `*.py` — `task_git` is a bash
#     function with no Python callers.
#   * NOT SEEN: a commit assembled through a variable (`$cmd commit …`) or built
#     up across separate statements. This is a grep over reassembled lines, so it
#     catches the common single-command shape and nothing subtler.
#   * OUT OF DETECTION SCOPE: `./ait git commit`. That is a different seam with
#     the same hazard; the two unscoped sites on it (aitask_verification_followup.sh,
#     lib/verified_update_lib.sh) are owned by a separate follow-up task, and this
#     guard deliberately makes no claim about them.
#
# It is a regression tripwire, NOT a proof of absence.
#
# Run: bash tests/test_no_unscoped_task_commit.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Allowlist ---------------------------------------------------------------
# Files permitted to issue a deliberately index-wide `task_git commit`, one entry
# per line with a `#` reason.
#
# It is EMPTY, and that is the intended end state: after t1599_4 every task-data
# commit in the tree names its own paths. An entry would only be justified by a
# commit whose path set is genuinely not enumerable at the call site AND cannot be
# expressed as a directory pathspec — aitask_zip_old.sh looked like that case and
# was still narrowed to two directory pathspecs, so the bar is high. Adding an
# entry means the swallow this guard exists to prevent becomes possible again in
# that file; say why in the comment.
ALLOWLIST=()

# Indirection so the negative controls can exercise allowlist suppression with a
# SYNTHETIC entry instead of pinning a real one (pattern from
# tests/test_no_lib_to_tui_import.sh).
ACTIVE_ALLOWLIST=(${ALLOWLIST[@]+"${ALLOWLIST[@]}"})

is_allowed() {
    local f="$1" a
    for a in ${ACTIVE_ALLOWLIST[@]+"${ACTIVE_ALLOWLIST[@]}"}; do
        [[ "$f" == "$a" ]] && return 0
    done
    return 1
}

# --- Scanner -----------------------------------------------------------------
# Reassemble `\`-continued lines, reporting the line number the command STARTS on.
# Load-bearing: aitask_note.sh:623 and :995 put their `-- "$file"` on the
# continuation line, and without this they are reported as violations.
JOIN_AWK='
{
    line = $0; start = NR
    while (line ~ /\\[ \t]*$/) {
        if ((getline nxt) <= 0) break
        sub(/\\[ \t]*$/, " ", line)
        line = line nxt
    }
    print start ":" line
}'

# A `task_git commit` invocation (NOT task_git_commit_scoped, which has no space).
COMMIT_RE='task_git[[:space:]]+commit'
# `--` as a standalone token = a pathspec separator is present.
SCOPED_RE='[[:space:]]--([[:space:]]|$)'

# is_scoped <logical-line> — 0 when the line provably carries a `--` pathspec
# separator, 1 otherwise. **Fails closed**: anything it cannot parse confidently
# counts as NOT scoped, so the line gets reported rather than waved through.
#
# Quoted arguments are removed before the separator test, because a commit
# MESSAGE may legitimately contain " -- " (`-m "ait: title -- annotation"`).
# Counting that as a pathspec would let an index-wide commit past the guard — a
# false negative, the one direction this guard must never fail in. A real
# `-- <paths>` separator always sits OUTSIDE the quotes.
#
# Escapes are collapsed FIRST. Without that step `\"` ends a quoted span early:
# `-m "ait: escaped \" -- annotation"` would strip to `-m "" -- annotation"` and
# the `--` still inside the shell string would read as a pathspec. That is a
# valid, ordinary shell form, not an exotic one, so it must be parsed rather than
# disclaimed.
#
# After removal no quote character should remain. One that does means the quoting
# is unbalanced or beyond this scanner (a here-doc body, an expansion that emits
# a quote), and the line is treated as unparseable — reported, never trusted.
is_scoped() {
    local bare
    bare="$(printf '%s\n' "$1" \
        | sed -e 's/\\./_/g' -e "s/'[^']*'//g" -e 's/"[^"]*"//g')"
    # Unbalanced / unparseable quoting: fail closed.
    case "$bare" in *\"*|*\'*) return 1 ;; esac
    [[ "$bare" =~ $SCOPED_RE ]]
}

scan_dir() {
    local root="$1" f rel
    while IFS= read -r -d '' f; do
        rel="${f#"$root"/}"
        is_allowed "$rel" && continue
        awk "$JOIN_AWK" "$f" 2>/dev/null | while IFS= read -r entry; do
            local lineno text
            lineno="${entry%%:*}"
            text="${entry#*:}"
            # Skip comment lines.
            [[ "$text" =~ ^[[:space:]]*# ]] && continue
            [[ "$text" =~ $COMMIT_RE ]] || continue
            is_scoped "$text" && continue
            printf '%s:%s:%s\n' "$rel" "$lineno" "$text"
        done
    done < <(find "$root/.aitask-scripts" -type f -name '*.sh' -print0 2>/dev/null)
}

# --- Test 1: the real tree ---------------------------------------------------
violations="$(scan_dir "$PROJECT_DIR")"
TOTAL=$((TOTAL + 1))
if [[ -z "$violations" ]]; then
    PASS=$((PASS + 1))
    echo "PASS: no unscoped task_git commit in .aitask-scripts/"
else
    FAIL=$((FAIL + 1))
    echo "FAIL: unscoped task_git commit(s) found — these commit the WHOLE index:"
    printf '  UNSCOPED: %s\n' "$violations"
    echo "  -> use task_git_commit_scoped <msg> <path>... (lib/task_utils.sh), or add"
    echo "     an explicit '-- <paths>' pathspec. Reference patterns:"
    echo "     aitask_attach.sh:_attach_commit, aitask_gate_record.sh, aitask_gate.sh."
fi

# --- Negative controls -------------------------------------------------------
# Every direction gets its own fixture: a scan that silently matched nothing would
# pass Test 1 for the wrong reason.
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.aitask-scripts"

cat > "$TMP/.aitask-scripts/aitask_rogue.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    task_git add "$file"
    task_git commit -m "ait: rogue unscoped commit"
}
EOF

cat > "$TMP/.aitask-scripts/aitask_scoped.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    task_git commit -m "ait: fine" -- "$file"
    task_git_commit_scoped "ait: also fine" "$file"
    task_git commit --amend --no-edit -o --quiet -- "${paths[@]}"
}
EOF

cat > "$TMP/.aitask-scripts/aitask_continued.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    task_git commit -m "ait: scoped on the next line" \
        -- "$file" >/dev/null 2>&1
}
EOF

cat > "$TMP/.aitask-scripts/aitask_commented.sh" <<'EOF'
#!/usr/bin/env bash
# A bare task_git commit -m "x" would commit the whole index.
run() { :; }
EOF

# A `--` INSIDE the commit message is not a pathspec. Without strip_quoted this
# file is silently treated as scoped — a false negative, the one direction this
# guard must never fail in.
cat > "$TMP/.aitask-scripts/aitask_dashes_in_msg.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    task_git commit -m "ait: title -- annotation"
}
EOF

# The same shape WITH a real separator must still pass: blanking the quoted span
# must not blind the scanner to a genuine pathspec sitting outside it.
cat > "$TMP/.aitask-scripts/aitask_dashes_and_paths.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    task_git commit -m "ait: title -- annotation" -- "$file"
}
EOF

# An ESCAPED quote inside the message. Without collapsing escapes first, the
# quoted span ends early at `\"`, the `--` still inside the shell string reads as
# a pathspec, and an index-wide commit walks past the guard. This is ordinary
# shell, not an exotic form.
cat > "$TMP/.aitask-scripts/aitask_escaped_quote.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    task_git commit -m "ait: escaped \" -- annotation"
}
EOF

# The escaped-quote shape WITH a real separator must still be accepted, so the
# escape handling cannot be "flag everything with a backslash".
cat > "$TMP/.aitask-scripts/aitask_escaped_quote_scoped.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    task_git commit -m "ait: escaped \" annotation" -- "$file"
}
EOF

# Unbalanced quoting is unparseable, and unparseable must fail CLOSED.
#
# A MULTI-LINE message is the realistic source of this: only `\`-continuations
# are reassembled, so a string that spans physical lines leaves the commit's
# logical line with an unterminated quote. Here the `--` sits inside that string,
# so with no complete quote pair to remove, nothing is stripped and the `--`
# survives — a line that reads as "scoped" unless unparseable quoting is refused.
cat > "$TMP/.aitask-scripts/aitask_unbalanced_quote.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    task_git commit -m "ait: multi-line -- message
    continues on the next line"
}
EOF

neg="$(scan_dir "$TMP")"

assert_contains "negative: a rogue unscoped commit IS flagged" \
    "aitask_rogue.sh" "$neg"
assert_not_contains "a commit carrying -- <paths> is NOT flagged" \
    "aitask_scoped.sh" "$neg"
assert_not_contains "a commit scoped on a CONTINUATION line is NOT flagged" \
    "aitask_continued.sh" "$neg"
assert_not_contains "prose in a comment is NOT flagged" \
    "aitask_commented.sh" "$neg"
assert_contains "a '--' inside the commit MESSAGE is not a pathspec — still flagged" \
    "aitask_dashes_in_msg.sh" "$neg"
assert_not_contains "a quoted '--' plus a REAL separator is not flagged" \
    "aitask_dashes_and_paths.sh" "$neg"
assert_contains "an ESCAPED quote does not end the message early — still flagged" \
    "aitask_escaped_quote.sh" "$neg"
assert_not_contains "an escaped quote plus a REAL separator is not flagged" \
    "aitask_escaped_quote_scoped.sh" "$neg"
assert_contains "unbalanced quoting is unparseable and fails CLOSED" \
    "aitask_unbalanced_quote.sh" "$neg"

# Exactly four violations across the nine fixtures — pins that the scan is
# neither over- nor under-matching.
neg_count="$(printf '%s\n' "$neg" | grep -c 'aitask_' || true)"
assert_eq "negative: exactly four violations across the fixture tree" "4" "$neg_count"

# The reported location is the line the command STARTS on.
assert_contains "negative: violation names file:line" "aitask_rogue.sh:4" "$neg"

# Allowlist suppression, via a synthetic entry.
ACTIVE_ALLOWLIST=(".aitask-scripts/aitask_rogue.sh")
neg_allow="$(scan_dir "$TMP")"
assert_not_contains "an allowlisted file is suppressed" "aitask_rogue.sh" "$neg_allow"
ACTIVE_ALLOWLIST=(${ALLOWLIST[@]+"${ALLOWLIST[@]}"})

echo
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
