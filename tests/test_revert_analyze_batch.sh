#!/usr/bin/env bash
# test_revert_analyze_batch.sh - Batch task->file-set map (t1569_2).
#
# `--task-files` stays the oracle; `--batch-map` must reproduce it for every id
# at whole-corpus cost. These are the cases where a naive batch silently
# diverges, each proven against a synthetic repo rather than the live corpus:
#
#   - Renames: the oracle uses `git diff-tree` (plumbing, renames OFF, so a
#     rename is a delete + an add) while `git log --name-only` is porcelain and
#     collapses it to the new path. Without --no-renames they disagree.
#   - `(t100, t101)` is not the literal `(t100)`; the oracle matches NEITHER id.
#   - A parent whose work landed only under a child id whose task file is gone
#     from disk: the oracle returns EMPTY, and the batch must agree -- reporting
#     UNKNOWN_HISTORY, never NO_FILES (which would read as "touched nothing").
#   - RECOVERED_* is opt-in and must never perturb the default product.
#   - The three-source id enumeration used by the acceptance oracle: a
#     commit-map-only enumeration omits every off-disk-child parent, and a NUL
#     in the stream empties the commit source with exit 1 and no diagnostic.
#
# Run: bash tests/test_revert_analyze_batch.sh
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0; FAIL=0; TOTAL=0
RA="$PROJECT_DIR/.aitask-scripts/aitask_revert_analyze.sh"
PY="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null; resolve_python 2>/dev/null || echo python3)"

# ONE parent fixture root, created and registered HERE in the parent shell --
# every caller does `fx="$(new_repo)"`, so a CLEANUP_DIRS+=(...) inside new_repo
# would run in a command-substitution subshell and be lost (see
# tests/test_change_surface.sh L36-44).
FIXTURE_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/test_rabatch_XXXXXX")"
cleanup() { [[ -n "${FIXTURE_ROOT:-}" ]] && rm -rf "$FIXTURE_ROOT"; }
trap cleanup EXIT

# new_repo -> path to a fresh git repo with aitasks/ + aiplans/ and one commit.
new_repo() {
    local tmp
    tmp="$(mktemp -d "$FIXTURE_ROOT/repo_XXXXXX")"
    (
        cd "$tmp" || exit 1
        git init -q .
        git config user.email test@example.com
        git config user.name Test
        git config commit.gpgsign false
        mkdir -p aitasks/archived aiplans
        echo seed > seed.txt
        git add -A
        git commit -qm "init"
    ) >/dev/null 2>&1
    echo "$tmp"
}

# ra <dir> <args...> -- run the analyzer from the fixture root.
ra() { local d="$1"; shift; ( cd "$d" && "$RA" "$@" ); }

# commit_file <dir> <path> <content> <subject>
commit_file() {
    local d="$1" path="$2" content="$3" subject="$4"
    ( cd "$d" && mkdir -p "$(dirname "$path")" && printf '%s\n' "$content" > "$path" \
        && git add -A && git commit -qm "$subject" ) >/dev/null 2>&1
}

# --------------------------------------------------------------------------
# 1. FILES / NO_FILES / UNKNOWN_HISTORY
# --------------------------------------------------------------------------
fx="$(new_repo)"
commit_file "$fx" "src/a.py" "a" "feature: add a (t10)"
( cd "$fx" && git commit -q --allow-empty -m "chore: nothing (t11)" ) >/dev/null 2>&1
out="$(ra "$fx" --batch-map --ids-from <(printf '10\n11\n12\n') 2>/dev/null)"

assert_contains "t10 reports its file" "TASKFILES:10|src/a.py" "$out"
assert_contains "t10 is FILES" "STATUS:10|FILES" "$out"
assert_contains "t11 matched but touched nothing" "STATUS:11|NO_FILES" "$out"
assert_contains "t12 never matched" "STATUS:12|UNKNOWN_HISTORY" "$out"

# STATUS is emitted for every QUERIED id, so absence is never a state.
assert_eq "one STATUS per queried id" "3" "$(grep -c '^STATUS:' <<<"$out")"

# --------------------------------------------------------------------------
# 2. Rename divergence -- the batch must emit BOTH old and new paths.
#    This is what --no-renames buys; without it only the new path appears.
# --------------------------------------------------------------------------
fx="$(new_repo)"
commit_file "$fx" "old/name.py" "content" "feature: add (t20)"
( cd "$fx" && mkdir -p new && git mv old/name.py new/name.py \
    && git commit -qm "refactor: move it (t20)" ) >/dev/null 2>&1

batch="$(ra "$fx" --batch-map --ids-from <(printf '20\n') 2>/dev/null | grep '^TASKFILES:20|' | cut -d'|' -f2- | sort -u)"
oracle="$(ra "$fx" --task-files 20 2>/dev/null | cut -d'|' -f2 | sort -u)"

assert_contains "batch keeps the pre-rename path" "old/name.py" "$batch"
assert_contains "batch has the post-rename path" "new/name.py" "$batch"
assert_eq "rename: batch is byte-equal to the oracle" "$oracle" "$batch"

# --------------------------------------------------------------------------
# 3. Comma-form negative control -- `(t100, t101)` matches NEITHER id.
# --------------------------------------------------------------------------
fx="$(new_repo)"
commit_file "$fx" "src/c.py" "c" "ait: link follow-ups (t100, t101)"
out="$(ra "$fx" --batch-map --ids-from <(printf '100\n101\n') 2>/dev/null)"

assert_contains "comma form does not match t100" "STATUS:100|UNKNOWN_HISTORY" "$out"
assert_contains "comma form does not match t101" "STATUS:101|UNKNOWN_HISTORY" "$out"
assert_eq "comma form yields no file rows" "0" "$(grep -c '^TASKFILES:' <<<"$out")"

oracle="$(ra "$fx" --task-files 100 2>/dev/null | cut -d'|' -f2 | sort -u)"
assert_eq "oracle agrees: comma form matches nothing" "" "$oracle"

# --------------------------------------------------------------------------
# 4. Off-disk-child divergence.
#
#    t30's work landed ONLY under t30_1, whose task file is not on disk. The
#    oracle's disk-derived expansion therefore finds nothing, and the batch must
#    agree -- UNKNOWN_HISTORY, never NO_FILES.
# --------------------------------------------------------------------------
fx="$(new_repo)"
commit_file "$fx" "src/child.py" "c" "feature: child work (t30_1)"
out="$(ra "$fx" --batch-map --ids-from <(printf '30\n30_1\n') 2>/dev/null)"

assert_contains "off-disk child: parent is UNKNOWN_HISTORY" "STATUS:30|UNKNOWN_HISTORY" "$out"
assert_eq "off-disk child: parent has no paths" "0" "$(grep -c '^TASKFILES:30|' <<<"$out")"
assert_contains "the child itself is FILES" "STATUS:30_1|FILES" "$out"
oracle="$(ra "$fx" --task-files 30 2>/dev/null | cut -d'|' -f2 | sort -u)"
assert_eq "oracle agrees: parent resolves empty" "" "$oracle"

# The same fixture WITH the child on disk: the oracle now expands into it.
mkdir -p "$fx/aitasks/t30"
printf -- '---\nstatus: Ready\n---\nbody\n' > "$fx/aitasks/t30/t30_1_child.md"
out="$(ra "$fx" --batch-map --ids-from <(printf '30\n') 2>/dev/null)"
assert_contains "on-disk child IS expanded into the parent" "TASKFILES:30|src/child.py" "$out"
assert_contains "on-disk child makes the parent FILES" "STATUS:30|FILES" "$out"

# --------------------------------------------------------------------------
# 5. RECOVERED_* isolation -- opt-in, and never perturbs the default product.
# --------------------------------------------------------------------------
fx="$(new_repo)"
commit_file "$fx" "src/r.py" "r" "feature: child work (t40_1)"
ids="$fx/ids.txt"; printf '40\n40_1\n' > "$ids"

default_out="$(ra "$fx" --batch-map --ids-from "$ids" 2>/dev/null)"
rec_out="$(ra "$fx" --batch-map --ids-from "$ids" --with-recovered 2>/dev/null)"

assert_eq "default output carries no RECOVERED_* lines" "0" "$(grep -c '^RECOVERED' <<<"$default_out")"
assert_eq "recovered set is non-empty (not vacuous)" "1" "$(grep -c '^RECOVERED_TASKFILES:40|' <<<"$rec_out")"

# (b) --with-recovered leaves every default line byte-identical.
assert_eq "--with-recovered does not alter the default product" "$(grep -E '^(TASKFILES|STATUS|COMMIT|TRACKED):' <<<"$default_out")" "$(grep -E '^(TASKFILES|STATUS|COMMIT|TRACKED):' <<<"$rec_out")"

assert_contains "default status stays UNKNOWN_HISTORY" "STATUS:40|UNKNOWN_HISTORY" "$rec_out"
assert_contains "recovered status finds the history" "RECOVERED_STATUS:40|FILES" "$rec_out"
assert_contains "divergence is counted" "RECOVERED_DIVERGES:40|1" "$rec_out"

# --------------------------------------------------------------------------
# 6. --help documents the constraints a consumer must not drop.
# --------------------------------------------------------------------------
help_out="$("$RA" --help 2>&1)"
assert_contains "help lists the subcommand" "--batch-map" "$help_out"
assert_contains "help narrows the UNKNOWN_HISTORY meaning" "disk-derived expansion" "$help_out"
assert_contains "help names the only sanctioned recovered caller" "aitask_parallel_admission.sh" "$help_out"
assert_contains "help states the no-substitution rule" "must not substitute" "$help_out"

# --------------------------------------------------------------------------
# 7. Framing fails closed: a corrupt stream emits NO map and exits non-zero.
# --------------------------------------------------------------------------
TFS="$PROJECT_DIR/.aitask-scripts/lib/task_file_sets.py"
bad_out="$(printf '\0nothex\0 not-a-ts\0msg\0' | "$PY" "$TFS" --root "$fx" 2>/dev/null)"
bad_rc=$?
assert_eq "framing violation emits no map" "" "$bad_out"
assert_eq "framing violation exits non-zero" "nonzero" "$( [ "$bad_rc" -ne 0 ] && echo nonzero || echo zero )"
bad_err="$(printf '\0nothex\0 not-a-ts\0msg\0' | "$PY" "$TFS" --root "$fx" 2>&1 >/dev/null)"
assert_contains "framing violation names itself" "FRAMING_ERROR:" "$bad_err"

# 7b. Truncation at the CLI level: a VALID record followed by a cut-short header
#     must emit no map and exit non-zero. Returning just the good record would
#     be a short map that looks complete and exits 0.
sha_a="$(printf 'a%.0s' $(seq 40))"; sha_b="$(printf 'b%.0s' $(seq 40))"
trunc_stream() { printf '\000%s\000100\000msg (t1)\000\nfile.py\000\000%s\000200\000' "$sha_a" "$sha_b"; }
trunc_out="$(trunc_stream | "$PY" "$TFS" --root "$fx" 2>/dev/null)"; trunc_rc=$?
assert_eq "valid-prefix + truncation emits no map" "" "$trunc_out"
assert_eq "valid-prefix + truncation exits non-zero" "nonzero" "$( [ "$trunc_rc" -ne 0 ] && echo nonzero || echo zero )"
trunc_err="$(trunc_stream | "$PY" "$TFS" --root "$fx" 2>&1 >/dev/null)"
assert_contains "truncation names itself" "FRAMING_ERROR:" "$trunc_err"

# Positive control for the guard: the SAME prefix, properly terminated, DOES
# produce a map -- so the assertions above cannot pass merely because the
# parser rejects everything.
ok_out="$(printf '\000%s\000100\000msg (t1)\000\nfile.py\000' "$sha_a" | "$PY" "$TFS" --root "$fx" 2>/dev/null)"
assert_contains "positive control: a well-formed stream still yields a map" "TASKFILES:1|file.py" "$ok_out"

# --------------------------------------------------------------------------
# 8. The acceptance oracle's three-source enumeration.
#
#    Asserted on the REAL pipeline, because the defect this guards lived in the
#    pipeline: a NUL in the commit stream makes grep treat stdin as binary and
#    the source silently empties.
# --------------------------------------------------------------------------
fx="$(new_repo)"
commit_file "$fx" "src/p.py" "p" "feature: parent work (t50)"
commit_file "$fx" "src/q.py" "q" "feature: child work (t60_1)"   # t60 is off-disk
printf -- '---\nstatus: Ready\n---\nb\n' > "$fx/aitasks/t70_nohistory.md"  # no commits at all

src_a="$( cd "$fx" && { ls aitasks/t*.md aitasks/t*/t*.md aitasks/archived/t*.md aitasks/archived/t*/t*.md 2>/dev/null; } \
    | sed -E 's#.*/t([0-9]+(_[0-9]+)?)_.*#\1#' | sort -u )"
src_b="$( cd "$fx" && git log --all --format='%B' | grep -oE '\(t[0-9]+(_[0-9]+)?\)' | tr -d '()' | sed 's/^t//' | sort -u )"
src_c="$( printf '%s\n%s\n' "$src_a" "$src_b" | grep '_' | cut -d'_' -f1 | sort -u )"
enum="$( printf '%s\n%s\n%s\n' "$src_a" "$src_b" "$src_c" | sed '/^$/d' | sort -u )"

assert_eq "commit source (b) is non-empty -- the grep-binary regression guard" "nonempty" "$( [ -n "$src_b" ] && echo nonempty || echo EMPTY )"
assert_contains "enumeration includes a no-history id (class B)" "70" "$enum"
assert_contains "enumeration includes the off-disk-child parent (class A)" "60" "$enum"

# Negative control: the commit map ALONE omits the class-A parent.
assert_eq "commit-map-only enumeration omits the class-A parent" "0" "$(grep -cx '60' <<<"$src_b")"
assert_eq "commit-map-only enumeration omits the no-history id" "0" "$(grep -cx '70' <<<"$src_b")"

# And the NUL form of source (b) really does empty out -- the reason %x00 was dropped.
nul_b="$( cd "$fx" && git log --all --format='%B%x00' | grep -oE '\(t[0-9]+(_[0-9]+)?\)' 2>/dev/null | wc -l )"
assert_eq "a NUL in the commit stream silently empties source (b)" "0" "$nul_b"

# --------------------------------------------------------------------------
# 9. Byte-equality over that enumeration, on the fixture.
# --------------------------------------------------------------------------
printf '%s\n' "$enum" > "$fx/enum.txt"
map="$(ra "$fx" --batch-map --ids-from "$fx/enum.txt" 2>/dev/null)"
mismatch=""
while read -r id; do
    [ -n "$id" ] || continue
    o="$(ra "$fx" --task-files "$id" 2>/dev/null | cut -d'|' -f2 | sort -u)"
    b="$(grep "^TASKFILES:${id}|" <<<"$map" | cut -d'|' -f2- | sort -u)"
    [ "$o" = "$b" ] || mismatch="$mismatch $id"
done <<< "$enum"
assert_eq "batch is byte-equal to the oracle for every enumerated id" "" "$mismatch"

# --------------------------------------------------------------------------
# 10. COMMIT: index carries the timestamp t1569_5 needs.
# --------------------------------------------------------------------------
assert_eq "commit index has one row for the file" "1" "$(grep -c '^COMMIT:src/p.py|' <<<"$map")"
ts="$(grep '^COMMIT:src/p.py|' <<<"$map" | cut -d'|' -f3)"
assert_eq "commit index carries an integer committed_at" "numeric" "$( [[ "$ts" =~ ^[0-9]+$ ]] && echo numeric || echo "not-numeric:$ts" )"

# --------------------------------------------------------------------------
echo ""
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
[[ "$FAIL" -eq 0 ]]
