#!/usr/bin/env bash
# test_aitask_merge_boardgroup.sh - base-aware `boardgroup` merge (t1243_8).
#
# Run: bash tests/test_aitask_merge_boardgroup.sh
#
# Scope split: this file covers the base-aware MERGE SEMANTICS through the real
# rebase path in legacy mode. The branch-mode plumbing that carries them (the
# `task_git show :1:` extraction and conflict staging inside a wedged rebase)
# is covered by tests/test_sync_branch_mode_automerge.sh.
#
# Why the fixture is shaped the way it is
# ---------------------------------------
# Git merges textually, per hunk. If the two sides' edits land in
# non-overlapping hunks the rebase succeeds cleanly, `aitask_merge.py` is never
# invoked, and an assertion on the final file content STILL PASSES — a test that
# proves nothing. So Test 1 asserts an unmerged path actually materialised
# before asserting the outcome, and Test 5 proves that control discriminates.

set -uo pipefail

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"

# Report a file's `boardgroup` as "<type>:<repr>" using the REAL loader, so an
# assertion pins presence AND type. A bare `boardgroup:` parses to None, which
# no string match on the file text would distinguish from the "" tombstone.
# Parameterised over the key (t1468_1) so `followup_kind`, which shares the
# base-aware resolver, can be pinned the same way. `parsed_boardgroup` stays as
# the boardgroup-specific wrapper so every existing call site is unchanged.
parsed_field() {
    PYTHONPATH="$PROJECT_DIR/.aitask-scripts/lib" python3 -c "
import sys, task_yaml as ty
parsed = ty.parse_frontmatter(open(sys.argv[1]).read())
if not parsed:
    print('UNPARSEABLE'); raise SystemExit
md = parsed[0]
key = sys.argv[2]
if key not in md:
    print('ABSENT'); raise SystemExit
v = md[key]
print(f'{type(v).__name__}:{v!r}')
" "$1" "$2"
}

parsed_boardgroup() { parsed_field "$1" boardgroup; }

# `labels` and `boardgroup` are ADJACENT so the two sides' single-line edits
# necessarily collide in one hunk.
#
# The unrelated edit is `labels` (union-merged), deliberately NOT `status`:
# divergent non-Implementing statuses are unresolvable by a PRE-EXISTING rule,
# so a status-based fixture reports PARTIAL for a reason that has nothing to do
# with this task and proves nothing about `boardgroup`.
write_task() {
    local path="$1" labels="$2" group_line="$3"
    {
        echo "---"
        echo "priority: high"
        echo "status: Ready"
        echo "labels: $labels"
        echo "$group_line"
        echo "updated_at: $4"
        echo "---"
        echo "Body stays the same"
    } > "$path"
}

# bare remote + local + pc2, all carrying `boardgroup: perf_work` at the base.
setup_repos() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    git init -q --bare "$tmpdir/remote.git"
    git clone -q "$tmpdir/remote.git" "$tmpdir/local" 2>/dev/null
    (
        cd "$tmpdir/local" || exit 1
        git config user.email test@test.com
        git config user.name Test
        git config commit.gpgsign false
        mkdir -p aitasks aiplans
        write_task aitasks/t1_sample.md "[ui]" "boardgroup: perf_work" "2026-01-01 09:00"
        git add -A
        git commit -q -m "base: grouped"
        git push -q 2>/dev/null
        cp "$PROJECT_DIR/ait" ./ait
        chmod +x ./ait
        cp -r "$PROJECT_DIR/.aitask-scripts" ./.aitask-scripts
        git add -A
        git commit -q -m "framework"
        git push -q 2>/dev/null
    ) >/dev/null 2>&1
    git clone -q "$tmpdir/remote.git" "$tmpdir/pc2" 2>/dev/null
    (
        cd "$tmpdir/pc2" || exit 1
        git config user.email test2@test.com
        git config user.name Test2
        git config commit.gpgsign false
    ) >/dev/null 2>&1
    echo "$tmpdir"
}

echo "=== boardgroup base-aware merge Tests ==="
echo ""

# --- Test 1: the cleared side wins over an unrelated labels-only edit ---
echo "--- Test 1: cleared boardgroup beats an unrelated labels-only edit ---"

TMP1="$(setup_repos)"

# pc2 CLEARS the group (writes the tombstone) and pushes.
(
    cd "$TMP1/pc2" || exit 1
    write_task aitasks/t1_sample.md "[ui]" 'boardgroup: ""' "2026-01-01 10:00"
    git add -A; git commit -q -m "pc2: ungroup"; git push -q 2>/dev/null
) >/dev/null 2>&1

# local changes ONLY labels, still carrying the old group, with a NEWER stamp.
# Under newer-wins this side would win a field it never touched.
(
    cd "$TMP1/local" || exit 1
    write_task aitasks/t1_sample.md "[api, ui]" "boardgroup: perf_work" "2026-01-01 12:00"
    git add -A; git commit -q -m "local: labels only"
) >/dev/null 2>&1

# POSITIVE CONTROL: the rebase must genuinely conflict. Without this the test
# could pass on a clean textual auto-merge that never invoked the driver.
(cd "$TMP1/local" || exit 1 && git fetch -q origin 2>/dev/null
 git rebase origin/main >/dev/null 2>&1 || git rebase origin/master >/dev/null 2>&1 || true)
unmerged=$(cd "$TMP1/local" && git diff --name-only --diff-filter=U 2>/dev/null)
assert_contains "Fixture produces a real unmerged path (control)" \
    "aitasks/t1_sample.md" "$unmerged"
(cd "$TMP1/local" || exit 1 && git rebase --abort >/dev/null 2>&1 || true)

output=$(cd "$TMP1/local" && ./ait sync --batch 2>/dev/null)
assert_eq_trim "Conflict auto-resolves" "AUTOMERGED" "$output"

merged=$(cat "$TMP1/local/aitasks/t1_sample.md")
assert_eq "Cleared side wins - tombstone survives as an empty STRING" \
    "str:''" "$(parsed_boardgroup "$TMP1/local/aitasks/t1_sample.md")"
assert_contains "Local labels edit is preserved" "api" "$merged"

rm -rf "$TMP1"

# --- Test 2: the withheld-base NEGATIVE CONTROL ---
echo "--- Test 2: negative control - without the base the same case is PARTIAL ---"

TMP2="$(mktemp -d)"
mkdir -p "$TMP2/aitasks"
# A conflicted file exactly as git would leave it (2-way markers, the style the
# repo actually produces — merge.conflictStyle is configured nowhere).
cat > "$TMP2/aitasks/t1_sample.md" <<'EOF'
---
priority: high
status: Ready
<<<<<<< HEAD
labels: [ui]
boardgroup: ""
=======
labels: [api, ui]
boardgroup: perf_work
>>>>>>> local
updated_at: 2026-01-01 12:00
---
Body stays the same
EOF
cp "$TMP2/aitasks/t1_sample.md" "$TMP2/with_base.md"
write_task "$TMP2/base.md" "[ui]" "boardgroup: perf_work" "2026-01-01 09:00"

# WITHOUT --base-file: nothing can say which side changed it -> fail closed.
out_nobase=$(cd "$PROJECT_DIR/.aitask-scripts/board" && \
    PYTHONDONTWRITEBYTECODE=1 python3 aitask_merge.py "$TMP2/aitasks/t1_sample.md" \
    --batch --rebase 2>/dev/null); rc_nobase=$?
assert_eq "Without a base the divergence is PARTIAL (exit 2)" "2" "$rc_nobase"
assert_contains "PARTIAL names boardgroup" "boardgroup" "$out_nobase"

# WITH --base-file: the same input resolves. This is what proves the base — and
# not some incidental difference in the fixture — is what decided it.
out_base=$(cd "$PROJECT_DIR/.aitask-scripts/board" && \
    PYTHONDONTWRITEBYTECODE=1 python3 aitask_merge.py "$TMP2/with_base.md" \
    --batch --rebase --base-file "$TMP2/base.md" 2>/dev/null); rc_base=$?
assert_eq "With a base the same input resolves (exit 0)" "0" "$rc_base"
assert_contains "Driver reports RESOLVED when the base decided it" \
    "RESOLVED" "$out_base"
assert_eq "Resolved file keeps the tombstone as an empty STRING" \
    "str:''" "$(parsed_boardgroup "$TMP2/with_base.md")"

rm -rf "$TMP2"

# --- Test 3: guard - every merge-driver reference is a based invocation or fails ---
echo "--- Test 3: guard - every merge-driver reference is classified, every invocation passes a base ---"

# Discovery is exhaustive over the scanned files (t2069). Every logical line
# (backslash continuations joined) that mentions the driver - the literal
# `aitask_merge.py`, or a `$VAR`/`${VAR}` reference to a variable assigned
# `.../aitask_merge.py` in ANY scanned file - is classified per simple command:
#   - INVOKE: `"$<any var>" "$<driver var>" ...`; it is based when a later word
#     of the SAME simple command carries `base_args` or `--base-file`;
#   - allowed: a pure driver-path assignment, and a driver ref that is the
#     operand of -e/-f/-r/-s/-x inside a `[[ ]]`, `[ ]` or `test` command;
#   - UNCLASSIFIED (a hard failure - update this guard): everything else, e.g. a
#     literal-path call, an array call, an alias, `"$PY" -s "$X"`, a driver
#     mention on a line with a command/process substitution, or a line whose
#     quoting/comment boundary cannot be decided safely.
# Comments are stripped with Bash's rule (a `#` opens one only at the START of
# a word), never shlex's, which treats `release#candidate` as a comment and
# would silently drop the rest of the line; the differential below pins this
# against real bash.
#
# Remaining boundary: only `*.sh` under .aitask-scripts/ is scanned (no Python
# file invokes the driver), and a driver path assembled without the literal
# `aitask_merge.py` in any scanned file is invisible to a static scan.
DRIVER_SCAN_PY=$(cat <<'PY'
import re, shlex, sys

CTRL = {';', '&&', '||', '|', '&', '(', ')', ';;', '|&', '&;'}
LEAD = {'!', 'if', 'then', 'do', 'else', 'elif', 'while', 'until', 'time', '{'}
FILE_TESTS = {'-e', '-f', '-r', '-s', '-x'}
WORD_BREAK = set(' \t;&|()<>')
SUBST = re.compile(r'\$\(|`|[<>]\(')
NAME_ASSIGN = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\+?=(.*)$', re.S)
VAR_WORD = re.compile(r'^\$\{?[A-Za-z_][A-Za-z0-9_]*\}?$')
LITERAL = 'aitask_merge.py'


def logical_lines(path):
    """Join backslash continuations the way Bash does: only an UNESCAPED
    trailing backslash in CODE continues a line. One inside a comment does not
    (a comment always ends at the newline), and `\\\\` is an escaped backslash.
    An undecidable line is never joined; it is classified on its own."""
    buf, start = '', 0
    with open(path, errors='replace') as fh:
        for no, line in enumerate(fh, 1):
            line = line.rstrip('\n')
            if not buf:
                start = no
            text = buf + line
            trailing = len(line) - len(line.rstrip('\\'))
            if trailing % 2 == 1 and strip_comment(text) == text:
                buf = text[:-1]
                continue
            yield start, text
            buf = ''
    if buf:
        yield start, buf


def strip_comment(s):
    """Bash's rule: an unquoted '#' opens a comment only at the START of a
    word. None = undecidable (unterminated quote, $'...', or a '#' inside
    $( ) / `...`), which the caller treats as unclassified."""
    if "$'" in s:
        return None
    q, brace, paren, tick, at_word_start = None, 0, 0, False, True
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        if q == "'":
            if ch == "'":
                q = None
        elif q == '"':
            if ch == '\\':
                i += 1
            elif ch == '"':
                q = None
        elif ch == '\\':
            i += 1
            at_word_start = False
        elif ch in "'\"":
            q, at_word_start = ch, False
        elif ch == '`':
            tick = not tick
            at_word_start = tick
        elif ch in '$<>' and i + 1 < n and s[i + 1] == '(':
            paren += 1
            i += 1
            at_word_start = True
        elif ch == '$' and i + 1 < n and s[i + 1] == '{':
            brace += 1
            i += 1
            at_word_start = False
        elif ch == '}' and brace:
            brace -= 1
            at_word_start = False
        elif ch == '(' and paren:
            paren += 1
            at_word_start = True
        elif ch == ')' and paren:
            paren -= 1
            at_word_start = False
        elif ch == '#' and not brace and at_word_start:
            return None if (paren or tick) else s[:i]
        else:
            at_word_start = ch in WORD_BREAK
        i += 1
    return None if q else s


def tokens(code):
    lx = shlex.shlex(code, posix=True, punctuation_chars=True)
    lx.whitespace_split = True
    lx.commenters = ''
    return list(lx)


lines = [(p, s, t, strip_comment(t)) for p in sys.argv[1:] for s, t in logical_lines(p)]

# Pass 1 - driver-path variables across EVERY scanned file.
drv = set()
for path, start, text, code in lines:
    if not code or LITERAL not in code:
        continue
    try:
        toks = tokens(code)
    except ValueError:
        continue
    for t in toks:
        m = NAME_ASSIGN.match(t)
        if m and m.group(2).endswith(LITERAL):
            drv.add(m.group(1))
alt = '|'.join(map(re.escape, sorted(drv)))
REF = re.compile(r'\$\{?(?:%s)(?![A-Za-z0-9_])' % alt) if drv else None
EXACT = re.compile(r'^\$\{?(?:%s)\}?$' % alt) if drv else None


def mentions(t):
    return LITERAL in t or bool(REF and REF.search(t))


def unclassified(path, start, text):
    print('UNCLASSIFIED\t%s:%d\t%s' % (path, start, text))


# Pass 2 - classify every mention, one simple command at a time.
for path, start, text, code in lines:
    if not mentions(text):
        continue
    if code is None or (mentions(code) and SUBST.search(code)):
        unclassified(path, start, text)
        continue
    if not mentions(code):
        continue                                    # only inside a comment
    try:
        toks = tokens(code)
    except ValueError:
        unclassified(path, start, text)
        continue
    bad = False
    i, n = 0, len(toks)
    while i < n:
        c = i
        while c < n and (toks[c] in LEAD or NAME_ASSIGN.match(toks[c])):
            m = NAME_ASSIGN.match(toks[c])
            if m:
                val = m.group(2)
                if (REF and REF.search(val)) or (LITERAL in val and not val.endswith(LITERAL)):
                    bad = True                      # alias / non-path value
                if c + 1 < n and toks[c + 1] == '(' and toks[c].endswith('='):
                    k = c + 2                       # NAME=( ... ) array
                    while k < n and toks[k] != ')':
                        k += 1
                    if any(mentions(t) for t in toks[c + 2:k]):
                        bad = True
                    c = k
            c += 1
        if c < n and toks[c] in ('[[', '[', 'test'):
            close = {'[[': ']]', '[': ']', 'test': None}[toks[c]]
            k = c + 1
            while k < n and (toks[k] != close if close else toks[k] not in CTRL):
                k += 1
            if close and k >= n:
                bad = True
            for p in range(c + 1, k):
                if mentions(toks[p]) and not (EXACT and EXACT.match(toks[p])
                                              and toks[p - 1] in FILE_TESTS):
                    bad = True
            i = k + 1
            continue
        j = c
        while j < n and toks[j] not in CTRL:
            j += 1
        body = toks[c:j]
        if len(body) >= 2 and VAR_WORD.match(body[0]) and EXACT and EXACT.match(body[1]):
            based = any('base_args' in t or '--base-file' in t for t in body[2:])
            print('INVOKE\t%d\t%s:%d' % (based, path, start))
            body = body[2:]
        if any(mentions(t) for t in body):
            bad = True
        i = j + 1
    if bad:
        unclassified(path, start, text)
PY
)

# scan_driver_refs <file>... -> INVOKE / UNCLASSIFIED rows. A scanner crash is
# itself an unclassified row, so it can never read as "nothing found".
scan_driver_refs() {
    python3 -c "$DRIVER_SCAN_PY" "$@" \
        || printf 'UNCLASSIFIED\tscanner\tSCANNER_FAILED rc=%s\n' "$?"
}

# count_driver_sites <file>... -> "<invocations> <with_base>"
count_driver_sites() {
    scan_driver_refs "$@" | awk -F'\t' '$1 == "INVOKE" { n++; b += $2 } END { print n + 0, b + 0 }'
}

# unclassified_count <file>... -> number of UNCLASSIFIED rows
unclassified_count() {
    scan_driver_refs "$@" | awk -F'\t' '$1 == "UNCLASSIFIED" { n++ } END { print n + 0 }'
}

TMP3="$(mktemp -d)"

# plant_case <file> <line>: a driver-path assignment, then <line>.
plant_case() {
    printf '%s\n' '_X_SCRIPT="$DIR/../board/aitask_merge.py"' "$2" > "$1"
}

# Planted control: proves the matcher joins continuation lines and tells a
# based call from an unbased one.
cat > "$TMP3/planted.sh" <<'EOF'
_X_SCRIPT="$DIR/../board/aitask_merge.py"
"$_X_PYTHON" "$_X_SCRIPT" "$f" \
    --batch --rebase ${base_args[@]+"${base_args[@]}"}
"$_X_PYTHON" "$_X_SCRIPT" "$f" \
    --batch --rebase
EOF
assert_eq "Planted control: 2 recognized split invocations, 1 with a base" \
    "2 1" "$(count_driver_sites "$TMP3/planted.sh")"
assert_eq "Planted control: nothing unclassified" \
    "0" "$(unclassified_count "$TMP3/planted.sh")"

# Benign negative control: legitimate non-invocation references stay silent.
cat > "$TMP3/benign.sh" <<'EOF'
# the driver lives at board/aitask_merge.py
_X_SCRIPT=""
_X_SCRIPT="$DIR/../board/aitask_merge.py"  # aitask_merge.py, resolved lazily
[[ -n "$_X_PYTHON" && -f "$_X_SCRIPT" ]]
[ -r "${_X_SCRIPT}" ] || exit 1
echo "$_X_SCRIPT_DIR"
EOF
assert_eq "Benign references: no invocation" "0 0" "$(count_driver_sites "$TMP3/benign.sh")"
assert_eq "Benign references: nothing unclassified" "0" "$(unclassified_count "$TMP3/benign.sh")"

# Class 1: the driver-path variable is assigned in a DIFFERENT (sourced) file.
cat > "$TMP3/defs.sh" <<'EOF'
_X_SCRIPT="$DIR/../board/aitask_merge.py"
EOF
cat > "$TMP3/caller.sh" <<'EOF'
"$_X_PYTHON" "$_X_SCRIPT" "$f" \
    --batch --rebase
EOF
assert_eq "Cross-file driver variable: the unbased call is recognized" \
    "1 0" "$(count_driver_sites "$TMP3/defs.sh" "$TMP3/caller.sh")"

# Class 2a: an interpreter variable whose name lacks PYTHON.
plant_case "$TMP3/interp.sh" '"$INTERP" "$_X_SCRIPT" "$f" --batch --rebase'
assert_eq "Non-PYTHON interpreter: the unbased call is recognized" \
    "1 0" "$(count_driver_sites "$TMP3/interp.sh")"

# One planted line per case that must be a hard failure (exactly one row).
while IFS='|' read -r label line; do
    plant_case "$TMP3/case.sh" "$line"
    assert_eq "Unclassified: $label" "1" "$(unclassified_count "$TMP3/case.sh")"
done <<'EOF'
literal-path call|python3 "$DIR/../board/aitask_merge.py" "$f" --batch --rebase --base-file x
array call|cmd=("$_X_PYTHON" "$_X_SCRIPT" "$f" --batch --rebase --base-file "$b")
alias of the driver path|S="$_X_SCRIPT"
interpreter option before the driver|"$INTERP" -s "$_X_SCRIPT" "$f" --batch --rebase
file-test exemption ends at the test command|[[ -f "$_X_SCRIPT" ]] && "$INTERP" -s "$_X_SCRIPT" "$f"
non-file test of the driver path|[[ -n "$_X_SCRIPT" ]]
ambiguous ANSI-C quoting|echo $'a\'b'; "$INTERP" "$_X_SCRIPT" "$g"
command substitution in a driver-path assignment|NEXT="$("$INTERP" /tmp/aitask_merge.py "$g" --batch --rebase)/aitask_merge.py"
backtick substitution in a driver-path assignment|NEXT=`"$INTERP" /tmp/aitask_merge.py "$g"`/aitask_merge.py
driver call wrapped in a substitution|out=$("$_X_PYTHON" "$_X_SCRIPT" "$f" --base-file "$b")
EOF

# A recognized call on a line must not mask a second call on the same line.
plant_case "$TMP3/compound.sh" \
    '"$I" "$_X_SCRIPT" "$f" --base-file "$b"; "$I" "$_X_SCRIPT" "$g" --batch --rebase'
assert_eq "Compound line: each call is counted, the unbased one is seen" \
    "2 1" "$(count_driver_sites "$TMP3/compound.sh")"
plant_case "$TMP3/compound.sh" \
    '"$I" "$_X_SCRIPT" "$f" --base-file "$b"; "$I" -u "$_X_SCRIPT" "$g"'
assert_eq "Compound line with an unsupported call: the based call is counted" \
    "1 1" "$(count_driver_sites "$TMP3/compound.sh")"
assert_eq "Compound line with an unsupported call: it is unclassified" \
    "1" "$(unclassified_count "$TMP3/compound.sh")"

# Comment boundaries: a mid-word `#` is not a comment, a genuine one is.
plant_case "$TMP3/c.sh" 'echo release#candidate; "$INTERP" "$_X_SCRIPT" "$g" --batch --rebase'
assert_eq "Mid-word # does not hide the call after it" "1 0" "$(count_driver_sites "$TMP3/c.sh")"
plant_case "$TMP3/c.sh" 'n=${f##*/}; "$INTERP" "$_X_SCRIPT" "$g" --batch --rebase'
assert_eq "\${f##*/} does not hide the call after it" "1 0" "$(count_driver_sites "$TMP3/c.sh")"
plant_case "$TMP3/c.sh" '"$I" "$_X_SCRIPT" "$f" --base-file "$b"  # aitask_merge.py call'
assert_eq "Genuine trailing comment: the based call is counted" "1 1" "$(count_driver_sites "$TMP3/c.sh")"
assert_eq "Genuine trailing comment: nothing unclassified" "0" "$(unclassified_count "$TMP3/c.sh")"
plant_case "$TMP3/c.sh" 'echo x # "$INTERP" "$_X_SCRIPT" "$g"'
assert_eq "Commented-out call: no row at all" \
    "0 0 0" "$(count_driver_sites "$TMP3/c.sh") $(unclassified_count "$TMP3/c.sh")"

# A backslash ending a COMMENT does not continue the line, and `\\` is an
# escaped backslash: the next line is a separate command bash executes.
while IFS='|' read -r label first; do
    printf '%s\n' '_X_SCRIPT="$DIR/../board/aitask_merge.py"' "$first" \
        '"$INTERP" "$_X_SCRIPT" "$g" --batch --rebase' > "$TMP3/c.sh"
    assert_eq "Not a continuation ($label): the next line's unbased call is seen" \
        "1 0" "$(count_driver_sites "$TMP3/c.sh")"
done <<'EOF'
full-line comment ending in a backslash|# note \
inline comment ending in a backslash|echo x # note \
escaped backslash at end of line|echo x\\
EOF

# Differential against REAL bash: the scanner reports a row for a probe iff bash
# actually executes the probe's call. `@CALL@` becomes a call whose stand-in
# interpreter prints `CALLED p<N>`; `@TAB@` becomes a literal tab and `@NL@` a
# newline (multi-line probes exercise continuation joining).
mkdir -p "$TMP3/diff"
cp "$TMP3/defs.sh" "$TMP3/diff/defs.sh"
{
    echo '_standin() { echo "CALLED $2"; }'
    echo 'INTERP=_standin; _X_SCRIPT=drv; f=a/b; x=; a=; b=c'
} > "$TMP3/diff/run.sh"
probe_ids=()
probe_n=0
while IFS= read -r probe; do
    probe_n=$((probe_n + 1))
    probe="${probe//@TAB@/$'\t'}"
    probe="${probe//@NL@/$'\n'}"
    probe="${probe//@CALL@/\"\$INTERP\" \"\$_X_SCRIPT\" p$probe_n --batch --rebase}"
    printf '%s\n' "$probe" > "$TMP3/diff/p$probe_n.sh"
    printf '%s\n' "$probe" >> "$TMP3/diff/run.sh"
    probe_ids+=("p$probe_n")
done <<'EOF'
echo x\ #candidate; @CALL@
echo x\;#candidate; @CALL@
echo x\|#c; @CALL@
echo x\\ #c; @CALL@
echo release#candidate; @CALL@
n=${f##*/}; @CALL@
echo $#; @CALL@
echo ${x:- #}; @CALL@
echo ${x:-"}" #}; @CALL@
echo "a # b" ; @CALL@
echo 'it''s #x'; @CALL@
a=1;# c; @CALL@
echo x #; @CALL@
echo "q"#c; @CALL@
echo 'q'#c; @CALL@
echo x&#c; @CALL@
echo $(echo a)#c; @CALL@
echo $(echo ")")#c; @CALL@
echo $((1+2))#c; @CALL@
echo $((2#101)); @CALL@
cat <(echo a)#c; @CALL@
(echo a)#c; @CALL@
(echo a) #c; @CALL@
echo `echo a`#c; @CALL@
echo `echo a` #c; @CALL@
echo a@TAB@#c; @CALL@
echo "x\"#"; @CALL@
echo $'a\'b'; @CALL@
#@CALL@
  # @CALL@
@CALL@ # trailing
# note \@NL@@CALL@
echo x # note \@NL@@CALL@
echo x\\@NL@@CALL@
echo x \@NL@&& @CALL@
@CALL@ # note \@NL@echo next
EOF
executed="$(cd "$TMP3/diff" && bash ./run.sh 2>/dev/null </dev/null | sed -n 's/^CALLED //p')"
reported="$(scan_driver_refs "$TMP3/diff"/defs.sh "$TMP3/diff"/p*.sh \
    | grep -oE '/p[0-9]+\.sh:' | sed 's|^/||; s|\.sh:$||' | sort -u)"
ran=0 skipped=0 diverged=""
for id in "${probe_ids[@]}"; do
    in_bash=no; in_scan=no
    grep -qx "$id" <<<"$executed" && in_bash=yes
    grep -qx "$id" <<<"$reported" && in_scan=yes
    if [[ $in_bash == yes ]]; then ran=$((ran + 1)); else skipped=$((skipped + 1)); fi
    [[ $in_bash == "$in_scan" ]] || diverged+="$id(bash=$in_bash scan=$in_scan $(head -n1 "$TMP3/diff/$id.sh")) "
done
assert_eq "Differential exercises both directions (>=15 executed, >=8 commented out)" \
    "1" "$([[ $ran -ge 15 && $skipped -ge 8 ]] && echo 1 || echo 0)"
assert_eq "Scanner reports a probe iff real bash executes its call" "" "$diverged"

# Base-removal mutant of the real call site must be caught.
automerge_src="$(cat "$PROJECT_DIR/.aitask-scripts/lib/task_automerge.sh")"
# shellcheck disable=SC2124  # the single-quoted pattern is literal text, not an array
automerge_mut="${automerge_src//' ${base_args[@]+"${base_args[@]}"}'/}"
assert_eq "Mutant precondition: removing base_args changed the copy" \
    "1" "$([[ "$automerge_mut" != "$automerge_src" ]] && echo 1 || echo 0)"
printf '%s\n' "$automerge_mut" > "$TMP3/task_automerge_mutant.sh"
assert_eq "Base-removal mutant of the real call site is caught" \
    "1 0" "$(count_driver_sites "$TMP3/task_automerge_mutant.sh")"

rm -rf "$TMP3"

# Real tree.
mapfile -t SH_FILES < <(find "$PROJECT_DIR/.aitask-scripts" -type f -name '*.sh' | sort)
tree_rows="$(scan_driver_refs "${SH_FILES[@]}")"
read -r invocations with_base < <(awk -F'\t' '$1 == "INVOKE" { n++; b += $2 } END { print n + 0, b + 0 }' <<<"$tree_rows")
assert_eq "At least one recognized driver invocation exists (guard is not vacuous)" \
    "1" "$([[ $invocations -ge 1 ]] && echo 1 || echo 0)"
assert_eq "The shared auto-merge library's call site is recognized" \
    "1" "$(grep -c $'^INVOKE\t.*/lib/task_automerge\\.sh:' <<<"$tree_rows" | awk '{ print ($1 >= 1) }')"
assert_eq "Every recognized driver invocation passes --base-file" \
    "$invocations" "$with_base"
assert_eq "No unclassified aitask_merge.py reference (update the guard)" \
    "" "$(grep '^UNCLASSIFIED' <<<"$tree_rows")"

# --- Test 4: an add/add conflict has no stage 1 and must not crash ---
echo "--- Test 4: missing/unreadable base degrades, never crashes ---"

TMP4="$(mktemp -d)"
cat > "$TMP4/conflicted.md" <<'EOF'
---
priority: high
<<<<<<< HEAD
boardgroup: alpha
=======
boardgroup: beta
>>>>>>> local
updated_at: 2026-01-01 12:00
---
Body
EOF
out4=$(cd "$PROJECT_DIR/.aitask-scripts/board" && \
    PYTHONDONTWRITEBYTECODE=1 python3 aitask_merge.py "$TMP4/conflicted.md" \
    --batch --rebase --base-file "$TMP4/does_not_exist.md" 2>/dev/null); rc4=$?
assert_eq "Unreadable base behaves like no base (PARTIAL, not a crash)" "2" "$rc4"
assert_contains "PARTIAL still names boardgroup" "boardgroup" "$out4"

rm -rf "$TMP4"

# --- Test 5: negative control on the CONTROL - far-apart edits merge cleanly ---
echo "--- Test 5: control discriminates - non-adjacent edits never conflict ---"

TMP5="$(setup_repos)"
# Same two semantic edits, but with filler between them so the hunks do not
# overlap. If this produced an unmerged path too, Test 1's positive control
# would be trivially true and would prove nothing.
far_task() {
    local path="$1" labels="$2" group_line="$3"
    {
        echo "---"
        echo "labels: $labels"
        echo "priority: high"
        echo "effort: low"
        echo "issue_type: bug"
        echo "status: Ready"
        echo "assigned_to: a@b.c"
        echo "created_at: 2026-01-01 08:00"
        echo "$group_line"
        echo "---"
        echo "Body stays the same"
    } > "$path"
}
(
    cd "$TMP5/local" || exit 1
    far_task aitasks/t1_sample.md "[ui]" "boardgroup: perf_work"
    git add -A; git commit -q -m "base far"; git push -q 2>/dev/null
) >/dev/null 2>&1
(
    cd "$TMP5/pc2" || exit 1
    git pull -q 2>/dev/null
    far_task aitasks/t1_sample.md "[ui]" 'boardgroup: ""'
    git add -A; git commit -q -m "pc2: ungroup far"; git push -q 2>/dev/null
) >/dev/null 2>&1
(
    cd "$TMP5/local" || exit 1
    far_task aitasks/t1_sample.md "[api, ui]" "boardgroup: perf_work"
    git add -A; git commit -q -m "local: status far"
    git fetch -q origin 2>/dev/null
    git rebase origin/main >/dev/null 2>&1 || git rebase origin/master >/dev/null 2>&1 || true
) >/dev/null 2>&1
far_unmerged=$(cd "$TMP5/local" && git diff --name-only --diff-filter=U 2>/dev/null)
assert_eq "Non-adjacent edits produce NO unmerged path" "" "$far_unmerged"

rm -rf "$TMP5"

# --- Test 6: followup_kind shares the resolver but DELETES, not tombstones ---
echo "--- Test 6: followup_kind clear removes the key end-to-end (t1468_1) ---"
# boardgroup persists "" to mean "deliberately ungrouped", so its resolved file
# keeps `boardgroup: ''` (Test 2). followup_kind has NO tombstone: a clear must
# leave no line at all. Same driver, same --base-file mechanism -- the contrast
# with Test 2's `str:''` is the point.
TMP6="$(mktemp -d)"
mkdir -p "$TMP6/aitasks"
cat > "$TMP6/aitasks/t1_sample.md" <<'EOF'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
<<<<<<< remote
labels: [ui, backend]
followup_kind: risk_mitigation
=======
labels: [ui, perf]
>>>>>>> local
updated_at: 2026-01-01 12:00
---
Body stays the same
EOF
cp "$TMP6/aitasks/t1_sample.md" "$TMP6/with_base.md"
cat > "$TMP6/base.md" <<'EOF'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [ui]
followup_kind: risk_mitigation
updated_at: 2026-01-01 09:00
---
Body stays the same
EOF

out6=$(cd "$PROJECT_DIR/.aitask-scripts/board" && \
    PYTHONDONTWRITEBYTECODE=1 python3 aitask_merge.py "$TMP6/with_base.md" \
    --batch --rebase --base-file "$TMP6/base.md" 2>/dev/null); rc6=$?
assert_eq "Local clear of followup_kind resolves against the base (exit 0)" "0" "$rc6"
assert_contains "Driver reports RESOLVED for the cleared kind" "RESOLVED" "$out6"
assert_eq "Cleared followup_kind is ABSENT, not a null or empty string" \
    "ABSENT" "$(parsed_field "$TMP6/with_base.md" followup_kind)"
assert_not_contains "Resolved file carries no followup_kind line at all" \
    "followup_kind" "$(cat "$TMP6/with_base.md")"

rm -rf "$TMP6"

# --- Summary ---
echo ""
echo "=== Results: $PASS passed, $FAIL failed (of $TOTAL) ==="
[[ $FAIL -eq 0 ]] || exit 1
exit 0
