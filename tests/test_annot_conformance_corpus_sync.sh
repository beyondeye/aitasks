#!/usr/bin/env bash
# test_annot_conformance_corpus_sync.sh - the annot conformance fixtures
# (goengines/internal/testmap/annot/testdata/conformance) stay exact copies of
# the bash, Python, Go and Kotlin fixtures of the t1954 parser-research corpus:
# the same file lists, the same bytes, the same executable bits (t1991).
# The Go gate never reads aidocs/ (it is hermetic), so this repository-level
# guard is what notices a research fixture that never reached it.
# Run: bash tests/test_annot_conformance_corpus_sync.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0
. "$PROJECT_DIR/tests/lib/asserts.sh"

CORPUS="$PROJECT_DIR/aidocs/testing_engine/t1954_parser_research/corpus"
COPY="$PROJECT_DIR/goengines/internal/testmap/annot/testdata/conformance"
LANGS=(bash python go kotlin)

# list_files <dir> <lang>: the regular files under <dir>/<lang>, as
# <lang>/<path>, in C-locale order (what comm expects).
list_files() {
    local dir="$1" lang="$2"
    [ -d "$dir/$lang" ] || return 0
    (cd "$dir" && find "$lang" -type f | LC_ALL=C sort)
}

# conformance_drift <corpus_dir> <copy_dir>: one line per difference, nothing
# when the copy is in sync.
conformance_drift() {
    local corpus="$1" copy="$2" lang f a b entry
    for lang in "${LANGS[@]}"; do
        LC_ALL=C comm -23 <(list_files "$corpus" "$lang") <(list_files "$copy" "$lang") | sed 's/^/only-in-research:/'
        LC_ALL=C comm -13 <(list_files "$corpus" "$lang") <(list_files "$copy" "$lang") | sed 's/^/only-in-copy:/'
        while IFS= read -r f; do
            cmp -s "$corpus/$f" "$copy/$f" || echo "content:$f"
            a=0
            b=0
            if [ -x "$corpus/$f" ]; then a=1; fi
            if [ -x "$copy/$f" ]; then b=1; fi
            [ "$a" = "$b" ] || echo "mode:$f"
        done < <(LC_ALL=C comm -12 <(list_files "$corpus" "$lang") <(list_files "$copy" "$lang"))
    done
    while IFS= read -r entry; do
        case "$entry" in
            bash|python|go|kotlin|PROVENANCE) ;;
            *) echo "extra-in-copy:$entry" ;;
        esac
    done < <(find "$copy" -mindepth 1 -maxdepth 1 -exec basename {} \; | LC_ALL=C sort)
}

# --- 1. the real copy is in sync -------------------------------------------
for lang in "${LANGS[@]}"; do
    n_corpus="$(list_files "$CORPUS" "$lang" | grep -c '\.in$' || true)"
    n_copy="$(list_files "$COPY" "$lang" | grep -c '\.in$' || true)"
    assert_eq "$lang: the copy has the corpus's fixture count" "$n_corpus" "$n_copy"
    if [ "$n_corpus" -gt 0 ]; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $lang: no fixtures in $CORPUS/$lang (a vacuous comparison)"
    fi
done
drift="$(conformance_drift "$CORPUS" "$COPY")"
assert_eq "the copied fixtures match the research corpus (refresh: the conformance_test.go header)" "" "$drift"

# PROVENANCE keeps the corpus commit the copy was taken from. Matching contents
# are the contract; the commit is provenance and need not be the newest one.
prov="$(cat "$COPY/PROVENANCE")"
assert_contains_re "PROVENANCE records the corpus commit" '^commit: [0-9a-f]{40}$' "$prov"

# --- 2. negative controls: each kind of drift is reported -------------------
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# fresh_pair: scratch copies of both trees in $TMP/r and $TMP/c.
fresh_pair() {
    rm -rf "$TMP/r" "$TMP/c"
    mkdir -p "$TMP/r"
    for lang in "${LANGS[@]}"; do
        cp -p -r "$CORPUS/$lang" "$TMP/r/"
    done
    cp -p -r "$COPY" "$TMP/c"
}

fresh_pair
assert_eq "control: an untouched scratch pair is in sync" "" "$(conformance_drift "$TMP/r" "$TMP/c")"

fresh_pair
printf 'x\n' > "$TMP/r/go/new_case.go.in"
assert_eq "control: a fixture only in the research corpus" \
    "only-in-research:go/new_case.go.in" "$(conformance_drift "$TMP/r" "$TMP/c")"

fresh_pair
printf 'x\n' > "$TMP/c/bash/stray.sh.in"
assert_eq "control: a fixture only in the copy" \
    "only-in-copy:bash/stray.sh.in" "$(conformance_drift "$TMP/r" "$TMP/c")"

fresh_pair
printf 'x' >> "$TMP/c/python/ordinary.py.in"
assert_eq "control: one changed byte" \
    "content:python/ordinary.py.in" "$(conformance_drift "$TMP/r" "$TMP/c")"

fresh_pair
chmod +x "$TMP/c/kotlin/ordinary.kt.in"
assert_eq "control: a gained executable bit" \
    "mode:kotlin/ordinary.kt.in" "$(conformance_drift "$TMP/r" "$TMP/c")"

fresh_pair
chmod -x "$TMP/c/bash/exec_mode_edit.sh.in"
assert_eq "control: a lost executable bit" \
    "mode:bash/exec_mode_edit.sh.in" "$(conformance_drift "$TMP/r" "$TMP/c")"

fresh_pair
printf 'x\n' > "$TMP/c/README"
assert_eq "control: a stray top-level entry in the copy" \
    "extra-in-copy:README" "$(conformance_drift "$TMP/r" "$TMP/c")"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]] || exit 1
