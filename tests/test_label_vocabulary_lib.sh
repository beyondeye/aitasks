#!/usr/bin/env bash
# test_label_vocabulary_lib.sh - Unit tests for the shared label-vocabulary
# seam in lib/task_utils.sh (t1312): labels_file_path, sanitize_label,
# get_existing_labels, add_label_to_file, normalize_labels_csv and
# add_labels_csv_to_file.
#
# Covers:
#   - lazy path resolution (TASK_DIR read at call time, not source time)
#   - a caller-set LABELS_FILE wins over TASK_DIR
#   - sanitize_label maps invalid chars to "_" ("UI Stuff" -> ui_stuff) and
#     yields "" for an all-invalid token
#   - normalize_labels_csv splits / trims / dedupes and reports drops on stderr
#   - the rich return names exactly the newly-added labels
#   - a bare add_label_to_file on a present label does not abort a `set -e`
#     caller, and get_existing_labels exits 0 on an empty file
#   - control characters (newline/tab/CR) are folded by sanitize_label, do not
#     truncate normalize_labels_csv, and are refused at the add_label_to_file
#     write site (the vocabulary file is line-delimited)
#   - empty input is a total no-op (nothing written)
#   - collation is LC_ALL=C-deterministic under a UTF-8 locale
#   - every entry of the LIVE aitasks/metadata/labels.txt is a sanitize_label
#     fixed point (the byte-identity property the chatlink payload guard's
#     subset check relies on)
#
# Run: bash tests/test_label_vocabulary_lib.sh

set -e

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

# --- Setup: temp TASK_DIR, exported BEFORE sourcing the lib -----------------
# The lazy-resolution case is only meaningful if the lib is sourced while
# TASK_DIR already points somewhere else than it will at call time.

TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT

TASK_DIR="$TMPROOT/aitasks"
mkdir -p "$TASK_DIR/metadata"
export TASK_DIR

unset SCRIPT_DIR || true
unset LABELS_FILE || true

# shellcheck source=../.aitask-scripts/lib/task_utils.sh
source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"

VOCAB="$TASK_DIR/metadata/labels.txt"

# --- Case 1: path resolution ------------------------------------------------

assert_eq "labels_file_path derives from TASK_DIR" "$VOCAB" "$(labels_file_path)"

# TASK_DIR changed AFTER sourcing must be honored (lazy, not frozen).
_saved_task_dir="$TASK_DIR"
TASK_DIR="$TMPROOT/other"
assert_eq "labels_file_path is lazy (re-reads TASK_DIR)" \
    "$TMPROOT/other/metadata/labels.txt" "$(labels_file_path)"
TASK_DIR="$_saved_task_dir"

LABELS_FILE="$TMPROOT/explicit.txt"
assert_eq "caller-set LABELS_FILE wins over TASK_DIR" \
    "$TMPROOT/explicit.txt" "$(labels_file_path)"
unset LABELS_FILE

# --- Case 2: sanitize_label -------------------------------------------------

assert_eq "sanitize_label lowercases" "backend" "$(sanitize_label 'BackEnd')"
assert_eq "sanitize_label maps space to _" "ui_stuff" "$(sanitize_label 'UI Stuff')"
assert_eq "sanitize_label collapses runs of _" "a_b" "$(sanitize_label 'a  !! b')"
assert_eq "sanitize_label trims edge _" "core" "$(sanitize_label '__core__')"
assert_eq "sanitize_label keeps hyphens" "aitask-create" "$(sanitize_label 'aitask-create')"
assert_eq "sanitize_label of all-invalid is empty" "" "$(sanitize_label '!!!')"

# Control characters must be folded BEFORE the line-oriented stages. sed works
# one line at a time, so an embedded newline used to survive the whole pipeline
# and reach both the YAML inline list and the line-delimited vocabulary file.
assert_eq "sanitize_label folds an embedded newline" "alpha_beta" \
    "$(sanitize_label "$(printf 'alpha\nbeta')")"
assert_eq "sanitize_label folds tab and CR" "a_b_c" \
    "$(sanitize_label "$(printf 'a\tb\rc')")"
assert_eq "sanitize_label folds (never deletes) a newline, keeping halves apart" \
    "alpha_beta" "$(sanitize_label "$(printf 'alpha\nbeta')")"

# --- Case 3: get_existing_labels on an empty / missing file -----------------
# A `[[ -s file ]] && sort` tail returns 1 on an empty file and would abort the
# `set -e` in force here.

: > "$VOCAB"
out="$(get_existing_labels)"
assert_eq "get_existing_labels on empty file -> empty, exit 0" "" "$out"
assert_file_exists "ensure_labels_file created the vocabulary" "$VOCAB"

rm -f "$VOCAB"
get_existing_labels >/dev/null
assert_file_exists "get_existing_labels recreates a missing vocabulary" "$VOCAB"

# --- Case 4: normalize_labels_csv (pure) ------------------------------------

assert_eq "normalize splits and trims" "ui,backend" \
    "$(normalize_labels_csv 'ui,  backend' 2>/dev/null)"
assert_eq "normalize sanitizes each token" "ui_stuff,backend" \
    "$(normalize_labels_csv 'UI Stuff, Backend' 2>/dev/null)"
assert_eq "normalize dedupes, preserving order" "b,a" \
    "$(normalize_labels_csv 'b,a,b' 2>/dev/null)"
assert_eq "normalize of empty input is empty" "" \
    "$(normalize_labels_csv '' 2>/dev/null)"
assert_eq "normalize drops all-invalid tokens" "" \
    "$(normalize_labels_csv ',,!!!' 2>/dev/null)"
assert_eq "normalize reports drops on stderr" "DROPPED:!!!" \
    "$(normalize_labels_csv 'ui,!!!' 2>&1 >/dev/null)"
assert_eq "normalize keeps the valid token alongside a drop" "ui" \
    "$(normalize_labels_csv 'ui,!!!' 2>/dev/null)"

# `read -ra` consumes one line: without the control-char fold, an embedded
# newline truncated the token list and everything after it vanished silently.
assert_eq "normalize does not truncate at an embedded newline" "a_b,c" \
    "$(normalize_labels_csv "$(printf 'a\nb,c')" 2>/dev/null)"

# normalize_labels_csv must not write anything.
: > "$VOCAB"
normalize_labels_csv 'brand_new_from_normalize' >/dev/null 2>&1
assert_eq "normalize_labels_csv writes no vocabulary" "" "$(cat "$VOCAB")"

# --- Case 5: add_label_to_file / rich return --------------------------------

: > "$VOCAB"
printf 'existing\n' > "$VOCAB"

add_labels_csv_to_file 'existing,fresh_one,UI Stuff,!!!'
assert_eq "normalized CSV surfaced" "existing,fresh_one,ui_stuff" "$AIT_LABELS_NORMALIZED"
assert_eq "rich return names ONLY the newly-added labels" "fresh_one ui_stuff" \
    "${AIT_LABELS_ADDED[*]}"
assert_eq "rich return names the dropped token" "!!!" "${AIT_LABELS_DROPPED[*]}"
assert_contains "vocabulary gained fresh_one" "fresh_one" "$(cat "$VOCAB")"
assert_contains "vocabulary gained ui_stuff" "ui_stuff" "$(cat "$VOCAB")"
assert_eq "pre-existing label not duplicated" "1" "$(grep -c '^existing$' "$VOCAB")"

# Re-registering the same CSV adds nothing.
add_labels_csv_to_file 'existing,fresh_one'
assert_eq "re-register adds nothing" "0" "${#AIT_LABELS_ADDED[@]}"

# Empty input is a total no-op, and must clear the previous call's state.
before="$(cat "$VOCAB")"
add_labels_csv_to_file ''
assert_eq "empty input adds nothing" "0" "${#AIT_LABELS_ADDED[@]}"
assert_eq "empty input clears the normalized CSV" "" "$AIT_LABELS_NORMALIZED"
assert_eq "empty input leaves the vocabulary byte-identical" "$before" "$(cat "$VOCAB")"

# A bare call under `set -e` (as aitask_update.sh makes it) must not abort.
add_label_to_file "existing"
assert_eq "bare add_label_to_file on a present label survives set -e" "ok" "ok"

# Write-site guard: a control character would inject an extra line into the
# line-delimited vocabulary that no reader could distinguish from a real entry.
: > "$VOCAB"
add_label_to_file "$(printf 'x\ny')" 2>/dev/null
assert_eq "a control-char label is refused, not written" "0" "$(wc -l < "$VOCAB" | xargs)"
add_label_to_file "$(printf 'p\tq')" 2>/dev/null
assert_eq "a tab-bearing label is refused too" "0" "$(wc -l < "$VOCAB" | xargs)"
guard_warn="$(add_label_to_file "$(printf 'x\ny')" 2>&1 >/dev/null)"
assert_contains_ci "the refusal is warned, not silent" "control character" "$guard_warn"
add_label_to_file "clean_label"
assert_eq "a clean label still writes" "1" "$(wc -l < "$VOCAB" | xargs)"

# Restore the fixture the later cases expect.
printf 'existing\nfresh_one\nui_stuff\n' > "$VOCAB"

# Labels may legitimately start with "-": the grep guard must use -F -x --.
add_label_to_file "-leading-hyphen"
assert_eq "a leading-hyphen label is stored" "1" "$(grep -c -- '^-leading-hyphen$' "$VOCAB")"
add_label_to_file "-leading-hyphen"
assert_eq "a leading-hyphen label is not duplicated" "1" "$(grep -c -- '^-leading-hyphen$' "$VOCAB")"

# --- Case 6: collation determinism ------------------------------------------
# The committed file must not reorder by locale. Build the same vocabulary
# under two locales and require byte-identical results.

# The tokens are chosen so C and en_US.UTF-8 collation genuinely DISAGREE:
# C compares bytes, so 'ait-c' (0x2d) < 'ait_b' (0x5f) < 'aitaa' (0x61); UTF-8
# collation ignores punctuation at the first level, giving 'aitaa' first. A set
# of plain lowercase words would order identically under both and make this
# case vacuous (verified: dropping the LC_ALL=C pin must fail this test).
build_vocab() {
    local target="$1"
    : > "$target"
    LABELS_FILE="$target"
    add_labels_csv_to_file 'aitaa,ait_b,ait-c,Zeta,Alpha'
    unset LABELS_FILE
}

# BOTH builds run in an explicit-locale subshell. Relying on the ambient
# environment for one of them makes the case vacuous whenever the developer's
# shell already exports the other locale (this machine's LANG is en_US.UTF-8).
(
    export LC_ALL=C LANG=C
    build_vocab "$TMPROOT/c.txt"
)
(
    export LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
    build_vocab "$TMPROOT/utf8.txt"
)

if diff -q "$TMPROOT/c.txt" "$TMPROOT/utf8.txt" >/dev/null 2>&1; then
    PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
else
    FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
    echo "FAIL: vocabulary ordering is locale-dependent"
    diff "$TMPROOT/c.txt" "$TMPROOT/utf8.txt" || true
fi

# ...and the order that survives is the C one, not merely "some stable order":
# a pin to the wrong locale would still be self-consistent.
assert_eq "vocabulary is ordered by C collation" \
    "ait-c ait_b aitaa alpha zeta" "$(tr '\n' ' ' < "$TMPROOT/c.txt" | xargs)"

# --- Case 7: the LIVE vocabulary is a sanitize_label fixed point ------------
# The chatlink payload guard accepts a remote label only when it byte-matches a
# labels.txt line, and promises the created task is byte-identical to the
# payload. A non-canonical entry (hand-edited uppercase, a space) would be
# rewritten by the create-side normalization and break that promise.

LIVE_VOCAB="$PROJECT_DIR/aitasks/metadata/labels.txt"
if [[ -f "$LIVE_VOCAB" ]]; then
    nonfixed=""
    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        case "$line" in \#*) continue ;; esac
        if [[ "$(sanitize_label "$line")" != "$line" ]]; then
            nonfixed="${nonfixed}${line} "
        fi
    done < "$LIVE_VOCAB"
    assert_eq "every live labels.txt entry is a sanitize_label fixed point" "" "$nonfixed"

    live_sorted="$(LC_ALL=C sort -u "$LIVE_VOCAB")"
    assert_eq "live labels.txt is LC_ALL=C sorted and deduped" \
        "$live_sorted" "$(cat "$LIVE_VOCAB")"
else
    echo "SKIP: live labels.txt not found at $LIVE_VOCAB"
fi

# --- Summary ---

echo
echo "Results: $PASS passed, $FAIL failed (total $TOTAL)"
[[ $FAIL -eq 0 ]]
