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
# a failing status reads as *unverified* rather than *clean*. On a path that may
# already be TRACKED and staged by another session, prefer its caller
# `ait_commit_paths_staging_untracked` (t1702): the scoped helper's own default
# `add` would replace that session's index entry, which is a second shared-index
# hazard this guard does not detect.
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
#   * ALSO SCANNED (t1728): `./ait git commit`. `./ait git <args>` is literally
#     `task_git <args>` in a subprocess (`ait` sources lib/task_utils.sh and
#     dispatches to it), so it carries the identical hazard and the identical
#     cure. It gets its own pattern because it needs its own matching rule:
#     * it is matched against the QUOTE-STRIPPED line, not the raw one. Five
#       occurrences in the tree are recovery-hint PROSE inside message strings
#       (aitask_sync.sh, aitask_setup.sh, lib/txn_snapshot.sh, and two in
#       aitask_note.sh), not commands. Stripping balanced quoted spans before
#       matching removes three of them for free, because a command's own
#       `./ait git commit` always sits outside the quotes.
#     * the remaining two are continuation PHYSICAL lines of multi-line `warn`
#       strings in aitask_note.sh. Only `\`-continuations are reassembled, so
#       those lines carry unbalanced quoting and fail closed -- correctly, since
#       relaxing that is what `aitask_unbalanced_quote.sh` below exists to
#       forbid. They are suppressed by AIT_GIT_ALLOWLIST instead, which applies
#       to THIS PATTERN ONLY: aitask_note.sh stays fully guarded for
#       `task_git commit`, which is how it actually commits task data. The hole
#       is one file, one pattern, and it closes when those two hint strings are
#       restructured onto a single logical line.
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

# Files exempt from the `./ait git commit` pattern ONLY. Deliberately separate
# from ALLOWLIST above: an entry here suppresses one seam in one file and leaves
# `task_git commit` fully guarded there, so it is a far smaller concession than
# an ALLOWLIST entry. It is NOT a place to park a real unscoped command -- the
# one entry is prose that the scanner cannot parse, and the header says exactly
# why. Adding another means saying, in the comment, why the match is not a
# command.
AIT_GIT_ALLOWLIST=(
    # Two recovery HINTS inside multi-line `warn` strings (both already written
    # with a `-- $file` pathspec, for anyone who copies them). They are
    # continuation physical lines, so their quoting is unparseable and the
    # fail-closed rule reports them. aitask_note.sh issues no `./ait git commit`
    # command of its own; its real task-data commits go through `task_git` and
    # are still scanned by the primary pattern.
    ".aitask-scripts/aitask_note.sh"
)
ACTIVE_AIT_GIT_ALLOWLIST=(${AIT_GIT_ALLOWLIST[@]+"${AIT_GIT_ALLOWLIST[@]}"})

is_ait_git_allowed() {
    local f="$1" a
    for a in ${ACTIVE_AIT_GIT_ALLOWLIST[@]+"${ACTIVE_AIT_GIT_ALLOWLIST[@]}"}; do
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
# The second seam: `./ait git commit` / `ait git commit`. The leading class
# rejects a longer identifier ending in "ait", and `(\./)?` lets the class match
# the whitespace before the `./` rather than the `/` itself.
AIT_GIT_COMMIT_RE='(^|[^[:alnum:]_/.])(\./)?ait[[:space:]]+git[[:space:]]+commit'
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
# strip_quoted <line> — the line with escapes collapsed and balanced quoted
# spans removed. Shared by is_scoped and by the `./ait git commit` match, so the
# two can never disagree about what counts as "inside a string".
strip_quoted() {
    printf '%s\n' "$1" \
        | sed -e 's/\\./_/g' -e "s/'[^']*'//g" -e 's/"[^"]*"//g'
}

is_scoped() {
    local bare
    bare="$(strip_quoted "$1")"
    # Unbalanced / unparseable quoting: fail closed.
    case "$bare" in *\"*|*\'*) return 1 ;; esac
    [[ "$bare" =~ $SCOPED_RE ]]
}

scan_dir() {
    local root="$1" f rel
    while IFS= read -r -d '' f; do
        rel="${f#"$root"/}"
        awk "$JOIN_AWK" "$f" 2>/dev/null | while IFS= read -r entry; do
            local lineno text bare
            lineno="${entry%%:*}"
            text="${entry#*:}"
            # Skip comment lines.
            [[ "$text" =~ ^[[:space:]]*# ]] && continue

            # Seam 1: `task_git commit`, matched on the RAW line. A mention
            # inside a string is vanishingly rare for this spelling, and
            # matching raw is what the existing controls pin.
            if ! is_allowed "$rel" && [[ "$text" =~ $COMMIT_RE ]]; then
                if ! is_scoped "$text"; then
                    printf '%s:%s:%s\n' "$rel" "$lineno" "$text"
                    continue
                fi
            fi

            # Seam 2: `./ait git commit`, matched on the QUOTE-STRIPPED line so
            # the recovery-hint prose in message strings is not mistaken for a
            # command. See the detection-scope note in the header.
            is_ait_git_allowed "$rel" && continue
            bare="$(strip_quoted "$text")"
            [[ "$bare" =~ $AIT_GIT_COMMIT_RE ]] || continue
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
    echo "PASS: no unscoped task_git commit / ./ait git commit in .aitask-scripts/"
else
    FAIL=$((FAIL + 1))
    echo "FAIL: unscoped task-data commit(s) found — these commit the WHOLE index:"
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

# --- `./ait git commit` fixtures (t1728) -------------------------------------

# The rogue shape on the second seam. `./ait git` is task_git in a subprocess,
# so this commits the whole shared index exactly as the first seam does.
cat > "$TMP/.aitask-scripts/aitask_ait_git_rogue.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    ./ait git add "$file"
    ./ait git commit -m "ait: rogue unscoped ait-git commit"
}
EOF

# Invoked without the `./` prefix — same command, same hazard.
cat > "$TMP/.aitask-scripts/aitask_ait_git_bare_prefix.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    ait git commit -m "ait: rogue without the dot-slash"
}
EOF

# The scoped shape must NOT be flagged: `-- <paths>` is a valid cure, and the
# guard's own failure hint offers it.
cat > "$TMP/.aitask-scripts/aitask_ait_git_scoped.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    ./ait git commit -m "ait: fine" -- "$file"
    ait_commit_paths_staging_untracked "ait: also fine" "$file"
}
EOF

# A recovery HINT inside a message string is prose, not a command, and must NOT
# be flagged. This is why the second seam matches on the quote-stripped line —
# five such occurrences exist in the real tree and none of them is a call.
cat > "$TMP/.aitask-scripts/aitask_ait_git_hint.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    die "path has uncommitted changes. Commit it (./ait git commit -- $p) or revert it."
}
EOF

# The seam must not be blinded by a longer identifier that merely ENDS in "ait":
# `portrait git commit` is not an `ait` invocation.
cat > "$TMP/.aitask-scripts/aitask_ait_git_lookalike.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    portrait git commit -m "not the ait dispatcher"
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

assert_contains "negative: a rogue unscoped ./ait git commit IS flagged" \
    "aitask_ait_git_rogue.sh" "$neg"
assert_contains "negative: the same command without ./ IS flagged" \
    "aitask_ait_git_bare_prefix.sh" "$neg"
assert_not_contains "an ./ait git commit carrying -- <paths> is NOT flagged" \
    "aitask_ait_git_scoped.sh" "$neg"
assert_not_contains "a recovery hint inside a message string is NOT flagged" \
    "aitask_ait_git_hint.sh" "$neg"
assert_not_contains "a longer identifier ending in 'ait' is NOT flagged" \
    "aitask_ait_git_lookalike.sh" "$neg"

# Exactly six violations across the fourteen fixtures — pins that the scan is
# neither over- nor under-matching. Four come from the `task_git commit` seam
# and two from `./ait git commit`; a fixture that stopped being detected, or one
# that started being over-detected, moves this number.
neg_count="$(printf '%s\n' "$neg" | grep -c 'aitask_' || true)"
assert_eq "negative: exactly six violations across the fixture tree" "6" "$neg_count"

# The reported location is the line the command STARTS on.
assert_contains "negative: violation names file:line" "aitask_rogue.sh:4" "$neg"

# Allowlist suppression, via a synthetic entry.
ACTIVE_ALLOWLIST=(".aitask-scripts/aitask_rogue.sh")
neg_allow="$(scan_dir "$TMP")"
assert_not_contains "an allowlisted file is suppressed" "aitask_rogue.sh" "$neg_allow"
ACTIVE_ALLOWLIST=(${ALLOWLIST[@]+"${ALLOWLIST[@]}"})

# The two allowlists are INDEPENDENT, and that independence is the whole reason
# aitask_note.sh can be exempted from one seam without losing the other. Pin
# both directions with a synthetic entry.
ACTIVE_AIT_GIT_ALLOWLIST=(".aitask-scripts/aitask_ait_git_rogue.sh")
neg_ait_allow="$(scan_dir "$TMP")"
assert_not_contains "an ait-git-allowlisted file is suppressed for THAT seam" \
    "aitask_ait_git_rogue.sh" "$neg_ait_allow"
assert_contains "…and the task_git seam is still guarded everywhere else" \
    "aitask_rogue.sh" "$neg_ait_allow"
ACTIVE_AIT_GIT_ALLOWLIST=(${AIT_GIT_ALLOWLIST[@]+"${AIT_GIT_ALLOWLIST[@]}"})

# The converse: a file on the ait-git allowlist must still be flagged for an
# unscoped `task_git commit`. This is the claim the header makes about
# aitask_note.sh, so it is asserted rather than asserted-in-prose.
cat > "$TMP/.aitask-scripts/aitask_both_seams.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    task_git commit -m "ait: unscoped on the primary seam"
}
EOF
ACTIVE_AIT_GIT_ALLOWLIST=(".aitask-scripts/aitask_both_seams.sh")
neg_both="$(scan_dir "$TMP")"
assert_contains "an ait-git-allowlisted file is STILL guarded for task_git commit" \
    "aitask_both_seams.sh" "$neg_both"
ACTIVE_AIT_GIT_ALLOWLIST=(${AIT_GIT_ALLOWLIST[@]+"${AIT_GIT_ALLOWLIST[@]}"})
rm -f "$TMP/.aitask-scripts/aitask_both_seams.sh"

echo
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
